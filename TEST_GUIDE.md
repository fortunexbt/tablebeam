# Testing Model Selection Features Locally

## Quick Start Test

```bash
# From the project root directory
./start.sh
```

This will:
1. Show your Apple Silicon chip detection (M1/M2/M3)
2. Display recommended models based on your RAM
3. Check if MLX is available
4. Launch the app

## Detailed Testing Steps

### 1. Test Hardware Detection

Look for these messages in the startup output:
```
🍎 Apple Silicon detected: M1 Pro
✨ Ollama automatically uses Metal GPU acceleration for optimal performance
💡 For even better performance, consider installing MLX:
   pip install mlx-lm
```

### 2. Test Model Settings UI

Once the app launches:

1. **Open Model Settings**:
   - Look in the left sidebar
   - Click "⚙️ Model Settings" to expand

2. **Check Hardware Info**:
   - Should show your chip (e.g., "M1 Pro with 16 GPU cores")
   - Shows available RAM
   - Click "View detailed hardware info" for more

3. **Check Recommendations**:
   - Should show recommended embedding model
   - Should show recommended language model
   - Both should say "Metal Optimized" on Apple Silicon

### 3. Test Model Selection

1. **Try Different Models**:
   - In Model Settings, use the dropdowns to select different models
   - Click "Apply Configuration"
   - The app should update without errors

2. **Download Missing Models**:
   - Select a model you don't have (e.g., "qwen2.5:7b-instruct-q4_K_M")
   - You'll see "Missing models: ..."
   - Click "Download Missing Models"
   - Watch the progress

### 4. Test Model Performance

1. **Load Data**:
   - Upload a CSV or use Google Sheets
   - Click "Load Data"

2. **Test Queries**:
   - Use the quick questions or type your own
   - Monitor GPU usage in Activity Monitor
   - You should see GPU activity under Ollama

### 5. Manual Hardware Detection Test

Create and run this test script:

```bash
# Save this as test_hardware.py in the project root
cat > test_hardware.py << 'EOF'
import sys
sys.path.append("src")
from model_selector_v2 import HardwareDetector, ModelRecommender

# Test hardware detection
detector = HardwareDetector()
print("Hardware Info:")
for key, value in detector.info.items():
    print(f"  {key}: {value}")

# Test recommendations
recommender = ModelRecommender(detector.info)
recs = recommender.recommend_models()
print(f"\nRecommended Models:")
print(f"  Embedding: {recs['embedding']['name']}")
print(f"  LLM: {recs['llm']['name']}")
print(f"\nOptimization Notes:")
for note in recs['notes']:
    print(f"  - {note}")
EOF

# Run it
python test_hardware.py
```

### 6. Verify Metal GPU Usage

While running queries:

1. **Open Activity Monitor**
2. **Go to Window → GPU History**
3. **Run queries in the app**
4. **You should see GPU usage spike**

### 7. Test Different RAM Scenarios

To simulate different RAM amounts, you can temporarily modify the detection:

```python
# In src/model_selector_v2.py, temporarily change line 22:
"available_ram_gb": 4,  # Simulate low RAM
```

Then restart the app to see different recommendations.

## Expected Results

### On Apple Silicon Mac:
- ✅ Detects specific chip (M1/M2/M3 variant)
- ✅ Shows unified memory and GPU cores
- ✅ Recommends Metal-optimized models
- ✅ Shows optimization tips
- ✅ GPU usage visible in Activity Monitor

### Model Recommendations by RAM:
- **< 4GB**: all-minilm + phi3:mini
- **4-8GB**: nomic-embed-text + llama3.2:3b
- **8GB+**: mxbai-embed-large + mistral:7b or qwen2.5:7b

## Common Issues

### "psutil not installed"
```bash
pip install psutil
```

### Models not downloading
```bash
# Manually download
ollama pull mxbai-embed-large
ollama pull llama3.2
```

### Can't see GPU usage
- Make sure Ollama is running: `ollama serve`
- Check Activity Monitor → Window → GPU History
- Run a query to trigger GPU usage

## Quick Validation Commands

```bash
# Check if on Apple Silicon
sysctl -n machdep.cpu.brand_string

# Check available RAM
python -c "import psutil; print(f'{psutil.virtual_memory().available / (1024**3):.1f}GB available')"

# Check Ollama models
ollama list

# Check if MLX is installed
python -c "import mlx; print('MLX is installed')" 2>/dev/null || echo "MLX not installed"
```

## Performance Testing

Compare query response times with different models:
1. Use phi3:mini (fastest, lowest quality)
2. Use llama3.2:3b (balanced)
3. Use mistral:7b (best quality, slower)

You should see Metal GPU acceleration working for all models on Apple Silicon!