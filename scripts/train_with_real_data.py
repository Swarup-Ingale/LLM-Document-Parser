#!/usr/bin/env python3
import os
import sys
import pandas as pd
from pathlib import Path
import subprocess
import shutil
from datetime import datetime
import random

# Add the parent directory to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.document_parser import DocumentParser

# Try to import OCR dependencies
try:
    import pytesseract
    from PIL import Image
    HAS_OCR = True
except ImportError:
    HAS_OCR = False
    print("OCR capabilities not available. Install pytesseract and Pillow for image processing.")

def clone_and_prepare_data():
    """Clone the receipts repository and prepare the data structure"""
    data_dir = Path("data")
    training_data_dir = data_dir / "training_data"
    raw_documents_dir = data_dir / "raw_documents"
    
    # Create directories
    for directory in [data_dir, training_data_dir, raw_documents_dir]:
        directory.mkdir(exist_ok=True)
    
    # Clone the repository if it doesn't exist
    repo_path = raw_documents_dir / "receipts" / "my-receipts"
    if not repo_path.exists():
        print("Cloning the receipts repository...")
        repo_path.parent.mkdir(exist_ok=True, parents=True)
        try:
            subprocess.run([
                "git", "clone", 
                "https://github.com/JensWalter/my-receipts.git",
                str(repo_path)
            ], check=True)
        except subprocess.CalledProcessError:
            print("Failed to clone repository. Using synthetic data instead.")
    
    return repo_path

def load_training_data_from_multiple_sources(parser):
    """Load training data from multiple sources: CSV, images, PDFs"""
    all_training_data = []
    
    # Load from CSV files - UPDATED to handle different formats
    csv_sources = [
        ("data/training_data/invoices_training.csv", "invoice"),
        ("data/training_data/contracts_training.csv", "contract"),  # Will auto-detect format
        ("data/training_data/contracts_training_01.csv", "contract"),
        ("data/training_data/Contracts_training_02.csv", "contract"),# Will auto-detect format
        ("data/training_data/receipts_training.csv", "receipt"),
        ("data/training_data/all_training_data.csv", None)
    ]
    
    for csv_path, doc_type in csv_sources:
        if os.path.exists(csv_path):
            print(f"Loading training data from {csv_path}...")
            # Use the enhanced load_training_data_from_csv method
            df = parser.load_training_data_from_csv(csv_path, doc_type)
            if not df.empty:
                all_training_data.append(df)
                print(f"✓ Loaded {len(df)} samples from {csv_path}")
            else:
                print(f"✗ No valid data found in {csv_path}")
    
    # ... rest of the function remains the same for images and PDFs
    # Load from image directories
    image_sources = [
        ("data/training_data/images/invoices", "invoice"),
        ("data/training_data/images/receipts", "receipt"),
        ("data/training_data/images/contracts", "contract")
    ]
    
    for image_dir, doc_type in image_sources:
        if os.path.exists(image_dir):
            print(f"Processing images from {image_dir}...")
            df = parser.load_training_data_from_images(image_dir, doc_type)
            if not df.empty:
                all_training_data.append(df)
                print(f"✓ Processed {len(df)} images from {image_dir}")
    
    # Load from PDF directories
    pdf_sources = [
        ("data/raw_documents/invoices", "invoice"),
        ("data/raw_documents/receipts", "receipt"),
        ("data/raw_documents/contracts", "contract")
    ]
    
    for pdf_dir, doc_type in pdf_sources:
        if os.path.exists(pdf_dir):
            print(f"Processing PDFs from {pdf_dir}...")
            df = process_existing_pdfs(pdf_dir, doc_type)
            if not df.empty:
                all_training_data.append(df)
                print(f"✓ Processed {len(df)} PDFs from {pdf_dir}")
    
    # Combine all data
    if all_training_data:
        combined_df = pd.concat(all_training_data, ignore_index=True)
        return combined_df
    else:
        return pd.DataFrame()

def process_receipts_for_training(repo_path):
    """Process receipts for training data with OCR"""
    training_data = []
    
    if not HAS_OCR:
        print("OCR not available. Using synthetic data for receipts.")
        # Fall back to synthetic data
        return create_synthetic_receipt_data(50)
    
    print("Processing receipt images with OCR...")
    
    # Walk through the repository structure
    for root, dirs, files in os.walk(repo_path):
        for file in files:
            if file.lower().endswith(('.jpg', '.jpeg', '.png')):
                image_path = os.path.join(root, file)
                try:
                    # Extract text using OCR - FIXED: Image is now imported
                    text = pytesseract.image_to_string(Image.open(image_path))
                    
                    if text.strip():  # Only add if we extracted text
                        training_data.append({
                            'text': text,
                            'document_type': 'receipt',
                            'source_file': file
                        })
                        print(f"✓ Processed {file}")
                    else:
                        print(f"✗ No text extracted from {file}")
                except Exception as e:
                    print(f"Error processing {image_path}: {e}")
    
    return training_data

