from typing import Dict, Any, List, Optional, Tuple
from src.database.insert import qdrant_client
from src.database.insert_analysis import analysis_storage
from src.workflow.state import ProcessingState
import uuid
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class StorageService:
    """
    Centralized storage service for agricultural demo analysis results
    
    Handles both chunk storage (for search) and analysis storage (for reporting)
    with user-controlled approval workflow.
    """
    
    def __init__(self):
        self.chunk_storage = qdrant_client
        self.analysis_storage = analysis_storage
        logger.info("📦 StorageService initialized")
    
    def prepare_storage_data(self, state: ProcessingState) -> Dict[str, Any]:
        """
        Prepare all data needed for storage without actually storing
        
        Returns:
            Dict containing prepared chunk metadata and analysis data
        """
        try:
            if not state.get("chunks"):
                raise ValueError("No chunks available for storage")
            
            if not state.get("analysis_result"):
                raise ValueError("No analysis result available for storage")
            
            # Generate unique IDs and timestamps
            form_id = str(uuid.uuid4())
            insertion_date = datetime.now().isoformat()
            
            # Prepare chunk metadata
            analysis_data = state.get("analysis_result", {})
            basic_info = analysis_data.get("basic_info", {})
            efficacy_analysis = analysis_data.get("efficacy_analysis", {})
            averages = efficacy_analysis.get("averages", {})
            
            # Extract user_id from state for multi-user isolation
            user_id = state.get("_user_id")
            
            chunk_metadata = {
                "form_id": form_id,
                "form_title": state["file_name"],
                "form_type": state.get("form_type", "unknown"),
                "date_of_insertion": insertion_date,
                "analysis_status": analysis_data.get("status", "unknown"),
                "cooperator": basic_info.get("cooperator", ""),
                "product": basic_info.get("product", ""),
                "location": basic_info.get("location", ""),
                "improvement_percent": averages.get("improvement_percent", 0)
            }
            
            # Add user_id to metadata for multi-user isolation
            if user_id:
                chunk_metadata["user_id"] = user_id
            
            # Prepare chunks with metadata
            prepared_chunks = []
            for chunk in state["chunks"]:
                chunk_copy = chunk.copy()
                chunk_copy["metadata"] = chunk_metadata.copy()
                prepared_chunks.append(chunk_copy)
            
            # Prepare analysis response structure
            analysis_response = {
                "status": "success",
                "total_reports": 1,
                "reports": [{
                    "report_number": 1,
                    "file_name": state["file_name"],
                    "form_id": form_id,
                    "form_type": state.get("form_type", ""),
                    "extracted_content": state.get("extracted_markdown", ""),
                    "analysis": state.get("analysis_result", {}),
                    "graph_suggestions": state.get("graph_suggestions", {}),
                    "processing_metrics": {
                        "chunk_count": len(state.get("chunks", [])),
                        "processing_steps": state.get("current_step", ""),
                        "insertion_date": insertion_date
                    },
                    "errors": state.get("errors", []),
                    "validation": {
                        "file_validation": state.get("file_validation"),
                        "content_validation": state.get("content_validation")
                    }
                }],
                "cross_report_analysis": {"cross_report_suggestions": []}
            }
            
            # Add user_id to analysis response for multi-user isolation
            if user_id:
                analysis_response["user_id"] = user_id
                analysis_response["reports"][0]["user_id"] = user_id
            
            storage_data = {
                "form_id": form_id,
                "insertion_date": insertion_date,
                "chunks": prepared_chunks,
                "analysis_response": analysis_response,
                "metadata": chunk_metadata,
                "file_name": state["file_name"],
                "form_type": state.get("form_type", "unknown")
            }
            
            logger.info(f"Storage data prepared for {state['file_name']}")
            logger.info(f"Chunks: {len(prepared_chunks)}, Form ID: {form_id}")
            
            return storage_data
            
        except Exception as e:
            logger.error(f"Failed to prepare storage data: {str(e)}")
            raise
    
    def store_chunks(self, chunks: List[Dict[str, Any]]) -> Tuple[bool, str]:
        """
        Store chunks in vector database for search functionality
        
        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            if not chunks:
                return False, "No chunks provided for storage"
            
            # Insert chunks into Qdrant
            insert_success = self.chunk_storage.insert_chunks(chunks)
            
            if insert_success:
                message = f"Successfully stored {len(chunks)} chunks in vector database"
                logger.info(message)
                return True, message
            else:
                message = "Failed to store chunks in vector database"
                logger.error(message)
                return False, message
                
        except Exception as e:
            message = f"Chunk storage failed: {str(e)}"
            logger.error(message)
            return False, message
    
    def store_analysis(self, analysis_response: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Store analysis results in structured database for reporting
        
        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            if not analysis_response:
                return False, "No analysis data provided for storage"
            
            # Insert analysis into structured storage
            storage_success = self.analysis_storage.insert_multi_report_response(analysis_response)
            
            if storage_success:
                message = "Successfully stored analysis results in structured database"
                logger.info(message)
                return True, message
            else:
                message = "Failed to store analysis results in structured database"
                logger.error(message)
                return False, message
                
        except Exception as e:
            message = f"Analysis storage failed: {str(e)}"
            logger.error(message)
            return False, message
    
    def store_all(self, storage_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Store both chunks and analysis data
        
        Args:
            storage_data: Prepared storage data from prepare_storage_data()
            
        Returns:
            Dict with storage results and status
        """
        try:
            chunks = storage_data.get("chunks", [])
            analysis_response = storage_data.get("analysis_response", {})
            form_id = storage_data.get("form_id", "unknown")
            
            # Store chunks
            chunk_success, chunk_message = self.store_chunks(chunks)
            
            # Store analysis
            analysis_success, analysis_message = self.store_analysis(analysis_response)
            
            # Determine overall success
            overall_success = chunk_success and analysis_success
            
            result = {
                "success": overall_success,
                "form_id": form_id,
                "storage_results": {
                    "chunks": {
                        "success": chunk_success,
                        "message": chunk_message,
                        "count": len(chunks)
                    },
                    "analysis": {
                        "success": analysis_success,
                        "message": analysis_message
                    }
                },
                "timestamp": datetime.now().isoformat()
            }
            
            if overall_success:
                logger.info(f"Complete storage successful for form {form_id}")
            else:
                logger.warning(f"Partial storage failure for form {form_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"Complete storage failed: {str(e)}")
            return {
                "success": False,
                "form_id": storage_data.get("form_id", "unknown"),
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    def get_storage_preview(self, state: ProcessingState) -> Dict[str, Any]:
        """
        Get a preview of what would be stored without actually storing
        
        Useful for user review before storage approval
        """
        try:
            storage_data = self.prepare_storage_data(state)
            
            # Create preview without storing
            preview = {
                "form_id": storage_data["form_id"],
                "file_name": storage_data["file_name"],
                "form_type": storage_data["form_type"],
                "chunk_count": len(storage_data["chunks"]),
                "analysis_summary": {
                    "product": storage_data["metadata"].get("product", ""),
                    "location": storage_data["metadata"].get("location", ""),
                    "cooperator": storage_data["metadata"].get("cooperator", ""),
                    "improvement_percent": storage_data["metadata"].get("improvement_percent", 0),
                    "analysis_status": storage_data["metadata"].get("analysis_status", "unknown")
                },
                "graph_suggestions_count": len(
                    state.get("graph_suggestions", {}).get("suggested_charts", [])
                ),
                "validation_status": {
                    "file_valid": state.get("file_validation", {}).get("is_valid", False),
                    "content_valid": state.get("is_valid_content", False)
                },
                "errors": state.get("errors", []),
                "prepared_at": datetime.now().isoformat()
            }
            
            return preview
            
        except Exception as e:
            logger.error(f"Failed to create storage preview: {str(e)}")
            return {
                "error": str(e),
                "prepared_at": datetime.now().isoformat()
            }


# Global instance for easy import
storage_service = StorageService()
