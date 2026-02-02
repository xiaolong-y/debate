#!/usr/bin/env python3
"""
Turbo LLM Opener - Maximum performance parallel LLM launcher.

Opens Claude, ChatGPT, and Gemini simultaneously using:
1. Native macOS 'open' command (parallel, non-blocking)
2. Optional AppleScript for browser tab control
3. Clipboard integration for instant prompt pasting

Performance: <200ms to open all 3 windows
"""

import subprocess
import sys

from config import LLMS
from utils import copy_to_clipboard, open_url_native, open_urls_parallel


def open_in_arc_tabs(urls: list[str]) -> bool:
    """
    Open URLs as tabs in Arc browser using AppleScript.
    Returns True if Arc is available and URLs were opened.
    """
    applescript = '''
    tell application "Arc"
        activate
        tell front window
            {}
        end tell
    end tell
    '''.format("\n            ".join(f'make new tab with properties {{URL:"{url}"}}' for url in urls))

    try:
        result = subprocess.run(
            ["osascript", "-e", applescript],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except Exception:
        return False


def open_in_chrome_tabs(urls: list[str]) -> bool:
    """
    Open URLs as tabs in Chrome using AppleScript.
    """
    applescript = '''
    tell application "Google Chrome"
        activate
        {}
    end tell
    '''.format("\n        ".join(f'open location "{url}"' for url in urls))

    try:
        result = subprocess.run(
            ["osascript", "-e", applescript],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except Exception:
        return False


def open_in_safari_tabs(urls: list[str]) -> bool:
    """
    Open URLs as tabs in Safari using AppleScript.
    """
    # Safari needs window management
    tab_commands = "\n            ".join(
        f'make new tab at end of tabs with properties {{URL:"{url}"}}'
        for url in urls[1:]  # Skip first, it goes in initial tab
    )

    applescript = f'''
    tell application "Safari"
        activate
        if (count of windows) = 0 then
            make new document with properties {{URL:"{urls[0]}"}}
        else
            set URL of front document to "{urls[0]}"
        end if
        tell front window
            {tab_commands}
        end tell
    end tell
    '''

    try:
        result = subprocess.run(
            ["osascript", "-e", applescript],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except Exception:
        return False


def get_default_browser() -> str | None:
    """Get the default browser on macOS."""
    try:
        result = subprocess.run(
            ["defaults", "read", "com.apple.LaunchServices/com.apple.launchservices.secure", "LSHandlers"],
            capture_output=True,
            text=True,
        )
        output = result.stdout.lower()
        if "chrome" in output:
            return "chrome"
        elif "arc" in output:
            return "arc"
        elif "safari" in output:
            return "safari"
        elif "firefox" in output:
            return "firefox"
    except Exception:
        pass
    return None


def turbo_open(
    prompt: str | None = None,
    browser: str | None = None,
    llms: list[str] | None = None,
) -> None:
    """
    Open all LLM chat windows with maximum performance.

    Args:
        prompt: Optional prompt to copy to clipboard
        browser: Force specific browser (arc, chrome, safari, or None for default)
        llms: List of LLMs to open (default: all)
    """
    # Select LLMs
    selected = llms or list(LLMS.keys())
    urls = [LLMS[llm]["new_chat_url"] for llm in selected if llm in LLMS]
    names = [LLMS[llm]["name"] for llm in selected if llm in LLMS]

    if not urls:
        print("No valid LLMs specified")
        return

    # Copy prompt to clipboard first (happens in parallel with browser opening)
    clipboard_ok = False
    if prompt:
        clipboard_ok = copy_to_clipboard(prompt)

    # Determine browser strategy
    browser = browser or get_default_browser()

    print(f"Opening {len(urls)} LLM windows...")

    # Try browser-specific tab opening for better UX (all tabs in one window)
    opened = False
    if browser == "arc":
        opened = open_in_arc_tabs(urls)
    elif browser == "chrome":
        opened = open_in_chrome_tabs(urls)
    elif browser == "safari":
        opened = open_in_safari_tabs(urls)

    # Fallback to generic open command (opens in default browser)
    if not opened:
        open_urls_parallel(urls)

    # Report status
    for name in names:
        print(f"   {name}")

    if prompt:
        if clipboard_ok:
            print(f"\nPrompt copied ({len(prompt)} chars)")
            print("Press Cmd+V in each chat window to paste")
        else:
            print(f"\nClipboard copy failed")
            print(f"   Prompt: {prompt[:80]}...")


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Open LLM chat windows in parallel",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  turbo "What is the meaning of life?"
  turbo --browser chrome "Compare Python and Rust"
  turbo --llms claude,chatgpt "Quick question"
        """,
    )
    parser.add_argument(
        "prompt",
        nargs="*",
        help="Prompt to copy to clipboard (optional)",
    )
    parser.add_argument(
        "--browser", "-b",
        choices=["arc", "chrome", "safari", "default"],
        help="Browser to use (default: auto-detect)",
    )
    parser.add_argument(
        "--llms", "-l",
        help="Comma-separated list of LLMs (default: claude,chatgpt,gemini)",
    )

    args = parser.parse_args()

    prompt = " ".join(args.prompt) if args.prompt else None
    browser = args.browser if args.browser != "default" else None
    llms = args.llms.split(",") if args.llms else None

    turbo_open(prompt=prompt, browser=browser, llms=llms)


if __name__ == "__main__":
    main()
