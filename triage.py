"""
Triage module for synthesizing/arbitrating LLM responses.
"""

from enum import Enum
from typing import Callable

from playwright_client import LLMClient


class TriageMode(str, Enum):
    SYNTHESIS = "synthesis"
    ARBITRATION = "arbitration"


PROMPTS = {
    TriageMode.SYNTHESIS: """You are synthesizing responses from three AI models: Claude, ChatGPT, and Gemini.

Your task:
1. Identify the best ideas from each response
2. Merge them into a coherent, unified answer
3. Remove redundancy while preserving unique insights
4. When a particular model had a notably good point, attribute it (e.g., "As Claude noted...")

Be concise but comprehensive. The goal is to give the user the best possible answer by combining the strengths of all three models.

---

ORIGINAL PROMPT:
{prompt}

---

CLAUDE'S RESPONSE:
{claude}

---

CHATGPT'S RESPONSE:
{chatgpt}

---

GEMINI'S RESPONSE:
{gemini}

---

Now provide your synthesis:""",

    TriageMode.ARBITRATION: """You are arbitrating between three AI models: Claude, ChatGPT, and Gemini.

Your task:
1. AGREEMENTS: List facts/claims where all three models agree (high confidence)
2. DISAGREEMENTS: List points where they conflict or contradict each other
3. VERDICT: For each disagreement, evaluate the reasoning and evidence, then:
   - Declare which model is correct, OR
   - Mark as "needs verification" if you can't determine the truth

Format your response clearly with sections for Agreements, Disagreements, and Verdicts.

---

ORIGINAL PROMPT:
{prompt}

---

CLAUDE'S RESPONSE:
{claude}

---

CHATGPT'S RESPONSE:
{chatgpt}

---

GEMINI'S RESPONSE:
{gemini}

---

Now provide your arbitration:""",
}


async def run_triage(
    prompt: str,
    responses: dict[str, str],
    mode: TriageMode = TriageMode.SYNTHESIS,
    triage_llm: str = "claude",
    on_chunk: Callable[[str], None] | None = None,
    timeout: int = 120000,
) -> str:
    """
    Run triage on collected responses.

    Args:
        prompt: Original user prompt
        responses: Dict of LLM name -> response
        mode: Synthesis or arbitration
        triage_llm: Which LLM to use for triage
        on_chunk: Streaming callback
        timeout: Max time (ms)

    Returns:
        Triage result
    """
    # Build triage prompt
    triage_prompt = PROMPTS[mode].format(
        prompt=prompt,
        claude=responses.get("claude", "[No response from Claude]"),
        chatgpt=responses.get("chatgpt", "[No response from ChatGPT]"),
        gemini=responses.get("gemini", "[No response from Gemini]"),
    )

    # Use specified LLM for triage
    async with LLMClient(triage_llm, headless=False) as client:
        result = await client.send_prompt(
            triage_prompt,
            on_chunk=on_chunk,
            timeout=timeout,
        )
        return result


async def run_triage_with_existing_client(
    client: LLMClient,
    prompt: str,
    responses: dict[str, str],
    mode: TriageMode = TriageMode.SYNTHESIS,
    on_chunk: Callable[[str], None] | None = None,
    timeout: int = 120000,
) -> str:
    """
    Run triage using an already-open client.

    Args:
        client: Existing LLMClient instance
        prompt: Original user prompt
        responses: Dict of LLM name -> response
        mode: Synthesis or arbitration
        on_chunk: Streaming callback
        timeout: Max time (ms)

    Returns:
        Triage result
    """
    triage_prompt = PROMPTS[mode].format(
        prompt=prompt,
        claude=responses.get("claude", "[No response from Claude]"),
        chatgpt=responses.get("chatgpt", "[No response from ChatGPT]"),
        gemini=responses.get("gemini", "[No response from Gemini]"),
    )

    return await client.send_prompt(
        triage_prompt,
        on_chunk=on_chunk,
        timeout=timeout,
    )
