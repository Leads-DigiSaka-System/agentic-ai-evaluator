# file: src/database/insert_analysis.py
from qdrant_client import QdrantClient
from qdrant_client.http import models
from src.generator.encoder import DenseEncoder
from src.utils.config import QDRANT_LOCAL_URI,QDRANT_COLLECTION_ANALYSIS
from typing import Dict, Any, List, Optional
import uuid
import logging
from datetime import datetime, date
import json

logger = logging.getLogger(__name__)

class AnalysisStorage:
    """Store analyzed agricultural demo data with graph suggestions"""
    
    def __init__(self):
        self.client = QdrantClient(url=QDRANT_LOCAL_URI)
        self.collection_name = QDRANT_COLLECTION_ANALYSIS
        self.dense_encoder = DenseEncoder()
        self.vector_size = 768
        
    def _safe_json_dumps(self, obj: Any) -> str:
        """Safely serialize to JSON handling non-serializable types"""
        if obj is None:
            return "{}"
            
        def default_serializer(o):
            if isinstance(o, (datetime, date)):
                return o.isoformat()
            elif hasattr(o, '__dict__'):
                return o.__dict__
            else:
                return str(o)
        
        try:
            return json.dumps(obj, default=default_serializer, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"JSON serialization failed, using string fallback: {str(e)}")
            return json.dumps({"error": "Failed to serialize", "original_type": str(type(obj))})
    
    def ensure_analysis_collection(self) -> bool:
        """Create collection for storing analysis results"""
        try:
            # Check if collection exists
            try:
                self.client.get_collection(self.collection_name)
                logger.info(f"📦 Analysis collection '{self.collection_name}' already exists")
                return True
            except Exception:
                # Collection doesn't exist, create it
                logger.info(f"📦 Creating analysis collection: {self.collection_name}")
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config={
                        "dense": models.VectorParams(
                            size=self.vector_size,
                            distance=models.Distance.COSINE
                        )
                    }
                )
                logger.info(f"✅ Analysis collection '{self.collection_name}' created")
                return True
                
        except Exception as e:
            logger.error(f"❌ Failed to ensure analysis collection: {str(e)}")
            return False
    
    def insert_multi_report_response(self, response: Dict[str, Any]) -> bool:
        """
        Insert complete multi-report response with all reports
        """
        try:
            if response.get("status") != "success":
                logger.warning("⚠️ Response status is not success, skipping insertion")
                return False
            
            reports = response.get("reports", [])
            if not reports:
                logger.warning("⚠️ No reports to insert")
                return False
            
            # Ensure collection exists
            if not self.ensure_analysis_collection():
                return False
            
            inserted_count = 0
            total_reports = len(reports)
            
            # Insert each report
            for report in reports:
                if self._insert_single_report(report, response):
                    inserted_count += 1
            
            # Store cross-report analysis for multi-reports
            if total_reports > 1 and inserted_count > 0:
                self._insert_cross_report_analysis(response)
            
            success_rate = (inserted_count / total_reports) * 100
            logger.info(f"✅ Inserted {inserted_count}/{total_reports} reports ({success_rate:.1f}% success rate)")
            
            return inserted_count > 0
            
        except Exception as e:
            logger.error(f"❌ Failed to insert multi-report response: {str(e)}")
            return False
    
    def _insert_single_report(self, report: Dict[str, Any], 
                             full_response: Dict[str, Any]) -> bool:
        """Insert a single report from the reports array"""
        try:
            # Validate required fields
            if not report or not isinstance(report, dict):
                logger.warning("⚠️ Invalid report format")
                return False
            
            analysis = report.get("analysis", {})
            graph_suggestions = report.get("graph_suggestions", {})
            
            # Skip if no analysis data or analysis failed
            if not analysis or analysis.get("status") == "error":
                logger.warning(f"⚠️ Skipping report {report.get('report_number')} - no valid analysis data")
                return False
            
            # Extract key info with safe access
            basic_info = analysis.get("basic_info", {})
            performance = analysis.get("performance_analysis", {})
            calculated = performance.get("calculated_metrics", {})
            cooperator_feedback = analysis.get("cooperator_feedback", {})
            commercial = analysis.get("commercial_metrics", {})
            
            # Create searchable summary text
            summary_text = self._create_summary_text(
                basic_info, calculated, cooperator_feedback, 
                report.get("form_type", ""), analysis
            )
            
            # Validate and generate vector
            if not summary_text or len(summary_text.strip()) < 10:
                summary_text = self._create_fallback_summary(basic_info)
            
            try:
                vector = self.dense_encoder.encode([summary_text])[0]
                if len(vector) != self.vector_size:
                    logger.error(f"❌ Vector size mismatch: {len(vector)} != {self.vector_size}")
                    return False
            except Exception as e:
                logger.error(f"❌ Vector encoding failed: {str(e)}")
                return False
            
            # Generate unique form_id if missing
            form_id = report.get("form_id") or f"form_{uuid.uuid4().hex[:8]}"
            
            # Prepare payload with safe nested access
            payload = self._prepare_report_payload(
                report, analysis, graph_suggestions, basic_info, 
                calculated, performance, cooperator_feedback, commercial,
                form_id, full_response, summary_text
            )
            
            # Create and insert point
            point_id = str(uuid.uuid4())
            point = models.PointStruct(
                id=point_id,
                vector={"dense": vector},
                payload=payload
            )
            
            # Insert into Qdrant
            operation_info = self.client.upsert(
                collection_name=self.collection_name,
                points=[point],
                wait=True
            )
            
            logger.info(f"✅ Report #{report.get('report_number')} inserted - {basic_info.get('product', 'N/A')}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to insert report {report.get('report_number')}: {str(e)}")
            return False
    
    def _prepare_report_payload(self, report: Dict, analysis: Dict, graph_suggestions: Dict,
                               basic_info: Dict, calculated: Dict, performance: Dict,
                               cooperator_feedback: Dict, commercial: Dict,
                               form_id: str, full_response: Dict, summary_text: str) -> Dict[str, Any]:
        """Prepare comprehensive payload with safe data access"""
        
        # Safe nested access for treatment comparison
        treatment_comparison = analysis.get("treatment_comparison", {})
        control_product = (treatment_comparison.get("control") or {}).get("product", "")
        leads_product = (treatment_comparison.get("leads_agri") or {}).get("product", "")
        
        # Safe nested access for statistical assessment
        statistical_assessment = performance.get("statistical_assessment", {})
        
        return {
            # Identification
            "form_id": form_id,
            "report_number": report.get("report_number", 1),
            "file_name": report.get("file_name", ""),
            "form_type": report.get("form_type", ""),
            "insertion_date": datetime.now().isoformat(),
            
            # Basic Info
            "cooperator": basic_info.get("cooperator", ""),
            "product": basic_info.get("product", ""),
            "location": basic_info.get("location", ""),
            "crop": basic_info.get("crop", ""),
            "application_date": basic_info.get("application_date", ""),
            "planting_date": basic_info.get("planting_date", ""),
            "plot_size": basic_info.get("plot_size", ""),
            "contact": basic_info.get("contact", ""),
            
            # Performance Metrics
            "improvement_percent": float(calculated.get("improvement_percent", 0)),
            "control_average": float(calculated.get("control_average", 0)),
            "leads_average": float(calculated.get("leads_average", 0)),
            "improvement_value": float(calculated.get("improvement_value", 0)),
            "performance_significance": statistical_assessment.get("improvement_significance", ""),
            "confidence_level": statistical_assessment.get("confidence_level", ""),
            
            # Product Category & Metrics
            "product_category": analysis.get("product_category", ""),
            "metrics_detected": analysis.get("metrics_detected", []),
            "measurement_intervals": analysis.get("measurement_intervals", []),
            "metric_type": performance.get("metric_type", ""),
            
            # Commercial Metrics
            "demo_date": commercial.get("demo_date", ""),
            "demo_participants": int(commercial.get("participants", 0)),
            "total_sales": float(commercial.get("total_sales", 0)),
            "sales_per_participant": float(commercial.get("sales_per_participant", 0)),
            "demo_conducted": bool(commercial.get("demo_conducted", False)),
            
            # Treatment Info
            "control_product": control_product,
            "leads_product": leads_product,
            
            # Feedback & Sentiment
            "cooperator_feedback": cooperator_feedback.get("raw_feedback", ""),
            "feedback_sentiment": cooperator_feedback.get("sentiment", ""),
            
            # Quality Indicators
            "data_quality_score": float(analysis.get("data_quality", {}).get("completeness_score", 0)),
            "missing_fields": analysis.get("data_quality", {}).get("missing_fields", []),
            
            # Full Data (safe JSON serialization)
            "full_analysis": self._safe_json_dumps(analysis),
            "graph_suggestions": self._safe_json_dumps(graph_suggestions),
            "chart_count": len(graph_suggestions.get("suggested_charts", [])),
            
            # Extracted content (controlled size)
            "extracted_content_preview": (report.get("extracted_content", "")[:200] + "...") 
                if len(report.get("extracted_content", "")) > 200 
                else report.get("extracted_content", ""),
            
            # Searchable summaries
            "summary_text": summary_text,
            "executive_summary": analysis.get("executive_summary", "")[:500],  # Limit size
            
            # Multi-report context
            "is_multi_report": full_response.get("total_reports", 1) > 1,
            "total_reports_in_batch": full_response.get("total_reports", 1),
            
            # Errors
            "has_errors": len(report.get("errors", [])) > 0,
            "errors": report.get("errors", [])[:10]  # Limit error list
        }
    
    def _create_fallback_summary(self, basic_info: Dict) -> str:
        """Create fallback summary when main summary fails"""
        product = basic_info.get("product", "unknown product")
        location = basic_info.get("location", "unknown location")
        cooperator = basic_info.get("cooperator", "unknown cooperator")
        return f"Agricultural demo for {product} at {location} by {cooperator}"
    
    def _insert_cross_report_analysis(self, response: Dict[str, Any]):
        """Insert cross-report comparison analysis"""
        try:
            cross_analysis = response.get("cross_report_analysis", {})
            if not cross_analysis.get("cross_report_suggestions"):
                return
            
            summary_text = f"Cross-report analysis of {response.get('total_reports')} agricultural demos"
            vector = self.dense_encoder.encode([summary_text])[0]
            
            payload = {
                "form_id": f"cross_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                "report_type": "cross_report_analysis",
                "total_reports": response.get("total_reports", 0),
                "insertion_date": datetime.now().isoformat(),
                "cross_report_data": json.dumps(cross_analysis),
                "summary_text": summary_text
            }
            
            point = models.PointStruct(
                id=str(uuid.uuid4()),
                vector={"analysis_vector": vector},
                payload=payload
            )
            
            self.client.upsert(
                collection_name=self.collection_name,
                points=[point],
                wait=True
            )
            
            logger.info(f"✅ Cross-report analysis inserted")
            
        except Exception as e:
            logger.error(f"⚠️ Failed to insert cross-report analysis: {str(e)}")
    
    def _create_summary_text(self, basic_info: Dict, calculated: Dict, 
                            feedback: Dict, form_type: str, 
                            full_analysis: Dict) -> str:
        """Create searchable text summary from analysis"""
        parts = []
        
        # Product and location
        if basic_info.get("product"):
            parts.append(f"Product: {basic_info['product']}")
        if basic_info.get("location"):
            parts.append(f"Location: {basic_info['location']}")
        if basic_info.get("cooperator"):
            parts.append(f"Cooperator: {basic_info['cooperator']}")
        if basic_info.get("crop"):
            parts.append(f"Crop: {basic_info['crop']}")
        
        # Form type and category
        if form_type:
            parts.append(f"Form Type: {form_type}")
        if full_analysis.get("product_category"):
            parts.append(f"Category: {full_analysis['product_category']}")
        
        # Performance
        improvement = calculated.get("improvement_percent", 0)
        if improvement != 0:
            parts.append(f"Improvement: {improvement:.2f}%")
            if calculated.get("improvement_interpretation"):
                parts.append(calculated.get("improvement_interpretation", ""))
        
        # Feedback
        if feedback.get("raw_feedback") and feedback.get("raw_feedback") != "N/A":
            parts.append(f"Feedback: {feedback['raw_feedback']}")
        
        # Key observations
        trend = full_analysis.get("performance_analysis", {}).get("trend_analysis", {})
        if trend.get("key_observation"):
            parts.append(trend["key_observation"])
        
        # Recommendations (top 2 only)
        recommendations = full_analysis.get("recommendations", [])
        if recommendations:
            top_recs = [r.get("recommendation", "") for r in recommendations[:2] if r.get("recommendation")]
            if top_recs:
                parts.append(f"Recommendations: {' '.join(top_recs)}")
        
        # Executive summary
        if full_analysis.get("executive_summary"):
            parts.append(full_analysis["executive_summary"])
        
        return " | ".join(parts)


# Global instance
analysis_storage = AnalysisStorage()