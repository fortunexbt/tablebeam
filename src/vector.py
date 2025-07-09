from langchain_ollama import OllamaEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document
import pandas as pd
import os
import shutil
from typing import List, Union, Optional
from langchain_core.vectorstores import VectorStoreRetriever
from colorama import Fore, Style
from gsheet_loader import load_gsheet_as_csv, extract_sheet_id
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def analyze_dataframe(df: pd.DataFrame) -> None:
    """
    Analyzes and prints information about the DataFrame structure.
    """
    print(f"\n{Fore.CYAN}=== Data Analysis ==={Style.RESET_ALL}")
    print(f"Total rows: {len(df)}")
    print(f"Total columns: {len(df.columns)}")
    print(f"\nColumn names and types:")
    for col in df.columns:
        non_null = df[col].notna().sum()
        print(f"  - {col}: {df[col].dtype} ({non_null}/{len(df)} non-null values)")
    print(f"{Fore.CYAN}==================={Style.RESET_ALL}\n")


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
    if df.empty:
        raise ValueError("The spreadsheet is empty")
    
    if len(df.columns) == 0:
        raise ValueError("The spreadsheet has no columns")
    
    documents = []
    columns = df.columns.tolist()
    
    # Identify potential primary key columns (for highlighting)
    primary_keys = ['id', 'name', 'client', 'company', 'title', 'subject', 'product']
    primary_col = None
    
    # Find the first column that might be a primary identifier
    for col in columns:
        if col.lower() in primary_keys:
            primary_col = col
            break
    
    # If no primary key found, use the first column
    if not primary_col and columns:
        primary_col = columns[0]
    
    print(f"\n{Fore.CYAN}Detected {len(columns)} columns: {', '.join(columns[:5])}{' ...' if len(columns) > 5 else ''}{Style.RESET_ALL}")
    if primary_col:
        print(f"{Fore.YELLOW}Using '{primary_col}' as primary identifier{Style.RESET_ALL}")
    
    for i, row in df.iterrows():
        # Build the document content dynamically
        content_lines = []
        
        # Add primary field with highlighting if it exists
        if primary_col and pd.notna(row.get(primary_col)):
            content_lines.append(f"{Fore.YELLOW}{primary_col}: {row[primary_col]}{Style.RESET_ALL}")
        
        # Add all other fields
        for col in columns:
            if col != primary_col and pd.notna(row.get(col)):
                # Clean the value and skip if empty
                value = str(row[col]).strip()
                if value and value.lower() not in ['nan', 'none', '']:
                    content_lines.append(f"{col}: {value}")
        
        # Combine all lines into page content
        page_content = "\n".join(content_lines)
        
        # Build metadata dynamically
        metadata = {"row_index": i}
        
        # Add important fields to metadata for better search
        metadata_candidates = ['id', 'name', 'client', 'company', 'type', 'category', 
                              'status', 'date', 'created', 'updated', 'size', 'account']
        
        for col in columns:
            if col.lower() in metadata_candidates and pd.notna(row.get(col)):
                # Use lowercase keys for metadata
                metadata[col.lower()] = str(row[col])
        
        # Create document only if there's content
        if page_content.strip():
            document = Document(
                page_content=page_content,
                metadata=metadata,
                id=f"row_{i}",
            )
            documents.append(document)
    
    print(f"{Fore.GREEN}✓ Created {len(documents)} documents from {len(df)} rows{Style.RESET_ALL}")
    print(f"{Fore.CYAN}You can now ask questions about any information in your spreadsheet!{Style.RESET_ALL}")
    
    return documents


def clear_vector_store(db_location: str = "./chroma_db_clients") -> None:
    """
    Clears the vector store by removing the database directory.
    
    Args:
        db_location: Path to the Chroma database directory
    """
    if os.path.exists(db_location):
        print(f"{Fore.YELLOW}Clearing vector store at {db_location}...{Style.RESET_ALL}")
        shutil.rmtree(db_location)
        print(f"{Fore.GREEN}Vector store cleared successfully!{Style.RESET_ALL}")
    else:
        print(f"{Fore.CYAN}No existing vector store found at {db_location}{Style.RESET_ALL}")


def setup_vector_store(
    documents: List[Document],
    db_location: str = "./chroma_db_clients",
    model_name: str = "mxbai-embed-large",
    collection_name: str = "client_tracking",
    k: int = 20,
    force_refresh: bool = False,
) -> VectorStoreRetriever:
    """
    Sets up and returns a Chroma vector store retriever.
    
    Args:
        documents: List of documents to add to the vector store
        db_location: Path to the Chroma database directory
        model_name: Name of the Ollama embedding model
        collection_name: Name of the Chroma collection
        k: Number of documents to retrieve
        force_refresh: If True, clears existing data and recreates the vector store
    """
    embeddings = OllamaEmbeddings(model=model_name)
    
    # Clear existing data if force_refresh is True
    if force_refresh:
        clear_vector_store(db_location)
    
    add_documents = not os.path.exists(db_location) or force_refresh

    vector_store = Chroma(
        collection_name=collection_name,
        persist_directory=db_location,
        embedding_function=embeddings,
    )

    if add_documents:
        print(f"{Fore.CYAN}Adding {len(documents)} documents to vector store...{Style.RESET_ALL}")
        vector_store.add_documents(documents, ids=[doc.id for doc in documents])
        print(f"{Fore.GREEN}Documents added successfully!{Style.RESET_ALL}")
    else:
        print(f"{Fore.CYAN}Using existing vector store with cached data{Style.RESET_ALL}")

    return vector_store.as_retriever(search_kwargs={"k": k})


def get_retriever(data_source: str = "client_tracking.csv", 
                  force_refresh: bool = False,
                  vector_store_type: Optional[str] = None,
                  namespace: Optional[str] = None) -> VectorStoreRetriever:
    """
    Returns a vector store retriever using client data from the given source.
    
    Args:
        data_source: Either a local CSV file path or a Google Sheets URL
        force_refresh: If True, clears existing data and recreates the vector store
        vector_store_type: Type of vector store to use ('chroma' or 'pinecone').
                          If None, uses VECTOR_STORE_TYPE env var or defaults to 'chroma'
        namespace: Optional namespace for Pinecone (ignored for ChromaDB)
        
    Returns:
        VectorStoreRetriever configured with the client data
    """
    # Determine vector store type
    if vector_store_type is None:
        vector_store_type = os.environ.get("VECTOR_STORE_TYPE", "chroma").lower()
    
    # Load data
    df = load_client_data(data_source)
    analyze_dataframe(df)  # Show data structure
    docs = create_documents(df)
    
    # Create appropriate retriever
    if vector_store_type == "pinecone":
        logger.info("Using Pinecone vector store")
        try:
            from .pinecone_vector import setup_pinecone_store
            return setup_pinecone_store(docs, namespace=namespace)
        except ImportError:
            logger.error("Pinecone dependencies not installed. Please install pinecone-client.")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize Pinecone: {e}")
            raise
    else:
        logger.info("Using ChromaDB vector store")
        return setup_vector_store(docs, force_refresh=force_refresh)
