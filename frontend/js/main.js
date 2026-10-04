/*
 * main.js - page logic for Part A (simulator) and Part B (AI + verifier).
 *
 * The browser does NO automata work. It only:
 *   1. sends requests to the Flask API (fetch + JSON),
 *   2. fills tables and lists with the answers,
 *   3. asks render.js to draw the graphs and animate them.
 * Part C (operations, quiz) and tools (export, theme, links) are in extras.js.
 */

// ---------------------------------------------------------------------------
// Page state
// ---------------------------------------------------------------------------
let currentRegex = "";       // the regex currently shown in Part A
let currentResult = null;    // the last /api/convert answer
let lastSimulation = null;   // the last /api/simulate answer
let lastVerification = null; // the last /api/verify answer
let lastOperation = null;    // the last /api/operations answer (extras.js)
let aiConfigured = false;
const graphs = {};           // Cytoscape instances: nfa, dfa, tree, direct, min_dfa, test, operation
const players = {};          // build-step players: nfa, dfa, direct

const animation = { kind: "dfa", steps: [], path: [], sets: [], index: 0, timer: null };

const EPSILON = "ε";

// ---------------------------------------------------------------------------
// Small helpers
// ---------------------------------------------------------------------------

/** Shortcut for document.getElementById. */
function $(id) {
  return document.getElementById(id);
}

/** Escape text before putting it inside HTML (prevents broken markup). */
function escapeHtml(text) {
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/** Show a list of states as {0, 1, 2}, or ∅ when empty. */
function formatSet(states, prefix = "") {
  if (!states || states.length === 0) return "∅";
  return "{" + states.map((s) => prefix + s).join(", ") + "}";
}

function show(element) { element.classList.remove("hidden"); }
function hide(element) { element.classList.add("hidden"); }

/**
 * POST json to the API and return the parsed answer.
 * On an error status we throw an Error carrying the server's message.
 */
async function postJson(url, body) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await response.json();
  if (!response.ok) {
    const error = new Error(data.error || "Request failed");
    error.data = data;
    throw error;
  }
  return data;
}

/**
 * Build an HTML table from a header row and body rows (cells are HTML strings).
 * A row can be a plain list of cells, or {cells, className, state}.
 */
function buildTable(tableElement, headers, rows) {
  let html = "<thead><tr>" + headers.map((h) => `<th>${h}</th>`).join("") + "</tr></thead><tbody>";
  for (const row of rows) {
    const rowClass = row.className ? ` class="${row.className}"` : "";
    const rowState = row.state !== undefined ? ` data-state="${escapeHtml(row.state)}"` : "";
    const cells = row.cells || row;
    html += `<tr${rowClass}${rowState}>` + cells.map((c) => `<td class="mono">${c}</td>`).join("") + "</tr>";
  }
  tableElement.innerHTML = html + "</tbody>";
}

/** Prefix a state name with → (start) and * (accepting), like textbooks do. */
function markState(name, isStart, isAccept) {
  let text = "";
  if (isStart) text += "→";
  if (isAccept) text += "*";
  return text + escapeHtml(name);
}

/** The name the minimizer gives a group of merged states: A, or {A,C}. */
function groupName(members) {
  return members.length === 1 ? members[0] : "{" + members.join(",") + "}";
}

/** Temporarily disable a button while waiting for the server. */
async function withBusyButton(button, busyText, work) {
  const original = button.textContent;
  button.disabled = true;
  button.textContent = busyText;
  try {
    await work();
  } finally {
    button.disabled = false;
    button.textContent = original;
  }
}

// ---------------------------------------------------------------------------
// Part A: convert a regex and show every stage
// ---------------------------------------------------------------------------

async function convertRegex() {
  const regex = $("regex-input").value;
  const errorBox = $("regex-error");
  hide(errorBox);
  try {
    const result = await postJson("/api/convert", { regex: regex });
    showPipeline(regex, result);
  } catch (error) {
    errorBox.textContent = error.message;
    show(errorBox);
    hide($("results"));
  }
}

