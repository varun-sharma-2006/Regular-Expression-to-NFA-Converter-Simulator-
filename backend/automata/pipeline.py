"""
pipeline.py - runs every stage in order, so app.py and other files do not
have to repeat it.

    regex -> postfix -> ε-NFA -> DFA -> minimized DFA          (main pipeline)
                     -> direct DFA (followpos) -> minimized    (second method, compared)
    minimized DFA -> regex (state elimination), proved equivalent to the input
    minimized DFA -> language properties (empty / finite / shortest strings)

Also: language operations on TWO regexes (complement, ∩, ∪, −, ⊕).
"""

from __future__ import annotations

from dataclasses import dataclass

from automata.dfa_to_regex import dfa_to_regex
from automata.direct_dfa import build_direct_dfa
from automata.minimize import minimize_dfa
from automata.operations import OPERATIONS, combine_dfas, complement_dfa, describe_language
from automata.parser import parse_regex
from automata.product import are_equivalent
from automata.subset import DFA, subset_construction
from automata.thompson import NFA, thompson_construction

# State elimination can produce very long regexes for big DFAs, so we only
# convert back when the minimized DFA is reasonably small.
MAX_STATES_FOR_REGEX = 25


def regex_to_min_dfa(regex: str) -> DFA:
    """regex -> minimized DFA, using only the main pipeline (fast)."""
    postfix = parse_regex(regex)["postfix"]
    nfa, _ = thompson_construction(postfix)
    dfa, _ = subset_construction(nfa)
    return minimize_dfa(dfa)[0]


def dfa_to_regex_report(dfa: DFA, original: DFA | None = None) -> dict:
    """
    Convert `dfa` back to a regex, and PROVE the result is right by building
    the regex's own minimized DFA and checking equivalence with `dfa`.
    """
    if len(dfa.states) > MAX_STATES_FOR_REGEX:
        return {
            "regex": None,
            "skipped": True,
            "message": f"The DFA has more than {MAX_STATES_FOR_REGEX} states; the regex would be too long to read.",
            "initial_edges": [],
            "steps": [],
            "verified": None,
        }
    regex, initial_edges, steps = dfa_to_regex(dfa)
    if regex is None:
        return {
            "regex": None,
            "skipped": False,
            "message": "The language is empty (∅), so there is no regex for it in our syntax.",
            "initial_edges": initial_edges,
            "steps": steps,
            "verified": None,
        }
    verified = are_equivalent(regex_to_min_dfa(regex), original or dfa)
    return {
        "regex": regex,
        "skipped": False,
        "message": "Proved equivalent to the original language." if verified else "Verification FAILED.",
        "initial_edges": initial_edges,
        "steps": steps,
        "verified": verified,
    }


@dataclass
class PipelineResult:
    """Everything produced for one regex."""
    parse: dict          # output of parse_regex (explicit form, postfix, steps)
    nfa: NFA
    nfa_steps: list[dict]
    dfa: DFA
    subset_details: dict
    min_dfa: DFA
    min_details: dict
    direct_dfa: DFA
    direct_details: dict
    direct_min_dfa: DFA

    def to_dict(self) -> dict:
        """All stages as JSON-friendly data for the frontend."""
        comparison = {
            "subset_states": len(self.dfa.states),
            "direct_states": len(self.direct_dfa.states),
            "minimized_subset_states": len(self.min_dfa.states),
            "minimized_direct_states": len(self.direct_min_dfa.states),
            "equivalent": are_equivalent(self.direct_dfa, self.min_dfa),
        }
        return {
            "parse": self.parse,
            "nfa": {**self.nfa.to_dict(), "steps": self.nfa_steps},
            "dfa": {**self.dfa.to_dict(), **self.subset_details},
            "min_dfa": {**self.min_dfa.to_dict(), **self.min_details},
            "direct_dfa": {**self.direct_dfa.to_dict(), **self.direct_details, "comparison": comparison},
            "regex_back": dfa_to_regex_report(self.min_dfa),
            "properties": describe_language(self.min_dfa),
        }


def run_pipeline(regex: str) -> PipelineResult:
    """
    Run all stages on `regex`.
    Raises RegexSyntaxError (from the parser) if the regex is invalid.
    """
    parse_result = parse_regex(regex)
    nfa, nfa_steps = thompson_construction(parse_result["postfix"])
    dfa, subset_details = subset_construction(nfa)
    min_dfa, min_details = minimize_dfa(dfa)
    direct, direct_details = build_direct_dfa(parse_result["postfix"])
    direct_min, _ = minimize_dfa(direct)
    return PipelineResult(
        parse_result, nfa, nfa_steps, dfa, subset_details, min_dfa, min_details,
        direct, direct_details, direct_min,
    )


def run_language_operation(regex1: str, regex2: str, operation: str, extra_alphabet: str = "") -> dict:
    """
    Apply `operation` ("complement", "union", "intersection", "difference",
    "symmetric_difference") and describe the resulting language.

    For complement only regex1 is used. Σ = symbols of the regex(es) plus
    `extra_alphabet` (complement depends on Σ: the complement of a* over {a}
    is ∅, but over {a, b} it is every string containing a b).
    """
    dfa1 = regex_to_min_dfa(regex1)
    extra = sorted(set(extra_alphabet))

    if operation == "complement":
        symbol = "Σ* − L1"
        result = complement_dfa(dfa1, extra)
        product_table = None
    elif operation in OPERATIONS:
        symbol = OPERATIONS[operation][0]
        dfa2 = regex_to_min_dfa(regex2)
        if extra:
            from automata.product import complete_dfa
            dfa1 = complete_dfa(dfa1, extra)
        result, product_table = combine_dfas(dfa1, dfa2, operation)
    else:
        raise ValueError(f"Unknown operation '{operation}'")

    minimized, _ = minimize_dfa(result)
    return {
        "operation": operation,
        "symbol": symbol,
        "alphabet": list(minimized.alphabet),
        "product_table": product_table,
        "product_states": len(result.states),
        "result_dfa": minimized.to_dict(),
        "properties": describe_language(minimized),
        "regex_back": dfa_to_regex_report(minimized),
    }
