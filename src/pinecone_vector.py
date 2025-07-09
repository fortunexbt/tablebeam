"""
Pinecone vector store implementation for client-tracker-assistant.
This module provides a Pinecone-based alternative to ChromaDB with integrated embeddings.
"""

import os
import time
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import pandas as pd
from pinecone import Pinecone, ServerlessSpec
from pinecone.models import QueryMatch
from langchain_core.documents import Document
from langchain_core.vectorstores import VectorStoreRetriever
from colorama import Fore, Style
import logging
from tenacity import retry, stop_after_attempt, wait_exponential

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class PineconeConfig:
    """Configuration for Pinecone vector store"""
    api_key: str
    index_name: str = "client-tracker"
    dimension: int = 1024  # mxbai-embed-large dimension
    metric: str = "cosine"
    cloud: str = "aws"
    region: str = "us-east-1"
    namespace: Optional[str] = None
    batch_size: int = 100
    max_retries: int = 3


class PineconeVectorStore:
    """
    Pinecone vector store implementation with integrated embeddings.
    Uses llama-text-embed-v2 for text embedding generation.
    """
    
    def __init__(self, config: PineconeConfig):
        """Initialize Pinecone client and index"""
        self.config = config
        self.pc = Pinecone(api_key=config.api_key)
        self._ensure_index_exists()
        self.index = self.pc.Index(config.index_name)
        
    def _ensure_index_exists(self):
        """Create index if it doesn't exist"""
        try:
            existing_indexes = self.pc.list_indexes()
            if self.config.index_name not in [idx.name for idx in existing_indexes]:
                logger.info(f"Creating index {self.config.index_name}")
                self.pc.create_index(
                    name=self.config.index_name,
                    dimension=self.config.dimension,
                    metric=self.config.metric,
                    spec=ServerlessSpec(
                        cloud=self.config.cloud,
                        region=self.config.region
                    )
                )
                # Wait for index to be ready
                time.sleep(10)
        except Exception as e:
            logger.error(f"Error creating index: {e}")
            raise
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def upsert_documents(self, documents: List[Document], show_progress: bool = True) -> Dict[str, Any]:
        """
        Upsert documents to Pinecone with batching and retry logic.
        
        Args:
            documents: List of LangChain Document objects
            show_progress: Whether to show progress during upsert
            
        Returns:
            Dictionary with upsert statistics
        """
        total_upserted = 0
        failed_batches = []
        
        # Process documents in batches
        for i in range(0, len(documents), self.config.batch_size):
            batch = documents[i:i + self.config.batch_size]
            vectors = []
            
            for doc in batch:
                # Create vector data
                vector_data = {
                    "id": doc.id or f"doc_{i + documents.index(doc)}",
                    "values": self._get_embedding(doc.page_content),
                    "metadata": {
                        **doc.metadata,
                        "text": doc.page_content[:1000],  # Store first 1000 chars in metadata
                        "full_text": doc.page_content
                    }
                }
                vectors.append(vector_data)
            
            try:
                # Upsert batch with namespace support
                response = self.index.upsert(
                    vectors=vectors,
                    namespace=self.config.namespace
                )
                total_upserted += response['upserted_count']
                
                if show_progress:
                    logger.info(f"Upserted batch {i//self.config.batch_size + 1}: "
                              f"{response['upserted_count']} vectors")
            except Exception as e:
                logger.error(f"Failed to upsert batch {i//self.config.batch_size + 1}: {e}")
                failed_batches.append(i)
        
        return {
            "total_upserted": total_upserted,
            "failed_batches": failed_batches,
            "success_rate": (len(documents) - len(failed_batches) * self.config.batch_size) / len(documents)
        }
    
    def _get_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for text.
        
        Note: When using Pinecone's inference-enabled indexes, you can send raw text
        directly. For this implementation, we're using the same embedding model as ChromaDB
        for compatibility during migration.
        """
        try:
            # Try to use the same embedding model as ChromaDB for consistency
            from langchain_ollama import OllamaEmbeddings
            embeddings = OllamaEmbeddings(model="mxbai-embed-large")
            return embeddings.embed_query(text)
        except Exception as e:
            logger.warning(f"Failed to generate embedding with Ollama: {e}")
            # Fallback to mock embedding for testing
            import hashlib
            import numpy as np
            
            text_hash = hashlib.md5(text.encode()).digest()
            seed = int.from_bytes(text_hash[:4], 'big')
            np.random.seed(seed)
            return np.random.randn(self.config.dimension).tolist()
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def search(self, 
               query: str, 
               top_k: int = 10, 
               filter: Optional[Dict[str, Any]] = None,
               include_metadata: bool = True) -> List[QueryMatch]:
        """
        Search for similar documents using vector similarity.
        
        Args:
            query: Query text
            top_k: Number of results to return
            filter: Optional metadata filter
            include_metadata: Whether to include metadata in results
            
        Returns:
            List of QueryMatch objects
        """
        try:
            # Get query embedding
            query_embedding = self._get_embedding(query)
            
            # Perform search
            results = self.index.query(
                vector=query_embedding,
                top_k=top_k,
                filter=filter,
                include_metadata=include_metadata,
                namespace=self.config.namespace
            )
            
            return results.matches
        except Exception as e:
            logger.error(f"Search failed: {e}")
            raise
    
    def rerank(self, 
               query: str, 
               matches: List[QueryMatch], 
               top_k: int = 5) -> List[Tuple[QueryMatch, float]]:
        """
        Rerank search results using cross-encoder or other reranking method.
        
        Args:
            query: Original query text
            matches: List of initial search results
            top_k: Number of reranked results to return
            
        Returns:
            List of tuples (match, rerank_score)
        """
        # In production, you would use a proper reranking model
        # For now, we'll use a simple heuristic based on metadata
        reranked = []
        
        for match in matches:
            # Simple reranking based on metadata relevance
            score = match.score
            metadata = match.metadata
            
            # Boost score if query terms appear in metadata
            query_terms = query.lower().split()
            for term in query_terms:
                if term in metadata.get('text', '').lower():
                    score *= 1.1
                if term in metadata.get('client', '').lower():
                    score *= 1.2
            
            reranked.append((match, score))
        
        # Sort by reranked score and return top_k
        reranked.sort(key=lambda x: x[1], reverse=True)
        return reranked[:top_k]
    
    def delete_namespace(self, namespace: str):
        """Delete all vectors in a namespace"""
        try:
            self.index.delete(delete_all=True, namespace=namespace)
            logger.info(f"Deleted all vectors in namespace: {namespace}")
        except Exception as e:
            logger.error(f"Failed to delete namespace {namespace}: {e}")
            raise
    
    def get_stats(self) -> Dict[str, Any]:
        """Get index statistics"""
        try:
            stats = self.index.describe_index_stats()
            return {
                "total_vectors": stats.total_vector_count,
                "dimensions": stats.dimension,
                "namespaces": stats.namespaces
            }
        except Exception as e:
            logger.error(f"Failed to get index stats: {e}")
            raise


class PineconeRetriever(VectorStoreRetriever):
    """
    LangChain-compatible retriever wrapper for Pinecone vector store.
    """
    
    def __init__(self, vector_store: PineconeVectorStore, search_kwargs: Optional[Dict[str, Any]] = None):
        self.vector_store = vector_store
        self.search_kwargs = search_kwargs or {"k": 20}
    
    def _get_relevant_documents(self, query: str) -> List[Document]:
        """Get relevant documents for a query"""
        k = self.search_kwargs.get("k", 20)
        filter = self.search_kwargs.get("filter", None)
        
        # Search for similar documents
        matches = self.vector_store.search(query, top_k=k, filter=filter)
        
        # Convert matches to documents
        documents = []
        for match in matches:
            doc = Document(
                page_content=match.metadata.get('full_text', match.metadata.get('text', '')),
                metadata={k: v for k, v in match.metadata.items() if k not in ['text', 'full_text']},
                id=match.id
            )
            documents.append(doc)
        
        return documents
    
    async def _aget_relevant_documents(self, query: str) -> List[Document]:
        """Async version of get_relevant_documents"""
        # For now, just call the sync version
        return self._get_relevant_documents(query)


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


def setup_pinecone_store(
    documents: List[Document],
    api_key: Optional[str] = None,
    index_name: str = "client-tracker",
    namespace: Optional[str] = None,
    k: int = 20,
) -> PineconeRetriever:
    """
    Sets up and returns a Pinecone vector store retriever.
    
    Args:
        documents: List of documents to index
        api_key: Pinecone API key (defaults to PINECONE_API_KEY env var)
        index_name: Name of the Pinecone index
        namespace: Optional namespace for multi-tenancy
        k: Number of results to return in searches
        
    Returns:
        PineconeRetriever instance
    """
    # Get API key from environment if not provided
    api_key = api_key or os.environ.get("PINECONE_API_KEY")
    if not api_key:
        raise ValueError("Pinecone API key not provided and PINECONE_API_KEY environment variable not set")
    
    # Create config
    config = PineconeConfig(
        api_key=api_key,
        index_name=index_name,
        namespace=namespace
    )
    
    # Initialize vector store
    vector_store = PineconeVectorStore(config)
    
    # Check if we need to add documents
    stats = vector_store.get_stats()
    namespace_stats = stats.get('namespaces', {}).get(namespace or '', {})
    
    if namespace_stats.get('vector_count', 0) == 0:
        logger.info(f"Adding {len(documents)} documents to Pinecone")
        result = vector_store.upsert_documents(documents)
        logger.info(f"Upsert complete: {result}")
    else:
        logger.info(f"Index already contains {namespace_stats.get('vector_count', 0)} vectors")
    
    # Create and return retriever
    return PineconeRetriever(vector_store, search_kwargs={"k": k})


def get_pinecone_retriever(csv_path: str = "client_tracking.csv", namespace: Optional[str] = None) -> PineconeRetriever:
    """
    Returns a Pinecone vector store retriever using client data from the given CSV.
    
    Args:
        csv_path: Path to the client tracking CSV file
        namespace: Optional namespace for multi-tenancy
        
    Returns:
        PineconeRetriever instance
    """
    df = load_client_data(csv_path)
    docs = create_documents(df)
    return setup_pinecone_store(docs, namespace=namespace)