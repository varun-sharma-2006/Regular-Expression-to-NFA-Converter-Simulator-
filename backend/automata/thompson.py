"""
thompson.py - Stage 2 of the pipeline: postfix expression -> ε-NFA.

THOMPSON'S CONSTRUCTION
    We build the NFA from small pieces called *fragments*. Every fragment has
    exactly ONE start state and ONE accept state. We read the postfix string
    left to right with a stack of fragments:

      operand (a, b, ε)  -> build a tiny 2-state fragment, push it
      unary op (* + ?)   -> pop 1 fragment, wrap it, push the result
      binary op (. |)    -> pop 2 fragments, join them, push the result

    At the end exactly one fragment is left on the stack: that is the NFA for
    the whole regex. Because every rule only ADDS new states and ε-edges and
    never changes old edges, each rule is easy to draw and to prove correct.

The NFA here is a simple class with:
    states       list of integers 0, 1, 2, ... (in creation order)
    start        the start state
    accept       the single accept state (Thompson NFAs have exactly one)
    alphabet     input symbols that appear in the regex (ε is NOT included)
    transitions  dict: state -> {symbol -> set of next states}
                 (symbol can be ε for epsilon-moves)
"""

from __future__ import annotations

from dataclasses import dataclass

from automata.parser import (
    CONCAT,
    EPSILON,
    OPTIONAL,
    PLUS,
    STAR,
    UNION,
    is_operand,
)


class NFA:
    """An ε-NFA with exactly one start state and one accept state."""

    def __init__(self) -> None:
        self.states: list[int] = []
        self.transitions: dict[int, dict[str, set[int]]] = {}
        self.alphabet: set[str] = set()
        self.start: int = -1
        self.accept: int = -1
        # Every edge in the order it was added. Used to show, for each
        # Thompson rule, exactly which edges that rule created.
        self.edge_log: list[tuple[int, str, int]] = []

    def new_state(self) -> int:
        """Create a new state, numbered in creation order (0, 1, 2, ...)."""
        state = len(self.states)
        self.states.append(state)
        self.transitions[state] = {}
        return state

    def add_transition(self, from_state: int, symbol: str, to_state: int) -> None:
        """Add the edge  from_state --symbol--> to_state."""
        if symbol not in self.transitions[from_state]:
            self.transitions[from_state][symbol] = set()
        self.transitions[from_state][symbol].add(to_state)
        self.edge_log.append((from_state, symbol, to_state))
        if symbol != EPSILON:
            self.alphabet.add(symbol)

    def get_targets(self, state: int, symbol: str) -> set[int]:
        """Return the set of states reachable from `state` on `symbol` (may be empty)."""
        return self.transitions[state].get(symbol, set())

    def sorted_alphabet(self) -> list[str]:
        return sorted(self.alphabet)

    def transition_table(self) -> list[dict]:
        """
        Build rows for the NFA transition table shown on the page:
        one row per state, one column per symbol plus a column for ε.
        """
        columns = self.sorted_alphabet() + [EPSILON]
        rows = []
        for state in self.states:
            cells = {}
            for symbol in columns:
                cells[symbol] = sorted(self.get_targets(state, symbol))
            rows.append({
                "state": state,
                "is_start": state == self.start,
                "is_accept": state == self.accept,
                "transitions": cells,
            })
        return rows

    def to_dict(self) -> dict:
        """Convert to plain JSON-friendly data for the frontend."""
        edges = []
        for from_state in self.states:
            for symbol, targets in sorted(self.transitions[from_state].items()):
                for to_state in sorted(targets):
                    edges.append({"from": from_state, "symbol": symbol, "to": to_state})
        return {
            "states": self.states,
            "start": self.start,
            "accepts": [self.accept],
            "alphabet": self.sorted_alphabet(),
            "edges": edges,
            "table": self.transition_table(),
        }


@dataclass
class Fragment:
    """A piece of NFA under construction: one entry state and one exit state."""
    start: int
    accept: int


