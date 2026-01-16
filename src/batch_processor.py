import argparse
import os
import json
from pathlib import Path
from datetime import datetime

# Add the parent directory to Python path
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.document_parser import DocumentParser

def process_directory(input_dir, output_dir, model_path=None):
    """Process all PDFs in a directory"""
    parser = DocumentParser(model_path)
    
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True, parents=True)
    
    results = []
    
    for pdf_file in input_path.glob("*.pdf"):
        try:
            print(f"Processing {pdf_file.name}...")
            
            # Parse the document
            result = parser.parse_document(str(pdf_file))
            
            if result["success"]:
                # Save results to JSON
                output_file = output_path / f"{pdf_file.stem}_results.json"
                with open(output_file, 'w') as f:
                    json.dump(result, f, indent=2)
                
                results.append({
                    'file': pdf_file.name,
                    'success': True,
                    'output_file': str(output_file)
                })
            else:
                print(f"Failed to process {pdf_file.name}: {result.get('error')}")
                results.append({
                    'file': pdf_file.name,
                    'success': False,
                    'error': result.get('error')
                })
                
        except Exception as e:
            print(f"Error processing {pdf_file.name}: {str(e)}")
            results.append({
                'file': pdf_file.name,
                'success': False,
                'error': str(e)
            })
    
    # Save summary report
    summary_file = output_path / "processing_summary.json"
    with open(summary_file, 'w') as f:
        json.dump({
            "processed_date": datetime.now().isoformat(),
            "total_files": len(results),
            "successful": len([r for r in results if r['success']]),
            "failed": len([r for r in results if not r['success']]),
            "details": results
        }, f, indent=2)
    
    print(f"Processing complete. Summary saved to {summary_file}")
    return results

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Process PDF documents in batch mode')
    parser.add_argument('--input', '-i', required=True, help='Input directory with PDF files')
    parser.add_argument('--output', '-o', required=True, help='Output directory for results')
    parser.add_argument('--model', '-m', default='models/document_classifier.joblib', 
                       help='Path to trained model file')
    
    args = parser.parse_args()
    
    process_directory(args.input, args.output, args.model)