#!/usr/bin/env python3
"""
Migration script to transfer data from ChromaDB to Pinecone.
This script reads existing embeddings from ChromaDB and migrates them to Pinecone.
"""

import os
import sys
import argparse
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import json

from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings
from langchain_core.documents import Document
from colorama import init, Fore, Style

from pinecone_vector import PineconeConfig, PineconeVectorStore

# Initialize colorama
init(autoreset=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ChromaToPineconeMigrator:
    """Handles migration of vector data from ChromaDB to Pinecone"""
    
    def __init__(self, 
                 chroma_path: str,
                 chroma_collection: str,
                 pinecone_api_key: str,
                 pinecone_index: str,
                 pinecone_namespace: Optional[str] = None,
                 embedding_model: str = "mxbai-embed-large"):
        """
        Initialize the migrator.
        
        Args:
            chroma_path: Path to ChromaDB persistence directory
            chroma_collection: Name of the ChromaDB collection
            pinecone_api_key: Pinecone API key
            pinecone_index: Name of the Pinecone index
            pinecone_namespace: Optional namespace for Pinecone
            embedding_model: Embedding model used in ChromaDB
        """
        self.chroma_path = chroma_path
        self.chroma_collection = chroma_collection
        self.embedding_model = embedding_model
        
        # Initialize Pinecone
        self.pinecone_config = PineconeConfig(
            api_key=pinecone_api_key,
            index_name=pinecone_index,
            namespace=pinecone_namespace
        )
        self.pinecone_store = PineconeVectorStore(self.pinecone_config)
        
        # Initialize ChromaDB
        self.embeddings = OllamaEmbeddings(model=embedding_model)
        self.chroma_store = Chroma(
            collection_name=chroma_collection,
            persist_directory=chroma_path,
            embedding_function=self.embeddings
        )
    
    def extract_documents_from_chroma(self) -> List[Document]:
        """Extract all documents from ChromaDB"""
        logger.info(f"{Fore.CYAN}Extracting documents from ChromaDB...{Style.RESET_ALL}")
        
        try:
            # Get all documents from ChromaDB
            # ChromaDB doesn't have a direct "get all" method, so we use a large search
            results = self.chroma_store.similarity_search("", k=10000)
            
            # If we got fewer results, try to get collection directly
            if len(results) < 100:  # Arbitrary threshold
                collection = self.chroma_store._collection
                all_data = collection.get()
                
                documents = []
                for i in range(len(all_data['ids'])):
                    doc = Document(
                        page_content=all_data['documents'][i] if all_data['documents'] else "",
                        metadata=all_data['metadatas'][i] if all_data['metadatas'] else {},
                        id=all_data['ids'][i]
                    )
                    documents.append(doc)
                
                logger.info(f"{Fore.GREEN}Extracted {len(documents)} documents from ChromaDB{Style.RESET_ALL}")
                return documents
            
            logger.info(f"{Fore.GREEN}Extracted {len(results)} documents from ChromaDB{Style.RESET_ALL}")
            return results
            
        except Exception as e:
            logger.error(f"{Fore.RED}Failed to extract documents from ChromaDB: {e}{Style.RESET_ALL}")
            raise
    
    def validate_migration(self, original_docs: List[Document]) -> Dict[str, Any]:
        """Validate that migration was successful"""
        logger.info(f"{Fore.CYAN}Validating migration...{Style.RESET_ALL}")
        
        validation_results = {
            "success": False,
            "original_count": len(original_docs),
            "migrated_count": 0,
            "sample_searches": [],
            "errors": []
        }
        
        try:
            # Get Pinecone stats
            stats = self.pinecone_store.get_stats()
            namespace_stats = stats.get('namespaces', {}).get(self.pinecone_config.namespace or '', {})
            validation_results["migrated_count"] = namespace_stats.get('vector_count', 0)
            
            # Check document count
            if validation_results["migrated_count"] != validation_results["original_count"]:
                validation_results["errors"].append(
                    f"Document count mismatch: {validation_results['original_count']} original vs "
                    f"{validation_results['migrated_count']} migrated"
                )
            
            # Perform sample searches
            sample_docs = original_docs[:min(5, len(original_docs))]
            for doc in sample_docs:
                # Extract a query from the document
                query = doc.metadata.get('client', doc.page_content[:50])
                
                # Search in Pinecone
                results = self.pinecone_store.search(query, top_k=1)
                
                validation_results["sample_searches"].append({
                    "query": query,
                    "found": len(results) > 0,
                    "top_result_score": results[0].score if results else 0
                })
            
            # Determine overall success
            validation_results["success"] = (
                validation_results["migrated_count"] == validation_results["original_count"] and
                all(search["found"] for search in validation_results["sample_searches"])
            )
            
            return validation_results
            
        except Exception as e:
            logger.error(f"{Fore.RED}Validation failed: {e}{Style.RESET_ALL}")
            validation_results["errors"].append(str(e))
            return validation_results
    
    def migrate(self, batch_size: int = 100, dry_run: bool = False) -> Dict[str, Any]:
        """
        Perform the migration from ChromaDB to Pinecone.
        
        Args:
            batch_size: Number of documents to process in each batch
            dry_run: If True, only simulate the migration without actually uploading
            
        Returns:
            Migration results dictionary
        """
        start_time = datetime.now()
        logger.info(f"{Fore.YELLOW}Starting migration from ChromaDB to Pinecone...{Style.RESET_ALL}")
        
        # Extract documents from ChromaDB
        documents = self.extract_documents_from_chroma()
        
        if dry_run:
            logger.info(f"{Fore.YELLOW}DRY RUN: Would migrate {len(documents)} documents{Style.RESET_ALL}")
            return {
                "dry_run": True,
                "document_count": len(documents),
                "estimated_batches": (len(documents) + batch_size - 1) // batch_size
            }
        
        # Update batch size in config
        self.pinecone_config.batch_size = batch_size
        
        # Perform migration
        logger.info(f"{Fore.CYAN}Uploading {len(documents)} documents to Pinecone...{Style.RESET_ALL}")
        upload_results = self.pinecone_store.upsert_documents(documents, show_progress=True)
        
        # Validate migration
        validation_results = self.validate_migration(documents)
        
        # Calculate duration
        duration = (datetime.now() - start_time).total_seconds()
        
        # Compile final results
        results = {
            "success": validation_results["success"],
            "duration_seconds": duration,
            "documents_processed": len(documents),
            "upload_results": upload_results,
            "validation": validation_results
        }
        
        # Print summary
        if results["success"]:
            logger.info(f"{Fore.GREEN}Migration completed successfully!{Style.RESET_ALL}")
            logger.info(f"  - Documents migrated: {results['documents_processed']}")
            logger.info(f"  - Duration: {duration:.2f} seconds")
            logger.info(f"  - Success rate: {upload_results['success_rate']*100:.1f}%")
        else:
            logger.error(f"{Fore.RED}Migration completed with errors!{Style.RESET_ALL}")
            for error in validation_results.get("errors", []):
                logger.error(f"  - {error}")
        
        return results


def main():
    """Main entry point for the migration script"""
    parser = argparse.ArgumentParser(
        description="Migrate vector data from ChromaDB to Pinecone"
    )
    
    # ChromaDB arguments
    parser.add_argument(
        "--chroma-path",
        default="./chroma_db_clients",
        help="Path to ChromaDB persistence directory"
    )
    parser.add_argument(
        "--chroma-collection",
        default="client_tracking",
        help="Name of the ChromaDB collection"
    )
    
    # Pinecone arguments
    parser.add_argument(
        "--pinecone-api-key",
        help="Pinecone API key (or set PINECONE_API_KEY env var)"
    )
    parser.add_argument(
        "--pinecone-index",
        default="client-tracker",
        help="Name of the Pinecone index"
    )
    parser.add_argument(
        "--pinecone-namespace",
        help="Optional namespace for Pinecone"
    )
    
    # Migration options
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Number of documents to process in each batch"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate migration without actually uploading"
    )
    parser.add_argument(
        "--embedding-model",
        default="mxbai-embed-large",
        help="Embedding model used in ChromaDB"
    )
    parser.add_argument(
        "--output-report",
        help="Path to save migration report JSON"
    )
    
    args = parser.parse_args()
    
    # Get Pinecone API key
    pinecone_api_key = args.pinecone_api_key or os.environ.get("PINECONE_API_KEY")
    if not pinecone_api_key:
        logger.error("Pinecone API key not provided. Use --pinecone-api-key or set PINECONE_API_KEY env var")
        sys.exit(1)
    
    # Check if ChromaDB exists
    if not os.path.exists(args.chroma_path):
        logger.error(f"ChromaDB path not found: {args.chroma_path}")
        sys.exit(1)
    
    # Create migrator
    migrator = ChromaToPineconeMigrator(
        chroma_path=args.chroma_path,
        chroma_collection=args.chroma_collection,
        pinecone_api_key=pinecone_api_key,
        pinecone_index=args.pinecone_index,
        pinecone_namespace=args.pinecone_namespace,
        embedding_model=args.embedding_model
    )
    
    # Perform migration
    try:
        results = migrator.migrate(
            batch_size=args.batch_size,
            dry_run=args.dry_run
        )
        
        # Save report if requested
        if args.output_report:
            with open(args.output_report, 'w') as f:
                json.dump(results, f, indent=2, default=str)
            logger.info(f"Migration report saved to: {args.output_report}")
        
        # Exit with appropriate code
        sys.exit(0 if results.get("success", False) else 1)
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()