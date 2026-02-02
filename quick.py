#!/usr/bin/env python3
"""
Quick LLM opener - Opens Claude, ChatGPT, and Gemini in parallel tabs.

Inspired by Alfred's "Launch URL in 3 Browsers" workflow.
Uses the default browser to open all 3 AI chat interfaces simultaneously.

Performance: ~100ms total (vs 10-30s for Playwright automation)
"""

import subprocess
import sys
import webbrowser
from urllib.parse import quote
import pyperclip  # Optional: for clipboard support


# LLM URLs - these open fresh chat windows
LLMS = {
    "claude": "https://claude.ai/new",
    "chatgpt": "https://chatgpt.com/",
    "gemini": "https://gemini.google.com/app",
}


def open_url_macos(url: str) -> None:
    """Open URL using macOS native 'open' command (faster than webbrowser)."""
    subprocess.Popen(["open", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def open_all_llms(prompt: str | None = None) -> None:
    """
    Open all 3 LLM chat windows in parallel.

    If prompt is provided, copies it to clipboard for easy pasting.
    """
    # Copy prompt to clipboard if provided
    if prompt:
        try:
            pyperclip.copy(prompt)
            print(f"📋 Prompt copied to clipboard ({len(prompt)} chars)")
        except Exception:
            print(f"⚠️  Could not copy to clipboard. Prompt: {prompt[:50]}...")

    # Open all URLs in parallel (non-blocking)
    print("🚀 Opening LLM chat windows...")
    for name, url in LLMS.items():
        open_url_macos(url)
        print(f"   ✓ {name}")

    if prompt:
        print("\n💡 Paste with ⌘V in each chat window")


def main():
    """CLI entry point."""
    prompt = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else None
    open_all_llms(prompt)


if __name__ == "__main__":
    main()
