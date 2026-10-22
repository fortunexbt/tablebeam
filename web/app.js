/* The page is a thin shell: every number it shows comes back from worker.js,
 * which runs the app's own Python. Nothing is computed here. */

const el = (id) => document.getElementById(id);
const nodes = {
  runtime: el("runtime"), sources: el("sources"), file: el("file"),
  tableCard: el("table-card"), tableName: el("table-name"), tableShape: el("table-shape"),
  tableParse: el("table-parse"), tableNote: el("table-note"), columns: el("columns"), columnsCaption: el("columns-caption"),
  warnings: el("warnings"), form: el("ask-form"), question: el("question"), submit: el("submit"),
  chips: el("chips"), failure: el("failure"), answer: el("answer"), restated: el("restated"),
  total: el("total"), groups: el("groups"), timing: el("timing"), parsed: el("parsed"),
  method: el("method"), evidenceOf: el("evidence-of"), working: el("working"),
  evidence: el("evidence"), evidenceCaption: el("evidence-caption"), download: el("download"),
  recorded: el("recorded"),
  recordedIntro: el("recorded-intro"), recordedQuestion: el("recorded-question"),
  recordedText: el("recorded-text"), recordedCoverage: el("recorded-coverage"),
  recordedSources: el("recorded-sources"), credits: el("credits"),
};

const STAGES = {
  runtime: "Downloading CPython for WebAssembly…",
  pandas: "Downloading pandas…",
  engine: "Loading Tablebeam's own modules…",
};

const state = { catalog: [], recorded: null, dataset: null, table: null, answer: null, group: null };

/* --- worker ---------------------------------------------------------- */

const worker = new Worker("/worker.js", { type: "module" });
const pending = new Map();
let ready = null;
let nextId = 0;

const engine = (call, args = {}) =>
  ready.then(
    () =>
      new Promise((resolve, reject) => {
        const id = ++nextId;
        pending.set(id, { resolve, reject });
        worker.postMessage({ id, call, args });
      }),
  );

ready = new Promise((resolve, reject) => {
  worker.onmessage = ({ data }) => {
    if (data.type === "stage") {
      nodes.runtime.dataset.state = "working";
      nodes.runtime.textContent = STAGES[data.stage];
    } else if (data.type === "ready") {
      resolve(data);
    } else if (data.type === "broken") {
      reject(new Error(data.reason));
    } else {
      const call = pending.get(data.id);
      pending.delete(data.id);
      if (data.type === "result") call.resolve(data.value);
      else call.reject(new Error(data.reason));
    }
  };
});

/* --- rendering helpers ----------------------------------------------- */

function clear(node) {
  node.replaceChildren();
  return node;
}

function add(parent, tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined && text !== null) node.textContent = text;
  if (className) node.className = className;
  parent.append(node);
  return node;
}

function renderRows(table, columns, rows) {
  const head = clear(table.tHead ?? table.createTHead()).insertRow();
  add(head, "th", "#", "idx");
  for (const column of columns) {
    add(head, "th", column.friendly, column.numeric ? "num" : null).scope = "col";
  }
  const body = clear(table.tBodies[0] ?? table.createTBody());
  for (const row of rows) {
    const line = body.insertRow();
    add(line, "td", row.row, "idx");
    row.cells.forEach((cell, index) => {
      const numeric = columns[index]?.numeric;
      const node = add(line, "td", cell ?? "—", numeric ? "num" : null);
      if (cell === null) node.classList.add("blank");
    });
  }
}

function paragraphs(node, text) {
  clear(node);
  for (const block of text.split("\n\n")) {
    if (block.startsWith("- ")) {
      const list = add(node, "ul");
      for (const item of block.split("\n")) add(list, "li", item.replace(/^- /, ""));
    } else {
      add(node, "p", block.replace(/\n/g, " "));
    }
  }
}

function fail(reason) {
  nodes.failure.textContent = reason;
  nodes.failure.hidden = false;
}

/* --- tables ----------------------------------------------------------- */

