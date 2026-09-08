# Changelog

All notable changes to Tablebeam are documented here. The project follows
[Semantic Versioning](https://semver.org/).

## Unreleased

- Replace the dashboard and persistent setup sidebar with one path: open a table, ask a question, read one answer.
- Add conservative built-in question parsing, schema-based examples, and explicit optional AI routing.
- Open CSV uploads immediately, preserve the current table on failed replacement, and put Google Sheets and AI configuration in contextual controls.
- Keep exact aggregates, typed filters, grouped charts, safe CSV exports, and calculation/source details behind the simple answer view.
- Preserve previous answers, connection settings, large-integer precision, and clear table-scoped state on replacement.
- Validate raw CSV headers and records before pandas inference, improve exact-token retrieval, and handle malformed provider/API inputs.
- Apply the same bounded parser to Google Sheets and retain nullable integer precision in imports, profiles, source evidence, and displays.
- Show actual provider readiness from the selected server, keep remote controls on their host, and reject invalid server addresses before local actions.
- Keep chart values readable across positive and negative results and explain groups without values.
- Check every runtime dependency version before launch or upgrade, using the environment's own interpreter on macOS, Linux, and Windows.
- Add parser, rendering, and end-to-end Streamlit regression coverage alongside API and ingestion tests.

## 2.0.0 — 2026-07-15

- Add a provider control surface for LM Studio, Ollama, and compatible local servers.
- Add model discovery, selection, server startup, and explicit model-loading controls.
- Keep deterministic table profiling and row retrieval separate from generated answers.
- Add source-row citations, provider-independent tests, Docker support, and a health-checked API.
- Harden the launcher with bounded retries, clear diagnostics, and a Windows entry point.
