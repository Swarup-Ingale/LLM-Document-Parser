#!/bin/bash
echo "Setting up document parser environment..."

# Create directory structure
mkdir -p data/{raw_documents,training_data,processed/{json_outputs,csv_exports,reports}}
mkdir -p models src scripts tests logs

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Download spaCy model
python -m spacy download en_core_web_sm

echo "Environment setup complete!"