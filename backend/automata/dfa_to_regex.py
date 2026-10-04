"""
dfa_to_regex.py - DFA -> regular expression (STATE ELIMINATION).

This closes the circle: regex -> ε-NFA -> DFA -> minimized DFA -> regex.
Together with Thompson's construction it proves Kleene's theorem: regular
expressions and finite automata describe exactly the same languages.

IDEA: a GENERALIZED NFA (GNFA) has REGULAR EXPRESSIONS on its edges instead
of single symbols. We remove states one by one; each time, we "repair" the
paths that went through the removed state by writing them as regexes.

ALGORITHM
    1. Drop useless states (unreachable, or unable to reach acceptance, such
       as the dead state): they add nothing to the language.
    2. Add a new state "start" with an ε-edge to the old start, and a new "final"
       with ε-edges from every old accepting state.
    3. Parallel edges p --a--> q and p --b--> q become one edge  p --a|b--> q.
    4. Eliminate the old states one at a time. Removing state k: for every
       pair p --R1--> k --R3--> q, with a self-loop R2 on k, add
            p --R1 (R2)* R3--> q         (union with the existing p->q edge)
    5. In the end only start --R--> final is left. R is the answer.

We choose to eliminate the state with the fewest in-edges × out-edges first:
it creates the fewest new edges, which keeps the regex shorter. (Any order
gives a correct, equivalent regex - only its length changes.)

The helpers union/concat/star build the regex STRINGS and apply simple
simplifications (ε·r = r, r|r = r, (r*)* = r*, ε|r = r?) so the answer
stays readable and is valid input for our own parser.
"""

from __future__ import annotations

from collections import deque

from automata.parser import EPSILON, is_symbol
from automata.subset import DFA

START = "start"   # lowercase: can never clash with DFA state names (A, B, ...)
FINAL = "final"


# ---------------------------------------------------------------------------
# Building regex strings safely
# ---------------------------------------------------------------------------

def _has_top_level_union(regex: str) -> bool:
    """True if `regex` has a '|' that is not inside parentheses, e.g. a|bc."""
    depth = 0
    for char in regex:
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        elif char == "|" and depth == 0:
            return True
    return False


def _is_atomic(regex: str) -> bool:
    """
    True if `regex` is ONE unit that * can be applied to directly:
    a single symbol / ε, or something fully wrapped in one pair of parentheses.
    """
    if len(regex) == 1:
        return True
    if not (regex.startswith("(") and regex.endswith(")")):
        return False
    # Check that the '(' at index 0 closes at the very end (not "(a)(b)").
    depth = 0
    for index, char in enumerate(regex):
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0 and index != len(regex) - 1:
                return False
    return True


def _wrap(regex: str) -> str:
    """Put parentheses around `regex` unless it is already one unit."""
    return regex if _is_atomic(regex) else "(" + regex + ")"


def regex_union(first: str | None, second: str | None) -> str | None:
    """first | second.  None means 'no edge' (the empty language ∅)."""
    if first is None:
        return second
    if second is None or first == second:
        return first
    # ε | r  =  r?   (optional)
    if first == EPSILON:
        return regex_optional(second)
    if second == EPSILON:
        return regex_optional(first)
    return first + "|" + second


def regex_optional(regex: str) -> str:
    """r? - but if r can already be empty (r* or r?), r is enough."""
    if regex == EPSILON:
        return EPSILON
    if regex[-1] in "*?" and _is_atomic(regex[:-1]):
        return regex
    return _wrap(regex) + "?"


def regex_concat(first: str | None, second: str | None) -> str | None:
    """first followed by second.  Anything followed by ∅ is ∅; ε is the identity."""
    if first is None or second is None:
        return None
    if first == EPSILON:
        return second
    if second == EPSILON:
        return first
    # A top-level union must be grouped first: (a|b)c, not a|bc.
    left = "(" + first + ")" if _has_top_level_union(first) else first
    right = "(" + second + ")" if _has_top_level_union(second) else second
    return left + right


