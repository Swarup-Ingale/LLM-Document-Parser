import pdfplumber
import spacy
import re
import phonenumbers
from typing import List, Dict, Any, Tuple, Optional
import json
from datetime import datetime
import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
from sklearn.preprocessing import LabelEncoder
import joblib
import logging
import os
from pathlib import Path
import csv
import random

# Try to import OCR dependencies
try:
    import pytesseract
    from PIL import Image
    HAS_OCR = True
except ImportError:
    HAS_OCR = False

class DocumentParser:
    def __init__(self, model_path: str = None):
        self.nlp = spacy.load("en_core_web_sm")
        self.logger = self.setup_logger()
        
        # Initialize ML components
        self.vectorizer = TfidfVectorizer(max_features=1000, ngram_range=(1, 2))
        
        # Use compatible RandomForestClassifier parameters
        self.classifier = RandomForestClassifier(
            n_estimators=100, 
            random_state=42,
            max_depth=None,  # Added for compatibility
            min_samples_split=2,  # Added for compatibility
            min_samples_leaf=1  # Added for compatibility
        )
        self.label_encoder = LabelEncoder()
        self.is_trained = False
        
        # Training history
        self.training_history = []
        self.last_training_samples = 0
        
        # Load model if provided
        if model_path:
            self.load_model(model_path)
        
        # Enhanced patterns for different document types
        self.patterns = {
            'invoice': {
                'invoice_number': r'(?:invoice|inv)\.?\s*#?\s*([A-Z0-9-]+)',
                'date': r'(?:date|invoice date):?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
                'due_date': r'(?:due date|due):?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
                'total_amount': r'(?:total|amount due|balance):?\s*(\$\d+(?:\.\d{2})?)',
                'tax': r'(?:tax|vat):?\s*(\$\d+(?:\.\d{2})?)',
                'first_name': r'(?:first name|given name):?\s*([A-Z][a-z]+)',
                'last_name': r'(?:last name|surname|family name):?\s*([A-Z][a-z]+)',
                'email': r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
                'product_id': r'(?:product id|product code|item #):?\s*([A-Z0-9-]+)',
                'qty': r'(?:quantity|qty):?\s*(\d+)',
                'amount': r'(?:amount|price):?\s*(\$\d+(?:\.\d{2})?)',
                'invoice_date': r'(?:invoice date|date issued):?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
                'address': r'(\d+\s+[\w\s]+,?\s*[A-Za-z\s]+,?\s*[A-Z]{2}\s*\d{5})',
                'city': r'(?:city):?\s*([A-Za-z\s]+)(?=\s*[,]|\s*[A-Z]{2})',
                'stock_code': r'(?:stock code|sku):?\s*([A-Z0-9-]+)',
                'job': r'(?:job|project|work order):?\s*([A-Z0-9-]+)'
            },
            'receipt': {
                'date': r'(?:date):?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
                'total': r'(?:total|amount):?\s*(\$\d+(?:\.\d{2})?)',
                'payment_method': r'(?:payment method|paid with):?\s*([A-Za-z\s]+)'
            },
            'contract': {
                'contract_id': r'(?:contract|agreement)\s*#?\s*([A-Z0-9-]+)',
                'date': r'(?:date|effective date):?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
                'parties': r'(?:between|parties):?\s*([A-Za-z0-9\s,&]+)(?:\s+and\s+)([A-Za-z0-9\s,&]+)',
                'amount': r'(?:amount|value):?\s*(\$\d+(?:\.\d{2})?)',
                'term': r'(?:term|duration):?\s*(\d+\s+(?:years?|months?|days?))',
                'buyer': r'(?:buyer|client):?\s*([A-Za-z0-9\s,&]+)',
                'supplier': r'(?:supplier|vendor):?\s*([A-Za-z0-9\s,&]+)'
            },
            'contact': {
                'email': r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
                'phone': r'(\+?\d{1,3}[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})',
                'website': r'(https?://[^\s]+)',
                'name': r'(?:name|contact):?\s*([A-Z][a-z]+\s+[A-Z][a-z]+)',
                'company': r'(?:company|firm|organization):?\s*([A-Za-z0-9\s&.,]+)',
                'address': r'(\d+\s+[\w\s]+,?\s*[A-Za-z\s]+,?\s*[A-Z]{2}\s*\d{5})',
                'zip_code': r'\b\d{5}(?:-\d{4})?\b'
            },
            'general': {
                'currency': r'(\$\d+(?:,\d{3})*(?:\.\d{2})?)',
                'percentage': r'(\d+(?:\.\d+)?%)',
                'date': r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})'
            }
        }
    
    def setup_logger(self):
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.INFO)
        
        # Create handlers
        c_handler = logging.StreamHandler()
        f_handler = logging.FileHandler('logs/app.log')
        c_handler.setLevel(logging.INFO)
        f_handler.setLevel(logging.INFO)
        
        # Create formatters and add it to handlers
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        c_handler.setFormatter(formatter)
        f_handler.setFormatter(formatter)
        
        # Add handlers to the logger
        logger.addHandler(c_handler)
        logger.addHandler(f_handler)
        
        return logger

    def extract_text_from_image(self, image_path: str) -> str:
        """Extract text from image using OCR"""
        if not HAS_OCR:
            self.logger.warning("OCR not available. Install pytesseract and Pillow for image processing.")
            return ""
        
        try:
            # Import here to ensure they're available
            import pytesseract
            from PIL import Image
            
            text = pytesseract.image_to_string(Image.open(image_path))
            return text
        except ImportError:
            self.logger.warning("OCR dependencies not available. Please install pytesseract and Pillow.")
            return ""
        except Exception as e:
            self.logger.error(f"Error extracting text from image {image_path}: {e}")
            return ""
    
    def extract_text_from_pdf(self, file_path: str) -> str:
        """Extract text from PDF document using pdfplumber"""
        text = ""
        try:
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
        except Exception as e:
            self.logger.error(f"Error extracting text from {file_path}: {e}")
        return text

    def load_training_data_from_csv(self, csv_path: str, document_type: str = None) -> pd.DataFrame:
        """Load training data from CSV file with enhanced support for different formats"""
        try:
            df = pd.read_csv(csv_path)
            
            # If CSV already has the required format, use it directly
            if 'text' in df.columns and 'document_type' in df.columns:
                # Filter out empty texts
                df = df[df['text'].notna() & (df['text'].str.len() > 0)]
                self.logger.info(f"Loaded {len(df)} training samples from {csv_path}")
                return df
            
            # If document_type is provided, create the required structure
            if document_type:
                return self._convert_csv_to_training_format(df, csv_path, document_type)
            
            # Try to auto-detect document type and convert
            return self._auto_detect_and_convert_csv(df, csv_path)
            
        except Exception as e:
            self.logger.error(f"Error loading training data from {csv_path}: {e}")
            return pd.DataFrame()

    def _convert_csv_to_training_format(self, df: pd.DataFrame, csv_path: str, document_type: str) -> pd.DataFrame:
        """Convert different CSV formats to standard training format"""
        training_data = []
        
        if document_type == 'invoice':
            # Handle invoice format with enhanced columns
            for idx, row in df.iterrows():
                text_parts = []
                
                # Build text from available columns
                if 'first_name' in df.columns and pd.notna(row.get('first_name')):
                    text_parts.append(f"First Name: {row['first_name']}")
                if 'last_name' in df.columns and pd.notna(row.get('last_name')):
                    text_parts.append(f"Last Name: {row['last_name']}")
                if 'email' in df.columns and pd.notna(row.get('email')):
                    text_parts.append(f"Email: {row['email']}")
                if 'product_id' in df.columns and pd.notna(row.get('product_id')):
                    text_parts.append(f"Product ID: {row['product_id']}")
                if 'qty' in df.columns and pd.notna(row.get('qty')):
                    text_parts.append(f"Quantity: {row['qty']}")
                if 'amount' in df.columns and pd.notna(row.get('amount')):
                    text_parts.append(f"Amount: ${row['amount']:.2f}" if isinstance(row['amount'], (int, float)) else f"Amount: {row['amount']}")
                if 'invoice_date' in df.columns and pd.notna(row.get('invoice_date')):
                    text_parts.append(f"Invoice Date: {row['invoice_date']}")
                if 'address' in df.columns and pd.notna(row.get('address')):
                    text_parts.append(f"Address: {row['address']}")
                if 'city' in df.columns and pd.notna(row.get('city')):
                    text_parts.append(f"City: {row['city']}")
                if 'stock_code' in df.columns and pd.notna(row.get('stock_code')):
                    text_parts.append(f"Stock Code: {row['stock_code']}")
                if 'job' in df.columns and pd.notna(row.get('job')):
                    text_parts.append(f"Job: {row['job']}")
                
                # Create invoice text
                invoice_text = f"""
                INVOICE
                
                Bill To:
                {row.get('first_name', '')} {row.get('last_name', '')}
                {row.get('address', '')}
                {row.get('city', '')}
                
                Contact: {row.get('email', '')}
                
                Invoice Date: {row.get('invoice_date', '')}
                
                Product Details:
                Product ID: {row.get('product_id', '')}
                Quantity: {row.get('qty', '')}
                Amount: {row.get('amount', '')}
                
                Stock Code: {row.get('stock_code', '')}
                Job: {row.get('job', '')}
                
                Additional Information:
                {' | '.join(text_parts)}
                """
                
                training_data.append({
                    'text': invoice_text,
                    'document_type': 'invoice'
                })
        
        elif document_type == 'contract':
            # Handle contract format based on your CSV structure
            for idx, row in df.iterrows():
                text_parts = []
                
                # Build text from available contract columns
                if 'tender_title' in df.columns and pd.notna(row.get('tender_title')):
                    text_parts.append(f"Contract Title: {row['tender_title']}")
                if 'buyer_name' in df.columns and pd.notna(row.get('buyer_name')):
                    text_parts.append(f"Buyer: {row['buyer_name']}")
                if 'tender_value_amount' in df.columns and pd.notna(row.get('tender_value_amount')):
                    amount = row['tender_value_amount']
                    if isinstance(amount, (int, float)):
                        text_parts.append(f"Contract Value: ${amount:,.2f}")
                    else:
                        text_parts.append(f"Contract Value: {amount}")
                if 'tender_datePublished' in df.columns and pd.notna(row.get('tender_datePublished')):
                    text_parts.append(f"Date Published: {row['tender_datePublished']}")
                if 'tender_contractType' in df.columns and pd.notna(row.get('tender_contractType')):
                    text_parts.append(f"Contract Type: {row['tender_contractType']}")
                if 'tender_description' in df.columns and pd.notna(row.get('tender_description')):
                    text_parts.append(f"Description: {row['tender_description']}")
                if 'tender_procuringEntity_name' in df.columns and pd.notna(row.get('tender_procuringEntity_name')):
                    text_parts.append(f"Procuring Entity: {row['tender_procuringEntity_name']}")
                if 'tender_mainProcurementCategory' in df.columns and pd.notna(row.get('tender_mainProcurementCategory')):
                    text_parts.append(f"Procurement Category: {row['tender_mainProcurementCategory']}")
                if 'tender_numberOfTenderers' in df.columns and pd.notna(row.get('tender_numberOfTenderers')):
                    text_parts.append(f"Number of Tenderers: {row['tender_numberOfTenderers']}")
                
                # Create contract text
                contract_text = f"""
                CONTRACT AGREEMENT
                
                {row.get('tender_title', 'Contract Document')}
                
                Parties:
                Buyer: {row.get('buyer_name', 'N/A')}
                {f"Procuring Entity: {row.get('tender_procuringEntity_name', '')}" if 'tender_procuringEntity_name' in df.columns and pd.notna(row.get('tender_procuringEntity_name')) else ''}
                
                Contract Details:
                Contract Type: {row.get('tender_contractType', 'N/A')}
                Procurement Category: {row.get('tender_mainProcurementCategory', 'N/A')}
                Contract Value: {row.get('tender_value_amount', 'N/A')}
                Date Published: {row.get('tender_datePublished', 'N/A')}
                Number of Tenderers: {row.get('tender_numberOfTenderers', 'N/A')}
                
                Description:
                {row.get('tender_description', 'No description available')}
                
                Additional Information:
                {' | '.join(text_parts)}
                """
                
                training_data.append({
                    'text': contract_text,
                    'document_type': 'contract'
                })
        
        else:
            # Generic conversion for other document types
            for idx, row in df.iterrows():
                # Create text from all available columns
                text_parts = [f"{col}: {row[col]}" for col in df.columns if pd.notna(row[col])]
                
                document_text = f"""
                DOCUMENT
                
                {document_type.upper() if document_type else 'DOCUMENT'}
                
                Details:
                {' | '.join(text_parts)}
                """
                
                training_data.append({
                    'text': document_text,
                    'document_type': document_type or 'general'
                })
        
        result_df = pd.DataFrame(training_data)
        self.logger.info(f"Converted {len(result_df)} rows from {csv_path} to training format for {document_type}")
        return result_df

    def _auto_detect_and_convert_csv(self, df: pd.DataFrame, csv_path: str) -> pd.DataFrame:
        """Auto-detect document type and convert CSV accordingly"""
        # Analyze column names to determine document type
        columns = set(df.columns.str.lower())
        
        if any(col in columns for col in ['first_name', 'last_name', 'email', 'product_id', 'qty', 'amount']):
            document_type = 'invoice'
        elif any(col in columns for col in ['tender_title', 'buyer_name', 'tender_value_amount', 'tender_contracttype']):
            document_type = 'contract'
        elif any(col in columns for col in ['store', 'total', 'payment_method']):
            document_type = 'receipt'
        else:
            document_type = 'general'
        
        self.logger.info(f"Auto-detected document type for {csv_path}: {document_type}")
        return self._convert_csv_to_training_format(df, csv_path, document_type)

    def load_training_data_from_images(self, image_dir: str, document_type: str) -> pd.DataFrame:
        """Load training data from image directory using OCR"""
        if not HAS_OCR:
            self.logger.warning("OCR not available. Skipping image training data.")
            return pd.DataFrame()
        
        data = []
        image_dir_path = Path(image_dir)
        
        if not image_dir_path.exists():
            self.logger.warning(f"Image directory {image_dir} does not exist.")
            return pd.DataFrame()
        
        # Supported image formats
        image_extensions = ['*.jpg', '*.jpeg', '*.png', '*.bmp', '*.tiff']
        
        for extension in image_extensions:
            for image_path in image_dir_path.glob(extension):
                try:
                    text = self.extract_text_from_image(str(image_path))
                    if text.strip():
                        data.append({
                            'text': text,
                            'document_type': document_type,
                            'source_file': image_path.name
                        })
                        self.logger.info(f"✓ Processed image: {image_path.name}")
                    else:
                        self.logger.warning(f"✗ No text extracted from: {image_path.name}")
                except Exception as e:
                    self.logger.error(f"Error processing image {image_path}: {e}")
        
        return pd.DataFrame(data)

    def clean_text(self, text: str) -> str:
        """Advanced text cleaning"""
        if not text:
            return ""
            
        # Remove header/footer noise (common patterns)
        text = re.sub(r'Page\s+\d+\s+of\s+\d+', '', text)
        text = re.sub(r'Confidential|Proprietary', '', text)
        
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove common PDF artifacts
        text = re.sub(r'�', '', text)
        
        # Normalize different types of quotes
        text = text.replace('"', '"').replace('""', '"').replace('""', '"')
        text = text.replace("'", "'").replace("''", "'").replace("''", "'")
        text = text.replace('–', '-').replace('—', '-')
        
        return text.strip()

    def extract_with_patterns(self, text: str, doc_type: str = "general") -> Dict[str, List[str]]:
        """Extract information using custom patterns with enhanced invoice support"""
        results = {}
        
        if doc_type not in self.patterns:
            doc_type = "general"
            
        for field, pattern in self.patterns[doc_type].items():
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                results[field] = list(set(matches))  # Remove duplicates
                
        return results

    def extract_invoice_details(self, text: str) -> Dict[str, Any]:
        """Enhanced invoice-specific information extraction"""
        # Basic pattern extraction
        pattern_results = self.extract_with_patterns(text, "invoice")
        
        # Enhanced extraction using spaCy for names
        doc = self.nlp(text)
        
        # Extract person names for first_name/last_name
        person_entities = [ent.text for ent in doc.ents if ent.label_ == "PERSON"]
        if person_entities:
            # Try to split first and last names
            for person in person_entities:
                name_parts = person.split()
                if len(name_parts) >= 2:
                    if 'first_name' not in pattern_results:
                        pattern_results['first_name'] = [name_parts[0]]
                    if 'last_name' not in pattern_results:
                        pattern_results['last_name'] = [name_parts[-1]]
        
        # Extract location entities for city
        location_entities = [ent.text for ent in doc.ents if ent.label_ in ["GPE", "LOC"]]
        if location_entities and 'city' not in pattern_results:
            pattern_results['city'] = location_entities
        
        return pattern_results

    def extract_entities(self, text: str) -> Dict[str, List[str]]:
        """Extract named entities using spaCy"""
        doc = self.nlp(text)
        entities = {
            "PERSON": [],
            "ORG": [],
            "GPE": [],
            "DATE": [],
            "MONEY": [],
            "PRODUCT": []
        }
        
        for ent in doc.ents:
            if ent.label_ in entities:
                if ent.text not in entities[ent.label_]:
                    entities[ent.label_].append(ent.text)
        
        return entities

    def extract_contact_info(self, text: str) -> Dict[str, Any]:
        """Comprehensive contact information extraction"""
        # Extract using patterns
        contact_patterns = self.extract_with_patterns(text, "contact")
        
        # Enhanced phone number parsing with phonenumbers library
        enhanced_phones = []
        for phone in contact_patterns.get('phone', []):
            try:
                parsed_phone = phonenumbers.parse(phone, "US")
                if phonenumbers.is_valid_number(parsed_phone):
                    formatted_phone = phonenumbers.format_number(
                        parsed_phone, phonenumbers.PhoneNumberFormat.INTERNATIONAL
                    )
                    enhanced_phones.append(formatted_phone)
            except:
                enhanced_phones.append(phone)
        
        if enhanced_phones:
            contact_patterns['phone'] = enhanced_phones
        
        # Try to extract contact block using common patterns
        contact_block_patterns = [
            r'contact.*?information:?(.*?)(?=\n\n|\n[A-Z]|\Z)',
            r'details:?(.*?)(?=\n\n|\n[A-Z]|\Z)',
            r'for more.*?information:?(.*?)(?=\n\n|\n[A-Z]|\Z)'
        ]
        
        contact_blocks = []
        for pattern in contact_block_patterns:
            blocks = re.findall(pattern, text, re.IGNORECASE | re.DOTALL)
            contact_blocks.extend(blocks)
        
        # Clean contact blocks
        cleaned_blocks = []
        for block in contact_blocks:
            block = re.sub(r'\s+', ' ', block).strip()
            if len(block) > 10:  # Minimum length threshold
                cleaned_blocks.append(block)
        
        if cleaned_blocks:
            contact_patterns['contact_blocks'] = cleaned_blocks
        
        return contact_patterns

    def extract_document_holder_name(self, text: str) -> Dict[str, Any]:
        """Extract the name of the person holding the document with high precision"""
        # Look for common patterns indicating document holder
        patterns = [
            r'(?:name|holder|account holder|contact):\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)',
            r'(?:mr\.|mrs\.|ms\.|dr\.)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)',
            r'prepared by:\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)',
            r'issued to:\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)',
            r'attention:\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)',
            r'attn:\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)',
        ]
        
        names = []
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            names.extend(matches)
        
        # Also use spaCy NER for person names
        doc = self.nlp(text)
        ner_names = [ent.text for ent in doc.ents if ent.label_ == "PERSON"]
        
        # Combine and deduplicate
        all_names = list(set(names + ner_names))
        
        # Filter out unlikely names (too short, etc.)
        filtered_names = [name for name in all_names if len(name.split()) >= 2 and len(name) > 4]
        
        # Score names by position (names near the beginning might be more important)
        scored_names = []
        for name in filtered_names:
            # Simple scoring: earlier in document = higher score
            position = text.find(name)
            score = max(0, 1 - (position / len(text))) if position >= 0 else 0
            scored_names.append((name, score))
        
        # Sort by score
        scored_names.sort(key=lambda x: x[1], reverse=True)
        
        return {
            "candidate_names": [name for name, score in scored_names],
            "primary_name": scored_names[0][0] if scored_names else None
        }

    def create_training_data(self, num_samples: int = 1000) -> pd.DataFrame:
        """Create synthetic training data for ML model with enhanced invoice data"""
        data = {
            'text': [],
            'document_type': []
        }
        
        # Generate synthetic samples
        for i in range(num_samples):
            if i % 3 == 0:
                # Enhanced invoice-like text with new columns
                first_name = random.choice(['John', 'Jane', 'Robert', 'Emily', 'Michael', 'Sarah'])
                last_name = random.choice(['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Davis'])
                email = f"{first_name.lower()}.{last_name.lower()}@example.com"
                product_id = f"PROD-{1000 + i}"
                qty = random.randint(1, 10)
                amount = round(random.uniform(10.0, 1000.0), 2)
                invoice_date = f"2023-{random.randint(1,12):02d}-{random.randint(1,28):02d}"
                address = f"{random.randint(100, 999)} Main St"
                city = random.choice(['New York', 'Los Angeles', 'Chicago', 'Houston', 'Phoenix'])
                stock_code = f"STK-{random.randint(1000, 9999)}"
                job = f"JOB-{random.randint(100, 999)}"
                
                text = f"""
                INVOICE #INV-{1000+i}
                Date: {invoice_date}
                Due Date: 2023-{(random.randint(1,12)):02d}-{random.randint(1,28):02d}
                
                Bill To:
                {first_name} {last_name}
                {address}
                {city}
                
                Product ID: {product_id}
                Quantity: {qty}
                Amount: ${amount}
                
                Total: ${amount * 1.1:.2f}
                Tax: ${amount * 0.1:.2f}
                
                Contact: {email}
                Job: {job}
                Stock Code: {stock_code}
                """
                
                data['text'].append(text)
                data['document_type'].append('invoice')
                
            elif i % 3 == 1:
                # Receipt-like text
                text = f"Receipt #{2000+i} Date: {datetime.now().strftime('%m/%d/%Y')} Total: ${i*7.25:.2f} Payment: Credit Card"
                data['text'].append(text)
                data['document_type'].append('receipt')
            else:
                # Contact-like text
                text = f"Contact: John Smith Email: john.smith{i}@example.com Phone: +1-555-{1000+i}"
                data['text'].append(text)
                data['document_type'].append('contact')
        
        return pd.DataFrame(data)

    def train_model(self, df: pd.DataFrame = None):
        """Train ML model to classify document types - FIXED VERSION"""
        if df is None:
            df = self.create_training_data(1000)
        
        # Store training info
        training_info = {
            "timestamp": datetime.now().isoformat(),
            "samples": len(df)
        }
        
        # Check if we have enough data
        if len(df) < 10:
            self.logger.warning(f"Very small training dataset: {len(df)} samples")
            if len(df) == 0:
                self.logger.error("No training data available")
                return self
        
        # Prepare features and labels
        try:
            X = self.vectorizer.fit_transform(df['text']).toarray()
            y = self.label_encoder.fit_transform(df['document_type'])
            
            # Split data
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42, stratify=y
            )
            
            # Train model with error handling
            try:
                self.classifier.fit(X_train, y_train)
                
                # Evaluate model
                y_pred = self.classifier.predict(X_test)
                self.logger.info("Model Evaluation:")
                self.logger.info(classification_report(y_test, y_pred, 
                                          target_names=self.label_encoder.classes_))
                
                self.is_trained = True
                self.last_training_samples = len(df)
                self.training_history.append(training_info)
                
            except Exception as e:
                self.logger.error(f"Error training model: {e}")
                # Fallback: use a simpler approach if RandomForest fails
                from sklearn.linear_model import LogisticRegression
                self.logger.info("Falling back to LogisticRegression")
                self.classifier = LogisticRegression(random_state=42)
                self.classifier.fit(X_train, y_train)
                self.is_trained = True
                self.last_training_samples = len(df)
                self.training_history.append(training_info)
                
        except Exception as e:
            self.logger.error(f"Error in training pipeline: {e}")
        
        return self

    def predict_document_type(self, text: str) -> str:
        """Predict document type using trained ML model"""
        if not self.is_trained:
            raise ValueError("Model must be trained before prediction")
        
        # Transform text to features
        features = self.vectorizer.transform([text]).toarray()
        
        # Predict
        prediction = self.classifier.predict(features)
        
        # Return decoded label
        return self.label_encoder.inverse_transform(prediction)[0]

    def save_model(self, path: str):
        """Save trained model to disk"""
        if not self.is_trained:
            raise ValueError("Model must be trained before saving")
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(path), exist_ok=True)
        
        model_data = {
            'vectorizer': self.vectorizer,
            'classifier': self.classifier,
            'label_encoder': self.label_encoder,
            'is_trained': self.is_trained,
            'training_history': self.training_history,
            'last_training_samples': self.last_training_samples
        }
        
        joblib.dump(model_data, path)
        
        self.logger.info(f"Model saved to {path}")

    def load_model(self, path: str):
        """Load trained model from disk"""
        if not os.path.exists(path):
            self.logger.warning(f"Model file {path} does not exist")
            return
        
        try:
            model_data = joblib.load(path)
            
            self.vectorizer = model_data['vectorizer']
            self.classifier = model_data['classifier']
            self.label_encoder = model_data['label_encoder']
            self.is_trained = model_data['is_trained']
            self.training_history = model_data.get('training_history', [])
            self.last_training_samples = model_data.get('last_training_samples', 0)
            
            self.logger.info(f"Model loaded from {path}")
        except Exception as e:
            self.logger.error(f"Error loading model from {path}: {e}")
            # Initialize new components if loading fails
            self.vectorizer = TfidfVectorizer(max_features=1000, ngram_range=(1, 2))
            self.classifier = RandomForestClassifier(n_estimators=100, random_state=42)
            self.label_encoder = LabelEncoder()
            self.is_trained = False

    def extract_features(self, text: str) -> Dict[str, Any]:
        """Extract features from text for ML analysis"""
        # Count various elements
        email_count = len(re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text))
        phone_count = len(re.findall(r'(\+?\d{1,3}[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})', text))
        currency_count = len(re.findall(r'(\$\d+(?:,\d{3})*(?:\.\d{2})?)', text))
        date_count = len(re.findall(r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', text))
        
        # Use spaCy for more advanced features
        doc = self.nlp(text)
        person_count = len([ent for ent in doc.ents if ent.label_ == "PERSON"])
        org_count = len([ent for ent in doc.ents if ent.label_ == "ORG"])
        
        return {
            'email_count': email_count,
            'phone_count': phone_count,
            'currency_count': currency_count,
            'date_count': date_count,
            'person_count': person_count,
            'org_count': org_count,
            'text_length': len(text)
        }

    def parse_document(self, file_path: str, doc_type: str = "general", use_ml: bool = False) -> Dict:
        """Main method to parse document and extract information with enhanced invoice support"""
        try:
            # Extract text based on file type
            if file_path.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp', '.tiff')):
                raw_text = self.extract_text_from_image(file_path)
            else:
                raw_text = self.extract_text_from_pdf(file_path)
            
            if not raw_text:
                return {
                    "success": False,
                    "error": "No text could be extracted from the document"
                }
            
            # Clean text
            cleaned_text = self.clean_text(raw_text)
            
            # Use ML to determine document type if requested
            if use_ml and self.is_trained:
                try:
                    doc_type = self.predict_document_type(cleaned_text)
                except Exception as e:
                    self.logger.warning(f"ML prediction failed: {e}")
            
            # Extract information using patterns - enhanced for invoices
            if doc_type == "invoice":
                pattern_results = self.extract_invoice_details(cleaned_text)
            else:
                pattern_results = self.extract_with_patterns(cleaned_text, doc_type)
            
            # Extract contact information
            contact_info = self.extract_contact_info(cleaned_text)
            
            # Extract document holder name
            name_info = self.extract_document_holder_name(cleaned_text)
            
            # Extract entities
            entities = self.extract_entities(cleaned_text)
            
            # Extract ML features
            ml_features = self.extract_features(cleaned_text)
            
            return {
                "success": True,
                "document_type": doc_type,
                "pattern_extraction": pattern_results,
                "contact_info": contact_info,
                "name_info": name_info,
                "entities": entities,
                "ml_features": ml_features,
                "cleaned_text": cleaned_text[:1000] + "..." if len(cleaned_text) > 1000 else cleaned_text,
                "extraction_time": datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error parsing document {file_path}: {e}")
            return {
                "success": False,
                "error": str(e),
                "extraction_time": datetime.now().isoformat()
            }

    def evaluate_model(self, test_documents: List[Dict]) -> Dict[str, Any]:
        """Evaluate model accuracy with real documents"""
        if not self.is_trained:
            return {"error": "Model not trained"}
    
        correct_predictions = 0
        total_documents = len(test_documents)
        confusion_data = {}
    
        for doc in test_documents:
            true_label = doc.get('true_document_type')
            file_path = doc.get('file_path')
        
            if not true_label or not file_path:
                continue
            
            try:
                # Parse document and get ML prediction
                result = self.parse_document(file_path, use_ml=True)
                predicted_label = result.get('document_type')
            
                # Track accuracy
                if predicted_label == true_label:
                    correct_predictions += 1
            
                # Build confusion matrix data
                key = f"{true_label}_{predicted_label}"
                confusion_data[key] = confusion_data.get(key, 0) + 1
            
            except Exception as e:
                self.logger.error(f"Error evaluating {file_path}: {e}")
    
        accuracy = (correct_predictions / total_documents) * 100 if total_documents > 0 else 0
    
        return {
            "accuracy": round(accuracy, 2),
            "correct_predictions": correct_predictions,
            "total_documents": total_documents,
            "confusion_data": confusion_data,
            "vectorizer_features": len(self.vectorizer.get_feature_names_out()),
            "model_classes": self.label_encoder.classes_.tolist(),
            "training_samples": self.last_training_samples
        }

    def get_training_info(self):
        """Get information about model training"""
        return {
            "training_samples": self.last_training_samples,
            "training_history": self.training_history,
            "is_trained": self.is_trained,
            "classes": self.label_encoder.classes_.tolist() if self.is_trained else []
        }