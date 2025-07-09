from langchain_ollama import OllamaEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document
import pandas as pd
import os
import shutil
from typing import List, Union
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


def detect_primary_key(df: pd.DataFrame) -> str:
    """
    Intelligently detects the primary key column from the DataFrame.
    
    Priority order:
    1. Column named 'id' (case-insensitive)
    2. Column named 'name' (case-insensitive)
    3. Column containing 'client' or 'company' (case-insensitive)
    4. First column that appears to have unique or mostly unique values
    5. Fall back to the first column
    
    Args:
        df: The DataFrame to analyze
        
    Returns:
        The name of the detected primary key column
    """
    columns_lower = {col.lower(): col for col in df.columns}
    
    # Check for 'id' column
    if 'id' in columns_lower:
        return columns_lower['id']
    
    # Check for 'name' column
    if 'name' in columns_lower:
        return columns_lower['name']
    
    # Check for columns containing 'client' or 'company'
    for keyword in ['client', 'company', 'customer', 'account']:
        for col_lower, col_original in columns_lower.items():
            if keyword in col_lower:
                return col_original
    
    # Check for columns with high uniqueness (>80% unique values)
    for col in df.columns:
        if df[col].dtype == 'object':  # Only check string columns
            uniqueness_ratio = len(df[col].unique()) / len(df)
            if uniqueness_ratio > 0.8:
                return col
    
    # Fall back to first column
    return df.columns[0]


def create_documents(df: pd.DataFrame) -> List[Document]:
    """
    Creates LangChain Document objects from the DataFrame rows.
    
    Args:
        df: pandas DataFrame containing the data
        
    Returns:
        List of Document objects ready for vector storage
    """
    documents = []
    
    # Detect the primary key column
    primary_key_col = detect_primary_key(df)
    print(f"{Fore.YELLOW}Using '{primary_key_col}' as primary identifier{Style.RESET_ALL}")
    
    # Convert DataFrame to string representation for better searchability
    df_str = df.astype(str)
    
    for idx, row in df.iterrows():
        # Create a text representation of the row
        # Format: "ColumnName: Value" for each column, joined by commas
        row_text_parts = []
        metadata = {"row_index": idx}
        
        for col in df.columns:
            value = row[col]
            # Skip NaN values
            if pd.notna(value):
                row_text_parts.append(f"{col}: {value}")
                # Store all values in metadata for structured retrieval
                metadata[col] = str(value)
        
        # Join all parts into a single text
        page_content = ", ".join(row_text_parts)
        
        # Create document with primary key as the ID
        primary_key_value = str(row[primary_key_col]) if pd.notna(row[primary_key_col]) else f"row_{idx}"
        doc_id = f"doc_{primary_key_value}_{idx}"
        
        doc = Document(
            page_content=page_content,
            metadata=metadata,
            id=doc_id
        )
        documents.append(doc)
    
    print(f"{Fore.GREEN}Created {len(documents)} documents from {len(df)} rows{Style.RESET_ALL}")
    return documents


