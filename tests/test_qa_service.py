from dataclasses import dataclass

from qa_service import answer_question, build_prompt


@dataclass
class FakeDocument:
    page_content: str
    metadata: dict


class FakeRetriever:
    def invoke(self, question):
        return [FakeDocument("company: Acme, status: Active", {"row_index": 4})]


class FakeLLM:
    def __init__(self):
        self.prompt = None

    def invoke(self, prompt):
        self.prompt = prompt
        return "Acme is active [Source 1]."


def test_prompt_labels_each_source_and_requires_grounding():
    prompt, sources = build_prompt("What is the status?", FakeRetriever().invoke(""))
    assert "[Source 1]" in prompt
    assert "Do not invent values" in prompt
    assert sources[0].row_index == 4


def test_answer_returns_citations_and_sources():
    llm = FakeLLM()
    result = answer_question(FakeRetriever(), llm, "What is the status?")
    assert result.answer.endswith("[Source 1].")
    assert result.sources[0].citation == "[Source 1]"
    assert "company: Acme" in llm.prompt
