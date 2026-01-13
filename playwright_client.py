"""
Playwright-based browser automation for LLM web interfaces.
Uses your actual Chrome browser profile to avoid CAPTCHA issues.
"""

import asyncio
import os
import random
import subprocess
import sys
from pathlib import Path
from typing import AsyncIterator, Callable

from playwright.async_api import async_playwright, BrowserContext, Page, Browser, TimeoutError as PlaywrightTimeout

from llm_selectors import (
    get_selectors,
    get_all_input_selectors,
    get_all_submit_selectors,
    get_all_response_selectors,
    LLMSelectors,
)

# Use actual Chrome profile on macOS
CHROME_USER_DATA = Path.home() / "Library" / "Application Support" / "Google" / "Chrome"
# Fallback to separate profile if Chrome profile doesn't exist
BROWSER_DATA_DIR = Path.home() / ".debate" / "browser-data"

# Shared browser instance (managed by orchestrator)
_shared_browser: Browser | None = None
_shared_context: BrowserContext | None = None
_chrome_process: subprocess.Popen | None = None

def get_chrome_path():
    """Get the path to Chrome executable."""
    if sys.platform == "darwin":
        chrome_paths = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Chrome.app/Contents/MacOS/Chrome",
        ]
        for path in chrome_paths:
            if os.path.exists(path):
                return path
    return None

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAY_BASE = 2  # seconds


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
    """Browser automation client for a single LLM."""

    def __init__(
        self,
        llm_name: str,
        browser_data_dir: Path = BROWSER_DATA_DIR,
        headless: bool = False,
        shared_context: BrowserContext | None = None,
    ):
        self.llm_name = llm_name
        self.selectors = get_selectors(llm_name)
        self.browser_data_dir = browser_data_dir / llm_name
        self.headless = headless
        self._shared_context = shared_context  # If provided, use this instead of creating our own
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._playwright = None
        self._owns_browser = False  # Whether we created the browser ourselves

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.stop()

    async def start(self):
        """Start browser - uses shared context if provided, else creates own browser."""
        if self._shared_context:
            # Use shared browser context from orchestrator
            self._context = self._shared_context
            self._page = await self._context.new_page()
            self._owns_browser = False
            return

        # Create our own browser (standalone mode) using saved profile
        self._owns_browser = True
        self._playwright = await async_playwright().start()

        # When running standalone, always use the separate profile (not system Chrome)
        # This is because system Chrome approach is handled by the orchestrator
        # Profile is in ~/.debate/browser-data/pw-{llm_name}/ (pw = playwright)
        profile_dir = BROWSER_DATA_DIR / f"pw-{self.llm_name}"
        profile_dir.mkdir(parents=True, exist_ok=True)

        # Clean up stale lock files from crashed sessions
        singleton_lock = profile_dir / "SingletonLock"
        if singleton_lock.exists():
            try:
                singleton_lock.unlink()
            except Exception:
                pass

        self._context = await self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=self.headless,
            viewport={"width": 1280, "height": 900},
        )

        # Get or create page
        if self._context.pages:
            self._page = self._context.pages[0]
        else:
            self._page = await self._context.new_page()

    async def stop(self):
        """Close page (and browser if we own it)."""
        if self._page:
            try:
                await self._page.close()
            except Exception:
                pass
            self._page = None

        # Only close browser if we created it ourselves
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

        # Try one more pass with query_selector (might be hidden)
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
            await self._page.goto(self.selectors.url, timeout=20000)
            await asyncio.sleep(2)  # Let page settle
            await self._page.wait_for_load_state("domcontentloaded", timeout=10000)

            # Try to find input field (indicates logged in)
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

        # Give extra time for any redirects after login
        await asyncio.sleep(2)

        # Verify login worked
        if await self.is_logged_in():
            print(f"[{self.llm_name.upper()}] ✓ Login successful! Session saved.")
        else:
            print(f"[{self.llm_name.upper()}] ⚠ Could not verify login. Try navigating to the chat page and press Enter again...")
            await asyncio.get_event_loop().run_in_executor(None, input)
            if await self.is_logged_in():
                print(f"[{self.llm_name.upper()}] ✓ Login verified!")

    async def send_prompt(
        self,
        prompt: str,
        on_chunk: Callable[[str], None] | None = None,
        timeout: int = 120000,
    ) -> str:
        """
        Send a prompt and stream the response.

        Args:
            prompt: The prompt to send
            on_chunk: Optional callback for streaming chunks
            timeout: Max time to wait for response (ms)

        Returns:
            Full response text
        """
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
                    # Refresh the page before retry
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

        # Navigate to new chat
        await self._page.goto(self.selectors.new_chat_url, timeout=30000)
        await asyncio.sleep(1)  # Let page initialize
        await self._page.wait_for_load_state("domcontentloaded", timeout=15000)
        await asyncio.sleep(0.5)  # Additional settle time

        # Find and fill input field
        input_selectors = get_all_input_selectors(self.llm_name)
        input_el = await self._find_element_with_fallbacks(
            input_selectors,
            timeout=15000,
            description="input field",
        )

        # Focus and type
        await input_el.click()
        await asyncio.sleep(0.2)

        # Use fill for textarea, type for contenteditable
        try:
            await input_el.fill(prompt)
        except Exception:
            # Fallback to typing character by character
            await input_el.type(prompt, delay=10)

        # Small delay before submit
        await asyncio.sleep(0.3)

        # Find and click submit button
        submit_selectors = get_all_submit_selectors(self.llm_name)
        submit_btn = await self._find_element_with_fallbacks(
            submit_selectors,
            timeout=5000,
            description="submit button",
        )

        await submit_btn.click()

        # Wait for response to start and stream it
        response_text = await self._stream_response(on_chunk, timeout)
        return response_text

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

        # Wait for response to appear
        await asyncio.sleep(1)

        while True:
            elapsed = (asyncio.get_event_loop().time() - start_time) * 1000
            if elapsed > timeout:
                if last_text:
                    return last_text  # Return partial response
                raise ResponseTimeoutError(f"Response timeout after {timeout}ms")

            # Try all response selectors
            current_text = ""
            for selector in response_selectors:
                try:
                    # Get all matching elements (in case of multiple messages)
                    elements = await self._page.query_selector_all(selector)
                    if elements:
                        # Get the last element's text (most recent response)
                        last_el = elements[-1]
                        current_text = await last_el.inner_text()
                        if current_text:
                            break
                except Exception:
                    continue

            if current_text:
                # Send new chunks to callback
                if current_text != last_text:
                    if on_chunk and len(current_text) > len(last_text):
                        new_content = current_text[len(last_text):]
                        if new_content:
                            on_chunk(new_content)
                    last_text = current_text
                    stable_count = 0
                else:
                    stable_count += 1

                # Check if response is complete
                is_complete = await self._check_response_complete()
                if is_complete:
                    return last_text

                # Fallback: if text stable for 3+ seconds, assume complete
                if stable_count > 30 and last_text:  # 30 * 100ms = 3 seconds
                    return last_text

            await asyncio.sleep(0.1)

    async def _check_response_complete(self) -> bool:
        """Check if the response generation is complete."""
        if not self._page:
            return False

        # Check for completion indicator
        if self.selectors.response_complete_indicator:
            try:
                el = await self._page.query_selector(
                    self.selectors.response_complete_indicator
                )
                if el:
                    return True
            except Exception:
                pass

        # Check if stop button is gone (indicates completion)
        if self.selectors.stop_selector:
            try:
                stop_btn = await self._page.query_selector(self.selectors.stop_selector)
                if stop_btn:
                    is_visible = await stop_btn.is_visible()
                    if not is_visible:
                        return True
                else:
                    # Stop button not in DOM - might be complete
                    return False
            except Exception:
                pass

        return False

    async def stream_prompt(
        self,
        prompt: str,
        timeout: int = 120000,
    ) -> AsyncIterator[str]:
        """
        Send a prompt and yield response chunks.

        Args:
            prompt: The prompt to send
            timeout: Max time to wait (ms)

        Yields:
            Response text chunks
        """
        queue: asyncio.Queue[str | None] = asyncio.Queue()

        def on_chunk(chunk: str):
            queue.put_nowait(chunk)

        async def run_prompt():
            try:
                await self.send_prompt(prompt, on_chunk=on_chunk, timeout=timeout)
            finally:
                queue.put_nowait(None)  # Signal completion

        # Start prompt in background
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
        self._browser = None
        self._context: BrowserContext | None = None

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.stop()

    async def start(self):
        """Start shared browser and all LLM clients."""
        global _chrome_process, _shared_browser, _shared_context

        self._playwright = await async_playwright().start()

        # Try to use actual Chrome first
        chrome_path = get_chrome_path()
        use_system_chrome = chrome_path and CHROME_USER_DATA.exists() and not self.headless

        if use_system_chrome:
            debug_port = 9222

            # Check if debug port is already in use (Chrome already running with debug)
            import socket
            port_in_use = False
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                result = sock.connect_ex(('localhost', debug_port))
                port_in_use = (result == 0)
                sock.close()
            except Exception:
                pass

            if port_in_use:
                print("Found existing Chrome with debug port, connecting...")
            else:
                print("=" * 60)
                print(" LLM Debate - Launching Chrome with your profile")
                print(" IMPORTANT: Close Chrome completely before continuing!")
                print("=" * 60)

                _chrome_process = subprocess.Popen([
                    chrome_path,
                    f"--remote-debugging-port={debug_port}",
                    f"--user-data-dir={CHROME_USER_DATA}",
                    "--no-first-run",
                    "--no-default-browser-check",
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

                await asyncio.sleep(3)

            try:
                self._browser = await self._playwright.chromium.connect_over_cdp(
                    f"http://localhost:{debug_port}"
                )
                _shared_browser = self._browser
                contexts = self._browser.contexts
                if contexts:
                    self._context = contexts[0]
                else:
                    self._context = await self._browser.new_context()
                _shared_context = self._context
                print("[OK] Connected to Chrome with your existing logins!")
            except Exception as e:
                print(f"Could not connect to Chrome: {e}")
                print("Using separate browser profiles instead...")
                if _chrome_process:
                    _chrome_process.terminate()
                    _chrome_process = None
                use_system_chrome = False

        if use_system_chrome:
            # All LLMs share the same Chrome context
            for name in self.llm_names:
                client = LLMClient(name, headless=self.headless, shared_context=self._context)
                await client.start()
                self.clients[name] = client
        else:
            # Each LLM gets its own browser with its own profile (from setup_auth.py)
            print("[INFO] Using separate Chromium browsers with saved profiles")
            print("[INFO] Run 'python setup_auth.py' first if not logged in")

            for name in self.llm_names:
                client = LLMClient(name, headless=self.headless)
                await client.start()
                self.clients[name] = client

    async def stop(self):
        """Stop all LLM clients and shared browser."""
        global _chrome_process, _shared_browser, _shared_context

        # Stop all clients (they'll just close their pages)
        for client in self.clients.values():
            try:
                await client.stop()
            except Exception as e:
                print(f"Warning: Error stopping client: {e}")

        self.clients.clear()

        # Close shared context and browser
        if self._context:
            try:
                await self._context.close()
            except Exception:
                pass
            self._context = None
            _shared_context = None

        if self._browser:
            try:
                await self._browser.close()
            except Exception:
                pass
            self._browser = None
            _shared_browser = None

        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

        # Terminate Chrome if we launched it
        if _chrome_process:
            _chrome_process.terminate()
            _chrome_process = None

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
        """
        Send prompt to all LLMs in parallel.

        Args:
            prompt: The prompt to send
            on_update: Callback(llm_name, chunk) for streaming updates
            timeout: Max time per LLM (ms)

        Returns:
            Dict mapping LLM name to response
        """
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

        # Run all LLMs in parallel
        tasks = [
            query_llm(name, client)
            for name, client in self.clients.items()
        ]
        results = await asyncio.gather(*tasks)

        return dict(results)
