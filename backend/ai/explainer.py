"""
explainer.py - AI tutor that explains one stage of the conversion.

The frontend sends the stage name and that stage's data (for example the
subset construction table). We turn the data into readable JSON, put it in
the prompt, and ask the LLM to explain it simply, like a friendly tutor.
"""

from __future__ import annotations

import json

from ai.llm_client import ask_llm

STAGE_DESCRIPTIONS = {
    "postfix": "converting the regex to postfix with explicit concatenation using the shunting-yard algorithm",
    "nfa": "building an ε-NFA from the postfix expression using Thompson's construction",
    "dfa": "converting the ε-NFA to a DFA using ε-closures and the subset construction",
    "min_dfa": "minimizing the DFA using the table-filling (Myhill-Nerode) method",
    "simulate": "running an input string on the automaton (DFA, or the ε-NFA with a set of active states)",
    "direct_dfa": "building a DFA directly from the regex with the followpos method (syntax tree, nullable, firstpos, lastpos, followpos)",
    "regex_back": "converting the minimized DFA back into a regular expression with state elimination",
    "properties": "deciding properties of the language: empty, finite or infinite, shortest accepted strings",
    "operations": "combining languages with the product automaton or the complement construction (closure properties)",
    "verify": "verifying an AI-generated regex with examples and DFA equivalence",
}

SYSTEM_PROMPT = """You are a friendly Automata Theory tutor for undergraduate students.
Explain the given conversion step in simple language, using the actual data provided
(refer to the real state names, symbols and table entries).
Structure: 1) what this step does and why, 2) a walk through the important rows of the
data, 3) one key takeaway. Keep it under 300 words. Use plain text with short
paragraphs or bullet points, no tables."""

# Keep prompts small: very large automata are summarised by truncation.
MAX_DATA_CHARACTERS = 12000


def explain_step(stage: str, data: dict, regex: str) -> str:
    """Ask the LLM to explain `stage` for `regex` using the stage's `data`."""
    description = STAGE_DESCRIPTIONS.get(stage, stage)
    data_text = json.dumps(data, ensure_ascii=False, indent=1)
    if len(data_text) > MAX_DATA_CHARACTERS:
        data_text = data_text[:MAX_DATA_CHARACTERS] + "\n... (truncated)"

    user_message = (
        f"Regular expression: {regex}\n"
        f"Step: {description}\n\n"
        f"Data produced by this step (JSON):\n{data_text}\n\n"
        "Please explain this step to me."
    )
    return ask_llm(SYSTEM_PROMPT, user_message)
