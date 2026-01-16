import os
import re
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from bson import ObjectId
from pymongo import MongoClient, TEXT, DESCENDING
import logging

class DocumentSearchEngine:
    def __init__(self, db_connection):
        self.db = db_connection
        self.logger = self._setup_logger()
        self.setup_search_indexes()

    def _setup_logger(self):
        """Setup logger for search engine"""
        logger = logging.getLogger(__name__)
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger

    def setup_search_indexes(self):
        """Create search indexes for optimal performance - FIXED VERSION"""
        try:
            # First, check and drop conflicting indexes
            existing_indexes = list(self.db.parsed_documents.list_indexes())
            
            for index in existing_indexes:
                index_name = index.get('name', '')
                index_key = index.get('key', {})
                
                # Check for conflicting compound indexes
                if (index_key.get('user_id') == 1 and index_key.get('created_at') == -1 and 
                    index_name != "user_recency_index"):
                    self.logger.info(f"Dropping conflicting index: {index_name}")
                    self.db.parsed_documents.drop_index(index_name)
                
                # Check for other text indexes that might conflict
                elif ('text' in index_name and index_name != "text_search_index" and 
                      any(field in index_key for field in ['filename', 'full_text', 'document_type'])):
                    self.logger.info(f"Dropping old text index: {index_name}")
                    self.db.parsed_documents.drop_index(index_name)

            # Create text search index with explicit name
            try:
                self.db.parsed_documents.create_index([
                    ("filename", TEXT),
                    ("full_text", TEXT),
                    ("document_type", TEXT)
                ], name="text_search_index", default_language="english")
                self.logger.info("Text search index created successfully")
            except Exception as e:
                if "index with different options already exists" not in str(e):
                    self.logger.warning(f"Text index creation: {e}")

            # Compound indexes for common queries with explicit names
            indexes_to_create = [
                {
                    "keys": [("user_id", 1), ("created_at", -1)],
                    "name": "user_recency_index"
                },
                {
                    "keys": [("user_id", 1), ("document_type", 1), ("created_at", -1)],
                    "name": "user_type_recency_index"
                }
            ]
            
            for index_config in indexes_to_create:
                try:
                    self.db.parsed_documents.create_index(
                        index_config["keys"],
                        name=index_config["name"]
                    )
                    self.logger.info(f"Index {index_config['name']} created successfully")
                except Exception as e:
                    if "already exists" not in str(e):
                        self.logger.warning(f"Index {index_config['name']} creation: {e}")
            
            self.logger.info("Search indexes setup completed")
            
        except Exception as e:
            self.logger.error(f"Error setting up search indexes: {e}")

    def search_documents(self, user_id: str, query: Dict[str, Any]) -> Dict[str, Any]:
        """
        Advanced document search with multiple filters - FIXED VERSION
        """
        try:
            # Build filter pipeline
            pipeline = self._build_search_pipeline(user_id, query)
            
            # Execute search
            results = list(self.db.parsed_documents.aggregate(pipeline))
            
            # Get total count for pagination
            count_pipeline = self._build_count_pipeline(user_id, query)
            total_count = list(self.db.parsed_documents.aggregate(count_pipeline))
            total = total_count[0]['total'] if total_count else 0
            
            # Format results
            formatted_results = self._format_search_results(results)
            
            return {
                "success": True,
                "results": formatted_results,
                "total_count": total,
                "filters_applied": query
            }
            
        except Exception as e:
            self.logger.error(f"Search error: {e}")
            return {
                "success": False,
                "error": str(e),
                "results": [],
                "total_count": 0
            }

    def _build_search_pipeline(self, user_id: str, query: Dict[str, Any]) -> List[Dict]:
        """Build MongoDB aggregation pipeline for search - FIXED VERSION"""
        pipeline = []
        match_stage = {"user_id": user_id}
        
        # Text search
        search_text = query.get('search_text')
        if search_text and search_text.strip():
            match_stage["$text"] = {"$search": search_text}

        # Document type filter
        document_types = query.get('document_types')
        if document_types and document_types != ['all']:
            match_stage["document_type"] = {"$in": document_types}

        # Date range filter
        date_filters = {}
        if query.get('date_from'):
            try:
                date_from = query['date_from'].replace('Z', '+00:00')
                date_filters["$gte"] = datetime.fromisoformat(date_from)
            except Exception as e:
                self.logger.warning(f"Invalid date_from: {query['date_from']} - {e}")
        
        if query.get('date_to'):
            try:
                date_to = query['date_to'].replace('Z', '+00:00')
                date_filters["$lte"] = datetime.fromisoformat(date_to)
            except Exception as e:
                self.logger.warning(f"Invalid date_to: {query['date_to']} - {e}")
        
        if date_filters:
            match_stage["created_at"] = date_filters

        # File type filter
        file_types = query.get('file_types')
        if file_types:
            match_stage["file_type"] = {"$in": file_types}

        # Add match stage to pipeline
        if match_stage:
            pipeline.append({"$match": match_stage})

        # Pagination
        page = max(1, query.get('page', 1))
        per_page = min(100, max(1, query.get('per_page', 20)))
        skip = (page - 1) * per_page

        # Add sorting and pagination
        sort_stage = {"$sort": {"created_at": DESCENDING}}
        
        # If text search, sort by score first, then date
        if search_text and search_text.strip():
            sort_stage["$sort"] = {"search_score": {"$meta": "textScore"}, "created_at": DESCENDING}
        
        pipeline.extend([
            sort_stage,
            {"$skip": skip},
            {"$limit": per_page}
        ])

        # Projection stage
        project_stage = {
            "$project": {
                "_id": 1,
                "document_id": 1,
                "filename": 1,
                "document_type": 1,
                "file_type": 1,
                "file_size": 1,
                "created_at": 1,
                "processing_time": 1,
                "text_preview": 1,
                "extraction_data": 1,
                "preview_data": 1
            }
        }
        
        # Add search score if text search was performed
        if search_text and search_text.strip():
            project_stage["$project"]["search_score"] = {"$meta": "textScore"}
        
        pipeline.append(project_stage)

        return pipeline

    def _build_count_pipeline(self, user_id: str, query: Dict[str, Any]) -> List[Dict]:
        """Build pipeline to get total count"""
        pipeline = []
        match_stage = {"user_id": user_id}
        
        # Text search
        search_text = query.get('search_text')
        if search_text and search_text.strip():
            match_stage["$text"] = {"$search": search_text}

        # Document type filter
        document_types = query.get('document_types')
        if document_types and document_types != ['all']:
            match_stage["document_type"] = {"$in": document_types}

        # Date range filter
        date_filters = {}
        if query.get('date_from'):
            try:
                date_from = query['date_from'].replace('Z', '+00:00')
                date_filters["$gte"] = datetime.fromisoformat(date_from)
            except:
                pass
        
        if query.get('date_to'):
            try:
                date_to = query['date_to'].replace('Z', '+00:00')
                date_filters["$lte"] = datetime.fromisoformat(date_to)
            except:
                pass
        
        if date_filters:
            match_stage["created_at"] = date_filters

        # File type filter
        file_types = query.get('file_types')
        if file_types:
            match_stage["file_type"] = {"$in": file_types}

        # Add match stage and count
        pipeline.append({"$match": match_stage})
        pipeline.append({"$count": "total"})
        
        return pipeline

    def _format_search_results(self, results: List[Dict]) -> List[Dict]:
        """Format search results for API response"""
        formatted = []
        for doc in results:
            formatted_doc = {
                "id": str(doc["_id"]),
                "document_id": doc.get("document_id", ""),
                "filename": doc.get("filename", ""),
                "document_type": doc.get("document_type", "unknown"),
                "file_type": doc.get("file_type", ""),
                "file_size": doc.get("file_size", 0),
                "created_at": doc.get("created_at").isoformat() if doc.get("created_at") else None,
                "processing_time": doc.get("processing_time", ""),
                "text_preview": self._truncate_text(doc.get("text_preview", ""), 200),
                "extraction_summary": self._create_extraction_summary(doc.get("extraction_data", {})),
                "has_preview": bool(doc.get("preview_data", {}).get("preview_generated", False))
            }
            
            if doc.get('search_score'):
                formatted_doc['relevance_score'] = round(doc['search_score'], 3)
                
            formatted.append(formatted_doc)
        
        return formatted

    def _truncate_text(self, text: str, max_length: int) -> str:
        """Truncate text with ellipsis"""
        if not text:
            return ""
        if len(text) <= max_length:
            return text
        return text[:max_length] + "..."

    def _create_extraction_summary(self, extraction_data: Dict) -> Dict:
        """Create a summary of extracted data for search results"""
        summary = {}
        
        if extraction_data.get('patterns'):
            patterns = extraction_data['patterns']
            summary['key_patterns'] = list(patterns.keys())[:3]
            summary['pattern_count'] = len(patterns)
        
        if extraction_data.get('contacts'):
            contacts = extraction_data['contacts']
            summary['contact_count'] = len(contacts)
            # Count actual contact values
            total_contacts = sum(len(v) if isinstance(v, list) else 1 for v in contacts.values() if v)
            summary['total_contacts'] = total_contacts
            
        if extraction_data.get('entities'):
            entities = extraction_data['entities']
            entity_counts = {k: len(v) for k, v in entities.items() if v}
            summary['entities'] = entity_counts
            
        return summary

    def get_search_facets(self, user_id: str) -> Dict[str, Any]:
        """Get available search facets and counts"""
        try:
            pipeline = [
                {"$match": {"user_id": user_id}},
                {"$facet": {
                    "document_types": [
                        {"$group": {"_id": "$document_type", "count": {"$sum": 1}}}
                    ],
                    "file_types": [
                        {"$group": {"_id": "$file_type", "count": {"$sum": 1}}}
                    ],
                    "date_range": [
                        {"$group": {
                            "_id": None,
                            "min_date": {"$min": "$created_at"},
                            "max_date": {"$max": "$created_at"}
                        }}
                    ],
                    "total_count": [
                        {"$count": "count"}
                    ]
                }}
            ]
            
            result = list(self.db.parsed_documents.aggregate(pipeline))
            if not result:
                return {
                    "document_types": {},
                    "file_types": {},
                    "date_range": {"min_date": None, "max_date": None},
                    "total_documents": 0
                }
                
            result = result[0]
            
            return {
                "document_types": {item["_id"]: item["count"] for item in result["document_types"] if item["_id"]},
                "file_types": {item["_id"]: item["count"] for item in result["file_types"] if item["_id"]},
                "date_range": {
                    "min_date": result["date_range"][0]["min_date"].isoformat() if result["date_range"] and result["date_range"][0]["min_date"] else None,
                    "max_date": result["date_range"][0]["max_date"].isoformat() if result["date_range"] and result["date_range"][0]["max_date"] else None
                },
                "total_documents": result["total_count"][0]["count"] if result["total_count"] else 0
            }
            
        except Exception as e:
            self.logger.error(f"Error getting search facets: {e}")
            return {
                "document_types": {},
                "file_types": {},
                "date_range": {"min_date": None, "max_date": None},
                "total_documents": 0
            }

    def quick_search(self, user_id: str, search_text: str, limit: int = 10) -> Dict[str, Any]:
        """Quick search for autocomplete and quick results"""
        try:
            pipeline = [
                {
                    "$match": {
                        "$text": {"$search": search_text},
                        "user_id": user_id
                    }
                },
                {"$sort": {"search_score": {"$meta": "textScore"}}},
                {"$limit": limit},
                {"$project": {
                    "_id": 1,
                    "filename": 1,
                    "document_type": 1,
                    "text_preview": 1,
                    "search_score": {"$meta": "textScore"}
                }}
            ]
            
            results = list(self.db.parsed_documents.aggregate(pipeline))
            formatted_results = [
                {
                    "id": str(doc["_id"]),
                    "filename": doc.get("filename"),
                    "document_type": doc.get("document_type"),
                    "text_snippet": self._truncate_text(doc.get("text_preview", ""), 100),
                    "score": round(doc.get("search_score", 0), 3)
                }
                for doc in results
            ]
            
            return {
                "success": True,
                "results": formatted_results,
                "query": search_text
            }
            
        except Exception as e:
            self.logger.error(f"Quick search error: {e}")
            return {
                "success": False,
                "error": str(e),
                "results": []
            }