"""
simulate.py - run an input string on a DFA (and on an ε-NFA, see simulate_nfa).

A DFA is simple to run: start in the start state, and for each input symbol
follow the ONE edge labelled with that symbol. After the last symbol, the
string is accepted if and only if we stopped in an accepting state.
Running time is O(length of the string) - one step per symbol.
"""

from __future__ import annotations

from automata.subset import DFA, epsilon_closure, move
from automata.thompson import NFA


def simulate_dfa(dfa: DFA, input_string: str) -> dict:
    """
    Run `input_string` on `dfa`.

    Returns a dictionary:
        accepted : True / False
        path     : list of states visited, starting with the start state
        steps    : one entry per symbol read: {index, from, symbol, to}
        reason   : a sentence explaining the result
    """
    current = dfa.start
    path = [current]
    steps = []

    for index, symbol in enumerate(input_string):
        # A symbol outside the alphabet has no edge at all, so the string
        # cannot be in the language. (Equivalent to going to a dead state.)
        if symbol not in dfa.alphabet:
            alphabet_text = ", ".join(dfa.alphabet) if dfa.alphabet else "(empty)"
            return {
                "accepted": False,
                "path": path,
                "steps": steps,
                "reason": (
                    f"Rejected: symbol '{symbol}' at position {index + 1} is not in the "
                    f"alphabet {{{alphabet_text}}}, so there is no transition for it."
                ),
            }

        next_state = dfa.next_state(current, symbol)
        steps.append({"index": index, "from": current, "symbol": symbol, "to": next_state})
        current = next_state
        path.append(current)

    accepted = dfa.is_accepting(current)
    shown_string = input_string if input_string else "ε"
    if accepted:
        reason = f"Accepted: after reading '{shown_string}' the DFA stops in {current}, which is an accepting state."
    elif current == dfa.dead_state:
        reason = (f"Rejected: the DFA fell into the dead state {current}; "
                  "no continuation can ever be accepted.")
    else:
        reason = f"Rejected: after reading '{shown_string}' the DFA stops in {current}, which is not accepting."

    return {"accepted": accepted, "path": path, "steps": steps, "reason": reason}


def accepts(dfa: DFA, input_string: str) -> bool:
    """Shortcut: True if the DFA accepts the string."""
    return simulate_dfa(dfa, input_string)["accepted"]


def _format_set(states: list[int]) -> str:
    if not states:
        return "∅"
    return "{" + ", ".join(f"q{s}" for s in states) + "}"


def simulate_nfa(nfa: NFA, input_string: str) -> dict:
    """
    Run `input_string` on the ε-NFA directly.

    An NFA can be in MANY states at once, so we keep the SET of current states:
        current = ε-closure({start})
        for each symbol a:  current = ε-closure(move(current, a))
    The string is accepted if the final set contains the accept state.
    (This is exactly what the subset construction does ahead of time - which
    is why the DFA and the NFA always give the same answer.)

    Returns:
        accepted : True / False
        sets     : the set of active states before and after each symbol
        path     : the same sets as readable text, e.g. "{q0, q1}"
        steps    : {index, symbol, move, closure} for each symbol
        reason   : a sentence explaining the result
    """
    current = sorted(epsilon_closure(nfa, [nfa.start]))
    sets = [current]
    steps = []

    for index, symbol in enumerate(input_string):
        moved = sorted(move(nfa, current, symbol))
        current = sorted(epsilon_closure(nfa, moved))
        steps.append({"index": index, "symbol": symbol, "move": moved, "closure": current})
        sets.append(current)
        if not current:
            break  # no active states left: nothing can ever be accepted

    accepted = len(sets) == len(input_string) + 1 and nfa.accept in current
    shown_string = input_string if input_string else "ε"
    if accepted:
        reason = (f"Accepted: after reading '{shown_string}' the active set {_format_set(current)} "
                  f"contains the accept state q{nfa.accept}.")
    elif not current:
        reason = "Rejected: the set of active states became empty (no transition for that symbol)."
    else:
        reason = (f"Rejected: after reading '{shown_string}' the active set {_format_set(current)} "
                  f"does not contain the accept state q{nfa.accept}.")

    return {
        "accepted": accepted,
        "sets": sets,
        "path": [_format_set(s) for s in sets],
        "steps": steps,
        "reason": reason,
    }
