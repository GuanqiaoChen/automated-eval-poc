"""
main.py — Character AI Automation PoC entry point
===================================================
Usage
-----
    # API strategy (default — no browser required)
    python main.py --strategy api

    # Web strategy (Playwright)
    python main.py --strategy web

    # Mobile strategy (Appium)
    python main.py --strategy mobile

    # Override character
    python main.py --strategy api --character <CHARACTER_ID>

    # Use custom message file
    python main.py --strategy api --messages-file my_messages.txt

Environment variables (set in .env or shell)
---------------------------------------------
    CAI_TOKEN          — Character AI authentication token  (required)
    CAI_CHARACTER_ID   — Target character id                (optional, has default)
    GOOGLE_API_KEY     — Gemini API key for ADK agents      (required)
    GEMINI_MODEL       — Gemini model name                  (default: gemini-2.0-flash)
    PLAYWRIGHT_HEADLESS— "true"/"false"                     (default: true)
    APPIUM_SERVER_URL  — Appium server URL                  (default: http://localhost:4723)
    APPIUM_DEVICE_NAME — ADB device name                    (default: emulator-5554)
"""

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from agents.api_agent import api_agent
from agents.web_agent import web_agent
from agents.mobile_agent import mobile_agent
from config.settings import cai_config, gemini_config
from data.messages import INPUT_MESSAGES
from utils.result_handler import ResultHandler, TurnResult

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

APP_NAME = "characterai_automation_poc"


# -- Argument parsing ----------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Character AI Automation PoC — Google ADK powered"
    )
    p.add_argument(
        "--strategy",
        choices=["api", "web", "mobile"],
        default="api",
        help="Automation strategy (default: api)",
    )
    p.add_argument(
        "--character",
        default=cai_config.character_id,
        help="Character AI character ID",
    )
    p.add_argument(
        "--messages-file",
        type=Path,
        default=None,
        help="Optional .txt file with one message per line (overrides built-in list)",
    )
    p.add_argument(
        "--no-adk",
        action="store_true",
        help="Bypass ADK and call automation tools directly (faster for testing)",
    )
    return p.parse_args()


# -- Message loading -----------------------------------------------------------

def load_messages(messages_file: Path | None) -> list[str]:
    if messages_file is not None:
        texts = messages_file.read_text(encoding="utf-8").splitlines()
        return [t.strip() for t in texts if t.strip()]
    return [m.text for m in INPUT_MESSAGES]


# -- Direct (no-ADK) execution path -------------------------------------------

def run_direct(strategy: str, character_id: str, messages: list[str]) -> None:
    """
    Bypass the ADK LLM layer and call the batch tool functions directly.
    Useful for quick smoke-tests where you do not want to spend Gemini tokens.
    """
    logger.info("Running in direct mode (no ADK)  strategy=%s", strategy)

    if strategy == "api":
        from tools.api_tool import send_batch_messages_api
        result = send_batch_messages_api(character_id, messages)
    elif strategy == "web":
        from tools.web_tool import send_batch_messages_web
        result = send_batch_messages_web(character_id, messages)
    elif strategy == "mobile":
        from tools.mobile_tool import send_batch_messages_mobile
        result = send_batch_messages_mobile(character_id, messages)
    else:
        raise ValueError(f"Unknown strategy: {strategy}")

    handler = ResultHandler(strategy=strategy, character_id=character_id)  # type: ignore[arg-type]

    for turn in result.get("turns", []):
        handler.record(
            TurnResult(
                message_id=turn["index"],
                message_text=turn["message"],
                response_text=turn.get("response_text") or "",
                strategy=strategy,  # type: ignore[arg-type]
                character_id=character_id,
                latency_ms=turn.get("latency_ms", 0.0),
                error=turn.get("error"),
            )
        )

    if result.get("error"):
        logger.error("Top-level error: %s", result["error"])

    handler.save()
    handler.print_summary()


# -- ADK execution path -------------------------------------------------------

_AGENT_MAP = {
    "api": api_agent,
    "web": web_agent,
    "mobile": mobile_agent,
}

async def run_with_adk(strategy: str, character_id: str, messages: list[str]) -> None:
    """
    Run the strategy-specific ADK agent directly, bypassing the orchestrator.
    The strategy is already known from the CLI argument, so no LLM routing needed.
    """
    if not gemini_config.api_key:
        logger.error(
            "GOOGLE_API_KEY is not set. "
            "Get a key from https://aistudio.google.com/app/apikey"
        )
        sys.exit(1)

    agent = _AGENT_MAP[strategy]
    session_service = InMemorySessionService()
    runner = Runner(
        agent=agent,
        app_name=APP_NAME,
        session_service=session_service,
    )

    session = await session_service.create_session(
        app_name=APP_NAME,
        user_id="poc_user",
    )

    task_prompt = (
        f"character_id: {character_id}\n"
        f"messages (in order):\n"
        + "\n".join(f"  {i+1}. {msg}" for i, msg in enumerate(messages))
    )

    logger.info("Sending task to %s …", agent.name)
    logger.debug("Task prompt:\n%s", task_prompt)

    content = types.Content(
        role="user",
        parts=[types.Part(text=task_prompt)],
    )

    final_response = ""
    async for event in runner.run_async(
        user_id="poc_user",
        session_id=session.id,
        new_message=content,
    ):
        if event.is_final_response():
            final_response = event.content.parts[0].text if event.content else ""

    print("\n" + "=" * 70)
    print(f"  {agent.name.upper()} REPORT")
    print("=" * 70)
    print(final_response)
    print("=" * 70 + "\n")


# -- Entry point ---------------------------------------------------------------

def main() -> None:
    args = parse_args()
    messages = load_messages(args.messages_file)

    logger.info(
        "Starting PoC  strategy=%s  character=%s  messages=%d",
        args.strategy,
        args.character,
        len(messages),
    )

    if not cai_config.token and args.strategy != "mobile":
        logger.warning(
            "CAI_TOKEN is not set. API and web strategies require a valid token.\n"
            "See README.md -> 'Getting your Character AI token'."
        )

    if args.no_adk:
        run_direct(args.strategy, args.character, messages)
    else:
        asyncio.run(run_with_adk(args.strategy, args.character, messages))


if __name__ == "__main__":
    main()