/** Display every stage of a pipeline result (used by Convert, the AI generator and the quiz). */
function showPipeline(regex, result) {
  currentRegex = regex;
  currentResult = result;
  show($("results"));
  // Hide old explanations: they belonged to the previous regex.
  document.querySelectorAll(".explanation").forEach(hide);

  showPostfix(result.parse);
  showNfa(result.nfa);
  showDfa(result.dfa);
  showDirectDfa(result.direct_dfa);
  showMinDfa(result.min_dfa);
  showRegexBack(result.regex_back);
  showProperties(result.properties);
  hide($("test-result"));
  $("verify-regex").value = result.parse.cleaned;
  if ($("op-regex1")) $("op-regex1").value = result.parse.cleaned;
  updateShareableUrl(regex);   // extras.js
}

function showPostfix(parse) {
  if (parse.expanded !== parse.cleaned) {
    $("expanded-output").textContent = parse.expanded;
    show($("expanded-fact"));
  } else {
    hide($("expanded-fact"));
  }
  $("explicit-output").textContent = parse.explicit;
  $("postfix-output").textContent = parse.postfix;
  const rows = parse.steps.map((step, i) => [
    i + 1,
    escapeHtml(step.symbol),
    escapeHtml(step.stack) || "—",
    escapeHtml(step.output) || "—",
    `<span style="font-family: inherit">${escapeHtml(step.action)}</span>`,
  ]);
  buildTable($("postfix-table"), ["#", "Symbol read", "Stack", "Output", "Action"], rows);
}

function showNfa(nfa) {
  graphs.nfa = drawAutomaton("nfa-graph", nfa, "q");

  $("thompson-steps").innerHTML = nfa.steps
    .map((s) => `<li><b>${escapeHtml(s.rule)}</b> (token <code>${escapeHtml(s.token)}</code>): ${escapeHtml(s.description)}</li>`)
    .join("");

  const columns = nfa.alphabet.concat([EPSILON]);
  const rows = nfa.table.map((row) => [
    markState("q" + row.state, row.is_start, row.is_accept),
    ...columns.map((symbol) => formatSet(row.transitions[symbol], "q")),
  ]);
  buildTable($("nfa-table"), ["State", ...columns], rows);

  // One build frame per Thompson rule: the states and edges that rule created.
  const frames = nfa.steps.map((step) => ({
    nodes: step.new_states,
    edges: step.new_edges.map((e) => edgeId(e.from, e.to)),
    text: `${step.rule} (token '${step.token}'): ${step.description}`,
  }));
  if (frames.length) {
    frames[frames.length - 1].nodes = frames[frames.length - 1].nodes.concat([START_MARKER_ID]);
    frames[frames.length - 1].edges = frames[frames.length - 1].edges.concat([START_ARROW_ID]);
  }
  setupBuildPlayer("nfa", frames);
}

/** Frames for a DFA built one state at a time (subset or direct method). */
function dfaBuildFrames(rows, alphabet, setPrefix) {
  return rows.map((row, index) => {
    const targets = alphabet.map((symbol) => row.transitions[symbol].target);
    const moves = alphabet.map((symbol) => `on '${symbol}' → ${row.transitions[symbol].target}`).join(", ");
    const set = row.nfa_states || row.positions;
    return {
      nodes: [row.state, ...targets].concat(index === 0 ? [START_MARKER_ID] : []),
      edges: targets.map((target) => edgeId(row.state, target)).concat(index === 0 ? [START_ARROW_ID] : []),
      text: `Process ${row.state} = ${formatSet(set, setPrefix)}: ${moves || "no symbols"}`,
    };
  });
}

