"""
Playwright-based browser automation for LLM web interfaces.
Uses playwright-stealth to bypass bot detection and Cloudflare CAPTCHAs.
"""

from __future__ import annotations

import asyncio
import json
import os
import random
import sys
from pathlib import Path
from typing import AsyncIterator, Callable, Optional, List, Dict

from playwright.async_api import async_playwright, BrowserContext, Page, Browser, TimeoutError as PlaywrightTimeout
from playwright_stealth import Stealth

# Stealth instance for hiding automation
_stealth = Stealth(
    navigator_platform_override="MacIntel",  # macOS
    navigator_vendor_override="Google Inc.",
)

from llm_selectors import (
    get_selectors,
    get_all_input_selectors,
    get_all_submit_selectors,
    get_all_response_selectors,
    LLMSelectors,
)

# Browser data directory for persistent sessions
BROWSER_DATA_DIR = Path.home() / ".debate" / "browser-data"
COOKIES_DIR = BROWSER_DATA_DIR / "cookies"

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAY_BASE = 2


class LLMClientError(Exception):
    """Base exception for LLM client errors."""
    pass


class AuthenticationError(LLMClientError):
    """User is not logged in."""
    pass


class SelectorNotFoundError(LLMClientError):
    """Could not find required DOM element."""
    pass


class ResponseTimeoutError(LLMClientError):
    """Response generation timed out."""
    pass


