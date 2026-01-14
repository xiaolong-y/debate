# LLM Debate - Working State Documentation

**Last verified**: 2025-01-13
**Commit**: `463d5fa`

---

## What's Working

### Core Functionality
- **Parallel querying** of Claude, ChatGPT, and Gemini via browser automation
- **Streaming responses** displayed in real-time in 4-pane web UI
- **Unified triage** (synthesis + arbitration) via Claude after all models respond
- **Session persistence** - login once, sessions saved for future use

### Backend: Patchright (Undetected Playwright)

**This is the ONLY working backend.** The `uc_client.py` (undetected-chromedriver) backend is deprecated.

| Component | Status | Notes |
|-----------|--------|-------|
| Patchright | ✅ Working | Undetected Playwright fork with built-in stealth |
| Claude auth | ✅ Working | Sessions persist in `~/.debate/browser-data/pw-claude/` |
| ChatGPT auth | ✅ Working | Required Patchright (regular Playwright was detected) |
| Gemini auth | ✅ Working | Sessions persist in `~/.debate/browser-data/pw-gemini/` |
| Triage/Synthesis | ✅ Working | Uses Claude for unified analysis |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  debate "prompt"                                            │
│     │                                                       │
│     ▼                                                       │
│  server.py (FastAPI + WebSocket on :8765)                   │
│     │                                                       │
│     ▼                                                       │
│  playwright_client.py (uses Patchright)                     │
│     │                                                       │
│     ├──► Claude (claude.ai)      ──┐                        │
│     ├──► ChatGPT (chatgpt.com)   ──┼──► Parallel queries    │
│     └──► Gemini (gemini.google)  ──┘                        │
│                    │                                        │
│                    ▼                                        │
│              triage.py                                      │
│              (Claude synthesizes all responses)             │
│                    │                                        │
│                    ▼                                        │
│              static/index.html (4-pane UI)                  │
└─────────────────────────────────────────────────────────────┘
```

---

## Key Files

| File | Purpose |
|------|---------|
| `debate.py` | CLI entry point |
| `server.py` | FastAPI server + WebSocket handling |
| `playwright_client.py` | Browser automation (imports from `patchright`) |
| `triage.py` | Synthesis/arbitration logic |
| `llm_selectors.py` | DOM selectors for each LLM site |
| `static/index.html` | 4-pane web UI with markdown rendering |

---

## Dependencies (Critical)

```
patchright==1.57.2      # Undetected Playwright fork (NOT regular playwright)
fastapi
uvicorn
websockets
typer
rich
```

**Install Patchright browser:**
```bash
patchright install chromium
```

---

## Browser Data Locations

```
~/.debate/browser-data/
├── pw-claude/          # Patchright profile for Claude
├── pw-chatgpt/         # Patchright profile for ChatGPT
├── pw-gemini/          # Patchright profile for Gemini
└── cookies/
    ├── claude.json     # Saved cookies
    ├── chatgpt.json
    └── gemini.json
```

---

## Commands

### Authenticate (one-time setup)
```bash
debate auth
# Opens browser for each LLM, manually log in, press Enter when done
```

### Run a debate
```bash
debate "Your prompt here"
# Opens browser UI at localhost:8765 with prompt pre-filled
```

### Check auth status
```bash
debate check
```

---

## Troubleshooting

### ChatGPT keeps redirecting to login
**Cause**: Bot detection invalidated session
**Fix**:
1. Clear profile: `rm -rf ~/.debate/browser-data/pw-chatgpt/`
2. Re-authenticate: `debate auth`

### "No module named 'triage'"
**Fix**: `git checkout HEAD -- triage.py`

### Browser hangs on startup
**Cause**: Stale lock files
**Fix**:
```bash
rm -f ~/.debate/browser-data/pw-*/SingletonLock
rm -f ~/.debate/browser-data/pw-*/SingletonSocket
```

### Patchright not found
**Fix**:
```bash
uv pip install patchright
patchright install chromium
```

---

## Why Patchright?

Regular Playwright + `playwright-stealth` was detected by ChatGPT's bot detection:
- OpenAI uses CDP (Chrome DevTools Protocol) detection
- Sessions were invalidated server-side after automation was detected
- Patchright patches these detection vectors at a lower level

Claude and Gemini worked with regular Playwright, but ChatGPT required Patchright.

---

## Verification Checklist

After any changes, verify:

1. **Import check**:
   ```bash
   python -c "from server import app; print('OK')"
   ```

2. **Auth check**:
   ```bash
   debate check
   ```

3. **Full debate test**:
   ```bash
   debate "What is 2+2?"
   ```
   - All 3 models should respond
   - Synthesis pane should show unified analysis
