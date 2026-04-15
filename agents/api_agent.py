"""
API Automation Sub-Agent
==========================
A Google ADK LlmAgent that interacts with Character AI through the
reverse-engineered unofficial API (characterai Python package).
This is the fastest and most reliable strategy for headless automation.
"""

from google.adk.agents import LlmAgent

from config.settings import gemini_config
from tools.api_tool import (
    get_character_info,
    init_api_session,
    send_batch_messages_api,
    send_message_api,
)

API_AGENT_INSTRUCTION = """
You are the API Automation Agent for Character AI.
Your job is to send messages to a Character AI character through the
unofficial API — no browser or device required.

Typical workflow for a batch run:
1. (Optional) Call get_character_info(character_id) to fetch metadata.
2. Call send_batch_messages_api(character_id, messages) — this handles the
   full conversation session and returns all turns in one result dict.

Typical workflow for a single message:
1. Call init_api_session(character_id) to start a conversation.  Note the chat_id.
2. Call send_message_api(character_id, chat_id, message) for each turn.

Always return the complete tool result as-is. If the token is missing,
tell the user to set the CAI_TOKEN environment variable (see README.md).
"""

api_agent = LlmAgent(
    name="api_automation_agent",
    model=gemini_config.model,
    description=(
        "Interacts with Character AI through the unofficial API. "
        "Fastest strategy — no browser needed. "
        "Use this agent when strategy is 'api'."
    ),
    instruction=API_AGENT_INSTRUCTION,
    tools=[
        get_character_info,
        init_api_session,
        send_message_api,
        send_batch_messages_api,
    ],
)