def thompson_construction(postfix: str) -> tuple[NFA, list[dict]]:
    """
    Build an ε-NFA from a postfix regex using Thompson's construction.

    Returns (nfa, steps) where `steps` lists every rule that was applied,
    in order, so the web page can show how the NFA was built. Each step also
    lists the states and edges that rule created (for the build animation).
    """
    nfa = NFA()
    stack: list[Fragment] = []
    steps: list[dict] = []
    states_before = 0   # number of states before the current rule
    edges_before = 0    # number of edges before the current rule

    def record(token: str, rule: str, description: str, fragment: Fragment) -> None:
        new_edges = []
        for from_state, symbol, to_state in nfa.edge_log[edges_before:]:
            new_edges.append({"from": from_state, "symbol": symbol, "to": to_state})
        steps.append({
            "step": len(steps) + 1,
            "token": token,
            "rule": rule,
            "description": description,
            "start": fragment.start,
            "accept": fragment.accept,
            "new_states": nfa.states[states_before:],
            "new_edges": new_edges,
        })

    for token in postfix:
        states_before = len(nfa.states)
        edges_before = len(nfa.edge_log)

        if is_operand(token):
            # Rule for a symbol 'a' (or ε): two new states and one edge.
            #     start --a--> accept
            start = nfa.new_state()
            accept = nfa.new_state()
            nfa.add_transition(start, token, accept)
            fragment = Fragment(start, accept)
            if token == EPSILON:
                rule = "Epsilon"
                description = f"New states q{start}, q{accept} with an ε-move q{start} → q{accept}"
            else:
                rule = "Symbol"
                description = f"New states q{start}, q{accept} with edge q{start} --{token}--> q{accept}"
            record(token, rule, description, fragment)
            stack.append(fragment)

        elif token == CONCAT:
            # Rule for concatenation N1.N2: connect N1's accept to N2's start
            # with an ε-move. The result starts where N1 starts and accepts
            # where N2 accepts. (Order matters: N2 was pushed last.)
            second = stack.pop()
            first = stack.pop()
            nfa.add_transition(first.accept, EPSILON, second.start)
            fragment = Fragment(first.start, second.accept)
            record(token, "Concatenation",
                   f"ε-move from q{first.accept} (end of first part) to q{second.start} "
                   f"(start of second part)", fragment)
            stack.append(fragment)

        elif token == UNION:
            # Rule for union N1|N2: a new start state with ε-moves to BOTH
            # NFAs (the machine "guesses" which branch to follow), and ε-moves
            # from both accept states to a new common accept state.
            second = stack.pop()
            first = stack.pop()
            start = nfa.new_state()
            accept = nfa.new_state()
            nfa.add_transition(start, EPSILON, first.start)
            nfa.add_transition(start, EPSILON, second.start)
            nfa.add_transition(first.accept, EPSILON, accept)
            nfa.add_transition(second.accept, EPSILON, accept)
            fragment = Fragment(start, accept)
            record(token, "Union",
                   f"New start q{start} with ε-moves to q{first.start} and q{second.start}; "
                   f"ε-moves from q{first.accept} and q{second.accept} to new accept q{accept}",
                   fragment)
            stack.append(fragment)

        elif token == STAR:
            # Rule for Kleene star N*: new start and accept states.
            #   start  -ε-> N.start        (enter N)
            #   start  -ε-> accept         (skip N: zero repetitions)
            #   N.accept -ε-> N.start      (loop back: repeat N again)
            #   N.accept -ε-> accept       (finish)
            inner = stack.pop()
            start = nfa.new_state()
            accept = nfa.new_state()
            nfa.add_transition(start, EPSILON, inner.start)
            nfa.add_transition(start, EPSILON, accept)
            nfa.add_transition(inner.accept, EPSILON, inner.start)
            nfa.add_transition(inner.accept, EPSILON, accept)
            fragment = Fragment(start, accept)
            record(token, "Kleene star",
                   f"New start q{start} and accept q{accept}; ε-moves q{start}→q{inner.start} (enter), "
                   f"q{start}→q{accept} (zero times), q{inner.accept}→q{inner.start} (repeat), "
                   f"q{inner.accept}→q{accept} (exit)", fragment)
            stack.append(fragment)

        elif token == PLUS:
            # Rule for N+ (one or more): same as star but WITHOUT the
            # start -> accept skip edge, so N must be passed at least once.
            inner = stack.pop()
            start = nfa.new_state()
            accept = nfa.new_state()
            nfa.add_transition(start, EPSILON, inner.start)
            nfa.add_transition(inner.accept, EPSILON, inner.start)
            nfa.add_transition(inner.accept, EPSILON, accept)
            fragment = Fragment(start, accept)
            record(token, "One or more (+)",
                   f"New start q{start} and accept q{accept}; ε-moves q{start}→q{inner.start} (enter), "
                   f"q{inner.accept}→q{inner.start} (repeat), q{inner.accept}→q{accept} (exit). "
                   "No skip edge, so at least one pass is required", fragment)
            stack.append(fragment)

        elif token == OPTIONAL:
            # Rule for N? (zero or one): like union of N with ε.
            # Enter N, or skip it directly; no loop-back edge.
            inner = stack.pop()
            start = nfa.new_state()
            accept = nfa.new_state()
            nfa.add_transition(start, EPSILON, inner.start)
            nfa.add_transition(start, EPSILON, accept)
            nfa.add_transition(inner.accept, EPSILON, accept)
            fragment = Fragment(start, accept)
            record(token, "Optional (?)",
                   f"New start q{start} and accept q{accept}; ε-moves q{start}→q{inner.start} (take it), "
                   f"q{start}→q{accept} (skip it), q{inner.accept}→q{accept} (exit). No loop", fragment)
            stack.append(fragment)

        else:
            raise ValueError(f"Unexpected token '{token}' in postfix expression")

    if len(stack) != 1:
        raise ValueError("Invalid postfix expression: expected exactly one NFA at the end")

    final_fragment = stack.pop()
    nfa.start = final_fragment.start
    nfa.accept = final_fragment.accept
    return nfa, steps
