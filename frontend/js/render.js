/*
 * render.js - everything that DRAWS with Cytoscape.js.
 *
 * The backend sends an automaton as:
 *   { states: [...], start: S, accepts: [...], dead_state: D, edges: [{from, symbol, to}, ...] }
 *
 * We turn it into Cytoscape "elements" (nodes + edges):
 *   - start state: a tiny invisible node with an arrow pointing at it
 *   - final states: double border (the textbook "double circle")
 *   - dead state: grey dashed border
 *   - several symbols between the same two states share ONE edge, labelled "a,b"
 *   - layout goes left to right (dagre if loaded, otherwise breadth-first)
 *
 * Colours come from CSS variables, so light and dark mode both look right.
 */

const START_MARKER_ID = "__start__";
const START_ARROW_ID = "start-arrow";

/** Read a colour defined in style.css (e.g. --graph-node). */
function cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

/** The id we give the (combined) edge between two states. */
function edgeId(from, to) {
  return "e:" + from + "->" + to;
}

/** Build the Cytoscape elements list for one automaton. */
function buildElements(automaton, labelPrefix) {
  const elements = [];
  const acceptSet = new Set(automaton.accepts.map(String));

  for (const state of automaton.states) {
    const id = String(state);
    const classes = [];
    if (acceptSet.has(id)) classes.push("accept");
    if (id === String(automaton.start)) classes.push("start");
    if (automaton.dead_state !== undefined && automaton.dead_state !== null && id === String(automaton.dead_state)) {
      classes.push("dead");
    }
    elements.push({ data: { id: id, label: labelPrefix + id }, classes: classes.join(" ") });
  }

  // Invisible node + arrow that marks the start state.
  elements.push({ data: { id: START_MARKER_ID, label: "" }, classes: "start-marker" });
  elements.push({
    data: { id: START_ARROW_ID, source: START_MARKER_ID, target: String(automaton.start), label: "start" },
    classes: "start-arrow",
  });

  // Combine all symbols that go between the same pair of states.
  const grouped = new Map();
  for (const edge of automaton.edges) {
    const key = edgeId(edge.from, edge.to);
    if (!grouped.has(key)) grouped.set(key, { from: String(edge.from), to: String(edge.to), symbols: [] });
    grouped.get(key).symbols.push(edge.symbol);
  }
  for (const [key, edge] of grouped) {
    elements.push({
      data: { id: key, source: edge.from, target: edge.to, label: edge.symbols.join(",") },
      classes: edge.from === edge.to ? "loop" : "",
    });
  }
  return elements;
}

/** Choose dagre (nice left-to-right layered layout) if it loaded from the CDN. */
function layoutOptions() {
  // cytoscape-dagre registers itself with Cytoscape and defines this global.
  if (typeof cytoscapeDagre !== "undefined") {
    return { name: "dagre", rankDir: "LR", nodeSep: 40, rankSep: 70, edgeSep: 20 };
  }
  return { name: "breadthfirst", directed: true, spacingFactor: 1.2 };
}

