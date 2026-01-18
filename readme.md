# LLM-Based Intelligent Document Parsing System

An advanced document parsing system powered by Large Language Models (LLMs) that automatically classifies PDF documents and extracts relevant structured information based on document type. The system is designed for scalability, reliability, and real-world usage with database integration, caching, export options, and a web interface.

---

## Prerequisites
    Python 3.8+
    OpenAI API key or compatible LLM API access
## Before Set up make sure to create Files Structure similar to 
    ```bash
    
        ├── data
        │   ├── exports
        │   ├── previews
        │   ├── processed
        │   │   ├── csv_exports
        │   │   ├── csv_outputs
        │   │   ├── json_outputs
        │   │   └── reports
        │   ├── raw_documents
        │   │   ├── contracts
        │   │   ├── invoices
        │   │   ├── others
        │   │   ├── receipts
        │   │   └── receipt_images
        │   ├── test
        │   ├── training_data
        │   │   ├── images
        │   │   ├── invoices
        │   │   └── receipts
        │   └── uploads
        │       ├── documents
        │       ├── images
        │       └── temp
        ├── logs
        ├── models
        ├── scripts
        │   └── __pycache__
        ├── src
        │   └── __pycache__
        └── tests
            └── test_data

## Set up
1. Clone the repository:
   ```bash
        git clone https://github.com/Swarup-Ingale/LLM-Document-Parser
        cd Document_Parser_LLM
2. Install dependencies:
   ```bash
        pip install -r requirements.txt
3. Set up environment variables:
        .env file

## Features

- **Automatic Document Classification**
  - Classifies PDF documents into:
    - Invoice
    - Contract
    - Receipt

- **Intelligent Information Extraction**
  - Extracts only the necessary and relevant fields based on the classified document type
  - Reduces noise and irrelevant data

- **Multiple Export Formats**
  - Export parsed output to:
    - CSV
    - JSON
    - Excel

- **Redis Caching Support**
  - Stores parsed results in a Redis server for fast access
  - Automatic fallback to local filesystem storage if:
    - Redis is not running
    - Redis is not configured
  - Stores:
    - Raw uploaded documents
    - Parsed output files

- **Web Interface**
  - User-friendly web-based interface for uploading and parsing documents
  - View parsed results directly from the browser

- **MongoDB Integration**
  - Secure storage of:
    - User credentials (username & password)
    - Metadata of files parsed by each user
  - Maintains data integrity and user isolation

- **Rate Limiting**
  - Limits the number of documents a user can parse per day
  - Prevents abuse and ensures fair resource usage

---

## How It Works

1. User uploads a PDF document through the web interface.
2. The LLM classifies the document as an **Invoice**, **Contract**, or **Receipt**.
3. Relevant information is extracted based on the document type.
4. Parsed data is:
   - Stored in Redis (if available), OR
   - Stored locally as a fallback
5. Results can be exported in CSV, JSON, or Excel format.
6. User activity and parsed file history are stored securely in MongoDB.

---

## Supported Document Types & Examples

| Document Type | Extracted Information |
|--------------|----------------------|
| Invoice | Invoice number, date, vendor, total amount, tax, line items |
| Contract | Parties involved, effective date, clauses, duration |
| Receipt | Merchant name, date, total amount, payment method |

---

## Technology Stack

- **LLM**: For document classification and intelligent extraction
- **Backend**: Python
- **Web Framework**: (Flask / FastAPI – as implemented)
- **Database**: MongoDB
- **Caching**: Redis (optional with fallback)
- **Storage**: Local filesystem for raw & parsed files
- **Export**: CSV, JSON, Excel

---

## Export Options

Parsed results can be exported in:
- `.csv`
- `.json`
- `.xlsx`

This allows easy integration with analytics tools, spreadsheets, or downstream systems.

---

## Rate Limiting Policy

- Each user is limited to a predefined number of document parses per day
- Rate limits are enforced at the backend level
- Limits reset automatically after 24 hours

---

## Use Cases

- Automated invoice processing
- Contract analysis and management
- Expense and receipt tracking
- Enterprise document workflows
- Academic and research projects

---

## License

This project is licensed under the **MIT License**.  
You are free to use, modify, and distribute this software with proper attribution.

---

## Author

**Swarup Ingale**
