"""
direct_dfa.py - regex -> DFA DIRECTLY, without building an ε-NFA first.
(The "followpos" method, Aho-Sethi-Ullman "Dragon Book" section 3.9.)

IDEA
    Number every symbol occurrence in the regex: these are POSITIONS.
    In (a|b)*abb#  the positions are  a=1, b=2, a=3, b=4, b=5, #=6.
    ('#' is an END MARKER we add: reaching it means "the regex is complete".)

    A DFA state is a SET of positions: "the positions that can match the next
    input symbol". followpos(i) says which positions can come right after
    position i in some matching string.

STEP 1 - build the syntax tree from the postfix of  (regex).#
STEP 2 - for every tree node compute (bottom-up):
    nullable(n) : can n match the empty string?
    firstpos(n) : positions that can match the FIRST symbol of a string of n
    lastpos(n)  : positions that can match the LAST symbol of a string of n

        node        nullable          firstpos                    lastpos
        leaf i      false             {i}                         {i}
        ε leaf      true              ∅                           ∅
        c1 | c2     n1 or n2          f1 ∪ f2                     l1 ∪ l2
        c1 . c2     n1 and n2         f1 ∪ f2 if n1 else f1       l1 ∪ l2 if n2 else l2
        c*          true              f                           l
        c+          n                 f                           l
        c?          true              f                           l

STEP 3 - followpos. Only two operators make one position follow another:
    concatenation c1.c2 : every i in lastpos(c1) is followed by firstpos(c2)
    star / plus  c*, c+ : every i in lastpos(c)  is followed by firstpos(c)  (loop)

STEP 4 - build the DFA (like subset construction, but on positions):
    start state = firstpos(root)
    from state S on symbol a: union of followpos(p) for every p in S labelled a
    a state is accepting if it contains the position of '#'

WHY IT IS INTERESTING: it skips ε-NFAs and ε-closures entirely, and it often
gives fewer states than Thompson + subset construction (but after minimization
both give the SAME minimal DFA, because the minimal DFA is unique).
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from automata.parser import CONCAT, EPSILON, OPTIONAL, PLUS, STAR, UNION, is_operand
from automata.subset import DEAD_STATE_NAME, DFA, make_state_name

END_MARKER = "#"

OPERATOR_KIND = {CONCAT: "concat", UNION: "union", STAR: "star", PLUS: "plus", OPTIONAL: "optional"}


@dataclass
class TreeNode:
    """One node of the syntax tree."""
    node_id: int
    kind: str                      # "symbol", "epsilon", "end", "concat", "union", "star", "plus", "optional"
    label: str                     # what is drawn: "a", "ε", "#", ".", "|", "*", "+", "?"
    children: list["TreeNode"] = field(default_factory=list)
    position: int | None = None    # only leaves with a symbol (or '#') have a position
    nullable: bool = False
    firstpos: set[int] = field(default_factory=set)
    lastpos: set[int] = field(default_factory=set)


def build_syntax_tree(postfix: str) -> tuple[TreeNode, list[TreeNode], dict[int, str], dict[int, set[int]]]:
    """
    Build the syntax tree of the AUGMENTED regex (regex).# from its postfix,
    computing nullable, firstpos, lastpos and followpos on the way.

    Postfix is perfect for this: children are always built before their
    parent, so every node can compute its values from its children at once.

    Returns (root, all_nodes_in_creation_order, symbol_at_position, followpos).
    """
    augmented = postfix + END_MARKER + CONCAT
    stack: list[TreeNode] = []
    nodes: list[TreeNode] = []
    symbol_at: dict[int, str] = {}
    followpos: dict[int, set[int]] = {}

    def new_node(kind: str, label: str, children: list[TreeNode]) -> TreeNode:
        node = TreeNode(node_id=len(nodes), kind=kind, label=label, children=children)
        nodes.append(node)
        return node

    for token in augmented:

        if token == EPSILON:
            # ε matches only the empty string: nullable, no positions.
            node = new_node("epsilon", EPSILON, [])
            node.nullable = True

        elif is_operand(token) or token == END_MARKER:
            # A leaf with a new position number.
            position = len(symbol_at) + 1
            kind = "end" if token == END_MARKER else "symbol"
            node = new_node(kind, token, [])
            node.position = position
            node.firstpos = {position}
            node.lastpos = {position}
            symbol_at[position] = token
            followpos[position] = set()

        elif token in (CONCAT, UNION):
            right = stack.pop()
            left = stack.pop()
            node = new_node(OPERATOR_KIND[token], token, [left, right])
            if token == UNION:
                node.nullable = left.nullable or right.nullable
                node.firstpos = left.firstpos | right.firstpos
                node.lastpos = left.lastpos | right.lastpos
            else:
                node.nullable = left.nullable and right.nullable
                # If the left part can be empty, the string may START in the right part.
                node.firstpos = left.firstpos | right.firstpos if left.nullable else set(left.firstpos)
                # If the right part can be empty, the string may END in the left part.
                node.lastpos = left.lastpos | right.lastpos if right.nullable else set(right.lastpos)
                # followpos rule 1: whatever ends the left part can be followed
                # by whatever starts the right part.
                for position in left.lastpos:
                    followpos[position] |= right.firstpos

        else:
            # Unary operator: * + ?
            child = stack.pop()
            node = new_node(OPERATOR_KIND[token], token, [child])
            node.firstpos = set(child.firstpos)
            node.lastpos = set(child.lastpos)
            if token == PLUS:
                node.nullable = child.nullable
            else:
                node.nullable = True     # * and ? can match zero times
            if token in (STAR, PLUS):
                # followpos rule 2: after the last symbol of one repetition,
                # the first symbol of the next repetition can follow (loop).
                for position in child.lastpos:
                    followpos[position] |= child.firstpos

        stack.append(node)

    root = stack.pop()
    return root, nodes, symbol_at, followpos


def build_direct_dfa(postfix: str) -> tuple[DFA, dict]:
    """
    Build a DFA directly from the postfix regex with the followpos method.

    Returns (dfa, details). `details` holds what the page shows:
        tree      : nodes and edges of the syntax tree, with nullable/firstpos/lastpos
        positions : position -> symbol and followpos
        dfa_table : one row per DFA state with the position sets
    """
    root, nodes, symbol_at, followpos = build_syntax_tree(postfix)
    end_position = len(symbol_at)   # '#' is the last leaf created
    alphabet = sorted({symbol for symbol in symbol_at.values() if symbol != END_MARKER})

    names: dict[frozenset[int], str] = {}
    order: list[frozenset[int]] = []
    queue: deque[frozenset[int]] = deque()
    letter_count = 0

    def get_name(position_set: frozenset[int]) -> str:
        nonlocal letter_count
        if position_set not in names:
            if len(position_set) == 0:
                names[position_set] = DEAD_STATE_NAME
            else:
                names[position_set] = make_state_name(letter_count)
                letter_count += 1
            order.append(position_set)
            queue.append(position_set)
        return names[position_set]

    start_set = frozenset(root.firstpos)
    start_name = get_name(start_set)
    transitions: dict[str, dict[str, str]] = {}
    table_rows = []

    while queue:
        current = queue.popleft()
        current_name = names[current]
        transitions[current_name] = {}
        cells = {}
        for symbol in alphabet:
            # Positions in this state that are labelled with the symbol ...
            matching = sorted(p for p in current if symbol_at[p] == symbol)
            # ... and everything that can follow them.
            target = set()
            for position in matching:
                target |= followpos[position]
            target_name = get_name(frozenset(target))
            transitions[current_name][symbol] = target_name
            cells[symbol] = {"positions": matching, "target_set": sorted(target), "target": target_name}
        table_rows.append({
            "state": current_name,
            "positions": sorted(current),
            "is_start": current == start_set,
            "is_accept": end_position in current,
            "is_dead": len(current) == 0,
            "transitions": cells,
        })

    states = [names[s] for s in order]
    accepts = {names[s] for s in order if end_position in s}
    dead_state = DEAD_STATE_NAME if frozenset() in names else None
    dfa = DFA(states, alphabet, start_name, accepts, transitions, dead_state)

    tree_nodes = []
    tree_edges = []
    for node in nodes:
        tree_nodes.append({
            "id": node.node_id,
            "kind": node.kind,
            "label": node.label,
            "position": node.position,
            "nullable": node.nullable,
            "firstpos": sorted(node.firstpos),
            "lastpos": sorted(node.lastpos),
        })
        for child in node.children:
            tree_edges.append({"from": node.node_id, "to": child.node_id})

    positions = []
    for position in sorted(symbol_at):
        positions.append({
            "position": position,
            "symbol": symbol_at[position],
            "followpos": sorted(followpos[position]),
        })

    details = {
        "tree": {"root": root.node_id, "nodes": tree_nodes, "edges": tree_edges},
        "positions": positions,
        "end_position": end_position,
        "dfa_table": table_rows,
    }
    return dfa, details
