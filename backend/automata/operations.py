"""
operations.py - operations ON languages, and questions ABOUT a language.

CLOSURE PROPERTIES (regular languages are closed under all of these):
    complement      Σ* − L      swap accepting and non-accepting states
                                (the DFA must be COMPLETE over Σ first!)
    union           L1 ∪ L2     product automaton, accept if one accepts
    intersection    L1 ∩ L2     product automaton, accept if both accept
    difference      L1 − L2     product automaton, accept if 1 accepts and 2 rejects
    symmetric diff  L1 ⊕ L2     product automaton, accept if exactly one accepts

DECISION PROBLEMS (answered exactly, using the DFA):
    empty?     no accepting state is reachable from the start
    infinite?  some cycle lies on a path from the start to an accepting state
               (then we can pump around the cycle forever)
    finite?    not infinite; then we can even count the strings
    shortest strings: breadth-first search, shortest strings first
"""

from __future__ import annotations

from collections import deque

from automata.dfa_to_regex import useful_states
from automata.parser import EPSILON
from automata.product import build_product, complete_dfa
from automata.subset import DFA

# Which product pairs accept, for each binary operation.
OPERATIONS = {
    "union": ("L1 ∪ L2", lambda accept1, accept2: accept1 or accept2),
    "intersection": ("L1 ∩ L2", lambda accept1, accept2: accept1 and accept2),
    "difference": ("L1 − L2", lambda accept1, accept2: accept1 and not accept2),
    "symmetric_difference": ("L1 ⊕ L2", lambda accept1, accept2: accept1 != accept2),
}


# ---------------------------------------------------------------------------
# Operations that build new automata
# ---------------------------------------------------------------------------

def complement_dfa(dfa: DFA, alphabet: list[str] | None = None) -> DFA:
    """
    Complement with respect to Σ = dfa.alphabet ∪ alphabet.

    The DFA is first made COMPLETE (every missing move goes to a dead state).
    This matters: a string that "falls off" an incomplete DFA is rejected, and
    after complementing it must be ACCEPTED - which only works if there is a
    real (dead) state to be in, which then becomes accepting.
    """
    complete = complete_dfa(dfa, alphabet or [])
    new_accepts = {state for state in complete.states if state not in complete.accepts}
    # After swapping, the old dead state accepts everything, so it is not dead anymore.
    return DFA(complete.states, complete.alphabet, complete.start, new_accepts,
               complete.transitions, dead_state=None)


def combine_dfas(dfa1: DFA, dfa2: DFA, operation: str) -> tuple[DFA, list[dict]]:
    """Apply a binary operation with the product automaton. Returns (dfa, product_table)."""
    _symbol, accept_rule = OPERATIONS[operation]
    return build_product(dfa1, dfa2, accept_rule)


# ---------------------------------------------------------------------------
# Questions about a language
# ---------------------------------------------------------------------------

def is_empty(dfa: DFA) -> bool:
    """L = ∅ exactly when the start state cannot reach any accepting state."""
    return dfa.start not in useful_states(dfa)


def is_infinite(dfa: DFA) -> bool:
    """
    L is infinite exactly when the 'useful' part of the DFA (states on some
    path from start to acceptance) contains a cycle. We look for a cycle with
    depth-first search, colouring states: 0 = new, 1 = on the current path,
    2 = finished. Meeting a state that is still on the path means a cycle.
    """
    useful = useful_states(dfa)
    colour = {state: 0 for state in useful}

    def has_cycle_from(state: str) -> bool:
        colour[state] = 1
        for symbol in dfa.alphabet:
            target = dfa.transitions[state].get(symbol)
            if target not in useful:
                continue
            if colour[target] == 1:
                return True
            if colour[target] == 0 and has_cycle_from(target):
                return True
        colour[state] = 2
        return False

    for state in useful:
        if colour[state] == 0 and has_cycle_from(state):
            return True
    return False


def count_strings(dfa: DFA) -> int:
    """
    Number of strings in a FINITE language. The useful part has no cycles,
    so count[state] = (1 if accepting) + sum of count[target] over its moves.
    """
    useful = useful_states(dfa)
    memory: dict[str, int] = {}

    def count_from(state: str) -> int:
        if state in memory:
            return memory[state]
        total = 1 if dfa.is_accepting(state) else 0
        for symbol in dfa.alphabet:
            target = dfa.transitions[state].get(symbol)
            if target in useful:
                total += count_from(target)
        memory[state] = total
        return total

    if dfa.start not in useful:
        return 0
    return count_from(dfa.start)


def shortest_strings(dfa: DFA, limit: int = 10, max_length: int = 25) -> list[str]:
    """
    The first `limit` accepted strings, shortest first (then alphabetical).

    Breadth-first search over strings. We only extend a string if its state
    can still reach an accepting state ('useful'), so we never waste time on
    strings that are already dead.
    """
    useful = useful_states(dfa)
    if dfa.start not in useful:
        return []

    results = []
    queue = deque([("", dfa.start)])
    work_done = 0
    while queue and len(results) < limit and work_done < 50000:
        text, state = queue.popleft()
        work_done += 1
        if dfa.is_accepting(state):
            results.append(text)
        if len(text) >= max_length:
            continue
        for symbol in dfa.alphabet:
            target = dfa.transitions[state].get(symbol)
            if target in useful:
                queue.append((text + symbol, target))
    return results


def describe_language(dfa: DFA, sample_size: int = 10) -> dict:
    """Answer the standard questions about L(dfa) in one dictionary."""
    empty = is_empty(dfa)
    infinite = False if empty else is_infinite(dfa)
    samples = shortest_strings(dfa, sample_size)
    shown_samples = [s if s else EPSILON for s in samples]
    result = {
        "empty": empty,
        "infinite": infinite,
        "finite": not infinite,
        "count": None if infinite else count_strings(dfa),
        "accepts_empty_string": dfa.is_accepting(dfa.start),
        "shortest_strings": shown_samples,
        "shortest_length": len(samples[0]) if samples else None,
        "alphabet": list(dfa.alphabet),
    }
    if empty:
        result["summary"] = "The language is EMPTY: no string is accepted."
    elif infinite:
        result["summary"] = ("The language is INFINITE: a cycle lies on a path to an accepting "
                             "state, so it can be pumped forever.")
    else:
        result["summary"] = f"The language is FINITE: it contains exactly {result['count']} string(s)."
    return result

