# Testing the Improved Model Selector

## What's New

1. **Better Model Organization**
   - Models sorted by size (Small → 3B → 7B → 13B)
   - Clear size indicators (MB/GB)
   - Context window shown (e.g., "128K context")
   - ✅ = Installed, ⬇️ = Needs download

2. **Live Download Progress**
   - Real-time download output
   - Progress bar showing overall completion
   - Individual model download status
   - Total download size estimate

3. **Improved UI**
   - Category grouping (Small, 3B, 7B, 13B models)
   - Refresh button to check for new models
   - Better visual feedback

## How to Test

### 1. Start the App
```bash
streamlit run src/app.py
```

### 2. Open Model Settings
- Look in the left sidebar
- Click "⚙️ Model Settings" to expand

### 3. Check the Model Lists
You should see:

**Embedding Models:**
- ✅ mxbai-embed-large (560MB, excellent)
- ⬇️ nomic-embed-text (274MB, good)
- ⬇️ all-minilm (45MB, basic)

**Language Models (grouped by size):**
```
--- Small Models ---
  ⬇️ qwen2.5:0.5b (0.4GB, 8K context)
  ⬇️ phi3:mini (2.2GB, 4K context)
--- 3B Models ---
  ✅ llama3.2:3b-instruct-q4_K_M (2.0GB, 8K context)
  ⬇️ llama3.2:3b-instruct-q8_0 (3.4GB, 8K context)
--- 7B Models ---
  ✅ mistral:7b-instruct-q4_K_M (4.1GB, 32K context)
  ⬇️ llama3.2:7b-instruct-q4_K_M (4.4GB, 8K context)
  ⬇️ qwen2.5:7b-instruct-q4_K_M (4.4GB, 128K context)
--- 13B Models ---
  ⬇️ mistral-nemo:12b-instruct-2407-q4_K_M (7.1GB, 128K context)
```

### 4. Test Model Download
1. Select a model with ⬇️ (not installed)
2. Click "📥 Download Missing Models"
3. Watch the live progress:
   - Progress bar fills up
   - Download output shows in real-time
   - Percentage updates as it downloads
   - Success/failure message when complete

### 5. Test Model Switching
1. Select different models from the dropdowns
2. Click "💾 Apply Configuration"
3. Load some data and run queries
4. Compare performance between models

## Expected Behavior

### Download Experience
- Shows total download size upfront
- Live terminal output during download
- Progress bar updates smoothly
- Clear success/failure indicators
- Auto-refreshes when complete

### Model Selection
- Current model highlighted in dropdown
- Categories make it easy to find models by size
- Icons show install status at a glance
- Smooth switching between models

## Testing Different Scenarios

### Test 1: Download Small Model
- Select "qwen2.5:0.5b" (only 0.4GB)
- Should download quickly
- Watch progress update

### Test 2: Download Large Model
- Select "mistral-nemo:12b" (7.1GB)
- See detailed progress updates
- May take 5-10 minutes

### Test 3: Multiple Downloads
- Select multiple uninstalled models
- See total size calculation
- Watch sequential downloads

### Test 4: Cancel and Resume
- Start a download
- Press Ctrl+C to cancel
- Restart and try again

## Troubleshooting

### "Model not showing as installed"
- Click the 🔄 Refresh button
- Check with `ollama list` in terminal

### "Download seems stuck"
- Check internet connection
- Try `ollama pull MODEL_NAME` manually
- Check disk space

### "Progress bar not updating"
- Some models don't report progress well
- Check the terminal output instead

## Performance Tips

1. **For Testing**: Start with small models (qwen2.5:0.5b)
2. **For Quality**: Use 7B models (mistral, qwen2.5)
3. **For Speed**: Use 3B models with Q4_K_M quantization
4. **For Best Results**: Match model to your RAM

The improved UI should make it much clearer which models you have, what you're downloading, and how the download is progressing!