class LLMClient:
    """Browser automation client for a single LLM using Playwright with stealth."""

    def __init__(
        self,
        llm_name: str,
        headless: bool = False,
        shared_context: BrowserContext | None = None,
    ):
        self.llm_name = llm_name
        self.selectors = get_selectors(llm_name)
        self.headless = headless
        self._shared_context = shared_context
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._playwright = None
        self._browser: Browser | None = None
        self._owns_browser = False

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.stop()

    async def start(self):
        """Start browser with stealth mode enabled."""
        if self._shared_context:
            self._context = self._shared_context
            self._page = await self._context.new_page()
            await _stealth.apply_stealth_async(self._page)
            self._owns_browser = False
            return

        self._owns_browser = True
        self._playwright = await async_playwright().start()

        # Use Playwright-specific profile directory
        profile_dir = BROWSER_DATA_DIR / f"pw-{self.llm_name}"
        profile_dir.mkdir(parents=True, exist_ok=True)

        # Clean up stale lock files
        singleton_lock = profile_dir / "SingletonLock"
        if singleton_lock.exists():
            try:
                singleton_lock.unlink()
            except Exception:
                pass

        # Launch with stealth-friendly settings
        self._context = await self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=self.headless,
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="en-US",
            timezone_id="America/New_York",
            # Stealth settings
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
            ],
            ignore_default_args=["--enable-automation"],
        )

        # Get or create page and apply stealth
        if self._context.pages:
            self._page = self._context.pages[0]
        else:
            self._page = await self._context.new_page()

        # Apply stealth scripts to hide automation
        await _stealth.apply_stealth_async(self._page)

        # Load saved cookies if available
        await self._load_cookies()

    async def stop(self):
        """Close page and save cookies."""
        # Save cookies before closing
        if self._owns_browser and self._context:
            await self._save_cookies()

        if self._page:
            try:
                await self._page.close()
            except Exception:
                pass
            self._page = None

        if self._owns_browser:
            if self._context:
                try:
                    await self._context.close()
                except Exception:
                    pass
                self._context = None
            if self._playwright:
                await self._playwright.stop()
                self._playwright = None

    async def _save_cookies(self):
        """Save cookies for session persistence."""
        if not self._context:
            return
        try:
            COOKIES_DIR.mkdir(parents=True, exist_ok=True)
            cookies = await self._context.cookies()
            cookie_file = COOKIES_DIR / f"{self.llm_name}.json"
            with open(cookie_file, "w") as f:
                json.dump(cookies, f)
        except Exception as e:
            print(f"[{self.llm_name}] Could not save cookies: {e}")

    async def _load_cookies(self):
        """Load saved cookies for session persistence."""
        if not self._context:
            return
        try:
            cookie_file = COOKIES_DIR / f"{self.llm_name}.json"
            if cookie_file.exists():
                with open(cookie_file) as f:
                    cookies = json.load(f)
                await self._context.add_cookies(cookies)
        except Exception as e:
            print(f"[{self.llm_name}] Could not load cookies: {e}")

    async def _find_element_with_fallbacks(
        self,
        selectors: list[str],
        timeout: int = 10000,
        description: str = "element",
    ):
        """Try to find an element using multiple selectors with fallbacks."""
        if not self._page:
            raise RuntimeError("Client not started")

        for selector in selectors:
            try:
                element = await self._page.wait_for_selector(
                    selector,
                    timeout=timeout // len(selectors),
                    state="visible",
                )
                if element:
                    return element
            except PlaywrightTimeout:
                continue

        for selector in selectors:
            element = await self._page.query_selector(selector)
            if element:
                return element

        raise SelectorNotFoundError(
            f"Could not find {description} for {self.llm_name}. "
            f"Tried selectors: {selectors}"
        )

    async def is_logged_in(self) -> bool:
        """Check if user is logged in to this LLM."""
        if not self._page:
            return False

        try:
            await self._page.goto(self.selectors.url, timeout=30000)
            await asyncio.sleep(2)
            await self._page.wait_for_load_state("domcontentloaded", timeout=10000)

            input_selectors = get_all_input_selectors(self.llm_name)
            for selector in input_selectors:
                element = await self._page.query_selector(selector)
                if element:
                    return True

            return False
        except Exception:
            return False

    async def setup_auth(self):
        """Interactive auth setup - opens browser for manual login."""
        if not self._page:
            raise RuntimeError("Client not started")

        await self._page.goto(self.selectors.url)
        print(f"\n{'='*60}")
        print(f"[{self.llm_name.upper()}] MANUAL LOGIN REQUIRED")
        print(f"{'='*60}")
        print(f"1. Complete any CAPTCHA/human verification in the browser")
        print(f"2. Log in with your credentials")
        print(f"3. Make sure you're on the main chat page")
        print(f"4. Press Enter here when fully logged in...")
        print(f"{'='*60}")
        await asyncio.get_event_loop().run_in_executor(None, input)

        await asyncio.sleep(2)
        await self._save_cookies()

        if await self.is_logged_in():
            print(f"[{self.llm_name.upper()}] ✓ Login successful! Session saved.")
        else:
            print(f"[{self.llm_name.upper()}] ⚠ Could not verify login. Try again and press Enter...")
            await asyncio.get_event_loop().run_in_executor(None, input)
            await self._save_cookies()

    async def send_prompt(
        self,
        prompt: str,
        on_chunk: Callable[[str], None] | None = None,
        timeout: int = 120000,
    ) -> str:
        """Send a prompt and stream the response."""
        return await self._send_prompt_with_retry(prompt, on_chunk, timeout)

    async def _send_prompt_with_retry(
        self,
        prompt: str,
        on_chunk: Callable[[str], None] | None,
        timeout: int,
    ) -> str:
        """Send prompt with retry logic."""
        last_error = None

        for attempt in range(MAX_RETRIES):
            try:
                return await self._send_prompt_impl(prompt, on_chunk, timeout)
            except (SelectorNotFoundError, PlaywrightTimeout) as e:
                last_error = e
                if attempt < MAX_RETRIES - 1:
                    delay = RETRY_DELAY_BASE * (2 ** attempt) + random.uniform(0, 1)
                    await asyncio.sleep(delay)
                    if self._page:
                        await self._page.reload()

        raise LLMClientError(f"Failed after {MAX_RETRIES} attempts: {last_error}")

    async def _send_prompt_impl(
        self,
        prompt: str,
        on_chunk: Callable[[str], None] | None,
        timeout: int,
    ) -> str:
        """Internal implementation of send_prompt."""
        if not self._page:
            raise RuntimeError("Client not started")

        await self._page.goto(self.selectors.new_chat_url, timeout=30000)
        await asyncio.sleep(1)
        await self._page.wait_for_load_state("domcontentloaded", timeout=15000)

        input_selectors = get_all_input_selectors(self.llm_name)
        input_el = await self._find_element_with_fallbacks(
            input_selectors,
            timeout=15000,
            description="input field",
        )

        await input_el.click()
        await asyncio.sleep(0.1)

        # Use JavaScript for faster input on long prompts
        try:
            await self._page.evaluate("""
                (args) => {
                    const [el, text] = args;
                    if (el.tagName === 'TEXTAREA' || el.tagName === 'INPUT') {
                        el.value = text;
                        el.dispatchEvent(new Event('input', { bubbles: true }));
                    } else {
                        el.innerText = text;
                        el.dispatchEvent(new InputEvent('input', { bubbles: true, data: text }));
                    }
                }
            """, [input_el, prompt])
        except Exception:
            try:
                await input_el.fill(prompt)
            except Exception:
                await input_el.type(prompt, delay=5)

        await asyncio.sleep(0.2)

        submit_selectors = get_all_submit_selectors(self.llm_name)
        submit_btn = await self._find_element_with_fallbacks(
            submit_selectors,
            timeout=5000,
            description="submit button",
        )

        await submit_btn.click()
        return await self._stream_response(on_chunk, timeout)

    async def _stream_response(
        self,
        on_chunk: Callable[[str], None] | None,
        timeout: int,
    ) -> str:
        """Stream response text as it's generated."""
        if not self._page:
            raise RuntimeError("Client not started")

        start_time = asyncio.get_event_loop().time()
        last_text = ""
        stable_count = 0
        response_selectors = get_all_response_selectors(self.llm_name)

        print(f"[{self.llm_name}] Waiting for response...")
        await asyncio.sleep(0.5)

        while True:
            elapsed = (asyncio.get_event_loop().time() - start_time) * 1000
            if elapsed > timeout:
                if last_text:
                    return last_text
                raise ResponseTimeoutError(f"Response timeout after {timeout}ms")

            current_text = ""
            for selector in response_selectors:
                try:
                    elements = await self._page.query_selector_all(selector)
                    if elements:
                        last_el = elements[-1]
                        current_text = await last_el.inner_text()
                        if current_text:
                            break
                except Exception:
                    continue

            if current_text:
                if current_text != last_text:
                    if len(last_text) == 0:
                        print(f"[{self.llm_name}] Got first response chunk")
                    if on_chunk and len(current_text) > len(last_text):
                        new_content = current_text[len(last_text):]
                        if new_content:
                            on_chunk(new_content)
                    last_text = current_text
                    stable_count = 0
                else:
                    stable_count += 1

                is_complete = await self._check_response_complete()
                if is_complete:
                    print(f"[{self.llm_name}] Response complete ({len(last_text)} chars)")
                    return last_text

                if stable_count > 20 and last_text:
                    print(f"[{self.llm_name}] Response stable ({len(last_text)} chars)")
                    return last_text

            await asyncio.sleep(0.1)

    async def _check_response_complete(self) -> bool:
        """Check if the response generation is complete."""
        if not self._page:
            return False

        if self.selectors.response_complete_indicator:
            try:
                el = await self._page.query_selector(
                    self.selectors.response_complete_indicator
                )
                if el:
                    return True
            except Exception:
                pass

        if self.selectors.stop_selector:
            try:
                stop_btn = await self._page.query_selector(self.selectors.stop_selector)
                if stop_btn:
                    is_visible = await stop_btn.is_visible()
                    if not is_visible:
                        return True
                else:
                    return False
            except Exception:
                pass

        return False

    async def stream_prompt(
        self,
        prompt: str,
        timeout: int = 120000,
    ) -> AsyncIterator[str]:
        """Send a prompt and yield response chunks."""
        queue: asyncio.Queue[str | None] = asyncio.Queue()

        def on_chunk(chunk: str):
            queue.put_nowait(chunk)

        async def run_prompt():
            try:
                await self.send_prompt(prompt, on_chunk=on_chunk, timeout=timeout)
            finally:
                queue.put_nowait(None)

        task = asyncio.create_task(run_prompt())

        try:
            while True:
                chunk = await queue.get()
                if chunk is None:
                    break
                yield chunk
        finally:
            if not task.done():
                task.cancel()


