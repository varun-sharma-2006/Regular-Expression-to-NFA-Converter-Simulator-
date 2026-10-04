/*
 * extras.js - Part C and page tools:
 *   - language operations (complement, ∩, ∪, −, ⊕)
 *   - practice quiz
 *   - export: graphs as PNG, tables as CSV or LaTeX
 *   - light / dark theme
 *   - shareable links (?regex=...)
 * Uses the helpers defined in main.js ($, postJson, buildTable, ...).
 */

// ---------------------------------------------------------------------------
// Language operations
// ---------------------------------------------------------------------------

function updateOperationForm() {
  const isComplement = $("op-operation").value === "complement";
  $("op-regex2-label").classList.toggle("hidden", isComplement);
}

async function applyOperation() {
  const errorBox = $("op-error");
  hide(errorBox);
  try {
    const result = await postJson("/api/operations", {
      regex1: $("op-regex1").value,
      regex2: $("op-regex2").value,
      operation: $("op-operation").value,
      alphabet: $("op-alphabet").value,
    });
    lastOperation = result;
    show($("op-result"));

    $("op-summary").textContent = `${result.symbol}: ${result.properties.summary}`;
    const facts = [
      ["Σ", "{" + result.alphabet.join(", ") + "}"],
      ["Product states", result.product_table ? result.product_states : "—"],
      ["Minimized result", result.result_dfa.states.length + " states"],
      ["Accepts ε?", result.properties.accepts_empty_string ? "yes" : "no"],
    ];
    $("op-facts").innerHTML = facts
      .map(([name, value]) => `<div><span>${name}</span><b>${escapeHtml(value)}</b></div>`)
      .join("");

    graphs.operation = drawAutomaton("op-graph", result.result_dfa);

    const productBox = $("op-product-box");
    if (result.product_table) {
      show(productBox);
      const alphabet = result.alphabet;
      buildTable(
        $("op-product-table"),
        ["State", "Pair (L1, L2)", "L1 accepts", "L2 accepts", ...alphabet.map(escapeHtml)],
        result.product_table.map((row) => ({
          className: row.is_accept ? "pass" : "",
          cells: [
            markState(row.state, row === result.product_table[0], row.is_accept),
            `(${escapeHtml(row.pair[0])}, ${escapeHtml(row.pair[1])})`,
            row.accept1 ? "yes" : "no",
            row.accept2 ? "yes" : "no",
            ...alphabet.map((symbol) => escapeHtml(row.transitions[symbol])),
          ],
        }))
      );
    } else {
      hide(productBox);
    }

    const strings = result.properties.shortest_strings;
    $("op-strings").innerHTML = strings.length
      ? strings.map((s) => `<code>${escapeHtml(s)}</code>`).join(" ")
      : "<span class='hint'>none (empty language)</span>";
    $("op-regex-back").textContent = result.regex_back.regex || result.regex_back.message;
    $("op-load").disabled = !result.regex_back.regex;
  } catch (error) {
    errorBox.textContent = error.message;
    show(errorBox);
    hide($("op-result"));
  }
}

// ---------------------------------------------------------------------------
// Practice quiz
// ---------------------------------------------------------------------------

let currentQuiz = null;

async function newQuiz() {
  const level = $("quiz-level").value;
  try {
    const response = await fetch("/api/quiz?level=" + encodeURIComponent(level));
    currentQuiz = await response.json();
  } catch (error) {
    alert("Could not load a quiz: " + error.message);
    return;
  }
  show($("quiz-box"));
  hide($("quiz-score"));
  $("quiz-regex").textContent = currentQuiz.regex;

  $("quiz-questions").innerHTML = currentQuiz.questions.map((question, index) => {
    let input;
    if (question.type === "yes_no" || question.type === "choice") {
      const options = question.type === "yes_no" ? ["yes", "no"] : question.options;
      input = options
        .map((option) => `<label><input type="radio" name="quiz-${index}" value="${option}"> ${option}</label>`)
        .join("");
    } else {
      input = `<input type="text" id="quiz-${index}" autocomplete="off" spellcheck="false">`;
    }
    return `<li>${escapeHtml(question.question)}
              <div class="answer-row">${input}</div>
              <span class="quiz-feedback hidden" id="quiz-feedback-${index}"></span></li>`;
  }).join("");
}

