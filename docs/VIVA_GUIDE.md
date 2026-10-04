# Viva Guide – AutomataAI

For each phase this guide gives: **how the code works**, a **worked trace of `(a|b)*abb`**, and **viva questions with answers**. All trace values were printed by the actual program. A demo checklist is at the end.

---

## Phase 1 – Parser (`automata/parser.py`)

### How it works
1. `clean_regex` removes spaces.
2. `validate_regex` scans left to right and remembers the previous character. It catches: invalid characters, `*`/`+`/`?` with nothing before them, `|` with a missing side, `()`, and unbalanced parentheses. Errors give a 1-based position.
3. `insert_explicit_concat` adds `.` between a character that can *end* an operand and one that can *start* an operand.
4. `infix_to_postfix` runs the shunting-yard algorithm and records a table row for every character.

### Trace
- Explicit: `(a|b)*.a.b.b`
- Postfix: **`ab|*a.b.b.`**

| Read | Stack | Output |
|---|---|---|
| ( | ( | |
| a | ( | a |
| \| | (\| | a |
| b | (\| | ab |
| ) | | ab\| |
| * | | ab\|* |
| . | . | ab\|* |
| a | . | ab\|*a |
| . | . | ab\|*a. |
| b | . | ab\|*a.b |
| . | . | ab\|*a.b. |
| b | . | ab\|*a.b.b |
| end | | ab\|*a.b.b. |

### Viva questions
1. **Why postfix?** Postfix needs no parentheses or precedence rules. Thompson's construction can then read it left to right with a stack: operands push fragments, and operators pop and combine them.
2. **Why insert `.`?** Concatenation has no symbol in the input, but shunting-yard can only handle operators it can see. Without the `.`, `ab|c` would be parsed wrongly.
3. **How do precedence and associativity work?** The precedences are `*+?`=3, `.`=2, `|`=1. Before pushing a binary operator, the algorithm pops every operator with precedence **≥** its own. Using ≥ makes operators left-associative: `a|b|c` becomes `ab|c|`.
4. **Why don't `* + ?` use the stack?** They are unary postfix operators with the highest precedence. Their operand is already complete at the end of the output, so they can go straight to the output.
5. **Complexity?** O(n). Each character is read once, and each operator is pushed and popped at most once.

---

## Phase 2 – Thompson's construction (`automata/thompson.py`)

### How it works
The code keeps a stack of **fragments**. A fragment is a (start, accept) pair. Each postfix token applies one rule (see the README), and every rule only *adds* new states and ε-edges. At the end, exactly one fragment is left, and that fragment is the NFA.

### Trace (`ab|*a.b.b.`)
| # | Token | Rule | Result |
|---|---|---|---|
| 1 | a | Symbol | q0 –a→ q1 |
| 2 | b | Symbol | q2 –b→ q3 |
| 3 | \| | Union | new q4 –ε→ q0, q2; q1, q3 –ε→ new q5 |
| 4 | * | Star | new q6, q7: q6→q4, q6→q7, q5→q4, q5→q7 (all ε) |
| 5 | a | Symbol | q8 –a→ q9 |
| 6 | . | Concat | q7 –ε→ q8 |
| 7 | b | Symbol | q10 –b→ q11 |
| 8 | . | Concat | q9 –ε→ q10 |
| 9 | b | Symbol | q12 –b→ q13 |
| 10 | . | Concat | q11 –ε→ q12 |

Start is **q6** and accept is **q13**: 14 states in total. That is 2 per symbol (5 symbols) + 2 for `|` + 2 for `*`.

### Viva questions
1. **Why does each fragment have exactly one start and one accept state?** Then every rule can join fragments in the same way: connect accept to start with ε. Composition stays simple and provably correct.
2. **What is the difference between the star, plus and optional rules?** Star has both a skip edge (s→f) and a loop edge (accept→start). Plus has no skip edge, so at least one pass is needed. Optional has no loop edge, so there is at most one pass.
3. **How many states does a Thompson NFA have?** At most 2 × the number of symbols and operators, so its size is linear in the length of the regex.
4. **Why use ε-edges for concatenation instead of merging states?** It is simpler, and each rule stays independent. Merging also works (as in the dragon book), but the ε-edge version is easier to draw and explain. Subset construction removes ε-edges later anyway.
5. **How do you know the NFA is correct?** The tests simulate the NFA on every string of length ≤ 4 over {a,b,c,0,1} for 12 regexes and compare each result with an independent checker.

---

## Phase 3 – Subset construction (`automata/subset.py`)

### How it works
- `epsilon_closure(S)`: a depth-first search that follows only ε-edges.
- `move(S, a)`: one step on `a` from every state in S.
- Breadth-first work list: the start state is ε-closure({q6}). For each DFA state and each symbol, the target is ε-closure(move(S, a)). New sets get the next letter name. An empty set is named ∅ (dead state).
- A DFA state is accepting if its set contains q13.

### Trace
| DFA | NFA set | on a | on b |
|---|---|---|---|
| →A | {0,2,4,6,7,8} | move={1,9} → B | move={3} → C |
| B | {0,1,2,4,5,7,8,9,10} | B | move={3,11} → D |
| C | {0,2,3,4,5,7,8} | B | C |
| D | {0,2,3,4,5,7,8,11,12} | B | move={3,13} → E |
| *E | {0,2,3,4,5,7,8,13} | B | C |

This gives 5 states, the same as the textbook (Aho–Ullman). No dead state is needed here. For `(ab)*`, reading `b` first leads to ∅.

### Viva questions
1. **Why "subset" construction?** An NFA can be in many states at once. Each DFA state represents the *set* of NFA states the NFA could be in.
2. **What is the ε-closure?** All states reachable using only ε-moves, including the state itself. It is computed with DFS or BFS.
3. **What is the worst case?** 2ⁿ DFA states for n NFA states. For example, `(a|b)*a(a|b)(a|b)…` needs about 2ᵏ states. That's why app.py limits regex length.
4. **What is the dead state and why add it?** It is the empty set of NFA states. It makes the DFA *complete* (one move for every symbol), which the table-filling algorithm and the equivalence check need.
5. **Which DFA states are accepting?** Those whose NFA set contains the NFA's accept state, because the NFA *could* be in an accepting state.

---

## Phase 4 – Minimization (`automata/minimize.py`) and simulation (`automata/simulate.py`)

### How it works
1. Remove unreachable states using BFS from the start state.
2. Pass 0: mark the pairs (accepting, non-accepting). The empty string ε already tells them apart.
3. Pass k: mark (p, q) if some symbol leads to a pair marked in an earlier pass.
4. Stop when a pass marks nothing new. Unmarked pairs are equivalent, so they are merged into groups.
5. Simulation: follow one edge per symbol and record the path.

### Trace
- **Pass 0:** (A,E), (B,E), (C,E), (D,E). E is the only accepting state.
- **Pass 1:** (A,D): on b, A→C and D→E, and (C,E) is marked. Likewise (B,D) and (C,D).
- **Pass 2:** (A,B): on b, A→C and B→D, and (C,D) is marked. Likewise (B,C).
- **Pass 3:** nothing new, so the algorithm stops.
- **Unmarked:** (A,C). The groups are **{A,C}, {B}, {D}, {E}**, so 5 states become 4.

| State | a | b |
|---|---|---|
| →{A,C} | B | {A,C} |
| B | B | D |
| D | B | E |
| *E | B | {A,C} |

**Simulating `aabb`:** {A,C} –a→ B –a→ B –b→ D –b→ E. **Accepted.**

### Viva questions
1. **When are two states equivalent?** When, for *every* string w, both accept w or both reject it (Myhill–Nerode).
2. **Why does marking work backwards?** If δ(p,a) and δ(q,a) are distinguishable by w, then p and q are distinguishable by a·w.
3. **Why remove unreachable states first?** They never affect the language. If they stayed, the result might not be minimal.
4. **Is the minimal DFA unique?** Yes, up to renaming of states. So two regexes are equivalent if and only if their minimal DFAs are isomorphic.
5. **How long does simulation take?** O(n) for a string of length n: one table lookup per symbol, with no backtracking (unlike an NFA).

---

## Phase 5 – Equivalence (`automata/equivalence.py`)

### How it works
It uses the product automaton with BFS over pairs (p₁, p₂), starting from (start₁, start₂). If one DFA has no edge for a symbol (different alphabets), it goes to an imaginary dead state `None`. The first pair found where exactly one DFA accepts gives the counterexample. BFS order guarantees that this counterexample is a shortest one.

### Trace: `(a|b)*abb` vs `(a|b)*ab`
BFS tries ε, a, b, aa, ab… For `ab`, the first DFA is in a non-accepting state and the second is accepting. Result: **"Not equivalent: 'ab' is accepted by (a|b)*ab but rejected by (a|b)*abb."**

### Viva questions
1. **Is this a proof or only testing?** It is a proof. There are at most |Q₁|×|Q₂| pairs, and every reachable pair is checked.
2. **Why is the counterexample shortest?** BFS visits pairs in order of the length of the string that reaches them.
3. **What is another method?** Minimize both DFAs and check whether they are isomorphic. Or check that L₁ ⊕ L₂ (symmetric difference) is empty, which is exactly what the product automaton does.
4. **How do you handle different alphabets?** Use the union of the alphabets. A missing transition goes to a dead state.
5. **Complexity?** O(|Q₁|·|Q₂|·|Σ|).

---

## Phase 6 – Flask API and frontend

### How it works
`app.py` serves the frontend and exposes JSON routes: `/api/convert`, `/api/simulate`, `/api/equivalence`, `/api/verify`, `/api/ai/status`, `/api/ai/nl-to-regex` and `/api/ai/explain`. Invalid regexes become HTTP 400 with `{error, position}`. The browser (`main.js`) only fetches data and fills tables. `render.js` draws the graphs with Cytoscape.js:
- an invisible node with a "start" arrow marks the start state
- final states have a double border
- the dead state is dashed
- symbols between the same pair of states are merged into one label such as "a,b"
- the dagre layout runs left to right

### Viva questions
1. **Why are the algorithms in Python and not JavaScript?** The algorithms stay in one place, are tested with pytest, and the frontend stays a simple display layer (separation of concerns).
2. **What does a request look like?** `POST /api/convert {"regex": "(a|b)*abb"}` returns the JSON for every stage.
3. **How is the animation done?** The backend returns the path. Next/Play move an index through it, and render.js adds CSS classes to the current node and the edge just taken.
4. **What stops the server from hanging?** The regex length limit (100 characters), because subset construction can blow up exponentially.

---

## Phase 7 – AI features

### How it works
- `llm_client.ask_llm()` is the only place that calls a provider. The provider, key and model come from `.env`.
- `nl_to_regex`: a strict system prompt lists the allowed syntax. The reply is cleaned, and **our parser validates it**. If it is invalid, the parser's error message is sent back to the LLM and it retries (up to 3 times).
- `verifier`: examples are run on the minimized DFA, and equivalence with the expected regex is checked. It gives a verdict without any AI.
- `explainer`: sends the stage's JSON data to the LLM with a tutor-style prompt.
- `builtin_explainer`: used when there is no API key. It fills a fixed template with the stage's real data (state names, sets, marked pairs), so its explanations are always correct.

### Viva questions
1. **Why not trust the AI's regex?** LLMs can produce answers that look right but are wrong. Automata give an exact, checkable answer. That is the core idea: AI generates, automata verify.
2. **Can examples prove a regex correct?** No. They can only find mistakes. The equivalence check against an expected regex is a real proof.
3. **What happens without an API key?** `is_configured()` is False. "Generate regex" returns 503 with a clear message. "Explain this step" falls back to the built-in explainer. Part A and the verifier work normally.
4. **How are AI features tested without paying for API calls?** The tests replace `ask_llm` with a fake function (monkeypatch).

---

## Phase 9 – Direct DFA with followpos (`automata/direct_dfa.py`)

### How it works
1. Augment the regex with an end marker: `(regex)#`. Build the syntax tree from the postfix `…#.`.
2. Number every symbol leaf (including `#`) with a **position**.
3. Compute, bottom-up, for every node:

| Node | nullable | firstpos | lastpos |
|---|---|---|---|
| leaf i | false | {i} | {i} |
| ε | true | ∅ | ∅ |
| c1 \| c2 | n1 or n2 | f1 ∪ f2 | l1 ∪ l2 |
| c1 · c2 | n1 and n2 | f1 ∪ f2 if n1, else f1 | l1 ∪ l2 if n2, else l2 |
| c* / c? | true | f | l |
| c+ | n | f | l |

4. **followpos** comes from only two rules. For c1·c2: every i in lastpos(c1) gets firstpos(c2). For c* and c+: every i in lastpos(c) gets firstpos(c), which is the loop back.
5. The DFA start state is firstpos(root). From S on a, the target is the union of followpos(p) for every p ∈ S labelled a. A state is accepting if it contains the position of `#`.

### Trace: `(a|b)*abb#`
Positions: a=1, b=2, a=3, b=4, b=5, #=6.

| Position | Symbol | followpos |
|---|---|---|
| 1 | a | {1, 2, 3} |
| 2 | b | {1, 2, 3} |
| 3 | a | {4} |
| 4 | b | {5} |
| 5 | b | {6} |
| 6 | # | ∅ |

| DFA | Positions | on a | on b |
|---|---|---|---|
| →A | {1,2,3} | followpos(1)∪followpos(3) = {1,2,3,4} = B | followpos(2) = {1,2,3} = A |
| B | {1,2,3,4} | B | {1,2,3,5} = C |
| C | {1,2,3,5} | B | {1,2,3,6} = D |
| *D | {1,2,3,6} | B | A |

The direct method gives **4 states**. Thompson + subset construction gave 5. After minimization both have 4, and the app *proves* that they accept the same language.

### Viva questions
1. **Why add `#`?** It turns "the regex has matched completely" into an ordinary position. Any DFA state containing that position is accepting.
2. **Why do only concatenation and star create followpos?** Those are the only operators that put one symbol *directly after* another. Union chooses one branch and `?` only adds the option of skipping, so neither creates a "next symbol" relation.
3. **Why can the direct method give fewer states than subset construction?** It never creates the many ε-reachable NFA states. Different DFA states from the subset method can correspond to the same set of positions.
4. **Do both methods give the same minimal DFA?** Yes. The minimal DFA of a language is unique up to renaming, so both shrink to the same 4-state machine.

---

## Phase 10 – DFA → Regex by state elimination (`automata/dfa_to_regex.py`)

### How it works
1. Drop useless states. These are states that are unreachable, or cannot reach acceptance, such as the dead state.
2. Add a new `start` state with an ε-edge to the old start, and a new `final` state with ε-edges from every accepting state. This gives a *generalized NFA*, whose edges carry regexes.
3. Repeatedly remove a state k. For every path p → k → q, add `R(pk) (R(kk))* R(kq)` and union it with any existing p → q edge.
4. When only `start → final` is left, its label is the regex.
5. The result is **verified**: the regex's own minimal DFA is checked for equivalence with the original.

### Trace on the minimized DFA of `(a|b)*abb`
| Step | Eliminate | Self-loop | New edges |
|---|---|---|---|
| 1 | {A,C} | b | start→B: `b*a`, E→B: `a\|bb*a` |
| 2 | D | none | B→B: `a\|ba`, B→E: `bb` |
| 3 | B | `a\|ba` | start→E: `b*a(a\|ba)*bb`, E→E: `(a\|bb*a)(a\|ba)*bb` |
| 4 | E | `(a\|bb*a)(a\|ba)*bb` | start→final: **`b*a(a|ba)*bb((a|bb*a)(a|ba)*bb)*`** |

This looks different from `(a|b)*abb`, but the app proves the two are equivalent.

### Viva questions
1. **What does this prove?** Together with Thompson's construction it proves **Kleene's theorem**: regular expressions and finite automata define exactly the same class of languages.
2. **Why is the result so long?** State elimination writes out every path explicitly, and regexes are not unique. Shortening a regex in general is hard. We apply simple rules such as `ε·r = r`, `r|r = r`, `(r*)* = r*` and `ε|r = r?`.
3. **Does the elimination order matter?** It changes how the regex *looks* but not the language. We remove the state with the fewest (in-edges × out-edges) first, which creates the fewest new edges.
4. **Why remove the dead state first?** No accepted string passes through it, so it would only add ∅ edges.

---

## Phase 11 – Language operations (`automata/product.py`, `automata/operations.py`)

### How it works
- **Product automaton:** states are pairs (p, q) of the two DFAs, built by BFS so only reachable pairs appear. The accepting pairs depend on the operation:

| Operation | Pair (p, q) accepts when… |
|---|---|
| L1 ∩ L2 | both accept |
| L1 ∪ L2 | at least one accepts |
| L1 − L2 | p accepts and q rejects |
| L1 ⊕ L2 | exactly one accepts |

- **Complement:** first make the DFA *complete* over Σ, adding a dead state for missing moves. Then swap accepting and non-accepting states.
- **Different alphabets:** both DFAs are completed over Σ1 ∪ Σ2.

### Trace: `(a|b)*abb` ∩ `(a|b)*b`
Pairs reached: A=({A,C},{A,B}), B=(B,{A,B}), C=({A,C},C), D=(D,C), E=(E,C). Only E is accepting, because both DFAs accept there. The result has the same language as `(a|b)*abb`. That is correct: every string ending in `abb` also ends in `b`. Consistent with this, `(a|b)*abb − (a|b)*b` is **empty**.

**Complement of `a*` over Σ = {a, b}:** the result is "every string containing at least one b". Its regex is `a*b(a|b)*`. In the result graph, the state named ∅ is the *old* dead state. After complementing it is accepting, so it accepts every continuation.

### Viva questions
1. **Why are regular languages closed under intersection?** The product construction builds a DFA for L1 ∩ L2 with |Q1|·|Q2| states, and a language with a DFA is regular.
2. **Why must the DFA be complete before complementing?** In an incomplete DFA a string can "fall off" with no transition, and is rejected. After swapping it must be *accepted*, but there is no state to accept it in. The dead state provides that state.
3. **Does the complement depend on Σ?** Yes. The complement of `a*` is ∅ over {a} but "contains a b" over {a, b}. That is why the app lets you add extra alphabet symbols.
4. **How is equivalence related?** L1 = L2 exactly when L1 ⊕ L2 = ∅. The equivalence checker searches the product for a pair in the symmetric difference.

---

## Phase 12 – Language properties (`automata/operations.py`)

### How it works
- **Empty?** Is any accepting state reachable from the start? (graph search)
- **Infinite?** Keep only *useful* states, those reachable from the start that can also reach acceptance. The language is infinite exactly when they contain a cycle, found by DFS with three colours.
- **Count (if finite):** the useful part has no cycles, so count(s) = [s accepting] + Σ count(δ(s, a)).
- **Shortest strings:** BFS from the start, extending only strings whose state is still useful.

### Trace
- `(a|b)*abb`: infinite. The shortest strings are abb, aabb, babb, aaabb, …
- `a?b?`: finite, exactly 4 strings: ε, a, b, ab.

### Viva questions
1. **Why does a cycle mean infinite?** You can go around the cycle any number of times before reaching acceptance. This is the same idea as the **pumping lemma**.
2. **Why only "useful" states?** A cycle in the dead state (∅ loops to itself) does not create accepted strings.
3. **Are these problems decidable?** Yes. For regular languages emptiness, finiteness and equivalence are all decidable with simple graph searches. For context-free languages equivalence is undecidable.

---

## Phase 13 – NFA simulation (`automata/simulate.py: simulate_nfa`)

### How it works
Keep the **set** of active NFA states. The starting set is ε-closure({start}). For each symbol a, the new set is ε-closure(move(set, a)). The string is accepted if the final set contains the accept state. If the set becomes empty, the string is rejected immediately.

### Trace: `abb` on the ε-NFA of `(a|b)*abb`
{q0,q2,q4,q6,q7,q8} → a → {q0,q1,q2,q4,q5,q7,q8,q9,q10} → b → {q0,q2,q3,q4,q5,q7,q8,q11,q12} → b → {q0,q2,q3,q4,q5,q7,q8,q13}.
The final set contains q13, so `abb` is **accepted**. These four sets are exactly the DFA states A → B → D → E.

### Viva question
**Why have a DFA at all, if the NFA can be simulated?** NFA simulation costs O(n·|Q|) per string because it handles whole sets. The DFA precomputes those sets once (subset construction), so each symbol takes one table lookup, O(n) in total.

---

## Phase 14 – Teaching and usability features

| Feature | How it works |
|---|---|
| Build step by step (⏮ ◀ ▶ ⏭) | The backend records which states and edges each Thompson rule created (`new_states`, `new_edges`). The DFA frames come from the subset table, one row per frame. Hidden elements keep their positions, so the picture grows in place. |
| Hover links | Hovering DFA state A highlights its NFA set {q0, q2, q4, q6, q7, q8}. Hovering {A,C} in the minimized DFA highlights A and C in the DFA. |
| Character classes | `[a-c]` is expanded to `(a|b|c)` *before* validation, so no other stage needs to know about classes. |
| Quiz | `quiz.py` generates random regexes until the minimal DFA has a suitable size, then asks 8 questions. The answers come from the same tested algorithms. |
| Export | PNG through Cytoscape's `cy.png()`. CSV and LaTeX are built from the HTML tables, with ε → `$\varepsilon$`, ∅ → `$\emptyset$`. |
| Theme | All colours are CSS variables with a dark set. The graphs read the same variables. |
| Shareable link | The regex is kept in the URL (`?regex=…`) and loaded on startup. |
| CI | `.github/workflows/tests.yml` runs pytest on every push. |

---

## Testing strategy (likely viva question)

**"How do you know your program is correct for ANY regex, not just your examples?"**

1. **Unit tests** for every algorithm, with known textbook answers. For example:
   - the DFA for `(a|b)*abb` has states A–E, and minimization merges A and C;
   - the followpos table matches the Dragon Book;
   - the direct method gives 4 states.
2. **Random (fuzz) testing** in `tests/test_random.py`. It generates 500 random regexes using every operator (`| * + ? ( ) ε`). For each one:
   - The DFA, the minimized DFA and the direct DFA are run on all 364 strings over {a,b,c} up to length 5. The results are compared with an independent answer key, Python's `re` module. `re` is used only in tests, never in the app.
   - Minimizing the minimized DFA again must not remove any state.
   - The equivalence checker must *prove* that the DFA and the minimized DFA accept the same language.
   - DFA → regex must produce a regex that is *proved* equivalent.
   - For 100 random pairs, ∩, ∪ and − are checked against the answer key on every string up to length 4.
3. **A fixed random seed** means the same regexes are tested every time, so any failure can be reproduced.
4. **API tests** use Flask's test client, and **AI tests** replace the LLM with a fake function, so no key is needed.
5. **GitHub Actions** runs all of this on every push.

## Manual demo checklist

| # | Action | Expected |
|---|---|---|
| 1 | Open the page | `(a|b)*abb` already converted, 5-state DFA, 4-state minimized DFA |
| 2 | Click each example chip | All stages update |
| 3 | Type `(a | b) * abb` (with spaces) | Works the same as without spaces |
| 4 | Type `a||b` | Error: "'\|' at position 3 is missing an expression on its left side." |
| 5 | Type `*a`, `(a`, `()`, `a@`, `[c-a]` | A clear error message for each |
| 6 | `a|bc` vs `(a|b)c` | Postfix `abc.\|` vs `ab\|c.` (precedence) |
| 7 | `[ab]*abb` | "Classes expanded: (a\|b)*abb", same automata as `(a|b)*abb` |
| 8 | `(ab)*` | DFA shows dead state ∅ (dashed) |
| 9 | ε-NFA card: press ⏮ then ▶ repeatedly | NFA is built one Thompson rule at a time |
| 10 | DFA card: hover over state A | NFA states q0, q2, q4, q6, q7, q8 light up |
| 11 | Direct DFA card | 4 states vs 5 from subset construction, "proved to accept the same language" |
| 12 | Minimized card: hover {A,C} | A and C light up in the DFA |
| 13 | DFA → Regex card | Elimination steps and "✔ Proved equivalent" |
| 14 | Properties: click "aabb" | Tester runs it: Accepted |
| 15 | Tester: `aabb` on minimized DFA, Next/Play | Path {A,C}→B→B→D→E animated |
| 16 | Tester: `abb` "on ε-NFA" | A whole *set* of states lights up at each step |
| 17 | Tester: `abc` on `(a|b)*abb` | Rejected: 'c' not in alphabet |
| 18 | Verifier: regex `(a|b)*ab`, positives `abb` | "AI regex is wrong", 'abb' fails |
| 19 | Verifier: regex `a*`, expected `a+` | Counterexample ε |
| 20 | Operations: `(a|b)*abb` ∩ `(a|b)*b` | Same language as `(a|b)*abb` (infinite) |
| 21 | Operations: `(a|b)*abb` − `(a|b)*b` | "The language is EMPTY" |
| 22 | Operations: complement of `a*`, extra alphabet `b` | Shortest strings b, ab, ba…; regex `a*b(a|b)*` |
| 23 | Quiz: New quiz → answer → Check answers | Score and explanations |
| 24 | ⬇ PNG on a graph, ⬇ LaTeX on a table | Files download |
| 25 | ◐ Theme | Switches light/dark, graphs recolour |
| 26 | 🔗 Link, open the link in a new tab | Same regex opens |
| 27 | No API key: "Explain this step" | Built-in explanation using the real states and tables |
| 28 | With key: "strings over {a,b} that end with abb" | Regex generated → all stages drawn → verify it |
| 29 | `cd backend && python -m pytest -q` | All tests pass |
