"""
Character AI – API Automation Tool
====================================
Strategy: Reverse-engineered unofficial API
Library : characterai  (pip install characterai)

Character AI uses a set of tRPC-over-HTTP(S) and WebSocket endpoints.
The `characterai` Python package (by kramcat) wraps these so we can
drive a conversation without any browser.

How the token is obtained:
  1. Log in to https://character.ai in a browser.
  2. Open DevTools → Application → Local Storage → https://character.ai
  3. Copy the value of  `char_token`
  4. Export it as the env-var  CAI_TOKEN

Alternatively, intercept a /api/trpc/* request in the Network tab and
copy the  Authorization: Token <value>  header.
"""

import asyncio
import logging
import time
from typing import Any

from characterai import aiocai

from config.settings import cai_config

logger = logging.getLogger(__name__)


# -- low-level helpers ---------------------------------------------------------

async def _get_client() -> aiocai.Client:
    """Return an authenticated async Character AI client."""
    if not cai_config.token:
        raise ValueError(
            "CAI_TOKEN is not set. "
            "See tools/api_tool.py docstring for instructions."
        )
    return aiocai.Client(cai_config.token)


# -- ADK tool functions -------------------------------------------------------
# These are plain Python functions with docstrings - Google ADK picks them up
# automatically and converts them into callable tools for the LlmAgent.

def get_character_info(character_id: str) -> dict[str, Any]:
    """
    Fetch public metadata for a Character AI character.

    Args:
        character_id: The unique character identifier (from the character's URL).

    Returns:
        A dict with keys: name, title, description, num_interactions, error.
    """
    async def _run() -> dict:
        try:
            client = await _get_client()
            char = await client.get_char(character_id)
            return {
                "name": getattr(char, "name", "unknown"),
                "title": getattr(char, "title", ""),
                "description": getattr(char, "description", ""),
                "num_interactions": getattr(char, "num_interactions", 0),
                "error": None,
            }
        except Exception as exc:
            logger.error("get_character_info failed: %s", exc)
            return {"error": str(exc)}

    return asyncio.run(_run())


def init_api_session(character_id: str) -> dict[str, Any]:
    """
    Start a new conversation session with a Character AI character via the API.

    Args:
        character_id: The unique character identifier.

    Returns:
        A dict with keys: chat_id, greeting, error.
        chat_id must be passed to subsequent send_message_api calls.
    """
    async def _run() -> dict:
        try:
            client = await _get_client()
            me = await client.get_me()
            async with await client.connect() as chat:
                new_chat, greeting = await chat.new_chat(character_id, me.id)
                return {
                    "chat_id": new_chat.chat_id,
                    "greeting": greeting.text,
                    "error": None,
                }
        except Exception as exc:
            logger.error("init_api_session failed: %s", exc)
            return {"chat_id": None, "greeting": None, "error": str(exc)}

    return asyncio.run(_run())


def send_message_api(
    character_id: str,
    chat_id: str,
    message: str,
) -> dict[str, Any]:
    """
    Send a single message to a Character AI character and return the response.

    Args:
        character_id: The unique character identifier.
        chat_id: The active chat session id (from init_api_session).
        message: The text message to send.

    Returns:
        A dict with keys: response_text, latency_ms, error.
    """
    async def _run() -> dict:
        try:
            client = await _get_client()
            t0 = time.monotonic()
            async with await client.connect() as chat:
                reply = await chat.send_message(character_id, chat_id, message)
            latency_ms = (time.monotonic() - t0) * 1000
            return {
                "response_text": reply.text,
                "latency_ms": round(latency_ms, 1),
                "error": None,
            }
        except Exception as exc:
            logger.error("send_message_api failed: %s", exc)
            return {"response_text": None, "latency_ms": 0.0, "error": str(exc)}

    return asyncio.run(_run())


def send_batch_messages_api(
    character_id: str,
    messages: list[str],
) -> dict[str, Any]:
    """
    Send a list of messages sequentially to a character and collect all responses.

    This is the primary batch-execution tool.  It opens one session, sends every
    message in order, and returns a list of turn dicts.

    Args:
        character_id: The unique character identifier.
        messages: Ordered list of message strings to send.

    Returns:
        A dict with keys:
          - turns: list of {message, response_text, latency_ms, error}
          - total_messages, successful, failed
          - error (top-level, if session init failed)
    """
    async def _run() -> dict:
        try:
            client = await _get_client()
            me = await client.get_me()

            turns = []
            async with await client.connect() as chat:
                # Create a fresh chat session
                new_chat, greeting = await chat.new_chat(character_id, me.id)
                logger.info(
                    "API session started  chat_id=%s  greeting=%r",
                    new_chat.chat_id,
                    greeting.text[:80],
                )

                for i, msg_text in enumerate(messages, start=1):
                    t0 = time.monotonic()
                    try:
                        reply = await chat.send_message(
                            character_id, new_chat.chat_id, msg_text
                        )
                        latency_ms = (time.monotonic() - t0) * 1000
                        turns.append({
                            "index": i,
                            "message": msg_text,
                            "response_text": reply.text,
                            "latency_ms": round(latency_ms, 1),
                            "error": None,
                        })
                        logger.info(
                            "[API] %d/%d sent  latency=%.0fms",
                            i, len(messages), latency_ms,
                        )
                        # Small courtesy delay — avoid rate-limiting
                        await asyncio.sleep(0.5)
                    except Exception as turn_exc:
                        latency_ms = (time.monotonic() - t0) * 1000
                        logger.error("[API] msg %d failed: %s", i, turn_exc)
                        turns.append({
                            "index": i,
                            "message": msg_text,
                            "response_text": None,
                            "latency_ms": round(latency_ms, 1),
                            "error": str(turn_exc),
                        })

            successful = sum(1 for t in turns if t["error"] is None)
            return {
                "turns": turns,
                "total_messages": len(turns),
                "successful": successful,
                "failed": len(turns) - successful,
                "error": None,
            }
        except Exception as exc:
            logger.error("send_batch_messages_api top-level failure: %s", exc)
            return {
                "turns": [],
                "total_messages": 0,
                "successful": 0,
                "failed": 0,
                "error": str(exc),
            }

    return asyncio.run(_run())
