#!/usr/bin/env python3
"""
Test script to verify the embedding dimension mismatch and quick questions fixes
"""
import os
import sys
import shutil
import pandas as pd
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent / 'src'))

from vector import get_retriever, load_client_data, create_documents
from colorama import Fore, Style, init

init(autoreset=True)

def test_embedding_dimension_fix():
    """Test that switching between embedding models with different dimensions works correctly"""
    print(f"\n{Fore.CYAN}=== Testing Embedding Dimension Fix ==={Style.RESET_ALL}")
    
    # Create test data
    test_data = pd.DataFrame({
        'id': [1, 2, 3],
        'name': ['Client A', 'Client B', 'Client C'],
        'value': [100, 200, 300]
    })
    
    # Save test data
    test_file = 'test_data.csv'
    test_data.to_csv(test_file, index=False)
    
    try:
        # Test 1: Create vector store with mxbai-embed-large (1024 dimensions)
        print(f"\n{Fore.YELLOW}Test 1: Creating vector store with mxbai-embed-large (1024 dims){Style.RESET_ALL}")
        retriever1 = get_retriever(test_file, force_refresh=True, embedding_model="mxbai-embed-large")
        results1 = retriever1.invoke("Client B")
        print(f"{Fore.GREEN}✓ Successfully created and queried with mxbai-embed-large{Style.RESET_ALL}")
        
        # Test 2: Switch to all-minilm (384 dimensions) without force_refresh
        print(f"\n{Fore.YELLOW}Test 2: Switching to all-minilm (384 dims) - should auto-detect and recreate{Style.RESET_ALL}")
        retriever2 = get_retriever(test_file, force_refresh=False, embedding_model="all-minilm")
        results2 = retriever2.invoke("Client B")
        print(f"{Fore.GREEN}✓ Successfully switched to all-minilm without manual refresh{Style.RESET_ALL}")
        
        # Test 3: Switch back to mxbai-embed-large
        print(f"\n{Fore.YELLOW}Test 3: Switching back to mxbai-embed-large (1024 dims){Style.RESET_ALL}")
        retriever3 = get_retriever(test_file, force_refresh=False, embedding_model="mxbai-embed-large")
        results3 = retriever3.invoke("Client B")
        print(f"{Fore.GREEN}✓ Successfully switched back to mxbai-embed-large{Style.RESET_ALL}")
        
        # Test 4: Use same model (should use cache)
        print(f"\n{Fore.YELLOW}Test 4: Using same model - should use cached data{Style.RESET_ALL}")
        retriever4 = get_retriever(test_file, force_refresh=False, embedding_model="mxbai-embed-large")
        results4 = retriever4.invoke("Client B")
        print(f"{Fore.GREEN}✓ Successfully used cached data{Style.RESET_ALL}")
        
        print(f"\n{Fore.GREEN}🎉 All embedding dimension tests passed!{Style.RESET_ALL}")
        
    except Exception as e:
        print(f"\n{Fore.RED}❌ Test failed: {e}{Style.RESET_ALL}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        if os.path.exists(test_file):
            os.remove(test_file)
        if os.path.exists('./chroma_db_clients/'):
            shutil.rmtree('./chroma_db_clients/')

def test_metadata_storage():
    """Test that embedding model metadata is correctly stored and retrieved"""
    print(f"\n{Fore.CYAN}=== Testing Metadata Storage ==={Style.RESET_ALL}")
    
    # Create test data
    test_data = pd.DataFrame({
        'id': [1],
        'name': ['Test Client']
    })
    
    test_file = 'test_metadata.csv'
    test_data.to_csv(test_file, index=False)
    
    try:
        # Create vector store
        print(f"\n{Fore.YELLOW}Creating vector store with metadata tracking{Style.RESET_ALL}")
        retriever = get_retriever(test_file, force_refresh=True, embedding_model="all-minilm")
        
        # Check metadata file exists
        metadata_file = "./chroma_db_clients/test_metadata/.embedding_model"
        if os.path.exists(metadata_file):
            with open(metadata_file, 'r') as f:
                stored_model = f.read().strip()
            print(f"{Fore.GREEN}✓ Metadata file created with model: {stored_model}{Style.RESET_ALL}")
            assert stored_model == "all-minilm", f"Expected 'all-minilm', got '{stored_model}'"
        else:
            print(f"{Fore.RED}❌ Metadata file not created{Style.RESET_ALL}")
            
        print(f"\n{Fore.GREEN}🎉 Metadata storage test passed!{Style.RESET_ALL}")
        
    except Exception as e:
        print(f"\n{Fore.RED}❌ Test failed: {e}{Style.RESET_ALL}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        if os.path.exists(test_file):
            os.remove(test_file)
        if os.path.exists('./chroma_db_clients/'):
            shutil.rmtree('./chroma_db_clients/')

def main():
    """Run all tests"""
    print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}Testing Embedding Dimension and Quick Questions Fixes{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
    
    # Check if required models are available
    print(f"\n{Fore.YELLOW}Checking required models...{Style.RESET_ALL}")
    required_models = ["mxbai-embed-large", "all-minilm"]
    
    try:
        import subprocess
        result = subprocess.run(['ollama', 'list'], capture_output=True, text=True)
        if result.returncode == 0:
            available_models = result.stdout.lower()
            missing = [m for m in required_models if m not in available_models]
            if missing:
                print(f"{Fore.YELLOW}Missing models: {', '.join(missing)}{Style.RESET_ALL}")
                print(f"{Fore.YELLOW}Please run: ollama pull {missing[0]}{Style.RESET_ALL}")
                return
        else:
            print(f"{Fore.YELLOW}Could not check Ollama models. Make sure Ollama is running.{Style.RESET_ALL}")
            return
    except Exception as e:
        print(f"{Fore.YELLOW}Could not check Ollama: {e}{Style.RESET_ALL}")
        return
    
    # Run tests
    test_metadata_storage()
    test_embedding_dimension_fix()
    
    print(f"\n{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
    print(f"{Fore.GREEN}All tests completed!{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}")

if __name__ == "__main__":
    main()