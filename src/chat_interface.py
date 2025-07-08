from langchain_ollama.llms import OllamaLLM
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.documents import Document
from vector import get_retriever
from colorama import Fore, Style, init
from typing import List
import sys
import os

# Initialize colorama for colored terminal prompts
init(autoreset=True)

# Initialize the LLM
model = OllamaLLM(model="llama3.2")

# Define the structured prompt template
template = """
You are a helpful assistant that can answer questions about data from spreadsheets and CSV files.

Here are some relevant records from the data: {records}

Based on the information above, provide an informed and helpful response to the following question: {question}

If the question cannot be answered from the provided data, say so clearly.
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
    # Check if a data source was provided as command line argument
    data_source = sys.argv[1] if len(sys.argv) > 1 else None
    
    if not data_source:
        # Check for environment variable
        data_source = os.environ.get('CLIENT_DATA_SOURCE')
    
    if not data_source:
        # Interactive prompt
        print(f"\n{Fore.GREEN}Welcome to Spreadsheet Q&A Assistant!{Style.RESET_ALL}")
        print(f"\n{Fore.YELLOW}This tool can answer questions about ANY spreadsheet or CSV file.{Style.RESET_ALL}")
        print(f"\n{Fore.CYAN}Data Source Options:{Style.RESET_ALL}")
        print("1. Local CSV file (e.g., 'data.csv' or '/path/to/file.csv')")
        print("2. Google Sheets URL (e.g., 'https://docs.google.com/spreadsheets/d/...')")
        print("3. Just the Google Sheet ID")
        
        data_source = input(f"\n{Fore.CYAN}Enter your data source: {Style.RESET_ALL}").strip()
        
        if not data_source:
            print(f"{Fore.RED}No data source provided. Exiting.{Style.RESET_ALL}")
            sys.exit(1)
    
    print(f"\n{Fore.GREEN}Loading data from: {data_source}{Style.RESET_ALL}")
    
    try:
        retriever = get_retriever(data_source)
        print(f"{Fore.GREEN}✓ Data loaded successfully!{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}✗ Error loading data: {str(e)}{Style.RESET_ALL}")
        sys.exit(1)

    while True:
        print("\n\n-------------------------------")
        question: str = input(
            f"{Fore.CYAN}Ask a question about your data (or 'q' to quit): {Style.RESET_ALL}"
        )
        print("\n\n")
        if question.lower() == "q":
            break

        try:
            answer: str = ask_question(question, retriever)
            print(answer)
        except Exception as e:
            print(f"{Fore.RED}Error: {str(e)}{Style.RESET_ALL}")


if __name__ == "__main__":
    main()
