#!/usr/bin/env python3
import os
import sys
from pymongo import MongoClient
from datetime import datetime

# Add the parent directory to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def initialize_database():
    """Initialize MongoDB database with collections and indexes"""
    try:
        # Connect to MongoDB
        client = MongoClient('mongodb://localhost:27017/')
        db = client['document_parser_db']
        
        # Create collections
        users_collection = db['users']
        documents_collection = db['parsed_documents']
        api_logs_collection = db['api_logs']
        
        # Create indexes
        users_collection.create_index('email', unique=True)
        users_collection.create_index('username', unique=True)
        documents_collection.create_index('user_id')
        documents_collection.create_index([('user_id', 1), ('created_at', -1)])
        api_logs_collection.create_index('timestamp')
        
        print("✓ Database initialized successfully")
        print(f"✓ Database: {db.name}")
        print(f"✓ Collections: {db.list_collection_names()}")
        
        # Create a sample admin user
        from werkzeug.security import generate_password_hash
        
        admin_user = {
            'username': 'admin',
            'email': 'admin@documentparser.com',
            'password_hash': generate_password_hash('admin123'),
            'first_name': 'System',
            'last_name': 'Administrator',
            'created_at': datetime.now(),
            'updated_at': datetime.now(),
            'is_active': True,
            'plan': 'enterprise',
            'document_limit': 10000,
            'used_documents': 0,
            'last_reset': datetime.now(),
            'role': 'admin'
        }
        
        try:
            users_collection.insert_one(admin_user)
            print("✓ Admin user created: admin@documentparser.com / admin123")
        except Exception as e:
            print(f"ℹ Admin user already exists: {e}")
        
        client.close()
        
    except Exception as e:
        print(f"✗ Database initialization failed: {e}")

if __name__ == "__main__":
    initialize_database()