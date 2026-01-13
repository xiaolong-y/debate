#!/usr/bin/env python3
"""
Simple one-at-a-time auth setup for debugging.
Usage: python setup_one.py [claude|chatgpt|gemini]
"""

import asyncio
import sys

# Force unbuffered output
def log(msg):
    print(msg, flush=True)


async def setup_one(llm_name: str):
    from playwright_client import LLMClient

    log(f"\n{'='*50}")
    log(f"Setting up {llm_name.upper()}")
    log(f"{'='*50}")

    log(f"[1/4] Creating client...")
    client = LLMClient(llm_name, headless=False)

    log(f"[2/4] Starting browser (this may take a moment)...")
    await client.start()
    log(f"[2/4] Browser started!")

    log(f"[3/4] Checking if already logged in...")
    logged_in = await client.is_logged_in()

    if logged_in:
        log(f"[3/4] Already logged in to {llm_name}!")
    else:
        log(f"[3/4] Not logged in. Starting auth flow...")
        await client.setup_auth()

    log(f"[4/4] Closing browser...")
    await client.stop()

    log(f"\nDone with {llm_name}!")


async def main():
    if len(sys.argv) < 2:
        log("Usage: python setup_one.py [claude|chatgpt|gemini|all]")
        sys.exit(1)

    target = sys.argv[1].lower()

    if target == "all":
        for llm in ["claude", "chatgpt", "gemini"]:
            await setup_one(llm)
    elif target in ["claude", "chatgpt", "gemini"]:
        await setup_one(target)
    else:
        log(f"Unknown LLM: {target}")
        sys.exit(1)


if __name__ == "__main__":
    log("Starting setup script...")
    asyncio.run(main())