function checkQuiz() {
  if (!currentQuiz) return;
  let score = 0;
  currentQuiz.questions.forEach((question, index) => {
    let given = "";
    if (question.type === "yes_no" || question.type === "choice") {
      const checked = document.querySelector(`input[name="quiz-${index}"]:checked`);
      given = checked ? checked.value : "";
    } else {
      given = $("quiz-" + index).value.trim();
    }
    const correct = given.toLowerCase() === question.answer.toLowerCase();
    if (correct) score += 1;
    const feedback = $("quiz-feedback-" + index);
    feedback.className = "quiz-feedback " + (correct ? "right" : "wrong");
    feedback.textContent = (correct ? "✔ Correct. " : `✘ Answer: ${question.answer}. `) + question.explanation;
  });
  const scoreBox = $("quiz-score");
  scoreBox.textContent = `Score: ${score} / ${currentQuiz.questions.length}`;
  scoreBox.className = "verdict " + (score === currentQuiz.questions.length ? "correct" : "nothing");
}

// ---------------------------------------------------------------------------
// Export: graphs as PNG, tables as CSV / LaTeX
// ---------------------------------------------------------------------------

/** Read a table's cells as plain text: a list of rows, each a list of strings. */
function tableToRows(table) {
  const rows = [];
  table.querySelectorAll("tr").forEach((tr) => {
    rows.push(Array.from(tr.children).map((cell) => cell.textContent.trim()));
  });
  return rows;
}

function downloadText(text, fileName, mimeType) {
  const blob = new Blob([text], { type: mimeType });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = fileName;
  link.click();
  URL.revokeObjectURL(link.href);
}

