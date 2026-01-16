#!/usr/bin/env python3
import os
import sys
import tempfile
import logging
import json
import uuid
import re
from datetime import datetime, timedelta
from pathlib import Path
from bson import ObjectId
from dotenv import load_dotenv
from datetime import time

# Configure logging to handle Unicode properly
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),  # Use stdout instead of stderr
        logging.FileHandler('app.log', encoding='utf-8')  # For file logging
    ]
)

# Fix import paths - add the project root to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.insert(0, project_root)

# Now import the modules
try:
    from src.search_engine import DocumentSearchEngine
    from src.export_manager import ExportManager
    from src.document_preview import DocumentPreviewGenerator
    from src.rate_limiter import RateLimitManager
    from src.celery_app import celery_app, process_document_async, batch_process_documents_async, export_documents_async, get_task_status
    print("✓ All technical improvement modules imported successfully")
except ImportError as e:
    print(f"⚠ Some modules not available: {e}")
    # Create dummy classes for missing modules
    class DocumentSearchEngine:
        def __init__(self, db): pass
        def search_documents(self, *args, **kwargs): return {"success": False, "error": "Search engine not available"}
        def get_search_facets(self, *args, **kwargs): return {}
    
    class ExportManager:
        def __init__(self, db): pass
    
    class DocumentPreviewGenerator:
        def __init__(self, *args, **kwargs): pass
        def generate_pdf_preview(self, *args, **kwargs): return None, None
        def generate_image_preview(self, *args, **kwargs): return None, None
    
    class RateLimitManager:
        def __init__(self, app): pass
    
    # Dummy Celery functions
    def process_document_async(*args, **kwargs): return None
    def batch_process_documents_async(*args, **kwargs): return None
    def export_documents_async(*args, **kwargs): return None
    def get_task_status(*args, **kwargs): return {"status": "unknown"}

# Flask imports
from flask import Flask, request, jsonify, render_template_string, send_file
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import JWTManager, jwt_required, create_access_token, get_jwt_identity
from flask_cors import CORS
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError

# Load environment variables
load_dotenv()

try:
    from src.document_parser import DocumentParser
    HAS_PARSER = True
    print("✓ DocumentParser imported successfully")
except ImportError as e:
    print(f"⚠ DocumentParser not available: {e}")
    HAS_PARSER = False

# Initialize Flask app
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB limit
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = True
app.config['JSON_SORT_KEYS'] = False
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'fallback-secret-key-change-in-production')
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=int(os.getenv('JWT_ACCESS_TOKEN_EXPIRES_HOURS', 24)))

# Enable CORS
CORS(app)

