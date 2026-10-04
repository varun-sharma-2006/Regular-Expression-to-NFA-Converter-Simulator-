"""
nl_to_regex.py - turn an English description into a regex using the LLM.

Steps:
    1. Ask the LLM with a STRICT system prompt: reply with only the regex,
       in exactly our syntax.
    2. Clean the reply (remove quotes, code fences, "Regex:" prefixes).
    3. Validate it with OUR parser. If invalid, tell the LLM what was wrong
       and retry (at most MAX_ATTEMPTS times).
The parser is the gatekeeper: the LLM's text is never trusted blindly.
"""

from __future__ import annotations

from ai.llm_client import ask_llm
from automata.parser import RegexSyntaxError, parse_regex

MAX_ATTEMPTS = 3

# The answer is one short line. The extra room is for models that "think"
# before answering, since thinking also counts towards the limit.
MAX_REPLY_TOKENS = 1500

SYSTEM_PROMPT = """You convert English descriptions of formal languages into regular expressions.

Output rules (follow exactly):
- Reply with ONLY the regular expression on one line. No explanation, no quotes, no code block.
- Allowed symbols: letters a-z and A-Z, and digits 0-9.
- Allowed operators: | (union), * (zero or more), + (one or more), ? (zero or one), parentheses ( ).
- Character classes are allowed as a shorthand: [abc], [a-z], [0-9].
- Concatenation is written by putting symbols next to each other (ab means a then b).
- Write ε for the empty string.
- NOT allowed: \\d, \\w, ., ^, $, {n}, spaces, negated classes like [^a].
- If the description does not name an alphabet, assume {a, b}.

Examples:
strings over {a,b} that end with abb -> (a|b)*abb
strings over {0,1} with an even number of 0s -> (1*01*0)*1*
strings of a's of odd length -> a(aa)*"""


def clean_llm_output(text: str) -> str:
    """
    LLMs sometimes wrap the answer, e.g. ```(a|b)*``` or 'Regex: (a|b)*'.
    Keep only the first non-empty line and strip such decorations.
    """
    lines = []
    for line in text.replace("```", "\n").splitlines():
        if line.strip():
            lines.append(line.strip())
    if not lines:
        return ""
    answer = lines[0]
    for prefix in ("regex:", "regular expression:", "answer:"):
        if answer.lower().startswith(prefix):
            answer = answer[len(prefix):].strip()
    answer = answer.strip("`'\" ")
    answer = answer.replace("\\epsilon", "ε").replace("Ɛ", "ε")
    return answer


def generate_regex(description: str) -> dict:
    """
    Ask the LLM for a regex matching `description`.

    Returns {"regex": str | None, "attempts": [...], "error": str | None}.
    Each attempt records what the LLM said and whether our parser accepted it.
    """
    attempts = []
    message = f"Description: {description}"

    for _ in range(MAX_ATTEMPTS):
        raw_reply = ask_llm(SYSTEM_PROMPT, message, max_tokens=MAX_REPLY_TOKENS)
        candidate = clean_llm_output(raw_reply)
        try:
            parse_regex(candidate)
            attempts.append({"reply": raw_reply, "regex": candidate, "valid": True, "error": None})
            return {"regex": candidate, "attempts": attempts, "error": None}
        except RegexSyntaxError as error:
            attempts.append({"reply": raw_reply, "regex": candidate, "valid": False, "error": error.message})
            # Retry with feedback: show the LLM its mistake.
            message = (
                f"Description: {description}\n\n"
                f"Your previous answer '{candidate}' is invalid: {error.message}\n"
                "Reply again with ONLY a valid regular expression in the allowed syntax."
            )

    return {
        "regex": None,
        "attempts": attempts,
        "error": f"The AI did not produce a valid regex after {MAX_ATTEMPTS} attempts.",
    }
