from qdrant_client import QdrantClient
from qdrant_client.http import models
from typing import List, Dict, Any, Optional
from src.utils.config import QDRANT_LOCAL_URI, QDRANT_COLLECTION_ANALYSIS, QDRANT_API_KEY
from src.utils.clean_logger import get_clean_logger
from src.utils.season_detector import detect_season_from_dates, get_season_name
import json


class ReportLister:
    
    def __init__(self):
        self.logger = get_clean_logger(__name__)
        # Initialize QdrantClient with optional API key for Qdrant Cloud
        # Increased timeout for remote Qdrant servers (60 seconds)
        if QDRANT_API_KEY:
            self.client = QdrantClient(url=QDRANT_LOCAL_URI, api_key=QDRANT_API_KEY, timeout=60)
            self.logger.info("ReportLister: Initialized with API key (Qdrant Cloud)")
        else:
            self.client = QdrantClient(url=QDRANT_LOCAL_URI, timeout=60)
            self.logger.info("ReportLister: Initialized without API key (local Qdrant)")
        self.collection_name = QDRANT_COLLECTION_ANALYSIS
    
    async def list_all_reports(self) -> Dict[str, Any]:
        """
        List ALL reports - simple get all, no pagination, no sorting.
        Everyone sees everything.
        
        Returns:
            Dictionary with all reports
        """
        try:
            # Fetch ALL points - simple scroll through entire collection
            all_points = []
            offset = None  # Start from beginning
            batch_size = 100  # Fetch in batches
            
            # Scroll through entire collection
            while True:
                scroll_result = self.client.scroll(
                    collection_name=self.collection_name,
                    scroll_filter=None,  #  No filter - show everything
                    limit=batch_size,
                    offset=offset,
                    with_payload=True,
                    with_vectors=False
                )
                
                points, next_offset = scroll_result
                if not points:
                    break
                
                all_points.extend(points)
                
                # Check if there are more points
                if next_offset is None:
                    break
                offset = next_offset
            
            # Helper function to safely parse JSON strings
            def safe_json_parse(json_str: str, default=None):
                """Safely parse JSON string, return default if fails"""
                if not json_str or json_str == "{}":
                    return default if default is not None else {}
                try:
                    return json.loads(json_str)
                except (json.JSONDecodeError, TypeError):
                    self.logger.warning(f"Failed to parse JSON: {json_str[:100] if json_str else 'None'}...")
                    return default if default is not None else {}
            
            # Format ALL results with COMPLETE data
            reports = []
            for point in all_points:
                payload = point.payload or {}
                
                # Helper to safely convert to float
                def safe_float(value, default=0.0):
                    try:
                        return float(value) if value is not None else default
                    except (ValueError, TypeError):
                        return default
                
                report = {
                    # Identification
                    "id": payload.get("form_id", ""),
                    "report_number": payload.get("report_number", 1),
                    "file_name": payload.get("file_name", ""),
                    "form_type": payload.get("form_type", ""),
                    "insertion_date": payload.get("insertion_date", ""),
                    
                    # Basic Info
                    "cooperator": payload.get("cooperator", ""),
                    "product": payload.get("product", ""),
                    "location": payload.get("location", ""),
                    "crop": payload.get("crop", ""),
                    "application_date": payload.get("application_date", ""),
                    "planting_date": payload.get("planting_date", ""),
                    "plot_size": payload.get("plot_size", ""),
                    "contact": payload.get("contact", ""),
                    # ✅ Season (wet/dry) - from stored value or detect from dates
                    "season": (season_value := payload.get("season") or detect_season_from_dates(
                        application_date=payload.get("application_date", ""),
                        planting_date=payload.get("planting_date", "")
                    )),
                    "season_name": get_season_name(season_value),
                    
                    # Performance Metrics
                    "improvement_percent": safe_float(payload.get("improvement_percent", 0)),
                    "control_average": safe_float(payload.get("control_average", 0)),
                    "leads_average": safe_float(payload.get("leads_average", 0)),
                    "improvement_value": safe_float(payload.get("improvement_value", 0)),
                    "performance_significance": payload.get("performance_significance", ""),
                    "confidence_level": payload.get("confidence_level", ""),
                    
                    # Product Category & Metrics
                    "product_category": payload.get("product_category", ""),
                    "metrics_detected": payload.get("metrics_detected", []),
                    "measurement_intervals": payload.get("measurement_intervals", []),
                    "metric_type": payload.get("metric_type", ""),
                    
                    # Treatment Info
                    "control_product": payload.get("control_product", ""),
                    "leads_product": payload.get("leads_product", ""),
                    
                    # Feedback & Sentiment
                    "cooperator_feedback": payload.get("cooperator_feedback", ""),
                    "feedback_sentiment": payload.get("feedback_sentiment", ""),
                    
                    # Quality Indicators
                    "data_quality_score": safe_float(payload.get("data_quality_score", 0)),
                    "missing_fields": payload.get("missing_fields", []),
                    
                    # ✅ FULL DATA - Parse JSON strings back to objects
                    "full_analysis": safe_json_parse(
                        payload.get("full_analysis", "{}"),
                        default={}
                    ),
                    "graph_suggestions": safe_json_parse(
                        payload.get("graph_suggestions", "{}"),
                        default={}
                    ),
                    "chart_count": payload.get("chart_count", 0),
                    
                    # Extracted content
                    "extracted_content_preview": payload.get("extracted_content_preview", ""),
                    
                    # Searchable summaries
                    "summary_text": payload.get("summary_text", ""),
                    "executive_summary": payload.get("executive_summary", ""),
                    
                    # Multi-report context
                    "is_multi_report": payload.get("is_multi_report", False),
                    "total_reports_in_batch": payload.get("total_reports_in_batch", 1),
                    
                    # Errors
                    "has_errors": payload.get("has_errors", False),
                    "errors": payload.get("errors", []),
                    
                    # User ID
                    "user_id": payload.get("user_id", ""),
                }
                
                reports.append(report)
            
            self.logger.info(f"Retrieved {len(reports)} reports (all data)")
            
            return {
                "reports": reports,
                "total_count": len(reports),
                "status": "success"
            }
            
        except Exception as e:
            self.logger.error(f"Error listing reports: {str(e)}", exc_info=True)
            return {
                "reports": [],
                "pagination": {},
                "status": "error",
                "error": str(e)
            }
    
    def _get_total_count(self) -> int:
        """Get total count of all reports (no filtering)."""
        try:
            count_result = self.client.count(
                collection_name=self.collection_name,
                count_filter=None  # ✅ Count everything
            )
            return count_result.count
        except Exception as e:
            self.logger.error(f"Error counting reports: {str(e)}")
            return 0
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """
        Get collection statistics - useful for admin dashboard.
        
        Returns:
            Dictionary with collection stats
        """
        try:
            collection_info = self.client.get_collection(self.collection_name)
            return {
                "total_reports": collection_info.points_count,
                "collection_name": self.collection_name,
                "status": "ready"
            }
        except Exception as e:
            self.logger.error(f"Error getting collection stats: {str(e)}")
            return {
                "status": "error",
                "error": str(e)
            }


# Global instance for easy import
report_lister = ReportLister()