function showDfa(dfa) {
  graphs.dfa = drawAutomaton("dfa-graph", dfa);

  buildTable(
    $("closure-table"),
    ["NFA state", "ε-closure"],
    dfa.closures.map((c) => ["q" + c.state, formatSet(c.closure, "q")])
  );

  const headers = ["DFA state", "NFA states"];
  for (const symbol of dfa.alphabet) headers.push(`move(·, ${escapeHtml(symbol)}) → ε-closure`);
  const rows = dfa.subset_table.map((row) => ({
    state: row.state,
    cells: [
      markState(row.state, row.is_start, row.is_accept),
      formatSet(row.nfa_states, "q"),
      ...dfa.alphabet.map((symbol) => {
        const cell = row.transitions[symbol];
        return `${formatSet(cell.move, "q")} → ${formatSet(cell.closure, "q")} = <b>${escapeHtml(cell.target)}</b>`;
      }),
    ],
  }));
  buildTable($("subset-table"), headers, rows);

  $("dead-state-note").textContent = dfa.dead_state
    ? `${dfa.dead_state} is the dead state (empty set of NFA states). It was added so that every state has a move on every symbol.`
    : "No dead state needed: every move leads to a non-empty set of NFA states.";

  setupBuildPlayer("dfa", dfaBuildFrames(dfa.subset_table, dfa.alphabet, "q"));

  // Hover link: a DFA state <-> the NFA states it stands for.
  const highlightSubset = (state) => {
    setHover(graphs.dfa, state ? [state] : []);
    setHover(graphs.nfa, state ? (dfa.sets[state] || []) : []);
    document.querySelectorAll("#subset-table tr").forEach((tr) => {
      tr.classList.toggle("hover-row", state !== null && tr.dataset.state === state);
    });
  };
  graphs.dfa.on("mouseover", "node", (event) => highlightSubset(event.target.id()));
  graphs.dfa.on("mouseout", "node", () => highlightSubset(null));
  document.querySelectorAll("#subset-table tbody tr").forEach((tr) => {
    tr.addEventListener("mouseenter", () => highlightSubset(tr.dataset.state));
    tr.addEventListener("mouseleave", () => highlightSubset(null));
  });
}

function showDirectDfa(direct) {
  const c = direct.comparison;
  $("direct-comparison").innerHTML =
    `Subset construction: <b>${c.subset_states}</b> states · Direct method: <b>${c.direct_states}</b> states · ` +
    `after minimization both have <b>${c.minimized_direct_states}</b> states · ` +
    (c.equivalent ? "✔ proved to accept the same language" : "✘ languages differ (bug!)");

  graphs.tree = drawSyntaxTree("tree-graph", direct.tree);

  const treeRows = direct.tree.nodes.map((node) => {
    let label = node.label === "." ? "• (concat)" : node.label;
    if (node.position !== null) label += " (position " + node.position + ")";
    return [escapeHtml(label), node.nullable ? "true" : "false", formatSet(node.firstpos), formatSet(node.lastpos)];
  });
  buildTable($("tree-table"), ["Node", "nullable", "firstpos", "lastpos"], treeRows);

  buildTable(
    $("followpos-table"),
    ["Position", "Symbol", "followpos"],
    direct.positions.map((p) => [p.position, escapeHtml(p.symbol), formatSet(p.followpos)])
  );

  const headers = ["DFA state", "Positions"];
  for (const symbol of direct.alphabet) headers.push(`on ${escapeHtml(symbol)}`);
  const rows = direct.dfa_table.map((row) => [
    markState(row.state, row.is_start, row.is_accept),
    formatSet(row.positions),
    ...direct.alphabet.map((symbol) => {
      const cell = row.transitions[symbol];
      return `followpos of ${formatSet(cell.positions)} = ${formatSet(cell.target_set)} = <b>${escapeHtml(cell.target)}</b>`;
    }),
  ]);
  buildTable($("direct-table"), headers, rows);

  graphs.direct = drawAutomaton("direct-graph", direct);
  setupBuildPlayer("direct", dfaBuildFrames(direct.dfa_table, direct.alphabet, ""));
}