def setup_chroma_store(documents: List[Document], 
                      data_source: str,
                      force_refresh: bool = False,
                      k: int = 5,
                      embedding_model: str = "mxbai-embed-large") -> VectorStoreRetriever:
    """
    Sets up a Chroma vector store with the given documents.
    
    Args:
        documents: List of Document objects to store
        data_source: The source of the data (used for naming the collection)
        force_refresh: If True, clears existing data and recreates the store
        k: Number of documents to retrieve in searches
        embedding_model: The Ollama embedding model to use
        
    Returns:
        VectorStoreRetriever configured for similarity search
    """
    # Create embeddings using Ollama with specified model
    embeddings = OllamaEmbeddings(
        model=embedding_model,
        base_url=os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    )
    
    # Create a collection name based on the data source
    if data_source.startswith('http'):
        collection_name = "gsheet_data"
    else:
        collection_name = os.path.basename(data_source).replace('.csv', '').replace('.', '_')
    
    # Set up the database location
    db_location = f"./chroma_db_clients/{collection_name}"
    
    # Check if we need to clear due to embedding model change
    metadata_file = os.path.join(db_location, ".embedding_model")
    model_changed = False
    
    if os.path.exists(db_location) and os.path.exists(metadata_file):
        try:
            with open(metadata_file, 'r') as f:
                stored_model = f.read().strip()
                if stored_model != embedding_model:
                    model_changed = True
                    print(f"{Fore.YELLOW}Embedding model changed from {stored_model} to {embedding_model}{Style.RESET_ALL}")
        except Exception as e:
            logger.warning(f"Could not read embedding model metadata: {e}")
    
    # Clear existing data if requested or model changed
    if (force_refresh or model_changed) and os.path.exists(db_location):
        print(f"{Fore.YELLOW}Clearing existing vector store at {db_location}...{Style.RESET_ALL}")
        shutil.rmtree(db_location)
    
    # Check if we need to add documents
    add_documents = not os.path.exists(db_location) or force_refresh or model_changed

    try:
        vector_store = Chroma(
            collection_name=collection_name,
            persist_directory=db_location,
            embedding_function=embeddings,
        )

        if add_documents:
            print(f"{Fore.CYAN}Adding {len(documents)} documents to vector store...{Style.RESET_ALL}")
            vector_store.add_documents(documents, ids=[doc.id for doc in documents])
            print(f"{Fore.GREEN}Documents added successfully!{Style.RESET_ALL}")
            
            # Store the embedding model metadata
            os.makedirs(db_location, exist_ok=True)
            with open(metadata_file, 'w') as f:
                f.write(embedding_model)
        else:
            print(f"{Fore.CYAN}Using existing vector store with cached data{Style.RESET_ALL}")
            # Verify the vector store works with current embeddings
            try:
                # Try a simple similarity search to check compatibility
                test_query = "test"
                vector_store.similarity_search(test_query, k=1)
            except Exception as e:
                if "dimension" in str(e).lower():
                    print(f"{Fore.RED}Dimension mismatch detected: {e}{Style.RESET_ALL}")
                    print(f"{Fore.YELLOW}Clearing incompatible vector store...{Style.RESET_ALL}")
                    shutil.rmtree(db_location)
                    # Recreate with correct dimensions
                    vector_store = Chroma(
                        collection_name=collection_name,
                        persist_directory=db_location,
                        embedding_function=embeddings,
                    )
                    print(f"{Fore.CYAN}Adding {len(documents)} documents to vector store...{Style.RESET_ALL}")
                    vector_store.add_documents(documents, ids=[doc.id for doc in documents])
                    print(f"{Fore.GREEN}Documents added successfully!{Style.RESET_ALL}")
                    # Store the embedding model metadata
                    with open(metadata_file, 'w') as f:
                        f.write(embedding_model)
                else:
                    raise

    except Exception as e:
        logger.error(f"Error setting up Chroma store: {e}")
        # If any error, try to recover by clearing and recreating
        if os.path.exists(db_location):
            print(f"{Fore.YELLOW}Error detected, clearing and recreating vector store...{Style.RESET_ALL}")
            shutil.rmtree(db_location)
        
        vector_store = Chroma(
            collection_name=collection_name,
            persist_directory=db_location,
            embedding_function=embeddings,
        )
        print(f"{Fore.CYAN}Adding {len(documents)} documents to vector store...{Style.RESET_ALL}")
        vector_store.add_documents(documents, ids=[doc.id for doc in documents])
        print(f"{Fore.GREEN}Documents added successfully!{Style.RESET_ALL}")
        # Store the embedding model metadata
        os.makedirs(db_location, exist_ok=True)
        with open(metadata_file, 'w') as f:
            f.write(embedding_model)

    return vector_store.as_retriever(search_kwargs={"k": k})


def get_retriever(data_source: str = "client_tracking.csv", 
                  force_refresh: bool = False,
                  embedding_model: str = "mxbai-embed-large") -> VectorStoreRetriever:
    """
    Returns a vector store retriever using client data from the given source.
    
    Args:
        data_source: Either a local CSV file path or a Google Sheets URL
        force_refresh: If True, clears existing data and recreates the vector store
        embedding_model: The Ollama embedding model to use
        
    Returns:
        VectorStoreRetriever configured with the client data
    """
    # Load data
    df = load_client_data(data_source)
    analyze_dataframe(df)  # Show data structure
    docs = create_documents(df)
    
    # Create ChromaDB retriever
    logger.info("Using ChromaDB vector store")
    return setup_chroma_store(docs, data_source, force_refresh, embedding_model=embedding_model)