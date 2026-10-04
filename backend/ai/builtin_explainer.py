"""
builtin_explainer.py - "Explain this step" WITHOUT an LLM.

When no API key is configured, the explain button still works: we build a
plain-English explanation directly from the data of that stage (the real
state names, sets and table rows). No AI is involved; it is a template
filled in with the actual results, so it is always correct.

With an API key, explainer.py (the AI tutor) is used instead.
"""

from __future__ import annotations


def _set_text(states: list) -> str:
    """[0, 1, 2] -> {0, 1, 2};  [] -> ∅"""
    if not states:
        return "∅"
    return "{" + ", ".join(str(s) for s in states) + "}"


def _explain_postfix(data: dict) -> str:
    explicit = data.get("explicit", "")
    postfix = data.get("postfix", "")
    steps = data.get("steps", [])
    pops = [s for s in steps if "pop" in s.get("action", "")]

    lines = [
        "WHAT THIS STEP DOES",
        "The regex is rewritten in postfix form, where every operator comes AFTER its operands. "
        "Postfix has no parentheses and no precedence rules, so Thompson's construction can read "
        "it left to right with a stack.",
        "",
        "HOW IT WORKED HERE",
        f"1. Hidden concatenation was made visible with '.': {data.get('cleaned', '')}  →  {explicit}",
        "2. The shunting-yard algorithm read the symbols one by one:",
        "   • operands (letters, digits, ε) and the unary operators * + ? went straight to the output;",
        "   • '(' was pushed on the stack, and ')' popped operators until the matching '(';",
        "   • a binary operator (. or |) first popped operators of higher or equal precedence.",
    ]
    if pops:
        lines.append("   Rows where operators were popped to the output:")
        for step in pops:
            lines.append(f"     – read '{step.get('symbol')}': {step.get('action')}")
    lines += [
        f"3. Final postfix: {postfix}",
        "",
        "KEY TAKEAWAY",
        "Precedence is * + ?  >  concatenation (.)  >  union (|). Postfix order encodes this, "
        "so the next stage never needs to think about precedence.",
    ]
    return "\n".join(lines)


def _explain_nfa(data: dict) -> str:
    steps = data.get("steps", [])
    table = data.get("table", [])
    start = next((row["state"] for row in table if row.get("is_start")), "?")
    accept = next((row["state"] for row in table if row.get("is_accept")), "?")

    lines = [
        "WHAT THIS STEP DOES",
        "Thompson's construction builds an ε-NFA from the postfix expression. It reads the postfix "
        "left to right with a stack of small NFA pieces (fragments). Every fragment has exactly one "
        "start state and one accept state.",
        "",
        "HOW IT WORKED HERE",
    ]
    for step in steps:
        lines.append(f"{step.get('step')}. token '{step.get('token')}' → {step.get('rule')}: {step.get('description')}")
    lines += [
        "",
        f"Result: {len(table)} states, start state q{start}, accept state q{accept}.",
        "",
        "KEY TAKEAWAY",
        "Each operator has one fixed rule. Symbols create 2 states, while union, *, + and ? add 2 new "
        "states with ε-moves, and concatenation adds one ε-move. So the NFA has at most 2 states per "
        "symbol/operator: its size grows linearly with the regex.",
    ]
    return "\n".join(lines)


def _explain_dfa(data: dict) -> str:
    rows = data.get("subset_table", [])
    lines = [
        "WHAT THIS STEP DOES",
        "Subset construction turns the ε-NFA into a DFA. Each DFA state stands for a SET of NFA "
        "states: all the states the NFA could be in at the same time.",
        "Two operations are used: move(S, a) = states reachable by one 'a' edge, and "
        "ε-closure(T) = everything reachable from T using only ε-moves.",
        "",
        "HOW IT WORKED HERE",
    ]
    for row in rows:
        role = []
        if row.get("is_start"):
            role.append("start state, the ε-closure of the NFA start")
        if row.get("is_accept"):
            role.append("accepting, because it contains the NFA accept state")
        if row.get("is_dead"):
            role.append("dead state: no NFA state left, it can never accept")
        role_text = f" ({'; '.join(role)})" if role else ""
        lines.append(f"• {row.get('state')} = {_set_text(row.get('nfa_states', []))}{role_text}")
        for symbol, cell in row.get("transitions", {}).items():
            lines.append(
                f"    on '{symbol}': move = {_set_text(cell.get('move', []))}, "
                f"ε-closure = {_set_text(cell.get('closure', []))}  →  {cell.get('target')}"
            )
    lines += [
        "",
        f"Result: {len(rows)} DFA states.",
        "",
        "KEY TAKEAWAY",
        "A DFA has exactly one move per symbol, so it never has to guess. In the worst case there "
        "can be 2^n DFA states for n NFA states, but usually only a few subsets are reachable.",
    ]
    return "\n".join(lines)


