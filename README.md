# AutomataAI – AI-Assisted Regular Expression to Minimized DFA Simulator

> **AI generates, automata verify.**

![tests](https://github.com/OWNER/REPO/actions/workflows/tests.yml/badge.svg)
<!-- After pushing to GitHub, replace OWNER/REPO above with your username and repository name. -->

A web app that converts a regular expression, step by step, into an ε-NFA (Thompson's construction), a DFA (subset construction, and also directly with the followpos method), a minimized DFA (table-filling), and back into a regex (state elimination). You can test strings with animations on the DFA or the ε-NFA, combine languages (∩ ∪ − ⊕ complement), answer questions about a language, and practise with a quiz. An LLM can turn plain-English descriptions into regexes, and the automata algorithms **verify** whether the AI's regex is actually correct.

All automata algorithms are written by hand in pure Python. The project uses no regex or automata libraries.

---

## Features

### Part A – Automata simulator
| # | Stage | What you see |
|---|---|---|
| 1 | Input | Regex box, ε button, examples, clear errors with position, **🔗 shareable link** |
| 2 | Postfix | Character classes expanded, explicit concatenation, postfix, shunting-yard table |
| 3 | ε-NFA | Graph with a **step-by-step build player** (⏮ ◀ ▶ ⏭), every Thompson rule, transition table |
| 4 | DFA | ε-closures, subset-construction table, dead state, graph with build player, **hover a DFA state to light up its NFA states** |
| 5 | Direct DFA | **followpos method**: syntax tree, nullable/firstpos/lastpos, followpos table, DFA; compared with subset construction |
| 6 | Minimized DFA | Marking passes with reasons, staircase table, groups, table, graph (**hover to see merged states**) |
| 7 | DFA → Regex | **State elimination** step by step; the result is *proved* equivalent to your regex |
| 8 | Properties | Empty? finite? infinite? number of strings, accepts ε?, **shortest accepted strings** |
| 9 | String tester | On the minimized DFA, DFA, or **ε-NFA (animated set of active states)**, with Next / Play / Reset |

### Part B – AI features
| # | Feature | Needs API key? |
|---|---|---|
| 10 | Natural language → regex (strict prompt, validated by our parser, retries with error feedback) | Yes |
| 11 | Regex verifier: examples on the DFA + exact equivalence proof with a shortest counterexample | **No** |
| – | "Explain this step" on every stage | No (built-in explanation without a key; AI tutor with one) |

### Part C – Language operations and practice
| # | Feature |
|---|---|
| 12 | **Language operations**: L1 ∩ L2, L1 ∪ L2, L1 − L2, L1 ⊕ L2 (product automaton) and complement Σ* − L1, with result DFA, product table, properties and a regex for the result |
| 13 | **Practice quiz**: random regex (easy/medium/hard) with 8 questions, checked automatically |

### Tools
- **Export:** every graph as PNG, every table as CSV or LaTeX (ready for your report)
- **Light/dark theme** (follows your system; ◐ button to switch)
- **Works on phones** (responsive layout)

---

## Project structure

```
backend/
  app.py                 Flask server + JSON API (also serves the frontend)
  quiz.py                random practice quizzes
  automata/
    parser.py            validation, character classes, explicit concatenation, shunting-yard
    thompson.py          postfix → ε-NFA (Thompson's construction)
    subset.py            ε-closure, move, ε-NFA → DFA (subset construction)
    direct_dfa.py        regex → DFA directly (syntax tree + followpos)
    minimize.py          DFA minimization (table-filling / Myhill–Nerode)
    dfa_to_regex.py      DFA → regex (state elimination)
    simulate.py          run a string on a DFA or on the ε-NFA
    product.py           product automaton, completing a DFA, shortest counterexample
    equivalence.py       are two regexes equivalent? (+ counterexample)
    operations.py        complement, ∩ ∪ − ⊕, empty / finite / infinite, shortest strings
    pipeline.py          runs all stages in order
  ai/
    llm_client.py        the only file that talks to the LLM provider (configurable)
    nl_to_regex.py       English → regex, validated by parser.py, with retries
    verifier.py          examples + equivalence verdict (no AI needed)
    explainer.py         AI tutor for any stage
    builtin_explainer.py explanation without AI (used when no API key is set)
  tests/                 pytest tests (incl. 500 random regexes checked against an answer key)
  requirements.txt
  .env.example
frontend/
  index.html, style.css
  js/render.js           Cytoscape.js drawing, build player, highlighting, PNG export
  js/main.js             Parts A and B: fetch API, fill tables, animations
  js/extras.js           Part C, export, theme, shareable links
docs/
  VIVA_GUIDE.md          per-phase explanation, worked example, viva Q&A, demo checklist
run.bat                  double-click launcher (Windows)
render.yaml              one-click deploy configuration for Render.com
.github/workflows/       GitHub Actions: runs all tests on every push
```

---

## Setup and run (Windows)

**Easiest:** double-click **`run.bat`** in the project folder. The first run creates the virtual environment and installs the packages, then the browser opens at http://127.0.0.1:5000. Close the black window to stop the server.

**Manual way:**

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# optional, only for the AI features:
copy .env.example .env      # then open .env and paste your key into LLM_API_KEY

python app.py
```
Open **http://127.0.0.1:5000** in your browser.

(macOS/Linux: `source .venv/bin/activate` and `cp .env.example .env`.)

**Shareable links:** the address bar always contains the current regex, e.g. `http://127.0.0.1:5000/?regex=(a%7Cb)*abb`. Opening that link shows the same regex.

### Run the tests
```powershell
cd backend
.venv\Scripts\activate
python -m pytest -v
```

`tests/test_random.py` generates **500 random regexes** (fixed seed, so every run is the same) using every operator. For each one, the DFA, the minimized DFA and the direct (followpos) DFA are checked on all 364 strings over {a,b,c} up to length 5 against an independent answer key. It also checks that:
- the minimized DFA cannot shrink further, and is proved equivalent to the DFA;
- DFA → regex gives a regex proved equivalent to the original;
- ∩, ∪ and − on 100 random pairs match the answer key.

### AI configuration (`backend/.env`)
| Variable | Meaning |
|---|---|
| `LLM_PROVIDER` | `anthropic` (default) or `openai` (OpenAI and any OpenAI-compatible server: Groq, OpenRouter, Ollama…) |
| `LLM_API_KEY` | your secret key. Never put it in the code. `.env` is in `.gitignore` |
| `LLM_MODEL` | optional. Defaults: `claude-opus-5-5` (anthropic), `gpt-4o-mini` (openai) |
| `LLM_BASE_URL` | optional, only for OpenAI-compatible servers |

---

## Put it online (optional)

1. Create a GitHub repository and push this project (see "Git" below).
2. On **render.com**: *New + → Blueprint* → choose your repository. `render.yaml` sets everything up (free plan).
3. Optional: in the Render dashboard add the environment variable `LLM_API_KEY` to enable AI.
4. Render gives you a public link like `https://automata-ai.onrender.com` that your teacher can open on any device.

GitHub Actions (`.github/workflows/tests.yml`) runs all tests automatically on every push. The green badge at the top of this README shows that they pass.

### Git
The project is already a Git repository with the first commit. To publish it:
```powershell
git remote add origin https://github.com/<your-username>/<repo-name>.git
git branch -M main
git push -u origin main
```

---

## Supported regex syntax
| Item | Meaning |
|---|---|
| `a`–`z`, `A`–`Z`, `0`–`9` | input symbols |
| `ε` | empty string |
| `[abc]`, `[a-d]`, `[0-9]` | character class: shorthand for `(a\|b\|c)`, `(a\|b\|c\|d)`, … |
| `r\|s` | union (lowest precedence) |
| `rs` | concatenation (implicit; we insert `.` internally) |
| `r*` `r+` `r?` | zero-or-more, one-or-more, zero-or-one (highest precedence) |
| `( )` | grouping |

Precedence: `* + ?` > concatenation > `|`. All binary operators are left-associative. Maximum length: 100 characters.

---

## How the algorithms work (short version)

**1. Parser (shunting-yard).** Spaces are removed and character classes are expanded (`[a-c]` becomes `(a|b|c)`). The regex is then validated. A `.` is inserted wherever concatenation is implied: between a character that can *end* an operand (`a`, `ε`, `)`, `*`, `+`, `?`) and one that can *start* an operand (`a`, `ε`, `(`). Then the infix expression is converted to postfix. Result for `(a|b)*abb`: `ab|*a.b.b.`

**2. Thompson's construction.** Read the postfix with a stack of NFA fragments. Each fragment has one start and one accept state.
- Symbol `a`: `s --a--> f`
- Concatenation `N1.N2`: ε from `N1.accept` to `N2.start`
- Union `N1|N2`: new `s` with ε to both starts, and ε from both accepts to a new `f`
- Star `N*`: new `s`, `f`; ε `s→N`, `s→f` (skip), `N.accept→N.start` (loop), `N.accept→f`
- Plus `N+`: the same as star but without the skip edge
- Optional `N?`: the same as star but without the loop edge

**3. Subset construction.** Each DFA state is a *set* of NFA states. The start state is ε-closure({q₀}). The target on a is ε-closure(move(S, a)). An empty set becomes the dead state ∅.

**4. Direct DFA (followpos).** Number the symbol positions of `(regex)#`. Compute nullable, firstpos and lastpos bottom-up on the syntax tree. Only concatenation and star/plus create followpos links. A DFA state is a set of positions; from S on a, the target is the union of followpos(p) for all p in S labelled a. A state is accepting if it contains the position of `#`. There are no ε-moves at all.

**5. Minimization (table-filling, Myhill–Nerode).** Remove unreachable states. Pass 0 marks (accepting, non-accepting) pairs. A later pass marks (p, q) if some symbol leads to a marked pair. Unmarked pairs are merged.

**6. DFA → regex (state elimination).** Add new `start` and `final` states with ε-edges. Then remove states one by one, replacing each path p → k → q by `R(pk) R(kk)* R(kq)`. The result is verified with the equivalence check.

**7. Simulation.** On a DFA, follow one edge per symbol (O(n)). On the ε-NFA, keep the *set* of active states: ε-closure(move(set, a)).

**8. Product automaton.** Run two DFAs together on pairs (p, q).
- **Equivalence:** BFS finds a pair where exactly one DFA accepts. The string leading to it is a shortest counterexample.
- **Operations:** choose which pairs accept (∩ both, ∪ either, − first only, ⊕ exactly one).
- **Complement:** make the DFA complete over Σ, then swap accepting and non-accepting states.

**9. Properties.**
- **Empty:** no accepting state is reachable.
- **Infinite:** a cycle lies on a start→accept path.
- **Finite:** count the paths.
- **Shortest strings:** BFS.

**10. "AI generates, automata verify".** The LLM's reply is never trusted. Our parser must accept it, otherwise the error is sent back for a retry. Then the verifier checks it on examples and proves equivalence with an expected regex.

See **[docs/VIVA_GUIDE.md](docs/VIVA_GUIDE.md)** for the full worked example on `(a|b)*abb`, viva questions with answers, and the demo checklist.
