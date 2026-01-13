#!/usr/bin/env python3
"""
Interactive auth setup for LLMs using Playwright with stealth mode.
Run this to log in to each LLM and save the session for later use.

Usage:
    python setup_auth_pw.py [claude|chatgpt|gemini|all]
"""

import asyncio
import sys
from playwright_client import LLMClient


async def setup_single(llm_name: str):
    """Set up authentication for a single LLM."""
    print(f"\n{'='*60}")
    print(f"Setting up Playwright auth for {llm_name.upper()}...")
    print(f"{'='*60}")

    client = LLMClient(llm_name, headless=False)
    await client.start()

    # Check if already logged in
    if await client.is_logged_in():
        print(f"[{llm_name.upper()}] Already logged in!")
        await client.stop()
        return True

    # Need to log in
    await client.setup_auth()

    # Verify login
    logged_in = await client.is_logged_in()
    if logged_in:
        print(f"[{llm_name.upper()}] ✓ Login saved successfully!")
    else:
        print(f"[{llm_name.upper()}] ⚠ Login verification failed, but session may be saved.")

    await client.stop()
    return logged_in


async def setup_all():
    """Set up authentication for all LLMs."""
    llms = ["claude", "chatgpt", "gemini"]
    results = {}

    for llm in llms:
        results[llm] = await setup_single(llm)

    print(f"\n{'='*60}")
    print("Setup Summary:")
    print(f"{'='*60}")
    for llm, success in results.items():
        status = "✓ Ready" if success else "⚠ May need retry"
        print(f"  {llm}: {status}")

    return results


async def check_all():
    """Check authentication status for all LLMs."""
    llms = ["claude", "chatgpt", "gemini"]

    print(f"\n{'='*60}")
    print("Checking auth status (Playwright stealth)...")
    print(f"{'='*60}")

    for llm in llms:
        client = LLMClient(llm, headless=True)
        await client.start()
        logged_in = await client.is_logged_in()
        status = "✓ Logged in" if logged_in else "✗ Not logged in"
        print(f"  {llm}: {status}")
        await client.stop()


async def main():
    if len(sys.argv) < 2:
        print("Usage: python setup_auth_pw.py [claude|chatgpt|gemini|all|check]")
        print("\nCommands:")
        print("  claude   - Set up Claude authentication")
        print("  chatgpt  - Set up ChatGPT authentication")
        print("  gemini   - Set up Gemini authentication")
        print("  all      - Set up all LLMs")
        print("  check    - Check auth status for all LLMs")
        sys.exit(1)

    cmd = sys.argv[1].lower()

    if cmd == "all":
        await setup_all()
    elif cmd == "check":
        await check_all()
    elif cmd in ["claude", "chatgpt", "gemini"]:
        await setup_single(cmd)
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
