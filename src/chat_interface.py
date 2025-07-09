from langchain_ollama.llms import OllamaLLM
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.documents import Document
from vector import get_retriever, clear_vector_store
from colorama import Fore, Style, init
from typing import List
import sys
import os
import argparse

# Initialize colorama for colored terminal prompts
init(autoreset=True)

# Initialize the LLM
model = OllamaLLM(model="llama3.2")

# Define the structured prompt template
template = """
You are an intelligent assistant that helps users analyze and understand data from their CSV files, spreadsheets, or Google Sheets.

Here are relevant records from the dataset: {records}

Based on the information above, provide a helpful and accurate response to the following question: {question}

Note: The data structure and field names may vary depending on the uploaded file. Be adaptive in your responses.
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
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Client Tracker Q&A Assistant')
    parser.add_argument('data_source', nargs='?', help='Data source (CSV file or Google Sheets URL)')
    parser.add_argument('--clear', action='store_true', help='Clear existing vector store before loading new data')
    parser.add_argument('--force-refresh', action='store_true', help='Force refresh the vector store with new data')
    
    args = parser.parse_args()
    
    # Clear vector store if requested
    if args.clear:
        clear_vector_store()
    
    data_source = args.data_source
    
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
        
        # Ask if user wants to clear existing data
        clear_choice = input(f"\n{Fore.YELLOW}Clear existing data before loading? (y/N): {Style.RESET_ALL}").strip().lower()
        if clear_choice == 'y':
            clear_vector_store()
            args.force_refresh = True
    
    print(f"\n{Fore.GREEN}Loading data from: {data_source}{Style.RESET_ALL}")
    
    try:
        retriever = get_retriever(data_source, force_refresh=args.force_refresh)
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