def create_synthetic_receipt_data(num_samples=50):
    """Create synthetic receipt training data"""
    receipts_data = []
    
    stores = ["Walmart", "Target", "Amazon", "Costco", "Best Buy", "Starbucks", "McDonald's"]
    payment_methods = ["Credit Card", "Cash", "Debit Card", "Apple Pay", "Google Pay"]
    
    for i in range(num_samples):
        store = random.choice(stores)
        amount = round(random.uniform(5.0, 200.0), 2)
        date = f"2023-{random.randint(1,12):02d}-{random.randint(1,28):02d}"
        payment = random.choice(payment_methods)
        
        receipt_text = f"""
        RECEIPT FROM {store.upper()}
        Date: {date}
        Time: {random.randint(10,22)}:{random.randint(10,59):02d}
        
        ITEMS:
        - Item 1: ${round(amount * 0.6, 2)}
        - Item 2: ${round(amount * 0.4, 2)}
        
        SUBTOTAL: ${amount}
        TAX: ${round(amount * 0.08, 2)}
        TOTAL: ${round(amount * 1.08, 2)}
        
        Payment Method: {payment}
        Thank you for your purchase!
        """
        
        receipts_data.append({
            'text': receipt_text,
            'document_type': 'receipt',
            'source_file': f'synthetic_receipt_{i+1}'
        })
    
    return receipts_data

def create_invoice_training_data(num_samples=50):
    """Create synthetic invoice training data"""
    invoices_data = []
    
    companies = ["ABC Corp", "XYZ Inc", "Tech Solutions", "Global Services", "Innovative Designs"]
    services = ["Web Development", "Consulting", "Software License", "Maintenance", "Cloud Services"]
    
    for i in range(num_samples):
        company = random.choice(companies)
        service = random.choice(services)
        amount = round(random.uniform(100.0, 5000.0), 2)
        invoice_date = f"2023-{random.randint(1,12):02d}-{random.randint(1,28):02d}"
        due_date = f"2023-{random.randint(1,12):02d}-{random.randint(1,28):02d}"
        
        invoice_text = f"""
        INVOICE
        Invoice Number: INV-{1000+i}
        Date: {invoice_date}
        Due Date: {due_date}
        
        From: {company}
        123 Business Street
        City, State 12345
        
        To: Client Company
        456 Client Avenue
        City, State 67890
        
        Description: {service}
        Amount: ${amount}
        
        Tax: ${round(amount * 0.1, 2)}
        Total: ${round(amount * 1.1, 2)}
        
        Payment Terms: Net 30
        Please make payment by the due date.
        """
        
        invoices_data.append({
            'text': invoice_text,
            'document_type': 'invoice',
            'source_file': f'synthetic_invoice_{i+1}'
        })
    
    return invoices_data

def create_contract_training_data(num_samples=50):
    """Create synthetic contract training data"""
    contracts_data = []
    
    parties = ["ABC Corp", "XYZ Inc", "Global Services", "Tech Solutions"]
    contract_types = ["Service Agreement", "License Agreement", "Non-Disclosure Agreement", "Employment Contract"]
    
    for i in range(num_samples):
        party_a = random.choice(parties)
        party_b = random.choice([p for p in parties if p != party_a])
        contract_type = random.choice(contract_types)
        effective_date = f"2023-{random.randint(1,12):02d}-{random.randint(1,28):02d}"
        expiration_date = f"2024-{random.randint(1,12):02d}-{random.randint(1,28):02d}"
        value = round(random.uniform(1000.0, 10000.0), 2)
        
        contract_text = f"""
        {contract_type.upper()}
        
        This Agreement is made and entered into as of {effective_date}
        by and between:
        
        {party_a} ("Party A")
        and
        {party_b} ("Party B")
        
        Term: {random.randint(1, 5)} years
        Value: ${value}
        
        Both parties agree to the terms and conditions outlined herein.
        """
        
        contracts_data.append({
            'text': contract_text,
            'document_type': 'contract',
            'source_file': f'synthetic_contract_{i+1}'
        })
    
    return contracts_data

def process_existing_pdfs(directory_path, doc_type):
    """Process existing PDF files in a directory"""
    training_data = []
    parser = DocumentParser()
    
    directory = Path(directory_path)
    if not directory.exists():
        return pd.DataFrame()
    
    for pdf_file in directory.glob("*.pdf"):
        try:
            text = parser.extract_text_from_pdf(str(pdf_file))
            if text and len(text) > 50:  # Minimum text length
                training_data.append({
                    'text': text,
                    'document_type': doc_type,
                    'source_file': pdf_file.name
                })
                print(f"✓ Processed {pdf_file.name}")
        except Exception as e:
            print(f"Error processing {pdf_file}: {e}")
    
    return pd.DataFrame(training_data)

def main():
    # Clone and prepare data
    repo_path = clone_and_prepare_data()
    
    # Initialize parser with existing model if available
    model_path = "models/document_classifier.joblib"
    parser = DocumentParser(model_path if os.path.exists(model_path) else None)
    
    # Load training data from multiple sources
    print("Loading training data from multiple sources...")
    df = load_training_data_from_multiple_sources(parser)
    
    # If no data found, create synthetic data
    if len(df) == 0:
        print("No training data found in files. Creating synthetic data...")
        invoices_data = create_invoice_training_data(50)
        receipts_data = create_synthetic_receipt_data(50)
        contracts_data = create_contract_training_data(50)
        all_training_data = invoices_data + receipts_data + contracts_data
        df = pd.DataFrame(all_training_data)
    
    # Train the model - FIXED: removed optimize and incremental parameters
    print(f"Training the model with {len(df)} samples...")
    parser.train_model(df)
    
    # Save the model
    os.makedirs(os.path.dirname(model_path), exist_ok=True)
    parser.save_model(model_path)
    
    print(f"Model trained and saved to {model_path}")
    print(f"Training completed with {len(df)} samples")
    
    # Show training info
    training_info = parser.get_training_info()
    print(f"Total training samples: {training_info['training_samples']}")
    print(f"Training sessions: {len(training_info['training_history'])}")
    
    # Show class distribution
    class_dist = df['document_type'].value_counts().to_dict()
    print(f"Class distribution: {class_dist}")

if __name__ == "__main__":
    main()