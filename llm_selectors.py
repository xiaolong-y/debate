"""
DOM selectors for LLM web interfaces.
Centralized here for easy updates when UIs change.

Each selector includes primary and fallback options to handle UI changes.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, List

from config import LLMS


@dataclass
class LLMSelectors:
    """Selectors for interacting with an LLM web interface."""
    url: str
    new_chat_url: str
    input_selector: str
    submit_selector: str
    response_selector: str
    stop_selector: Optional[str] = None
    response_complete_indicator: Optional[str] = None
    # Fallback selectors for when UI changes
    input_fallbacks: List[str] = field(default_factory=list)
    submit_fallbacks: List[str] = field(default_factory=list)
    response_fallbacks: List[str] = field(default_factory=list)


SELECTORS = {
    "claude": LLMSelectors(
        url=LLMS["claude"]["url"],
        new_chat_url=LLMS["claude"]["new_chat_url"],
        # Primary: ProseMirror contenteditable editor
        input_selector="div.ProseMirror[contenteditable='true']",
        submit_selector="button[aria-label='Send Message']",
        response_selector="div[data-is-streaming]",
        stop_selector="button[aria-label='Stop Response']",
        response_complete_indicator="div[data-is-streaming='false']",
        # Fallbacks for UI variations
        input_fallbacks=[
            "[contenteditable='true'].ProseMirror",
            "div[contenteditable='true']",
            "[data-placeholder*='message']",
            "fieldset [contenteditable='true']",
        ],
        submit_fallbacks=[
            "button[type='submit']",
            "button:has(svg[data-icon='send'])",
            "[aria-label*='Send']",
            "button[data-testid='send-button']",
        ],
        response_fallbacks=[
            "[data-message-author='assistant']",
            ".assistant-message",
            "[class*='response']",
            "[class*='message'][class*='assistant']",
        ],
    ),
    "chatgpt": LLMSelectors(
        url=LLMS["chatgpt"]["url"],
        new_chat_url=LLMS["chatgpt"]["new_chat_url"],
        # ChatGPT uses contenteditable div now, not textarea
        input_selector="div#prompt-textarea[contenteditable='true']",
        submit_selector="button[data-testid='send-button']",
        # Target the markdown prose content inside assistant message, not the wrapper
        response_selector="div[data-message-author-role='assistant'] .markdown.prose",
        stop_selector="button[aria-label='Stop generating']",
        response_complete_indicator=None,  # Check for absence of streaming indicator
        input_fallbacks=[
            "#prompt-textarea",
            "div[contenteditable='true'][id='prompt-textarea']",
            "[contenteditable='true'][data-placeholder]",
            "textarea[placeholder*='message']",
            "[contenteditable='true']",
            "div[role='textbox']",
        ],
        submit_fallbacks=[
            "button[aria-label='Send prompt']",
            "[data-testid='send-button']",
            "button[aria-label='Send message']",
            "button:has(svg path[d*='M15.192'])",  # Send icon path
            "form button[type='submit']",
            "button.send-button",
        ],
        response_fallbacks=[
            # Target actual content, not wrapper elements
            "div[data-message-author-role='assistant'] .prose",
            "div[data-message-author-role='assistant'] .markdown",
            "[data-message-author-role='assistant'] div.whitespace-pre-wrap",
            ".agent-turn .markdown",
            "article[data-testid='conversation-turn-3'] .prose",
        ],
    ),
    "gemini": LLMSelectors(
        url=LLMS["gemini"]["url"],
        new_chat_url=LLMS["gemini"]["new_chat_url"],
        # Gemini uses custom web components - selectors updated Jan 2025
        input_selector="rich-textarea div[contenteditable='true']",
        submit_selector="button.send-button",
        response_selector=".model-response-text .markdown-main-panel",
        stop_selector="button[aria-label='Stop responding']",
        response_complete_indicator=None,
        input_fallbacks=[
            ".ql-editor[contenteditable='true']",
            "[aria-label*='Enter a prompt']",
            "div[contenteditable='true']",
            "rich-textarea [contenteditable='true']",
        ],
        submit_fallbacks=[
            "button[aria-label='Send message']",
            "[aria-label='Submit']",
            "button[data-test-id='send-button']",
            "button mat-icon-button",
        ],
        response_fallbacks=[
            # Gemini response content selectors
            ".response-content",
            "message-content .markdown",
            ".model-response-text",
            "[class*='response'] .markdown",
            "model-response .content",
            ".conversation-container .model-response",
        ],
    ),
}


def get_selectors(llm: str) -> LLMSelectors:
    """Get selectors for a specific LLM."""
    if llm not in SELECTORS:
        raise ValueError(f"Unknown LLM: {llm}. Available: {list(SELECTORS.keys())}")
    return SELECTORS[llm]


def get_all_input_selectors(llm: str) -> list[str]:
    """Get all possible input selectors for an LLM (primary + fallbacks)."""
    sel = get_selectors(llm)
    return [sel.input_selector] + sel.input_fallbacks


def get_all_submit_selectors(llm: str) -> list[str]:
    """Get all possible submit selectors for an LLM (primary + fallbacks)."""
    sel = get_selectors(llm)
    return [sel.submit_selector] + sel.submit_fallbacks


def get_all_response_selectors(llm: str) -> list[str]:
    """Get all possible response selectors for an LLM (primary + fallbacks)."""
    sel = get_selectors(llm)
    return [sel.response_selector] + sel.response_fallbacks
