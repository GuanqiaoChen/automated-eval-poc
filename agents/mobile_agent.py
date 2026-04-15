"""
Mobile Automation Sub-Agent
=============================
A Google ADK LlmAgent that drives the Character AI Android application
via Appium.  The orchestrator delegates mobile-specific tasks here.
"""

from google.adk.agents import LlmAgent

from config.settings import gemini_config
from tools.mobile_tool import (
    close_mobile_session,
    init_mobile_session,
    send_batch_messages_mobile,
    send_message_mobile,
)

MOBILE_AGENT_INSTRUCTION = """
You are the Mobile Automation Agent for Character AI.
Your job is to send messages to a Character AI character through its Android
application using Appium and UiAutomator2.

Prerequisites (verify before running):
  • Appium server must be running at the configured APPIUM_SERVER_URL.
  • An Android device or emulator must be connected and have the Character AI
    app installed with the user already logged in.

Workflow for a batch run:
1. Call send_batch_messages_mobile(character_id, messages) — handles the full
   session lifecycle and returns all turns.

Workflow for a single message:
1. Call init_mobile_session(character_id) to launch the app and navigate to chat.
2. Call send_message_mobile(character_id, message) for each message.
3. Call close_mobile_session(character_id) when finished.

Always return the raw JSON from the tool.  If init fails with a connection
error, remind the user to start the Appium server and connect a device.
"""

mobile_agent = LlmAgent(
    name="mobile_automation_agent",
    model=gemini_config.model,
    description=(
        "Automates Character AI Android app using Appium/UiAutomator2. "
        "Use this agent when the automation strategy is 'mobile'."
    ),
    instruction=MOBILE_AGENT_INSTRUCTION,
    tools=[
        init_mobile_session,
        send_message_mobile,
        close_mobile_session,
        send_batch_messages_mobile,
    ],
)