function showMinDfa(minDfa) {
  graphs.min_dfa = drawAutomaton("min-graph", minDfa);

  // Passes: which pairs were marked and why.
  let passesHtml = "";
  if (minDfa.removed_unreachable.length) {
    passesHtml += `<p>Removed unreachable states: ${minDfa.removed_unreachable.map(escapeHtml).join(", ")}</p>`;
  }
  for (const pass of minDfa.passes) {
    const title = pass.pass === 0 ? "Pass 0 (accepting vs. non-accepting)" : `Pass ${pass.pass}`;
    passesHtml += `<p><b>${title}</b></p>`;
    if (pass.marked.length === 0) {
      passesHtml += "<p class='hint'>No new pairs marked" + (pass.pass > 0 ? " → algorithm stops." : ".") + "</p>";
    } else {
      passesHtml += "<ul>" + pass.marked
        .map((m) => `<li><code>(${escapeHtml(m.pair[0])}, ${escapeHtml(m.pair[1])})</code> ${escapeHtml(m.reason)}</li>`)
        .join("") + "</ul>";
    }
  }
  $("passes").innerHTML = passesHtml;

  showPairTable(minDfa);

  $("groups").innerHTML = minDfa.groups
    .map((group) => `<code>{${group.map(escapeHtml).join(", ")}}</code>`)
    .join(" ");

  const rows = minDfa.table.map((row) => [
    markState(row.state, row.is_start, row.is_accept),
    ...minDfa.alphabet.map((symbol) => escapeHtml(row.transitions[symbol])),
  ]);
  buildTable($("min-table"), ["State", ...minDfa.alphabet.map(escapeHtml)], rows);

  // Hover link: a minimized state <-> the DFA states merged into it.
  const members = {};
  for (const group of minDfa.groups) members[groupName(group)] = group;
  graphs.min_dfa.on("mouseover", "node", (event) => {
    setHover(graphs.min_dfa, [event.target.id()]);
    setHover(graphs.dfa, members[event.target.id()] || []);
  });
  graphs.min_dfa.on("mouseout", "node", () => {
    setHover(graphs.min_dfa, []);
    setHover(graphs.dfa, []);
  });
}

/**
 * Draw the classic staircase table: row i, column j (j < i) is the pair
 * (state j, state i). ✗k = marked in pass k, "=" = never marked = equivalent.
 */
function showPairTable(minDfa) {
  const tableStates = minDfa.table_states;  // DFA states used by the algorithm
  const passOf = new Map();
  for (const mark of minDfa.marks) {
    passOf.set(mark.pair[0] + "|" + mark.pair[1], mark.pass);
  }
  if (tableStates.length < 2) {
    $("pair-table").innerHTML = "<tr><td>Only one state: nothing to compare.</td></tr>";
    return;
  }
  let html = "<tbody>";
  for (let i = 1; i < tableStates.length; i++) {
    html += `<tr><th>${escapeHtml(tableStates[i])}</th>`;
    for (let j = 0; j < i; j++) {
      const pass = passOf.get(tableStates[j] + "|" + tableStates[i]);
      if (pass === null || pass === undefined) {
        html += `<td class="same" title="equivalent">=</td>`;
      } else {
        html += `<td class="marked" title="marked in pass ${pass}">✗${pass}</td>`;
      }
    }
    html += "</tr>";
  }
  html += "<tr><th></th>" + tableStates.slice(0, -1).map((s) => `<th>${escapeHtml(s)}</th>`).join("") + "</tr>";
  $("pair-table").innerHTML = html + "</tbody>";
}

function showRegexBack(report) {
  const output = $("regex-back-output");
  const verdict = $("regex-back-verdict");
  const loadButton = $("regex-back-load");
  output.textContent = report.regex || "—";
  if (report.regex && report.verified) {
    verdict.className = "verdict correct";
    verdict.textContent = "✔ Proved equivalent to your regex (product automaton check).";
  } else {
    verdict.className = "verdict nothing";
    verdict.textContent = report.message;
  }
  loadButton.disabled = !report.regex;

  $("gnfa-edges").innerHTML = report.initial_edges
    .map((e) => `<li>${escapeHtml(e.from)} → ${escapeHtml(e.to)}: <code>${escapeHtml(e.regex)}</code></li>`)
    .join("");
  $("elimination-steps").innerHTML = report.steps
    .map((step) => {
      const loop = step.loop ? `self-loop <code>${escapeHtml(step.loop)}</code>` : "no self-loop";
      const edges = step.new_edges.length
        ? step.new_edges.map((e) => `${escapeHtml(e.from)} → ${escapeHtml(e.to)}: <code>${escapeHtml(e.regex)}</code>`).join("<br>")
        : "no paths went through it";
      return `<li><b>Eliminate ${escapeHtml(step.eliminated)}</b> (${loop})<br>${edges}</li>`;
    })
    .join("");
}

