#!/usr/bin/env python3
import requests
import json
import sys
import os

# Add the parent directory to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def print_response(response, title):
    """Print API response in a formatted way"""
    print(f"\n{'='*50}")
    print(f"{title}")
    print(f"{'='*50}")
    print(f"Status Code: {response.status_code}")
    try:
        response_json = response.json()
        print("Response JSON:")
        print(json.dumps(response_json, indent=2))
        return response_json
    except:
        print(f"Response: {response.text}")
        return None

def test_health():
    response = requests.get('http://localhost:5000/health')
    return print_response(response, "Health Check")

def test_parse(file_path):
    if not os.path.exists(file_path):
        print(f"File {file_path} not found.")
        return None
        
    with open(file_path, 'rb') as f:
        files = {'file': f}
        response = requests.post('http://localhost:5000/parse', files=files)
        
    return print_response(response, f"Parse Document: {os.path.basename(file_path)}")

def test_batch(file_paths):
    files = []
    for file_path in file_paths:
        if os.path.exists(file_path):
            files.append(('files', open(file_path, 'rb')))
        else:
            print(f"File {file_path} not found.")
            
    if files:
        response = requests.post('http://localhost:5000/batch_parse', files=files)
        
        # Close the files
        for _, f in files:
            f.close()
            
        return print_response(response, "Batch Parse")
    else:
        print("No valid files provided for batch processing.")
        return None

def test_model_info():
    response = requests.get('http://localhost:5000/model/info')
    return print_response(response, "Model Information")

def test_model_classes():
    response = requests.get('http://localhost:5000/model/classes')
    return print_response(response, "Model Classes")

if __name__ == '__main__':
    # Check if API is running
    try:
        # Test all endpoints
        test_health()
        test_model_info()
        test_model_classes()
        
        # Test with sample documents if they exist
        sample_invoice = 'data/raw_documents/invoices/sample_invoice.pdf'
        sample_receipt = 'data/raw_documents/receipts/2021-09-02-hotel amarin.pdf'
        
        if os.path.exists(sample_invoice):
            test_parse(sample_invoice)
        
        if os.path.exists(sample_receipt):
            test_parse(sample_receipt)
            
        if os.path.exists(sample_invoice) and os.path.exists(sample_receipt):
            test_batch([sample_invoice, sample_receipt])
            
    except requests.exceptions.ConnectionError:
        print("API server is not running. Please start it with: python scripts/start_api.py")