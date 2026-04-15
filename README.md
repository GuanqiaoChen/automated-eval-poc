# Character AI Automation PoC — Google ADK

Proof of concept demonstrating three complementary strategies for
programmatically sending messages to a **Character AI** character and
capturing responses.  The whole system is orchestrated by a
**Google ADK** multi-agent pipeline backed by Gemini 2.0 Flash.

---

## Architecture overview

```
main.py
  └─ Runner (Google ADK)
       └─ OrchestratorAgent          ← root LlmAgent, routes tasks
            ├─ ApiAutomationAgent    ← sub-agent: unofficial API
            │    └─ tools/api_tool.py   (characterai package)
            ├─ WebAutomationAgent    ← sub-agent: Playwright browser
            │    └─ tools/web_tool.py   (playwright)
            └─ MobileAutomationAgent ← sub-agent: Appium Android
                 └─ tools/mobile_tool.py (Appium-Python-Client)
```

### Strategy comparison

| Strategy | Speed | Dependencies           | Requires UI | Best for                     |
|----------|-------|------------------------|-------------|------------------------------|
| `api`    | ★★★   | `characterai` package  | No          | CI, batch, headless servers  |
| `web`    | ★★    | Playwright, Chromium   | Yes (hidden) | Browser UX validation        |
| `mobile` | ★     | Appium, Android device | Yes         | Mobile app testing           |

---

## Quick start

### 1 — Prerequisites

```bash
python -m pip install -r requirements.txt
playwright install chromium          # web strategy only
```

For the **mobile** strategy you also need:
```bash
npm install -g appium
appium driver install uiautomator2
# connect an Android device or start an emulator, then:
appium --address 0.0.0.0 --port 4723
```

### 2 — Configuration

```bash
cp .env.example .env
# edit .env and fill in CAI_TOKEN and GOOGLE_API_KEY
```

#### Getting your Character AI token

1. Open [character.ai](https://character.ai) in Chrome and log in.
2. Press **F12** → **Application** → **Local Storage** → `https://character.ai`.
3. Copy the value of `char_token`.

Alternatively, open **Network** → filter requests by `trpc` → pick any request
→ **Request Headers** → copy the value after `Authorization: Token `.

#### Getting a Gemini API key

1. Visit [Google AI Studio](https://aistudio.google.com/app/apikey).
2. Click **Create API key** and copy the value.
3. Paste it as `GOOGLE_API_KEY` in your `.env`.

### 3 — Run

```bash
# API strategy (recommended — no browser required)
python main.py --strategy api

# Web strategy
python main.py --strategy web --no-adk   # direct mode (no Gemini tokens used)
python main.py --strategy web            # full ADK orchestrator

# Mobile strategy  (requires Appium server + device)
python main.py --strategy mobile

# Override target character
python main.py --strategy api --character <CHARACTER_ID>

# Use a custom message list (one message per line)
python main.py --strategy api --messages-file my_questions.txt
```

The `--no-adk` flag bypasses the Gemini orchestrator and calls the tool functions
directly.  This is faster and costs no API credits — useful for quick smoke tests.

---

## Project layout

```
.
├── agents/
│   ├── orchestrator.py     # Root ADK LlmAgent — routes tasks to sub-agents
│   ├── api_agent.py        # API strategy sub-agent
│   ├── web_agent.py        # Web strategy sub-agent
│   └── mobile_agent.py     # Mobile strategy sub-agent
├── tools/
│   ├── api_tool.py         # characterai package wrappers (ADK tool functions)
│   ├── web_tool.py         # Playwright automation functions
│   └── mobile_tool.py      # Appium automation functions
├── config/
│   └── settings.py         # Centralised config (reads from .env)
├── data/
│   └── messages.py         # 15 sample input messages
├── utils/
│   └── result_handler.py   # Collects turns → JSON report
├── results/                # Auto-created; JSON session reports written here
├── main.py                 # Entry point + CLI
├── requirements.txt
└── .env.example
```

---

## How each strategy works

### API strategy (`api_tool.py`)

Character AI exposes an unofficial WebSocket-based API that the official
web and mobile clients use.  The Python package `characterai` (by kramcat)
wraps this API.  We authenticate with the user's `CAI_TOKEN`, open a new
chat session with the target character, and send all messages over the same
WebSocket connection.

**No browser or device needed.**

```
CAI servers ←→ WebSocket ←→ characterai package ←→ api_tool.py ←→ ADK agent
```

### Web strategy (`web_tool.py`)

Playwright launches a Chromium browser (headless by default), injects the
auth token into `localStorage`, and navigates to the character's chat page.
For each message we:
1. Locate the `contenteditable` input with ARIA role selectors.
2. Type the text and press Enter (or click the Send button).
3. Poll for a new message bubble to appear.
4. Wait for the typing indicator to disappear, then extract the text.

This exercises the full client-side SPA code path — the same path a real
user would follow.

### Mobile strategy (`mobile_tool.py`)

Appium connects to an Android device/emulator via the UiAutomator2 driver.
We deep-link directly into the character's chat screen using the app's
registered URI scheme (`characterai://chat/<id>`).  For each message we:
1. Find the message input by its resource-id.
2. Send the text and tap the Send button.
3. Wait for the typing indicator to vanish.
4. Scroll to the bottom of the message list and extract the last bubble text.

---

## Output

Every run writes a JSON report to `results/` with this shape:

```json
{
  "session_id": "20250415T120000",
  "strategy": "api",
  "character_id": "...",
  "started_at": "...",
  "finished_at": "...",
  "turns": [
    {
      "message_id": 1,
      "message_text": "Hello! I'm excited to chat with you today.",
      "response_text": "Hi there! ...",
      "strategy": "api",
      "character_id": "...",
      "latency_ms": 743.2,
      "timestamp": "...",
      "error": null
    },
    ...
  ],
  "summary": {
    "total_messages": 15,
    "successful": 15,
    "failed": 0,
    "success_rate_pct": 100.0,
    "avg_latency_ms": 820.4,
    "min_latency_ms": 543.1,
    "max_latency_ms": 1241.8
  }
}
```

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `CAI_TOKEN is not set` | Set `CAI_TOKEN` in `.env` (see §Getting your token) |
| `GOOGLE_API_KEY is not set` | Set `GOOGLE_API_KEY` in `.env` |
| Playwright: `Chat page did not finish loading` | Try `PLAYWRIGHT_HEADLESS=false` to debug; check if CAI token is valid |
| Appium: `Could not connect to Appium server` | Run `appium --address 0.0.0.0 --port 4723` in a terminal |
| Appium: element not found | CAI app updated its UI — use Appium Inspector to update locators in `tools/mobile_tool.py` |
| Rate limiting / 429 errors | Increase the `asyncio.sleep` / `time.sleep` delays in the batch tools |