function showProperties(properties) {
  $("properties-summary").textContent = properties.summary;
  const facts = [
    ["Empty?", properties.empty ? "yes" : "no"],
    ["Finite?", properties.finite ? "yes" : "no (infinite)"],
    ["Number of strings", properties.count === null ? "∞" : properties.count],
    ["Accepts ε?", properties.accepts_empty_string ? "yes" : "no"],
    ["Shortest length", properties.shortest_length === null ? "—" : properties.shortest_length],
    ["Alphabet Σ", "{" + properties.alphabet.join(", ") + "}"],
  ];
  $("properties-facts").innerHTML = facts
    .map(([name, value]) => `<div><span>${name}</span><b>${escapeHtml(value)}</b></div>`)
    .join("");
  $("shortest-strings").innerHTML = properties.shortest_strings.length
    ? properties.shortest_strings.map((s) => `<button class="chip" data-test="${escapeHtml(s)}">${escapeHtml(s)}</button>`).join("")
    : "<span class='hint'>none</span>";
  document.querySelectorAll("#shortest-strings .chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      $("test-string").value = chip.dataset.test === EPSILON ? "" : chip.dataset.test;
      $("section-tester").scrollIntoView();
      testString();
    });
  });
}

// ---------------------------------------------------------------------------
// Build-step players (⏮ ◀ ▶ ⏭ above the ε-NFA, DFA and direct-DFA graphs)
// ---------------------------------------------------------------------------

function setupBuildPlayer(key, frames) {
  const controls = document.querySelector(`.build-controls[data-graph="${key}"]`);
  const status = controls.querySelector(".build-status");
  if (!frames.length) {
    players[key] = null;
    status.textContent = "";
    return;
  }
  players[key] = createBuildPlayer(graphs[key], frames, status);
  players[key].last();
}

// ---------------------------------------------------------------------------
// String tester with step-by-step animation
// ---------------------------------------------------------------------------

async function testString() {
  if (!currentResult) return;
  const automatonKey = $("test-automaton").value;
  const text = $("test-string").value.trim();
  try {
    const result = await postJson("/api/simulate", {
      regex: currentRegex,
      string: text,
      automaton: automatonKey,
    });
    lastSimulation = { input: text || EPSILON, automaton: automatonKey, ...result };
    show($("test-result"));

    const verdict = $("test-verdict");
    verdict.textContent = result.accepted ? "✔ Accepted" : "✘ Rejected";
    verdict.className = "verdict " + (result.accepted ? "accepted" : "rejected");
    $("test-reason").textContent = result.reason;

    // Draw a fresh copy of the chosen automaton for the animation.
    const prefix = automatonKey === "nfa" ? "q" : "";
    graphs.test = drawAutomaton("test-graph", currentResult[automatonKey], prefix);
    stopPlaying();
    animation.kind = result.kind;
    animation.steps = result.steps;
    animation.path = result.path;
    animation.sets = result.sets || [];
    animation.index = 0;
    graphs.test.ready(() => updateAnimation());
  } catch (error) {
    alert(error.message);
  }
}

function updateAnimation() {
  if (animation.kind === "nfa") {
    highlightSet(graphs.test, animation.sets, animation.steps, currentResult.nfa.edges, animation.index);
  } else {
    highlightStep(graphs.test, animation.path, animation.steps, animation.index);
  }

  // Path text with the current state (or set) highlighted.
  $("test-path").innerHTML = animation.path
    .map((state, i) => (i === animation.index ? `<span class="current">${escapeHtml(state)}</span>` : escapeHtml(state)))
    .join(" → ");

  const status = $("anim-status");
  if (animation.index === 0) {
    status.textContent = animation.kind === "nfa"
      ? `Start: ε-closure of the start state = ${animation.path[0]}`
      : `Start in ${animation.path[0]}`;
  } else {
    const step = animation.steps[animation.index - 1];
    status.textContent = animation.kind === "nfa"
      ? `Step ${animation.index}/${animation.steps.length}: read '${step.symbol}', move = ${formatSet(step.move, "q")}, ε-closure = ${formatSet(step.closure, "q")}`
      : `Step ${animation.index}/${animation.steps.length}: read '${step.symbol}', ${step.from} → ${step.to}`;
  }
}

function nextStep() {
  if (animation.index < animation.path.length - 1) {
    animation.index += 1;
    updateAnimation();
    return true;
  }
  return false;
}

function stopPlaying() {
  if (animation.timer) clearInterval(animation.timer);
  animation.timer = null;
}

