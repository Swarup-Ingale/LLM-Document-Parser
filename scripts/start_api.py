#!/usr/bin/env python3
import os
import sys

# Add the parent directory to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.api_server import app

if __name__ == '__main__':
    # Create necessary directories
    os.makedirs('logs', exist_ok=True)
    os.makedirs('models', exist_ok=True)
    
    print("Starting Document Parser API Server...")
    print("API will be available at: http://localhost:5000")
    print()
    print("Endpoints:")
    print("  GET  /health              - Health check")
    print("  POST /parse               - Parse a single document")
    print("  POST /batch_parse         - Parse multiple documents")
    print("  GET  /model/info          - Get model information")
    print("  GET  /model/classes       - Get model classes")
    print()
    print("Example usage:")
    print('  curl -X POST -F "file=@document.pdf" http://localhost:5000/parse')
    print('  curl -X POST -F "files=@doc1.pdf" -F "files=@doc2.pdf" http://localhost:5000/batch_parse')
    print()
    
    app.run(host='0.0.0.0', port=5000, debug=True)