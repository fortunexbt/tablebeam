#!/usr/bin/env python3
"""
Test script for Google Sheets integration.
"""

from gsheet_loader import extract_sheet_id, get_sheet_csv_url, load_gsheet_as_csv
from colorama import Fore, Style, init

init(autoreset=True)

def test_google_sheets():
    """Test Google Sheets functionality with a public example sheet."""
    
    print(f"\n{Fore.CYAN}Testing Google Sheets Integration{Style.RESET_ALL}\n")
    
    # Test with a public Google Sheets example
    # This is Google's public example spreadsheet
    test_url = "https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/edit"
    
    print(f"Test URL: {test_url}")
    
    # Test ID extraction
    sheet_id = extract_sheet_id(test_url)
    print(f"\n{Fore.GREEN}✓ Extracted Sheet ID:{Style.RESET_ALL} {sheet_id}")
    
    # Test CSV URL generation
    csv_url = get_sheet_csv_url(sheet_id)
    print(f"{Fore.GREEN}✓ Generated CSV URL:{Style.RESET_ALL} {csv_url}")
    
    # Test loading the sheet
    try:
        print(f"\n{Fore.YELLOW}Loading Google Sheet...{Style.RESET_ALL}")
        df = load_gsheet_as_csv(test_url)
        print(f"{Fore.GREEN}✓ Successfully loaded!{Style.RESET_ALL}")
        print(f"\nDataFrame shape: {df.shape}")
        print(f"Columns: {', '.join(df.columns)}")
        print(f"\nFirst few rows:")
        print(df.head())
        
    except Exception as e:
        print(f"{Fore.RED}✗ Error loading sheet: {str(e)}{Style.RESET_ALL}")
        return False
    
    # Test with just the ID
    print(f"\n{Fore.CYAN}Testing with just Sheet ID...{Style.RESET_ALL}")
    try:
        df2 = load_gsheet_as_csv(sheet_id)
        print(f"{Fore.GREEN}✓ Successfully loaded using just ID!{Style.RESET_ALL}")
        assert df.equals(df2), "DataFrames should be identical"
        
    except Exception as e:
        print(f"{Fore.RED}✗ Error: {str(e)}{Style.RESET_ALL}")
        return False
    
    print(f"\n{Fore.GREEN}All tests passed! 🎉{Style.RESET_ALL}")
    return True


if __name__ == "__main__":
    # Run the test
    success = test_google_sheets()
    
    if success:
        print(f"\n{Fore.CYAN}You can now use Google Sheets URLs with the chat interface!{Style.RESET_ALL}")
        print("\nExample usage:")
        print('  python chat_interface.py "https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID/edit"')
    else:
        print(f"\n{Fore.RED}Some tests failed. Please check your setup.{Style.RESET_ALL}")