function play() {
  stopPlaying();
  if (animation.index >= animation.path.length - 1) {
    animation.index = 0;
    updateAnimation();
  }
  animation.timer = setInterval(() => {
    if (!nextStep()) stopPlaying();
  }, 800);
}

function resetAnimation() {
  stopPlaying();
  animation.index = 0;
  updateAnimation();
}

// ---------------------------------------------------------------------------
// Part B: AI features
// ---------------------------------------------------------------------------

async function checkAiStatus() {
  const badge = $("ai-status");
  try {
    const response = await fetch("/api/ai/status");
    const status = await response.json();
    aiConfigured = status.configured;
    badge.textContent = aiConfigured ? `AI: on (${status.provider})` : "AI: not configured";
    badge.className = "badge " + (aiConfigured ? "on" : "off");
  } catch (error) {
    badge.textContent = "AI: server not reachable";
    badge.className = "badge off";
  }
}

const AI_OFF_MESSAGE =
  "AI is not configured. Add LLM_API_KEY to backend/.env and restart the server. " +
  "Everything else works without it.";

async function generateFromEnglish() {
  const messageBox = $("nl-message");
  const description = $("nl-input").value.trim();
  show(messageBox);
  if (!aiConfigured) {
    messageBox.className = "error";
    messageBox.textContent = AI_OFF_MESSAGE;
    return;
  }
  if (!description) {
    messageBox.className = "error";
    messageBox.textContent = "Please type a description first.";
    return;
  }
  await withBusyButton($("nl-button"), "Thinking…", async () => {
    try {
      const result = await postJson("/api/ai/nl-to-regex", { description: description });
      const retries = result.attempts.length - 1;
      messageBox.className = "info";
      messageBox.innerHTML =
        `AI regex: <code>${escapeHtml(result.regex)}</code> (validated by our parser` +
        (retries ? `, after ${retries} retr${retries === 1 ? "y" : "ies"}` : "") +
        "). The stages above now show its automata. Use the verifier below to check it.";
      $("regex-input").value = result.regex;
      showPipeline(result.regex, result.pipeline);
      $("verify-regex").value = result.regex;
      $("section-input").scrollIntoView();
    } catch (error) {
      messageBox.className = "error";
      let text = error.message;
      if (error.data && error.data.attempts) {
        text += " Attempts: " + error.data.attempts.map((a) => `'${a.regex}' (${a.error})`).join("; ");
      }
      messageBox.textContent = text;
    }
  });
}

/** Split "abb, aabb\nbabb" into ["abb", "aabb", "babb"]. */
function splitExamples(text) {
  return text.split(/[,\n]/).map((s) => s.trim()).filter((s) => s.length > 0);
}

async function verify() {
  const resultBox = $("verify-result");
  const verdict = $("verify-verdict");
  try {
    const result = await postJson("/api/verify", {
      regex: $("verify-regex").value,
      positives: splitExamples($("verify-positives").value),
      negatives: splitExamples($("verify-negatives").value),
      expected: $("verify-expected").value,
    });
    lastVerification = result;
    show(resultBox);
    verdict.textContent = result.message;
    verdict.className = "verdict " + result.verdict;

    const rows = result.examples.map((r) => ({
      className: r.passed ? "pass" : "fail",
      cells: [
        escapeHtml(r.string),
        r.kind,
        r.expected,
        r.actual,
        r.passed ? "✔ pass" : "✘ fail",
        r.path.map(escapeHtml).join(" → "),
      ],
    }));
    if (rows.length) {
      buildTable($("verify-table"), ["String", "Type", "Expected", "DFA says", "Result", "Path"], rows);
    } else {
      $("verify-table").innerHTML = "";
    }

    const eq = result.equivalence;
    $("verify-equivalence").innerHTML = eq
      ? `<b>Equivalence check:</b> ${escapeHtml(eq.explanation)}`
      : "";
  } catch (error) {
    show(resultBox);
    verdict.textContent = error.message;
    verdict.className = "verdict error";
    $("verify-table").innerHTML = "";
    $("verify-equivalence").textContent = "";
  }
}

