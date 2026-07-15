# Tablebeam + Google Sheets

Tablebeam can load a public Google Sheet through Google's CSV export endpoint.

1. In Google Sheets, choose **Share → Anyone with the link → Viewer**.
2. Start Tablebeam with `./start.sh`.
3. Choose **Google Sheet** in the sidebar, paste the full URL, and click **Load data**.

URLs with a tab identifier work:

```text
https://docs.google.com/spreadsheets/d/SHEET_ID/edit#gid=123
```

Tablebeam validates the downloaded table, shows its profile and preview, then performs local row search. It does not send the entire sheet to the model—only the selected rows and aggregate profile are included in the request.

If access fails, confirm the sharing setting and retry. Google Sheets is the explicit network path; CSV loading and model calls remain on the configured machine.
