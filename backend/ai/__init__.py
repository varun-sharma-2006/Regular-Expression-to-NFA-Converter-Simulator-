"""
The ai package: features that use a Large Language Model (LLM).

    llm_client.py    one small function, ask_llm(), that talks to the provider
    nl_to_regex.py   English description -> regex (validated by our parser)
    verifier.py      checks a regex with examples + equivalence (NO LLM needed)
    explainer.py     AI tutor that explains a stage in simple words

Core idea: "AI generates, automata verify." The LLM may make mistakes, so its
regex is never trusted blindly: the automata pipeline checks it.
"""