/** The data each "Explain this step" button sends to the explainer. */
function dataForStage(stage) {
  if (stage === "verify") return lastVerification;
  if (stage === "simulate") return lastSimulation;
  if (stage === "operations") return lastOperation;
  if (!currentResult) return null;
  if (stage === "postfix") return currentResult.parse;
  if (stage === "nfa") return { steps: currentResult.nfa.steps, table: currentResult.nfa.table };
  if (stage === "dfa") return { closures: currentResult.dfa.closures, subset_table: currentResult.dfa.subset_table };
  if (stage === "min_dfa") {
    const m = currentResult.min_dfa;
    return { passes: m.passes, groups: m.groups, minimized_table: m.table };
  }
  if (stage === "direct_dfa") {
    const d = currentResult.direct_dfa;
    return { positions: d.positions, dfa_table: d.dfa_table, end_position: d.end_position, comparison: d.comparison };
  }
  if (stage === "regex_back") return currentResult.regex_back;
  if (stage === "properties") return currentResult.properties;
  return null;
}

async function explainStage(button) {
  const stage = button.dataset.stage;
  const box = document.querySelector(`.explanation[data-for="${stage}"]`);
  show(box);
  const data = dataForStage(stage);
  if (!data) {
    box.textContent = "Run this step first, then ask for an explanation.";
    return;
  }
  const regex = stage === "verify" ? data.regex : currentRegex;
  await withBusyButton(button, "Explaining…", async () => {
    box.textContent = aiConfigured ? "The AI tutor is writing an explanation…" : "Preparing explanation…";
    try {
      const result = await postJson("/api/ai/explain", { stage: stage, data: data, regex: regex });
      // Without an API key the server sends a built-in (non-AI) explanation.
      const note = result.source === "built-in"
        ? "\n\n(Built-in explanation. Add an API key in backend/.env for the AI tutor.)"
        : "";
      box.textContent = result.explanation + note;
    } catch (error) {
      box.textContent = error.message;
    }
  });
}

// ---------------------------------------------------------------------------
// Wire up buttons when the page loads
// ---------------------------------------------------------------------------

/** Put a regex in the input box and convert it (used by several buttons). */
function loadRegex(regex) {
  $("regex-input").value = regex;
  convertRegex();
  $("section-input").scrollIntoView();
}

document.addEventListener("DOMContentLoaded", () => {
  $("convert-button").addEventListener("click", convertRegex);
  $("regex-input").addEventListener("keydown", (e) => { if (e.key === "Enter") convertRegex(); });

  $("epsilon-button").addEventListener("click", () => {
    const input = $("regex-input");
    const position = input.selectionStart ?? input.value.length;
    input.value = input.value.slice(0, position) + EPSILON + input.value.slice(position);
    input.focus();
    input.setSelectionRange(position + 1, position + 1);
  });

  document.querySelectorAll("#section-input .chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      $("regex-input").value = chip.dataset.regex;
      convertRegex();
    });
  });

  // Build-step player buttons (⏮ ◀ ▶ ⏭).
  document.querySelectorAll(".build-controls button").forEach((button) => {
    button.addEventListener("click", () => {
      const key = button.closest(".build-controls").dataset.graph;
      if (players[key]) players[key][button.dataset.build]();
    });
  });

  $("regex-back-load").addEventListener("click", () => {
    if (currentResult && currentResult.regex_back.regex) loadRegex(currentResult.regex_back.regex);
  });

  $("test-button").addEventListener("click", testString);
  $("test-string").addEventListener("keydown", (e) => { if (e.key === "Enter") testString(); });
  $("anim-next").addEventListener("click", () => { stopPlaying(); nextStep(); });
  $("anim-play").addEventListener("click", play);
  $("anim-reset").addEventListener("click", resetAnimation);

  $("nl-button").addEventListener("click", generateFromEnglish);
  $("nl-input").addEventListener("keydown", (e) => { if (e.key === "Enter") generateFromEnglish(); });
  $("verify-button").addEventListener("click", verify);

  document.querySelectorAll("button.explain").forEach((button) => {
    button.addEventListener("click", () => explainStage(button));
  });

  checkAiStatus();

  // Open the regex from a shared link (?regex=...), or the classic example.
  const sharedRegex = new URLSearchParams(window.location.search).get("regex");
  $("regex-input").value = sharedRegex || "(a|b)*abb";
  convertRegex();
});