def _explain_min_dfa(data: dict) -> str:
    passes = data.get("passes", [])
    groups = data.get("groups", [])
    lines = [
        "WHAT THIS STEP DOES",
        "Minimization merges states that behave the same for every possible future input "
        "(Myhill–Nerode). The table-filling method finds every pair of states that CAN be told apart; "
        "the pairs that are never marked are equivalent.",
        "",
        "HOW IT WORKED HERE",
    ]
    for one_pass in passes:
        marked = one_pass.get("marked", [])
        if one_pass.get("pass") == 0:
            lines.append("Pass 0 – mark pairs where one state accepts and the other does not:")
        else:
            lines.append(f"Pass {one_pass.get('pass')} – mark pairs whose moves lead to an already-marked pair:")
        if not marked:
            lines.append("   nothing new was marked, so the algorithm stops.")
        for mark in marked:
            pair = mark.get("pair", ["?", "?"])
            lines.append(f"   ({pair[0]}, {pair[1]}): {mark.get('reason')}")

    merged = [g for g in groups if len(g) > 1]
    lines.append("")
    lines.append("Equivalence groups: " + ", ".join("{" + ", ".join(g) + "}" for g in groups))
    if merged:
        for group in merged:
            lines.append(f"States {', '.join(group)} were never distinguished, so they are merged into one state.")
    else:
        lines.append("Every pair was distinguished, so the DFA was already minimal.")
    lines += [
        "",
        "KEY TAKEAWAY",
        "If (δ(p,a), δ(q,a)) is distinguishable, then (p, q) is too. The minimal DFA is unique "
        "(up to renaming states) for a given language.",
    ]
    return "\n".join(lines)


def _explain_simulate(data: dict) -> str:
    if data.get("kind") == "nfa":
        lines = [
            "WHAT THIS STEP DOES",
            "The string is run on the ε-NFA directly. An NFA can be in MANY states at once, so we keep "
            "the SET of active states: start with ε-closure({start}); for each symbol a, the new set is "
            "ε-closure(move(set, a)). Accept if the final set contains the accept state.",
            "",
            "HOW IT WORKED HERE",
            f"Input: '{data.get('input', '')}'",
        ]
        path = data.get("path", [])
        if path:
            lines.append(f"Start: {path[0]}")
        for number, step in enumerate(data.get("steps", []), start=1):
            lines.append(f"{number}. read '{step.get('symbol')}': move = {_set_text(step.get('move', []))}, "
                         f"ε-closure = {_set_text(step.get('closure', []))}")
        lines += [
            data.get("reason", ""),
            "",
            "KEY TAKEAWAY",
            "Each active set here is exactly one DFA state from the subset construction. The DFA simply "
            "computes these sets ahead of time, so it needs only one lookup per symbol.",
        ]
        return "\n".join(lines)

    lines = [
        "WHAT THIS STEP DOES",
        "The string is run on the DFA: start in the start state and, for each symbol, follow the "
        "ONE edge with that symbol. The string is accepted if the last state is accepting.",
        "",
        "HOW IT WORKED HERE",
        f"Input: '{data.get('input', '')}'",
    ]
    path = data.get("path", [])
    if path:
        lines.append(f"Start in {path[0]}.")
    for number, step in enumerate(data.get("steps", []), start=1):
        lines.append(f"{number}. read '{step.get('symbol')}': {step.get('from')} → {step.get('to')}")
    lines += [
        data.get("reason", ""),
        "",
        "KEY TAKEAWAY",
        "A DFA needs exactly one step per symbol, so testing a string takes O(n) time, "
        "with no backtracking.",
    ]
    return "\n".join(lines)


