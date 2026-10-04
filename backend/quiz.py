"""
quiz.py - practice mode: a random regex plus questions about its automata.

The answers are computed by our own algorithms, so they are always correct.
Questions:
    * Is the string w accepted?            (3 strings, mixed accept/reject)
    * Is ε (the empty string) accepted?
    * How many states does the minimized DFA have?
    * Is the language finite or infinite?
    * How long is the shortest accepted string?
    * Which state does the minimized DFA reach after reading w?
"""

from __future__ import annotations

import itertools
import random

from automata.operations import describe_language
from automata.pipeline import regex_to_min_dfa
from automata.simulate import simulate_dfa

LEVELS = {
    # level: (tree depth, min states, max states)
    "easy": (2, 2, 3),
    "medium": (3, 3, 5),
    "hard": (4, 4, 7),
}


def random_regex(generator: random.Random, depth: int, alphabet: str = "ab") -> str:
    """Build a random regex recursively (same idea as tests/test_random.py)."""
    if depth == 0 or generator.random() < 0.25:
        return generator.choice(alphabet)
    kind = generator.choice(["concat", "concat", "union", "star", "plus", "optional"])
    if kind == "concat":
        return random_regex(generator, depth - 1, alphabet) + random_regex(generator, depth - 1, alphabet)
    if kind == "union":
        return "(" + random_regex(generator, depth - 1, alphabet) + "|" + random_regex(generator, depth - 1, alphabet) + ")"
    operator = {"star": "*", "plus": "+", "optional": "?"}[kind]
    inner = random_regex(generator, depth - 1, alphabet)
    if len(inner) > 1 and not (inner.startswith("(") and inner.endswith(")")):
        inner = "(" + inner + ")"
    return inner + operator


def _all_strings(alphabet: list[str], max_length: int) -> list[str]:
    strings = []
    for length in range(1, max_length + 1):
        for letters in itertools.product(alphabet, repeat=length):
            strings.append("".join(letters))
    return strings


def make_quiz(level: str = "medium", seed: int | None = None) -> dict:
    """Create one quiz. `seed` makes it reproducible (used by the tests)."""
    depth, min_states, max_states = LEVELS.get(level, LEVELS["medium"])
    generator = random.Random(seed)

    # Try random regexes until one has an interesting minimized DFA.
    for _ in range(500):
        regex = random_regex(generator, depth)
        dfa = regex_to_min_dfa(regex)
        properties = describe_language(dfa, sample_size=6)
        if min_states <= len(dfa.states) <= max_states and not properties["empty"]:
            break

    candidates = _all_strings(dfa.alphabet, 5)
    accepted = [s for s in candidates if simulate_dfa(dfa, s)["accepted"]]
    rejected = [s for s in candidates if not simulate_dfa(dfa, s)["accepted"]]

    # Three test strings: at least one accepted and one rejected when possible.
    test_strings = []
    if accepted:
        test_strings.append(generator.choice(accepted[:20]))
    if rejected:
        test_strings.append(generator.choice(rejected[:20]))
    while len(test_strings) < 3:
        pool = [s for s in candidates[:30] if s not in test_strings]
        test_strings.append(generator.choice(pool))
    generator.shuffle(test_strings)

    questions = []
    for text in test_strings:
        run = simulate_dfa(dfa, text)
        questions.append({
            "type": "yes_no",
            "question": f"Is the string '{text}' accepted?",
            "answer": "yes" if run["accepted"] else "no",
            "explanation": f"Path: {' → '.join(run['path'])}. {run['reason']}",
        })

    accepts_empty = properties["accepts_empty_string"]
    questions.append({
        "type": "yes_no",
        "question": "Is the empty string ε accepted?",
        "answer": "yes" if accepts_empty else "no",
        "explanation": (f"The start state {dfa.start} is "
                        f"{'accepting' if accepts_empty else 'not accepting'}."),
    })

    questions.append({
        "type": "number",
        "question": "How many states does the minimized DFA have (count the dead state if there is one)?",
        "answer": str(len(dfa.states)),
        "explanation": f"The minimized DFA has the states {', '.join(dfa.states)}.",
    })

    questions.append({
        "type": "choice",
        "options": ["finite", "infinite"],
        "question": "Is the language finite or infinite?",
        "answer": "infinite" if properties["infinite"] else "finite",
        "explanation": properties["summary"],
    })

    questions.append({
        "type": "number",
        "question": "What is the length of the SHORTEST accepted string? (ε has length 0)",
        "answer": str(properties["shortest_length"]),
        "explanation": f"The shortest accepted strings are: {', '.join(properties['shortest_strings'][:3])}.",
    })

    trace_text = generator.choice([s for s in candidates if 2 <= len(s) <= 4])
    run = simulate_dfa(dfa, trace_text)
    questions.append({
        "type": "text",
        "question": f"In the minimized DFA, which state do you end in after reading '{trace_text}'? "
                    "(Click 'Show automata' to see the state names.)",
        "answer": run["path"][-1],
        "explanation": f"Path: {' → '.join(run['path'])}.",
    })

    return {"regex": regex, "level": level, "questions": questions}
