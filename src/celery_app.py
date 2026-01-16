import os
from celery import Celery
from celery.signals import after_setup_logger
import logging
from datetime import datetime
from typing import Dict, Any, List
import tempfile
from pathlib import Path

# Configure Celery
celery_app = Celery('document_parser')

# Celery configuration
celery_app.conf.update(
    broker_url=os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
    result_backend=os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/1'),
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_send_sent_event=True,
    worker_send_task_events=True,
    task_ignore_result=False,
    task_store_errors_even_if_ignored=True,
    
    # Task routes
    task_routes={
        'src.celery_app.process_document_async': {'queue': 'parsing'},
        'src.celery_app.batch_process_documents_async': {'queue': 'batch'},
        'src.celery_app.generate_previews_async': {'queue': 'previews'},
        'src.celery_app.export_documents_async': {'queue': 'exports'},
    },
    
    # Rate limiting
    task_annotations={
        'src.celery_app.process_document_async': {'rate_limit': '10/m'},
        'src.celery_app.batch_process_documents_async': {'rate_limit': '2/m'},
    }
)

@after_setup_logger.connect
def setup_celery_logging(logger, *args, **kwargs):
    """Configure logging for Celery"""
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler = logging.FileHandler('logs/celery.log')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

class TaskProgress:
    """Helper class for tracking task progress"""
    def __init__(self, task, total_steps: int = 100):
        self.task = task
        self.total_steps = total_steps
        self.current_step = 0
    
    def update_progress(self, step: int, message: str = None):
        """Update task progress"""
        self.current_step = step
        progress = (step / self.total_steps) * 100
        
        self.task.update_state(
            state='PROGRESS',
            meta={
                'current': step,
                'total': self.total_steps,
                'progress': progress,
                'message': message,
                'timestamp': datetime.now().isoformat()
            }
        )

