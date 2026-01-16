#!/usr/bin/env python3
import pandas as pd
import os
import sys
from pathlib import Path

# Add the parent directory to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def convert_invoice_csv_to_training(input_csv, output_csv):
    """Convert invoice data CSV to training format with text and document_type"""
    
    # Read the input CSV
    df = pd.read_csv(input_csv)
    
    # Create training data format
    training_data = []
    
    for idx, row in df.iterrows():
        # Generate realistic invoice text from the row data
        invoice_text = f"""
        INVOICE
        
        Bill To:
        {row['first_name']} {row['last_name']}
        {row['address']}
        {row['city']}
        
        Contact: {row['email']}
        
        Invoice Date: {row['invoice_date']}
        
        Product Details:
        Product ID: {row['product_id']}
        Quantity: {row['qty']}
        Unit Price: ${row['amount']/row['qty']:.2f}
        Amount: ${row['amount']}
        
        Stock Code: {row['stock_code']}
        Job: {row['job']}
        
        Subtotal: ${row['amount']}
        Tax: ${row['amount'] * 0.1:.2f}
        Total: ${row['amount'] * 1.1:.2f}
        
        Payment Terms: Net 30
        Thank you for your business!
        """
        
        training_data.append({
            'text': invoice_text,
            'document_type': 'invoice',
            'first_name': row['first_name'],
            'last_name': row['last_name'],
            'email': row['email'],
            'product_id': row['product_id'],
            'qty': row['qty'],
            'amount': row['amount'],
            'invoice_date': row['invoice_date'],
            'address': row['address'],
            'city': row['city'],
            'stock_code': row['stock_code'],
            'job': row['job']
        })
    
    # Create output DataFrame
    output_df = pd.DataFrame(training_data)
    
    # Save to output CSV
    output_df.to_csv(output_csv, index=False)
    print(f"Converted {len(output_df)} invoices to training format")
    print(f"Output saved to: {output_csv}")
    
    return output_df

def main():
    input_file = "data/training_data/invoices_training.csv"
    output_file = "data/training_data/invoices_training_formatted.csv"
    
    # Create directory if it doesn't exist
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    if os.path.exists(input_file):
        convert_invoice_csv_to_training(input_file, output_file)
        print(f"\nTraining file created with columns: {pd.read_csv(output_file).columns.tolist()}")
    else:
        print(f"Input file {input_file} not found!")
        print("Creating a sample training file instead...")
        create_sample_training_file(output_file)

def create_sample_training_file(output_file):
    """Create a sample training file with correct format"""
    sample_data = {
        'text': [
            "INVOICE #INV-1001\nDate: 2023-01-15\nBill To: John Smith\nAmount: $1500.00\nProduct: Consulting Services",
            "INVOICE #INV-1002\nDate: 2023-01-16\nBill To: Jane Doe\nAmount: $750.50\nProduct: Software License"
        ],
        'document_type': ['invoice', 'invoice'],
        'first_name': ['John', 'Jane'],
        'last_name': ['Smith', 'Doe'],
        'email': ['john.smith@example.com', 'jane.doe@example.com'],
        'product_id': ['PROD-1001', 'PROD-1002'],
        'qty': [1, 1],
        'amount': [1500.00, 750.50],
        'invoice_date': ['2023-01-15', '2023-01-16'],
        'address': ['123 Main St', '456 Oak Ave'],
        'city': ['New York', 'Los Angeles'],
        'stock_code': ['STK-1001', 'STK-1002'],
        'job': ['Consulting', 'Software']
    }
    
    df = pd.DataFrame(sample_data)
    df.to_csv(output_file, index=False)
    print(f"Sample training file created at: {output_file}")

if __name__ == "__main__":
    main()