function toCsv(rows) {
  return rows
    .map((row) => row.map((cell) => '"' + cell.replace(/"/g, '""') + '"').join(","))
    .join("\n");
}

/** Escape LaTeX special characters and turn our symbols into math mode. */
function latexEscape(text) {
  return text
    .replace(/\\/g, "\\textbackslash{}")
    .replace(/([&%$#_{}])/g, "\\$1")
    .replace(/~/g, "\\textasciitilde{}")
    .replace(/\^/g, "\\textasciicircum{}")
    .replace(/ε/g, "$\\varepsilon$")
    .replace(/∅/g, "$\\emptyset$")
    .replace(/→/g, "$\\rightarrow$")
    .replace(/✗/g, "$\\times$")
    .replace(/✔/g, "$\\checkmark$")
    .replace(/∪/g, "$\\cup$");
}

function toLatex(rows) {
  const columns = Math.max(...rows.map((row) => row.length));
  const lines = [
    "\\begin{tabular}{" + "|l".repeat(columns) + "|}",
    "\\hline",
  ];
  for (const row of rows) {
    const cells = row.map(latexEscape);
    while (cells.length < columns) cells.push("");
    lines.push(cells.join(" & ") + " \\\\ \\hline");
  }
  lines.push("\\end{tabular}");
  return lines.join("\n");
}

/** Add small export buttons above every graph and table. */
function addExportTools() {
  document.querySelectorAll(".graph[data-graph]").forEach((graphDiv) => {
    const tools = document.createElement("div");
    tools.className = "graph-tools";
    tools.innerHTML = `<button class="secondary" data-action="fit" title="Fit the graph to the box">⤢ Fit</button>
                       <button class="secondary" data-action="png" title="Download as PNG image">⬇ PNG</button>`;
    graphDiv.parentNode.insertBefore(tools, graphDiv);
    tools.addEventListener("click", (event) => {
      const action = event.target.dataset.action;
      const cy = graphs[graphDiv.dataset.graph];
      if (!cy || !action) return;
      if (action === "fit") cy.fit(undefined, 20);
      if (action === "png") downloadGraphPng(cy, graphDiv.dataset.name || "automaton");
    });
  });

  document.querySelectorAll(".table-wrap[data-name]").forEach((wrap) => {
    const tools = document.createElement("div");
    tools.className = "table-tools";
    tools.innerHTML = `<button class="secondary" data-action="csv">⬇ CSV</button>
                       <button class="secondary" data-action="latex">⬇ LaTeX</button>`;
    wrap.parentNode.insertBefore(tools, wrap);
    tools.addEventListener("click", (event) => {
      const action = event.target.dataset.action;
      const table = wrap.querySelector("table");
      if (!action || !table || !table.rows.length) return;
      const rows = tableToRows(table);
      if (action === "csv") downloadText(toCsv(rows), wrap.dataset.name + ".csv", "text/csv");
      if (action === "latex") downloadText(toLatex(rows), wrap.dataset.name + ".tex", "text/plain");
    });
  });
}

// ---------------------------------------------------------------------------
// Theme (light / dark)
// ---------------------------------------------------------------------------

function currentTheme() {
  const chosen = document.documentElement.dataset.theme;
  if (chosen) return chosen;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function toggleTheme() {
  const next = currentTheme() === "dark" ? "light" : "dark";
  document.documentElement.dataset.theme = next;
  try {
    localStorage.setItem("theme", next);
  } catch (error) { /* storage blocked: theme just won't be remembered */ }
  // Re-apply the graph styles with the new colours.
  for (const cy of Object.values(graphs)) {
    if (cy) cy.style(graphStyle());
  }
}

// ---------------------------------------------------------------------------
// Shareable links
// ---------------------------------------------------------------------------

/** Keep the address bar in sync, e.g. http://127.0.0.1:5000/?regex=(a%7Cb)*abb */
function updateShareableUrl(regex) {
  const url = new URL(window.location.href);
  url.searchParams.set("regex", regex);
  window.history.replaceState(null, "", url);
}

async function copyShareLink() {
  const box = $("share-message");
  const link = window.location.href;
  try {
    await navigator.clipboard.writeText(link);
    box.textContent = "Link copied: " + link;
  } catch (error) {
    box.textContent = "Copy this link: " + link;
  }
  show(box);
  setTimeout(() => hide(box), 4000);
}

// ---------------------------------------------------------------------------
// AI setup assistant
// ---------------------------------------------------------------------------

async function openAiDialog() {
  await checkAiStatus();   // main.js: refreshes aiConfigured and the badge
  $("ai-dialog-status").textContent = aiConfigured
    ? "AI is configured: " + $("ai-status").textContent.replace("AI: ", "") + ". Use \"Test connection\" to check the key."
    : "AI is not configured yet. Everything else works without it. Follow these 4 steps to enable it:";
  $("ai-test-result").textContent = "";
  $("ai-dialog").showModal();
}

async function testAiConnection() {
  const result = $("ai-test-result");
  await withBusyButton($("ai-test-button"), "Testing…", async () => {
    try {
      const answer = await postJson("/api/ai/test", {});
      result.className = "test-ok";
      result.textContent = `✔ Connected to ${answer.provider} (${answer.model}). The AI replied: "${answer.reply}"`;
    } catch (error) {
      result.className = "test-fail";
      result.textContent = "✘ " + error.message;
    }
  });
  checkAiStatus();
}

// ---------------------------------------------------------------------------
// Wire up
// ---------------------------------------------------------------------------

document.addEventListener("DOMContentLoaded", () => {
  addExportTools();

  $("op-operation").addEventListener("change", updateOperationForm);
  $("op-button").addEventListener("click", applyOperation);
  $("op-load").addEventListener("click", () => {
    if (lastOperation && lastOperation.regex_back.regex) loadRegex(lastOperation.regex_back.regex);
  });
  updateOperationForm();

  $("quiz-new").addEventListener("click", newQuiz);
  $("quiz-check").addEventListener("click", checkQuiz);
  $("quiz-show").addEventListener("click", () => {
    if (currentQuiz) loadRegex(currentQuiz.regex);
  });

  $("theme-button").addEventListener("click", toggleTheme);
  $("ai-status").addEventListener("click", openAiDialog);
  $("ai-dialog-close").addEventListener("click", () => $("ai-dialog").close());
  $("ai-test-button").addEventListener("click", testAiConnection);
  $("share-button").addEventListener("click", copyShareLink);
});
