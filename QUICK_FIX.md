# Quick Fix for psutil Error

The app is failing because `psutil` is missing. Here's how to fix it:

## Option 1: Quick Fix (Recommended)
```bash
# If you have the virtual environment active:
pip install psutil

# Or if running directly:
pip install psutil --user
```

## Option 2: Full Reinstall
```bash
# This will install all dependencies including psutil
./start.sh
```

## Option 3: Just Test Hardware Detection
```bash
# First install psutil
pip install psutil

# Then run the quick test
./quick_test.sh
```

## Testing After Fix

Once psutil is installed, you can:

1. **Run the app**:
   ```bash
   streamlit run src/app.py
   ```

2. **Check Model Settings**:
   - Open the sidebar
   - Expand "⚙️ Model Settings"
   - You should see your hardware info
   - You should see model recommendations

The error happened because we added hardware detection that uses `psutil` to check RAM and CPU info. Once installed, everything should work!