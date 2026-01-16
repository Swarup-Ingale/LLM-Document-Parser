import pandas as pd
import json
import csv
import io
from datetime import datetime
from typing import List, Dict, Any
from bson import ObjectId
import logging
from pathlib import Path

class ExportManager:
    def __init__(self, db_connection):
        self.db = db_connection
        self.logger = logging.getLogger(__name__)

    def export_to_csv(self, document_ids: List[str], user_id: str) -> io.StringIO:
        """Export documents to CSV format - FIXED VERSION"""
        try:
            # Convert string IDs to ObjectId
            object_ids = []
            for doc_id in document_ids:
                try:
                    object_ids.append(ObjectId(doc_id))
                except:
                    self.logger.warning(f"Invalid document ID: {doc_id}")
            
            if not object_ids:
                raise ValueError("No valid document IDs provided")
            
            # Fetch documents
            documents = list(self.db.parsed_documents.find({
                "_id": {"$in": object_ids},
                "user_id": user_id
            }))
            
            if not documents:
                raise ValueError("No documents found for export")
            
            self.logger.info(f"Exporting {len(documents)} documents to CSV for user {user_id}")
            
            # Prepare data for CSV
            csv_data = []
            for doc in documents:
                row = {
                    'document_id': doc.get('document_id', ''),
                    'filename': doc.get('filename', ''),
                    'document_type': doc.get('document_type', ''),
                    'file_type': doc.get('file_type', ''),
                    'file_size': doc.get('file_size', 0),
                    'created_at': doc.get('created_at', '').isoformat() if doc.get('created_at') else '',
                    'processing_time': doc.get('processing_time', ''),
                }
                
                # Add extraction data
                extraction = doc.get('extraction_data', {})
                if extraction.get('patterns'):
                    for key, value in extraction['patterns'].items():
                        if value:
                            row[f'pattern_{key}'] = ', '.join(value) if isinstance(value, list) else str(value)
                
                if extraction.get('contacts'):
                    for key, value in extraction['contacts'].items():
                        if value:
                            row[f'contact_{key}'] = ', '.join(value) if isinstance(value, list) else str(value)
                
                if extraction.get('names'):
                    names = extraction.get('names', {})
                    if names.get('primary_name'):
                        row['primary_name'] = names['primary_name']
                    if names.get('candidate_names'):
                        row['candidate_names'] = ', '.join(names['candidate_names'])
                
                csv_data.append(row)
            
            # Create CSV in memory
            output = io.StringIO()
            if csv_data:
                df = pd.DataFrame(csv_data)
                df.to_csv(output, index=False, encoding='utf-8')
            
            output.seek(0)
            return output
            
        except Exception as e:
            self.logger.error(f"CSV export error: {e}")
            raise

    def export_to_excel(self, document_ids: List[str], user_id: str) -> io.BytesIO:
        """Export documents to Excel format with multiple sheets - FIXED VERSION"""
        try:
            object_ids = []
            for doc_id in document_ids:
                try:
                    object_ids.append(ObjectId(doc_id))
                except:
                    continue
            
            if not object_ids:
                raise ValueError("No valid document IDs provided")
                
            documents = list(self.db.parsed_documents.find({
                "_id": {"$in": object_ids},
                "user_id": user_id
            }))
            
            if not documents:
                raise ValueError("No documents found for export")
            
            self.logger.info(f"Exporting {len(documents)} documents to Excel for user {user_id}")
            
            # Create Excel writer
            output = io.BytesIO()
            
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                # Main document info sheet
                main_data = []
                for doc in documents:
                    main_data.append({
                        'Document ID': doc.get('document_id', ''),
                        'Filename': doc.get('filename', ''),
                        'Document Type': doc.get('document_type', ''),
                        'File Type': doc.get('file_type', ''),
                        'File Size (bytes)': doc.get('file_size', 0),
                        'Created At': doc.get('created_at', '').isoformat() if doc.get('created_at') else '',
                        'Processing Time (s)': doc.get('processing_time', ''),
                    })
                
                if main_data:
                    pd.DataFrame(main_data).to_excel(writer, sheet_name='Document Info', index=False)
                
                # Extraction patterns sheet
                pattern_data = []
                for doc in documents:
                    extraction = doc.get('extraction_data', {})
                    patterns = extraction.get('patterns', {})
                    
                    for pattern_key, pattern_values in patterns.items():
                        if pattern_values:
                            pattern_data.append({
                                'Document ID': doc.get('document_id', ''),
                                'Filename': doc.get('filename', ''),
                                'Pattern Type': pattern_key,
                                'Values': ', '.join(pattern_values) if isinstance(pattern_values, list) else str(pattern_values)
                            })
                
                if pattern_data:
                    pd.DataFrame(pattern_data).to_excel(writer, sheet_name='Extraction Patterns', index=False)
                
                # Contact information sheet
                contact_data = []
                for doc in documents:
                    extraction = doc.get('extraction_data', {})
                    contacts = extraction.get('contacts', {})
                    
                    for contact_key, contact_values in contacts.items():
                        if contact_values:
                            contact_data.append({
                                'Document ID': doc.get('document_id', ''),
                                'Filename': doc.get('filename', ''),
                                'Contact Type': contact_key,
                                'Values': ', '.join(contact_values) if isinstance(contact_values, list) else str(contact_values)
                            })
                
                if contact_data:
                    pd.DataFrame(contact_data).to_excel(writer, sheet_name='Contact Info', index=False)
                
                # Text preview sheet
                text_data = []
                for doc in documents:
                    text_data.append({
                        'Document ID': doc.get('document_id', ''),
                        'Filename': doc.get('filename', ''),
                        'Text Preview': doc.get('text_preview', '')[:32767]  # Excel cell limit
                    })
                
                if text_data:
                    pd.DataFrame(text_data).to_excel(writer, sheet_name='Text Preview', index=False)
            
            output.seek(0)
            return output
            
        except Exception as e:
            self.logger.error(f"Excel export error: {e}")
            raise

    def export_to_json(self, document_ids: List[str], user_id: str) -> str:
        """Export documents to JSON format - FIXED VERSION"""
        try:
            object_ids = []
            for doc_id in document_ids:
                try:
                    object_ids.append(ObjectId(doc_id))
                except:
                    continue
            
            if not object_ids:
                raise ValueError("No valid document IDs provided")
                
            documents = list(self.db.parsed_documents.find({
                "_id": {"$in": object_ids},
                "user_id": user_id
            }))
            
            if not documents:
                raise ValueError("No documents found for export")
            
            self.logger.info(f"Exporting {len(documents)} documents to JSON for user {user_id}")
            
            # Convert ObjectId to string for JSON serialization
            for doc in documents:
                doc['_id'] = str(doc['_id'])
                if doc.get('created_at'):
                    doc['created_at'] = doc['created_at'].isoformat()
                if doc.get('updated_at'):
                    doc['updated_at'] = doc['updated_at'].isoformat()
            
            export_data = {
                "export_info": {
                    "export_date": datetime.now().isoformat(),
                    "total_documents": len(documents),
                    "format": "json",
                    "version": "1.0"
                },
                "documents": documents
            }
            
            return json.dumps(export_data, indent=2, ensure_ascii=False)
            
        except Exception as e:
            self.logger.error(f"JSON export error: {e}")
            raise

    def get_export_formats(self) -> List[Dict[str, str]]:
        """Get available export formats"""
        return [
            {"format": "csv", "description": "Comma-separated values", "extension": ".csv"},
            {"format": "excel", "description": "Microsoft Excel format", "extension": ".xlsx"},
            {"format": "json", "description": "JSON data format", "extension": ".json"}
        ]