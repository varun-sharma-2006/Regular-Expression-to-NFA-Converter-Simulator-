"""
product.py - the PRODUCT AUTOMATON: running two DFAs side by side.

A state of the product automaton is a PAIR (p, q): "DFA1 is in p and DFA2 is
in q after reading the same input". From (p, q) on symbol a we go to
(δ1(p, a), δ2(q, a)). So one product run = two DFA runs at the same time.

The product is used for two things in this project:
    1. Equivalence (equivalence.py): search for a pair where exactly ONE DFA
       accepts. The string leading there is a counterexample.
    2. Language operations (operations.py): choose which pairs accept:
           intersection  L1 ∩ L2 : both accept
           union         L1 ∪ L2 : at least one accepts
           difference    L1 − L2 : DFA1 accepts and DFA2 rejects
           symmetric diff L1 ⊕ L2: exactly one accepts
       This is the standard proof that regular languages are CLOSED under
       these operations.

DIFFERENT ALPHABETS: both DFAs are first made complete over the union of
their alphabets; a symbol a DFA has never seen leads to its dead state.
"""

from __future__ import annotations

from collections import deque
from typing import Callable

from automata.subset import DEAD_STATE_NAME, DFA, make_state_name


# ---------------------------------------------------------------------------
# Completing a DFA over a bigger alphabet
# ---------------------------------------------------------------------------

def complete_dfa(dfa: DFA, alphabet: list[str]) -> DFA:
    """
    Return a copy of `dfa` that has a transition for every symbol in `alphabet`.
    Missing transitions go to a dead state (created if the DFA has none).
    """
    alphabet = sorted(set(alphabet) | set(dfa.alphabet))
    states = list(dfa.states)
    transitions = {state: dict(dfa.transitions[state]) for state in states}
    dead_state = dfa.dead_state

    needs_dead_state = any(
        symbol not in transitions[state] for state in states for symbol in alphabet
    )
    if needs_dead_state and dead_state is None:
        dead_state = DEAD_STATE_NAME
        states.append(dead_state)
        transitions[dead_state] = {}

    for state in states:
        for symbol in alphabet:
            if symbol not in transitions[state]:
                transitions[state][symbol] = dead_state

    return DFA(states, alphabet, dfa.start, set(dfa.accepts), transitions, dead_state)


# ---------------------------------------------------------------------------
# Building the product automaton
# ---------------------------------------------------------------------------

def build_product(
    dfa1: DFA,
    dfa2: DFA,
    accept_rule: Callable[[bool, bool], bool],
) -> tuple[DFA, list[dict]]:
    """
    Build the reachable part of the product automaton.

    `accept_rule(accept1, accept2)` decides if a pair is accepting, e.g.
    `lambda a, b: a and b` for intersection.

    Returns (product_dfa, table). Product states are renamed A, B, C, ...
    and `table` says which pair each name stands for.
    """
    alphabet = sorted(set(dfa1.alphabet) | set(dfa2.alphabet))
    dfa1 = complete_dfa(dfa1, alphabet)
    dfa2 = complete_dfa(dfa2, alphabet)

    start_pair = (dfa1.start, dfa2.start)
    names = {start_pair: make_state_name(0)}
    order = [start_pair]
    queue = deque([start_pair])
    transitions: dict[str, dict[str, str]] = {}

    # Breadth-first search over pairs: only reachable pairs are created.
    while queue:
        pair = queue.popleft()
        state1, state2 = pair
        transitions[names[pair]] = {}
        for symbol in alphabet:
            next_pair = (dfa1.next_state(state1, symbol), dfa2.next_state(state2, symbol))
            if next_pair not in names:
                names[next_pair] = make_state_name(len(order))
                order.append(next_pair)
                queue.append(next_pair)
            transitions[names[pair]][symbol] = names[next_pair]

    accepts = set()
    table = []
    for pair in order:
        state1, state2 = pair
        accept1 = dfa1.is_accepting(state1)
        accept2 = dfa2.is_accepting(state2)
        is_accept = accept_rule(accept1, accept2)
        if is_accept:
            accepts.add(names[pair])
        table.append({
            "state": names[pair],
            "pair": [state1, state2],
            "accept1": accept1,
            "accept2": accept2,
            "is_accept": is_accept,
            "transitions": dict(transitions[names[pair]]),
        })

    states = [names[pair] for pair in order]
    product = DFA(states, alphabet, names[start_pair], accepts, transitions)
    return product, table


# ---------------------------------------------------------------------------
# Equivalence: search the product for a pair where exactly one DFA accepts
# ---------------------------------------------------------------------------

def _step(dfa: DFA, state: str | None, symbol: str) -> str | None:
    """Move one step; None means 'in the imaginary dead state'."""
    if state is None or symbol not in dfa.alphabet:
        return None
    return dfa.next_state(state, symbol)


def _accepts(dfa: DFA, state: str | None) -> bool:
    return state is not None and dfa.is_accepting(state)


def find_counterexample(dfa1: DFA, dfa2: DFA) -> str | None:
    """
    Return a shortest string accepted by exactly one of the two DFAs,
    or None if the DFAs accept the same language.

    Breadth-first search over pairs explores shorter strings first, so the
    first difference we find is a SHORTEST counterexample.
    """
    alphabet = sorted(set(dfa1.alphabet) | set(dfa2.alphabet))

    start_pair = (dfa1.start, dfa2.start)
    # For each visited pair we remember the string that first reached it.
    reached_by: dict[tuple, str] = {start_pair: ""}
    queue = deque([start_pair])

    while queue:
        pair = queue.popleft()
        state1, state2 = pair
        if _accepts(dfa1, state1) != _accepts(dfa2, state2):
            return reached_by[pair]
        for symbol in alphabet:
            next_pair = (_step(dfa1, state1, symbol), _step(dfa2, state2, symbol))
            if next_pair not in reached_by:
                reached_by[next_pair] = reached_by[pair] + symbol
                queue.append(next_pair)

    return None


def are_equivalent(dfa1: DFA, dfa2: DFA) -> bool:
    """True if the two DFAs accept exactly the same language."""
    return find_counterexample(dfa1, dfa2) is None


def run_dfa(dfa: DFA, text: str) -> bool:
    """Small helper: does `dfa` accept `text`? (unknown symbols -> reject)"""
    state: str | None = dfa.start
    for symbol in text:
        state = _step(dfa, state, symbol)
    return _accepts(dfa, state)
