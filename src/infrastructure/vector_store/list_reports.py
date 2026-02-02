from qdrant_client import QdrantClient
from qdrant_client.http import models
from typing import List, Dict, Any, Optional
from src.core.config import QDRANT_LOCAL_URI, QDRANT_COLLECTION_ANALYSIS, QDRANT_USE_API_KEY, QDRANT_API_KEY
from src.shared.logging.clean_logger import get_clean_logger
from src.shared.season_detector import detect_season_from_dates, get_season_name
import json


class ReportLister:
    
    def __init__(self):
        self.logger = get_clean_logger(__name__)
        # Initialize QdrantClient with optional API key (only when URL is HTTPS)
        # Increased timeout for remote Qdrant servers (60 seconds)
        if QDRANT_USE_API_KEY:
            self.client = QdrantClient(url=QDRANT_LOCAL_URI, api_key=QDRANT_API_KEY, timeout=60)
            self.logger.info("ReportLister: Initialized with API key (Qdrant Cloud)")
        else:
            self.client = QdrantClient(url=QDRANT_LOCAL_URI, timeout=60)
            self.logger.info("ReportLister: Initialized without API key (local Qdrant)")
        self.collection_name = QDRANT_COLLECTION_ANALYSIS
    
    async def list_all_reports(self, cooperative: Optional[str] = None) -> Dict[str, Any]:
        """
        List reports filtered by cooperative only.
        Same cooperative can see all data within that cooperative.
        
        Args:
            cooperative: Optional cooperative ID for filtering
        
        Returns:
            Dictionary with filtered reports
        """
        try:
            # Build filter for cooperative only
            # Note: Qdrant MatchValue is case-sensitive, so we'll do post-filtering
            # Store cooperative for post-filtering (normalized matching)
            scroll_filter = None  # Don't filter at Qdrant level - use post-filtering for case-insensitive matching
            cooperative_for_filtering = None
            if cooperative:
                cooperative_for_filtering = cooperative.strip()
                self.logger.debug(f"Will filter by cooperative in post-processing (case-insensitive): {cooperative_for_filtering}")
            
            # Fetch points - scroll through collection with filter
            all_points = []
            offset = None  # Start from beginning
            batch_size = 100  # Fetch in batches
            
            # Scroll through collection with filter
            while True:
                scroll_result = self.client.scroll(
                    collection_name=self.collection_name,
                    scroll_filter=scroll_filter,  # ✅ Filter by cooperative only
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
            
            # ✅ Helper function to safely extract nested data (handles both dict and JSON string for backward compatibility)
            def safe_extract_nested(field_value, default=None):
                """Extract nested data - handles both dict (new format) and JSON string (old format)"""
                if field_value is None:
                    return default if default is not None else {}
                
                # If already a dictionary, return as-is (new format)
                if isinstance(field_value, dict):
                    return field_value
                
                # If string, try to parse as JSON (old format - backward compatibility)
                if isinstance(field_value, str):
                    if not field_value or field_value == "{}":
                        return default if default is not None else {}
                    try:
                        return json.loads(field_value)
                    except (json.JSONDecodeError, TypeError):
                        self.logger.warning(f"Failed to parse JSON: {field_value[:100] if field_value else 'None'}...")
                        return default if default is not None else {}
                
                # Fallback
                return default if default is not None else {}
            
            # Normalize cooperative for matching (same logic as search tools)
            def normalize_coop(name):
                """Normalize cooperative name by removing common suffixes"""
                name = name.lower().strip()
                for suffix in [" agri", " agriculture", " cooperative", " coop"]:
                    if name.endswith(suffix):
                        name = name[:-len(suffix)].strip()
                return name
            
            query_coop_norm = normalize_coop(cooperative_for_filtering) if cooperative_for_filtering else None
            
            # Format ALL results with COMPLETE data
            reports = []
            for point in all_points:
                payload = point.payload or {}
                
                # Post-filter by cooperative (case-insensitive with normalization)
                if cooperative_for_filtering:
                    doc_cooperative = payload.get("cooperative", "").strip()
                    doc_coop_norm = normalize_coop(doc_cooperative)
                    
                    # Match if normalized names match, or if one contains the other
                    if (query_coop_norm != doc_coop_norm and 
                        query_coop_norm not in doc_coop_norm and 
                        doc_coop_norm not in query_coop_norm):
                        continue  # Skip this document
                
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
                    
                    # ✅ FULL DATA - Direct dictionary access (with backward compatibility for old JSON strings)
                    "full_analysis": safe_extract_nested(
                        payload.get("full_analysis"),
                        default={}
                    ),
                    "graph_suggestions": safe_extract_nested(
                        payload.get("graph_suggestions"),
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
                    
                    # User ID and Cooperative
                    "user_id": payload.get("user_id", ""),
                    "cooperative": payload.get("cooperative", ""),
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
    
    def get_collection_stats(self, cooperative: Optional[str] = None) -> Dict[str, Any]:
        """
        Get collection statistics filtered by cooperative only.
        
        Args:
            cooperative: Optional cooperative ID for filtering
        
        Returns:
            Dictionary with collection stats
        """
        try:
            # Build filter for cooperative only
            count_filter = None
            if cooperative:
                count_filter = models.Filter(
                    must=[
                        models.FieldCondition(
                            key="cooperative",
                            match=models.MatchValue(value=cooperative)
                        )
                    ]
                )
            
            # Get count with filter
            count_result = self.client.count(
                collection_name=self.collection_name,
                count_filter=count_filter
            )
            
            return {
                "total_reports": count_result.count,
                "collection_name": self.collection_name,
                "status": "ready",
                "cooperative": cooperative
            }
        except Exception as e:
            self.logger.error(f"Error getting collection stats: {str(e)}")
            return {
                "status": "error",
                "error": str(e)
            }


# Global instance for easy import
report_lister = ReportLister()

