"""Streamlit interface for the private spreadsheet analysis assistant."""

from __future__ import annotations

import os
import hashlib
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))

from model_selector_v2 import HardwareDetector, ModelRecommender, render_model_settings_ui


def get_imports() -> None:
    """Load heavier AI integrations only after the user selects a source."""

    global ChatOllama, answer_question, create_documents, get_retriever
    global load_client_data, profile_dataframe, DataValidationError
    global ollama_status, model_error_message
    if "answer_question" not in globals():
        from data_pipeline import DataValidationError, profile_dataframe
        from qa_service import answer_question
        from runtime import model_error_message, ollama_status
        from vector import create_documents, get_retriever, load_client_data
        from langchain_ollama import ChatOllama


def initialize_state() -> None:
    defaults: dict[str, Any] = {
        "messages": [],
        "retriever": None,
        "data_loaded": False,
        "current_data_source": None,
        "data_source_key": None,
        "upload_signature": None,
        "data_profile": None,
        "embedding_model": None,
        "llm_model": None,
        "process_last_message": False,
        "last_embedding_model": None,
        "temp_file_path": None,
        "force_reload": False,
        "demo_requested": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
    if os.getenv("START_WITH_DEMO") == "1" and not st.session_state.data_loaded:
        st.session_state.demo_requested = True

    if st.session_state.embedding_model is None:
        # Keep the default pair aligned with the launcher's deterministic model
        # setup. Users can still choose a hardware-specific pair in settings.
        st.session_state.embedding_model = os.getenv("EMBEDDING_MODEL", "mxbai-embed-large")
        st.session_state.llm_model = os.getenv("LLM_MODEL", os.getenv("OLLAMA_MODEL", "llama3.2"))
        st.session_state.last_embedding_model = st.session_state.embedding_model


def load_into_session(
    source: str,
    display_name: str,
    *,
    source_key: str | None = None,
    force_refresh: bool = False,
) -> None:
    get_imports()
    with st.spinner(f"Loading {display_name} and preparing local search…"):
        df = load_client_data(source)
        retriever = get_retriever(
            source,
            embedding_model=st.session_state.embedding_model,
            force_refresh=force_refresh,
        )
    st.session_state.retriever = retriever
    st.session_state.data_profile = profile_dataframe(df)
    st.session_state.data_loaded = True
    st.session_state.current_data_source = display_name
    st.session_state.data_source_key = source_key or source
    st.session_state.messages = []
    st.session_state.last_embedding_model = st.session_state.embedding_model
    st.success(f"Loaded {display_name}: {len(df):,} rows × {len(df.columns)} columns")


def render_answer(question: str, container: Any) -> str:
    """Render one grounded answer and its source records."""

    get_imports()
    try:
        llm = ChatOllama(
            model=st.session_state.llm_model,
            base_url=os.getenv("OLLAMA_HOST", "http://localhost:11434"),
            temperature=0,
        )
        result = answer_question(
            st.session_state.retriever,
            llm,
            question,
            limit=5,
            profile=st.session_state.data_profile,
        )
        container.write(result.answer)
        if result.sources:
            with container.expander(f"📄 Sources ({len(result.sources)})", expanded=False):
                for source in result.sources:
                    st.markdown(f"**{source.citation} · row {source.row_index}**")
                    st.code(source.content, language="text")
        st.session_state.messages.append({"role": "assistant", "content": result.answer})
        return result.answer
    except Exception as exc:
        message = model_error_message(st.session_state.llm_model, exc)
        container.error(message)
        with container.expander("Troubleshooting", expanded=False):
            container.markdown(
                "- Check that Ollama is running.\n"
                f"- Check that `{st.session_state.llm_model}` is installed.\n"
                "- If you changed the embedding model, reload the data."
            )
        return message


st.set_page_config(
    page_title="Spreadsheet Q&A Assistant",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
      .stApp { background: #0e1117; }
      section[data-testid="stSidebar"] { background: #171c28; border-right: 1px solid #2d3748; }
      .feature-card { background: #171c28; padding: 20px; border-radius: 10px; border: 1px solid #2d3748; }
      .status-badge { display: inline-flex; gap: 8px; align-items: center; background: rgba(72,187,120,.1); border: 1px solid #48bb78; padding: 8px 16px; border-radius: 20px; color: #8ee3ad; }
      .stButton > button { min-height: 2.6rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

initialize_state()

st.markdown(
    """
    <div style='text-align:center; padding:16px 0 28px'>
      <h1 style='color:#63b3ed; margin-bottom:8px'>📊 Spreadsheet Q&A Assistant</h1>
      <p style='color:#a0aec0; font-size:18px'>Ask grounded questions about a private CSV or Google Sheet.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown("### 🤖 Local AI status")
    try:
        get_imports()
        status = ollama_status()
        if status["available"]:
            st.success(f"Ollama connected · {len(status['models'])} model(s) installed")
        else:
            st.warning("Ollama is not reachable yet")
            st.caption(status["base_url"])
            st.code("ollama serve", language="bash")
    except Exception as exc:
        st.warning(f"AI dependencies are not ready: {exc}")

    st.divider()
    with st.expander("⚙️ Model settings", expanded=False):
        try:
            render_model_settings_ui(st)
        except Exception as exc:
            st.warning(f"Model settings unavailable: {exc}")

    st.divider()
    st.markdown("### 📁 Data source")
    if st.button("✨ Try the built-in demo", use_container_width=True):
        st.session_state.demo_requested = True

    if st.session_state.data_loaded and st.button("🗑️ Clear local cache", use_container_width=True):
        cache_path = Path(os.getenv("VECTOR_DB_PATH", "./chroma_db_clients"))
        if cache_path.exists():
            shutil.rmtree(cache_path)
        st.session_state.data_loaded = False
        st.session_state.retriever = None
        st.session_state.data_profile = None
        st.session_state.messages = []
        st.rerun()

    source_choice = st.radio(
        "Choose a source",
        ["📤 Upload CSV", "🔗 Google Sheets URL"],
        label_visibility="collapsed",
    )
    data_path = None

    if st.session_state.demo_requested:
        st.session_state.demo_requested = False
        demo_path = Path(__file__).parent.parent / "sample_data.csv"
        try:
            load_into_session(str(demo_path), "Built-in demo dataset", source_key="demo")
            st.session_state.temp_file_path = str(demo_path)
        except Exception as exc:
            st.error(str(exc))

    if source_choice == "📤 Upload CSV":
        uploaded_file = st.file_uploader(
            "Drop a CSV file here",
            type=["csv"],
            help="UTF-8 CSV files up to 100 MB; values are processed locally.",
        )
        if uploaded_file is not None:
            uploaded_bytes = uploaded_file.getvalue()
            upload_signature = hashlib.sha256(uploaded_bytes).hexdigest()
            if (
                st.session_state.data_source_key == uploaded_file.name
                and st.session_state.upload_signature == upload_signature
                and st.session_state.temp_file_path
                and Path(st.session_state.temp_file_path).is_file()
            ):
                data_path = st.session_state.temp_file_path
            else:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".csv", mode="wb") as tmp:
                    tmp.write(uploaded_bytes)
                    data_path = tmp.name
            if (
                st.session_state.data_source_key != uploaded_file.name
                or not st.session_state.data_loaded
                or st.session_state.last_embedding_model != st.session_state.embedding_model
                or st.session_state.upload_signature != upload_signature
            ):
                try:
                    st.session_state.temp_file_path = data_path
                    st.session_state.upload_signature = upload_signature
                    load_into_session(data_path, uploaded_file.name, source_key=uploaded_file.name)
                except Exception as exc:
                    st.error(str(exc))
    else:
        sheet_url = st.text_input(
            "Public Google Sheets URL",
            placeholder="https://docs.google.com/spreadsheets/d/…",
            help="The sheet must be publicly viewable; its CSV export is fetched directly.",
        ).strip()
        if sheet_url:
            data_path = sheet_url
            if st.session_state.data_source_key != sheet_url or not st.session_state.data_loaded:
                try:
                    load_into_session(sheet_url, "Google Sheet", source_key=sheet_url)
                except Exception as exc:
                    st.error(str(exc))

    if st.session_state.data_loaded and st.session_state.data_profile:
        profile = st.session_state.data_profile
        with st.expander("📊 Dataset profile", expanded=True):
            st.metric("Rows", f"{profile.row_count:,}")
            st.metric("Columns", profile.column_count)
            st.caption(f"{profile.memory_mb:.2f} MB in memory · {profile.duplicate_rows:,} duplicate rows")
            st.caption("Columns: " + ", ".join(profile.columns))
            for warning in profile.warnings:
                st.warning(warning)

    preview_path = data_path or st.session_state.temp_file_path
    if st.session_state.data_loaded and preview_path:
        with st.expander("Preview first 10 rows", expanded=False):
            try:
                get_imports()
                st.dataframe(load_client_data(preview_path).head(10), use_container_width=True, hide_index=True)
            except Exception as exc:
                st.info(f"Preview unavailable: {exc}")

    if st.session_state.force_reload and st.session_state.data_loaded:
        st.session_state.force_reload = False
        reload_source = st.session_state.data_source_key
        if reload_source and not reload_source.startswith("http"):
            reload_source = st.session_state.temp_file_path or reload_source
        if reload_source:
            try:
                load_into_session(
                    reload_source,
                    st.session_state.current_data_source or "data source",
                    source_key=st.session_state.data_source_key,
                    force_refresh=True,
                )
            except Exception as exc:
                st.error(f"Could not reload with the new embedding model: {exc}")

if st.session_state.data_loaded:
    st.markdown(
        f"<div class='status-badge'>● Loaded locally: {st.session_state.current_data_source}</div>",
        unsafe_allow_html=True,
    )
    st.markdown("#### 💡 Start with a question")
    quick_questions = [
        "What are the main patterns in this data?",
        "Summarize the key insights with sources.",
        "Which categories have the most records?",
        "What data is missing or inconsistent?",
        "Show the highest-value records.",
    ]
    quick_columns = st.columns(3)
    for index, question in enumerate(quick_questions):
        if quick_columns[index % 3].button(question, key=f"quick_{index}", use_container_width=True):
            st.session_state.messages.append({"role": "user", "content": question})
            st.session_state.process_last_message = True
            st.rerun()

    st.divider()
    chat_container = st.container()
    with chat_container:
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.write(message["content"])

    if st.session_state.process_last_message and st.session_state.messages:
        st.session_state.process_last_message = False
        last_message = st.session_state.messages[-1]
        if last_message["role"] == "user":
            with chat_container.chat_message("assistant") as assistant:
                with st.spinner("Analyzing local records…"):
                    render_answer(last_message["content"], assistant)

    if prompt := st.chat_input("Ask a question about your data", key="chat_input"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with chat_container.chat_message("user"):
            st.write(prompt)
        with chat_container.chat_message("assistant") as assistant:
            with st.spinner("Analyzing local records…"):
                render_answer(prompt, assistant)
else:
    columns = st.columns(3)
    cards = [
        ("🏠 Local by default", "CSV data, embeddings, and answers stay on this machine. Google Sheets is the explicit network path."),
        ("🔎 Grounded answers", "Answers include the retrieved source rows so you can verify what the model used."),
        ("📈 Profile first", "See row counts, types, missing values, duplicates, and a preview before asking questions."),
    ]
    for column, (title, body) in zip(columns, cards):
        with column:
            st.markdown(f"<div class='feature-card'><h3>{title}</h3><p>{body}</p></div>", unsafe_allow_html=True)
    st.info("Upload a CSV, connect a public Google Sheet, or click ‘Try the built-in demo’ in the sidebar to begin.")
