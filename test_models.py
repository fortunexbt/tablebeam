#!/usr/bin/env python3
"""
Test script to verify model selection and hardware detection
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent / "src"))

from model_selector_v2 import HardwareDetector, ModelRecommender
from model_backends import BackendManager
import json

def main():
    print("🔍 Testing Hardware Detection and Model Selection\n")
    
    # Test hardware detection
    detector = HardwareDetector()
    print("📊 Hardware Information:")
    print(json.dumps(detector.info, indent=2))
    print()
    
    # Test model recommendations
    recommender = ModelRecommender(detector.info)
    recommendations = recommender.recommend_models()
    
    print("🤖 Model Recommendations:")
    print(f"Hardware Summary: {recommendations['hardware_summary']}")
    print()
    
    print("📝 Embedding Model:")
    emb = recommendations['embedding']
    print(f"  Name: {emb['name']}")
    print(f"  Size: {emb['size_mb']}MB")
    print(f"  Quality: {emb['quality']}")
    print(f"  Reason: {emb['reason']}")
    print()
    
    print("💬 Language Model:")
    llm = recommendations['llm']
    print(f"  Name: {llm['name']}")
    print(f"  Size: {llm['size_gb']}GB")
    print(f"  Quality: {llm['quality']}")
    print(f"  Context: {llm['context']} tokens")
    print(f"  Reason: {llm['reason']}")
    print()
    
    if recommendations['notes']:
        print("💡 Optimization Tips:")
        for note in recommendations['notes']:
            print(f"  {note}")
        print()
    
    # Test backend availability
    print("🔧 Available Backends:")
    backend_manager = BackendManager()
    for backend in backend_manager.list_backends():
        print(f"  - {backend}")
    
    if backend_manager.is_mlx_available():
        print("\n✅ MLX backend is available for Apple Silicon optimization")
    else:
        print("\n❌ MLX backend not available (install with: pip install mlx-lm)")

if __name__ == "__main__":
    main()