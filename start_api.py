#!/usr/bin/env python3
"""
Simple launcher for the Document Parser API
"""
import os
import sys

def main():
    # Add the current directory to Python path
    current_dir = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, current_dir)
    
    # Check if src directory exists
    src_dir = os.path.join(current_dir, 'src')
    if not os.path.exists(src_dir):
        print("❌ Error: 'src' directory not found!")
        print("Please make sure you're running this from the project root directory.")
        return
    
    # Create necessary directories
    os.makedirs('logs', exist_ok=True)
    os.makedirs('models', exist_ok=True)
    os.makedirs('data/previews', exist_ok=True)
    os.makedirs('data/exports', exist_ok=True)
    
    print("🚀 Starting Document Parser API Server...")
    print(f"📁 Project root: {current_dir}")
    
    try:
        # Import and run the app
        from src.api_server import app
        print("✅ API server imported successfully!")
        print("🌐 Web Interface: http://localhost:5000")
        print("🔧 API Health: http://localhost:5000/api/health")
        print("\nPress Ctrl+C to stop the server")
        
        app.run(host='0.0.0.0', port=5000, debug=True)
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("\n📋 Troubleshooting steps:")
        print("1. Make sure all required packages are installed:")
        print("   pip install -r requirements.txt")
        print("2. Check that all files are in the correct locations")
        print("3. Ensure you're running from the project root directory")

if __name__ == '__main__':
    main()