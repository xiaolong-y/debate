"""
Triage module for synthesizing and arbitrating LLM responses.
Combines both operations in a single pass for token efficiency.
"""

from enum import Enum
from typing import Callable

from playwright_client import LLMClient


class TriageMode(str, Enum):
    """Triage mode - now unified does both synthesis and arbitration."""
    UNIFIED = "unified"
    # Legacy modes kept for compatibility
    SYNTHESIS = "synthesis"
    ARBITRATION = "arbitration"


# System prompt injected to make unified analysis work
SYSTEM_PROMPT = """When analyzing the three AI responses below, structure your analysis in exactly this format:

## Consensus Points
List facts and conclusions where all three models agree. These represent high-confidence information.

## Key Disagreements
Identify where the models conflict or provide different answers. For each disagreement:
- State the conflicting positions
- Evaluate the reasoning quality
- Indicate which position seems most credible (or mark as "needs verification")

## Synthesized Answer
Merge the best insights from all three responses into a coherent, comprehensive answer.
- Integrate complementary perspectives
- Attribute unique insights when valuable (e.g., "As noted by one model...")
- Remove redundancy while preserving nuance

Be concise but thorough. The goal is to give the user maximum value from consulting three different AI models."""


PROMPTS = {
    TriageMode.UNIFIED: """You are analyzing responses from three AI models: Claude, ChatGPT, and Gemini.

{system_prompt}

---

ORIGINAL QUESTION:
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

Now provide your unified analysis:""",

    # Legacy prompts for backwards compatibility
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


def build_triage_prompt(
    prompt: str,
    responses: dict[str, str],
    mode: TriageMode = TriageMode.UNIFIED,
) -> str:
    """Build the triage prompt with all responses."""
    template = PROMPTS[mode]

    return template.format(
        system_prompt=SYSTEM_PROMPT if mode == TriageMode.UNIFIED else "",
        prompt=prompt,
        claude=responses.get("claude", "[No response from Claude]"),
        chatgpt=responses.get("chatgpt", "[No response from ChatGPT]"),
        gemini=responses.get("gemini", "[No response from Gemini]"),
    )


async def run_triage(
    prompt: str,
    responses: dict[str, str],
    mode: TriageMode = TriageMode.UNIFIED,
    triage_llm: str = "claude",
    on_chunk: Callable[[str], None] | None = None,
    timeout: int = 120000,
) -> str:
    """
    Run triage on collected responses.

    Args:
        prompt: Original user prompt
        responses: Dict of LLM name -> response
        mode: Triage mode (unified recommended)
        triage_llm: Which LLM to use for triage
        on_chunk: Streaming callback
        timeout: Max time (ms)

    Returns:
        Triage result
    """
    triage_prompt = build_triage_prompt(prompt, responses, mode)

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
    mode: TriageMode = TriageMode.UNIFIED,
    on_chunk: Callable[[str], None] | None = None,
    timeout: int = 120000,
) -> str:
    """
    Run triage using an already-open client.

    Args:
        client: Existing LLMClient instance
        prompt: Original user prompt
        responses: Dict of LLM name -> response
        mode: Triage mode (unified recommended)
        on_chunk: Streaming callback
        timeout: Max time (ms)

    Returns:
        Triage result
    """
    triage_prompt = build_triage_prompt(prompt, responses, mode)

    return await client.send_prompt(
        triage_prompt,
        on_chunk=on_chunk,
        timeout=timeout,
    )
