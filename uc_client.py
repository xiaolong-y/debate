"""
LLM client using undetected-chromedriver to bypass Cloudflare.
This replaces playwright_client.py for sites with bot detection.
"""

from __future__ import annotations

import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable, Optional, Dict

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from llm_selectors import get_selectors, LLMSelectors

# Browser data directory
BROWSER_DATA_DIR = Path.home() / ".debate" / "browser-data"

# Thread pool for running blocking Selenium code
_executor = ThreadPoolExecutor(max_workers=6)


class LLMClient:
    """Browser automation client using undetected-chromedriver."""

    def __init__(self, llm_name: str, headless: bool = False):
        self.llm_name = llm_name
        self.selectors = get_selectors(llm_name)
        self.profile_dir = BROWSER_DATA_DIR / f"uc-{llm_name}"
        self.headless = headless
        self.driver: uc.Chrome | None = None

    def start(self):
        """Start the browser."""
        self.profile_dir.mkdir(parents=True, exist_ok=True)

        options = uc.ChromeOptions()
        options.add_argument(f"--user-data-dir={self.profile_dir}")
        options.add_argument("--window-size=1280,900")

        if self.headless:
            options.add_argument("--headless=new")

        self.driver = uc.Chrome(options=options, use_subprocess=True)

    def stop(self):
        """Close the browser."""
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
            self.driver = None

    def is_logged_in(self) -> bool:
        """Check if user is logged in."""
        if not self.driver:
            return False

        try:
            self.driver.get(self.selectors.url)
            time.sleep(2)  # Let page load

            # Try to find the input field (indicates logged in)
            input_selectors = [self.selectors.input_selector] + self.selectors.input_fallbacks
            for selector in input_selectors:
                try:
                    element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if element:
                        return True
                except NoSuchElementException:
                    continue

            return False
        except Exception as e:
            print(f"[{self.llm_name}] Error checking login: {e}")
            return False

    def setup_auth(self):
        """Interactive auth setup."""
        if not self.driver:
            raise RuntimeError("Client not started")

        self.driver.get(self.selectors.url)
        print(f"\n{'='*60}")
        print(f"[{self.llm_name.upper()}] MANUAL LOGIN REQUIRED")
        print(f"{'='*60}")
        print(f"1. Complete any CAPTCHA/human verification")
        print(f"2. Log in with your credentials")
        print(f"3. Make sure you're on the main chat page")
        print(f"4. Press Enter here when done...")
        print(f"{'='*60}")
        input()

        time.sleep(2)
        if self.is_logged_in():
            print(f"[{self.llm_name.upper()}] ✓ Login verified!")
        else:
            print(f"[{self.llm_name.upper()}] ⚠ Could not verify login, but session may be saved.")

    def _find_element(self, selectors: list[str], timeout: int = 10) -> any:
        """Find element using multiple selectors with fallbacks."""
        for selector in selectors:
            try:
                element = WebDriverWait(self.driver, timeout // len(selectors)).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
                if element:
                    return element
            except TimeoutException:
                continue
        raise NoSuchElementException(f"Could not find element with selectors: {selectors}")

    def _find_clickable(self, selectors: list[str], timeout: int = 10) -> any:
        """Find clickable element using multiple selectors."""
        for selector in selectors:
            try:
                element = WebDriverWait(self.driver, timeout // len(selectors)).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                )
                if element:
                    return element
            except TimeoutException:
                continue
        raise NoSuchElementException(f"Could not find clickable element: {selectors}")

    def send_prompt(
        self,
        prompt: str,
        on_chunk: Callable[[str], None] | None = None,
        timeout: int = 120,
    ) -> str:
        """Send a prompt and get the response."""
        if not self.driver:
            raise RuntimeError("Client not started")

        # Navigate to new chat
        self.driver.get(self.selectors.new_chat_url)
        time.sleep(1.5)  # Reduced from 2s

        # Find input field
        input_selectors = [self.selectors.input_selector] + self.selectors.input_fallbacks
        input_el = self._find_element(input_selectors, timeout=10)

        # Clear and type prompt
        input_el.click()
        time.sleep(0.1)

        # For contenteditable divs, use JavaScript to set content (much faster for long text)
        try:
            # Try to set via JavaScript for speed
            self.driver.execute_script("""
                var el = arguments[0];
                var text = arguments[1];
                if (el.tagName === 'TEXTAREA' || el.tagName === 'INPUT') {
                    el.value = text;
                    el.dispatchEvent(new Event('input', { bubbles: true }));
                } else {
                    // contenteditable div
                    el.innerText = text;
                    el.dispatchEvent(new InputEvent('input', { bubbles: true, data: text }));
                }
            """, input_el, prompt)
        except Exception:
            # Fallback to send_keys (slower but more reliable)
            try:
                input_el.clear()
            except Exception:
                pass
            input_el.send_keys(prompt)

        time.sleep(0.2)

        # Find and click submit
        submit_selectors = [self.selectors.submit_selector] + self.selectors.submit_fallbacks
        submit_btn = self._find_clickable(submit_selectors, timeout=5)
        submit_btn.click()

        # Stream response
        return self._stream_response(on_chunk, timeout)

    def _stream_response(
        self,
        on_chunk: Callable[[str], None] | None,
        timeout: int,
    ) -> str:
        """Stream response as it's generated."""
        start_time = time.time()
        last_text = ""
        stable_count = 0
        response_selectors = [self.selectors.response_selector] + self.selectors.response_fallbacks

        print(f"[{self.llm_name}] Waiting for response with selectors: {response_selectors[:2]}...")
        time.sleep(0.5)  # Reduced from 1s - wait for response to start

        while True:
            elapsed = time.time() - start_time
            if elapsed > timeout:
                if last_text:
                    return last_text
                raise TimeoutException(f"Response timeout after {timeout}s")

            # Try all response selectors
            current_text = ""
            for selector in response_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        current_text = elements[-1].text
                        if current_text:
                            break
                except Exception:
                    continue

            if current_text:
                if current_text != last_text:
                    if len(last_text) == 0:
                        print(f"[{self.llm_name}] Got first response chunk ({len(current_text)} chars)")
                    if on_chunk and len(current_text) > len(last_text):
                        new_content = current_text[len(last_text):]
                        if new_content:
                            on_chunk(new_content)
                    last_text = current_text
                    stable_count = 0
                else:
                    stable_count += 1

                # Check if response is complete
                if self._is_response_complete():
                    print(f"[{self.llm_name}] Response complete ({len(last_text)} chars)")
                    return last_text

                # Fallback: if stable for 2+ seconds (reduced from 3s)
                if stable_count > 20 and last_text:
                    print(f"[{self.llm_name}] Response stable, returning ({len(last_text)} chars)")
                    return last_text

            time.sleep(0.1)

    def _is_response_complete(self) -> bool:
        """Check if response is complete."""
        # Check for completion indicator
        if self.selectors.response_complete_indicator:
            try:
                el = self.driver.find_element(
                    By.CSS_SELECTOR,
                    self.selectors.response_complete_indicator
                )
                if el:
                    return True
            except NoSuchElementException:
                pass

        # Check if stop button is gone
        if self.selectors.stop_selector:
            try:
                stop_btn = self.driver.find_element(
                    By.CSS_SELECTOR,
                    self.selectors.stop_selector
                )
                if not stop_btn.is_displayed():
                    return True
            except NoSuchElementException:
                # Stop button not found - might be complete
                return False

        return False


class DebateOrchestrator:
    """Orchestrates parallel prompts to multiple LLMs using undetected-chromedriver."""

    def __init__(
        self,
        llms: list[str] | None = None,
        headless: bool = False,
    ):
        self.llm_names = llms or ["claude", "chatgpt", "gemini"]
        self.headless = headless
        self.clients: dict[str, LLMClient] = {}

    def start(self):
        """Start all LLM clients in parallel for speed."""
        import concurrent.futures

        print("Starting browsers in parallel...")

        def start_one(name: str) -> tuple[str, LLMClient]:
            client = LLMClient(name, headless=self.headless)
            client.start()
            return name, client

        # Start all browsers in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = {executor.submit(start_one, name): name for name in self.llm_names}
            for future in concurrent.futures.as_completed(futures):
                try:
                    name, client = future.result()
                    self.clients[name] = client
                    print(f"  ✓ {name} ready")
                except Exception as e:
                    print(f"  ✗ {futures[future]} failed: {e}")

        print("All browsers started!")

    def stop(self):
        """Stop all LLM clients."""
        for client in self.clients.values():
            client.stop()
        self.clients.clear()

    def check_auth(self) -> dict[str, bool]:
        """Check which LLMs are logged in (in parallel)."""
        import concurrent.futures

        def check_one(name: str, client: LLMClient) -> tuple[str, bool]:
            return name, client.is_logged_in()

        result = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(check_one, name, client) for name, client in self.clients.items()]
            for future in concurrent.futures.as_completed(futures):
                name, logged_in = future.result()
                result[name] = logged_in

        return result

    def setup_all_auth(self):
        """Interactive setup for all LLMs."""
        auth_status = self.check_auth()
        for name, logged_in in auth_status.items():
            if not logged_in:
                client = self.clients.get(name)
                if client:
                    client.setup_auth()

    async def debate(
        self,
        prompt: str,
        on_update: Callable[[str, str], None] | None = None,
        timeout: int = 120,
    ) -> dict[str, str]:
        """Send prompt to all LLMs in parallel."""
        loop = asyncio.get_event_loop()

        async def query_llm(name: str, client: LLMClient) -> tuple[str, str]:
            def chunk_callback(chunk: str):
                if on_update:
                    on_update(name, chunk)

            try:
                # Run blocking Selenium code in thread pool
                response = await loop.run_in_executor(
                    _executor,
                    lambda: client.send_prompt(prompt, on_chunk=chunk_callback, timeout=timeout)
                )
                return name, response
            except Exception as e:
                error_msg = f"[Error: {type(e).__name__}: {str(e)[:100]}]"
                if on_update:
                    on_update(name, error_msg)
                return name, error_msg

        # Run all LLMs in parallel
        tasks = [query_llm(name, client) for name, client in self.clients.items()]
        results = await asyncio.gather(*tasks)

        return dict(results)

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()


# Async context manager wrapper
class AsyncDebateOrchestrator:
    """Async wrapper for DebateOrchestrator."""

    def __init__(self, llms: list[str] | None = None, headless: bool = False):
        self._orch = DebateOrchestrator(llms, headless)

    async def __aenter__(self):
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(_executor, self._orch.start)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(_executor, self._orch.stop)

    async def check_auth(self) -> dict[str, bool]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_executor, self._orch.check_auth)

    async def setup_all_auth(self):
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(_executor, self._orch.setup_all_auth)

    async def debate(
        self,
        prompt: str,
        on_update: Callable[[str, str], None] | None = None,
        timeout: int = 120,
    ) -> dict[str, str]:
        return await self._orch.debate(prompt, on_update, timeout)

    @property
    def clients(self):
        return self._orch.clients