/** The Cytoscape style sheet, built from the current theme colours. */
function graphStyle() {
  const node = cssVar("--graph-node");
  const nodeText = cssVar("--text");
  const border = cssVar("--primary");
  const startFill = cssVar("--graph-start");
  const edge = cssVar("--graph-edge");
  const labelBg = cssVar("--graph-bg");
  const muted = cssVar("--muted");
  return [
    {
      selector: "node",
      style: {
        "label": "data(label)",
        "text-valign": "center",
        "text-halign": "center",
        "text-wrap": "wrap",
        "width": 46,
        "height": 46,
        "background-color": node,
        "border-width": 2,
        "border-color": border,
        "font-size": 14,
        "font-family": "Consolas, monospace",
        "color": nodeText,
      },
    },
    { selector: "node.start", style: { "background-color": startFill } },
    { selector: "node.accept", style: { "border-style": "double", "border-width": 7 } },
    { selector: "node.dead", style: { "border-color": muted, "border-style": "dashed", "color": muted } },
    { selector: "node.start-marker", style: { "width": 2, "height": 2, "opacity": 0 } },
    {
      selector: "edge",
      style: {
        "label": "data(label)",
        "curve-style": "bezier",
        "target-arrow-shape": "triangle",
        "width": 1.6,
        "line-color": edge,
        "target-arrow-color": edge,
        "font-size": 14,
        "font-family": "Consolas, monospace",
        "color": nodeText,
        "text-background-color": labelBg,
        "text-background-opacity": 1,
        "text-background-padding": 2,
        "control-point-step-size": 50,
      },
    },
    { selector: "edge.loop", style: { "loop-direction": "-45deg", "loop-sweep": "-60deg", "control-point-step-size": 60 } },
    { selector: "edge.start-arrow", style: { "font-size": 11, "color": muted } },
    // Syntax tree (direct DFA): smaller nodes, no arrows.
    { selector: "node.tree", style: { "width": 40, "height": 40, "font-size": 13 } },
    { selector: "node.tree-op", style: { "shape": "round-rectangle", "background-color": startFill } },
    { selector: "node.nullable", style: { "border-style": "dashed" } },
    { selector: "edge.tree-edge", style: { "target-arrow-shape": "none" } },
    // Highlighting: animation, hover links and the build player.
    { selector: "node.active", style: { "background-color": cssVar("--highlight"), "color": "#1f2430" } },
    { selector: "node.visited", style: { "background-color": cssVar("--highlight-soft"), "color": "#1f2430" } },
    { selector: "node.hover", style: { "background-color": cssVar("--hover"), "color": "#1f2430" } },
    {
      selector: "edge.active",
      style: { "line-color": "#f08c00", "target-arrow-color": "#f08c00", "width": 3.5 },
    },
    { selector: ".build-hidden", style: { "display": "none" } },
  ];
}

/**
 * Draw `automaton` inside the element with id `containerId`.
 * `labelPrefix` is added before each state name ("q" for NFA states 0,1,2 -> q0,q1,q2).
 * Returns the Cytoscape instance so the caller can highlight states later.
 */
function drawAutomaton(containerId, automaton, labelPrefix = "") {
  const container = document.getElementById(containerId);
  container.innerHTML = "";
  return cytoscape({
    container: container,
    elements: buildElements(automaton, labelPrefix),
    style: graphStyle(),
    layout: layoutOptions(),
    wheelSensitivity: 0.3,
    maxZoom: 1.6,   // stops tiny automata from being blown up to giant size
    minZoom: 0.2,
  });
}

/** Turn 3 into "₃" so positions can be written as a₃ in the syntax tree. */
function subscript(number) {
  const digits = "₀₁₂₃₄₅₆₇₈₉";
  return String(number).split("").map((d) => digits[Number(d)]).join("");
}

/**
 * Draw the syntax tree of the direct (followpos) method, top-down.
 * Leaves show their position (a₁), operator nodes show the operator,
 * and nullable nodes get a dashed border.
 */
function drawSyntaxTree(containerId, tree) {
  const container = document.getElementById(containerId);
  container.innerHTML = "";
  const elements = [];
  for (const node of tree.nodes) {
    const isLeaf = node.kind === "symbol" || node.kind === "end" || node.kind === "epsilon";
    let label = node.label === "." ? "•" : node.label;
    if (node.position !== null) label += subscript(node.position);
    const classes = ["tree", isLeaf ? "tree-leaf" : "tree-op"];
    if (node.nullable) classes.push("nullable");
    elements.push({ data: { id: "t" + node.id, label: label }, classes: classes.join(" ") });
  }
  for (const edge of tree.edges) {
    elements.push({
      data: { id: "te" + edge.from + "-" + edge.to, source: "t" + edge.from, target: "t" + edge.to, label: "" },
      classes: "tree-edge",
    });
  }
  return cytoscape({
    container: container,
    elements: elements,
    style: graphStyle(),
    // A layered top-down layout: root at the top, leaves at the bottom.
    layout: typeof cytoscapeDagre !== "undefined"
      ? { name: "dagre", rankDir: "TB", nodeSep: 25, rankSep: 35 }
      : { name: "breadthfirst", directed: true, roots: ["t" + tree.root] },
    wheelSensitivity: 0.3,
    maxZoom: 1.6,
    minZoom: 0.2,
  });
}

