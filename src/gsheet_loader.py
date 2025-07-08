import re
import pandas as pd
from typing import Optional
import requests
from urllib.parse import urlparse, parse_qs
import logging

logger = logging.getLogger(__name__)


def extract_sheet_id(url: str) -> Optional[str]:
    """
    Extract Google Sheet ID from various URL formats.
    
    Supports:
    - https://docs.google.com/spreadsheets/d/{id}/edit
    - https://docs.google.com/spreadsheets/d/{id}/edit#gid=0
    - https://docs.google.com/spreadsheets/d/{id}
    """
    # Pattern to match Google Sheets URLs
    patterns = [
        r'docs\.google\.com/spreadsheets/d/([a-zA-Z0-9-_]+)',
        r'spreadsheets\.google\.com/.*[?&]key=([a-zA-Z0-9-_]+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    # If no pattern matches, assume the input might be just the ID
    if re.match(r'^[a-zA-Z0-9-_]+$', url):
        return url
    
    return None


def get_sheet_csv_url(sheet_id: str, gid: Optional[str] = None) -> str:
    """
    Convert Google Sheet ID to CSV export URL.
    
    Args:
        sheet_id: The Google Sheet ID
        gid: Optional sheet/tab ID (defaults to first sheet)
    
    Returns:
        CSV export URL
    """
    base_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
    if gid:
        base_url += f"&gid={gid}"
    return base_url


def extract_gid_from_url(url: str) -> Optional[str]:
    """Extract the gid (sheet ID) from a Google Sheets URL if present."""
    # Check for #gid= in the URL
    gid_match = re.search(r'#gid=(\d+)', url)
    if gid_match:
        return gid_match.group(1)
    
    # Check for gid in query parameters
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    if 'gid' in params:
        return params['gid'][0]
    
    return None


def load_gsheet_as_csv(url: str, timeout: int = 30) -> pd.DataFrame:
    """
    Load a Google Sheet as a pandas DataFrame.
    
    Args:
        url: Google Sheets URL or Sheet ID
        timeout: Request timeout in seconds
    
    Returns:
        pandas DataFrame
    
    Raises:
        ValueError: If the URL is invalid or the sheet cannot be accessed
        requests.RequestException: If there's a network error
    """
    # Extract sheet ID
    sheet_id = extract_sheet_id(url)
    if not sheet_id:
        raise ValueError(f"Could not extract Google Sheet ID from URL: {url}")
    
    # Extract GID if present
    gid = extract_gid_from_url(url)
    
    # Get CSV export URL
    csv_url = get_sheet_csv_url(sheet_id, gid)
    
    logger.info(f"Loading Google Sheet: {sheet_id}")
    if gid:
        logger.info(f"Using sheet/tab with gid: {gid}")
    
    try:
        # Make the request
        response = requests.get(csv_url, timeout=timeout)
        response.raise_for_status()
        
        # Check if we got HTML instead of CSV (usually means the sheet is private)
        content_type = response.headers.get('content-type', '')
        if 'text/html' in content_type:
            raise ValueError(
                "Could not access the Google Sheet. Make sure it's publicly readable. "
                "To make it public: Share → Change to 'Anyone with the link can view'"
            )
        
        # Parse CSV content
        from io import StringIO
        csv_content = StringIO(response.text)
        df = pd.read_csv(csv_content)
        
        logger.info(f"Successfully loaded {len(df)} rows from Google Sheet")
        return df
        
    except requests.exceptions.Timeout:
        raise ValueError(f"Timeout while loading Google Sheet (waited {timeout}s)")
    except requests.exceptions.RequestException as e:
        raise ValueError(f"Error loading Google Sheet: {str(e)}")


def validate_gsheet_data(df: pd.DataFrame, required_columns: Optional[list] = None) -> None:
    """
    Validate that the loaded Google Sheet has the expected structure.
    
    Args:
        df: The loaded DataFrame
        required_columns: List of required column names
    
    Raises:
        ValueError: If validation fails
    """
    if df.empty:
        raise ValueError("The Google Sheet is empty")
    
    if required_columns:
        missing_columns = set(required_columns) - set(df.columns)
        if missing_columns:
            raise ValueError(
                f"Missing required columns: {', '.join(missing_columns)}. "
                f"Found columns: {', '.join(df.columns)}"
            )


# Example usage and testing
if __name__ == "__main__":
    # Test URL extraction
    test_urls = [
        "https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/edit#gid=0",
        "https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/edit",
        "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms",
    ]
    
    for url in test_urls:
        sheet_id = extract_sheet_id(url)
        gid = extract_gid_from_url(url)
        print(f"URL: {url}")
        print(f"  Sheet ID: {sheet_id}")
        print(f"  GID: {gid}")
        print(f"  CSV URL: {get_sheet_csv_url(sheet_id, gid)}")
        print()