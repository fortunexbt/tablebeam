# Google Sheets guide

The Streamlit app can load a public Google Sheet through its CSV export endpoint. The sheet must be shared as **Anyone with the link can view**.

## Use the app

```bash
./start.sh
```

In the sidebar, choose **Google Sheets URL**, paste a URL such as:

```text
https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/edit#gid=123
```

The app validates the URL, downloads the selected tab as CSV, profiles the result, and indexes it locally. It supports a full edit URL, a URL with `gid`, or a plain sheet ID.

## Troubleshooting

- **Access denied or HTML returned:** make the sheet publicly viewable and retry.
- **Invalid URL:** use the full `docs.google.com/spreadsheets/d/...` URL or a plain sheet ID.
- **Stale results:** use **Clear local cache** in the sidebar, then load the sheet again.
- **Large or malformed data:** check the header row, remove empty trailing ranges, and keep the source under the app's 250,000-row/100 MB safety limits.

## Privacy

Google Sheets is the explicit network path: the selected sheet is downloaded from Google. After download, validation, embeddings, and local model inference run on the configured machine. Protect the local Chroma directory because it contains embeddings and source metadata.