/** Remove all animation highlights. */
function clearHighlights(cy) {
  cy.elements().removeClass("active visited");
}

/**
 * Highlight the animation state after `stepIndex` symbols have been read:
 * states already visited are pale yellow, the current state is bright yellow,
 * and the edge that was just taken is orange.
 */
function highlightStep(cy, path, steps, stepIndex) {
  clearHighlights(cy);
  for (let i = 0; i < stepIndex; i++) {
    cy.getElementById(String(path[i])).addClass("visited");
  }
  cy.getElementById(String(path[stepIndex])).addClass("active");
  if (stepIndex > 0) {
    const step = steps[stepIndex - 1];
    cy.getElementById(edgeId(step.from, step.to)).addClass("active");
  }
}

/**
 * NFA version: highlight a whole SET of active states, plus the symbol
 * edges that were followed to reach them.
 */
function highlightSet(cy, sets, steps, nfaEdges, stepIndex) {
  clearHighlights(cy);
  for (const state of sets[stepIndex]) {
    cy.getElementById(String(state)).addClass("active");
  }
  if (stepIndex > 0) {
    const previous = new Set(sets[stepIndex - 1].map(String));
    const moved = new Set(steps[stepIndex - 1].move.map(String));
    const symbol = steps[stepIndex - 1].symbol;
    for (const edge of nfaEdges) {
      if (edge.symbol === symbol && previous.has(String(edge.from)) && moved.has(String(edge.to))) {
        cy.getElementById(edgeId(edge.from, edge.to)).addClass("active");
      }
    }
  }
}

/** Mark a group of node ids with the "hover" class (or clear it with an empty list). */
function setHover(cy, ids) {
  if (!cy) return;
  cy.nodes().removeClass("hover");
  for (const id of ids) cy.getElementById(String(id)).addClass("hover");
}

/**
 * BUILD PLAYER: show how a graph is built, one step at a time.
 * `frames` is a list of {nodes: [...ids], edges: [...ids], text}. Frame k
 * shows everything from frames 0..k. Returns an object with first/prev/
 * next/last methods used by the ⏮ ◀ ▶ ⏭ buttons.
 */
function createBuildPlayer(cy, frames, statusElement) {
  const player = { index: frames.length - 1 };

  player.show = function (index) {
    player.index = Math.max(0, Math.min(index, frames.length - 1));
    const visible = new Set();
    for (let i = 0; i <= player.index; i++) {
      for (const id of frames[i].nodes) visible.add(String(id));
      for (const id of frames[i].edges) visible.add(String(id));
    }
    cy.batch(() => {
      cy.elements().forEach((element) => {
        if (visible.has(element.id())) element.removeClass("build-hidden");
        else element.addClass("build-hidden");
      });
    });
    const complete = player.index === frames.length - 1;
    statusElement.textContent = complete
      ? `Complete (${frames.length} steps). Use ⏮ to replay the construction.`
      : `Step ${player.index + 1}/${frames.length}: ${frames[player.index].text}`;
  };
  player.first = () => player.show(0);
  player.prev = () => player.show(player.index - 1);
  player.next = () => player.show(player.index + 1);
  player.last = () => player.show(frames.length - 1);
  return player;
}

/** Download a graph as a PNG image (2x resolution, theme background). */
function downloadGraphPng(cy, fileName) {
  const dataUrl = cy.png({ full: true, scale: 2, bg: cssVar("--graph-bg") });
  const link = document.createElement("a");
  link.href = dataUrl;
  link.download = fileName + ".png";
  link.click();
}
