#!/usr/bin/env python3
"""
Example client for the Client Tracker Assistant REST API
Demonstrates how to interact with the API endpoints.
"""

import asyncio
import json
import logging
import time
from typing import Optional, Dict, Any

import httpx
from httpx import AsyncClient, Response

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ClientTrackerAPIClient:
    """Client for interacting with the Client Tracker Assistant API."""
    
    def __init__(self, base_url: str = "http://localhost:8000", timeout: float = 30.0):
        """
        Initialize the API client.
        
        Args:
            base_url: The base URL of the API server
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session: Optional[AsyncClient] = None
    
    async def __aenter__(self):
        """Async context manager entry."""
        self.session = AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(self.timeout),
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.aclose()
    
    async def check_health(self) -> Dict[str, Any]:
        """
        Check the health status of the API.
        
        Returns:
            Dict containing health status information
        """
        response = await self.session.get("/health")
        response.raise_for_status()
        return response.json()
    
    async def check_ready(self) -> Dict[str, Any]:
        """
        Check if the API is ready to handle requests.
        
        Returns:
            Dict containing readiness status and component checks
        """
        response = await self.session.get("/ready")
        response.raise_for_status()
        return response.json()
    
    async def query(self, question: str, context_limit: Optional[int] = None) -> Dict[str, Any]:
        """
        Submit a query to the API.
        
        Args:
            question: The question to ask about client information
            context_limit: Optional limit on the number of context documents to use
        
        Returns:
            Dict containing the answer and metadata
        """
        payload = {"question": question}
        if context_limit is not None:
            payload["context_limit"] = context_limit
        
        response = await self.session.post(
            "/api/v1/query",
            json=payload,
            headers={"X-Request-ID": f"example-{time.time()}"}
        )
        response.raise_for_status()
        return response.json()
    
    async def get_metrics(self) -> Dict[str, Any]:
        """
        Get basic metrics from the API.
        
        Returns:
            Dict containing service metrics
        """
        response = await self.session.get("/metrics")
        response.raise_for_status()
        return response.json()


async def example_usage():
    """Demonstrate usage of the API client."""
    
    # Create client instance
    async with ClientTrackerAPIClient("http://localhost:8000") as client:
        
        # 1. Check health
        print("\n1. Checking API health...")
        try:
            health = await client.check_health()
            print(f"Health Status: {health['status']}")
            print(f"Environment: {health['environment']}")
            print(f"Uptime: {health['uptime_seconds']:.2f} seconds")
        except Exception as e:
            print(f"Health check failed: {e}")
            return
        
        # 2. Check readiness
        print("\n2. Checking API readiness...")
        try:
            ready = await client.check_ready()
            print(f"Ready: {ready['ready']}")
            print("Component checks:")
            for component, status in ready['checks'].items():
                print(f"  - {component}: {'✓' if status else '✗'}")
        except Exception as e:
            print(f"Readiness check failed: {e}")
            return
        
        # 3. Example queries
        example_questions = [
            "What clients are using Slack for communication?",
            "Which validators have the largest size?",
            "Tell me about client onboarding documentation status",
            "What actions are needed for pending clients?",
            "List all clients with their communication channels"
        ]
        
        print("\n3. Running example queries...")
        for i, question in enumerate(example_questions, 1):
            print(f"\n--- Query {i} ---")
            print(f"Question: {question}")
            
            try:
                start_time = time.time()
                result = await client.query(question, context_limit=10)
                
                print(f"Answer: {result['answer']}")
                print(f"Context documents used: {result['context_count']}")
                print(f"Processing time: {result['processing_time_ms']:.2f}ms")
                print(f"Client-side latency: {(time.time() - start_time) * 1000:.2f}ms")
                
            except Exception as e:
                print(f"Query failed: {e}")
        
        # 4. Get metrics
        print("\n4. Getting service metrics...")
        try:
            metrics = await client.get_metrics()
            print(f"Service uptime: {metrics['uptime_seconds']:.2f} seconds")
            print(f"Environment: {metrics['environment']}")
        except Exception as e:
            print(f"Failed to get metrics: {e}")


async def batch_query_example():
    """Demonstrate concurrent batch querying."""
    
    questions = [
        "What is the status of validator XYZ?",
        "Which clients need onboarding documents?",
        "List all enterprise-size clients",
        "What communication channels are being used?",
        "Which accounts have pending actions?"
    ]
    
    async with ClientTrackerAPIClient("http://localhost:8000") as client:
        print("\nRunning batch queries concurrently...")
        start_time = time.time()
        
        # Create tasks for concurrent execution
        tasks = [client.query(q) for q in questions]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        total_time = (time.time() - start_time) * 1000
        
        # Process results
        successful = 0
        for question, result in zip(questions, results):
            if isinstance(result, Exception):
                print(f"\n✗ Failed: {question}")
                print(f"  Error: {result}")
            else:
                successful += 1
                print(f"\n✓ Success: {question}")
                print(f"  Answer preview: {result['answer'][:100]}...")
                print(f"  Processing time: {result['processing_time_ms']:.2f}ms")
        
        print(f"\n--- Batch Summary ---")
        print(f"Total queries: {len(questions)}")
        print(f"Successful: {successful}")
        print(f"Failed: {len(questions) - successful}")
        print(f"Total time: {total_time:.2f}ms")
        print(f"Average time per query: {total_time / len(questions):.2f}ms")


def sync_example():
    """Synchronous example using httpx."""
    import httpx
    
    print("\nSynchronous API usage example...")
    
    with httpx.Client(base_url="http://localhost:8000", timeout=30.0) as client:
        # Health check
        response = client.get("/health")
        if response.status_code == 200:
            health = response.json()
            print(f"API Status: {health['status']}")
        
        # Simple query
        response = client.post(
            "/api/v1/query",
            json={"question": "What clients are currently active?"}
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"\nQuery Result:")
            print(f"Answer: {result['answer']}")
            print(f"Processing time: {result['processing_time_ms']:.2f}ms")
        else:
            print(f"Query failed with status {response.status_code}")


async def error_handling_example():
    """Demonstrate error handling."""
    
    async with ClientTrackerAPIClient("http://localhost:8000") as client:
        print("\nError handling examples...")
        
        # 1. Invalid query (too long)
        try:
            await client.query("x" * 2000)  # Exceeds max length
        except httpx.HTTPStatusError as e:
            print(f"\n1. Validation error handled: {e.response.status_code}")
            error_data = e.response.json()
            print(f"   Error: {error_data.get('error')}")
        
        # 2. Invalid context limit
        try:
            await client.query("Test question", context_limit=100)  # Exceeds limit
        except httpx.HTTPStatusError as e:
            print(f"\n2. Invalid parameter handled: {e.response.status_code}")
            error_data = e.response.json()
            print(f"   Error: {error_data.get('error')}")


if __name__ == "__main__":
    print("Client Tracker Assistant API - Example Client")
    print("=" * 50)
    
    # Run examples
    asyncio.run(example_usage())
    
    # Uncomment to run additional examples:
    # asyncio.run(batch_query_example())
    # sync_example()
    # asyncio.run(error_handling_example())
    
    print("\n" + "=" * 50)
    print("Examples completed!")