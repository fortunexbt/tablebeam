#!/usr/bin/env python3
"""
Utility to inspect the structure of a Google Sheet or CSV file.
"""

import sys
from colorama import Fore, Style, init
from gsheet_loader import load_gsheet_as_csv, extract_sheet_id
import pandas as pd

init(autoreset=True)

def inspect_data_source(source: str):
    """Inspect a data source and show its structure."""
    
    print(f"\n{Fore.CYAN}Data Source Inspector{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'='*50}{Style.RESET_ALL}\n")
    
    try:
        # Load the data
        if source.startswith('http') or extract_sheet_id(source):
            print(f"Loading Google Sheet: {source}")
            df = load_gsheet_as_csv(source)
        else:
            print(f"Loading CSV file: {source}")
            df = pd.read_csv(source)
        
        print(f"\n{Fore.GREEN}✓ Successfully loaded!{Style.RESET_ALL}")
        
        # Show basic info
        print(f"\n{Fore.YELLOW}Basic Information:{Style.RESET_ALL}")
        print(f"  • Rows: {len(df)}")
        print(f"  • Columns: {len(df.columns)}")
        
        # Show columns
        print(f"\n{Fore.YELLOW}Column Names:{Style.RESET_ALL}")
        for i, col in enumerate(df.columns, 1):
            print(f"  {i}. {col}")
        
        # Show data types
        print(f"\n{Fore.YELLOW}Column Data Types:{Style.RESET_ALL}")
        for col, dtype in df.dtypes.items():
            print(f"  • {col}: {dtype}")
        
        # Show sample data
        print(f"\n{Fore.YELLOW}Sample Data (first 3 rows):{Style.RESET_ALL}")
        print(df.head(3).to_string())
        
        # Check for expected columns
        print(f"\n{Fore.YELLOW}Compatibility Check:{Style.RESET_ALL}")
        expected_columns = ['Client', 'Type', 'Account', 'Communication Channel', 
                          'Update', 'Action', 'Assets', 'Onboarding Docs', 'Size', 'Notes']
        
        found = []
        missing = []
        
        for col in expected_columns:
            if col in df.columns:
                found.append(col)
            else:
                # Check case-insensitive
                found_alt = False
                for df_col in df.columns:
                    if col.lower() == df_col.lower():
                        found.append(f"{col} (found as '{df_col}')")
                        found_alt = True
                        break
                if not found_alt:
                    missing.append(col)
        
        if found:
            print(f"\n{Fore.GREEN}Found columns:{Style.RESET_ALL}")
            for col in found:
                print(f"  ✓ {col}")
        
        if missing:
            print(f"\n{Fore.YELLOW}Missing columns (will use defaults):{Style.RESET_ALL}")
            for col in missing:
                print(f"  • {col}")
        
        print(f"\n{Fore.CYAN}The assistant will adapt to your column structure!{Style.RESET_ALL}")
        
    except Exception as e:
        print(f"\n{Fore.RED}Error: {str(e)}{Style.RESET_ALL}")
        return False
    
    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"\n{Fore.YELLOW}Usage:{Style.RESET_ALL}")
        print(f"  python inspect_sheet.py <google_sheet_url_or_csv_path>")
        print(f"\n{Fore.YELLOW}Examples:{Style.RESET_ALL}")
        print(f"  python inspect_sheet.py https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID/edit")
        print(f"  python inspect_sheet.py client_tracking.csv")
        sys.exit(1)
    
    source = sys.argv[1]
    inspect_data_source(source)