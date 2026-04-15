"""
Character AI – Web Automation Tool
=====================================
Strategy: Browser automation via Playwright (async, Chromium)
Install : pip install playwright && playwright install chromium

Flow
----
1.  Launch a Chromium browser (headless by default).
2.  Inject the CAI auth token into localStorage so the site treats the
    session as authenticated — no username/password flow needed.
3.  Navigate to the character's chat page.
4.  For each message:
      a. Locate the message input (contenteditable div or textarea).
      b. Type the message and press Enter / click Send.
      c. Wait for the character's reply bubble to appear and stabilise.
      d. Extract and return the reply text.
5.  Close the browser.

Token injection details
-----------------------
Character AI stores authentication state in localStorage under the key
`char_token`.  By calling  page.evaluate()  before the first navigation
we can pre-seed a session without ever going through the login page.

Selector notes (as of early 2025)
----------------------------------
The CAI SPA uses Tailwind/CSS-in-JS and does not expose stable `data-testid`
attributes.  We use a combination of:
  - ARIA roles  (role="textbox")
  - Accessible labels that are less likely to change than class names
  - Fallback XPath expressions

These selectors may need updating if CAI significantly revamps its UI.
"""

import asyncio
import logging
import time
from typing import Any

from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    async_playwright,
)

from config.settings import cai_config, playwright_config

logger = logging.getLogger(__name__)

# -- Selectors ----------------------------------------------------------------
# Order = priority.  The tool tries each in sequence and uses the first match.

MESSAGE_INPUT_SELECTORS = [
    'div[role="textbox"]',
    'textarea[placeholder*="message" i]',
    'textarea[placeholder*="Message" i]',
    'textarea[data-testid="message-input"]',
    'div[contenteditable="true"]',
]

SEND_BUTTON_SELECTORS = [
    'button[aria-label*="send" i]',
    'button[data-testid="send-button"]',
    'button[type="submit"]',
]

# The most-recently-added character message bubble
CHAR_RESPONSE_SELECTORS = [
    # The last message row that is NOT authored by the user
    'div[data-testid="message-row"]:last-child div[data-testid="message-text"]',
    # Fallback: any paragraph inside the chat area
    'div[class*="CharacterMessage"]:last-child p',
    'p[data-testid="character-message"]:last-of-type',
]

CHAT_PAGE_READY_SELECTOR = 'div[role="textbox"], textarea'


# -- Browser lifecycle helpers ------------------------------------------------

async def _create_context(p: Playwright) -> tuple[Browser, BrowserContext]:
    browser = await p.chromium.launch(
        headless=playwright_config.headless,
        slow_mo=playwright_config.slow_mo,
        args=[
            "--no-sandbox",
            "--disable-blink-features=AutomationControlled",
        ],
    )
    context = await browser.new_context(
        viewport={
            "width": playwright_config.viewport_width,
            "height": playwright_config.viewport_height,
        },
        user_agent=playwright_config.user_agent,
        locale="en-US",
    )
    # Hide webdriver fingerprint
    await context.add_init_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )
    return browser, context


async def _inject_auth_token(page: Page, token: str) -> None:
    """
    Seed the Character AI auth token into localStorage.
    This must be called BEFORE the page navigates to character.ai.
    """
    # We navigate to the origin first (blank) so localStorage is accessible
    await page.goto(cai_config.web_url, wait_until="domcontentloaded")
    await page.evaluate(
        """(token) => {
            localStorage.setItem('char_token', token);
            // Some CAI versions use this key
            localStorage.setItem('CAI_TOKEN', token);
        }""",
        token,
    )
    logger.debug("Auth token injected into localStorage")


async def _find_element(page: Page, selectors: list[str], timeout: int = 5_000):
    """Return the first element matching any of the given selectors."""
    for sel in selectors:
        try:
            el = await page.wait_for_selector(sel, timeout=timeout)
            if el:
                return el
        except Exception:
            continue
    return None


async def _wait_for_response(page: Page, prev_count: int, timeout: int = 30_000) -> str:
    """
    Wait until a new character message bubble appears, then return its text.

    Strategy:
      - Poll for a new element count rather than a fixed selector so we detect
        the reply even if the exact selector changes.
      - Once a new bubble appears we wait an extra second for it to finish
        streaming before reading the text.
    """
    deadline = time.monotonic() + timeout / 1000
    while time.monotonic() < deadline:
        await asyncio.sleep(0.5)
        try:
            # Count all paragraphs in character messages
            count = await page.evaluate(
                """() => document.querySelectorAll(
                    'div[data-testid="message-row"], div[class*="CharacterMessage"]'
                ).length"""
            )
            if count > prev_count:
                # Wait for streaming to finish (typing indicator disappears)
                await asyncio.sleep(1.5)
                break
        except Exception:
            pass

    # Extract the text of the last character message
    for sel in CHAR_RESPONSE_SELECTORS:
        try:
            el = await page.query_selector(sel)
            if el:
                text = await el.inner_text()
                if text.strip():
                    return text.strip()
        except Exception:
            continue

    # Final fallback: grab all visible text from the chat area
    try:
        chat_area = await page.query_selector('div[class*="chat"], main')
        if chat_area:
            all_text = await chat_area.inner_text()
            lines = [l.strip() for l in all_text.splitlines() if l.strip()]
            if lines:
                return lines[-1]
    except Exception:
        pass

    return "[response extraction failed]"


# -- ADK tool functions -------------------------------------------------------

