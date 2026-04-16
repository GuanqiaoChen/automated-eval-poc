"""
Character AI – Mobile Automation Tool
========================================
Strategy : Appium (UiAutomator2 driver) controlling the Character AI Android app
Install  : pip install Appium-Python-Client
Requires :
  • Appium server  ≥ 2.0   (npm install -g appium)
  • UiAutomator2 driver    (appium driver install uiautomator2)
  • Android device or emulator with Character AI app installed and signed in
  • ANDROID_HOME / ADB path configured

Quick-start Appium server (from a terminal):
  appium --address 0.0.0.0 --port 4723

How to find correct element locators:
  appium doctor --android
  Use Appium Inspector to introspect live element trees on the device.

Tested against Character AI version 2.x on Android 12+.
Locators are identified by resource-id / content-desc and are more stable
than XPath but may still require updates across app versions.
"""

import logging
import time
from typing import Any

from appium import webdriver as appium_driver
from appium.options.android.uiautomator2.base import UiAutomator2Options
from appium.webdriver.common.appiumby import AppiumBy
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from config.settings import appium_config, cai_config

logger = logging.getLogger(__name__)

# -- Element locators ---------------------------------------------------------
# These were captured with Appium Inspector on CAI 2.x / Android 12.
# Adjust if the app is updated.

_LOC = {
    # Home screen — React Native app uses accessibility labels, not resource-ids
    "search_fab":       (AppiumBy.ACCESSIBILITY_ID, "Search"),
    "search_input":     (AppiumBy.XPATH, '//android.widget.EditText'),

    # Character profile / chat list
    "start_chat_btn":   (AppiumBy.ACCESSIBILITY_ID, "Start chatting"),
    "chat_item":        (AppiumBy.XPATH,
                         '//android.view.ViewGroup[@content-desc]'),

    # Active chat — EditText is the message input in React Native
    "msg_input":        (AppiumBy.XPATH, '//android.widget.EditText'),
    "send_btn":         (AppiumBy.XPATH,
                         '//*[@content-desc="Send" or @content-desc="Send message"'
                         ' or @content-desc="send" or @content-desc="submit"]'),
    "msg_list":         (AppiumBy.XPATH, '//*[@scrollable="true"]'),
    # Last non-empty TextView that isn't the input itself
    "last_ai_msg":      (AppiumBy.XPATH,
                         '(//android.widget.TextView[string-length(@text) > 0])[last()]'),
    # Typing indicator (accessibility label may vary)
    "typing_indicator": (AppiumBy.XPATH,
                         '//*[contains(@content-desc,"typing") or contains(@content-desc,"Typing")]'),
}


# -- Driver lifecycle ---------------------------------------------------------

class MobileSession:
    """Wraps a single Appium driver session."""

    def __init__(self) -> None:
        opts = UiAutomator2Options()
        opts.platform_name = appium_config.platform_name
        opts.device_name = appium_config.device_name
        opts.app_package = appium_config.app_package
        opts.app_activity = appium_config.app_activity
        opts.automation_name = appium_config.automation_name
        opts.no_reset = True        # keep existing login / app data
        opts.new_command_timeout = appium_config.new_command_timeout

        logger.info("Connecting to Appium at %s …", appium_config.server_url)
        self.driver = appium_driver.Remote(
            command_executor=appium_config.server_url,
            options=opts,
        )
        self.driver.implicitly_wait(appium_config.implicit_wait)
        logger.info("Appium session started  session_id=%s", self.driver.session_id)

    def wait_for(self, locator: tuple, timeout: int = 20) -> Any:
        return WebDriverWait(self.driver, timeout).until(
            EC.presence_of_element_located(locator)
        )

    def wait_gone(self, locator: tuple, timeout: int = 60) -> None:
        WebDriverWait(self.driver, timeout).until(
            EC.invisibility_of_element_located(locator)
        )

    def quit(self) -> None:
        try:
            self.driver.quit()
        except Exception:
            pass


