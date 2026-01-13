#!/usr/bin/env python3
"""
Setup authentication using undetected-chromedriver.
This bypasses Cloudflare's bot detection by using a patched Chrome.
"""

import asyncio
import time
from pathlib import Path

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Browser data directory
BROWSER_DATA_DIR = Path.home() / ".debate" / "browser-data"

SITES = {
    "claude": {
        "url": "https://claude.ai",
        "login_indicator": "New chat",  # Text that appears when logged in
    },
    "chatgpt": {
        "url": "https://chatgpt.com",
        "login_indicator": "ChatGPT",
    },
    "gemini": {
        "url": "https://gemini.google.com/app",
        "login_indicator": "Gemini",
    },
}


def setup_auth_for_site(name: str, config: dict):
    """Setup authentication for a single site."""
    print(f"\n{'='*60}")
    print(f"[{name.upper()}] Setting up authentication...")
    print(f"{'='*60}")

    profile_dir = BROWSER_DATA_DIR / f"uc-{name}"
    profile_dir.mkdir(parents=True, exist_ok=True)

    options = uc.ChromeOptions()
    options.add_argument(f"--user-data-dir={profile_dir}")
    options.add_argument("--window-size=1280,900")

    driver = None
    try:
        driver = uc.Chrome(options=options, use_subprocess=True)
        driver.get(config["url"])

        print(f"\nBrowser opened to {config['url']}")
        print("1. Complete any CAPTCHA/verification")
        print("2. Log in with your credentials")
        print("3. Make sure you see the main chat interface")
        print("\nPress Enter here when done...")
        input()

        # Check if logged in
        page_source = driver.page_source
        if config["login_indicator"] in page_source:
            print(f"[{name.upper()}] ✓ Login verified!")
        else:
            print(f"[{name.upper()}] ⚠ Could not verify login, but session may be saved.")
            print("Press Enter to continue...")
            input()

    except Exception as e:
        print(f"[{name.upper()}] Error: {e}")
    finally:
        if driver:
            driver.quit()


def main():
    """Run setup for all sites."""
    print("\n" + "="*60)
    print(" LLM Debate - Authentication Setup")
    print(" Using undetected-chromedriver to bypass Cloudflare")
    print("="*60)

    for name, config in SITES.items():
        setup_auth_for_site(name, config)
        time.sleep(1)

    print("\n" + "="*60)
    print(" Setup complete!")
    print(" Your sessions are saved. Run 'python debate.py' to start.")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
