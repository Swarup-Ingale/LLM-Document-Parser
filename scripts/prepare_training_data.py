#!/usr/bin/env python3
import os
import sys
import pandas as pd
from pathlib import Path
import argparse

# Add the parent directory to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.document_parser import DocumentParser

def create_sample_csv_files():
    """Create sample CSV training files if they don't exist"""
    training_dir = Path("data/training_data")
    training_dir.mkdir(exist_ok=True, parents=True)
    
    # Sample invoice data
    invoice_data = {
        'text': [
            "INVOICE #INV-1001\nDate: 2023-01-15\nDue Date: 2023-02-15\nTotal: $1500.00\nTax: $120.00",
            "Invoice INV-1002\nDate: 01/20/2023\nAmount Due: $750.50\nTax: $60.04",
            "INVOICE\nInvoice Number: 1003\nDate: 2023-01-25\nTotal Amount: $2200.00\nVAT: $176.00"
        ],
        'document_type': ['invoice', 'invoice', 'invoice'],
        'source': ['sample', 'sample', 'sample']
    }
    
    # Sample receipt data
    receipt_data = {
        'text': [
            "RECEIPT\nStore: Walmart\nDate: 2023-01-15\nTotal: $45.67\nPayment: Credit Card",
            "Receipt #RCPT-2001\nDate: 01/16/2023\nAmount: $23.45\nPayment Method: Cash",
            "STORE RECEIPT\nDate: 2023-01-17\nTotal: $89.99\nPaid with: Debit Card"
        ],
        'document_type': ['receipt', 'receipt', 'receipt'],
        'source': ['sample', 'sample', 'sample']
    }
    
    # Sample contract data
    contract_data = {
        'text': [
            "CONTRACT AGREEMENT\nBetween ABC Corp and XYZ Inc\nEffective Date: 2023-01-01\nTerm: 2 years",
            "SERVICE AGREEMENT\nParties: Company A and Client B\nDate: 2023-02-01\nDuration: 1 year",
            "NON-DISCLOSURE AGREEMENT\nBetween Tech Solutions and Partner Corp\nDate: 2023-03-01"
        ],
        'document_type': ['contract', 'contract', 'contract'],
        'source': ['sample', 'sample', 'sample']
    }
    
    # Create DataFrames and save as CSV
    pd.DataFrame(invoice_data).to_csv(training_dir / "invoices_training.csv", index=False)
    pd.DataFrame(receipt_data).to_csv(training_dir / "receipts_training.csv", index=False)
    pd.DataFrame(contract_data).to_csv(training_dir / "contracts_training.csv", index=False)
    
    # Create combined training data
    combined_data = {
        'text': invoice_data['text'] + receipt_data['text'] + contract_data['text'],
        'document_type': invoice_data['document_type'] + receipt_data['document_type'] + contract_data['document_type'],
        'source': invoice_data['source'] + receipt_data['source'] + contract_data['source']
    }
    pd.DataFrame(combined_data).to_csv(training_dir / "all_training_data.csv", index=False)
    
    print("Sample CSV training files created:")
    print("  - data/training_data/invoices_training.csv")
    print("  - data/training_data/receipts_training.csv")
    print("  - data/training_data/contracts_training.csv")
    print("  - data/training_data/all_training_data.csv")

def create_image_directories():
    """Create directory structure for image training data"""
    image_dirs = [
        "data/training_data/images/invoices",
        "data/training_data/images/receipts", 
        "data/training_data/images/contracts"
    ]
    
    for dir_path in image_dirs:
        Path(dir_path).mkdir(exist_ok=True, parents=True)
        print(f"Created directory: {dir_path}")

def main():
    parser = argparse.ArgumentParser(description='Prepare training data structure')
    parser.add_argument('--create-samples', action='store_true', help='Create sample CSV files')
    parser.add_argument('--create-dirs', action='store_true', help='Create image directories')
    parser.add_argument('--all', action='store_true', help='Create everything')
    
    args = parser.parse_args()
    
    if args.all or args.create_samples:
        create_sample_csv_files()
    
    if args.all or args.create_dirs:
        create_image_directories()
    
    if not any([args.create_samples, args.create_dirs, args.all]):
        print("Please specify an option:")
        print("  --create-samples  Create sample CSV training files")
        print("  --create-dirs     Create image directories")
        print("  --all             Create everything")
        print("\nExample: python scripts/prepare_training_data.py --all")

if __name__ == "__main__":
    main()