function renderTable(dataset, table) {
  state.table = table;
  nodes.tableName.textContent = dataset.name;
  const columns = table.columns.length;
  nodes.tableShape.textContent =
    `${table.rows.toLocaleString()} ${table.rows === 1 ? "row" : "rows"} × ${columns} ` +
    `${columns === 1 ? "column" : "columns"}`;
  nodes.tableParse.textContent = `parsed in ${Math.round(table.ms)} ms`;
  nodes.tableNote.textContent = dataset.note;

  clear(nodes.columns);
  for (const column of table.columns) {
    const item = add(nodes.columns, "li", column.friendly, column.numeric ? "num" : null);
    if (column.missing) add(item, "span", ` ${column.missing.toLocaleString()} blank`, "blank");
  }
  const numeric = table.columns.filter((column) => column.numeric).length;
  nodes.columnsCaption.textContent = numeric
    ? `${numeric} ${numeric === 1 ? "column holds" : "columns hold"} numbers and can be totalled or averaged. Any column can group a result.`
    : "No column holds numbers, so only row counts are available.";

  clear(nodes.warnings);
  for (const warning of table.warnings) add(nodes.warnings, "li", warning);
  nodes.warnings.hidden = table.warnings.length === 0;
  nodes.tableCard.hidden = false;

  const questions = dataset.questions ?? table.suggestions;
  clear(nodes.chips);
  for (const question of questions) {
    add(nodes.chips, "button", question).onclick = () => {
      nodes.question.value = question;
      ask(question);
    };
  }
  nodes.question.placeholder = questions[0] ?? "Count rows";
}

async function openTable(dataset, bytes) {
  nodes.failure.hidden = true;
  nodes.answer.hidden = true;
  nodes.recorded.hidden = true;
  state.dataset = dataset;
  for (const button of nodes.sources.children) {
    button.setAttribute("aria-pressed", String(button.dataset.file === dataset.file));
  }
  try {
    renderTable(dataset, await engine("load", { bytes, label: dataset.name }));
  } catch (error) {
    nodes.tableCard.hidden = true;
    fail(error.message);
    return;
  }
  const first = (dataset.questions ?? state.table.suggestions)[0];
  if (first) {
    nodes.question.value = first;
    await ask(first);
  }
}

async function openBundled(dataset) {
  const response = await fetch(`/datasets/${dataset.file}`);
  await openTable(dataset, new Uint8Array(await response.arrayBuffer()));
}

/* --- answers ---------------------------------------------------------- */

function renderGroups(answer) {
  const ordered = answer.result
    .map((row, index) => ({ ...row, index, size: Math.abs(Number(row.exact)) || 0 }))
    .sort((a, b) => b.size - a.size);
  const widest = Math.max(...ordered.map((row) => row.size), 0);

  clear(nodes.groups);
  for (const row of ordered) {
    const button = add(nodes.groups, "button", null, "group");
    button.type = "button";
    add(button, "span", row.group ?? "(blank)", "name");
    const bar = add(button, "span", null, "bar");
    bar.style.width = widest > 0 ? `${Math.max(1, (row.size / widest) * 100)}%` : "1px";
    add(button, "span", row.value, "amount");
    add(button, "span", `${row.rows.toLocaleString()} rows`, "rows");
    button.dataset.index = row.index;
    button.onclick = () => showEvidence(row.index);
  }
  nodes.groups.hidden = false;
  nodes.total.hidden = true;
}

function renderAnswer(answer) {
  state.answer = answer;
  nodes.recorded.hidden = true;
  nodes.restated.textContent = answer.question;
  nodes.parsed.textContent = `${answer.parsed}\n${answer.call}`;
  paragraphs(nodes.method, answer.details);
  nodes.timing.textContent =
    `${answer.total_rows.toLocaleString()} rows read in ${answer.ms} ms, in this browser tab.` +
    (answer.big_integers
      ? " These totals are past the largest integer JavaScript can hold exactly, so they are printed as Python computed them."
      : "");

  if (answer.group_by === null) {
    nodes.total.textContent = answer.headline;
    nodes.total.hidden = false;
    nodes.groups.hidden = true;
  } else {
    renderGroups(answer);
  }

  nodes.answer.hidden = false;
  nodes.answer.removeAttribute("data-fresh");
  requestAnimationFrame(() => nodes.answer.setAttribute("data-fresh", ""));
  return showEvidence(answer.group_by === null ? null : 0);
}

