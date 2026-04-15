"""
Web Automation Sub-Agent
=========================
A Google ADK LlmAgent that can drive the Character AI website using
Playwright.  The orchestrator delegates web-specific tasks to this agent.
"""

from google.adk.agents import LlmAgent

from config.settings import gemini_config
from tools.web_tool import (
    close_web_session,
    init_web_session,
    send_batch_messages_web,
    send_message_web,
)

WEB_AGENT_INSTRUCTION = """
You are the Web Automation Agent for Character AI.
Your job is to send messages to a Character AI character through its web interface
(character.ai) using Playwright browser automation.

Workflow for a batch run:
1. Call send_batch_messages_web(character_id, messages) — this handles session
   lifecycle internally and returns all turns in one shot.

Workflow for a single message:
1. Call init_web_session(character_id) to launch the browser and navigate to the chat.
2. Call send_message_web(character_id, message) for each message.
3. Call close_web_session(character_id) when done.

Always return the raw JSON result from the tool; do not paraphrase or truncate it.
If a tool returns an error, report it immediately without retrying automatically.
"""

web_agent = LlmAgent(
    name="web_automation_agent",
    model=gemini_config.model,
    description=(
        "Automates Character AI web interface using Playwright. "
        "Use this agent when the automation strategy is 'web'."
    ),
    instruction=WEB_AGENT_INSTRUCTION,
    tools=[
        init_web_session,
        send_message_web,
        close_web_session,
        send_batch_messages_web,
    ],
)
