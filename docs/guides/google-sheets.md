# Google Sheets Integration Guide

This guide explains how to use Google Sheets as a data source for the Spreadsheet Q&A Assistant.

## Prerequisites

- Google account
- Google Sheet with data (must be publicly accessible)

## Making Your Sheet Public

1. Open your Google Sheet
2. Click "Share" button
3. Change access to "Anyone with the link can view"
4. Copy the sharing link

## Supported URL Formats

The assistant accepts Google Sheets in several formats:

```bash
# Full URL
python src/chat_interface.py "https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/edit"

# With specific sheet/tab
python src/chat_interface.py "https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/edit#gid=123"

# Just the ID
python src/chat_interface.py "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms"
```

## Usage Methods

### 1. Command Line Argument
```bash
python src/chat_interface.py "YOUR_GOOGLE_SHEETS_URL"
```

### 2. Environment Variable
```bash
export CLIENT_DATA_SOURCE="YOUR_GOOGLE_SHEETS_URL"
python src/chat_interface.py
```

### 3. Interactive Prompt
```bash
python src/chat_interface.py
# Then enter the URL when prompted
```

## Data Refresh Options

When switching between different sheets or updating data:

```bash
# Clear all existing data before loading
python src/chat_interface.py --clear

# Force refresh with new data
python src/chat_interface.py --force-refresh
```

## Troubleshooting

### Common Issues

1. **"Access Denied" Error**
   - Ensure your sheet is set to "Anyone with the link can view"
   - Check the URL is correctly formatted

2. **"Invalid Sheet ID" Error**
   - Verify the sheet ID in your URL
   - Try using the full URL instead of just the ID

3. **Data Not Updating**
   - Use `--force-refresh` flag to reload data
   - Or use `--clear` to completely reset the vector store

## Best Practices

- Keep sheets reasonably sized (under 10,000 rows for best performance)
- Use clear column headers
- Avoid complex formulas that might not export well
- Consider using specific sheet tabs for different datasets

## Privacy Note

When using Google Sheets, the data is downloaded locally and processed on your machine. No data is sent to external services (unless using cloud deployment mode with Pinecone).