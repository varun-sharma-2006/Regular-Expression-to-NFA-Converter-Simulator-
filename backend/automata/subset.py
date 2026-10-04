"""
subset.py - Stage 3 of the pipeline: ε-NFA -> DFA (subset construction).

IDEA
    An NFA can be in MANY states at once. A DFA can only be in ONE.
    So each DFA state stands for a SET of NFA states: "all the NFA states the
    NFA could be in right now". That is why it is called *subset* construction.

TWO HELPER OPERATIONS
    ε-closure(S)  = all NFA states reachable from the states in S using only
                    ε-moves (including the states of S themselves).
    move(S, a)    = all NFA states reachable from S by ONE edge labelled a.

ALGORITHM
    1. DFA start state = ε-closure({NFA start}).
    2. For each unprocessed DFA state S and each symbol a:
           T = ε-closure(move(S, a))
       If T is new, give it a name and add it to the work list.
       Add the DFA edge S --a--> T.
    3. A DFA state is accepting if its set contains the NFA accept state.
    4. If some T is the empty set, it becomes the DEAD state (∅): once there,
       every symbol keeps you there and you can never accept. Including it
       makes the DFA *complete* (every state has an edge for every symbol).
"""

from __future__ import annotations

from collections import deque
from typing import Iterable

from automata.parser import EPSILON
from automata.thompson import NFA

DEAD_STATE_NAME = "∅"


class DFA:
    """
    A complete deterministic finite automaton.

        states       list of state names, e.g. ["A", "B", "C"]
        alphabet     list of input symbols, e.g. ["a", "b"]
        start        name of the start state
        accepts      set of accepting state names
        transitions  dict: state -> {symbol -> next state}  (exactly one!)
        dead_state   name of the dead (trap) state, or None if there is none
    """

    def __init__(
        self,
        states: list[str],
        alphabet: list[str],
        start: str,
        accepts: set[str],
        transitions: dict[str, dict[str, str]],
        dead_state: str | None = None,
    ) -> None:
        self.states = states
        self.alphabet = alphabet
        self.start = start
        self.accepts = accepts
        self.transitions = transitions
        self.dead_state = dead_state

    def next_state(self, state: str, symbol: str) -> str:
        """δ(state, symbol): the one state we move to."""
        return self.transitions[state][symbol]

    def is_accepting(self, state: str) -> bool:
        return state in self.accepts

    def transition_table(self) -> list[dict]:
        """One row per state with the target for each symbol."""
        rows = []
        for state in self.states:
            rows.append({
                "state": state,
                "is_start": state == self.start,
                "is_accept": state in self.accepts,
                "is_dead": state == self.dead_state,
                "transitions": dict(self.transitions[state]),
            })
        return rows

    def to_dict(self) -> dict:
        """Convert to plain JSON-friendly data for the frontend."""
        edges = []
        for state in self.states:
            for symbol in self.alphabet:
                edges.append({"from": state, "symbol": symbol, "to": self.transitions[state][symbol]})
        return {
            "states": self.states,
            "start": self.start,
            "accepts": [s for s in self.states if s in self.accepts],
            "alphabet": self.alphabet,
            "dead_state": self.dead_state,
            "edges": edges,
            "table": self.transition_table(),
        }


def epsilon_closure(nfa: NFA, states: Iterable[int]) -> frozenset[int]:
    """
    Return every NFA state reachable from `states` using only ε-moves.

    This is a graph search (depth-first, using a stack): start with the given
    states, and keep following ε-edges until no new state is found.
    Each state is always in its own closure (zero ε-moves).
    We return a frozenset so it can be used as a dictionary key.
    """
    closure = set(states)
    to_visit = list(states)
    while to_visit:
        state = to_visit.pop()
        for next_state in nfa.get_targets(state, EPSILON):
            if next_state not in closure:
                closure.add(next_state)
                to_visit.append(next_state)
    return frozenset(closure)


def move(nfa: NFA, states: Iterable[int], symbol: str) -> frozenset[int]:
    """Return all NFA states reachable from `states` by exactly one `symbol` edge."""
    result = set()
    for state in states:
        result.update(nfa.get_targets(state, symbol))
    return frozenset(result)


def make_state_name(index: int) -> str:
    """0 -> A, 1 -> B, ..., 25 -> Z, 26 -> AA, 27 -> AB, ... (like spreadsheet columns)."""
    name = ""
    index += 1
    while index > 0:
        index, remainder = divmod(index - 1, 26)
        name = chr(ord("A") + remainder) + name
    return name


def format_set(states: Iterable[int]) -> str:
    """Show a set of NFA states nicely, e.g. {0, 1, 3}. Empty set is ∅."""
    ordered = sorted(states)
    if not ordered:
        return DEAD_STATE_NAME
    return "{" + ", ".join(str(s) for s in ordered) + "}"


def subset_construction(nfa: NFA) -> tuple[DFA, dict]:
    """
    Convert an ε-NFA into an equivalent complete DFA.

    Returns (dfa, details). `details` holds everything the page shows:
        closures : ε-closure of every single NFA state
        subset_table : the subset construction table, one row per DFA state, with
                   move() and ε-closure() for every symbol
        sets     : which NFA states each DFA state stands for
    """
    alphabet = nfa.sorted_alphabet()

    # ε-closure of each individual NFA state (shown on the page for learning).
    closures = []
    for state in nfa.states:
        closures.append({"state": state, "closure": sorted(epsilon_closure(nfa, [state]))})

    names: dict[frozenset[int], str] = {}     # NFA-state set -> DFA state name
    order: list[frozenset[int]] = []          # DFA states in discovery order
    letter_count = 0

    def get_name(state_set: frozenset[int]) -> str:
        """Give a DFA state set a name the first time we see it."""
        nonlocal letter_count
        if state_set not in names:
            if len(state_set) == 0:
                names[state_set] = DEAD_STATE_NAME
            else:
                names[state_set] = make_state_name(letter_count)
                letter_count += 1
            order.append(state_set)
            work_list.append(state_set)
        return names[state_set]

    work_list: deque[frozenset[int]] = deque()

    # Step 1: the start state is the ε-closure of the NFA start state.
    start_set = epsilon_closure(nfa, [nfa.start])
    start_name = get_name(start_set)

    transitions: dict[str, dict[str, str]] = {}
    table_rows: list[dict] = []

    # Step 2: process DFA states one by one (breadth-first order).
    while work_list:
        current_set = work_list.popleft()
        current_name = names[current_set]
        transitions[current_name] = {}
        row_cells = {}
        for symbol in alphabet:
            moved = move(nfa, current_set, symbol)
            target_set = epsilon_closure(nfa, moved)
            target_name = get_name(target_set)
            transitions[current_name][symbol] = target_name
            row_cells[symbol] = {
                "move": sorted(moved),
                "closure": sorted(target_set),
                "target": target_name,
            }
        table_rows.append({
            "state": current_name,
            "nfa_states": sorted(current_set),
            "is_start": current_set == start_set,
            "is_accept": nfa.accept in current_set,
            "is_dead": len(current_set) == 0,
            "transitions": row_cells,
        })

    # Step 3: accepting DFA states are those containing the NFA accept state.
    states = [names[s] for s in order]
    accepts = {names[s] for s in order if nfa.accept in s}
    dead_state = DEAD_STATE_NAME if frozenset() in names else None

    dfa = DFA(states, alphabet, start_name, accepts, transitions, dead_state)
    details = {
        "closures": closures,
        "subset_table": table_rows,
        "sets": {names[s]: sorted(s) for s in order},
    }
    return dfa, details