def _explain_verify(data: dict) -> str:
    examples = data.get("examples", [])
    failed = [e for e in examples if not e.get("passed")]
    lines = [
        "WHAT THIS STEP DOES",
        "The regex is checked in two ways: (1) each example string is run on its minimized DFA, and "
        "(2) if an expected regex is given, the two languages are compared exactly with a product "
        "automaton.",
        "",
        "HOW IT WORKED HERE",
        f"Regex checked: {data.get('regex', '')}",
        f"Examples: {len(examples)} tested, {len(failed)} failed.",
    ]
    for example in failed:
        lines.append(
            f"   '{example.get('string')}' should be {example.get('expected')}ed but the DFA says "
            f"{example.get('actual')}."
        )
    equivalence = data.get("equivalence")
    if equivalence:
        lines.append(f"Equivalence: {equivalence.get('explanation')}")
    lines += [
        f"Verdict: {data.get('message', '')}",
        "",
        "KEY TAKEAWAY",
        "Examples can only reveal mistakes; they cannot prove a regex correct. The equivalence "
        "check is a real proof: it explores every reachable pair of states.",
    ]
    return "\n".join(lines)


def _explain_direct_dfa(data: dict) -> str:
    comparison = data.get("comparison", {})
    lines = [
        "WHAT THIS STEP DOES",
        "The followpos method builds a DFA straight from the regex, with no ε-NFA. Every symbol "
        "occurrence gets a POSITION number, and an end marker # is added: (regex)#. A DFA state is a "
        "set of positions that can match the next input symbol.",
        "",
        "HOW IT WORKED HERE",
        "followpos table (which positions can come right after each position):",
    ]
    for row in data.get("positions", []):
        lines.append(f"   position {row.get('position')} ('{row.get('symbol')}') → followpos = "
                     f"{_set_text(row.get('followpos', []))}")
    lines.append("DFA states (sets of positions):")
    for row in data.get("dfa_table", []):
        flags = []
        if row.get("is_start"):
            flags.append("start = firstpos(root)")
        if row.get("is_accept"):
            flags.append(f"accepting: contains the # position {data.get('end_position')}")
        flag_text = f" ({'; '.join(flags)})" if flags else ""
        lines.append(f"   {row.get('state')} = {_set_text(row.get('positions', []))}{flag_text}")
        for symbol, cell in row.get("transitions", {}).items():
            lines.append(f"      on '{symbol}': positions {_set_text(cell.get('positions', []))} labelled "
                         f"'{symbol}' → union of their followpos = {_set_text(cell.get('target_set', []))} "
                         f"= {cell.get('target')}")
    if comparison:
        lines += [
            "",
            f"Comparison: subset construction gave {comparison.get('subset_states')} states, the direct "
            f"method gave {comparison.get('direct_states')}. After minimization both have "
            f"{comparison.get('minimized_direct_states')} states, as the theory predicts "
            "(the minimal DFA is unique).",
        ]
    lines += [
        "",
        "KEY TAKEAWAY",
        "Only concatenation and star/plus create followpos links: lastpos(left) → firstpos(right) for "
        "c1·c2, and lastpos(c) → firstpos(c) for c* (the loop back).",
    ]
    return "\n".join(lines)


