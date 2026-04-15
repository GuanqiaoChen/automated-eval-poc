"""
Orchestrator Agent
===================
The root Google ADK agent.  It receives a task description from the
runner, decides which automation strategy to use, delegates to the
appropriate sub-agent, and synthesises the final report.

Strategy selection logic
------------------------
  api    → headless, fastest, no GUI dependencies.  Default choice.
  web    → Playwright; requires a display and CAI_TOKEN.
  mobile → Appium; requires a device/emulator and running Appium server.

The orchestrator never calls automation tools directly — it always
delegates to the correct sub-agent via Google ADK's sub_agents mechanism.
"""

from google.adk.agents import LlmAgent

from agents.api_agent import api_agent
from agents.mobile_agent import mobile_agent
from agents.web_agent import web_agent
from config.settings import gemini_config

ORCHESTRATOR_INSTRUCTION = """
You are the Orchestrator for an automated Character AI evaluation system.

Your responsibilities:
1. Parse the user's task to extract:
   - character_id  (Character AI character identifier)
   - messages      (list of strings to send, in order)
   - strategy      ("api" | "web" | "mobile")  — default to "api" if unspecified
2. Delegate the batch run to the appropriate sub-agent:
   - strategy "api"    → api_automation_agent
   - strategy "web"    → web_automation_agent
   - strategy "mobile" → mobile_automation_agent
3. After the sub-agent returns results, produce a clear summary that includes:
   - Which strategy was used and why
   - Total messages sent, success count, failure count
   - Average response latency
   - A table of [Message #, Message (truncated), Response (truncated), Latency, Status]
   - Any errors encountered

Strategy selection guidance
---------------------------
  • Choose "api"    when no browser/device is available, or for CI/batch jobs.
  • Choose "web"    when you need to test the real browser UX or validate UI.
  • Choose "mobile" when you need to test the Android app experience.

Output format
-------------
Always present results in a structured markdown report, then return the
raw result JSON under a collapsible section.

Important rules
---------------
  - Never call automation tools directly from this agent — always delegate.
  - If the sub-agent reports an error, include the error in your summary
    and suggest the most likely fix.
  - Do not retry failed turns automatically; report and move on.
"""

orchestrator_agent = LlmAgent(
    name="orchestrator_agent",
    model=gemini_config.model,
    description="Root orchestrator that routes Character AI automation tasks to sub-agents.",
    instruction=ORCHESTRATOR_INSTRUCTION,
    sub_agents=[api_agent, web_agent, mobile_agent],
)
