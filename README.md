# LLM Debate

Query **Claude, ChatGPT, and Gemini** simultaneously using your existing web subscriptions.

No API keys needed — uses browser automation or direct URL opening.

<p align="center">
  <img src="https://img.shields.io/badge/Claude-Pro-orange" alt="Claude">
  <img src="https://img.shields.io/badge/ChatGPT-Plus-green" alt="ChatGPT">
  <img src="https://img.shields.io/badge/Gemini-Advanced-blue" alt="Gemini">
</p>

---

## Two Modes

| Mode | Speed | Features |
|------|-------|----------|
| **Turbo** ⚡ | **3-50ms** | Opens all 3 windows instantly, prompt in clipboard |
| **Full** 🔬 | ~10s | Playwright automation, response streaming, synthesis |

---

## Quick Start (Turbo Mode)

```bash
# Install
git clone https://github.com/xiaolong-y/debate.git
cd debate
export PATH="$PWD/bin:$PATH"

# Use it (fastest)
llm "What is the meaning of life?"
```

That's it! All 3 chat windows open in **<50ms**, prompt is in your clipboard. Press ⌘V in each.

### Alternative commands

```bash
# Shell script version
3llm "Your question here"

# Python CLI
debate "Your question here"
debate go "Your question here"
```

---

## How Turbo Mode Works

Inspired by Alfred's [Launch URL in 3 Browsers](https://github.com/alfredapp/launch-url-in-3-browsers-workflow) workflow:

```
┌─────────────────────────────────────────┐
│  ask "What is AI?"                      │
└─────────────────────────────────────────┘
              │
              ▼ (parallel, <100ms total)
    ┌─────────┼─────────┐
    ▼         ▼         ▼
 Claude    ChatGPT   Gemini
(new tab) (new tab) (new tab)
              │
              ▼
     📋 Prompt in clipboard
         (⌘V to paste)
```

**Performance breakdown:**
- `pbcopy`: ~5ms (background)
- `open -g` (3 URLs parallel): ~10ms
- Shell overhead: ~5-20ms
- Total: **<50ms** (5-13ms after browser warmup)

---

## Full Mode (with Synthesis)

For automated response collection and AI-powered synthesis:

```bash
# One-time setup
pip install -r requirements.txt
patchright install chromium
debate auth  # Log in to each service

# Run with synthesis
debate run "Compare React vs Vue vs Svelte"
```

Opens a web UI at `localhost:8765` with 4 panes:
- Claude response (streaming)
- ChatGPT response (streaming)
- Gemini response (streaming)
- Unified Analysis (synthesis + arbitration)

---

## Commands Reference

| Command | Speed | Description |
|---------|-------|-------------|
| `llm "prompt"` | **3ms** | ⚡ Ultra-fast - background, silent |
| `q "prompt"` | ~50ms | ⚡ Fast with emoji |
| `3llm "prompt"` | ~100ms | ⚡ Verbose with emojis |
| `ask "prompt"` | ~250ms | Python version |
| `debate "prompt"` | ~100ms | Full CLI, turbo default |
| `debate run "prompt"` | ~10s | 🔬 Full mode + synthesis |
| `debate auth` | - | 🔐 Set up login sessions |
| `debate check` | - | ✅ Check auth status |
| `debate kill` | - | 🛑 Stop server |

---

## Alfred Workflow

An Alfred workflow is included in `alfred/` for keyboard shortcut access:

1. Open `alfred/info.plist` in Alfred
2. Type `3llm your question` to trigger
3. All 3 windows open with prompt in clipboard

---

## Installation Options

### Minimal (Turbo Mode Only)

```bash
git clone https://github.com/xiaolong-y/debate.git
export PATH="$HOME/Documents/GitHub/debate/bin:$PATH"
```

No dependencies! Uses only macOS built-in commands.

### Full Installation

```bash
cd debate
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
patchright install chromium
```

---

## Requirements

- **macOS** (uses `open` and `pbcopy`)
- Active subscriptions to Claude Pro, ChatGPT Plus, and/or Gemini Advanced
- Python 3.10+ (for full mode only)

---

## Architecture

```
debate/
├── bin/
│   ├── llm          # ⚡ Ultra-fast (<50ms)
│   ├── q            # ⚡ Fast with output
│   ├── 3llm         # ⚡ Shell script with emojis
│   ├── ask          # Python version
│   └── debate       # Full CLI
├── alfred/
│   └── info.plist   # Alfred workflow
├── debate.py        # Main CLI with both modes
├── turbo.py         # Feature-rich Python module
├── quick.py         # Simple Python opener
├── server.py        # FastAPI server (full mode)
├── playwright_client.py  # Browser automation
├── llm_selectors.py      # DOM selectors
└── static/
    └── index.html   # 4-pane web UI
```

---

## Why Two Modes?

**Turbo Mode** is for quick questions where you want to manually compare responses. It's instant and reliable.

**Full Mode** is for deeper analysis where you want:
- Automated response collection
- Side-by-side streaming
- AI-synthesized consensus/disagreements
- Markdown rendering with code highlighting

Choose based on your needs!

---

## Troubleshooting

### Turbo mode opens wrong browser

Set your default browser in System Preferences → Desktop & Dock → Default web browser.

### Full mode: ChatGPT keeps logging out

```bash
rm -rf ~/.debate/browser-data/pw-chatgpt/
debate auth
```

### Port already in use

```bash
debate kill
```

---

## License

MIT

---

## Acknowledgments

- [Alfred's Launch URL in 3 Browsers](https://github.com/alfredapp/launch-url-in-3-browsers-workflow) — Inspiration
- [Patchright](https://github.com/Kaliiiiiiiiii-Vinyzu/patchright-python) — Undetected Playwright
- [Karpathy's LLM Council](https://github.com/karpathy/llm-council) — Multi-LLM synthesis idea
