#!/usr/bin/env python3
"""
Example script demonstrating Pinecone integration with client-tracker-assistant.
This shows how to use Pinecone for vector search and retrieval.
"""

import os
import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from vector import get_retriever
from pinecone_vector import PineconeConfig, PineconeVectorStore
from colorama import init, Fore, Style

# Initialize colorama for colored output
init(autoreset=True)


def example_basic_usage():
    """Basic example using the unified retriever interface"""
    print(f"\n{Fore.CYAN}=== Basic Pinecone Usage ==={Style.RESET_ALL}\n")
    
    # Set environment variable to use Pinecone
    os.environ["VECTOR_STORE_TYPE"] = "pinecone"
    
    # Make sure API key is set
    if not os.environ.get("PINECONE_API_KEY"):
        print(f"{Fore.RED}Error: PINECONE_API_KEY environment variable not set{Style.RESET_ALL}")
        print("Please set your Pinecone API key:")
        print("  export PINECONE_API_KEY=your-api-key-here")
        return
    
    try:
        # Get retriever (will use Pinecone based on env var)
        print("Initializing Pinecone retriever...")
        retriever = get_retriever("client_tracking.csv")
        
        # Perform searches
        queries = [
            "Find all enterprise clients",
            "Which clients use Slack for communication?",
            "Show me clients with onboarding documentation",
            "List financial services clients"
        ]
        
        for query in queries:
            print(f"\n{Fore.YELLOW}Query: {query}{Style.RESET_ALL}")
            results = retriever.get_relevant_documents(query)
            
            print(f"Found {len(results)} relevant documents:")
            for i, doc in enumerate(results[:3]):  # Show top 3
                client = doc.metadata.get('client', 'Unknown')
                print(f"  {i+1}. {Fore.GREEN}{client}{Style.RESET_ALL}")
                print(f"     Channel: {doc.metadata.get('channel', 'N/A')}")
                print(f"     Size: {doc.metadata.get('size', 'N/A')}")
    
    except Exception as e:
        print(f"{Fore.RED}Error: {e}{Style.RESET_ALL}")


def example_advanced_usage():
    """Advanced example using Pinecone directly"""
    print(f"\n{Fore.CYAN}=== Advanced Pinecone Usage ==={Style.RESET_ALL}\n")
    
    api_key = os.environ.get("PINECONE_API_KEY")
    if not api_key:
        print(f"{Fore.RED}Error: PINECONE_API_KEY not set{Style.RESET_ALL}")
        return
    
    try:
        # Create Pinecone configuration
        config = PineconeConfig(
            api_key=api_key,
            index_name="client-tracker",
            namespace="example"  # Use a separate namespace for examples
        )
        
        # Initialize vector store
        print("Initializing Pinecone vector store...")
        vector_store = PineconeVectorStore(config)
        
        # Get index statistics
        stats = vector_store.get_stats()
        print(f"\n{Fore.CYAN}Index Statistics:{Style.RESET_ALL}")
        print(f"  Total vectors: {stats['total_vectors']}")
        print(f"  Dimensions: {stats['dimensions']}")
        print(f"  Namespaces: {list(stats['namespaces'].keys())}")
        
        # Perform search with metadata filtering
        print(f"\n{Fore.YELLOW}Searching for Enterprise clients...{Style.RESET_ALL}")
        results = vector_store.search(
            query="large corporate clients with complex needs",
            top_k=5,
            filter={"size": "Enterprise"}
        )
        
        print(f"Found {len(results)} matches:")
        for i, match in enumerate(results):
            print(f"  {i+1}. Score: {match.score:.3f}")
            print(f"     Client: {match.metadata.get('client', 'Unknown')}")
            print(f"     Account: {match.metadata.get('account', 'N/A')}")
        
        # Demonstrate reranking
        if results:
            print(f"\n{Fore.YELLOW}Reranking results...{Style.RESET_ALL}")
            reranked = vector_store.rerank(
                query="large corporate clients with complex needs",
                matches=results,
                top_k=3
            )
            
            print("Reranked top 3:")
            for i, (match, score) in enumerate(reranked):
                print(f"  {i+1}. Rerank Score: {score:.3f}")
                print(f"     Client: {match.metadata.get('client', 'Unknown')}")
    
    except Exception as e:
        print(f"{Fore.RED}Error: {e}{Style.RESET_ALL}")


def example_namespace_management():
    """Example showing namespace usage for multi-tenancy"""
    print(f"\n{Fore.CYAN}=== Namespace Management Example ==={Style.RESET_ALL}\n")
    
    api_key = os.environ.get("PINECONE_API_KEY")
    if not api_key:
        print(f"{Fore.RED}Error: PINECONE_API_KEY not set{Style.RESET_ALL}")
        return
    
    try:
        namespaces = ["team-alpha", "team-beta", "team-gamma"]
        
        for namespace in namespaces:
            print(f"\n{Fore.YELLOW}Working with namespace: {namespace}{Style.RESET_ALL}")
            
            # Create retriever with specific namespace
            retriever = get_retriever(
                "client_tracking.csv",
                vector_store_type="pinecone",
                namespace=namespace
            )
            
            # Each namespace has isolated data
            results = retriever.get_relevant_documents("Show all clients")
            print(f"  Documents in namespace: {len(results)}")
            
            if results:
                print(f"  Sample client: {results[0].metadata.get('client', 'Unknown')}")
    
    except Exception as e:
        print(f"{Fore.RED}Error: {e}{Style.RESET_ALL}")


def main():
    """Run all examples"""
    print(f"{Fore.MAGENTA}{'='*60}{Style.RESET_ALL}")
    print(f"{Fore.MAGENTA}Pinecone Integration Examples{Style.RESET_ALL}")
    print(f"{Fore.MAGENTA}{'='*60}{Style.RESET_ALL}")
    
    # Check if running in example mode
    if len(sys.argv) > 1:
        example = sys.argv[1]
        if example == "basic":
            example_basic_usage()
        elif example == "advanced":
            example_advanced_usage()
        elif example == "namespace":
            example_namespace_management()
        else:
            print(f"{Fore.RED}Unknown example: {example}{Style.RESET_ALL}")
            print("Available examples: basic, advanced, namespace")
    else:
        # Run all examples
        example_basic_usage()
        example_advanced_usage()
        example_namespace_management()
        
        print(f"\n{Fore.GREEN}All examples completed!{Style.RESET_ALL}")
        print("\nTo run a specific example:")
        print("  python examples/pinecone_example.py basic")
        print("  python examples/pinecone_example.py advanced")
        print("  python examples/pinecone_example.py namespace")


if __name__ == "__main__":
    main()