#!/usr/bin/env python3
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.document_parser import DocumentParser
import json
from pathlib import Path

def test_model_accuracy():
    parser = DocumentParser("models/document_classifier.joblib")
    
    # Test documents with known types
    test_docs = [
        {"file_path": "data/test/invoice.pdf", "true_document_type": "invoice"},
        {"file_path": "data/test/invoice_01.pdf", "true_document_type": "invoice"},
        {"file_path": "data/test/invoice_02.pdf", "true_document_type": "invoice"},
        {"file_path": "data/test/invoice_03.pdf", "true_document_type": "invoice"},
        {"file_path": "data/test/invoice_04.pdf", "true_document_type": "receipt"},
        {"file_path": "data/test/invoice_05.pdf", "true_document_type": "receipt"},
        {"file_path": "data/test/invoice_06.pdf", "true_document_type": "receipt"},
        {"file_path": "data/test/Contract.pdf", "true_document_type": "contract"},
        {"file_path": "data/test/Contract_01.pdf", "true_document_type": "contract"},
        {"file_path": "data/test/Contract_02.pdf", "true_document_type": "contract"},
        {"file_path": "data/test/Contract_03.pdf", "true_document_type": "contract"},
        {"file_path": "data/test/Contract_04.pdf", "true_document_type": "contract"},
        {"file_path": "data/test/Contract_05.pdf", "true_document_type": "contract"},
        {"file_path": "data/test/Contract_06.pdf", "true_document_type": "contract"},
        {"file_path": "data/test/Contract_07.pdf", "true_document_type": "contract"},
        {"file_path": "data/test/receipt.pdf", "true_document_type": "receipt"},
        {"file_path": "data/test/receipt_01.pdf", "true_document_type": "receipt"},
        {"file_path": "data/test/receipt_02.pdf", "true_document_type": "receipt"},
        {"file_path": "data/test/receipt_03.pdf", "true_document_type": "receipt"},
        {"file_path": "data/test/receipt_04.pdf", "true_document_type": "receipt"},
        {"file_path": "data/test/receipt_04.pdf", "true_document_type": "receipt"},
        {"file_path": "data/test/receipt_05.pdf", "true_document_type": "receipt"},
        {"file_path": "data/test/receipt_06.pdf", "true_document_type": "receipt"},
        {"file_path": "data/test/receipt_07.pdf", "true_document_type": "receipt"},
        {"file_path": "data/test/receipt_08.pdf", "true_document_type": "receipt"},
        {"file_path": "data/test/receipt_09.pdf", "true_document_type": "receipt"},
        {"file_path": "data/test/receipt_10.pdf", "true_document_type": "receipt"},
        {"file_path": "data/test/receipt_11.pdf", "true_document_type": "receipt"},
        {"file_path": "data/test/receipt_12.pdf", "true_document_type": "receipt"},
        {"file_path": "data/test/receipt_13.pdf", "true_document_type": "receipt"},
        {"file_path": "data/test/receipt_14.pdf", "true_document_type": "receipt"},
        {"file_path": "data/test/receipt_15.pdf", "true_document_type": "receipt"},
        {"file_path": "data/test/receipt_16.pdf", "true_document_type": "receipt"},
        {"file_path": "data/test/receipt_17.pdf", "true_document_type": "receipt"},
        {"file_path": "data/test/receipt_18.pdf", "true_document_type": "receipt"},
        {"file_path": "data/test/receipt_19.pdf", "true_document_type": "receipt"},
        {"file_path": "data/test/receipt_20.pdf", "true_document_type": "receipt"},
        {"file_path": "data/test/receipt_21.pdf", "true_document_type": "receipt"},
        {"file_path": "data/test/receipt_22.pdf", "true_document_type": "receipt"},
        {"file_path": "data/test/Contract_08.pdf", "true_document_type": "contract"},
        {"file_path": "data/test/Contract_09.pdf", "true_document_type": "contract"},
        {"file_path": "data/test/Contract_10.pdf", "true_document_type": "contract"},
        {"file_path": "data/test/Contract_11.pdf", "true_document_type": "contract"},
        {"file_path": "data/test/Contract_12.pdf", "true_document_type": "contract"},
        {"file_path": "data/test/Contract_13.pdf", "true_document_type": "contract"},
        {"file_path": "data/test/Contract_14.pdf", "true_document_type": "contract"},
        {"file_path": "data/test/Contract_15.pdf", "true_document_type": "contract"},
        {"file_path": "data/test/Contract_16.pdf", "true_document_type": "contract"},
        {"file_path": "data/test/Contract_17.pdf", "true_document_type": "contract"},
        {"file_path": "data/test/Contract_18.pdf", "true_document_type": "contract"},
        {"file_path": "data/test/Contract_19.pdf", "true_document_type": "contract"},
        {"file_path": "data/test/Contract_20.pdf", "true_document_type": "contract"},
        {"file_path": "data/test/invoice_07.pdf", "true_document_type": "receipt"},
        {"file_path": "data/test/invoice_08.pdf", "true_document_type": "receipt"},
        {"file_path": "data/test/invoice_09.pdf", "true_document_type": "invoice"},
        {"file_path": "data/test/invoice_10.pdf", "true_document_type": "invoice"},
        {"file_path": "data/test/invoice_11.pdf", "true_document_type": "invoice"},
        {"file_path": "data/test/invoice_12.pdf", "true_document_type": "invoice"},
        {"file_path": "data/test/invoice_13.pdf", "true_document_type": "invoice"},
        {"file_path": "data/test/invoice_14.pdf", "true_document_type": "invoice"},
        {"file_path": "data/test/invoice_15.pdf", "true_document_type": "invoice"},
        {"file_path": "data/test/invoice_16.pdf", "true_document_type": "invoice"},
        {"file_path": "data/test/invoice_17.pdf", "true_document_type": "invoice"},
        {"file_path": "data/test/invoice_18.pdf", "true_document_type": "invoice"},
        {"file_path": "data/test/invoice_19.pdf", "true_document_type": "invoice"},
        {"file_path": "data/test/invoice_20.pdf", "true_document_type": "invoice"},
        {"file_path": "data/test/invoice_21.pdf", "true_document_type": "invoice"},
        {"file_path": "data/test/invoice_22.pdf", "true_document_type": "invoice"},
        {"file_path": "data/test/invoice_23.pdf", "true_document_type": "invoice"},
        {"file_path": "data/test/invoice_24.pdf", "true_document_type": "invoice"},
        {"file_path": "data/test/invoice_25.pdf", "true_document_type": "invoice"},
        {"file_path": "data/test/invoice_26.pdf", "true_document_type": "invoice"},
        {"file_path": "data/test/invoice_27.pdf", "true_document_type": "invoice"},
        {"file_path": "data/test/invoice_28.pdf", "true_document_type": "invoice"},
        {"file_path": "data/test/invoice_29.pdf", "true_document_type": "invoice"},
        {"file_path": "data/test/invoice_30.pdf", "true_document_type": "invoice"},
        {"file_path": "data/test/invoice_31.pdf", "true_document_type": "invoice"},
        {"file_path": "data/test/invoice_32.pdf", "true_document_type": "invoice"},
        {"file_path": "data/test/invoice_33.pdf", "true_document_type": "invoice"},
        {"file_path": "data/test/invoice_34.pdf", "true_document_type": "invoice"},
        {"file_path": "data/test/invoice_35.pdf", "true_document_type": "invoice"},
        # Add more test files with their true labels
    ]
    
    # Filter out non-existent files
    valid_test_docs = [doc for doc in test_docs if os.path.exists(doc['file_path'])]
    
    if not valid_test_docs:
        print("No test documents found. Create a 'data/test' folder with sample documents.")
        return
    
    print(f"Testing model with {len(valid_test_docs)} documents...")
    
    # Evaluate model
    results = parser.evaluate_model(valid_test_docs)
    
    # Print results
    print("\n" + "="*50)
    print("MODEL EVALUATION RESULTS")
    print("="*50)
    print(f"Accuracy: {results['accuracy']}%")
    print(f"Correct: {results['correct_predictions']}/{results['total_documents']}")
    print(f"Vectorizer Features: {results['vectorizer_features']}")
    print(f"Model Classes: {results['model_classes']}")
    print(f"Training Samples: {results['training_samples']}")
    
    # Confusion matrix
    if results.get('confusion_data'):
        print("\nConfusion Data:")
        for key, count in results['confusion_data'].items():
            true, pred = key.split('_')
            print(f"  True: {true} -> Predicted: {pred}: {count}")

if __name__ == "__main__":
    test_model_accuracy()