def _explain_regex_back(data: dict) -> str:
    lines = [
        "WHAT THIS STEP DOES",
        "State elimination turns the minimized DFA back into a regex. Edges may carry regexes "
        "(a generalized NFA). We add a new 'start' and 'final' state, then remove the old states one "
        "by one, replacing every path p → k → q by one edge  p --R(pk) (R(kk))* R(kq)--> q.",
        "",
        "HOW IT WORKED HERE",
    ]
    if data.get("skipped"):
        lines.append(data.get("message", ""))
    for step in data.get("steps", []):
        loop = step.get("loop")
        loop_text = f"self-loop {loop}" if loop else "no self-loop"
        lines.append(f"Eliminate {step.get('eliminated')} ({loop_text}):")
        for edge in step.get("new_edges", []):
            lines.append(f"   {edge.get('from')} → {edge.get('to')}: {edge.get('regex')}")
    lines += [
        "",
        f"Result: {data.get('regex') or '∅ (empty language)'}",
        data.get("message", "") if not data.get("skipped") else "",
        "",
        "KEY TAKEAWAY",
        "Thompson's construction (regex → automaton) plus state elimination (automaton → regex) prove "
        "Kleene's theorem: regular expressions and finite automata describe exactly the same languages. "
        "The order of elimination changes how the regex looks, but never its language.",
    ]
    return "\n".join(lines)


def _explain_properties(data: dict) -> str:
    samples = ", ".join(data.get("shortest_strings", [])) or "none"
    lines = [
        "WHAT THIS STEP DOES",
        "Questions about the language are answered exactly from the minimized DFA:",
        "• EMPTY? – is any accepting state reachable from the start?",
        "• INFINITE? – is there a cycle on a path from the start to an accepting state? "
        "If yes, we can go around it any number of times (pumping), giving infinitely many strings.",
        "• SHORTEST STRINGS – breadth-first search from the start finds strings in order of length.",
        "",
        "HOW IT WORKED HERE",
        data.get("summary", ""),
        f"Accepts ε: {'yes' if data.get('accepts_empty_string') else 'no'}",
        f"Shortest accepted strings: {samples}",
        "",
        "KEY TAKEAWAY",
        "For regular languages these questions are DECIDABLE, and the DFA answers them with simple "
        "graph searches.",
    ]
    return "\n".join(lines)


def _explain_operations(data: dict) -> str:
    lines = [
        "WHAT THIS STEP DOES",
        "Regular languages are CLOSED under complement, union, intersection and difference. "
        "The proofs are constructions:",
        "• complement: make the DFA complete over Σ, then swap accepting and non-accepting states;",
        "• product automaton: run both DFAs together on pairs (p, q) and choose which pairs accept "
        "(∩: both, ∪: at least one, −: first only, ⊕: exactly one).",
        "",
        "HOW IT WORKED HERE",
        f"Operation: {data.get('symbol', '')} over Σ = {{{', '.join(data.get('alphabet', []))}}}",
    ]
    table = data.get("product_table")
    if table:
        lines.append(f"The product automaton has {len(table)} reachable pairs:")
        for row in table:
            pair = row.get("pair", ["?", "?"])
            lines.append(f"   {row.get('state')} = ({pair[0]}, {pair[1]}) "
                         f"{'accepting' if row.get('is_accept') else ''}")
    properties = data.get("properties", {})
    lines.append(properties.get("summary", ""))
    regex = (data.get("regex_back") or {}).get("regex")
    if regex:
        lines.append(f"A regex for the result: {regex}")
    lines += [
        "",
        "KEY TAKEAWAY",
        "Complement only works on a COMPLETE DFA: the dead state must exist so it can become accepting. "
        "And the answer depends on Σ: the complement of a* over {a} is ∅, but over {a, b} it is not.",
    ]
    return "\n".join(lines)


_EXPLAINERS = {
    "postfix": _explain_postfix,
    "nfa": _explain_nfa,
    "dfa": _explain_dfa,
    "min_dfa": _explain_min_dfa,
    "simulate": _explain_simulate,
    "verify": _explain_verify,
    "direct_dfa": _explain_direct_dfa,
    "regex_back": _explain_regex_back,
    "properties": _explain_properties,
    "operations": _explain_operations,
}


def explain_step_builtin(stage: str, data: dict) -> str:
    """Return a template-based explanation of `stage` using its real data."""
    explainer = _EXPLAINERS.get(stage)
    if explainer is None or not isinstance(data, dict):
        return "No built-in explanation is available for this step."
    try:
        return explainer(data)
    except (KeyError, TypeError, AttributeError, IndexError):
        return "The data for this step looks incomplete. Run the step again and retry."
