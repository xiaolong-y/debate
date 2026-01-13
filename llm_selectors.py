"""
DOM selectors for LLM web interfaces.
Centralized here for easy updates when UIs change.

Each selector includes primary and fallback options to handle UI changes.
"""

from dataclasses import dataclass, field


@dataclass
class LLMSelectors:
    """Selectors for interacting with an LLM web interface."""
    url: str
    new_chat_url: str
    input_selector: str
    submit_selector: str
    response_selector: str
    stop_selector: str | None = None
    response_complete_indicator: str | None = None
    # Fallback selectors for when UI changes
    input_fallbacks: list[str] = field(default_factory=list)
    submit_fallbacks: list[str] = field(default_factory=list)
    response_fallbacks: list[str] = field(default_factory=list)


SELECTORS = {
    "claude": LLMSelectors(
        url="https://claude.ai",
        new_chat_url="https://claude.ai/new",
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
        url="https://chatgpt.com",
        new_chat_url="https://chatgpt.com/",
        input_selector="#prompt-textarea",
        submit_selector="button[data-testid='send-button']",
        response_selector="div[data-message-author-role='assistant']",
        stop_selector="button[aria-label='Stop generating']",
        response_complete_indicator=None,  # Check for absence of streaming indicator
        input_fallbacks=[
            "textarea[placeholder*='message']",
            "[contenteditable='true']",
            "textarea#prompt-textarea",
        ],
        submit_fallbacks=[
            "button[aria-label='Send prompt']",
            "[data-testid='send-button']",
            "button:has(svg[class*='send'])",
        ],
        response_fallbacks=[
            "[data-message-author-role='assistant']",
            ".markdown.prose",
            "[class*='agent-turn']",
        ],
    ),
    "gemini": LLMSelectors(
        url="https://gemini.google.com",
        new_chat_url="https://gemini.google.com/app",
        # Gemini uses custom web components
        input_selector="rich-textarea div[contenteditable='true']",
        submit_selector="button[aria-label='Send message']",
        response_selector="message-content.model-response-text",
        stop_selector="button[aria-label='Stop responding']",
        response_complete_indicator=None,
        input_fallbacks=[
            ".ql-editor[contenteditable='true']",
            "[aria-label*='Enter a prompt']",
            "div[contenteditable='true']",
        ],
        submit_fallbacks=[
            "button.send-button",
            "[aria-label='Submit']",
            "button:has([data-icon='send'])",
        ],
        response_fallbacks=[
            ".model-response-text",
            "[class*='response-container']",
            ".markdown-main-panel",
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
