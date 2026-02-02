"""
Shared utility functions for the debate tool.
Handles clipboard, URL opening, and other common operations.
"""

import os
import subprocess
from concurrent.futures import ThreadPoolExecutor


def copy_to_clipboard(text: str) -> bool:
    """
    Copy text to macOS clipboard using pbcopy.

    Returns True on success, False on failure.
    """
    try:
        process = subprocess.Popen(
            ["pbcopy"],
            stdin=subprocess.PIPE,
            env={**os.environ, "LANG": "en_US.UTF-8"},
        )
        process.communicate(text.encode("utf-8"))
        return process.returncode == 0
    except Exception:
        return False


def open_url_native(url: str) -> subprocess.Popen:
    """
    Open URL using native macOS 'open' command.

    Returns the Popen object (non-blocking).
    """
    return subprocess.Popen(
        ["open", url],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def open_url_background(url: str) -> subprocess.Popen:
    """
    Open URL in background without bringing browser to foreground.

    Uses -g flag for faster perceived performance.
    """
    return subprocess.Popen(
        ["open", "-g", url],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def open_urls_parallel(urls: list[str], background: bool = False) -> None:
    """
    Open multiple URLs in true parallel using ThreadPoolExecutor.
    """
    opener = open_url_background if background else open_url_native
    with ThreadPoolExecutor(max_workers=len(urls)) as executor:
        list(executor.map(opener, urls))
