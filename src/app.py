"""Tablebeam web app: load a table, choose a local model server, ask questions."""

from __future__ import annotations

import os
from pathlib import Path

import streamlit as st

from assistant_core import LocalTable, OpenAICompatibleClient, ProviderError


DEMO_PATH = Path(__file__).parent.parent / "sample_data.csv"
PROVIDERS = {
    "LM Studio": "http://localhost:1234/v1",
    "Ollama": "http://localhost:11434/v1",
}


def setup_state() -> None:
    defaults = {
        "table": None,
        "messages": [],
        "queued_question": None,
        "demo_loaded": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def load_demo() -> None:
    st.session_state.table = LocalTable.from_source(str(DEMO_PATH))
    st.session_state.demo_loaded = True
    st.session_state.messages = []


def render_sources(sources: list[dict]) -> None:
    if not sources:
        return
    with st.expander(f"Sources ({len(sources)})", expanded=False):
        for source in sources:
            st.markdown(f"**{source['citation']} · row {source['row_number']}**")
            st.code(source["content"], language="text")


st.set_page_config(page_title="Tablebeam", page_icon="✦", layout="wide")
setup_state()

st.title("✦ Tablebeam")
st.caption("Ask your local model about a CSV or Google Sheet — with the rows behind every answer.")

with st.sidebar:
    st.header("1. Model")
    provider_name = st.radio("Provider", list(PROVIDERS), horizontal=True)
    default_url = os.getenv("LLM_BASE_URL", PROVIDERS[provider_name])
    base_url = st.text_input("Server URL", value=default_url, help="LM Studio: start its OpenAI-compatible server first.")
    model = st.text_input("Model", value=os.getenv("LLM_MODEL", "auto"), help="Use auto to select the first loaded model.")
    api_key = st.text_input("API key (usually blank)", value=os.getenv("LLM_API_KEY", ""), type="password")
    client = OpenAICompatibleClient(base_url=base_url, model=model, api_key=api_key, timeout=120)
    status = client.status()
    if status["ready"]:
        st.success(f"Connected · {len(status['models'])} model(s)")
        st.caption(", ".join(status["models"][:3]))
    else:
        st.warning("Local server not connected")
        st.caption("Start LM Studio's local server, or run `ollama serve`.")

    st.divider()
    st.header("2. Table")
    if st.button("Use demo data", use_container_width=True):
        try:
            load_demo()
        except Exception as exc:
            st.error(str(exc))

    data_kind = st.radio("Source", ["CSV file", "Google Sheet"], horizontal=True)
    uploaded = None
    sheet_url = ""
    if data_kind == "CSV file":
        uploaded = st.file_uploader("Choose a CSV", type=["csv"])
    else:
        sheet_url = st.text_input("Public Google Sheets URL", placeholder="https://docs.google.com/spreadsheets/d/…")

    if st.button("Load data", type="primary", use_container_width=True):
        try:
            if uploaded is not None:
                st.session_state.table = LocalTable.from_csv_bytes(uploaded.getvalue())
                st.session_state.demo_loaded = False
            elif sheet_url.strip():
                st.session_state.table = LocalTable.from_source(sheet_url.strip())
                st.session_state.demo_loaded = False
            else:
                st.error("Choose a CSV, enter a Google Sheet URL, or use the demo.")
            st.session_state.messages = []
        except Exception as exc:
            st.error(str(exc))

    if st.session_state.table is not None:
        profile = st.session_state.table.profile
        st.divider()
        st.metric("Rows", f"{profile.row_count:,}")
        st.metric("Columns", profile.column_count)
        st.caption("Columns: " + ", ".join(profile.columns))
        for warning in profile.warnings:
            st.warning(warning)
        with st.expander("Preview", expanded=False):
            st.dataframe(st.session_state.table.dataframe.head(10), use_container_width=True, hide_index=True)

if os.getenv("START_WITH_DEMO") == "1" and st.session_state.table is None:
    try:
        load_demo()
    except Exception as exc:
        st.error(str(exc))

table: LocalTable | None = st.session_state.table
if table is None:
    st.info("Load a CSV, connect a public Google Sheet, or click Use demo data in the sidebar.")
    st.markdown("**LM Studio quick start**: load a model → Developer → Start Server → leave the URL at `http://localhost:1234/v1`. Then ask a question.")
else:
    label = "Built-in demo" if st.session_state.demo_loaded else "Loaded dataset"
    st.success(f"{label}: {table.profile.row_count:,} rows ready")
    st.subheader("Ask a question")

    quick_questions = [
        "Summarize the key insights.",
        "What are the main patterns?",
        "What data is missing?",
        "Show the highest-value records.",
    ]
    quick_columns = st.columns(4)
    for index, question in enumerate(quick_questions):
        if quick_columns[index].button(question, key=f"quick_{index}", use_container_width=True):
            st.session_state.queued_question = question
            st.rerun()

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])
            if message["role"] == "assistant":
                render_sources(message.get("sources", []))

    question = st.session_state.pop("queued_question", None) or st.chat_input("Ask about your data")
    if question:
        st.session_state.messages.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.write(question)
        with st.chat_message("assistant"):
            with st.spinner("Asking the local model…"):
                try:
                    answer, sources = client.ask(question, table)
                    source_dicts = [source.as_dict() for source in sources]
                    st.write(answer)
                    render_sources(source_dicts)
                    st.session_state.messages.append({"role": "assistant", "content": answer, "sources": source_dicts})
                except ProviderError as exc:
                    st.error(str(exc))
