"""Tablebeam: an evidence-first local workspace for asking questions of tables."""

from __future__ import annotations

import base64
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
    """Give the Streamlit primitives a deliberate signal-desk visual system."""

    st.markdown(
        """
        <style>
        :root {
            --tb-paper: #f3f0e8;
            --tb-white: #fffdf8;
            --tb-ink: #111315;
            --tb-muted: #5b605f;
            --tb-line: rgba(17, 19, 21, .2);
            --tb-blue: #2d43ff;
            --tb-lime: #d7f25b;
            --tb-orange: #ff704d;
        }
        .stApp { background: var(--tb-paper); color: var(--tb-ink); }
        .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6,
        .stApp p, .stApp label, .stApp [data-testid="stMarkdownContainer"] { color: var(--tb-ink); }
        .stApp [data-testid="stCaptionContainer"] p,
        .stApp [data-testid="stWidgetLabel"] p,
        .stApp [data-testid="stMarkdownContainer"] small { color: var(--tb-muted); }
        .block-container { max-width: 1360px; padding: 1.35rem 3.2rem 5rem; }
        [data-testid="stSidebar"], [data-testid="collapsedControl"] { display: none; }
        [data-testid="stHeader"] { background: transparent; }
        [data-testid="stDecoration"] { background: var(--tb-blue); height: 4px; }
        [data-testid="stAppDeployButton"] { display: none; }
        #MainMenu { visibility: hidden; }
        [data-testid="stToolbar"] { opacity: .45; }
        .tb-masthead { display: flex; align-items: center; justify-content: space-between; gap: 1rem; border-bottom: 2px solid var(--tb-ink); padding: .45rem 0 .9rem; }
        .tb-brand { display: flex; align-items: center; gap: .7rem; }
        .tb-mark { display: grid; place-items: center; width: 2.15rem; height: 2.15rem; background: var(--tb-blue); color: var(--tb-lime); font-size: 1.3rem; transform: rotate(45deg); }
        .tb-mark span { transform: rotate(-45deg); }
        .tb-brand-name { font-size: .88rem; letter-spacing: .18em; font-weight: 900; line-height: 1; }
        .tb-brand-sub { display: block; margin-top: .35rem; color: var(--tb-muted); font: 600 .58rem/1 ui-monospace, SFMono-Regular, Menlo, monospace; letter-spacing: .14em; }
        .tb-masthead-center { color: var(--tb-muted); font: 700 .64rem/1 ui-monospace, SFMono-Regular, Menlo, monospace; letter-spacing: .18em; }
        .tb-live { display: flex; align-items: center; gap: .5rem; font: 800 .64rem/1 ui-monospace, SFMono-Regular, Menlo, monospace; letter-spacing: .08em; }
        .tb-live-dot { width: .55rem; height: .55rem; border-radius: 50%; background: var(--tb-orange); box-shadow: 0 0 0 4px rgba(255,112,77,.16); }
        .tb-live-dot.ready { background: #2eae76; box-shadow: 0 0 0 4px rgba(46,174,118,.16); }
        .tb-kicker { color: var(--tb-blue); font: 900 .66rem/1 ui-monospace, SFMono-Regular, Menlo, monospace; letter-spacing: .16em; text-transform: uppercase; }
        .tb-hero-title { max-width: 10ch; margin: .85rem 0 1.1rem; color: var(--tb-ink); font: 900 clamp(4.2rem, 9vw, 8.8rem)/.82 "Arial Narrow", "Avenir Next Condensed", "Helvetica Neue", sans-serif; letter-spacing: -.095em; text-transform: uppercase; }
        .tb-hero-title em { color: var(--tb-blue); font-style: normal; }
        .tb-hero-copy { max-width: 31rem; color: var(--tb-muted); font-size: 1.05rem; line-height: 1.55; }
        .tb-hero-note { border-left: 4px solid var(--tb-orange); margin-top: 2rem; padding: .2rem 0 .25rem 1rem; font-size: .9rem; line-height: 1.45; }
        .tb-visual { position: relative; overflow: hidden; min-height: 27rem; background: var(--tb-ink); border: 2px solid var(--tb-ink); box-shadow: 12px 12px 0 var(--tb-blue); }
        .tb-visual img { width: 100%; height: 100%; min-height: 27rem; object-fit: cover; opacity: .78; mix-blend-mode: screen; filter: saturate(1.35) contrast(1.2); }
        .tb-visual:before { content: ""; position: absolute; inset: 0; z-index: 1; background: linear-gradient(135deg, rgba(45,67,255,.5), transparent 42%, rgba(215,242,91,.22)); mix-blend-mode: screen; }
        .tb-visual-grid { position: absolute; inset: 0; z-index: 2; background-image: linear-gradient(rgba(255,255,255,.13) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.13) 1px, transparent 1px); background-size: 2.2rem 2.2rem; mask-image: linear-gradient(to bottom, rgba(0,0,0,.95), transparent 80%); }
        .tb-visual-label { position: absolute; z-index: 3; left: 1.25rem; bottom: 1.15rem; color: var(--tb-lime); font: 800 .68rem/1.3 ui-monospace, SFMono-Regular, Menlo, monospace; letter-spacing: .12em; }
        .tb-loop { display: grid; grid-template-columns: repeat(3, 1fr); border-top: 2px solid var(--tb-ink); border-bottom: 2px solid var(--tb-ink); margin-top: 4rem; }
        .tb-loop-step { min-height: 7rem; padding: 1.1rem 1.2rem 1rem 0; border-right: 1px solid var(--tb-line); }
        .tb-loop-step + .tb-loop-step { padding-left: 1.2rem; }
        .tb-loop-step:last-child { border-right: 0; }
        .tb-loop-number { color: var(--tb-orange); font: 900 .68rem/1 ui-monospace, SFMono-Regular, Menlo, monospace; }
        .tb-loop-title { margin: .75rem 0 .3rem; font-size: 1.15rem; font-weight: 850; letter-spacing: -.04em; }
        .tb-loop-copy { color: var(--tb-muted); font-size: .85rem; line-height: 1.4; }
        [data-testid="stExpander"] { border: 2px solid var(--tb-ink); border-radius: 0; background: var(--tb-ink); box-shadow: 7px 7px 0 var(--tb-lime); margin: 1.5rem 0 1.5rem; overflow: hidden; }
        [data-testid="stExpander"] details:not([open]) { height: 3.1rem; overflow: hidden; }
        [data-testid="stExpander"] summary p { color: var(--tb-lime) !important; font: 900 .7rem/1 ui-monospace, SFMono-Regular, Menlo, monospace; letter-spacing: .14em; text-transform: uppercase; }
        [data-testid="stExpander"] [data-testid="stWidgetLabel"] p,
        [data-testid="stExpander"] [data-testid="stCaptionContainer"] p,
        [data-testid="stExpander"] [data-testid="stMarkdownContainer"] p { color: #f4f2ea !important; }
        [data-testid="stExpander"] [data-testid="stRadio"] label p { color: #f4f2ea !important; }
        [data-testid="stExpander"] [data-testid="stWidgetLabel"] p { font-size: .73rem; font-weight: 800; letter-spacing: .04em; }
        [data-testid="stExpander"] input, [data-testid="stExpander"] textarea,
        [data-testid="stExpander"] [data-baseweb="select"] > div { background: #fffdf8 !important; color: var(--tb-ink) !important; border-color: rgba(255,255,255,.35) !important; border-radius: 0 !important; }
        [data-testid="stExpander"] [data-testid="stAlert"] { border-radius: 0; }
        [data-testid="stExpander"] .stButton > button { background: transparent; border-color: rgba(255,255,255,.5); color: #fffdf8; border-radius: 0; }
        [data-testid="stExpander"] .stButton > button:hover { background: var(--tb-lime); color: var(--tb-ink); border-color: var(--tb-lime); }
        .tb-deck-label { color: var(--tb-lime); font: 800 .63rem/1 ui-monospace, SFMono-Regular, Menlo, monospace; letter-spacing: .15em; text-transform: uppercase; border-bottom: 1px solid rgba(255,255,255,.24); padding-bottom: .55rem; margin: .4rem 0 1rem; }
        .tb-status { display: flex; align-items: center; gap: .55rem; min-height: 2.65rem; padding: .65rem .8rem; background: rgba(215,242,91,.12); border: 1px solid rgba(215,242,91,.45); color: var(--tb-lime); font: 800 .7rem/1.3 ui-monospace, SFMono-Regular, Menlo, monospace; letter-spacing: .04em; }
        .tb-status.offline { background: rgba(255,112,77,.12); border-color: rgba(255,112,77,.5); color: #ff9d84; }
        .tb-status-dot { width: .5rem; height: .5rem; flex: 0 0 auto; border-radius: 50%; background: currentColor; }
        .tb-workspace-head { display: flex; align-items: flex-end; justify-content: space-between; gap: 2rem; border-bottom: 2px solid var(--tb-ink); padding-bottom: 1.2rem; }
        .tb-workspace-title { margin: .65rem 0 .2rem; font: 900 clamp(2.5rem, 5vw, 5rem)/.88 "Arial Narrow", "Avenir Next Condensed", "Helvetica Neue", sans-serif; letter-spacing: -.08em; text-transform: uppercase; }
        .tb-workspace-meta { color: var(--tb-muted); font: 600 .72rem/1.4 ui-monospace, SFMono-Regular, Menlo, monospace; letter-spacing: .04em; }
        .tb-signal-badge { min-width: 8.2rem; padding: .8rem; background: var(--tb-blue); color: #fff; text-align: right; }
        .tb-signal-badge small { display: block; color: var(--tb-lime); font: 800 .59rem/1 ui-monospace, SFMono-Regular, Menlo, monospace; letter-spacing: .1em; }
        .tb-signal-badge strong { display: block; margin-top: .45rem; font-size: 1.25rem; letter-spacing: -.04em; }
        .tb-section-title { margin: .6rem 0 .25rem; font: 900 clamp(2.4rem, 5vw, 5.4rem)/.86 "Arial Narrow", "Avenir Next Condensed", "Helvetica Neue", sans-serif; letter-spacing: -.08em; text-transform: uppercase; }
        .tb-conversation-label { color: var(--tb-blue); font: 900 .65rem/1 ui-monospace, SFMono-Regular, Menlo, monospace; letter-spacing: .15em; }
        .tb-proof { border-left: 4px solid var(--tb-orange); padding: .2rem 0 .2rem 1rem; color: var(--tb-muted); font-size: .88rem; line-height: 1.5; }
        div[data-testid="stMetric"] { background: var(--tb-white); border: 2px solid var(--tb-ink); border-radius: 0; padding: .85rem 1rem; box-shadow: 5px 5px 0 var(--tb-lime); }
        div[data-testid="stMetricLabel"] { color: var(--tb-muted); font: 800 .65rem/1 ui-monospace, SFMono-Regular, Menlo, monospace; letter-spacing: .08em; text-transform: uppercase; }
        div[data-testid="stMetricValue"] { color: var(--tb-ink); font-weight: 900; letter-spacing: -.06em; }
        .stButton > button { min-height: 2.6rem; border: 2px solid var(--tb-ink); border-radius: 0; background: var(--tb-white); color: var(--tb-ink); font-weight: 800; transition: transform .16s ease, background .16s ease, box-shadow .16s ease; }
        .stButton > button p { color: inherit !important; }
        .stButton > button:hover { background: var(--tb-lime); border-color: var(--tb-ink); color: var(--tb-ink); transform: translate(-2px, -2px); box-shadow: 4px 4px 0 var(--tb-ink); }
        button[kind="primary"] { background: var(--tb-blue) !important; color: #ffffff !important; border-color: var(--tb-blue) !important; }
        button[kind="primary"]:hover { background: var(--tb-orange) !important; border-color: var(--tb-orange) !important; color: var(--tb-ink) !important; }
        .stChatInput > div { border: 2px solid var(--tb-ink) !important; border-radius: 0 !important; background: var(--tb-white) !important; }
        .stApp input, .stApp textarea { color: var(--tb-ink) !important; border-radius: 0 !important; }
        [data-testid="stRadio"] label p { color: inherit !important; }
        [data-testid="stTabs"] { border-bottom: 2px solid var(--tb-ink); }
        [data-testid="stTabs"] button { color: var(--tb-muted); font: 800 .72rem/1 ui-monospace, SFMono-Regular, Menlo, monospace; letter-spacing: .08em; text-transform: uppercase; }
        [data-testid="stTabs"] button[aria-selected="true"] { color: var(--tb-blue); }
        [data-testid="stDataFrame"] { border: 2px solid var(--tb-ink); }
        @media (max-width: 900px) {
            .block-container { padding: 1rem 1.1rem 3rem; }
            .tb-masthead-center { display: none; }
            .tb-hero-title { max-width: 8ch; font-size: clamp(3.7rem, 16vw, 6.5rem); }
            .tb-visual { min-height: 18rem; margin-top: 2rem; box-shadow: 7px 7px 0 var(--tb-blue); }
            .tb-visual img { min-height: 18rem; }
            .tb-loop { grid-template-columns: 1fr; }
            .tb-loop-step, .tb-loop-step + .tb-loop-step { border-right: 0; border-bottom: 1px solid var(--tb-line); padding: 1rem 0; }
            .tb-loop-step:last-child { border-bottom: 0; }
            .tb-workspace-head { align-items: flex-start; flex-direction: column; gap: 1rem; }
        }
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


def render_masthead(status: ProviderState) -> None:
    state_label = "READY" if status.ready else ("ONLINE" if status.server_online else "OFFLINE")
    state_class = "ready" if status.server_online else ""
    st.markdown(
        f'''<div class="tb-masthead">
            <div class="tb-brand">
                <span class="tb-mark"><span>✦</span></span>
                <div><span class="tb-brand-name">TABLEBEAM</span><span class="tb-brand-sub">LOCAL SIGNAL DESK</span></div>
            </div>
            <div class="tb-masthead-center">DATA IN&nbsp;&nbsp;/&nbsp;&nbsp;SIGNAL OUT</div>
            <div class="tb-live"><span class="tb-live-dot {state_class}"></span>{status.provider.upper()} · {state_label}</div>
        </div>''',
        unsafe_allow_html=True,
    )


def render_control_deck() -> tuple[OpenAICompatibleClient, ProviderState]:
    with st.expander("Control deck · provider / model / table", expanded=False):
        st.markdown('<div class="tb-deck-label">01 · Model signal</div>', unsafe_allow_html=True)
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

        status_text = f"READY · {len(state.loaded_models)} loaded" if state.ready else ("ONLINE · load a model" if state.server_online else "OFFLINE · start a local server")
        status_class = "tb-status" if state.server_online else "tb-status offline"
        st.markdown(f'<div class="{status_class}"><span class="tb-status-dot"></span>{status_text}</div>', unsafe_allow_html=True)
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
        st.markdown('<div class="tb-deck-label">02 · Table source</div>', unsafe_allow_html=True)
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
            st.markdown('<div class="tb-deck-label">Loaded table</div>', unsafe_allow_html=True)
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


def render_landing(status: ProviderState) -> None:
    left, right = st.columns([1.08, .92], gap="large")
    with left:
        st.markdown('<div class="tb-kicker">LOCAL TABLE INTELLIGENCE · 01</div>', unsafe_allow_html=True)
        st.markdown('<h1 class="tb-hero-title">Rows<br>become<br><em>signal.</em></h1>', unsafe_allow_html=True)
        st.markdown('<p class="tb-hero-copy">A focused local desk for turning spreadsheets into a point of view. Ask a sharp question, get a concise answer, and keep the proof in reach.</p>', unsafe_allow_html=True)
        if st.button("Open the demo table", type="primary", key="landing_demo"):
            try:
                load_demo()
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
        if status.ready:
            st.markdown('<div class="tb-hero-note"><strong>Signal is live.</strong><br>Your local model is ready for a first question.</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="tb-hero-note"><strong>Desk is waiting.</strong><br>Start a local server in the control deck, then bring in a table.</div>', unsafe_allow_html=True)
    with right:
        if BANNER_PATH.exists():
            banner_data = base64.b64encode(BANNER_PATH.read_bytes()).decode("ascii")
            st.markdown(
                f'<div class="tb-visual"><img src="data:image/jpeg;base64,{banner_data}" alt="Abstract blue signal beam" /><div class="tb-visual-grid"></div><div class="tb-visual-label">SIGNAL DESK / LOCAL ONLY / 001</div></div>',
                unsafe_allow_html=True,
            )

    st.markdown('<div class="tb-loop">\
        <div class="tb-loop-step"><div class="tb-loop-number">01 / INGEST</div><div class="tb-loop-title">Bring the table.</div><div class="tb-loop-copy">CSV or a public Google Sheet. Validation stays on your machine.</div></div>\
        <div class="tb-loop-step"><div class="tb-loop-number">02 / ASK</div><div class="tb-loop-title">Find the signal.</div><div class="tb-loop-copy">A local model gets only the profile and rows that matter.</div></div>\
        <div class="tb-loop-step"><div class="tb-loop-number">03 / PROVE</div><div class="tb-loop-title">Keep the proof.</div><div class="tb-loop-copy">Every answer keeps its retrieved evidence one click away.</div></div>\
    </div>', unsafe_allow_html=True)


def render_explore(table: LocalTable) -> None:
    profile = table.profile
    total_cells = profile.row_count * profile.column_count
    missing_cells = sum(profile.missing_values.values())
    completeness = 100 if not total_cells else (1 - missing_cells / total_cells) * 100

    st.markdown('<div class="tb-kicker">TABLE PROFILE / LOCAL COMPUTE</div>', unsafe_allow_html=True)
    st.markdown('<div class="tb-section-title">Know the shape<br>before you ask.</div>', unsafe_allow_html=True)
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


def render_workspace(table: LocalTable, client: OpenAICompatibleClient, status: ProviderState) -> None:
    profile = table.profile
    label = st.session_state.table_label or "Loaded table"
    header_left, header_right = st.columns([0.8, 0.2])
    with header_left:
        st.markdown('<div class="tb-kicker">ACTIVE TABLE / LOCAL</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="tb-workspace-title">{label}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="tb-workspace-meta">{profile.row_count:,} ROWS · {profile.column_count} COLUMNS · PROFILE READY</div>', unsafe_allow_html=True)
    with header_right:
        signal = "READY" if status.ready else ("ONLINE" if status.server_online else "OFFLINE")
        st.markdown(f'<div class="tb-signal-badge"><small>MODEL SIGNAL</small><strong>{signal}</strong></div>', unsafe_allow_html=True)

    ask_tab, explore_tab = st.tabs(["Ask", "Explore"])
    with ask_tab:
        st.markdown('<div class="tb-conversation-label">CONVERSATION / ASK THE DESK</div>', unsafe_allow_html=True)
        st.markdown('<div class="tb-section-title">What do you<br>want to know?</div>', unsafe_allow_html=True)
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
active_url = st.session_state.server_url if st.session_state.provider_seen == st.session_state.provider_name else PROVIDERS[st.session_state.provider_name]
initial_status = get_provider_state(st.session_state.provider_name, active_url, st.session_state.api_key)
render_masthead(initial_status)
client, status = render_control_deck()

if os.getenv("START_WITH_DEMO") == "1" and st.session_state.table is None:
    try:
        load_demo()
    except Exception as exc:
        st.error(str(exc))

if st.session_state.table is None:
    render_landing(status)
else:
    render_workspace(st.session_state.table, client, status)
