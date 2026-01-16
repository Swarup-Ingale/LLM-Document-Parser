#!/usr/bin/env python3
import os
from pathlib import Path

def clean_empty_json_files():
    """Remove empty JSON files from processed directory"""
    json_dir = Path("data/processed/json_outputs")
    
    if not json_dir.exists():
        print(f"JSON directory {json_dir} does not exist.")
        return
    
    empty_files = []
    
    for json_file in json_dir.glob("*.json"):
        if os.path.getsize(json_file) == 0:
            empty_files.append(json_file)
            json_file.unlink()  # Delete the file
    
    if empty_files:
        print(f"Removed {len(empty_files)} empty JSON files:")
        for file in empty_files:
            print(f"  - {file.name}")
    else:
        print("No empty JSON files found.")

if __name__ == "__main__":
    clean_empty_json_files()