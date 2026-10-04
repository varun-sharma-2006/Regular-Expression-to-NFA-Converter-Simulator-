"""
verifier.py - check whether a (possibly AI-generated) regex is correct.

This file uses NO AI at all: it is pure automata theory, so it works even
without an API key. Two independent checks:

    1. Examples test: run each positive example (should be accepted) and each
       negative example (should be rejected) on the regex's minimized DFA.
       This can find mistakes but can never PROVE correctness.

    2. Equivalence test (optional): if the user gives an "expected" regex,
       compare the two languages exactly with the product automaton
       (equivalence.py). This is a real proof, and if they differ we get a
       shortest counterexample string.
"""

from __future__ import annotations

from automata.equivalence import check_equivalence
from automata.parser import EPSILON, RegexSyntaxError
from automata.pipeline import regex_to_min_dfa
from automata.simulate import simulate_dfa


def normalize_example(example: str) -> str:
    """Users type ε to mean the empty string; spaces are ignored."""
    text = example.strip()
    if text == EPSILON:
        return ""
    return text


def verify_regex(
    regex: str,
    positive_examples: list[str],
    negative_examples: list[str],
    expected_regex: str | None = None,
) -> dict:
    """
    Run all checks and return a report with a final verdict.

    Raises RegexSyntaxError if `regex` itself is invalid.
    An invalid `expected_regex` is reported inside the result instead.
    """
    dfa = regex_to_min_dfa(regex)

    # ---- Check 1: examples ----
    example_results = []
    for kind, examples, should_accept in (
        ("positive", positive_examples, True),
        ("negative", negative_examples, False),
    ):
        for example in examples:
            text = normalize_example(example)
            run = simulate_dfa(dfa, text)
            example_results.append({
                "string": text if text else EPSILON,
                "kind": kind,
                "expected": "accept" if should_accept else "reject",
                "actual": "accept" if run["accepted"] else "reject",
                "passed": run["accepted"] == should_accept,
                "path": run["path"],
            })
    failed = [r for r in example_results if not r["passed"]]

    # ---- Check 2: equivalence with the expected regex ----
    equivalence = None
    expected_error = None
    if expected_regex and expected_regex.strip():
        try:
            equivalence = check_equivalence(regex, expected_regex)
        except RegexSyntaxError as error:
            expected_error = f"The expected regex is invalid: {error.message}"

    # ---- Final verdict ----
    reasons = []
    if failed:
        listed = ", ".join(f"'{r['string']}' ({r['kind']})" for r in failed)
        reasons.append(f"{len(failed)} example(s) failed: {listed}.")
    if equivalence and not equivalence["equivalent"]:
        reasons.append(equivalence["explanation"])

    if expected_error:
        verdict = "error"
        message = expected_error
    elif reasons:
        verdict = "wrong"
        message = "AI regex is wrong. " + " ".join(reasons)
    elif equivalence and equivalence["equivalent"]:
        verdict = "correct"
        message = ("AI regex verified correct: it defines exactly the same language as the "
                   "expected regex (proved with the product automaton)")
        if example_results:
            message += f", and all {len(example_results)} examples pass."
        else:
            message += "."
    elif example_results:
        verdict = "correct"
        message = (f"AI regex verified correct on all {len(example_results)} examples. "
                   "(Examples can only show mistakes, not prove correctness. "
                   "Add an expected regex for a full proof.)")
    else:
        verdict = "nothing"
        message = "Nothing to verify: add examples and/or an expected regex."

    return {
        "regex": regex,
        "examples": example_results,
        "equivalence": equivalence,
        "verdict": verdict,
        "message": message,
    }
