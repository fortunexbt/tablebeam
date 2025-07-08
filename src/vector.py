from langchain_ollama import OllamaEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document
import pandas as pd
import os
from typing import List, Union
from langchain_core.vectorstores import VectorStoreRetriever
from colorama import Fore, Style
from gsheet_loader import load_gsheet_as_csv, extract_sheet_id


def load_client_data(source: str) -> pd.DataFrame:
    """
    Loads the client tracking data from a CSV file or Google Sheet.
    
    Args:
        source: Either a local CSV file path or a Google Sheets URL
        
    Returns:
        pandas DataFrame with the client data
    """
    # Check if it's a Google Sheets URL
    if source.startswith('http') or extract_sheet_id(source):
        print(f"{Fore.CYAN}Loading data from Google Sheet...{Style.RESET_ALL}")
        return load_gsheet_as_csv(source)
    else:
        # Local CSV file
        print(f"{Fore.CYAN}Loading data from local CSV: {source}{Style.RESET_ALL}")
        return pd.read_csv(source)


def create_documents(df: pd.DataFrame) -> List[Document]:
    """
    Converts a DataFrame into LangChain Document objects for vector storage.
    Colorizes the 'Client' line in the output for terminal visibility.
    """
    documents = []
    for i, row in df.iterrows():
        # Colorize the "Client" line for better visibility
        client_line = f"{Fore.YELLOW}Client: {row['Client']}{Style.RESET_ALL}"

        # Remaining content (no color)
        other_fields = f"""
        Type: {row['Type']}
        Account: {row['Account']}
        Communication Channel: {row['Communication Channel']}
        Update: {row['Update']}
        Action: {row['Action']}
        Assets: {row['Assets']}
        Onboarding Docs: {row['Onboarding Docs']}
        Size: {row['Size']}
        Notes: {row['Notes']}
        """.strip()

        # Combine lines
        page_content = f"{client_line}\n{other_fields}"

        document = Document(
            page_content=page_content,
            metadata={
                "client": row["Client"],
                "account": row["Account"],
                "channel": row["Communication Channel"],
                "size": row["Size"],
            },
            id=str(i),
        )
        documents.append(document)
    return documents


def setup_vector_store(
    documents: List[Document],
    db_location: str = "./chroma_db_clients",
    model_name: str = "mxbai-embed-large",
    collection_name: str = "client_tracking",
    k: int = 20,
) -> VectorStoreRetriever:
    """
    Sets up and returns a Chroma vector store retriever.
    """
    embeddings = OllamaEmbeddings(model=model_name)
    add_documents = not os.path.exists(db_location)

    vector_store = Chroma(
        collection_name=collection_name,
        persist_directory=db_location,
        embedding_function=embeddings,
    )

    if add_documents:
        vector_store.add_documents(documents, ids=[doc.id for doc in documents])

    return vector_store.as_retriever(search_kwargs={"k": k})


def get_retriever(data_source: str = "client_tracking.csv") -> VectorStoreRetriever:
    """
    Returns a vector store retriever using client data from the given source.
    
    Args:
        data_source: Either a local CSV file path or a Google Sheets URL
        
    Returns:
        VectorStoreRetriever configured with the client data
    """
    df = load_client_data(data_source)
    docs = create_documents(df)
    return setup_vector_store(docs)
