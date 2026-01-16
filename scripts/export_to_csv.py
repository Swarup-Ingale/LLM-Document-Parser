#!/usr/bin/env python3
import json
import csv
import os
from pathlib import Path
import pandas as pd

def json_to_csv():
    """Convert JSON outputs to CSV format"""
    json_dir = Path("data/processed/json_outputs")
    csv_dir = Path("data/processed/csv_exports")
    csv_dir.mkdir(exist_ok=True, parents=True)
    
    all_data = []
    
    # Check if JSON directory exists and has files
    if not json_dir.exists():
        print(f"JSON directory {json_dir} does not exist.")
        return
    
    json_files = list(json_dir.glob("*.json"))
    if not json_files:
        print(f"No JSON files found in {json_dir}")
        return
    
    # Process all JSON files
    for json_file in json_files:
        try:
            # Skip empty files
            if os.path.getsize(json_file) == 0:
                print(f"Skipping empty file: {json_file}")
                continue
                
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            if data.get("success", False):
                # Extract relevant information
                row = {
                    "filename": data.get("filename", ""),
                    "document_type": data.get("document_type", ""),
                    "processing_time": data.get("extraction_time", "")
                }
                
                # Add pattern extraction data
                patterns = data.get("pattern_extraction", {})
                for key, values in patterns.items():
                    row[key] = values[0] if values else ""
                
                # Add contact information
                contacts = data.get("contact_info", {})
                for key, values in contacts.items():
                    row[key] = values[0] if values else ""
                
                # Add name information
                names = data.get("name_info", {})
                if names:
                    row["primary_name"] = names.get("primary_name", "")
                    row["candidate_names"] = ", ".join(names.get("candidate_names", []))
                
                all_data.append(row)
                
        except json.JSONDecodeError as e:
            print(f"Error reading {json_file}: {e}")
        except Exception as e:
            print(f"Unexpected error with {json_file}: {e}")
    
    # Convert to DataFrame and save as CSV
    if all_data:
        df = pd.DataFrame(all_data)
        csv_path = csv_dir / "extracted_data.csv"
        df.to_csv(csv_path, index=False, encoding='utf-8')
        print(f"Exported {len(all_data)} records to {csv_path}")
    else:
        print("No valid data found to export.")

if __name__ == "__main__":
    json_to_csv()