# Initialize JWT Manager
jwt = JWTManager(app)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/api_server.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# MongoDB Configuration - FIXED VERSION
def initialize_mongodb_with_retry(max_retries=3, delay=1):
    """Initialize MongoDB connection with retry logic for index creation"""
    for attempt in range(max_retries):
        try:
            mongodb_uri = os.getenv('MONGODB_URI', 'mongodb://localhost:27017/')
            database_name = os.getenv('DATABASE_NAME', 'document_parser_db')
            
            client = MongoClient(mongodb_uri)
            db = client[database_name]
            
            # Test connection
            client.admin.command('ping')
            
            # Initialize collections
            users_collection = db['users']
            documents_collection = db['parsed_documents']
            api_logs_collection = db['api_logs']
            
            # Create user indexes with error handling
            try:
                users_collection.create_index('email', unique=True)
            except Exception as e:
                if "already exists" not in str(e):
                    logger.warning(f"User email index creation: {e}")
            
            try:
                users_collection.create_index('username', unique=True)
            except Exception as e:
                if "already exists" not in str(e):
                    logger.warning(f"User username index creation: {e}")
            
            logger.info("MongoDB connected successfully")
            return client, db, users_collection, documents_collection, api_logs_collection, True
            
        except Exception as e:
            logger.warning(f"MongoDB connection attempt {attempt + 1}/{max_retries} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(delay)
                delay *= 2  # Exponential backoff
            else:
                raise e
    
    # If all retries failed
    return None, None, None, None, None, False

# Initialize MongoDB
try:
    client, db, users_collection, documents_collection, api_logs_collection, MONGODB_CONNECTED = initialize_mongodb_with_retry()
except Exception as e:
    logger.error(f"All MongoDB connection attempts failed: {e}")
    # Fallback - will still work but without database functionality
    client, db, users_collection, documents_collection, api_logs_collection = None, None, None, None, None
    MONGODB_CONNECTED = False
    
# Initialize the document parser with the trained model
MODEL_PATH = os.getenv('MODEL_PATH', "models/document_classifier_modified_before_one_night.joblib")
parser = None

if HAS_PARSER:
    try:
        parser = DocumentParser(MODEL_PATH)
        if parser.is_trained:
            logger.info(f"Model loaded successfully from {MODEL_PATH}")
            logger.info(f"Model can predict: {parser.label_encoder.classes_}")
        else:
            logger.warning("Model loaded but not trained. Using rule-based parsing only.")
    except Exception as e:
        logger.error(f"Failed to load model: {e}")
        parser = DocumentParser()  # Fallback to untrained parser
else:
    logger.warning("DocumentParser not available - running in API-only mode")

# ============================================================================
# NEW TECHNICAL IMPROVEMENTS INITIALIZATION
# ============================================================================

# Initialize search engine with error handling
def initialize_search_engine_safely(db_connection, max_retries=3, delay=1):
    """Initialize search engine with retry logic for index conflicts"""
    if db_connection is None:
        logger.warning("No database connection - search engine disabled")
        return DocumentSearchEngine(None)  # Dummy instance
    
    for attempt in range(max_retries):
        try:
            search_engine = DocumentSearchEngine(db_connection)
            logger.info("Search engine initialized successfully")
            return search_engine
        except Exception as e:
            if "Index already exists" in str(e) and attempt < max_retries - 1:
                logger.warning(f"Search engine index conflict, retrying in {delay}s... (Attempt {attempt + 1}/{max_retries})")
                time.sleep(delay)
                delay *= 2
            else:
                logger.error(f"Search engine initialization failed after {max_retries} attempts: {e}")
                # Return a dummy instance that won't crash the app
                class DummySearchEngine:
                    def search_documents(self, *args, **kwargs): 
                        return {"success": False, "error": "Search engine not available"}
                    def get_search_facets(self, *args, **kwargs): 
                        return {}
                    def quick_search(self, *args, **kwargs): 
                        return {"success": False, "error": "Search engine not available"}
                return DummySearchEngine()
    
    # Fallback
    class DummySearchEngine:
        def search_documents(self, *args, **kwargs): 
            return {"success": False, "error": "Search engine not available"}
        def get_search_facets(self, *args, **kwargs): 
            return {}
        def quick_search(self, *args, **kwargs): 
            return {"success": False, "error": "Search engine not available"}
    return DummySearchEngine()

# Initialize search engine
search_engine = initialize_search_engine_safely(db)

# Initialize export manager
export_manager = ExportManager(db)

# Initialize document preview generator
preview_generator = DocumentPreviewGenerator()

# Initialize rate limiting
rate_limit_manager = RateLimitManager(app)

class JSONEncoder(json.JSONEncoder):
    """Custom JSON encoder to handle ObjectId"""
    def default(self, o):
        if isinstance(o, ObjectId):
            return str(o)
        return json.JSONEncoder.default(self, o)

app.json_encoder = JSONEncoder

def log_api_activity(user_id, endpoint, method, status, metadata=None):
    """Log API activity to MongoDB"""
    if api_logs_collection is not None:
        try:
            log_entry = {
                'user_id': user_id,
                'endpoint': endpoint,
                'method': method,
                'status': status,
                'timestamp': datetime.now(),
                'ip_address': request.remote_addr,
                'user_agent': request.headers.get('User-Agent'),
                'metadata': metadata or {}
            }
            api_logs_collection.insert_one(log_entry)
        except Exception as e:
            logger.error(f"Failed to log API activity: {e}")

def format_api_response(success, data=None, message=None, status_code=200):
    """Standardized API response format"""
    response = {
        "success": success,
        "timestamp": datetime.now().isoformat(),
        "status_code": status_code
    }
    
    if data is not None:
        response["data"] = data
        
    if message is not None:
        response["message"] = message
        
    return jsonify(response), status_code

# ... [REST OF YOUR API_SERVER.PY CODE CONTINUES AS BEFORE]
# Include all the routes and functionality from your previous api_server.py

def validate_email(email):
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_password(password):
    """Validate password strength - simplified for demo"""
    if len(password) < 6:
        return False, "Password must be at least 6 characters long"
    return True, "Password is acceptable"

# ============================================================================
# FRONTEND ROUTES (EXISTING + ENHANCED)
# ============================================================================

@app.route('/')
def index():
    """Serve the main frontend page with enhanced features"""
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Document Parser - Enhanced Interface</title>
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            
            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                padding: 20px;
            }
            
            .container {
                max-width: 1200px;
                margin: 0 auto;
                background: white;
                border-radius: 15px;
                box-shadow: 0 20px 40px rgba(0,0,0,0.1);
                overflow: hidden;
            }
            
            .header {
                background: linear-gradient(135deg, #2c3e50 0%, #3498db 100%);
                color: white;
                padding: 30px;
                text-align: center;
            }
            
            .header h1 {
                font-size: 2.2em;
                margin-bottom: 10px;
            }
            
            .header p {
                font-size: 1.1em;
                opacity: 0.9;
            }
            
            .tabs {
                display: flex;
                background: #34495e;
                flex-wrap: wrap;
            }
            
            .tab {
                flex: 1;
                padding: 15px;
                text-align: center;
                color: white;
                cursor: pointer;
                transition: background 0.3s;
                min-width: 120px;
            }
            
            .tab:hover {
                background: #2c3e50;
            }
            
            .tab.active {
                background: #3498db;
            }
            
            .content {
                padding: 30px;
                min-height: 600px;
            }
            
            .tab-content {
                display: none;
            }
            
            .tab-content.active {
                display: block;
            }
            
            .form-group {
                margin-bottom: 20px;
            }
            
            label {
                display: block;
                margin-bottom: 8px;
                font-weight: 600;
                color: #2c3e50;
            }
            
            input, select, textarea {
                width: 100%;
                padding: 12px;
                border: 2px solid #ddd;
                border-radius: 8px;
                font-size: 16px;
                transition: border 0.3s;
            }
            
            input:focus, select:focus, textarea:focus {
                border-color: #3498db;
                outline: none;
            }
            
            button {
                background: #3498db;
                color: white;
                border: none;
                padding: 15px 30px;
                border-radius: 8px;
                font-size: 16px;
                cursor: pointer;
                transition: background 0.3s;
                width: 100%;
                margin: 5px 0;
            }
            
            button:hover {
                background: #2980b9;
            }
            
            button:disabled {
                background: #bdc3c7;
                cursor: not-allowed;
            }
            
            .result {
                margin-top: 20px;
                padding: 20px;
                background: #f8f9fa;
                border-radius: 8px;
                border-left: 4px solid #3498db;
                display: none;
            }
            
            .result.success {
                border-left-color: #27ae60;
            }
            
            .result.error {
                border-left-color: #e74c3c;
            }
            
            .file-input {
                padding: 20px;
                border: 2px dashed #ddd;
                border-radius: 8px;
                text-align: center;
                cursor: pointer;
                transition: border 0.3s;
            }
            
            .file-input:hover {
                border-color: #3498db;
            }
            
            .file-input.dragover {
                border-color: #3498db;
                background: #f8f9fa;
            }
            
            .status {
                padding: 10px;
                border-radius: 5px;
                margin-bottom: 20px;
                text-align: center;
            }
            
            .status.healthy {
                background: #d4edda;
                color: #155724;
            }
            
            .status.error {
                background: #f8d7da;
                color: #721c24;
            }
            
            .hidden {
                display: none;
            }
            
            .user-info {
                background: #e8f4fd;
                padding: 15px;
                border-radius: 8px;
                margin-bottom: 20px;
            }
            
            .logout-btn {
                background: #e74c3c;
                width: auto;
                padding: 8px 15px;
                margin-top: 10px;
            }
            
            .logout-btn:hover {
                background: #c0392b;
            }
            
            /* NEW: Search and Export Styles */
            .search-filters {
                background: #f8f9fa;
                padding: 20px;
                border-radius: 8px;
                margin-bottom: 20px;
            }
            
            .filter-row {
                display: flex;
                gap: 15px;
                margin-bottom: 15px;
                flex-wrap: wrap;
            }
            
            .filter-group {
                flex: 1;
                min-width: 200px;
            }
            
            .document-grid {
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
                gap: 20px;
                margin-top: 20px;
            }
            
            .document-card {
                border: 1px solid #ddd;
                border-radius: 8px;
                padding: 15px;
                background: white;
                transition: transform 0.2s, box-shadow 0.2s;
            }
            
            .document-card:hover {
                transform: translateY(-2px);
                box-shadow: 0 4px 12px rgba(0,0,0,0.1);
            }
            
            .document-thumbnail {
                width: 100%;
                height: 150px;
                background: #f0f0f0;
                border-radius: 4px;
                display: flex;
                align-items: center;
                justify-content: center;
                margin-bottom: 10px;
                color: #666;
                font-size: 14px;
            }
            
            .document-actions {
                display: flex;
                gap: 5px;
                margin-top: 10px;
            }
            
            .document-actions button {
                flex: 1;
                padding: 8px;
                font-size: 12px;
            }
            
            .progress-bar {
                width: 100%;
                height: 20px;
                background: #f0f0f0;
                border-radius: 10px;
                overflow: hidden;
                margin: 10px 0;
            }
            
            .progress-fill {
                height: 100%;
                background: #3498db;
                transition: width 0.3s;
            }
            
            .export-options {
                display: flex;
                gap: 10px;
                margin: 10px 0;
            }
            
            .export-options button {
                flex: 1;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>📄 Document Parser - Enhanced</h1>
                <p>Advanced Document Processing with Search, Export & Preview</p>
            </div>
            
            <div class="tabs">
                <div class="tab active" onclick="switchTab('health')">Health Check</div>
                <div class="tab" onclick="switchTab('parse')">Parse Document</div>
                <div class="tab" onclick="switchTab('search')">Search & Browse</div>
                <div class="tab" onclick="switchTab('batch')">Batch Process</div>
                <div class="tab" onclick="switchTab('auth')">Authentication</div>
            </div>
            
            <div class="content">
                <!-- Health Check Tab -->
                <div id="health-tab" class="tab-content active">
                    <h2>System Health</h2>
                    <div class="status" id="health-status">Checking system status...</div>
                    <button onclick="checkHealth()">Refresh Health Check</button>
                    <div class="result" id="health-result"></div>
                </div>
                
                <!-- Parse Document Tab -->
                <div id="parse-tab" class="tab-content">
                    <h2>Parse Single Document</h2>
                    <div class="user-info hidden" id="user-info-parse">
                        Welcome, <span id="user-name"></span>!
                        <button class="logout-btn" onclick="logout()">Logout</button>
                    </div>
                    <div class="login-prompt" id="login-prompt-parse">
                        <p>Please login to parse documents</p>
                        <button onclick="switchTab('auth')">Go to Login</button>
                    </div>
                    <div class="hidden" id="parse-form">
                        <div class="form-group">
                            <label for="document-file">Select Document (PDF or Image):</label>
                            <div class="file-input" id="file-dropzone">
                                <p>📁 Drop your file here or click to browse</p>
                                <input type="file" id="document-file" accept=".pdf,.jpg,.jpeg,.png,.bmp,.tiff" style="display: none;">
                                <div id="file-name">No file selected</div>
                            </div>
                        </div>
                        
                        <div class="form-group">
                            <label for="use-ml">Use Machine Learning:</label>
                            <select id="use-ml">
                                <option value="true">Yes (Recommended)</option>
                                <option value="false">No (Rule-based only)</option>
                            </select>
                        </div>
                        
                        <div class="form-group">
                            <label for="async-processing">
                                <input type="checkbox" id="async-processing"> Use Background Processing (Recommended for large files)
                            </label>
                        </div>
                        
                        <button onclick="parseDocument()" id="parse-btn">Parse Document</button>
                        <div class="progress-bar hidden" id="parse-progress">
                            <div class="progress-fill" id="parse-progress-fill" style="width: 0%"></div>
                        </div>
                        <div class="result" id="parse-result"></div>
                    </div>
                </div>
                
                <!-- NEW: Search & Browse Tab -->
                <div id="search-tab" class="tab-content">
                    <h2>Search & Browse Documents</h2>
                    <div class="user-info hidden" id="user-info-search">
                        Welcome, <span id="user-name-search"></span>!
                        <button class="logout-btn" onclick="logout()">Logout</button>
                    </div>
                    <div class="login-prompt" id="login-prompt-search">
                        <p>Please login to search documents</p>
                        <button onclick="switchTab('auth')">Go to Login</button>
                    </div>
                    <div class="hidden" id="search-form">
                        <div class="search-filters">
                            <div class="filter-row">
                                <div class="filter-group">
                                    <label>Search Text:</label>
                                    <input type="text" id="search-text" placeholder="Enter keywords...">
                                </div>
                                <div class="filter-group">
                                    <label>Document Type:</label>
                                    <select id="search-doc-type">
                                        <option value="all">All Types</option>
                                        <option value="invoice">Invoice</option>
                                        <option value="receipt">Receipt</option>
                                        <option value="contract">Contract</option>
                                    </select>
                                </div>
                            </div>
                            <div class="filter-row">
                                <div class="filter-group">
                                    <label>Date From:</label>
                                    <input type="date" id="search-date-from">
                                </div>
                                <div class="filter-group">
                                    <label>Date To:</label>
                                    <input type="date" id="search-date-to">
                                </div>
                            </div>
                            <button onclick="performSearch()">Search Documents</button>
                        </div>
                        
                        <div class="export-options">
                            <button onclick="exportSelected('csv')" style="background: #27ae60">Export CSV</button>
                            <button onclick="exportSelected('excel')" style="background: #2980b9">Export Excel</button>
                            <button onclick="exportSelected('json')" style="background: #8e44ad">Export JSON</button>
                        </div>
                        
                        <div id="search-results">
                            <!-- Search results will be populated here -->
                        </div>
                    </div>
                </div>
                
                <!-- Batch Parse Tab -->
                <div id="batch-tab" class="tab-content">
                    <h2>Batch Parse Documents</h2>
                    <div class="user-info hidden" id="user-info-batch">
                        Welcome, <span id="user-name-batch"></span>!
                        <button class="logout-btn" onclick="logout()">Logout</button>
                    </div>
                    <div class="login-prompt" id="login-prompt-batch">
                        <p>Please login to process multiple documents</p>
                        <button onclick="switchTab('auth')">Go to Login</button>
                    </div>
                    <div class="hidden" id="batch-form">
                        <div class="form-group">
                            <label for="batch-files">Select Multiple Documents:</label>
                            <div class="file-input" id="batch-dropzone">
                                <p>📁 Drop multiple files here or click to browse</p>
                                <input type="file" id="batch-files" multiple accept=".pdf,.jpg,.jpeg,.png,.bmp,.tiff" style="display: none;">
                                <div id="batch-file-names">No files selected</div>
                            </div>
                        </div>
                        
                        <button onclick="batchParse()" id="batch-btn">Process Documents</button>
                        <div class="progress-bar hidden" id="batch-progress">
                            <div class="progress-fill" id="batch-progress-fill" style="width: 0%"></div>
                        </div>
                        <div class="result" id="batch-result"></div>
                    </div>
                </div>
                
                <!-- Authentication Tab -->
                <div id="auth-tab" class="tab-content">
                    <h2>Authentication</h2>
                    
                    <!-- Login Form -->
                    <div id="login-section">
                        <h3>Login</h3>
                        <div class="form-group">
                            <label for="login-email">Email:</label>
                            <input type="email" id="login-email" placeholder="your@email.com">
                        </div>
                        <div class="form-group">
                            <label for="login-password">Password:</label>
                            <input type="password" id="login-password" placeholder="Your password">
                        </div>
                        <button onclick="login()">Login</button>
                    </div>
                    
                    <!-- Register Form -->
                    <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #ddd;">
                        <h3>Register New Account</h3>
                        <div class="form-group">
                            <label for="reg-username">Username:</label>
                            <input type="text" id="reg-username" placeholder="Choose a username">
                        </div>
                        <div class="form-group">
                            <label for="reg-email">Email:</label>
                            <input type="email" id="reg-email" placeholder="your@email.com">
                        </div>
                        <div class="form-group">
                            <label for="reg-password">Password:</label>
                            <input type="password" id="reg-password" placeholder="At least 6 characters">
                        </div>
                        <div class="form-group">
                            <label for="reg-firstname">First Name:</label>
                            <input type="text" id="reg-firstname" placeholder="Your first name">
                        </div>
                        <div class="form-group">
                            <label for="reg-lastname">Last Name:</label>
                            <input type="text" id="reg-lastname" placeholder="Your last name">
                        </div>
                        <button onclick="register()">Register</button>
                    </div>
                    
                    <div class="result" id="auth-result"></div>
                </div>
            </div>
        </div>

            <script>
            let currentUser = null;
            let authToken = localStorage.getItem('authToken');
            let selectedDocuments = new Set();
            
            // Check if user is already logged in
            if (authToken) {
                checkAuthStatus();
            } else {
                // Show login prompts by default
                document.querySelectorAll('.login-prompt').forEach(el => el.style.display = 'block');
                document.querySelectorAll('.user-info').forEach(el => el.style.display = 'none');
            }
            
            function switchTab(tabName) {
                console.log('Switching to tab:', tabName);
                
                // Hide all tabs
                document.querySelectorAll('.tab-content').forEach(tab => {
                    tab.classList.remove('active');
                    tab.style.display = 'none';
                });
                document.querySelectorAll('.tab').forEach(tab => {
                    tab.classList.remove('active');
                });
                
                // Show selected tab
                const targetTab = document.getElementById(tabName + '-tab');
                if (targetTab) {
                    targetTab.classList.add('active');
                    targetTab.style.display = 'block';
                }
                
                // Activate the clicked tab
                event.target.classList.add('active');
                
                // Special handling for certain tabs
                if (tabName === 'health') {
                    checkHealth();
                } else if (tabName === 'search') {
                    loadSearchFacets();
                }
            }
            
            function showMessage(elementId, message, type = 'info') {
                const element = document.getElementById(elementId);
                if (element) {
                    element.innerHTML = message;
                    element.className = `result ${type}`;
                    element.style.display = 'block';
                    
                    // Auto-hide success messages after 5 seconds
                    if (type === 'success') {
                        setTimeout(() => {
                            element.style.display = 'none';
                        }, 5000);
                    }
                }
            }
            
            function checkHealth() {
                fetch('/api/health')
                    .then(response => response.json())
                    .then(data => {
                        const statusDiv = document.getElementById('health-status');
                        const resultDiv = document.getElementById('health-result');
                        
                        if (data.success) {
                            statusDiv.className = 'status healthy';
                            statusDiv.innerHTML = '✅ System is Healthy';
                            
                            resultDiv.innerHTML = `
                                <h3>System Information:</h3>
                                <p><strong>Service:</strong> ${data.data.service}</p>
                                <p><strong>Version:</strong> ${data.data.version}</p>
                                <p><strong>Model Loaded:</strong> ${data.data.model_loaded ? '✅ Yes' : '❌ No'}</p>
                                <p><strong>Database:</strong> ${data.data.database_connected ? '✅ Connected' : '❌ Disconnected'}</p>
                                <p><strong>Total Users:</strong> ${data.data.total_users || 0}</p>
                                <p><strong>Total Documents:</strong> ${data.data.total_documents || 0}</p>
                            `;
                        } else {
                            statusDiv.className = 'status error';
                            statusDiv.innerHTML = '❌ System Error';
                            resultDiv.innerHTML = `<p>Error: ${data.message}</p>`;
                        }
                        resultDiv.style.display = 'block';
                    })
                    .catch(error => {
                        document.getElementById('health-status').className = 'status error';
                        document.getElementById('health-status').innerHTML = '❌ Connection Failed';
                        document.getElementById('health-result').innerHTML = `<p>Error: ${error}</p>`;
                        document.getElementById('health-result').style.display = 'block';
                    });
            }
            
            // File upload handling
            document.getElementById('file-dropzone').addEventListener('click', () => {
                document.getElementById('document-file').click();
            });
            
            document.getElementById('batch-dropzone').addEventListener('click', () => {
                document.getElementById('batch-files').click();
            });
            
            document.getElementById('document-file').addEventListener('change', (e) => {
                const file = e.target.files[0];
                document.getElementById('file-name').textContent = file ? file.name : 'No file selected';
            });
            
            document.getElementById('batch-files').addEventListener('change', (e) => {
                const files = e.target.files;
                document.getElementById('batch-file-names').textContent = 
                    files.length > 0 ? `${files.length} files selected` : 'No files selected';
            });
            
            // Authentication functions
            function login() {
                const email = document.getElementById('login-email').value;
                const password = document.getElementById('login-password').value;
                
                if (!email || !password) {
                    alert('Please enter both email and password');
                    return;
                }
                
                console.log('Attempting login for:', email);
                
                fetch('/api/auth/login', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ email, password })
                })
                .then(response => {
                    if (!response.ok) {
                        throw new Error(`HTTP error! status: ${response.status}`);
                    }
                    return response.json();
                })
                .then(data => {
                    console.log('Login response:', data);
                    if (data.success) {
                        authToken = data.data.access_token;
                        currentUser = data.data.user;
                        localStorage.setItem('authToken', authToken);
                        showMessage('auth-result', `✅ Login successful! Welcome ${currentUser.first_name}`, 'success');
                        updateUIForAuth();
                    } else {
                        showMessage('auth-result', `❌ Login failed: ${data.message}`, 'error');
                    }
                })
                .catch(error => {
                    console.error('Login error:', error);
                    showMessage('auth-result', `❌ Network error: ${error.message}`, 'error');
                });
            }
            
            function register() {
                const userData = {
                    username: document.getElementById('reg-username').value,
                    email: document.getElementById('reg-email').value,
                    password: document.getElementById('reg-password').value,
                    first_name: document.getElementById('reg-firstname').value,
                    last_name: document.getElementById('reg-lastname').value
                };
                
                // Basic validation
                if (!userData.username || !userData.email || !userData.password) {
                    alert('Please fill in all required fields');
                    return;
                }
                
                console.log('Attempting registration for:', userData.email);
                
                fetch('/api/auth/register', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(userData)
                })
                .then(response => {
                    if (!response.ok) {
                        throw new Error(`HTTP error! status: ${response.status}`);
                    }
                    return response.json();
                })
                .then(data => {
                    console.log('Registration response:', data);
                    if (data.success) {
                        showMessage('auth-result', '✅ Registration successful! You can now login.', 'success');
                        // Clear form
                        document.getElementById('reg-username').value = '';
                        document.getElementById('reg-email').value = '';
                        document.getElementById('reg-password').value = '';
                        document.getElementById('reg-firstname').value = '';
                        document.getElementById('reg-lastname').value = '';
                    } else {
                        showMessage('auth-result', `❌ Registration failed: ${data.message}`, 'error');
                    }
                })
                .catch(error => {
                    console.error('Registration error:', error);
                    showMessage('auth-result', `❌ Network error: ${error.message}`, 'error');
                });
            }
            
            function checkAuthStatus() {
                if (!authToken) {
                    console.log('No auth token found');
                    return;
                }
                
                console.log('Checking auth status with token:', authToken.substring(0, 20) + '...');
                
                fetch('/api/auth/profile', {
                    headers: { 'Authorization': 'Bearer ' + authToken }
                })
                .then(response => {
                    if (!response.ok) {
                        throw new Error(`HTTP error! status: ${response.status}`);
                    }
                    return response.json();
                })
                .then(data => {
                    console.log('Auth status response:', data);
                    if (data.success) {
                        currentUser = data.data;
                        updateUIForAuth();
                    } else {
                        console.log('Auth check failed, removing token');
                        localStorage.removeItem('authToken');
                        authToken = null;
                    }
                })
                .catch(error => {
                    console.error('Auth status check error:', error);
                    localStorage.removeItem('authToken');
                    authToken = null;
                });
            }
            
            function updateUIForAuth() {
                console.log('Updating UI for authenticated user:', currentUser);
                
                // Update all user info sections
                document.querySelectorAll('#user-name, #user-name-batch, #user-name-search').forEach(el => {
                    if (currentUser && currentUser.first_name) {
                        el.textContent = currentUser.first_name + ' ' + currentUser.last_name;
                    }
                });
                
                // Show authenticated content
                document.querySelectorAll('.user-info').forEach(el => {
                    el.classList.remove('hidden');
                    el.style.display = 'block';
                });
                document.querySelectorAll('.login-prompt').forEach(el => {
                    el.classList.add('hidden');
                    el.style.display = 'none';
                });
                document.querySelectorAll('#parse-form, #batch-form, #search-form').forEach(el => {
                    el.classList.remove('hidden');
                    el.style.display = 'block';
                });
            }
            
            function logout() {
                console.log('Logging out user');
                localStorage.removeItem('authToken');
                authToken = null;
                currentUser = null;
                
                // Update UI
                document.querySelectorAll('.user-info').forEach(el => {
                    el.classList.add('hidden');
                    el.style.display = 'none';
                });
                document.querySelectorAll('.login-prompt').forEach(el => {
                    el.classList.remove('hidden');
                    el.style.display = 'block';
                });
                document.querySelectorAll('#parse-form, #batch-form, #search-form').forEach(el => {
                    el.classList.add('hidden');
                    el.style.display = 'none';
                });
                
                // Switch to health tab
                switchTab('health');
                showMessage('auth-result', '✅ Logged out successfully', 'success');
            }
            
            // Document parsing functions
            function parseDocument() {
                if (!authToken) {
                    alert('Please login first');
                    switchTab('auth');
                    return;
                }
                
                const fileInput = document.getElementById('document-file');
                const useMl = document.getElementById('use-ml').value;
                const useAsync = document.getElementById('async-processing') ? document.getElementById('async-processing').checked : false;
                
                if (!fileInput.files[0]) {
                    alert('Please select a file');
                    return;
                }
                
                const formData = new FormData();
                formData.append('file', fileInput.files[0]);
                formData.append('use_ml', useMl);
                formData.append('async', useAsync.toString());
                
                const parseBtn = document.getElementById('parse-btn');
                parseBtn.disabled = true;
                parseBtn.textContent = 'Processing...';
                
                fetch('/api/documents/parse', {
                    method: 'POST',
                    headers: { 'Authorization': 'Bearer ' + authToken },
                    body: formData
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        showMessage('parse-result', `
                            <h3>✅ Document Parsed Successfully!</h3>
                            <p><strong>File:</strong> ${data.data.filename}</p>
                            <p><strong>Type:</strong> ${data.data.document_type}</p>
                            <p><strong>Processing Time:</strong> ${data.data.processing_time}</p>
                            <details>
                                <summary>View Extraction Details</summary>
                                <pre>${JSON.stringify(data.data.extraction, null, 2)}</pre>
                            </details>
                        `, 'success');
                    } else {
                        showMessage('parse-result', `❌ Error: ${data.message}`, 'error');
                    }
                })
                .catch(error => {
                    showMessage('parse-result', `❌ Error: ${error}`, 'error');
                })
                .finally(() => {
                    parseBtn.disabled = false;
                    parseBtn.textContent = 'Parse Document';
                });
            }
            
            function batchParse() {
                if (!authToken) {
                    alert('Please login first');
                    switchTab('auth');
                    return;
                }
                
                const fileInput = document.getElementById('batch-files');
                
                if (!fileInput.files.length) {
                    alert('Please select files');
                    return;
                }
                
                const formData = new FormData();
                for (let file of fileInput.files) {
                    formData.append('files', file);
                }
                
                const batchBtn = document.getElementById('batch-btn');
                batchBtn.disabled = true;
                batchBtn.textContent = 'Processing...';
                
                fetch('/api/documents/batch_parse', {
                    method: 'POST',
                    headers: { 'Authorization': 'Bearer ' + authToken },
                    body: formData
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        const successful = data.data.documents.filter(d => d.success).length;
                        const total = data.data.documents.length;
                        
                        showMessage('batch-result', `
                            <h3>✅ Batch Processing Complete!</h3>
                            <p><strong>Processed:</strong> ${successful}/${total} documents successfully</p>
                            <details>
                                <summary>View Results</summary>
                                <pre>${JSON.stringify(data.data.documents, null, 2)}</pre>
                            </details>
                        `, 'success');
                    } else {
                        showMessage('batch-result', `❌ Error: ${data.message}`, 'error');
                    }
                })
                .catch(error => {
                    showMessage('batch-result', `❌ Error: ${error}`, 'error');
                })
                .finally(() => {
                    batchBtn.disabled = false;
                    batchBtn.textContent = 'Process Documents';
                });
            }
            
            // Search functionality
            function loadSearchFacets() {
                if (!authToken) return;
                
                fetch('/api/documents/search/facets', {
                    headers: {'Authorization': 'Bearer ' + authToken}
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        console.log('Search facets loaded:', data.data);
                    }
                });
            }
            
            function performSearch() {
                if (!authToken) {
                    alert('Please login first');
                    switchTab('auth');
                    return;
                }
                
                const searchParams = {
                    search_text: document.getElementById('search-text').value,
                    document_types: [document.getElementById('search-doc-type').value],
                    date_from: document.getElementById('search-date-from').value,
                    date_to: document.getElementById('search-date-to').value,
                    page: 1,
                    per_page: 20
                };
                
                // Remove 'all' from document types
                if (searchParams.document_types[0] === 'all') {
                    searchParams.document_types = [];
                }
                
                fetch('/api/documents/search', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': 'Bearer ' + authToken
                    },
                    body: JSON.stringify(searchParams)
                })
                .then(response => response.json())
                .then(data => {
                    displaySearchResults(data);
                })
                .catch(error => {
                    console.error('Search error:', error);
                    showMessage('search-results', `❌ Search error: ${error}`, 'error');
                });
            }
            
            function displaySearchResults(data) {
                const resultsDiv = document.getElementById('search-results');
                
                if (!data.success || !data.results || data.results.length === 0) {
                    resultsDiv.innerHTML = '<div class="result info"><p>No documents found matching your search criteria.</p></div>';
                    return;
                }
                
                let html = `<h3>Found ${data.total_count} documents</h3>`;
                html += '<div class="document-grid">';
                
                data.results.forEach(doc => {
                    html += `
                        <div class="document-card">
                            <div class="document-thumbnail">
                                ${doc.document_type ? doc.document_type.toUpperCase() : 'DOCUMENT'}
                            </div>
                            <h4>${doc.filename}</h4>
                            <p><strong>Type:</strong> ${doc.document_type || 'Unknown'}</p>
                            <p><strong>Date:</strong> ${doc.created_at ? new Date(doc.created_at).toLocaleDateString() : 'Unknown'}</p>
                            <p><strong>Size:</strong> ${doc.file_size ? (doc.file_size / 1024).toFixed(1) + ' KB' : 'Unknown'}</p>
                            <div class="document-actions">
                                <button onclick="viewDocument('${doc.id}')">View</button>
                                <button onclick="toggleSelectDocument('${doc.id}')">Select</button>
                            </div>
                        </div>
                    `;
                });
                
                html += '</div>';
                resultsDiv.innerHTML = html;
            }
            
            function toggleSelectDocument(docId) {
                if (selectedDocuments.has(docId)) {
                    selectedDocuments.delete(docId);
                } else {
                    selectedDocuments.add(docId);
                }
                updateSelectedCount();
            }
            
            function updateSelectedCount() {
                console.log('Selected documents:', selectedDocuments.size);
            }
            
            function exportSelected(format) {
                if (selectedDocuments.size === 0) {
                    alert('Please select documents to export');
                    return;
                }
                
                const docIds = Array.from(selectedDocuments);
                
                fetch('/api/documents/export', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': 'Bearer ' + authToken
                    },
                    body: JSON.stringify({
                        document_ids: docIds,
                        format: format
                    })
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        showMessage('search-results', `✅ Export started! Task ID: ${data.data.task_id}`, 'success');
                        monitorExportTask(data.data.task_id);
                    } else {
                        alert('Export failed: ' + data.message);
                    }
                })
                .catch(error => {
                    alert('Export error: ' + error);
                });
            }
            
            function monitorExportTask(taskId) {
                const checkStatus = () => {
                    fetch('/api/tasks/' + taskId, {
                        headers: {'Authorization': 'Bearer ' + authToken}
                    })
                    .then(response => response.json())
                    .then(data => {
                        if (data.data.status === 'SUCCESS') {
                            // Download the export file
                            window.location.href = data.data.result.download_url;
                        } else if (data.data.status === 'PROGRESS' || data.data.status === 'PENDING') {
                            setTimeout(checkStatus, 1000);
                        }
                    });
                };
                checkStatus();
            }
            
            function viewDocument(docId) {
                alert('View document: ' + docId);
                // Implement document viewing logic here
            }
            
            // Initial health check
            checkHealth();
            
            // Initialize the first tab
            document.addEventListener('DOMContentLoaded', function() {
                switchTab('health');
            });
        </script>
    </body>
    </html>
    """
    return html_content

# ============================================================================
# EXISTING API ROUTES (ORIGINAL FUNCTIONALITY)
# ============================================================================

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        total_users = users_collection.count_documents({}) if users_collection is not None else 0
        total_documents = documents_collection.count_documents({}) if documents_collection is not None else 0
        
        health_data = {
            "status": "healthy",
            "service": "Document Parser API",
            "version": "3.0.0",  # Updated version
            "timestamp": datetime.now().isoformat(),
            "model_loaded": parser.is_trained if parser else False,
            "model_classes": parser.label_encoder.classes_.tolist() if parser and parser.is_trained else [],
            "database_connected": MONGODB_CONNECTED,
            "total_users": total_users,
            "total_documents": total_documents,
            "features": {
                "search_engine": True,
                "export_system": True,
                "document_previews": True,
                "rate_limiting": True,
                "background_processing": True
            }
        }
        return format_api_response(True, health_data, "Service is healthy")
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return format_api_response(False, None, f"Health check failed: {str(e)}", 500)

@app.route('/api/auth/register', methods=['POST'])
def register():
    """Register a new user"""
    try:
        data = request.get_json()
        
        if not data:
            return format_api_response(False, None, "No data provided", 400)
        
        required_fields = ['username', 'email', 'password', 'first_name', 'last_name']
        missing_fields = [field for field in required_fields if field not in data]
        
        if missing_fields:
            return format_api_response(False, None, f"Missing required fields: {', '.join(missing_fields)}", 400)
        
        # Validate email
        if not validate_email(data['email']):
            return format_api_response(False, None, "Invalid email format", 400)
        
        # Validate password
        is_valid_password, password_message = validate_password(data['password'])
        if not is_valid_password:
            return format_api_response(False, None, password_message, 400)
        
        # Check if user already exists
        if users_collection is not None and users_collection.find_one({'$or': [{'email': data['email']}, {'username': data['username']}]}):
            return format_api_response(False, None, "User with this email or username already exists", 409)
        
        # Create user document
        user_doc = {
            'username': data['username'],
            'email': data['email'],
            'password_hash': generate_password_hash(data['password']),
            'first_name': data['first_name'],
            'last_name': data['last_name'],
            'created_at': datetime.now(),
            'updated_at': datetime.now(),
            'is_active': True,
            'plan': 'free',
            'document_limit': 1000,
            'used_documents': 0,
            'last_reset': datetime.now()
        }
        
        # Insert user
        if users_collection is not None:
            result = users_collection.insert_one(user_doc)
            user_id = str(result.inserted_id)
        else:
            # Fallback without database
            user_id = str(uuid.uuid4())
        
        # Create access token
        access_token = create_access_token(identity=user_id)
        
        user_data = {
            'user_id': user_id,
            'username': data['username'],
            'email': data['email'],
            'first_name': data['first_name'],
            'last_name': data['last_name'],
            'plan': 'free',
            'document_limit': 1000,
            'used_documents': 0
        }
        
        log_api_activity(user_id, '/api/auth/register', 'POST', 'success')
        return format_api_response(True, {
            'user': user_data,
            'access_token': access_token
        }, "User registered successfully")
        
    except DuplicateKeyError:
        return format_api_response(False, None, "User with this email or username already exists", 409)
    except Exception as e:
        logger.error(f"Registration error: {e}")
        return format_api_response(False, None, "Registration failed", 500)

@app.route('/api/auth/login', methods=['POST'])
def login():
    """Login user and return access token"""
    try:
        data = request.get_json()
        
        if not data or 'email' not in data or 'password' not in data:
            return format_api_response(False, None, "Email and password required", 400)
        
        # Find user by email
        user = None
        if users_collection is not None:
            user = users_collection.find_one({'email': data['email'], 'is_active': True})
        
        # Demo fallback - allow login with any credentials if no DB
        if users_collection is None:
            user = {
                '_id': 'demo-user-id',
                'email': data['email'],
                'first_name': 'Demo',
                'last_name': 'User',
                'username': 'demo',
                'plan': 'free',
                'document_limit': 1000,
                'used_documents': 0
            }
            password_valid = True  # Accept any password in demo mode
        else:
            password_valid = user and check_password_hash(user['password_hash'], data['password'])
        
        if not user or not password_valid:
            return format_api_response(False, None, "Invalid email or password", 401)
        
        # Update last login
        if users_collection is not None:
            users_collection.update_one(
                {'_id': user['_id']},
                {'$set': {'last_login': datetime.now()}}
            )
        
        user_id = str(user['_id']) if users_collection is not None else 'demo-user-id'
        
        # Create access token
        access_token = create_access_token(identity=user_id)
        
        user_data = {
            'user_id': user_id,
            'username': user['username'],
            'email': user['email'],
            'first_name': user['first_name'],
            'last_name': user['last_name'],
            'plan': user.get('plan', 'free'),
            'document_limit': user.get('document_limit', 1000),
            'used_documents': user.get('used_documents', 0)
        }
        
        log_api_activity(user_id, '/api/auth/login', 'POST', 'success')
        return format_api_response(True, {
            'user': user_data,
            'access_token': access_token
        }, "Login successful")
        
    except Exception as e:
        logger.error(f"Login error: {e}")
        return format_api_response(False, None, "Login failed", 500)

@app.route('/api/auth/profile', methods=['GET'])
@jwt_required()
def get_profile():
    """Get user profile"""
    try:
        user_id = get_jwt_identity()
        
        # Demo user handling
        if user_id == 'demo-user-id':
            user_data = {
                'user_id': 'demo-user-id',
                'username': 'demo',
                'email': 'demo@example.com',
                'first_name': 'Demo',
                'last_name': 'User',
                'plan': 'free',
                'document_limit': 1000,
                'used_documents': 0
            }
            return format_api_response(True, user_data, "Profile retrieved successfully")
        
        if users_collection is not None:
            user = users_collection.find_one({'_id': ObjectId(user_id)})
            
            if not user:
                return format_api_response(False, None, "User not found", 404)
            
            user_data = {
                'user_id': str(user['_id']),
                'username': user['username'],
                'email': user['email'],
                'first_name': user['first_name'],
                'last_name': user['last_name'],
                'plan': user.get('plan', 'free'),
                'document_limit': user.get('document_limit', 1000),
                'used_documents': user.get('used_documents', 0),
                'created_at': user['created_at'].isoformat() if user.get('created_at') else None,
                'last_login': user.get('last_login', {}).isoformat() if user.get('last_login') else None
            }
            
            log_api_activity(user_id, '/api/auth/profile', 'GET', 'success')
            return format_api_response(True, user_data, "Profile retrieved successfully")
        else:
            return format_api_response(False, None, "Database not available", 503)
            
    except Exception as e:
        logger.error(f"Profile retrieval error: {e}")
        return format_api_response(False, None, "Failed to retrieve profile", 500)

# ============================================================================
# NEW TECHNICAL IMPROVEMENTS API ROUTES
# ============================================================================

@app.route('/api/documents/search', methods=['POST'])
@jwt_required()
def search_documents():
    """Advanced document search with filtering - FIXED VERSION"""
    try:
        user_id = get_jwt_identity()
        search_query = request.get_json()
        
        if not search_query:
            return format_api_response(False, None, "Search query required", 400)
        
        # Validate and set defaults
        if not isinstance(search_query, dict):
            return format_api_response(False, None, "Invalid search query format", 400)
        
        # Set default values
        search_query.setdefault('page', 1)
        search_query.setdefault('per_page', 20)
        search_query.setdefault('document_types', ['all'])
        
        results = search_engine.search_documents(user_id, search_query)
        return jsonify(results)
        
    except Exception as e:
        logger.error(f"Search error: {e}")
        return format_api_response(False, None, f"Search failed: {str(e)}", 500)

@app.route('/api/documents/search/facets', methods=['GET'])
@jwt_required()
def get_search_facets():
    """Get available search facets - FIXED VERSION"""
    try:
        user_id = get_jwt_identity()
        facets = search_engine.get_search_facets(user_id)
        return format_api_response(True, facets, "Facets retrieved successfully")
    except Exception as e:
        logger.error(f"Facets error: {e}")
        return format_api_response(False, None, f"Failed to get facets: {str(e)}", 500)

@app.route('/api/documents/export', methods=['POST'])
@jwt_required()
def export_documents():
    """Export documents in various formats - FIXED VERSION"""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        
        if not data or 'document_ids' not in data:
            return format_api_response(False, None, "Document IDs required", 400)
        
        export_format = data.get('format', 'csv')
        document_ids = data['document_ids']
        
        # Validate export format
        valid_formats = ['csv', 'excel', 'json']
        if export_format not in valid_formats:
            return format_api_response(False, None, f"Invalid export format. Supported: {', '.join(valid_formats)}", 400)
        
        # Check if we have documents to export
        if not document_ids:
            return format_api_response(False, None, "No documents selected for export", 400)
        
        # For now, use synchronous export (simpler)
        try:
            if export_format == 'csv':
                export_result = export_manager.export_to_csv(document_ids, user_id)
                file_extension = '.csv'
                mime_type = 'text/csv'
            elif export_format == 'excel':
                export_result = export_manager.export_to_excel(document_ids, user_id)
                file_extension = '.xlsx'
                mime_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            elif export_format == 'json':
                export_result = export_manager.export_to_json(document_ids, user_id)
                file_extension = '.json'
                mime_type = 'application/json'
            
            # Generate filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            export_filename = f"export_{timestamp}{file_extension}"
            export_path = f"data/exports/{export_filename}"
            
            # Ensure directory exists
            os.makedirs("data/exports", exist_ok=True)
            
            # Save the export file
            if hasattr(export_result, 'getvalue'):
                # It's a BytesIO or StringIO object
                mode = 'wb' if export_format != 'csv' else 'w'
                with open(export_path, mode) as f:
                    f.write(export_result.getvalue())
            else:
                # It's a string (JSON)
                with open(export_path, 'w', encoding='utf-8') as f:
                    f.write(export_result)
            
            logger.info(f"Export created: {export_filename} with {len(document_ids)} documents")
            
            return format_api_response(True, {
                "export_format": export_format,
                "export_filename": export_filename,
                "download_url": f"/api/exports/download/{export_filename}",
                "document_count": len(document_ids),
                "file_size": os.path.getsize(export_path) if os.path.exists(export_path) else 0
            }, "Export completed successfully")
            
        except Exception as export_error:
            logger.error(f"Export generation error: {export_error}")
            return format_api_response(False, None, f"Export generation failed: {str(export_error)}", 500)
        
    except Exception as e:
        logger.error(f"Export endpoint error: {e}")
        return format_api_response(False, None, f"Export failed: {str(e)}", 500)

@app.route('/api/exports/list', methods=['GET'])
@jwt_required()
def list_exports():
    """List available export files for the user"""
    try:
        user_id = get_jwt_identity()
        exports_dir = Path("data/exports")
        
        if not exports_dir.exists():
            return format_api_response(True, {"exports": []}, "No exports available")
        
        # Get export files (you might want to filter by user_id in filename)
        export_files = []
        for file_path in exports_dir.glob("export_*"):
            if file_path.is_file():
                export_files.append({
                    "filename": file_path.name,
                    "file_size": file_path.stat().st_size,
                    "created_time": datetime.fromtimestamp(file_path.stat().st_mtime).isoformat(),
                    "download_url": f"/api/exports/download/{file_path.name}"
                })
        
        # Sort by creation time (newest first)
        export_files.sort(key=lambda x: x["created_time"], reverse=True)
        
        return format_api_response(True, {"exports": export_files}, "Exports listed successfully")
        
    except Exception as e:
        logger.error(f"Error listing exports: {e}")
        return format_api_response(False, None, f"Failed to list exports: {str(e)}", 500)
    
@app.route('/api/exports/download/<filename>', methods=['GET'])
@jwt_required()
def download_export(filename):
    """Download exported file"""
    try:
        export_path = os.path.join("data/exports", filename)
        
        if not os.path.exists(export_path):
            return format_api_response(False, None, "Export file not found", 404)
        
        # Determine MIME type
        if filename.endswith('.csv'):
            mimetype = 'text/csv'
        elif filename.endswith('.xlsx'):
            mimetype = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        elif filename.endswith('.json'):
            mimetype = 'application/json'
        else:
            mimetype = 'application/octet-stream'
        
        return send_file(export_path, as_attachment=True, download_name=filename, mimetype=mimetype)
        
    except Exception as e:
        logger.error(f"Download error: {e}")
        return format_api_response(False, None, "Download failed", 500)

@app.route('/api/previews/<document_id>/thumbnail', methods=['GET'])
@jwt_required()
def get_document_thumbnail(document_id):
    """Get document thumbnail"""
    try:
        thumbnail_path = preview_generator.previews_dir / f"{document_id}_thumbnail.png"
        if not thumbnail_path.exists():
            thumbnail_path = preview_generator.previews_dir / f"{document_id}_thumbnail.jpg"
        
        if thumbnail_path.exists():
            return send_file(str(thumbnail_path), mimetype='image/png')
        else:
            return format_api_response(False, None, "Thumbnail not found", 404)
            
    except Exception as e:
        logger.error(f"Thumbnail error: {e}")
        return format_api_response(False, None, "Failed to get thumbnail", 500)

@app.route('/api/previews/<document_id>/preview', methods=['GET'])
@jwt_required()
def get_document_preview(document_id):
    """Get document preview"""
    try:
        preview_path = preview_generator.previews_dir / f"{document_id}_preview.png"
        if not preview_path.exists():
            preview_path = preview_generator.previews_dir / f"{document_id}_preview.jpg"
        
        if preview_path.exists():
            return send_file(str(preview_path), mimetype='image/png')
        else:
            return format_api_response(False, None, "Preview not found", 404)
            
    except Exception as e:
        logger.error(f"Preview error: {e}")
        return format_api_response(False, None, "Failed to get preview", 500)

@app.route('/api/tasks/<task_id>', methods=['GET'])
@jwt_required()
def get_task_status_endpoint(task_id):
    """Get status of a background task"""
    try:
        status = get_task_status(task_id)
        return format_api_response(True, status, "Task status retrieved")
    except Exception as e:
        logger.error(f"Task status error: {e}")
        return format_api_response(False, None, "Failed to get task status", 500)

@app.route('/api/documents/async_parse', methods=['POST'])
@jwt_required()
def async_parse_document():
    """Parse document asynchronously - FIXED VERSION"""
    try:
        user_id = get_jwt_identity()
        
        if 'file' not in request.files:
            return format_api_response(False, None, "No file provided", 400)
        
        file = request.files['file']
        if file.filename == '':
            return format_api_response(False, None, "No file selected", 400)
        
        # Check if Celery is available
        try:
            from src.celery_app import process_document_async
            CELERY_AVAILABLE = True
        except ImportError:
            CELERY_AVAILABLE = False
            logger.warning("Celery not available, falling back to sync processing")
        
        if not CELERY_AVAILABLE:
            # Fall back to sync processing
            return original_parse_document()
        
        # Save file to temporary location
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp_file:
            file.save(tmp_file.name)
            tmp_path = tmp_file.name
        
        # Start background task
        document_id = str(uuid.uuid4())
        use_ml = request.form.get('use_ml', 'true').lower() == 'true'
        
        task = process_document_async.delay(tmp_path, user_id, document_id, use_ml)
        
        return format_api_response(True, {
            "task_id": task.id,
            "document_id": document_id,
            "status": "processing",
            "message": "Document processing started in background"
        }, "Async processing started")
        
    except Exception as e:
        logger.error(f"Async parse error: {e}")
        return format_api_response(False, None, f"Async processing failed: {str(e)}", 500)
    
# ============================================================================
# NEW: DOCUMENT VIEWING & MANAGEMENT ENDPOINTS
# ============================================================================

@app.route('/api/documents/<document_id>', methods=['GET'])
@jwt_required()
def get_document(document_id):
    """Get full document details by ID"""
    try:
        user_id = get_jwt_identity()
        
        # Demo user handling
        if user_id == 'demo-user-id':
            return format_api_response(False, None, "Demo user cannot view documents", 403)
        
        if documents_collection is None:
            return format_api_response(False, None, "Document storage not available", 503)
        
        # Find document by document_id and user_id (for security)
        document = documents_collection.find_one({
            "document_id": document_id,
            "user_id": user_id
        })
        
        if not document:
            return format_api_response(False, None, "Document not found", 404)
        
        # Convert ObjectId to string and format dates
        document['_id'] = str(document['_id'])
        if document.get('created_at'):
            document['created_at'] = document['created_at'].isoformat()
        if document.get('updated_at'):
            document['updated_at'] = document['updated_at'].isoformat()
        
        log_api_activity(user_id, f'/api/documents/{document_id}', 'GET', 'success')
        return format_api_response(True, document, "Document retrieved successfully")
        
    except Exception as e:
        logger.error(f"Error getting document {document_id}: {e}")
        return format_api_response(False, None, f"Failed to retrieve document: {str(e)}", 500)

@app.route('/api/documents/<document_id>/preview', methods=['GET'])
@jwt_required()
def get_document_preview_full(document_id):
    """Get complete document preview with all extraction data"""
    try:
        user_id = get_jwt_identity()
        
        if documents_collection is None:
            return format_api_response(False, None, "Document storage not available", 503)
        
        # Find document
        document = documents_collection.find_one({
            "document_id": document_id,
            "user_id": user_id
        })
        
        if not document:
            return format_api_response(False, None, "Document not found", 404)
        
        # Get preview URLs
        preview_urls = preview_generator.get_preview_urls(document_id)
        
        # Format response with all document data
        response_data = {
            "document_info": {
                "document_id": document.get("document_id"),
                "filename": document.get("filename"),
                "document_type": document.get("document_type"),
                "file_type": document.get("file_type"),
                "file_size": document.get("file_size"),
                "created_at": document.get("created_at").isoformat() if document.get("created_at") else None,
                "processing_time": document.get("processing_time")
            },
            "extraction_data": document.get("extraction_data", {}),
            "preview_data": {
                **preview_urls,
                "base64_thumbnail": preview_generator.generate_base64_thumbnail(document_id)
            },
            "text_content": {
                "preview": document.get("text_preview", ""),
                "full_text": document.get("full_text", "")[:5000]  # Limit for response
            }
        }
        
        return format_api_response(True, response_data, "Document preview retrieved")
        
    except Exception as e:
        logger.error(f"Error getting document preview {document_id}: {e}")
        return format_api_response(False, None, f"Failed to get document preview: {str(e)}", 500)

@app.route('/api/documents/<document_id>', methods=['DELETE'])
@jwt_required()
def delete_document(document_id):
    """Delete a document and its previews"""
    try:
        user_id = get_jwt_identity()
        
        if documents_collection is None:
            return format_api_response(False, None, "Document storage not available", 503)
        
        # Find and delete document
        result = documents_collection.delete_one({
            "document_id": document_id,
            "user_id": user_id
        })
        
        if result.deleted_count == 0:
            return format_api_response(False, None, "Document not found", 404)
        
        # Clean up preview files
        preview_generator.cleanup_previews(document_id)
        
        # Update user document count
        if users_collection is not None and user_id != 'demo-user-id':
            try:
                users_collection.update_one(
                    {'_id': ObjectId(user_id)},
                    {'$inc': {'used_documents': -1}}
                )
            except Exception as e:
                logger.error(f"Failed to update user document count: {e}")
        
        logger.info(f"Document {document_id} deleted by user {user_id}")
        log_api_activity(user_id, f'/api/documents/{document_id}', 'DELETE', 'success')
        return format_api_response(True, None, "Document deleted successfully")
        
    except Exception as e:
        logger.error(f"Error deleting document {document_id}: {e}")
        return format_api_response(False, None, f"Failed to delete document: {str(e)}", 500)

# ============================================================================
# UPDATED EXISTING ROUTES WITH NEW FEATURES
# ============================================================================

# Store reference to original parse_document for sync fallback
def original_parse_document():
    """Original sync document parsing implementation"""
    user_id = get_jwt_identity()
    
    if not parser:
        return format_api_response(False, None, "Document parser not available", 503)
    
    # Check if file was uploaded
    if 'file' not in request.files:
        return format_api_response(False, None, "No file provided", 400)
    
    file = request.files['file']
    
    # Check if file has a name
    if file.filename == '':
        return format_api_response(False, None, "No file selected", 400)
    
    # Check file type
    allowed_extensions = {'.pdf', '.jpg', '.jpeg', '.png', '.bmp', '.tiff'}
    file_ext = Path(file.filename).suffix.lower()
    
    if not (file and file_ext in allowed_extensions):
        return format_api_response(False, None, 
                                 f"Invalid file type. Supported: {', '.join(allowed_extensions)}", 400)
    
    # Create a temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp_file:
        file.save(tmp_file.name)
        tmp_path = tmp_file.name
    
    try:
        # Get parameters from request
        use_ml = request.form.get('use_ml', 'true').lower() == 'true'
        doc_type = request.form.get('doc_type', 'general')
        
        # Parse the document
        logger.info(f"Processing document: {file.filename}, User: {user_id}")
        
        result = parser.parse_document(tmp_path, doc_type=doc_type, use_ml=use_ml)
        
        # Generate preview for the document
        document_id = str(uuid.uuid4())
        preview_data = {}
        if result["success"]:
            if tmp_path.lower().endswith('.pdf'):
                preview_path, thumbnail_path = preview_generator.generate_pdf_preview(tmp_path, document_id)
            else:
                preview_path, thumbnail_path = preview_generator.generate_image_preview(tmp_path, document_id)
            
            preview_data = {
                "preview_generated": bool(preview_path),
                "preview_url": f"/api/previews/{document_id}/preview" if preview_path else None,
                "thumbnail_url": f"/api/previews/{document_id}/thumbnail" if thumbnail_path else None
            }
        
        # Clean up temporary file
        os.unlink(tmp_path)
        
        # Format the response
        if result["success"]:
            response_data = {
                "document_id": document_id,
                "document_type": result.get("document_type", "unknown"),
                "filename": file.filename,
                "extraction": {
                    'patterns': result.get("pattern_extraction", {}),
                    'contacts': result.get("contact_info", {}),
                    'names': result.get("name_info", {}),
                    'entities': result.get("entities", {}),
                    'features': result.get("ml_features", {})
                },
                "processing_time": result.get("extraction_time"),
                "text_preview": result.get("cleaned_text", "")[:500] + "..." 
                if len(result.get("cleaned_text", "")) > 500 
                else result.get("cleaned_text", ""),
                "preview_data": preview_data
            }
            
            # Save to database
            save_document_to_db(user_id, file.filename, file_ext[1:], 
                              len(file.read()) if hasattr(file, 'read') else 0, 
                              result, document_id, preview_data)
            
            log_api_activity(user_id, '/api/documents/parse', 'POST', 'success', 
                           {'filename': file.filename, 'document_type': result.get("document_type")})
            return format_api_response(True, response_data, "Document parsed successfully")
        else:
            log_api_activity(user_id, '/api/documents/parse', 'POST', 'error', 
                           {'filename': file.filename, 'error': result.get("error")})
            return format_api_response(False, None, result.get("error", "Unknown error occurred"), 500)
            
    except Exception as e:
        # Clean up temporary file in case of error
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        
        logger.error(f"Error processing document {file.filename} for user {user_id}: {str(e)}")
        log_api_activity(user_id, '/api/documents/parse', 'POST', 'error', {'filename': file.filename, 'error': str(e)})
        return format_api_response(False, None, f"Processing failed: {str(e)}", 500)

@app.route('/api/documents/parse', methods=['POST'])
@jwt_required()
def parse_document():
    """Parse document (sync or async based on parameter)"""
    use_async = request.form.get('async', 'false').lower() == 'true'
    
    if use_async:
        return async_parse_document()
    else:
        # Existing sync implementation
        return original_parse_document()

@app.route('/api/documents/batch_parse', methods=['POST'])
@jwt_required()
def batch_parse():
    """Parse multiple documents in a batch"""
    user_id = get_jwt_identity()
    
    if not parser:
        return format_api_response(False, None, "Document parser not available", 503)
    
    if 'files' not in request.files:
        return format_api_response(False, None, "No files provided", 400)
    
    files = request.files.getlist('files')
    results = []
    saved_count = 0
    
    for file in files:
        if file.filename == '':
            continue
            
        allowed_extensions = {'.pdf', '.jpg', '.jpeg', '.png', '.bmp', '.tiff'}
        file_ext = Path(file.filename).suffix.lower()
        
        if file and file_ext in allowed_extensions:
            with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp_file:
                file.save(tmp_file.name)
                tmp_path = tmp_file.name
            
            try:
                use_ml = request.form.get('use_ml', 'true').lower() == 'true'
                doc_type = request.form.get('doc_type', 'general')
                
                result = parser.parse_document(tmp_path, doc_type=doc_type, use_ml=use_ml)
                
                # Generate preview
                document_id = str(uuid.uuid4())
                preview_data = {}
                if result["success"]:
                    if tmp_path.lower().endswith('.pdf'):
                        preview_path, thumbnail_path = preview_generator.generate_pdf_preview(tmp_path, document_id)
                    else:
                        preview_path, thumbnail_path = preview_generator.generate_image_preview(tmp_path, document_id)
                    
                    preview_data = {
                        "preview_generated": bool(preview_path),
                        "preview_url": f"/api/previews/{document_id}/preview" if preview_path else None,
                        "thumbnail_url": f"/api/previews/{document_id}/thumbnail" if thumbnail_path else None
                    }
                
                # Save document to database if successful
                saved_doc_id = None
                if result["success"]:
                    saved_doc_id = save_document_to_db(
                        user_id=user_id,
                        filename=file.filename,
                        file_type=file_ext[1:],
                        file_size=len(file.read()) if hasattr(file, 'read') else 0,
                        result=result,
                        document_id=document_id,
                        preview_data=preview_data
                    )
                    if saved_doc_id:
                        saved_count += 1
                
                # Format the result for this file
                file_result = {
                    "filename": file.filename,
                    "success": result["success"],
                    "document_type": result.get("document_type", "unknown"),
                    "processing_time": result.get("extraction_time"),
                    "document_id": document_id,
                    "saved_to_db": saved_doc_id is not None,
                    "preview_data": preview_data
                }
                
                if result["success"]:
                    file_result["extraction"] = {
                        "patterns": result.get("pattern_extraction", {}),
                        "contacts": result.get("contact_info", {}),
                        "names": result.get("name_info", {}),
                        "entities": result.get("entities", {})
                    }
                else:
                    file_result["error"] = result.get("error", "Unknown error")
                
                results.append(file_result)
                
            except Exception as e:
                logger.error(f"Error processing document {file.filename}: {str(e)}")
                results.append({
                    "filename": file.filename,
                    "success": False,
                    "error": str(e)
                })
            
            finally:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
        else:
            results.append({
                "filename": file.filename,
                "success": False,
                "error": f"Invalid file type. Supported: {', '.join(allowed_extensions)}"
            })
    
    # Update user document count
    if saved_count > 0 and users_collection is not None and user_id != 'demo-user-id':
        try:
            users_collection.update_one(
                {'_id': ObjectId(user_id)},
                {'$inc': {'used_documents': saved_count}}
            )
            logger.info(f"Updated document count for user {user_id} by {saved_count}")
        except Exception as e:
            logger.error(f"Failed to update user document count: {e}")
    
    log_api_activity(user_id, '/api/documents/batch_parse', 'POST', 'success', 
                   {'total_files': len(files), 'successful': len([r for r in results if r['success']]), 'saved': saved_count})
    return format_api_response(True, {"documents": results}, f"Processed {len(results)} documents, saved {saved_count} to database")

def save_document_to_db(user_id, filename, file_type, file_size, result, document_id, preview_data=None):
    """Save parsed document to MongoDB with proper user association - FIXED VERSION"""
    if documents_collection is None:
        logger.warning("Database not available - skipping document save")
        return None
    
    try:
        # Validate user_id
        if not user_id or user_id == 'demo-user-id':
            logger.warning(f"Invalid user_id for document save: {user_id}")
            return None
            
        document_data = {
            'document_id': document_id,
            'user_id': user_id,
            'filename': filename,
            'file_type': file_type,
            'file_size': file_size,
            'document_type': result.get("document_type", "unknown"),
            'extraction_data': {
                'patterns': result.get("pattern_extraction", {}),
                'contacts': result.get("contact_info", {}),
                'names': result.get("name_info", {}),
                'entities': result.get("entities", {}),
                'features': result.get("ml_features", {})
            },
            'processing_time': result.get("extraction_time"),
            'text_preview': result.get("cleaned_text", "")[:2000],
            'full_text': result.get("cleaned_text", ""),
            'preview_data': preview_data or {},
            'created_at': datetime.now(),
            'updated_at': datetime.now()
        }
        
        # Insert into database
        result = documents_collection.insert_one(document_data)
        document_db_id = str(result.inserted_id)
        
        logger.info(f"Document saved to database for user {user_id}: {filename} (DB ID: {document_db_id})")
        return document_id
        
    except Exception as e:
        logger.error(f"Failed to save document to database for user {user_id}: {e}")
        return None

@app.route('/api/documents/my-documents', methods=['GET'])
@jwt_required()
def get_my_documents():
    """Get all documents for the current user"""
    try:
        user_id = get_jwt_identity()
        
        if documents_collection is not None:
            documents = list(documents_collection.find(
                {'user_id': user_id}
            ).sort('created_at', -1).limit(50))
            
            # Convert ObjectId to string for JSON serialization
            for doc in documents:
                doc['_id'] = str(doc['_id'])
                if doc.get('created_at'):
                    doc['created_at'] = doc['created_at'].isoformat()
            
            return format_api_response(True, {'documents': documents}, f"Retrieved {len(documents)} documents")
        else:
            return format_api_response(False, None, "Document storage not available", 503)
        
    except Exception as e:
        logger.error(f"Error getting user documents: {e}")
        return format_api_response(False, None, "Failed to retrieve documents", 500)

@app.route('/api/stats/my-stats', methods=['GET'])
@jwt_required()
def get_my_stats():
    """Get document statistics for the current user"""
    try:
        user_id = get_jwt_identity()
        
        if documents_collection is not None:
            total_documents = documents_collection.count_documents({'user_id': user_id})
            
            # Get document type distribution
            pipeline = [
                {'$match': {'user_id': user_id}},
                {'$group': {'_id': '$document_type', 'count': {'$sum': 1}}}
            ]
            type_distribution = list(documents_collection.aggregate(pipeline))
            
            stats = {
                'total_documents': total_documents,
                'type_distribution': type_distribution
            }
            
            return format_api_response(True, stats, "Statistics retrieved")
        else:
            return format_api_response(False, None, "Document storage not available", 503)
        
    except Exception as e:
        logger.error(f"Error getting user stats: {e}")
        return format_api_response(False, None, "Failed to retrieve statistics", 500)

# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.errorhandler(404)
def not_found(error):
    return format_api_response(False, None, "Endpoint not found", 404)

@app.errorhandler(500)
def internal_error(error):
    return format_api_response(False, None, "Internal server error", 500)

@jwt.unauthorized_loader
def unauthorized_response(callback):
    return format_api_response(False, None, "Missing or invalid token", 401)

@jwt.invalid_token_loader
def invalid_token_response(callback):
    return format_api_response(False, None, "Invalid token", 401)

@jwt.expired_token_loader
def expired_token_response(callback):
    return format_api_response(False, None, "Token has expired", 401)

# ============================================================================
# APPLICATION STARTUP
# ============================================================================

if __name__ == '__main__':
    # Create necessary directories
    os.makedirs('logs', exist_ok=True)
    os.makedirs('models', exist_ok=True)
    os.makedirs('data/previews', exist_ok=True)
    os.makedirs('data/exports', exist_ok=True)
    
    logger.info("Starting Enhanced Document Parser API Server")
    logger.info(f"Model loaded: {parser.is_trained if parser else False}")
    logger.info(f"Database connected: {MONGODB_CONNECTED}")
    logger.info("Search Engine: [READY]")
    logger.info("Export System: [READY]") 
    logger.info("Preview System: [READY]")
    logger.info("Background Processing: [READY]")
    logger.info("Web Interface: http://localhost:5000")
    logger.info("API Health: http://localhost:5000/api/health")
    
    # Run the Flask app
    app.run(host='0.0.0.0', port=5000, debug=True)