# Module-level session registry
_MOBILE_SESSIONS: dict[str, MobileSession] = {}


# -- Navigation helpers -------------------------------------------------------


def dump_ui(session: MobileSession) -> None:
    """Print all visible element resource-ids and text — useful for finding real locators."""
    source = session.driver.page_source
    import re
    ids = re.findall(r'resource-id="([^"]+)"', source)
    texts = re.findall(r'text="([^"]{1,40})"', source)
    logger.info("=== UI DUMP resource-ids ===\n%s", "\n".join(sorted(set(ids))))
    logger.info("=== UI DUMP texts ===\n%s", "\n".join(t for t in texts if t))


def _navigate_to_character(session: MobileSession, character_id: str) -> None:
    """
    Deep-link directly into the character's chat.
    Tries HTTPS app link first, then falls back to home screen navigation.
    """
    deep_link = f"https://character.ai/chat/{character_id}"
    try:
        session.driver.execute_script(
            "mobile: deepLink",
            {"url": deep_link, "package": appium_config.app_package},
        )
        logger.debug("Deep-linked to %s", deep_link)
        time.sleep(2)
        # Wait for message input to appear (chat screen loaded)
        session.wait_for(_LOC["msg_input"], timeout=15)
    except Exception as exc:
        logger.warning("Deep link failed (%s), trying home screen navigation", exc)
        _navigate_via_home(session, character_id)


def _navigate_via_home(session: MobileSession, character_id: str) -> None:
    """Fallback navigation: open the search and find the character by id."""
    session.driver.activate_app(appium_config.app_package)
    time.sleep(2)
    dump_ui(session)  # log actual element IDs to help fix locators

    search = session.wait_for(_LOC["search_fab"])
    search.click()

    search_input = session.wait_for(_LOC["search_input"])
    search_input.send_keys(character_id)

    # Tap first result
    first = session.wait_for(_LOC["chat_item"], timeout=10)
    first.click()

    session.wait_for(_LOC["msg_input"], timeout=15)


def _get_last_ai_message_count(session: MobileSession) -> int:
    """Return number of AI message elements currently visible."""
    try:
        return len(session.driver.find_elements(*_LOC["last_ai_msg"]))
    except Exception:
        return 0


def _read_last_ai_message(session: MobileSession) -> str:
    """Scroll to bottom and extract the text of the last AI message bubble."""
    # Scroll to the bottom of the message list
    try:
        msg_list = session.driver.find_element(*_LOC["msg_list"])
        session.driver.execute_script(
            "mobile: scroll",
            {"element": msg_list.id, "direction": "down"},
        )
    except Exception:
        pass

    try:
        el = session.driver.find_element(*_LOC["last_ai_msg"])
        return el.text.strip()
    except NoSuchElementException:
        return "[response extraction failed]"


def _wait_for_typing_done(session: MobileSession, prev_count: int, timeout: int = 60) -> str:
    """Wait until the typing indicator disappears, then read the response."""
    deadline = time.monotonic() + timeout
    # First wait for a new message to appear
    while time.monotonic() < deadline:
        count = _get_last_ai_message_count(session)
        if count > prev_count:
            break
        time.sleep(0.5)

    # Then wait for typing indicator to vanish (response fully rendered)
    try:
        session.wait_gone(_LOC["typing_indicator"], timeout=int(deadline - time.monotonic()))
    except Exception:
        pass

    time.sleep(0.5)  # small buffer for final render
    return _read_last_ai_message(session)


# -- ADK tool functions -------------------------------------------------------