def regex_star(regex: str | None) -> str:
    """(regex)*.  ∅* = ε* = ε, and (r*)* = (r+)* = (r?)* = r*."""
    if regex is None or regex == EPSILON:
        return EPSILON
    if regex[-1] in "*+?" and _is_atomic(regex[:-1]):
        return regex[:-1] + "*"
    return _wrap(regex) + "*"


# ---------------------------------------------------------------------------
# State elimination
# ---------------------------------------------------------------------------

def useful_states(dfa: DFA) -> set[str]:
    """States that are reachable from the start AND can reach an accepting state."""
    reachable = {dfa.start}
    queue = deque([dfa.start])
    while queue:
        state = queue.popleft()
        for symbol in dfa.alphabet:
            target = dfa.transitions[state].get(symbol)
            if target is not None and target not in reachable:
                reachable.add(target)
                queue.append(target)

    # Walk the edges BACKWARDS from the accepting states.
    can_accept = set(dfa.accepts)
    changed = True
    while changed:
        changed = False
        for state in dfa.states:
            if state in can_accept:
                continue
            for symbol in dfa.alphabet:
                if dfa.transitions[state].get(symbol) in can_accept:
                    can_accept.add(state)
                    changed = True
                    break

    return reachable & can_accept


def _edges_text(edges: dict[tuple[str, str], str]) -> list[dict]:
    return [{"from": p, "to": q, "regex": r} for (p, q), r in edges.items()]


def dfa_to_regex(dfa: DFA) -> tuple[str | None, list[dict], list[dict]]:
    """
    Convert a DFA into an equivalent regex with state elimination.

    Returns (regex, initial_edges, steps):
        regex          : the result, or None if the language is empty
        initial_edges  : the GNFA edges before anything is eliminated
        steps          : for each eliminated state, its self-loop and the new
                         edges it created
    """
    keep = useful_states(dfa)
    if dfa.start not in keep:
        return None, [], []          # no accepting state is reachable: L = ∅

    # Steps 2 + 3: build the GNFA. Edge (p, q) -> regex.
    edges: dict[tuple[str, str], str] = {}

    def add_edge(source: str, target: str, regex: str) -> None:
        edges[(source, target)] = regex_union(edges.get((source, target)), regex)

    add_edge(START, dfa.start, EPSILON)
    for state in dfa.states:
        if state not in keep:
            continue
        if state in dfa.accepts:
            add_edge(state, FINAL, EPSILON)
        for symbol in dfa.alphabet:
            target = dfa.transitions[state].get(symbol)
            if target in keep:
                add_edge(state, target, symbol)

    initial_edges = _edges_text(edges)
    remaining = [state for state in dfa.states if state in keep]
    steps = []

    # Step 4: eliminate the old states one at a time.
    while remaining:
        def cost(state: str) -> int:
            incoming = [p for (p, q) in edges if q == state and p != state]
            outgoing = [q for (p, q) in edges if p == state and q != state]
            return len(incoming) * len(outgoing)

        state = min(remaining, key=cost)    # first state with the lowest cost
        remaining.remove(state)

        loop = edges.get((state, state))
        incoming = [(p, r) for (p, q), r in edges.items() if q == state and p != state]
        outgoing = [(q, r) for (p, q), r in edges.items() if p == state and q != state]

        new_edges = []
        for source, regex_in in incoming:
            for target, regex_out in outgoing:
                # path  source -> state (loop)* -> target
                bypass = regex_concat(regex_concat(regex_in, regex_star(loop)), regex_out)
                old = edges.get((source, target))
                edges[(source, target)] = regex_union(old, bypass)
                new_edges.append({
                    "from": source,
                    "to": target,
                    "via": bypass,
                    "old": old,
                    "regex": edges[(source, target)],
                })

        # Remove every edge that touches the eliminated state.
        for key in list(edges):
            if state in key:
                del edges[key]

        steps.append({
            "eliminated": state,
            "loop": loop,
            "new_edges": new_edges,
            "edges_left": _edges_text(edges),
        })

    return edges.get((START, FINAL)), initial_edges, steps


def uses_only_supported_symbols(regex: str) -> bool:
    """Sanity helper for tests: the output only uses our regex syntax."""
    for char in regex:
        if not (is_symbol(char) or char in "|*+?()" or char == EPSILON):
            return False
    return True
