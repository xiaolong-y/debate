"""
Central configuration for the debate tool.
Single source of truth for LLM URLs, paths, and settings.
"""

from pathlib import Path

# LLM Endpoints
LLMS = {
    "claude": {
        "name": "Claude",
        "url": "https://claude.ai",
        "new_chat_url": "https://claude.ai/new",
    },
    "chatgpt": {
        "name": "ChatGPT",
        "url": "https://chatgpt.com",
        "new_chat_url": "https://chatgpt.com/",
    },
    "gemini": {
        "name": "Gemini",
        "url": "https://gemini.google.com",
        "new_chat_url": "https://gemini.google.com/app",
    },
}

# Browser data directory for persistent sessions
BROWSER_DATA_DIR = Path.home() / ".debate" / "browser-data"
COOKIES_DIR = BROWSER_DATA_DIR / "cookies"

# Server settings
DEFAULT_PORT = 8765

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAY_BASE = 2