class DebateOrchestrator:
    """Orchestrates parallel prompts to multiple LLMs."""

    def __init__(
        self,
        llms: list[str] | None = None,
        headless: bool = False,
    ):
        self.llm_names = llms or ["claude", "chatgpt", "gemini"]
        self.headless = headless
        self.clients: dict[str, LLMClient] = {}
        self._playwright = None
        self._context: BrowserContext | None = None

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.stop()

    async def start(self):
        """Start all LLM clients in parallel."""
        print("Starting browsers with stealth mode...")

        async def start_client(name: str) -> tuple[str, LLMClient]:
            client = LLMClient(name, headless=self.headless)
            await client.start()
            return name, client

        # Start all clients in parallel
        tasks = [start_client(name) for name in self.llm_names]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                print(f"  ✗ Failed to start client: {result}")
            else:
                name, client = result
                self.clients[name] = client
                print(f"  ✓ {name} ready")

        print("All browsers started!")

    async def stop(self):
        """Stop all LLM clients."""
        for client in self.clients.values():
            try:
                await client.stop()
            except Exception as e:
                print(f"Warning: Error stopping client: {e}")
        self.clients.clear()

    async def check_auth(self) -> dict[str, bool]:
        """Check which LLMs are logged in (in parallel)."""
        async def check_one(name: str, client: LLMClient) -> tuple[str, bool]:
            return name, await client.is_logged_in()

        tasks = [check_one(name, client) for name, client in self.clients.items()]
        results = await asyncio.gather(*tasks)
        return dict(results)

    async def setup_all_auth(self):
        """Interactive setup for all LLMs that need it."""
        auth_status = await self.check_auth()

        for name, logged_in in auth_status.items():
            if not logged_in:
                client = self.clients.get(name)
                if client:
                    await client.setup_auth()

    async def debate(
        self,
        prompt: str,
        on_update: Callable[[str, str], None] | None = None,
        timeout: int = 120000,
    ) -> dict[str, str]:
        """Send prompt to all LLMs in parallel."""
        async def query_llm(name: str, client: LLMClient) -> tuple[str, str]:
            def chunk_callback(chunk: str):
                if on_update:
                    on_update(name, chunk)

            try:
                response = await client.send_prompt(
                    prompt,
                    on_chunk=chunk_callback,
                    timeout=timeout,
                )
                return name, response
            except Exception as e:
                error_msg = f"[Error: {type(e).__name__}: {str(e)[:100]}]"
                if on_update:
                    on_update(name, error_msg)
                return name, error_msg

        tasks = [
            query_llm(name, client)
            for name, client in self.clients.items()
        ]
        results = await asyncio.gather(*tasks)

        return dict(results)
