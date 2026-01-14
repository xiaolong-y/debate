# LLM Debate

Query Claude, ChatGPT, and Gemini **in parallel** using your existing subscriptions, then synthesize their responses into a unified analysis.

No API keys needed — uses browser automation to leverage your web subscriptions.

<p align="center">
  <img src="https://img.shields.io/badge/Claude-Pro-orange" alt="Claude">
  <img src="https://img.shields.io/badge/ChatGPT-Plus-green" alt="ChatGPT">
  <img src="https://img.shields.io/badge/Gemini-Advanced-blue" alt="Gemini">
</p>

---

## How It Works

```
┌─────────────────────────────────────────────────────────────┐
│  debate run "Is Rust better than Go for CLI tools?"        │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              Patchright (Undetected Playwright)             │
│                                                             │
│         ┌──────────┬──────────┬──────────┐                  │
│         ▼          ▼          ▼          │                  │
│      Claude    ChatGPT    Gemini         │                  │
│     (claude.ai) (chatgpt.com) (gemini.google.com)           │
│         │          │          │                             │
│         └──────────┴──────────┘                             │
│                    │                                        │
│                    ▼                                        │
│            Unified Analysis                                 │
│         (Claude synthesizes all responses)                  │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              4-Pane Web UI (localhost:8765)                 │
│  ┌─────────────────┬─────────────────┐                      │
│  │    Claude       │    ChatGPT      │                      │
│  │  (streaming)    │   (streaming)   │                      │
│  ├─────────────────┼─────────────────┤                      │
│  │    Gemini       │   Synthesis     │                      │
│  │  (streaming)    │   (streaming)   │                      │
│  └─────────────────┴─────────────────┘                      │
└─────────────────────────────────────────────────────────────┘
```

---

## Features

- **Parallel Queries** — Ask all three LLMs simultaneously
- **Streaming Responses** — Watch responses appear in real-time
- **Unified Analysis** — Claude synthesizes consensus and disagreements
- **Rich Markdown** — Code highlighting, math rendering, tables
- **Session Persistence** — Login once, sessions saved for future use
- **No API Keys** — Uses your existing web subscriptions

---

## Installation

### Prerequisites

- Python 3.10+
- Active subscriptions to Claude Pro, ChatGPT Plus, and/or Gemini Advanced

### Setup

```bash
# Clone the repository
git clone https://github.com/xiaolong-y/debate.git
cd debate

# Create virtual environment and install dependencies
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Install Patchright browser
pip install patchright
patchright install chromium

# Add to PATH (add this to your ~/.zshrc or ~/.bashrc)
export PATH="$HOME/Documents/GitHub/debate/bin:$PATH"
```

### Authenticate

Run the auth command to log in to each LLM (one-time setup):

```bash
debate auth
```

This opens browser windows for Claude, ChatGPT, and Gemini. Log in manually to each, then press Enter when done. Sessions are saved to `~/.debate/browser-data/`.

---

## Usage

### Commands

| Command | Description |
|---------|-------------|
| `debate run "prompt"` | Run a debate with the given prompt |
| `debate auth` | Authenticate all LLM accounts |
| `debate check` | Check authentication status |
| `debate kill` | Kill any running debate server |
| `debate server` | Start server only (no browser) |

### Examples

```bash
# Simple question
debate run "What is the best programming language for beginners?"

# Complex analysis
debate run "Compare React, Vue, and Svelte for a new startup"

# Research question
debate run "What are the implications of quantum computing for cryptography?"
```

---

## Web UI

The debate opens a browser at `http://localhost:8765` with a 4-pane interface:

| Pane | Content |
|------|---------|
| Top Left | Claude's response |
| Top Right | ChatGPT's response |
| Bottom Left | Gemini's response |
| Bottom Right | Unified Analysis (synthesis + arbitration) |

### Features

- **Live Streaming** — Responses appear as they're generated
- **Markdown Rendering** — Headers, lists, code blocks, tables
- **Syntax Highlighting** — Code blocks with language detection
- **Math Support** — LaTeX rendering via KaTeX
- **Thinking Blocks** — Collapsible reasoning sections
- **Copy Buttons** — Copy raw markdown from any pane
- **Dark Mode** — Automatic based on system preference

---

## Architecture

```
debate/
├── bin/
│   └── debate           # CLI entry point
├── static/
│   └── index.html       # 4-pane web UI
├── debate.py            # CLI commands
├── server.py            # FastAPI + WebSocket server
├── playwright_client.py # Browser automation (Patchright)
├── triage.py            # Synthesis/arbitration logic
├── llm_selectors.py     # DOM selectors for each LLM
└── WORKING_STATE.md     # Debugging documentation
```

### Key Technologies

| Component | Technology |
|-----------|------------|
| Browser Automation | [Patchright](https://github.com/Kaliiiiiiiiii-Vinyzu/patchright-python) (undetected Playwright) |
| Web Server | FastAPI + WebSocket |
| Frontend | Vanilla JS + marked.js + highlight.js + KaTeX |
| CLI | Typer + Rich |

---

## Why Patchright?

Regular Playwright is detected by ChatGPT's bot detection:

- OpenAI uses CDP (Chrome DevTools Protocol) fingerprinting
- Sessions get invalidated server-side after automation is detected
- Standard stealth plugins don't bypass this

[Patchright](https://github.com/Kaliiiiiiiiii-Vinyzu/patchright-python) patches these detection vectors at a lower level, making automation undetectable.

---

## Troubleshooting

### ChatGPT keeps redirecting to login

```bash
# Clear the corrupted profile
rm -rf ~/.debate/browser-data/pw-chatgpt/
rm ~/.debate/browser-data/cookies/chatgpt.json

# Re-authenticate
debate auth
```

### Port already in use

```bash
debate kill
```

### Browser hangs on startup

```bash
# Clear stale lock files
rm -f ~/.debate/browser-data/pw-*/SingletonLock
```

### Check auth status

```bash
debate check
```

---

## Browser Data

Sessions are stored in `~/.debate/browser-data/`:

```
~/.debate/browser-data/
├── pw-claude/      # Claude browser profile
├── pw-chatgpt/     # ChatGPT browser profile
├── pw-gemini/      # Gemini browser profile
└── cookies/        # Saved cookies
```

To reset everything:

```bash
rm -rf ~/.debate/browser-data/
debate auth
```

---

## Contributing

Contributions welcome! Key areas:

- **Selector Updates** — LLM sites change their DOM frequently. Update `llm_selectors.py` if something breaks.
- **New LLMs** — Add support for other chat interfaces (Perplexity, Mistral, etc.)
- **UI Improvements** — The web UI is self-contained in `static/index.html`

---

## License

MIT

---

## Acknowledgments

- [Patchright](https://github.com/Kaliiiiiiiiii-Vinyzu/patchright-python) — Undetected Playwright
- [Karpathy's LLM Council](https://github.com/karpathy/llm-council) — Inspiration for multi-LLM synthesis
