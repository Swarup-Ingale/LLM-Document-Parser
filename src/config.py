import os

# Base paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')
MODELS_DIR = os.path.join(BASE_DIR, 'models')
LOGS_DIR = os.path.join(BASE_DIR, 'logs')

# Data paths
RAW_DOCUMENTS_DIR = os.path.join(DATA_DIR, 'raw_documents')
TRAINING_DATA_DIR = os.path.join(DATA_DIR, 'training_data')
PROCESSED_DIR = os.path.join(DATA_DIR, 'processed')
PREVIEWS_DIR = os.path.join(DATA_DIR, 'previews')
EXPORTS_DIR = os.path.join(DATA_DIR, 'exports')

# Model paths
DEFAULT_MODEL_PATH = os.path.join(MODELS_DIR, 'document_classifier_modified_before_one_night.joblib')

# API settings
API_HOST = '0.0.0.0'
API_PORT = 5000

# Rate Limiting
RATE_LIMIT_STORAGE_URL = "redis://localhost:6379/0"
DEFAULT_RATE_LIMITS = ["200 per day", "50 per hour"]

# Celery Configuration
CELERY_BROKER_URL = "redis://localhost:6379/0"
CELERY_RESULT_BACKEND = "redis://localhost:6379/1"

# Search Configuration
MAX_SEARCH_RESULTS = 1000
SEARCH_PAGE_SIZE = 20

# Preview Configuration
THUMBNAIL_SIZE = (200, 280)
PREVIEW_SIZE = (800, 1120)

# Export Configuration
MAX_EXPORT_DOCUMENTS = 1000
EXPORT_RETENTION_DAYS = 7

# Ensure directories exist
for directory in [DATA_DIR, MODELS_DIR, LOGS_DIR, RAW_DOCUMENTS_DIR, 
                 TRAINING_DATA_DIR, PROCESSED_DIR, PREVIEWS_DIR, EXPORTS_DIR]:
    os.makedirs(directory, exist_ok=True)