@celery_app.task(bind=True, name='process_document_async')
def process_document_async(self, file_path: str, user_id: str, document_id: str, 
                          use_ml: bool = True, generate_preview: bool = True) -> Dict[str, Any]:
    """Background task to process a single document"""
    try:
        progress = TaskProgress(self, total_steps=4)
        
        # Import here to avoid circular imports
        from src.document_parser import DocumentParser
        from src.document_preview import DocumentPreviewGenerator
        
        progress.update_progress(1, "Initializing document parser...")
        
        # Initialize parser
        parser = DocumentParser()
        
        progress.update_progress(2, "Parsing document content...")
        
        # Parse document
        result = parser.parse_document(file_path, use_ml=use_ml)
        
        progress.update_progress(3, "Generating document preview...")
        
        # Generate preview if requested
        preview_data = {}
        if generate_preview and result["success"]:
            preview_generator = DocumentPreviewGenerator()
            
            if file_path.lower().endswith('.pdf'):
                preview_path, thumbnail_path = preview_generator.generate_pdf_preview(
                    file_path, document_id
                )
            else:
                preview_path, thumbnail_path = preview_generator.generate_image_preview(
                    file_path, document_id
                )
            
            preview_data = {
                "preview_generated": bool(preview_path),
                "preview_path": preview_path,
                "thumbnail_path": thumbnail_path
            }
        
        progress.update_progress(4, "Finalizing processing...")
        
        # Clean up temporary file
        if os.path.exists(file_path) and tempfile.gettempdir() in file_path:
            os.unlink(file_path)
        
        return {
            "success": True,
            "document_id": document_id,
            "processing_result": result,
            "preview_data": preview_data,
            "task_id": self.request.id,
            "completed_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        logging.error(f"Background processing failed for {file_path}: {e}")
        
        # Clean up temporary file on error
        if os.path.exists(file_path) and tempfile.gettempdir() in file_path:
            try:
                os.unlink(file_path)
            except:
                pass
        
        return {
            "success": False,
            "document_id": document_id,
            "error": str(e),
            "task_id": self.request.id,
            "completed_at": datetime.now().isoformat()
        }

@celery_app.task(bind=True, name='batch_process_documents_async')
def batch_process_documents_async(self, file_paths: List[str], user_id: str, 
                                use_ml: bool = True) -> Dict[str, Any]:
    """Background task to process multiple documents in batch"""
    try:
        total_files = len(file_paths)
        progress = TaskProgress(self, total_steps=total_files + 2)
        
        from src.document_parser import DocumentParser
        from src.document_preview import DocumentPreviewGenerator
        
        progress.update_progress(0, "Initializing batch processing...")
        
        parser = DocumentParser()
        preview_generator = DocumentPreviewGenerator()
        
        results = []
        successful = 0
        failed = 0
        
        for i, file_path in enumerate(file_paths):
            document_id = f"batch_{self.request.id}_{i}"
            
            progress.update_progress(
                i + 1, 
                f"Processing {i+1}/{total_files}: {Path(file_path).name}"
            )
            
            try:
                # Parse document
                result = parser.parse_document(file_path, use_ml=use_ml)
                
                # Generate preview
                if file_path.lower().endswith('.pdf'):
                    preview_path, thumbnail_path = preview_generator.generate_pdf_preview(
                        file_path, document_id
                    )
                else:
                    preview_path, thumbnail_path = preview_generator.generate_image_preview(
                        file_path, document_id
                    )
                
                results.append({
                    "filename": Path(file_path).name,
                    "document_id": document_id,
                    "success": True,
                    "result": result,
                    "preview_generated": bool(preview_path)
                })
                successful += 1
                
            except Exception as e:
                logging.error(f"Error processing {file_path}: {e}")
                results.append({
                    "filename": Path(file_path).name,
                    "document_id": document_id,
                    "success": False,
                    "error": str(e)
                })
                failed += 1
            
            finally:
                # Clean up temporary file
                if os.path.exists(file_path) and tempfile.gettempdir() in file_path:
                    try:
                        os.unlink(file_path)
                    except:
                        pass
        
        progress.update_progress(total_files + 1, "Batch processing completed")
        
        return {
            "success": True,
            "total_processed": total_files,
            "successful": successful,
            "failed": failed,
            "results": results,
            "task_id": self.request.id,
            "completed_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        logging.error(f"Batch processing task failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "task_id": self.request.id,
            "completed_at": datetime.now().isoformat()
        }

@celery_app.task(bind=True, name='generate_previews_async')
def generate_previews_async(self, document_ids: List[str]) -> Dict[str, Any]:
    """Background task to generate previews for existing documents"""
    try:
        progress = TaskProgress(self, total_steps=len(document_ids))
        
        from src.document_preview import DocumentPreviewGenerator
        from pymongo import MongoClient
        
        client = MongoClient('mongodb://localhost:27017/')
        db = client['document_parser_db']
        
        preview_generator = DocumentPreviewGenerator()
        results = []
        
        for i, doc_id in enumerate(document_ids):
            progress.update_progress(i + 1, f"Generating preview for document {i+1}")
            
            # Get document from database
            document = db.parsed_documents.find_one({"document_id": doc_id})
            if not document:
                results.append({
                    "document_id": doc_id,
                    "success": False,
                    "error": "Document not found"
                })
                continue
            
            # Get original file path (this would need to be stored during upload)
            # For now, we'll skip actual preview generation in this example
            results.append({
                "document_id": doc_id,
                "success": True,
                "preview_generated": False,  # Would be True in real implementation
                "message": "Preview generation queued"
            })
        
        client.close()
        
        return {
            "success": True,
            "results": results,
            "task_id": self.request.id,
            "completed_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        logging.error(f"Preview generation task failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "task_id": self.request.id
        }

@celery_app.task(bind=True, name='export_documents_async')
def export_documents_async(self, document_ids: List[str], user_id: str, 
                          export_format: str = 'csv') -> Dict[str, Any]:
    """Background task to export documents in various formats"""
    try:
        progress = TaskProgress(self, total_steps=3)
        
        from src.export_manager import ExportManager
        from pymongo import MongoClient
        
        progress.update_progress(1, "Preparing export data...")
        
        client = MongoClient('mongodb://localhost:27017/')
        db = client['document_parser_db']
        export_manager = ExportManager(db)
        
        progress.update_progress(2, f"Generating {export_format.upper()} export...")
        
        # Generate export based on format
        if export_format == 'csv':
            export_data = export_manager.export_to_csv(document_ids, user_id)
            file_extension = '.csv'
            mime_type = 'text/csv'
        elif export_format == 'excel':
            export_data = export_manager.export_to_excel(document_ids, user_id)
            file_extension = '.xlsx'
            mime_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        elif export_format == 'json':
            export_data = export_manager.export_to_json(document_ids, user_id)
            file_extension = '.json'
            mime_type = 'application/json'
        else:
            raise ValueError(f"Unsupported export format: {export_format}")
        
        progress.update_progress(3, "Export completed successfully")
        
        # Save export result to file (in real implementation)
        export_filename = f"export_{self.request.id}{file_extension}"
        export_path = f"data/exports/{export_filename}"
        
        # Ensure directory exists
        os.makedirs("data/exports", exist_ok=True)
        
        if hasattr(export_data, 'getvalue'):
            # It's a BytesIO or StringIO object
            with open(export_path, 'wb' if export_format != 'csv' else 'w') as f:
                if export_format == 'csv':
                    f.write(export_data.getvalue())
                else:
                    f.write(export_data.getvalue())
        else:
            # It's a string (JSON)
            with open(export_path, 'w') as f:
                f.write(export_data)
        
        client.close()
        
        return {
            "success": True,
            "export_format": export_format,
            "export_filename": export_filename,
            "export_path": export_path,
            "document_count": len(document_ids),
            "download_url": f"/api/exports/download/{export_filename}",
            "task_id": self.request.id,
            "completed_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        logging.error(f"Export task failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "task_id": self.request.id
        }

def get_task_status(task_id: str) -> Dict[str, Any]:
    """Get the status of a Celery task"""
    try:
        task = celery_app.AsyncResult(task_id)
        
        response = {
            "task_id": task_id,
            "status": task.status,
            "ready": task.ready()
        }
        
        if task.status == 'PROGRESS':
            response.update(task.result or {})
        elif task.status == 'SUCCESS':
            response["result"] = task.result
        elif task.status == 'FAILURE':
            response["error"] = str(task.result)
        
        return response
        
    except Exception as e:
        logging.error(f"Error getting task status {task_id}: {e}")
        return {
            "task_id": task_id,
            "status": 'UNKNOWN',
            "error": str(e)
        }