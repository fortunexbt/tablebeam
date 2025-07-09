#!/usr/bin/env python3
"""
Quick test to see available models and recommendations
"""

import subprocess
import sys
sys.path.append("src")

print("📊 Checking Ollama Models\n")

# Get available models
print("Installed models:")
try:
    result = subprocess.run(['ollama', 'list'], capture_output=True, text=True)
    if result.returncode == 0:
        print(result.stdout)
    else:
        print("❌ Failed to list models")
except Exception as e:
    print(f"❌ Error: {e}")

print("\n" + "="*50 + "\n")

# Show model recommendations
from model_selector_v2 import HardwareDetector, ModelRecommender

detector = HardwareDetector()
recommender = ModelRecommender(detector.info)
recommendations = recommender.recommend_models()

print(f"🖥️  Hardware: {recommendations['hardware_summary']}\n")

print("🤖 Recommended Models:")
print(f"  Embedding: {recommendations['embedding']['name']} ({recommendations['embedding']['size_mb']}MB)")
print(f"  LLM: {recommendations['llm']['name']} ({recommendations['llm']['size_gb']}GB)")

print("\n📦 All Available LLM Options (sorted by size):")
for name, info in ModelRecommender.LLM_MODELS.items():
    print(f"  {info['category']:5} | {info['size_gb']:4.1f}GB | {name}")

print("\nTo test the UI, run: streamlit run src/app.py")