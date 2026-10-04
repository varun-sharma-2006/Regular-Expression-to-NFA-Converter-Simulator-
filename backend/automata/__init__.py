"""
The automata package holds every algorithm of the project, written in pure Python.

Pipeline (each file is one stage):
    parser.py      regex text      -> postfix expression
    thompson.py    postfix         -> ε-NFA
    subset.py      ε-NFA           -> DFA
    minimize.py    DFA             -> minimized DFA
    simulate.py    DFA + string    -> accepted / rejected + path of states
    equivalence.py two regexes     -> same language? (+ counterexample)
"""
