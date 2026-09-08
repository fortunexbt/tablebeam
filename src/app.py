"""A question-first interface for Tablebeam's local table tools."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from html import escape
import os
from pathlib import Path

import pandas as pd
import streamlit as st

from answer_view import display_result, render_answer
from assistant_core import LocalTable, OpenAICompatibleClient, ProviderError
from provider_control import ProviderController, ProviderState, valid_server_address
from question_actions import Calculation, friendly_column, parse_question, suggested_questions
from table_analysis import FilterSpec, filter_dataframe, summarize_dataframe

ROOT = Path(__file__).parent.parent
PROVIDERS = {"LM Studio": "http://localhost:1234/v1", "Ollama": "http://localhost:11434/v1"}
OPERATIONS = {"Total": "sum", "Average": "mean", "Median": "median", "Lowest value": "min", "Highest value": "max", "Number of rows": "count"}


def setup_state() -> None:
    provider = os.getenv("LLM_PROVIDER", "LM Studio")
    provider = provider if provider in PROVIDERS else "LM Studio"
    defaults = {
        "table": None, "table_label": None, "demo_loaded": False,
        "demo_bootstrapped": False, "answer": None, "answer_history": [],
        "pending_question": None, "question_error": None, "import_error": None,
        "show_importer": False, "show_ai_settings": False,
        "import_completed": False,
        "connection": {"provider": provider, "url": os.getenv("LLM_BASE_URL") or PROVIDERS[provider],
                       "model": os.getenv("LLM_MODEL", "auto"), "api_key": os.getenv("LLM_API_KEY", "")},
        "connection_state": None, "connection_notice": None, "auto_start_attempted": False,
        "connection_revision": 0, "connection_action_failed": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def set_table(table: LocalTable | None, label: str | None, *, demo: bool = False) -> None:
    for key in list(st.session_state):
        if key.startswith(("analysis_", "question_", "ask_", "preview_")):
            del st.session_state[key]
    st.session_state.update(table=table, table_label=label, demo_loaded=demo, answer=None,
                            answer_history=[], pending_question=None, question_error=None,
                            show_importer=False, import_error=None, messages=[])


def load_demo() -> None:
    set_table(LocalTable.from_source(str(ROOT / "sample_data.csv")), "Sample accounts", demo=True)


def load_upload(widget_key: str) -> None:
    uploaded = st.session_state.get(widget_key)
    if uploaded is not None:
        try:
            set_table(LocalTable.from_csv_bytes(uploaded.getvalue()), uploaded.name)
            st.session_state.import_completed = True
        except (ValueError, OSError) as exc:
            st.session_state.import_error = str(exc)


def import_controls(prefix: str) -> None:
    st.file_uploader("Upload a CSV", type=["csv"], key=f"{prefix}_upload", on_change=load_upload,
                     args=(f"{prefix}_upload",), help="UTF-8 CSV, up to 100 MB. Your file is processed on this computer.")
    if st.session_state.import_error:
        st.error(st.session_state.import_error)
    with st.expander("Use a Google Sheet instead"):
        with st.form(f"{prefix}_sheet_form"):
            url = st.text_input("Public Google Sheets link", placeholder="Paste your sheet link")
            st.caption("The sheet must be shared as ‘Anyone with the link’. Loading downloads it from Google.")
            load = st.form_submit_button("Open sheet")
        if load:
            try:
                if not url.strip().startswith(("https://docs.google.com/spreadsheets/", "http://docs.google.com/spreadsheets/")):
                    raise ValueError("Paste a public Google Sheets link.")
                set_table(LocalTable.from_source(url.strip()), "Google Sheet")
                st.rerun()
            except (ValueError, OSError) as exc:
                st.error(str(exc))


@st.dialog("Open a table")
def import_dialog() -> None:
    if st.session_state.import_completed:
        st.session_state.import_completed = False
        st.rerun()
    import_controls("replace")
    if st.button("Use example data", key="replace_demo"):
        load_demo()
        st.rerun()
    if st.button("Start over", key="start_over", help="Clear the table and answers from this session. Your original file is unchanged."):
        set_table(None, None)
        st.rerun()


def controller() -> ProviderController:
    config = st.session_state.connection
    return ProviderController(config["provider"], config["url"], api_key=config["api_key"])


def ready_model(state: ProviderState | None) -> str | None:
    if state is None or not state.ready:
        return None
    loaded = [model.model_id for model in state.ready_models]
    requested = st.session_state.connection["model"]
    return loaded[0] if requested == "auto" else (requested if requested in loaded else None)


@st.dialog("Connect your AI")
def ai_dialog() -> None:
    st.write("Use LM Studio or Ollama running on your computer. Totals and comparisons work without either.")
    config = st.session_state.connection
    provider = st.radio("Your app", list(PROVIDERS), index=list(PROVIDERS).index(config["provider"]), key="ai_provider", horizontal=True)
    if provider != config["provider"]:
        config.update(provider=provider, url=PROVIDERS[provider], model="auto", api_key="")
        st.session_state.connection_state = None
        st.session_state.connection_notice = None
        st.session_state.connection_revision += 1
    state = st.session_state.connection_state
    if st.button("Find local models", type="primary", key="check_connection"):
        with st.spinner("Looking for your local model…"):
            state = controller().probe()
            st.session_state.connection_state = state
    if state is not None:
        if not state.server_online:
            st.info(f"Open {provider} and start its local server, then try again.")
            if st.button("Start server", key="start_server"):
                result = controller().start_server()
                st.session_state.connection_notice = (result.output if result.ok else result.error) or result.output
                st.session_state.connection_action_failed = not result.ok
                st.session_state.connection_state = controller().probe()
                st.session_state.show_ai_settings = True
                st.rerun()
        else:
            options = [model.model_id for model in state.models]
            if config["model"] != "auto" and config["model"] not in options:
                options.append(config["model"])
            if options:
                current = config["model"]
                preferred = current if current in options else (state.loaded_models[0].model_id if state.loaded_models else options[0])
                selected = st.selectbox("Model", options, index=options.index(preferred),
                                        key=f"ai_model_choice_{st.session_state.connection_revision}")
                if config["model"] != selected:
                    config["model"] = selected
                    st.session_state.connection_revision += 1
                if ready_model(state):
                    st.success("Ready to answer your questions.")
                else:
                    st.caption("This model needs to be loaded before it can answer.")
                    job = controller().model_job(selected)
                    if job and job["running"]:
                        st.info("Model loading. Use Find local models to check progress.")
                    elif job and job["returncode"] != 0:
                        st.error(f"The model could not be loaded. Open {provider} for details or choose another model.")
                    installed = any(model.model_id == selected and model.installed for model in state.models)
                    action = "Download model" if provider == "Ollama" and not installed else "Load this model"
                    if st.button(action, key="load_model"):
                        result = controller().load_model(selected)
                        st.session_state.connection_notice = (result.output if result.ok else result.error) or result.output
                        st.session_state.connection_action_failed = not result.ok
                        st.session_state.connection_state = controller().probe()
                        st.session_state.show_ai_settings = True
                        st.rerun()
            else:
                st.info(f"No models found. Download a chat model in {provider}, then check again.")
    else:
        st.caption("First, open your model app and enable its local server.")
    with st.expander("Advanced settings"):
        with st.form("connection_form"):
            revision = st.session_state.connection_revision
            url = st.text_input("Server address", value=config["url"], key=f"ai_url_{revision}")
            model_id = st.text_input("Model ID", value=config["model"], key=f"ai_model_id_{revision}")
            api_key = st.text_input("API key", value=config["api_key"], type="password", key=f"ai_api_key_{revision}")
            st.caption("AI questions send selected rows and the table profile to this address. Use a local address to keep them on your computer.")
            save = st.form_submit_button("Save connection")
        if save:
            if not valid_server_address(url.strip()):
                st.error("Enter a server address starting with http:// or https://, without query parameters.")
            else:
                config.update(url=url.strip(), model=model_id.strip() or "auto", api_key=api_key)
                st.session_state.connection_revision += 1
                st.session_state.connection_state = None
                st.session_state.show_ai_settings = True
                st.rerun()
    if st.session_state.connection_notice:
        if st.session_state.connection_action_failed:
            st.error(st.session_state.connection_notice)
        else:
            with st.expander("Connection details"):
                st.text(st.session_state.connection_notice)
    if ready_model(st.session_state.connection_state):
        if st.button("Done", key="close_ai"):
            st.session_state.show_ai_settings = False
            st.rerun()


def save_answer(answer: dict) -> None:
    old = st.session_state.answer
    if old and old.get("kind") in {"calculation", "ai"}:
        st.session_state.answer_history = [old] + st.session_state.answer_history[:4]
    st.session_state.answer = answer
    st.session_state.question_error = None


def calculate(question: str, spec: Calculation, table: LocalTable,
              filters: list[FilterSpec] | None = None, filter_label: str = "All rows") -> None:
    selected = filter_dataframe(table.dataframe, filters or [])
    result = summarize_dataframe(selected, spec.operation, spec.column, spec.group_by)
    save_answer({"kind": "calculation", "question": question, "operation": spec.operation,
                 "column": spec.column, "group_by": spec.group_by, "result": result,
                 "selected_rows": len(selected), "total_rows": len(table.dataframe),
                 "filter_label": filter_label, "selected_data": selected,
                 "missing_values": int(selected[spec.column].isna().sum()) if spec.column else 0})


def answer_question(question: str, table: LocalTable, *, use_ai: bool = False) -> None:
    clean = question.strip()
    if not clean:
        st.session_state.question_error = "Type a question, or choose one of the examples below."
        return
    spec = None if use_ai else parse_question(clean, table.dataframe)
    try:
        if spec is not None:
            calculate(clean, spec, table)
            return
        # AI is explicit: an unrecognized calculation must not silently become
        # a generated number, even if a provider is already connected.
        if not use_ai:
            save_answer({"kind": "needs_ai", "question": clean})
            return
        with st.spinner("Checking your local AI…"):
            state = controller().probe()
            st.session_state.connection_state = state
        model = ready_model(state)
        if model is None:
            save_answer({"kind": "needs_ai", "question": clean, "offline": True})
            return
        config = st.session_state.connection
        client = OpenAICompatibleClient(base_url=config["url"], model=model, api_key=config["api_key"], timeout=120)
        with st.spinner("Reading your table…"):
            text, sources = client.ask(clean, table)
        info = table.search_info(clean)
        label = "Matching rows" if info["mode"] == "matched" else "First-row sample; no matching terms"
        save_answer({"kind": "ai", "question": clean, "text": text, "sources": [source.as_dict() for source in sources],
                     "coverage": f"{label}: {len(sources)} of {len(table.dataframe):,} rows, plus the table profile.",
                     "profile": table.prompt_profile()})
    except (ValueError, ProviderError) as exc:
        st.session_state.question_error = str(exc)


def choose_question(question: str) -> None:
    st.session_state.question_text = question
    st.session_state.pending_question = question


def restore_answer(index: int) -> None:
    history = list(st.session_state.answer_history)
    answer = history.pop(index)
    current = st.session_state.answer
    if current and current.get("kind") in {"calculation", "ai"}:
        history.insert(0, current)
    st.session_state.answer_history = history[:5]
    st.session_state.answer = answer
    st.session_state.question_text = answer["question"]
    st.session_state.question_error = None


def filter_controls(df: pd.DataFrame) -> tuple[list[FilterSpec], str]:
    column = st.selectbox("Only include rows where", [None] + list(df.columns),
                          format_func=lambda value: "No filter" if value is None else friendly_column(value), key="analysis_filter_column")
    if column is None:
        return [], "All rows"
    series = df[column]
    numeric = pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(series)
    operators = {"is": "eq", "is not": "ne"}
    if numeric:
        operators.update({"is greater than": "gt", "is at least": "ge", "is less than": "lt", "is at most": "le"})
    elif not pd.api.types.is_bool_dtype(series):
        operators["contains"] = "contains"
    operators.update({"is empty": "is_missing", "is not empty": "not_missing"})
    condition = st.selectbox("Condition", list(operators), key=f"analysis_operator_{column}")
    value = None
    if operators[condition] not in {"is_missing", "not_missing"}:
        if numeric:
            raw = st.text_input("Value", value="0", key=f"analysis_value_num_{column}")
            try:
                value = Decimal(raw) if pd.api.types.is_integer_dtype(series) else float(raw)
            except (ValueError, InvalidOperation):
                raise ValueError("Enter a number for the filter.") from None
        elif pd.api.types.is_bool_dtype(series):
            value = st.selectbox("Value", [True, False], key=f"analysis_value_bool_{column}")
        elif operators[condition] in {"eq", "ne"} and 0 < series.nunique() <= 100:
            value = st.selectbox("Value", series.dropna().unique().tolist(), key=f"analysis_value_choice_{column}")
        else:
            value = st.text_input("Value", key=f"analysis_value_text_{column}")
    label = friendly_column(column) + " " + condition + (f" {value}" if value is not None else "")
    return [FilterSpec(column, operators[condition], value)], label


def render_builder(table: LocalTable) -> None:
    with st.expander("Build a calculation"):
        st.caption("Choose the columns directly. This calculation starts from your full table.")
        choices = list(OPERATIONS) if table.profile.numeric_columns else ["Number of rows"]
        if st.session_state.get("analysis_operation") not in choices:
            st.session_state.analysis_operation = choices[0]
        columns = st.columns(3)
        op = columns[0].selectbox("Find", choices, key="analysis_operation")
        measure = None
        if OPERATIONS[op] != "count":
            measure = columns[1].selectbox("Of", table.profile.numeric_columns, format_func=friendly_column, key="analysis_measure")
        group = columns[2].selectbox("Compare by", [None] + list(table.dataframe.columns),
                                    format_func=lambda value: "Nothing" if value is None else friendly_column(value), key="analysis_group")
        try:
            filters, label = filter_controls(table.dataframe)
            if st.button("Calculate", key="calculate_custom"):
                title = op + (" " + friendly_column(measure).lower() if measure else "")
                if group:
                    title += " by " + friendly_column(group).lower()
                if filters:
                    title += " · " + label
                calculate(title, Calculation(OPERATIONS[op], measure, group), table, filters, label)
                st.rerun()
        except ValueError as exc:
            st.error(str(exc))


def render_ai_request(answer: dict, table: LocalTable) -> None:
    with st.container(border=True, key="ai_request"):
        st.markdown("### Use AI for this question")
        st.write("This wording is outside the built-in calculations. AI can interpret your table; for an exact number, use **Build a calculation** below.")
        if answer.get("offline"):
            st.info("No model is ready yet. Connect your AI, then ask again. Your question is saved.")
        if ready_model(st.session_state.connection_state):
            if st.button("Ask AI", type="primary", key="ask_ai"):
                answer_question(answer["question"], table, use_ai=True)
                st.rerun()
        elif st.button("Connect AI", type="primary", key="connect_ai"):
            st.session_state.show_ai_settings = True
            st.rerun()
        with st.expander("See what AI would receive"):
            info = table.search_info(answer["question"])
            kind = "Matching rows" if info["mode"] == "matched" else "First-row sample (no matching terms)"
            st.caption(f"{kind}: {info['selected_rows']} of {info['total_rows']} rows. AI answers may not describe the whole table.")
            for source in table.search(answer["question"]):
                st.markdown(f"**{source.citation} · row {source.row_number}**")
                st.code(source.content, language="text")
            st.code(table.prompt_profile(), language="text")


def render_workspace(table: LocalTable) -> None:
    with st.container(key="table_header"):
        source, change = st.columns([5, 1])
        with source:
            st.markdown(f'<div class="tb-file">{escape(st.session_state.table_label or "Your table")}</div>', unsafe_allow_html=True)
            st.caption(f"{table.profile.row_count:,} rows · {table.profile.column_count} columns")
        if change.button("Change table", key="change_table", use_container_width=True):
            st.session_state.show_importer = True
    st.markdown('<h1 class="tb-question-title">What would you like to know?</h1>', unsafe_allow_html=True)
    with st.form("question_form", border=False):
        field, submit = st.columns([5, 1])
        question = field.text_input("Your question", key="question_text", label_visibility="collapsed",
                                    placeholder="Ask for a total, an average, or a comparison…", max_chars=2000)
        ask = submit.form_submit_button("Get answer", type="primary", use_container_width=True)
    with st.container(key="suggestions"):
        suggestions = suggested_questions(table.dataframe)
        for col, item in zip(st.columns(len(suggestions)), suggestions):
            col.button(item.label, key=f"suggest_{item.question}", on_click=choose_question,
                       args=(item.question,), use_container_width=True)
    pending = st.session_state.pop("pending_question", None)
    if ask or pending:
        answer_question(pending or question, table)
    if st.session_state.question_error:
        st.error(st.session_state.question_error)
    answer = st.session_state.answer
    if answer:
        if answer["kind"] == "needs_ai":
            render_ai_request(answer, table)
        else:
            render_answer(answer)
            if answer["kind"] == "calculation" and answer["selected_rows"] == 0:
                if st.button("Use all rows", key="clear_result_filter"):
                    calculate(answer["question"].split(" · ")[0], Calculation(answer["operation"], answer["column"], answer["group_by"]), table)
                    st.rerun()
    else:
        st.caption("Choose an example above, or type your own. Each question starts from the full table.")
    render_builder(table)
    with st.expander(f"View data · {table.profile.row_count:,} rows"):
        st.dataframe(display_result(table.dataframe.head(100)), use_container_width=True, hide_index=True)
        if len(table.dataframe) > 100:
            st.caption("Showing the first 100 rows.")
        for warning in table.profile.warnings:
            st.warning(warning)
        if st.checkbox("Show column details", key="show_columns"):
            st.dataframe(pd.DataFrame({"Column": table.profile.columns,
                                       "Type": [str(table.dataframe[c].dtype) for c in table.profile.columns],
                                       "Missing": [table.profile.missing_values[c] for c in table.profile.columns]}),
                         use_container_width=True, hide_index=True)
    if st.session_state.answer_history:
        with st.expander("Previous answers"):
            for index, previous in enumerate(st.session_state.answer_history):
                st.button(previous["question"], key=f"history_{index}", on_click=restore_answer, args=(index,))
    st.caption("Your table stays in this session. Download any answers you want to keep.")


def main() -> None:
    st.set_page_config(page_title="Tablebeam · ask your spreadsheet", page_icon="✦", layout="wide")
    setup_state()
    st.session_state.import_completed = False
    st.markdown(f"<style>{(ROOT / 'assets' / 'tablebeam.css').read_text()}</style>", unsafe_allow_html=True)
    with st.container(key="app_header"):
        brand, settings = st.columns([5, 1])
        brand.markdown('<div class="tb-brand"><span>✦</span> tablebeam</div>', unsafe_allow_html=True)
        if st.session_state.table is not None and settings.button("AI settings", key="open_ai_settings", use_container_width=True):
            st.session_state.show_ai_settings = True
    if not st.session_state.demo_bootstrapped:
        st.session_state.demo_bootstrapped = True
        if os.getenv("START_WITH_DEMO") == "1":
            load_demo()
    auto_start = os.getenv("AUTO_START_PROVIDER", os.getenv("AUTO_START_MODEL", "0")) == "1"
    if auto_start and not st.session_state.auto_start_attempted:
        st.session_state.auto_start_attempted = True
        state = controller().probe()
        if not state.server_online:
            controller().start_server()
        st.session_state.connection_state = controller().probe()
    if st.session_state.table is None:
        st.markdown('<h1 class="tb-landing-title">Get answers from<br>your spreadsheet.</h1>', unsafe_allow_html=True)
        st.markdown('<p class="tb-intro">Start with a CSV. Get a total, compare categories, or ask a question.</p>', unsafe_allow_html=True)
        with st.container(key="import_card"):
            import_controls("landing")
            if st.button("Try example data", key="landing_demo", use_container_width=True):
                load_demo()
                st.rerun()
        st.caption("No account needed. Calculations run on your computer.")
    else:
        render_workspace(st.session_state.table)
    if st.session_state.show_importer:
        # Dismissed dialogs are not reopened by the next unrelated rerun.
        st.session_state.show_importer = False
        import_dialog()
    elif st.session_state.show_ai_settings:
        st.session_state.show_ai_settings = False
        ai_dialog()


if __name__ == "__main__":
    main()
