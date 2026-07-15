"""Tablebeam: an evidence-first local workspace for asking questions of tables."""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import streamlit as st

from assistant_core import LocalTable, OpenAICompatibleClient, ProviderError
from provider_control import ProviderController, ProviderState


ROOT = Path(__file__).parent.parent
DEMO_PATH = ROOT / "sample_data.csv"
BANNER_PATH = ROOT / "assets" / "tablebeam-banner.jpg"
PROVIDERS = {
    "LM Studio": "http://localhost:1234/v1",
    "Ollama": "http://localhost:11434/v1",
}


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        :root {
            --beam-paper: #f4f6f2;
            --beam-panel: #ffffff;
            --beam-ink: #15252c;
            --beam-muted: #64747a;
            --beam-line: #dbe4df;
            --beam-teal: #087f86;
            --beam-coral: #e6875f;
        }
        .stApp {
            background: var(--beam-paper);
            color: var(--beam-ink);
        }
        .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6,
        .stApp p, .stApp label, .stApp [data-testid="stMarkdownContainer"] {
            color: var(--beam-ink);
        }
        .stApp [data-testid="stCaptionContainer"] p,
        .stApp [data-testid="stWidgetLabel"] p,
        .stApp [data-testid="stMarkdownContainer"] small {
            color: var(--beam-muted);
        }
        .block-container { max-width: 1240px; padding-top: 4rem; padding-bottom: 4rem; }
        [data-testid="stSidebar"] {
            background: #152b31;
            border-right: 0;
        }
        [data-testid="stSidebar"] .block-container { padding-top: 2rem; }
        [data-testid="stSidebar"] h3, [data-testid="stSidebar"] p, [data-testid="stSidebar"] label { color: #eaf4f0 !important; }
        [data-testid="stSidebar"] [data-testid="stRadio"] label p { color: #eaf4f0 !important; }
        [data-testid="stSidebar"] [data-testid="stCaptionContainer"] p { color: #a9c1bd !important; }
        [data-testid="stSidebar"] input { background: #f7faf8 !important; }
        .beam-wordmark { letter-spacing: .16em; font-size: .72rem; font-weight: 800; color: #88e0d4; }
        .beam-eyebrow { color: var(--beam-teal); font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: .66rem; letter-spacing: .14em; font-weight: 800; }
        .beam-hero-title { font-family: "Iowan Old Style", "Palatino Linotype", Georgia, serif; font-size: clamp(2.7rem, 5vw, 4.7rem); line-height: .98; letter-spacing: -.05em; margin: .65rem 0 1rem; color: var(--beam-ink); }
        .beam-hero-title em { color: var(--beam-teal); font-style: normal; }
        .beam-hero-copy { color: #51636a; font-size: 1.03rem; line-height: 1.6; max-width: 32rem; }
        .beam-panel { background: var(--beam-panel); border: 1px solid var(--beam-line); border-radius: 16px; padding: 1.1rem 1.2rem; box-shadow: 0 10px 30px rgba(27, 54, 54, .05); }
        .beam-signal { border-left: 3px solid var(--beam-coral); padding: .2rem 0 .2rem .9rem; color: #53666b; line-height: 1.45; }
        .beam-signal strong { color: var(--beam-ink); }
        .beam-kicker { color: var(--beam-muted); font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: .65rem; letter-spacing: .13em; text-transform: uppercase; }
        .beam-section-title { font-family: "Iowan Old Style", "Palatino Linotype", Georgia, serif; font-size: 2.15rem; color: var(--beam-ink); letter-spacing: -.04em; margin: .15rem 0 .25rem; }
        .beam-ready { display: inline-block; color: var(--beam-teal); border: 1px solid #a9d8d0; background: #e7f5f1; border-radius: 999px; padding: .25rem .6rem; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: .65rem; letter-spacing: .08em; text-transform: uppercase; }
        div[data-testid="stMetric"] { background: var(--beam-panel); border: 1px solid var(--beam-line); border-radius: 13px; padding: .8rem .95rem; box-shadow: 0 6px 20px rgba(27, 54, 54, .04); }
        div[data-testid="stMetricLabel"] { color: var(--beam-muted); }
        div[data-testid="stMetricValue"] { color: var(--beam-ink); }
        .stButton > button { border-radius: 9px; border: 1px solid #cddbd5; background: #ffffff; color: var(--beam-ink); transition: all .18s ease; }
        .stButton > button p { color: inherit !important; }
        .stButton > button:hover { border-color: var(--beam-teal); color: var(--beam-teal); transform: translateY(-1px); }
        button[kind="primary"] { background: var(--beam-teal) !important; color: #ffffff !important; border-color: var(--beam-teal) !important; font-weight: 700; }
        button[kind="primary"]:hover { background: #096b70 !important; color: #ffffff !important; }
        .stChatInput > div { border-color: #a9d8d0 !important; background: #ffffff !important; }
        .stApp input, .stApp textarea { color: var(--beam-ink) !important; }
        [data-testid="stRadio"] label p { color: inherit !important; }
        [data-testid="stExpander"] { border-color: var(--beam-line); background: rgba(255, 255, 255, .65); }
        [data-testid="stTabs"] button { color: var(--beam-muted); }
        [data-testid="stTabs"] button[aria-selected="true"] { color: var(--beam-teal); }
        </style>
        """,
        unsafe_allow_html=True,
    )


def setup_state() -> None:
    configured_provider = os.getenv("LLM_PROVIDER", "LM Studio")
    configured_url = os.getenv("LLM_BASE_URL") or PROVIDERS.get(configured_provider, PROVIDERS["LM Studio"])
    defaults = {
        "table": None,
        "table_label": None,
        "messages": [],
        "queued_question": None,
        "demo_loaded": False,
        "provider_name": configured_provider if configured_provider in PROVIDERS else "LM Studio",
        "provider_seen": None,
        "server_url": configured_url,
        "model_name": os.getenv("LLM_MODEL", "auto"),
        "model_select": os.getenv("LLM_MODEL", "auto"),
        "model_custom": "",
        "api_key": os.getenv("LLM_API_KEY", ""),
        "auto_start_attempted": False,
        "provider_notice": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def set_table(table: LocalTable, label: str, *, demo: bool = False) -> None:
    st.session_state.table = table
    st.session_state.table_label = label
    st.session_state.demo_loaded = demo
    st.session_state.messages = []


def load_demo() -> None:
    set_table(LocalTable.from_source(str(DEMO_PATH)), "sample_data.csv", demo=True)


def clear_table() -> None:
    st.session_state.table = None
    st.session_state.table_label = None
    st.session_state.demo_loaded = False
    st.session_state.messages = []


@st.cache_data(ttl=4, show_spinner=False)
def get_provider_state(provider: str, base_url: str, api_key: str) -> ProviderState:
    return ProviderController(provider, base_url, api_key=api_key).probe()


def render_sources(sources: list[dict]) -> None:
    if not sources:
        return
    with st.expander(f"Evidence · {len(sources)} retrieved rows", expanded=False):
        st.caption("These are the exact rows sent to the local model.")
        for source in sources:
            st.markdown(f"**{source['citation']} · row {source['row_number']}**")
            st.code(source["content"], language="text")


def render_sidebar() -> tuple[OpenAICompatibleClient, ProviderState]:
    with st.sidebar:
        st.markdown('<div class="beam-wordmark">✦ TABLEBEAM</div>', unsafe_allow_html=True)
        st.caption("Local table intelligence")

        st.markdown("### Model")
        provider_name = st.radio("Provider", list(PROVIDERS), horizontal=True, key="provider_name", label_visibility="collapsed")
        if st.session_state.provider_seen != provider_name:
            st.session_state.server_url = PROVIDERS[provider_name]
            st.session_state.model_name = "auto"
            st.session_state.model_select = "auto"
            st.session_state.model_custom = ""
            st.session_state.provider_seen = provider_name
        st.text_input("Server URL", key="server_url", help="LM Studio defaults to http://localhost:1234/v1")
        st.text_input("API key", key="api_key", type="password", help="Usually blank for LM Studio and Ollama.")

        controller = ProviderController(
            provider_name,
            st.session_state.server_url,
            api_key=st.session_state.api_key,
        )
        state = get_provider_state(provider_name, st.session_state.server_url, st.session_state.api_key)

        auto_start = os.getenv("AUTO_START_PROVIDER", os.getenv("AUTO_START_MODEL", "0")) == "1"
        if auto_start and not st.session_state.auto_start_attempted:
            st.session_state.auto_start_attempted = True
            if not state.server_online:
                result = controller.start_server()
                st.session_state.provider_notice = result.output or result.error
                get_provider_state.clear()
                state = controller.probe()

        if state.ready:
            st.success(f"Ready · {len(state.loaded_models)} loaded")
        elif state.server_online:
            st.warning("Server online · no model loaded")
        else:
            st.error("Model server offline")
        st.caption(state.message)

        start_col, refresh_col = st.columns(2)
        with start_col:
            if st.button("Start server", use_container_width=True, key="start_provider"):
                result = controller.start_server()
                st.session_state.provider_notice = result.output or result.error
                get_provider_state.clear()
                st.rerun()
        with refresh_col:
            if st.button("Refresh", use_container_width=True, key="refresh_provider"):
                get_provider_state.clear()
                st.rerun()

        model_options = ["auto"] + [model.model_id for model in state.models if model.model_id != "auto"]
        custom_option = "Custom model ID…"
        if st.session_state.model_name not in model_options and st.session_state.model_name != "auto":
            st.session_state.model_select = custom_option
            st.session_state.model_custom = st.session_state.model_name
        elif st.session_state.model_select not in model_options and st.session_state.model_select != custom_option:
            st.session_state.model_select = "auto"
        selection = st.selectbox("Model", model_options + [custom_option], key="model_select")
        if selection == custom_option:
            st.text_input("Model ID", key="model_custom", placeholder="e.g. llama3.2:3b")
            st.session_state.model_name = st.session_state.model_custom.strip() or "auto"
        else:
            st.session_state.model_name = selection

        if state.models:
            loaded = ", ".join(model.model_id for model in state.loaded_models[:2])
            installed = ", ".join(model.model_id for model in state.models[:3])
            st.caption(f"Loaded: {loaded or 'none'}")
            st.caption(f"Available: {installed}")
        if st.session_state.model_name != "auto":
            job = controller.model_job(st.session_state.model_name)
            if job and job["running"]:
                st.info("Model job running… refresh in a moment.")
            action = "Pull / load model" if provider_name == "Ollama" else "Load model into memory"
            if st.button(action, use_container_width=True, key="load_provider_model"):
                result = controller.load_model(st.session_state.model_name)
                st.session_state.provider_notice = result.output or result.error
                get_provider_state.clear()
                st.rerun()
        if st.session_state.provider_notice:
            st.caption(st.session_state.provider_notice)

        st.divider()
        st.markdown("### Table")
        if st.button("Open demo table", use_container_width=True):
            try:
                load_demo()
                st.rerun()
            except Exception as exc:
                st.error(str(exc))

        data_kind = st.radio("Source", ["CSV file", "Google Sheet"], horizontal=True, label_visibility="collapsed")
        uploaded = None
        sheet_url = ""
        if data_kind == "CSV file":
            uploaded = st.file_uploader("Upload a CSV", type=["csv"], label_visibility="collapsed")
        else:
            sheet_url = st.text_input("Public Google Sheets URL", placeholder="Paste a public sheet URL")

        if st.button("Load table", type="primary", use_container_width=True):
            try:
                if uploaded is not None:
                    set_table(LocalTable.from_csv_bytes(uploaded.getvalue()), uploaded.name)
                    st.rerun()
                elif sheet_url.strip():
                    set_table(LocalTable.from_source(sheet_url.strip()), "Google Sheet")
                    st.rerun()
                else:
                    st.error("Choose a CSV, paste a sheet URL, or open the demo table.")
            except Exception as exc:
                st.error(str(exc))

        table: LocalTable | None = st.session_state.table
        if table is not None:
            st.divider()
            st.markdown('<div class="beam-kicker">Loaded table</div>', unsafe_allow_html=True)
            st.markdown(f"**{st.session_state.table_label or 'Table'}**")
            st.caption(f"{table.profile.row_count:,} rows · {table.profile.column_count} columns")
            if st.button("Clear table", use_container_width=True):
                clear_table()
                st.rerun()

    client = OpenAICompatibleClient(
        base_url=st.session_state.server_url,
        model=st.session_state.model_name,
        api_key=st.session_state.api_key,
        timeout=120,
    )
    return client, state


def render_landing(status: dict) -> None:
    left, right = st.columns([1.05, 0.95], gap="large")
    with left:
        st.markdown('<div class="beam-eyebrow">LOCAL TABLE INTELLIGENCE · 01</div>', unsafe_allow_html=True)
        st.markdown('<div class="beam-hero-title">Your data,<br><em>without the detour.</em></div>', unsafe_allow_html=True)
        st.markdown(
            '<p class="beam-hero-copy">Drop in a table. Ask a sharp question. Get a concise answer with the exact rows behind it — all on your machine.</p>',
            unsafe_allow_html=True,
        )
        if st.button("Open the demo table", type="primary", key="landing_demo"):
            try:
                load_demo()
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
        if status.ready:
            st.markdown('<div class="beam-signal"><strong>Model signal is clear.</strong><br>Your local endpoint is ready for questions.</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="beam-signal"><strong>One small step first.</strong><br>Start LM Studio’s local server, then open the demo table.</div>', unsafe_allow_html=True)
    with right:
        if BANNER_PATH.exists():
            st.image(str(BANNER_PATH), use_container_width=True)
        st.markdown(
            '<div class="beam-panel"><div class="beam-kicker">The Tablebeam loop</div><p style="margin:.7rem 0 0;color:#51636a;line-height:1.55">Validate locally → retrieve the signal → ask your model → inspect the evidence.</p></div>',
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<div class="beam-eyebrow">START SIMPLE · 02</div>', unsafe_allow_html=True)
    st.markdown('<div class="beam-section-title">A clear path from table to signal.</div>', unsafe_allow_html=True)
    cards = st.columns(3)
    for card, number, title, copy in zip(
        cards,
        ["01", "02", "03"],
        ["Bring a table", "Ask naturally", "See the proof"],
        ["CSV and public Google Sheets are supported.", "LM Studio is the default. Ollama is one flag away.", "Every answer keeps its retrieved rows one click away."],
    ):
        with card:
            st.markdown(f'<div class="beam-panel"><div class="beam-eyebrow">{number}</div><h4 style="margin:.7rem 0 .35rem;color:#15252c">{title}</h4><p style="margin:0;color:#64747a;line-height:1.5">{copy}</p></div>', unsafe_allow_html=True)


def render_explore(table: LocalTable) -> None:
    profile = table.profile
    total_cells = profile.row_count * profile.column_count
    missing_cells = sum(profile.missing_values.values())
    completeness = 100 if not total_cells else (1 - missing_cells / total_cells) * 100

    st.markdown('<div class="beam-kicker">TABLE PROFILE</div>', unsafe_allow_html=True)
    st.markdown('<div class="beam-section-title">Know the shape before you ask.</div>', unsafe_allow_html=True)
    metrics = st.columns(4)
    metrics[0].metric("Rows", f"{profile.row_count:,}")
    metrics[1].metric("Columns", profile.column_count)
    metrics[2].metric("Completeness", f"{completeness:.1f}%")
    metrics[3].metric("Duplicate rows", f"{profile.duplicate_rows:,}")

    overview = pd.DataFrame(
        {
            "column": profile.columns,
            "type": [str(table.dataframe[column].dtype) for column in profile.columns],
            "missing": [profile.missing_values[column] for column in profile.columns],
        }
    )
    st.markdown("#### Column map")
    st.dataframe(overview, use_container_width=True, hide_index=True)

    numeric = table.numeric_summary()
    if not numeric.empty:
        st.markdown("#### Numeric signal")
        st.caption("These aggregates are computed locally and included as profile context for the model.")
        st.dataframe(numeric, use_container_width=True, hide_index=True)

    st.markdown("#### Preview")
    st.dataframe(table.dataframe.head(25), use_container_width=True, hide_index=True)
    if profile.warnings:
        with st.expander(f"Data quality notes · {len(profile.warnings)}", expanded=False):
            for warning in profile.warnings:
                st.warning(warning)
    else:
        st.caption("No data-quality warnings detected.")


def render_workspace(table: LocalTable, client: OpenAICompatibleClient, status: dict) -> None:
    profile = table.profile
    label = st.session_state.table_label or "Loaded table"
    header_left, header_right = st.columns([0.8, 0.2])
    with header_left:
        st.markdown('<div class="beam-ready">Table ready</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="beam-section-title">{label}</div>', unsafe_allow_html=True)
        st.caption(f"{profile.row_count:,} rows · {profile.column_count} columns · loaded locally")
    with header_right:
        st.metric("Signal", "Ready" if status.ready else ("Online" if status.server_online else "Offline"))

    ask_tab, explore_tab = st.tabs(["Ask", "Explore"])
    with ask_tab:
        st.markdown('<div class="beam-kicker">CONVERSATION</div>', unsafe_allow_html=True)
        st.markdown('<div class="beam-section-title">What do you want to know?</div>', unsafe_allow_html=True)
        st.caption("Ask for a summary, a pattern, a follow-up, or a specific record. Tablebeam keeps the evidence close.")

        quick_questions = [
            "Give me a concise executive summary.",
            "Which records need attention?",
            "What are the largest values?",
            "What should I investigate next?",
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

        question = st.session_state.pop("queued_question", None) or st.chat_input("Ask about your table…")
        if question and question.strip():
            clean_question = question.strip()
            st.session_state.messages.append({"role": "user", "content": clean_question})
            with st.chat_message("user"):
                st.write(clean_question)
            with st.chat_message("assistant"):
                with st.spinner("Following the beam…"):
                    try:
                        answer, sources = client.ask(clean_question, table)
                        source_dicts = [source.as_dict() for source in sources]
                        st.write(answer)
                        render_sources(source_dicts)
                        st.session_state.messages.append({"role": "assistant", "content": answer, "sources": source_dicts})
                    except ProviderError as exc:
                        st.error(str(exc))

    with explore_tab:
        render_explore(table)


st.set_page_config(page_title="Tablebeam", page_icon="✦", layout="wide")
setup_state()
inject_styles()
client, status = render_sidebar()

if os.getenv("START_WITH_DEMO") == "1" and st.session_state.table is None:
    try:
        load_demo()
    except Exception as exc:
        st.error(str(exc))

if st.session_state.table is None:
    render_landing(status)
else:
    render_workspace(st.session_state.table, client, status)
