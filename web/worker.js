/* Runs Tablebeam's Python off the main thread.
 *
 * The modules under engine/ are byte-for-byte copies of the app's source, so
 * every number this worker reports comes from the code that ships in the app.
 */

import { loadPyodide } from "https://cdn.jsdelivr.net/pyodide/v314.0.7/full/pyodide.mjs";

const RUNTIME = "https://cdn.jsdelivr.net/pyodide/v314.0.7/full/";
const MODULES = [
  "answer_format.py",
  "data_pipeline.py",
  "question_actions.py",
  "table_analysis.py",
  "engine.py",
];

let engine = null;

function toPlain(result) {
  if (result && typeof result.toJs === "function") {
    const plain = result.toJs({ dict_converter: Object.fromEntries, create_pyproxies: false });
    result.destroy();
    return plain;
  }
  return result;
}

/* Python exceptions arrive with their traceback attached; the page only wants
 * the message the app itself would show. */
function message(error) {
  const text = String((error && error.message) || error).trim();
  const last = text.split("\n").filter(Boolean).pop() || "Something went wrong.";
  const named = /^[\w.]*(?:Error|Exception|Warning)(?:: (?<detail>.+))?$/.exec(last);
  return named?.groups?.detail ?? last;
}

async function boot() {
  postMessage({ type: "stage", stage: "runtime" });
  const pyodide = await loadPyodide({ indexURL: RUNTIME });

  postMessage({ type: "stage", stage: "pandas" });
  const sources = Promise.all(
    MODULES.map(async (name) => [name, await (await fetch("engine/" + name)).text()]),
  );
  await pyodide.loadPackage("pandas", { messageCallback: () => {} });

  postMessage({ type: "stage", stage: "engine" });
  pyodide.FS.mkdir("/tablebeam");
  for (const [name, text] of await sources) {
    pyodide.FS.writeFile("/tablebeam/" + name, text);
  }
  pyodide.runPython("import sys; sys.path.insert(0, '/tablebeam')");
  engine = pyodide.pyimport("engine");

  postMessage({
    type: "ready",
    python: pyodide.runPython("import platform; platform.python_version()"),
    pandas: pyodide.runPython("import pandas; pandas.__version__"),
  });
}

const calls = {
  load: ({ bytes, label }) => engine.load(bytes, label),
  ask: ({ question }) => engine.ask(question),
  evidence: ({ groupIndex }) => engine.evidence(groupIndex),
  rows_csv: ({ groupIndex }) => engine.rows_csv(groupIndex),
};

onmessage = ({ data }) => {
  const { id, call, args } = data;
  try {
    postMessage({ type: "result", id, call, value: toPlain(calls[call](args)) });
  } catch (error) {
    postMessage({ type: "failed", id, call, reason: message(error) });
  }
};

boot().catch((error) => postMessage({ type: "broken", reason: message(error) }));