def init_web_session(character_id: str) -> dict[str, Any]:
    """
    Open a Playwright browser, authenticate, and navigate to a Character AI
    character chat page.  Call this once before send_message_web.

    Args:
        character_id: Character AI character identifier.

    Returns:
        A dict with keys: status, greeting, error.
    """
    # We store the running context in a module-level registry so the ADK tool
    # functions (which are synchronous wrappers) can share the same browser.
    # In production you would use dependency injection instead.
    return asyncio.run(_init_web_session_async(character_id))


async def _init_web_session_async(character_id: str) -> dict[str, Any]:
    try:
        p = await async_playwright().start()
        browser, context = await _create_context(p)
        page = await context.new_page()

        if cai_config.token:
            await _inject_auth_token(page, cai_config.token)

        chat_url = f"{cai_config.web_url}/chat/{character_id}"
        await page.goto(chat_url, wait_until="networkidle", timeout=playwright_config.timeout)

        # Wait for chat to load
        el = await _find_element(page, [CHAT_PAGE_READY_SELECTOR], timeout=15_000)
        if not el:
            raise RuntimeError("Chat page did not finish loading")

        # Store context for later use — simple module-level approach for PoC
        _WEB_SESSIONS[character_id] = {
            "playwright": p,
            "browser": browser,
            "context": context,
            "page": page,
        }

        logger.info("Web session initialised for character %s", character_id)
        return {"status": "ready", "greeting": None, "error": None}

    except Exception as exc:
        logger.error("init_web_session failed: %s", exc)
        return {"status": "error", "greeting": None, "error": str(exc)}


# Module-level registry of open browser sessions (PoC simplification)
_WEB_SESSIONS: dict[str, dict] = {}


def send_message_web(character_id: str, message: str) -> dict[str, Any]:
    """
    Send a single message to a Character AI character via the web interface
    and return the character's response.

    init_web_session must be called first.

    Args:
        character_id: Character AI character identifier.
        message: The text message to send.

    Returns:
        A dict with keys: response_text, latency_ms, error.
    """
    return asyncio.run(_send_message_web_async(character_id, message))


async def _send_message_web_async(character_id: str, message: str) -> dict[str, Any]:
    session = _WEB_SESSIONS.get(character_id)
    if not session:
        return {
            "response_text": None,
            "latency_ms": 0.0,
            "error": "Session not initialised. Call init_web_session first.",
        }

    page: Page = session["page"]
    t0 = time.monotonic()

    try:
        # Count existing character messages before sending
        prev_count = await page.evaluate(
            """() => document.querySelectorAll(
                'div[data-testid="message-row"], div[class*="CharacterMessage"]'
            ).length"""
        )

        # Find and fill the message input
        input_el = await _find_element(page, MESSAGE_INPUT_SELECTORS, timeout=10_000)
        if not input_el:
            raise RuntimeError("Message input not found on page")

        await input_el.click()
        await input_el.fill(message)
        await asyncio.sleep(0.2)

        # Try send button first, then fall back to Enter key
        send_btn = await _find_element(page, SEND_BUTTON_SELECTORS, timeout=2_000)
        if send_btn:
            await send_btn.click()
        else:
            await input_el.press("Enter")

        response_text = await _wait_for_response(
            page, prev_count, timeout=playwright_config.timeout
        )
        latency_ms = (time.monotonic() - t0) * 1000

        logger.info("[WEB] message sent  latency=%.0fms", latency_ms)
        return {
            "response_text": response_text,
            "latency_ms": round(latency_ms, 1),
            "error": None,
        }

    except Exception as exc:
        latency_ms = (time.monotonic() - t0) * 1000
        logger.error("send_message_web failed: %s", exc)
        return {
            "response_text": None,
            "latency_ms": round(latency_ms, 1),
            "error": str(exc),
        }


def close_web_session(character_id: str) -> dict[str, Any]:
    """
    Close the Playwright browser for the given character session.

    Args:
        character_id: Character AI character identifier.

    Returns:
        A dict with keys: status, error.
    """
    return asyncio.run(_close_web_session_async(character_id))


async def _close_web_session_async(character_id: str) -> dict[str, Any]:
    session = _WEB_SESSIONS.pop(character_id, None)
    if not session:
        return {"status": "not_found", "error": None}
    try:
        await session["browser"].close()
        await session["playwright"].stop()
        return {"status": "closed", "error": None}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


def send_batch_messages_web(
    character_id: str,
    messages: list[str],
) -> dict[str, Any]:
    """
    Initialise a web session, send all messages in order, close the session,
    and return the collected turns.

    Args:
        character_id: Character AI character identifier.
        messages: Ordered list of message strings.

    Returns:
        A dict with keys: turns, total_messages, successful, failed, error.
    """
    return asyncio.run(_send_batch_messages_web_async(character_id, messages))


async def _send_batch_messages_web_async(
    character_id: str,
    messages: list[str],
) -> dict[str, Any]:
    init_result = await _init_web_session_async(character_id)
    if init_result["error"]:
        return {
            "turns": [],
            "total_messages": 0,
            "successful": 0,
            "failed": 0,
            "error": init_result["error"],
        }

    turns = []
    for i, msg_text in enumerate(messages, start=1):
        result = await _send_message_web_async(character_id, msg_text)
        turns.append({
            "index": i,
            "message": msg_text,
            "response_text": result["response_text"],
            "latency_ms": result["latency_ms"],
            "error": result["error"],
        })
        logger.info(
            "[WEB] %d/%d  latency=%.0fms  err=%s",
            i, len(messages), result["latency_ms"], result["error"],
        )
        await asyncio.sleep(1.0)   # polite delay between messages

    await _close_web_session_async(character_id)

    successful = sum(1 for t in turns if t["error"] is None)
    return {
        "turns": turns,
        "total_messages": len(turns),
        "successful": successful,
        "failed": len(turns) - successful,
        "error": None,
    }
