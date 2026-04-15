"""
Configuration settings for the Character AI automation agent system.

All secrets are loaded from environment variables or a .env file.
Never hard-code credentials in source.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
RESULTS_DIR = BASE_DIR / "results"
RESULTS_DIR.mkdir(exist_ok=True)


@dataclass
class CharacterAIConfig:
    # Authentication token — get from Character AI web app:
    #   DevTools → Application → Local Storage → char_token
    #   OR DevTools → Network → any /api/trpc/ request → Authorization header
    token: str = field(default_factory=lambda: os.getenv("CAI_TOKEN", ""))

    # Default character to chat with (Albert Einstein on Character AI)
    character_id: str = field(
        default_factory=lambda: os.getenv(
            "CAI_CHARACTER_ID", "iP7_APzHqjMnZOiGZ9_aFnZS_y0snoRrAXFLAwtfEJQ"
        )
    )

    # Character AI base URLs
    web_url: str = "https://character.ai"
    api_base: str = "https://neo.character.ai"


@dataclass
class PlaywrightConfig:
    headless: bool = field(
        default_factory=lambda: os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() == "true"
    )
    slow_mo: int = 100          # ms between actions — helps avoid bot detection
    timeout: int = 30_000       # ms per action
    viewport_width: int = 1280
    viewport_height: int = 800
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )


@dataclass
class AppiumConfig:
    server_url: str = field(
        default_factory=lambda: os.getenv("APPIUM_SERVER_URL", "http://localhost:4723")
    )
    platform_name: str = "Android"
    device_name: str = field(
        default_factory=lambda: os.getenv("APPIUM_DEVICE_NAME", "emulator-5554")
    )
    app_package: str = "com.character.ai"
    app_activity: str = "com.character.ai.MainActivity"
    automation_name: str = "UiAutomator2"
    implicit_wait: int = 10     # seconds
    new_command_timeout: int = 300


@dataclass
class GeminiConfig:
    # Gemini model used by the ADK agents
    model: str = field(
        default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    )
    api_key: str = field(
        default_factory=lambda: os.getenv("GOOGLE_API_KEY", "")
    )


# Singleton instances used throughout the project
cai_config = CharacterAIConfig()
playwright_config = PlaywrightConfig()
appium_config = AppiumConfig()
gemini_config = GeminiConfig()
