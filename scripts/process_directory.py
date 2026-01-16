#!/usr/bin/env python3
import sys
import os

# Add the parent directory to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.batch_processor import process_directory
import argparse

def main():
    parser = argparse.ArgumentParser(description='Process PDF documents in batch mode')
    parser.add_argument('--input', '-i', required=True, help='Input directory with PDF files')
    parser.add_argument('--output', '-o', required=True, help='Output directory for results')
    parser.add_argument('--model', '-m', default='models/document_classifier.joblib', 
                       help='Path to trained model file')
    
    args = parser.parse_args()
    
    process_directory(args.input, args.output, args.model)

if __name__ == "__main__":
    main()