async function showEvidence(groupIndex) {
  for (const button of nodes.groups.children) {
    button.setAttribute("aria-pressed", "false");
  }
  state.group = groupIndex;
  const evidence = await engine("evidence", { groupIndex });
  if (groupIndex !== null) {
    nodes.groups.querySelector(`[data-index="${groupIndex}"]`)?.setAttribute("aria-pressed", "true");
  }
  nodes.evidenceOf.textContent =
    evidence.group === null ? "this number" : `${evidence.group_by} = ${evidence.group}`;
  nodes.working.textContent = evidence.working ?? "";
  nodes.working.hidden = evidence.working === null;
  renderRows(nodes.evidence, state.table.columns, evidence.rows);
  nodes.evidenceCaption.textContent =
    evidence.rows.length < evidence.count
      ? `First ${evidence.rows.length} of ${evidence.count.toLocaleString()} rows used. Every one of the ${evidence.count.toLocaleString()} is in the calculation.`
      : `All ${evidence.count.toLocaleString()} rows used.`;
  nodes.evidenceCaption.textContent += " The # column is the row's position in the file.";
}

function renderRecorded(question) {
  const { answer, model, dataset } = state.recorded;
  nodes.answer.hidden = true;
  nodes.recordedIntro.textContent =
    `Tablebeam did not recognise “${question}” as one of the forms it computes over this table. ` +
    `In the desktop app a question like that goes to a model running on your own machine. This page ` +
    `runs no model, so here is a stored example of what comes back, using ${dataset} and ${model}.`;
  nodes.recordedQuestion.textContent = answer.question;
  paragraphs(nodes.recordedText, answer.text);
  nodes.recordedCoverage.textContent = answer.coverage;
  nodes.recordedSources.textContent = [
    ...answer.sources.map((source) => `${source.citation} · row ${source.row_number}\n${source.content}`),
    `Table profile given to the model\n${answer.profile}`,
  ].join("\n\n");
  nodes.recorded.hidden = false;
}

async function ask(question) {
  nodes.failure.hidden = true;
  nodes.submit.disabled = true;
  try {
    const answer = await engine("ask", { question });
    if (answer.kind === "needs_ai") renderRecorded(answer.question);
    else await renderAnswer(answer);
  } catch (error) {
    fail(error.message);
  } finally {
    nodes.submit.disabled = false;
  }
}

/* --- start ------------------------------------------------------------ */

nodes.download.onclick = async () => {
  const csv = await engine("rows_csv", { groupIndex: state.group });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
  link.download = "tablebeam-rows-used.csv";
  link.click();
  URL.revokeObjectURL(link.href);
};

nodes.form.onsubmit = (event) => {
  event.preventDefault();
  const question = nodes.question.value.trim();
  if (question) ask(question);
};

nodes.file.onchange = async () => {
  const file = nodes.file.files[0];
  if (!file) return;
  await openTable(
    { file: file.name, name: file.name, note: "Your file, read in this tab. It was never uploaded." },
    new Uint8Array(await file.arrayBuffer()),
  );
};

async function start() {
  const [catalog, recorded] = await Promise.all([
    fetch("/catalog.json").then((response) => response.json()),
    fetch("/recorded-answer.json").then((response) => response.json()),
  ]);
  state.catalog = catalog;
  state.recorded = recorded;

  for (const dataset of catalog) {
    const button = add(nodes.sources, "button", dataset.name);
    button.type = "button";
    button.dataset.file = dataset.file;
    button.setAttribute("aria-pressed", "false");
    button.onclick = () => openBundled(dataset);
  }
  nodes.credits.textContent =
    "Tables: " + catalog.map((dataset) => `${dataset.name} — ${dataset.credit}`).join(" · ");

  try {
    const versions = await ready;
    nodes.runtime.dataset.state = "done";
    nodes.runtime.textContent =
      `CPython ${versions.python} · pandas ${versions.pandas} · WebAssembly, in this tab`;
  } catch (error) {
    nodes.runtime.dataset.state = "done";
    nodes.runtime.textContent = `The Python runtime did not start: ${error.message}`;
    return;
  }
  await openBundled(catalog[0]);
}

start();
