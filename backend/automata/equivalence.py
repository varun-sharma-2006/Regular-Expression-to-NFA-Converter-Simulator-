"""
equivalence.py - do two regular expressions describe the SAME language?

METHOD: product automaton + breadth-first search (see product.py)
    Run both DFAs "side by side". A state of the product automaton is a PAIR
    (p, q): DFA1 is in p and DFA2 is in q after reading the same input.
    Starting from (start1, start2) we explore every reachable pair with BFS.

    If we reach a pair where ONE DFA accepts and the OTHER rejects, the string
    that led us there is a COUNTEREXAMPLE: it is in one language but not the
    other, so the regexes are NOT equivalent.

    If no such pair is reachable, the languages are equal.

    Because BFS explores shorter strings first, the counterexample we return
    is a SHORTEST one, which is the easiest to understand.

WHY THIS TERMINATES: there are at most |Q1| × |Q2| pairs, and each is visited
once. So the check is exact (a proof), not just testing a few strings.

DIFFERENT ALPHABETS: if regex1 uses {a, b} and regex2 uses {a, c}, we use the
union {a, b, c}. A DFA that has no edge for a symbol goes to an imaginary dead
state (it never accepts again).
"""

from __future__ import annotations

from automata.pipeline import regex_to_min_dfa
from automata.product import are_equivalent, find_counterexample, run_dfa

# Re-exported so other files can keep importing them from here.
__all__ = ["are_equivalent", "find_counterexample", "check_equivalence"]


def check_equivalence(regex1: str, regex2: str) -> dict:
    """
    Compare two regexes. Raises RegexSyntaxError if either is invalid.

    Returns:
        equivalent      : True / False
        counterexample  : a shortest distinguishing string ("" means ε), or None
        accepted_by     : "regex1" or "regex2" (which one accepts the counterexample)
        explanation     : a sentence for the user
    """
    dfa1 = regex_to_min_dfa(regex1)
    dfa2 = regex_to_min_dfa(regex2)
    counterexample = find_counterexample(dfa1, dfa2)

    if counterexample is None:
        return {
            "equivalent": True,
            "counterexample": None,
            "accepted_by": None,
            "explanation": f"'{regex1}' and '{regex2}' define exactly the same language.",
        }

    shown = counterexample if counterexample else "ε"
    if run_dfa(dfa1, counterexample):
        accepted_by, accepter, rejecter = "regex1", regex1, regex2
    else:
        accepted_by, accepter, rejecter = "regex2", regex2, regex1

    return {
        "equivalent": False,
        "counterexample": counterexample,
        "accepted_by": accepted_by,
        "explanation": (
            f"Not equivalent: the string '{shown}' is accepted by '{accepter}' "
            f"but rejected by '{rejecter}'."
        ),
    }
