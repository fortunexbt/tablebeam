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
    Works with ANY spreadsheet structure - adapts to whatever columns are present.
    """
    # First, let's check what columns we have
    print(f"\n{Fore.CYAN}Detected {len(df.columns)} columns: {', '.join(df.columns[:5])}{' ...' if len(df.columns) > 5 else ''}{Style.RESET_ALL}")
    
    if df.empty:
        raise ValueError("The spreadsheet is empty")
    
    if len(df.columns) == 0:
        raise ValueError("The spreadsheet has no columns")
    
    documents = []
    
    # Use the first column as the primary identifier
    primary_key = df.columns[0]
    print(f"{Fore.GREEN}Using '{primary_key}' as the primary identifier{Style.RESET_ALL}")
    
    # Create a document for each row
    for i, row in df.iterrows():
        # Get the primary identifier value
        primary_value = str(row[primary_key]) if pd.notna(row[primary_key]) else f"Row {i+1}"
        
        # Create the header line with color
        header_line = f"{Fore.YELLOW}{primary_key}: {primary_value}{Style.RESET_ALL}"
        
        # Build the content from all columns
        field_lines = []
        for col in df.columns:
            if col != primary_key:  # Skip the primary key as it's already in the header
                value = row[col]
                if pd.notna(value) and str(value).strip():  # Only include non-empty values
                    field_lines.append(f"{col}: {value}")
        
        # Combine all fields
        if field_lines:
            other_fields = "\n        ".join(field_lines)
            page_content = f"{header_line}\n        {other_fields}"
        else:
            page_content = header_line
        
        # Create metadata - include first few columns that have values
        metadata = {
            "id": str(i),
            "primary_key": primary_key,
            "primary_value": primary_value
        }
        
        # Add first few columns to metadata for filtering
        metadata_cols = 0
        for col in df.columns[:5]:  # Limit to first 5 columns for metadata
            if pd.notna(row[col]):
                # Clean column name for metadata key
                clean_col = col.lower().replace(" ", "_").replace("-", "_")
                metadata[clean_col] = str(row[col])
                metadata_cols += 1
        
        document = Document(
            page_content=page_content,
            metadata=metadata,
            id=str(i),
        )
        documents.append(document)
    
    print(f"{Fore.GREEN}✓ Created {len(documents)} documents from your data{Style.RESET_ALL}")
    print(f"{Fore.CYAN}You can now ask questions about any information in your spreadsheet!{Style.RESET_ALL}")
    
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
