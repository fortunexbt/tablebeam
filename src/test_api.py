#!/usr/bin/env python3
"""
Simple test script to verify the API is working correctly.
Run this after starting the API server.
"""

import sys
import time
import httpx


def test_api(base_url="http://localhost:8000"):
    """Run basic API tests."""
    print(f"Testing API at {base_url}")
    print("=" * 50)
    
    # Test 1: Root endpoint
    print("\n1. Testing root endpoint...")
    try:
        response = httpx.get(f"{base_url}/")
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            print(f"   Response: {response.json()}")
            print("   ✓ Root endpoint working")
        else:
            print("   ✗ Root endpoint failed")
    except Exception as e:
        print(f"   ✗ Error: {e}")
        return False
    
    # Test 2: Health check
    print("\n2. Testing health endpoint...")
    try:
        response = httpx.get(f"{base_url}/health")
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Service status: {data['status']}")
            print(f"   Uptime: {data['uptime_seconds']:.2f} seconds")
            print("   ✓ Health check passed")
        else:
            print("   ✗ Health check failed")
    except Exception as e:
        print(f"   ✗ Error: {e}")
        return False
    
    # Test 3: Readiness check
    print("\n3. Testing readiness endpoint...")
    try:
        response = httpx.get(f"{base_url}/ready")
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Ready: {data['ready']}")
            print("   Component checks:")
            for component, status in data['checks'].items():
                print(f"     - {component}: {'✓' if status else '✗'}")
            print("   ✓ Readiness check passed")
        else:
            print("   ✗ Service not ready")
            print(f"   Response: {response.text}")
    except Exception as e:
        print(f"   ✗ Error: {e}")
        return False
    
    # Test 4: API Documentation
    print("\n4. Testing API documentation...")
    try:
        response = httpx.get(f"{base_url}/docs")
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            print("   ✓ API documentation available at /docs")
        else:
            print("   ✗ API documentation not available")
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    # Test 5: Query endpoint
    print("\n5. Testing query endpoint...")
    try:
        # Test with a simple query
        query_data = {
            "question": "What clients are currently in the system?",
            "context_limit": 5
        }
        
        start_time = time.time()
        response = httpx.post(
            f"{base_url}/api/v1/query",
            json=query_data,
            timeout=30.0
        )
        request_time = (time.time() - start_time) * 1000
        
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Question: {data['question']}")
            print(f"   Answer preview: {data['answer'][:100]}...")
            print(f"   Context documents: {data['context_count']}")
            print(f"   Server processing time: {data['processing_time_ms']:.2f}ms")
            print(f"   Total request time: {request_time:.2f}ms")
            print("   ✓ Query endpoint working")
        else:
            print("   ✗ Query failed")
            print(f"   Response: {response.text}")
    except Exception as e:
        print(f"   ✗ Error: {e}")
        return False
    
    # Test 6: Error handling
    print("\n6. Testing error handling...")
    try:
        # Send invalid query (empty)
        response = httpx.post(
            f"{base_url}/api/v1/query",
            json={"question": ""}
        )
        print(f"   Empty query status: {response.status_code}")
        if response.status_code == 422:
            print("   ✓ Validation error handled correctly")
        else:
            print("   ✗ Validation error not handled properly")
        
        # Send query with invalid context_limit
        response = httpx.post(
            f"{base_url}/api/v1/query",
            json={"question": "Test", "context_limit": 100}
        )
        print(f"   Invalid context limit status: {response.status_code}")
        if response.status_code == 422:
            print("   ✓ Parameter validation working")
        else:
            print("   ✗ Parameter validation not working")
            
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    # Test 7: Metrics endpoint
    print("\n7. Testing metrics endpoint...")
    try:
        response = httpx.get(f"{base_url}/metrics")
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Uptime: {data['uptime_seconds']:.2f} seconds")
            print("   ✓ Metrics endpoint working")
        else:
            print("   ✗ Metrics endpoint failed")
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    print("\n" + "=" * 50)
    print("API testing completed!")
    return True


if __name__ == "__main__":
    # Allow custom base URL as command line argument
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
    
    print("Client Tracker Assistant API - Test Suite")
    print("========================================")
    print(f"\nMake sure the API server is running at {base_url}")
    print("You can start it with: python api_server.py")
    print("\nPress Enter to start testing...")
    input()
    
    success = test_api(base_url)
    
    if success:
        print("\n✓ All basic tests completed successfully!")
    else:
        print("\n✗ Some tests failed. Please check the API server logs.")
        sys.exit(1)