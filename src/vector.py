from langchain_ollama import OllamaEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document
import pandas as pd
import os
from typing import List, Optional
from langchain_core.vectorstores import VectorStoreRetriever
from colorama import Fore, Style
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_client_data(filepath: str) -> pd.DataFrame:
    """
    Loads the client tracking CSV data into a pandas DataFrame.
    """
    return pd.read_csv(filepath)


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


def get_retriever(csv_path: str = "client_tracking.csv", 
                  vector_store_type: Optional[str] = None,
                  namespace: Optional[str] = None) -> VectorStoreRetriever:
    """
    Returns a vector store retriever using client data from the given CSV.
    
    Args:
        csv_path: Path to the client tracking CSV file
        vector_store_type: Type of vector store to use ('chroma' or 'pinecone').
                          If None, uses VECTOR_STORE_TYPE env var or defaults to 'chroma'
        namespace: Optional namespace for Pinecone (ignored for ChromaDB)
        
    Returns:
        VectorStoreRetriever instance
    """
    # Determine vector store type
    if vector_store_type is None:
        vector_store_type = os.environ.get("VECTOR_STORE_TYPE", "chroma").lower()
    
    # Load data
    df = load_client_data(csv_path)
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
        return setup_vector_store(docs)
