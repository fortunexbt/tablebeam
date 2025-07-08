from langchain_ollama.llms import OllamaLLM
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.documents import Document
from vector import get_retriever
from colorama import Fore, Style, init
from typing import List

# Initialize colorama for colored terminal prompts
init(autoreset=True)

# Initialize the LLM
model = OllamaLLM(model="llama3.2")

# Define the structured prompt template
template = """
You are an expert assistant helping manage validator and client onboarding workflows.

Here are some relevant client records: {records}

Based on the information above, provide an informed response to the following question: {question}
"""
prompt = ChatPromptTemplate.from_template(template)
chain = prompt | model


def ask_question(question: str, retriever) -> str:
    """
    Given a question, retrieve documents and use the LLM to return a response.
    """
    documents: List[Document] = retriever.invoke(question)
    context: str = "\n---\n".join([doc.page_content for doc in documents])
    response: str = chain.invoke({"records": context, "question": question})
    return response


def main() -> None:
    """
    Entry point: launches terminal chat interface for Q&A over client records.
    """
    retriever = get_retriever()

    while True:
        print("\n\n-------------------------------")
        question: str = input(
            f"{Fore.CYAN}Ask your question about a validator/client (q to quit): {Style.RESET_ALL}"
        )
        print("\n\n")
        if question.lower() == "q":
            break

        answer: str = ask_question(question, retriever)
        print(answer)


if __name__ == "__main__":
    main()
