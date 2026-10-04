"""
minimize.py - Stage 4 of the pipeline: DFA -> minimized DFA (table-filling).

IDEA (Myhill-Nerode)
    Two states p and q are EQUIVALENT if, for every possible remaining input
    string w, reading w from p and reading w from q give the same answer
    (both accept or both reject). Equivalent states can be merged.
    Two states are DISTINGUISHABLE if some string w makes one accept and the
    other reject.

TABLE-FILLING ALGORITHM (find all distinguishable pairs)
    Pass 0: mark every pair (p, q) where one is accepting and the other is
            not. The empty string ε already distinguishes them.
    Pass k: for every unmarked pair (p, q) and every symbol a, look at the
            pair (δ(p,a), δ(q,a)). If THAT pair is already marked, then
            (p, q) is distinguishable too: the string "a + whatever
            distinguished the targets" works. Mark (p, q).
    Repeat until a pass marks nothing new.
    Every pair still unmarked is equivalent -> merge them into one group.

Before that we drop unreachable states (they can never be visited, so they
do not affect the language). The input DFA must be complete, which our
subset construction guarantees.
"""

from __future__ import annotations

from collections import deque

from automata.subset import DFA


def remove_unreachable_states(dfa: DFA) -> tuple[DFA, list[str]]:
    """
    Return (new_dfa, removed_states). A breadth-first search from the start
    state finds every reachable state; everything else is removed.
    """
    reachable = {dfa.start}
    queue = deque([dfa.start])
    while queue:
        state = queue.popleft()
        for symbol in dfa.alphabet:
            target = dfa.next_state(state, symbol)
            if target not in reachable:
                reachable.add(target)
                queue.append(target)

    kept_states = [s for s in dfa.states if s in reachable]
    removed_states = [s for s in dfa.states if s not in reachable]
    new_transitions = {s: dict(dfa.transitions[s]) for s in kept_states}
    new_accepts = {s for s in dfa.accepts if s in reachable}
    dead_state = dfa.dead_state if dfa.dead_state in reachable else None
    new_dfa = DFA(kept_states, list(dfa.alphabet), dfa.start, new_accepts, new_transitions, dead_state)
    return new_dfa, removed_states


def _pair(state_a: str, state_b: str, position: dict[str, int]) -> tuple[str, str]:
    """
    Store each pair in ONE fixed order (the order the states appear in the
    DFA), so (A, B) and (B, A) are treated as the same pair.
    """
    if position[state_a] < position[state_b]:
        return (state_a, state_b)
    return (state_b, state_a)


def _group_name(members: list[str]) -> str:
    """A group of one state keeps its name; a merged group is shown as {A,C}."""
    if len(members) == 1:
        return members[0]
    return "{" + ",".join(members) + "}"


def _find_trap_state(
    states: list[str], accepts: set[str], transitions: dict[str, dict[str, str]]
) -> str | None:
    """
    A dead (trap) state is non-accepting and every move loops back to itself.
    Used when the input DFA did not say which state is dead (e.g. a product
    automaton). In a minimal DFA there is at most one such state.
    """
    for state in states:
        if state in accepts:
            continue
        if all(target == state for target in transitions[state].values()):
            return state
    return None


def minimize_dfa(dfa: DFA) -> tuple[DFA, dict]:
    """
    Minimize a complete DFA with the table-filling method.

    Returns (minimized_dfa, details). `details` contains:
        removed_unreachable : states dropped because they cannot be reached
        table_states        : the states used in the table (row/column order)
        passes              : for each pass, the pairs marked and WHY
        marks               : every pair and the pass it was marked in
                              (None = never marked = equivalent)
        groups              : the final equivalence classes
    """
    dfa, removed_states = remove_unreachable_states(dfa)
    states = dfa.states
    position = {state: index for index, state in enumerate(states)}

    # All unordered pairs of different states: (states[i], states[j]) with i < j.
    all_pairs = []
    for i in range(len(states)):
        for j in range(i + 1, len(states)):
            all_pairs.append((states[i], states[j]))

    # marked[pair] = the pass number in which the pair was marked.
    marked: dict[tuple[str, str], int] = {}
    passes: list[dict] = []

    # ---- Pass 0: accepting vs non-accepting ----
    pass_zero = []
    for p, q in all_pairs:
        if dfa.is_accepting(p) != dfa.is_accepting(q):
            marked[(p, q)] = 0
            accepting_one = p if dfa.is_accepting(p) else q
            pass_zero.append({
                "pair": [p, q],
                "reason": f"{accepting_one} is accepting and the other is not (distinguished by ε)",
            })
    passes.append({"pass": 0, "marked": pass_zero})

    # ---- Pass 1, 2, ...: propagate distinguishability backwards ----
    pass_number = 0
    while True:
        pass_number += 1
        newly_marked = []
        # Use only marks from EARLIER passes, so each pass is easy to follow
        # by hand. (The final result is the same either way.)
        marked_before_this_pass = set(marked)
        for p, q in all_pairs:
            if (p, q) in marked:
                continue
            for symbol in dfa.alphabet:
                target_p = dfa.next_state(p, symbol)
                target_q = dfa.next_state(q, symbol)
                if target_p == target_q:
                    continue  # same target: this symbol cannot tell p and q apart
                target_pair = _pair(target_p, target_q, position)
                if target_pair in marked_before_this_pass:
                    marked[(p, q)] = pass_number
                    newly_marked.append({
                        "pair": [p, q],
                        "reason": (
                            f"on '{symbol}': {p}→{target_p} and {q}→{target_q}, "
                            f"and ({target_pair[0]}, {target_pair[1]}) is already marked"
                        ),
                    })
                    break  # one reason is enough
        if not newly_marked:
            passes.append({"pass": pass_number, "marked": []})
            break
        passes.append({"pass": pass_number, "marked": newly_marked})

    # ---- Build equivalence groups from the UNMARKED pairs ----
    # Equivalence is transitive, so a state's group is simply itself plus
    # every later state it was never distinguished from.
    group_of: dict[str, str] = {}
    groups: list[list[str]] = []
    for state in states:
        if state in group_of:
            continue
        members = [state]
        for other in states:
            if other != state and other not in group_of:
                if _pair(state, other, position) not in marked:
                    members.append(other)
        name = _group_name(members)
        for member in members:
            group_of[member] = name
        groups.append(members)

    # ---- Build the minimized DFA: one state per group ----
    # Any member can represent the group, because all members behave the same.
    new_states = [_group_name(members) for members in groups]
    new_transitions: dict[str, dict[str, str]] = {}
    new_accepts: set[str] = set()
    for members in groups:
        name = _group_name(members)
        representative = members[0]
        new_transitions[name] = {}
        for symbol in dfa.alphabet:
            new_transitions[name][symbol] = group_of[dfa.next_state(representative, symbol)]
        if dfa.is_accepting(representative):
            new_accepts.add(name)

    if dfa.dead_state:
        new_dead_state = group_of[dfa.dead_state]
    else:
        new_dead_state = _find_trap_state(new_states, new_accepts, new_transitions)
    minimized = DFA(
        new_states,
        list(dfa.alphabet),
        group_of[dfa.start],
        new_accepts,
        new_transitions,
        new_dead_state,
    )

    marks_list = []
    for p, q in all_pairs:
        marks_list.append({"pair": [p, q], "pass": marked.get((p, q))})

    details = {
        "removed_unreachable": removed_states,
        "table_states": states,
        "passes": passes,
        "marks": marks_list,
        "groups": groups,
    }
    return minimized, details
