"""Exercise the question-first workspace without a live model or network."""
from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from assistant_core import LocalTable, OpenAICompatibleClient, ProviderError
from provider_control import ProviderController, ProviderModel, ProviderState

APP = Path(__file__).parents[1] / "src" / "app.py"


@pytest.fixture
def workspace(monkeypatch):
    for name in (
        "START_WITH_DEMO", "AUTO_START_PROVIDER", "AUTO_START_MODEL",
        "LLM_PROVIDER", "LLM_MODEL", "LLM_BASE_URL", "LLM_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)

    def unexpected(*args, **kwargs):
        raise AssertionError("Local exploration must not contact a provider")

    monkeypatch.setattr(ProviderController, "probe", unexpected)
    monkeypatch.setattr(OpenAICompatibleClient, "ask", unexpected)
    return AppTest.from_file(str(APP), default_timeout=25)


def demo(workspace):
    workspace.run()
    workspace.button(key="landing_demo").click().run()
    assert not workspace.exception
    return workspace


def button(app, label):
    return next(item for item in app.button if item.label == label)


def text_input(app, label):
    return next(item for item in app.text_input if item.label == label)


def submit_dialog(app, label, visibility_key):
    # AppTest reruns the entire script for dialog widgets, while Streamlit's
    # browser reruns only the still-open dialog fragment. Preserve that visible
    # surface in the harness so the real handler consumes the submitted event.
    app.session_state[visibility_key] = True
    button(app, label).click().run()
    assert not app.exception


def ask(app, question):
    app.text_input(key="question_text").set_value(question)
    button(app, "Get answer").click().run()
    assert not app.exception
    return app.session_state.answer


def custom_table(workspace, frame, name="custom.csv"):
    workspace.run()
    workspace.session_state.table = LocalTable(frame)
    workspace.session_state.table_label = name
    workspace.run()
    assert not workspace.exception
    return workspace


def ready_state():
    return ProviderState(
        provider="LM Studio", base_url="http://localhost:1234/v1", server_online=True,
        models=(ProviderModel("installed-only", "Installed model"),
                ProviderModel("loaded-model", "Loaded model", loaded=True)),
        cli_available=True, message="Ready",
    )


def offline_state():
    return ProviderState(
        provider="LM Studio", base_url="http://localhost:1234/v1",
        server_online=False, models=(), cli_available=False, message="Offline",
    )


def test_demo_starts_with_a_question_and_no_automatic_result(workspace):
    app = demo(workspace)
    assert app.session_state.table.profile.row_count == 12
    assert app.session_state.answer is None
    assert app.session_state.answer_history == []
    assert app.text_input(key="question_text").value == ""
    assert not app.metric
    assert app.selectbox(key="analysis_group").value is None
    assert app.selectbox(key="analysis_filter_column").value is None
    assert len([item for item in app.button if (item.key or "").startswith("suggest_")]) == 3


def test_suggestion_gives_an_exact_grouped_answer_without_model(workspace):
    app = demo(workspace)
    app.button(key="suggest_Annual revenue by status").click().run()
    assert not app.exception
    answer = app.session_state.answer
    assert answer["kind"] == "calculation"
    assert answer["group_by"] == "status"
    assert answer["selected_rows"] == answer["total_rows"] == 12
    result = answer["result"].set_index("status")
    assert result["value"].to_dict() == {
        "Active": 1_200_000, "At risk": 268_000, "Churned": 39_000, "Onboarding": 272_000,
    }
    assert result["rows"].sum() == 12
    assert app.text_input(key="question_text").value == answer["question"]


def test_plain_total_uses_every_row_without_model(workspace):
    app = demo(workspace)
    answer = ask(app, "Total annual revenue")
    assert answer["kind"] == "calculation"
    assert answer["column"] == "annual_revenue"
    assert answer["group_by"] is None
    assert answer["selected_rows"] == answer["total_rows"] == 12
    assert answer["result"]["value"].item() == 1_779_000
    assert app.metric[0].value == "1,779,000"


def test_typed_group_question_uses_the_requested_column(workspace):
    answer = ask(demo(workspace), "Total annual revenue by owner")
    assert answer["group_by"] == "owner"
    assert answer["result"].set_index("owner")["value"].to_dict() == {
        "Maya": 676_000, "Jon": 553_000, "Sam": 550_000,
    }
    assert answer["result"]["rows"].tolist() == [4, 4, 4]


def test_builder_waits_for_calculate_and_keeps_the_completed_answer(workspace):
    app = demo(workspace)
    app.selectbox(key="analysis_filter_column").select("status").run()
    app.selectbox(key="analysis_value_choice_status").select("At risk").run()
    assert app.session_state.answer is None
    app.button(key="calculate_custom").click().run()
    assert not app.exception
    answer = app.session_state.answer
    assert answer["selected_rows"] == 3
    assert answer["result"]["value"].item() == 268_000
    assert answer["result"]["rows"].item() == 3
    assert set(answer["selected_data"]["status"]) == {"At risk"}
    assert app.metric[0].value == "268,000"
    app.selectbox(key="analysis_value_choice_status").select("Active").run()
    assert app.session_state.answer["result"]["value"].item() == 268_000
    assert app.session_state.answer_history == []
    app.button(key="calculate_custom").click().run()
    assert app.session_state.answer["result"]["value"].item() == 1_200_000
    assert len(app.session_state.answer_history) == 1


def test_fresh_question_starts_from_full_table_after_filtered_answer(workspace):
    app = demo(workspace)
    app.selectbox(key="analysis_filter_column").select("status").run()
    app.selectbox(key="analysis_value_choice_status").select("At risk").run()
    app.button(key="calculate_custom").click().run()
    answer = ask(app, "Total annual revenue")
    assert answer["filter_label"] == "All rows"
    assert answer["selected_rows"] == 12
    assert answer["result"]["value"].item() == 1_779_000
    assert app.session_state.answer_history[0]["result"]["value"].item() == 268_000


def test_empty_filter_can_return_to_all_rows(workspace):
    app = demo(workspace)
    app.selectbox(key="analysis_filter_column").select("annual_revenue").run()
    app.text_input(key="analysis_value_num_annual_revenue").set_value("-1").run()
    app.button(key="calculate_custom").click().run()
    assert app.session_state.answer["selected_rows"] == 0
    assert any("No rows match" in item.value for item in app.info)
    app.button(key="clear_result_filter").click().run()
    assert not app.exception
    assert app.session_state.answer["selected_rows"] == 12
    assert app.metric[0].value == "1,779,000"


def test_unsupported_question_explains_ai_and_previews_only_local_sources(workspace):
    app = demo(workspace)
    answer = ask(app, "zzzznomatch")
    assert answer == {"kind": "needs_ai", "question": "zzzznomatch"}
    assert app.session_state.answer_history == []
    assert not app.metric
    assert any("First-row sample" in item.value and "8 of 12" in item.value for item in app.caption)
    assert "connect_ai" in [item.key for item in app.button]
    assert "ask_ai" not in [item.key for item in app.button]


def test_model_that_goes_offline_preserves_question_without_orphan_answer(workspace, monkeypatch):
    app = demo(workspace)
    app.session_state.connection_state = ready_state()
    ask(app, "Which accounts need attention?")
    monkeypatch.setattr(ProviderController, "probe", lambda self: offline_state())
    app.button(key="ask_ai").click().run()
    assert not app.exception
    assert app.session_state.answer == {
        "kind": "needs_ai", "question": "Which accounts need attention?", "offline": True,
    }
    assert app.session_state.answer_history == []
    assert app.text_input(key="question_text").value == "Which accounts need attention?"
    assert "connect_ai" in [item.key for item in app.button]


def test_ai_uses_the_loaded_model_and_retains_the_actual_source_proof(workspace, monkeypatch):
    app = demo(workspace)
    app.session_state.connection_state = ready_state()
    calls = []

    def answer(self, question, table, limit=8):
        calls.append((self.model, self.base_url, question))
        return "Acorn needs attention [Source 1].", table.search(question, limit)

    monkeypatch.setattr(ProviderController, "probe", lambda self: ready_state())
    monkeypatch.setattr(OpenAICompatibleClient, "ask", answer)
    ask(app, "Acorn")
    assert calls == []  # Unsupported wording does not call AI without an explicit action.
    app.button(key="ask_ai").click().run()
    assert not app.exception
    assert calls == [("loaded-model", "http://localhost:1234/v1", "Acorn")]
    answer = app.session_state.answer
    assert answer["kind"] == "ai"
    assert answer["sources"][0]["row_number"] == 2
    assert "Acorn Retail" in answer["sources"][0]["content"]
    assert "1 of 12" in answer["coverage"]
    assert answer["profile"] == app.session_state.table.prompt_profile()
    assert app.session_state.answer_history == []
    assert any("Acorn Retail" in item.value for item in app.code)


def test_provider_failure_keeps_the_question_and_no_generated_answer(workspace, monkeypatch):
    app = demo(workspace)
    app.session_state.connection_state = ready_state()
    monkeypatch.setattr(ProviderController, "probe", lambda self: ready_state())

    def fail(*args, **kwargs):
        raise ProviderError("Provider unavailable")

    monkeypatch.setattr(OpenAICompatibleClient, "ask", fail)
    ask(app, "Which records need attention?")
    app.button(key="ask_ai").click().run()
    assert not app.exception
    assert any(item.value == "Provider unavailable" for item in app.error)
    assert app.text_input(key="question_text").value == "Which records need attention?"
    assert app.session_state.answer["kind"] == "needs_ai"
    assert app.session_state.answer_history == []


def test_replacing_table_clears_answer_history_question_and_filters(workspace):
    app = demo(workspace)
    app.selectbox(key="analysis_filter_column").select("status").run()
    app.selectbox(key="analysis_value_choice_status").select("At risk").run()
    app.selectbox(key="analysis_group").select("owner").run()
    app.button(key="calculate_custom").click().run()
    ask(app, "Total annual revenue")
    assert app.session_state.answer_history
    app.button(key="change_table").click().run()
    submit_dialog(app, "Use example data", "show_importer")
    assert not app.exception
    assert app.session_state.answer is None
    assert app.session_state.answer_history == []
    assert app.text_input(key="question_text").value == ""
    assert app.selectbox(key="analysis_filter_column").value is None
    assert app.selectbox(key="analysis_group").value is None
    assert not app.metric


def test_previous_answer_can_be_reopened_without_widget_mutation_error(workspace):
    app = demo(workspace)
    ask(app, "Total annual revenue")
    ask(app, "How many rows are there?")
    assert app.metric[0].value == "12"
    app.button(key="history_0").click().run()
    assert not app.exception
    assert app.metric[0].value == "1,779,000"
    assert app.text_input(key="question_text").value == "Total annual revenue"
    assert app.session_state.answer["result"]["value"].item() == 1_779_000


def test_environment_connection_survives_initial_and_workspace_render(workspace, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "Ollama")
    monkeypatch.setenv("LLM_BASE_URL", "http://localhost:9876/v1")
    monkeypatch.setenv("LLM_MODEL", "configured-model")
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    app = demo(workspace)
    assert app.session_state.connection == {
        "provider": "Ollama", "url": "http://localhost:9876/v1",
        "model": "configured-model", "api_key": "test-key",
    }
    app.button(key="open_ai_settings").click().run()
    assert not app.exception
    assert text_input(app, "Server address").value == "http://localhost:9876/v1"
    assert text_input(app, "Model ID").value == "configured-model"


def test_connection_dialog_custom_model_edits_persist_and_can_reset_to_auto(workspace):
    app = demo(workspace)
    app.button(key="open_ai_settings").click().run()
    text_input(app, "Server address").set_value("http://localhost:9876/v1")
    text_input(app, "Model ID").set_value("model-a")
    submit_dialog(app, "Save connection", "show_ai_settings")
    assert not app.exception
    assert app.session_state.connection["model"] == "model-a"
    assert app.session_state.connection["url"] == "http://localhost:9876/v1"
    text_input(app, "Model ID").set_value("model-b")
    submit_dialog(app, "Save connection", "show_ai_settings")
    assert not app.exception
    assert app.session_state.connection["model"] == "model-b"
    text_input(app, "Model ID").set_value("")
    submit_dialog(app, "Save connection", "show_ai_settings")
    assert not app.exception
    assert app.session_state.connection["model"] == "auto"
    assert app.session_state.connection_state is None


def test_provider_change_refreshes_advanced_defaults(workspace):
    app = demo(workspace)
    app.button(key="open_ai_settings").click().run()
    text_input(app, "Server address").set_value("http://localhost:9876/v1")
    text_input(app, "Model ID").set_value("custom-lm-model")
    text_input(app, "API key").set_value("old-provider-key")
    submit_dialog(app, "Save connection", "show_ai_settings")
    app.session_state.show_ai_settings = True
    app.radio(key="ai_provider").set_value("Ollama").run()
    assert not app.exception
    assert text_input(app, "Server address").value == "http://localhost:11434/v1"
    assert text_input(app, "Model ID").value == "auto"
    assert text_input(app, "API key").value == ""
    submit_dialog(app, "Save connection", "show_ai_settings")
    assert app.session_state.connection == {
        "provider": "Ollama", "url": "http://localhost:11434/v1",
        "model": "auto", "api_key": "",
    }
    ask(app, "Total annual revenue")  # Closing the dialog cleans up its widgets.
    app.button(key="open_ai_settings").click().run()
    assert app.radio(key="ai_provider").value == "Ollama"
    assert text_input(app, "Server address").value == "http://localhost:11434/v1"


def test_discovered_loaded_model_persists_after_closing_settings(workspace, monkeypatch):
    app = demo(workspace)
    ask(app, "Which accounts need attention?")
    app.button(key="connect_ai").click().run()
    monkeypatch.setattr(ProviderController, "probe", lambda self: ready_state())
    submit_dialog(app, "Find local models", "show_ai_settings")
    assert app.session_state.connection["model"] == "loaded-model"
    assert text_input(app, "Model ID").value == "loaded-model"
    submit_dialog(app, "Done", "show_ai_settings")
    assert app.session_state.connection["model"] == "loaded-model"
    assert app.session_state.answer["kind"] == "needs_ai"
    assert "ask_ai" in [item.key for item in app.button]
    assert "connect_ai" not in [item.key for item in app.button]


def test_start_with_demo_has_no_automatic_calculation(workspace, monkeypatch):
    monkeypatch.setenv("START_WITH_DEMO", "1")
    workspace.run()
    assert not workspace.exception
    assert workspace.session_state.table.profile.row_count == 12
    assert workspace.session_state.answer is None
    assert not workspace.metric


def test_table_name_is_html_escaped(workspace):
    app = custom_table(workspace, pd.DataFrame({"a": [1]}), '<img src=x onerror="alert(1)">.csv')
    header = next(item.value for item in app.markdown if 'class="tb-file"' in item.value)
    assert "&lt;img" in header
    assert "<img src=x" not in header
    assert not app.exception


def test_large_integer_scalar_and_filter_keep_every_digit(workspace):
    app = custom_table(workspace, pd.DataFrame({"n": [9223372036854775807] * 2}))
    answer = ask(app, "Total n")
    assert answer["result"]["value"].item() == 18_446_744_073_709_551_614
    assert app.metric[0].value == "18,446,744,073,709,551,614"
    app.selectbox(key="analysis_filter_column").select("n").run()
    app.text_input(key="analysis_value_num_n").set_value("9223372036854775807").run()
    app.button(key="calculate_custom").click().run()
    assert not app.exception
    assert app.session_state.answer["selected_rows"] == 2
    assert app.metric[0].value == "18,446,744,073,709,551,614"


def test_integer_equality_above_javascript_precision_keeps_distinct_values(workspace):
    app = custom_table(workspace, pd.DataFrame({"n": [9007199254740992, 9007199254740993]}))
    app.selectbox(key="analysis_filter_column").select("n").run()
    app.text_input(key="analysis_value_num_n").set_value("9007199254740993").run()
    app.button(key="calculate_custom").click().run()
    assert not app.exception
    assert app.session_state.answer["selected_rows"] == 1
    assert app.metric[0].value == "9,007,199,254,740,993"


def test_nullable_boolean_csv_filters_both_values_and_missing_rows(workspace):
    frame = LocalTable.from_csv_bytes(b"id,flag\n1,true\n2,\n3,false\n").dataframe
    app = custom_table(workspace, frame)
    app.selectbox(key="analysis_operation").select("Number of rows").run()
    app.selectbox(key="analysis_filter_column").select("flag").run()
    for value, row_id in ((True, 1), (False, 3)):
        app.selectbox(key="analysis_value_bool_flag").select(value).run()
        app.button(key="calculate_custom").click().run()
        assert not app.exception
        assert app.session_state.answer["selected_data"]["id"].tolist() == [row_id]
        assert app.metric[0].value == "1"
    app.selectbox(key="analysis_operator_flag").select("is empty").run()
    app.button(key="calculate_custom").click().run()
    assert not app.exception
    assert app.session_state.answer["selected_data"]["id"].tolist() == [2]
    assert app.metric[0].value == "1"


def test_grouped_sum_beyond_arrow_integer_range_renders_exact_text(workspace):
    app = custom_table(workspace, pd.DataFrame({"team": ["A"] * 3, "n": [9223372036854775807] * 3}))
    answer = ask(app, "Total n by team")
    assert answer["result"]["value"].item() == 27_670_116_110_564_327_421
    assert app.dataframe[0].value["value"].item() == "27670116110564327421"
    assert any("preserve every digit" in item.value for item in app.caption)


def test_fractional_threshold_on_large_integer_column_is_exact(workspace):
    app = custom_table(workspace, pd.DataFrame({"n": [9007199254740992, 9007199254740993]}))
    app.selectbox(key="analysis_operation").select("Number of rows").run()
    app.selectbox(key="analysis_filter_column").select("n").run()
    app.selectbox(key="analysis_operator_n").select("is greater than").run()
    app.text_input(key="analysis_value_num_n").set_value("9007199254740992.5").run()
    app.button(key="calculate_custom").click().run()
    assert not app.exception
    assert app.session_state.answer["selected_data"]["n"].tolist() == [9007199254740993]
    assert app.metric[0].value == "1"


def test_start_over_returns_to_upload_without_reloading_demo(workspace, monkeypatch):
    monkeypatch.setenv("START_WITH_DEMO", "1")
    workspace.run()
    ask(workspace, "Count rows")
    workspace.button(key="change_table").click().run()
    submit_dialog(workspace, "Start over", "show_importer")
    assert workspace.session_state.table is None
    assert workspace.session_state.answer is None
    assert workspace.session_state.answer_history == []
    assert workspace.button(key="landing_demo").label == "Try example data"


def test_previous_answer_recall_keeps_the_latest_answer(workspace):
    app = demo(workspace)
    ask(app, "Total annual revenue")
    ask(app, "How many rows are there?")
    app.button(key="history_0").click().run()
    assert not app.exception
    assert app.session_state.answer["question"] == "Total annual revenue"
    assert app.session_state.answer_history[0]["question"] == "How many rows are there?"
    app.button(key="history_0").click().run()
    assert app.session_state.answer["result"]["value"].item() == 12
    assert app.session_state.answer_history[0]["question"] == "Total annual revenue"


def test_invalid_connection_does_not_replace_working_settings(workspace):
    app = demo(workspace)
    app.button(key="open_ai_settings").click().run()
    text_input(app, "Server address").set_value("http://[broken")
    submit_dialog(app, "Save connection", "show_ai_settings")
    assert any("Enter a server address" in error.value for error in app.error)
    assert app.session_state.connection["url"] == "http://localhost:1234/v1"