def init_mobile_session(character_id: str) -> dict[str, Any]:
    """
    Launch the Character AI Android app via Appium and navigate to the
    specified character's chat screen.

    Prerequisites:
      - Appium server running at APPIUM_SERVER_URL (default: http://localhost:4723)
      - Android device/emulator connected with the Character AI app installed
        and the user already logged in (no_reset=True preserves login state)

    Args:
        character_id: Character AI character identifier.

    Returns:
        A dict with keys: status, error.
    """
    try:
        session = MobileSession()
        _navigate_to_character(session, character_id)
        _MOBILE_SESSIONS[character_id] = session
        logger.info("Mobile session ready for character %s", character_id)
        return {"status": "ready", "error": None}
    except Exception as exc:
        logger.error("init_mobile_session failed: %s", exc)
        return {"status": "error", "error": str(exc)}


def send_message_mobile(character_id: str, message: str) -> dict[str, Any]:
    """
    Send a single message via the Character AI Android app and return the response.

    init_mobile_session must be called first.

    Args:
        character_id: Character AI character identifier.
        message: The text message to send.

    Returns:
        A dict with keys: response_text, latency_ms, error.
    """
    session = _MOBILE_SESSIONS.get(character_id)
    if not session:
        return {
            "response_text": None,
            "latency_ms": 0.0,
            "error": "Session not initialised. Call init_mobile_session first.",
        }

    t0 = time.monotonic()
    try:
        prev_count = _get_last_ai_message_count(session)

        msg_input = session.wait_for(_LOC["msg_input"], timeout=10)
        msg_input.clear()
        msg_input.send_keys(message)

        # Try send button first; fall back to Enter key (more reliable on React Native)
        try:
            send_btn = session.wait_for(_LOC["send_btn"], timeout=3)
            send_btn.click()
        except Exception:
            msg_input.send_keys("\n")

        response_text = _wait_for_typing_done(session, prev_count, timeout=60)
        latency_ms = (time.monotonic() - t0) * 1000

        logger.info("[MOB] message sent  latency=%.0fms", latency_ms)
        return {
            "response_text": response_text,
            "latency_ms": round(latency_ms, 1),
            "error": None,
        }

    except (TimeoutException, WebDriverException, NoSuchElementException) as exc:
        latency_ms = (time.monotonic() - t0) * 1000
        logger.error("send_message_mobile failed: %s", exc)
        return {
            "response_text": None,
            "latency_ms": round(latency_ms, 1),
            "error": str(exc),
        }


def close_mobile_session(character_id: str) -> dict[str, Any]:
    """
    Close the Appium session for the given character.

    Args:
        character_id: Character AI character identifier.

    Returns:
        A dict with keys: status, error.
    """
    session = _MOBILE_SESSIONS.pop(character_id, None)
    if not session:
        return {"status": "not_found", "error": None}
    try:
        session.quit()
        return {"status": "closed", "error": None}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


def send_batch_messages_mobile(
    character_id: str,
    messages: list[str],
) -> dict[str, Any]:
    """
    Open a mobile session, send all messages in order, close the session,
    and return the collected turns.

    Args:
        character_id: Character AI character identifier.
        messages: Ordered list of message strings.

    Returns:
        A dict with keys: turns, total_messages, successful, failed, error.
    """
    init_res = init_mobile_session(character_id)
    if init_res["error"]:
        return {
            "turns": [],
            "total_messages": 0,
            "successful": 0,
            "failed": 0,
            "error": init_res["error"],
        }

    turns = []
    for i, msg_text in enumerate(messages, start=1):
        result = send_message_mobile(character_id, msg_text)
        turns.append({
            "index": i,
            "message": msg_text,
            "response_text": result["response_text"],
            "latency_ms": result["latency_ms"],
            "error": result["error"],
        })
        logger.info(
            "[MOB] %d/%d  latency=%.0fms  err=%s",
            i, len(messages), result["latency_ms"], result["error"],
        )
        time.sleep(1.5)   # polite delay

    close_mobile_session(character_id)

    successful = sum(1 for t in turns if t["error"] is None)
    return {
        "turns": turns,
        "total_messages": len(turns),
        "successful": successful,
        "failed": len(turns) - successful,
        "error": None,
    }
