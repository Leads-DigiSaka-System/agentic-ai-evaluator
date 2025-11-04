import os
import tempfile
import re
from typing import List, Dict, Any
from src.workflow.state import ProcessingState
from src.workflow.graph import processing_workflow
from src.Upload.form_extractor import extract_pdf_with_gemini, extract_pdf_metadata
from src.database.insert_analysis import analysis_storage 
from src.utils.clean_logger import get_clean_logger
from src.utils.config import LANGFUSE_CONFIGURED

# Import Langfuse decorator if available
if LANGFUSE_CONFIGURED:
    try:
        from langfuse import observe
        from src.monitoring.trace.langfuse_helper import (
            flush_langfuse, 
            update_trace_with_metrics, 
            get_trace_url,
            get_langfuse_client
        )
        LANGFUSE_AVAILABLE = True
    except ImportError:
        LANGFUSE_AVAILABLE = False
        def observe(*args, **kwargs):
            def decorator(func):
                return func
            return decorator
        def flush_langfuse():
            pass
        def update_trace_with_metrics(*args, **kwargs):
            pass
        def get_trace_url():
            return None
        def get_langfuse_client():
            return None
else:
    LANGFUSE_AVAILABLE = False
    def observe(*args, **kwargs):
        def decorator(func):
            return func
        return decorator
    def flush_langfuse():
        pass
    def update_trace_with_metrics(*args, **kwargs):
        pass
    def get_trace_url():
        return None
    def get_langfuse_client():
        return None

logger = get_clean_logger(__name__)


class MultiReportHandler:
    """Handler for processing PDFs with multiple reports including graph suggestions"""
    
    @staticmethod
    async def process_multi_report_pdf(file_content: bytes, original_filename: str) -> Dict[str, Any]:
        """
        Process a file that may contain multiple reports
        
        SUPPORTS: PDF (single/multi-report), PNG, JPG, JPEG
        
        NOW WITH VALIDATION:
        - File format validation happens during extraction
        - Content validation happens in workflow
        - Auto-detects file type from extension
        """
        tmp_path = None
        try:
            # Detect file type from original filename
            file_ext = original_filename.lower().split('.')[-1] if '.' in original_filename else 'pdf'
            suffix = f".{file_ext}"
            
            logger.file_upload(original_filename, len(file_content))
            
            # Save with correct extension
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix, mode='wb') as tmp_file:
                tmp_file.write(file_content)
                tmp_file.flush()
                tmp_path = tmp_file.name
            
            logger.info(f"Saved to temporary file: {tmp_path}")

            # Extract content (supports both PDF and images via Gemini)
            logger.file_extraction(original_filename, file_ext.upper(), len(file_content))
            extracted_markdown = extract_pdf_with_gemini(tmp_path)
            
            if not extracted_markdown:
                logger.file_error(original_filename, f"Failed to extract content from {file_ext.upper()}")
                raise Exception(
                    f"Failed to extract content from {file_ext.upper()}. "
                    "File may be corrupted, encrypted, or not a valid file."
                )

            # Extract metadata (handles both PDF and images)
            pdf_metadata = extract_pdf_metadata(tmp_path)

            # Split and process reports
            result = await MultiReportHandler._process_reports(
                extracted_markdown, file_content, original_filename, tmp_path, pdf_metadata
            )

            return result

        except Exception as e:
            raise e
        finally:
            # Clean up temporary file
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except:
                    pass

    @staticmethod
    async def _process_reports(extracted_markdown: str, file_content: bytes, 
                             original_filename: str, tmp_path: str, pdf_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Split markdown into individual reports using intelligent detection
        
        WORKS WITH VALIDATION:
        - Single reports: Full validation in workflow (extract → validate → analyze)
        - Multiple reports: Pre-extracted markdown, content validated in workflow
        """
        # Use the unique separator for splitting
        reports_markdown = MultiReportHandler._split_reports_intelligently(extracted_markdown)

        logger.processing_start("multi-report processing", f"file: {original_filename}")

        # CRITICAL FIX: Handle single vs multiple reports differently
        if len(reports_markdown) == 1:
            # For SINGLE REPORT, use full workflow with validation
            logger.info("Processing as SINGLE REPORT (full validation enabled)")
            report_response = await MultiReportHandler._process_single_report_direct(
                tmp_path, file_content, original_filename, pdf_metadata
            )
            
            # Check if content validation failed
            if report_response.get("errors"):
                validation_errors = [e for e in report_response["errors"] if "validation" in e.lower()]
                if validation_errors:
                    logger.file_validation(original_filename, "failed", validation_errors[0])
            
            result = {
                "status": "success" if not report_response.get("errors") else "failed",
                "total_reports": 1,
                "reports": [report_response],
                "cross_report_analysis": {"cross_report_suggestions": []}
            }
            
            # Analysis storage is now handled separately via API endpoint
            result["analysis_storage_status"] = "ready_for_approval"
            logger.storage_start("analysis storage", "ready for user approval")
            
            return result
        
        # For MULTIPLE REPORTS, use pre-extracted markdown approach
        all_reports_response = []
        for i, report_md in enumerate(reports_markdown):
            report_response = await MultiReportHandler._process_single_report(
                report_md, file_content, original_filename, tmp_path, pdf_metadata, i, len(reports_markdown)
            )
            all_reports_response.append(report_response)

        # Generate cross-report graph suggestions
        cross_report_suggestions = MultiReportHandler._generate_cross_report_suggestions(all_reports_response)

        result = {
            "status": "success",
            "total_reports": len(all_reports_response),
            "reports": all_reports_response,
            "cross_report_analysis": cross_report_suggestions
        }
        
        result["analysis_storage_status"] = "ready_for_approval"
        logger.storage_start("analysis storage", "ready for user approval")
        
        return result

    @staticmethod
    @observe(as_type="generation", name="process_single_report_direct")
    async def _process_single_report_direct(tmp_path: str, file_content: bytes, 
                                           original_filename: str, pdf_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a SINGLE report PDF with FULL VALIDATION
        
        Uses official Langfuse @observe() decorator for tracing
        """
        logger = get_clean_logger(__name__)
        
        try:
            logger.info("Processing SINGLE REPORT with full validation")
            
            # Detect file_type from metadata or filename extension
            file_type = pdf_metadata.get("file_type")
            if not file_type or file_type == "unknown":
                file_ext = original_filename.lower().split('.')[-1] if '.' in original_filename else ''
                if file_ext == 'pdf':
                    file_type = "pdf"
                elif file_ext in ['png', 'jpg', 'jpeg']:
                    file_type = "image"
                else:
                    file_type = file_ext or "unknown"
            
            # Log processing start to Langfuse
            if LANGFUSE_AVAILABLE:
                client = get_langfuse_client()
                if client:
                    try:
                        client.update_current_trace(
                            name="process_single_report",
                            metadata={
                                "file_name": original_filename,
                                "file_type": file_type,
                                "file_size": len(file_content),
                                "processing_type": "single_report"
                            },
                            tags=["single_report", file_type, "agricultural_demo"]
                        )
                    except Exception:
                        pass  # Silently fail if not in trace context

            # Initialize state WITHOUT pre-extracted markdown
            initial_state: ProcessingState = {
                "file_path": tmp_path,
                "file_name": original_filename,
                "file_content": file_content,
                "extracted_markdown": None,
                "form_type": None,
                "chunks": [],
                "analysis_result": None,
                "graph_suggestions": None,
                "form_id": "",
                "metadata": {},
                "insertion_date": "",
                "current_step": "start",
                "errors": [],
                "file_validation": None,
                "is_valid_content": None,
                "content_validation": None
            }

            # Execute the workflow (now includes validation)
            final_state = processing_workflow.invoke(initial_state)

            # Build response with validation info
            report_response = {
                "report_number": 1,
                "file_name": original_filename,
                "form_id": "",
                "form_type": final_state.get("form_type", ""),
                "extracted_content": final_state.get("extracted_markdown", ""),
                "analysis": final_state.get("analysis_result", {}),
                "graph_suggestions": final_state.get("graph_suggestions", {}),
                "chunks": final_state.get("chunks", []),
                "processing_metrics": {
                    "chunk_count": len(final_state.get("chunks", [])),
                    "processing_steps": final_state.get("current_step", ""),
                    "workflow_completed": True,
                    "storage_ready": True
                },
                "errors": final_state.get("errors", []),
                "validation": {
                    "file_validation": final_state.get("file_validation"),
                    "content_validation": final_state.get("content_validation")
                },
                "storage_status": "ready_for_approval",
                "storage_message": "Analysis completed. Use /api/storage/preview to review and /api/storage/approve to store."
            }

            # Log final metrics to Langfuse
            if LANGFUSE_AVAILABLE:
                update_trace_with_metrics({
                    "success": len(final_state["errors"]) == 0,
                    "error_count": len(final_state["errors"]),
                    "chunk_count": len(final_state.get("chunks", [])),
                    "chart_count": len(final_state.get("graph_suggestions", {}).get("suggested_charts", [])),
                    "form_type": final_state.get("form_type", ""),
                    "is_valid_content": final_state.get("is_valid_content", False),
                    "final_step": final_state.get("current_step", "")
                })
                
                trace_url = get_trace_url()
                if trace_url:
                    logger.info(f"📊 Langfuse trace: {trace_url}")

            if final_state["errors"]:
                logger.processing_error(original_filename, f"Single report completed with errors: {final_state['errors']}")
            else:
                chart_count = len(final_state.get("graph_suggestions", {}).get("suggested_charts", []))
                logger.processing_success(original_filename, f"Single report processed successfully with {chart_count} chart suggestions")

            # Flush Langfuse events
            flush_langfuse()
            logger.info(f"✅ Workflow completed - trace available in Langfuse dashboard")

            return report_response

        except Exception as e:
            logger.processing_error(original_filename, f"Failed to process single report: {str(e)}")
            import traceback
            traceback.print_exc()
            
            # Log error to Langfuse
            if LANGFUSE_AVAILABLE:
                from src.monitoring.trace.langfuse_helper import update_trace_with_error
                update_trace_with_error(e, {
                    "file_name": original_filename,
                    "processing_type": "single_report"
                })
            
            # Flush even on error
            flush_langfuse()
            
            return {
                "report_number": 1,
                "file_name": original_filename,
                "form_id": "",
                "form_type": "",
                "extracted_content": "",
                "analysis": {},
                "graph_suggestions": {},
                "processing_metrics": {},
                "errors": [f"Single report processing failed: {str(e)}"],
                "validation": {"file_validation": None, "content_validation": None},
                "storage_status": "failed",
                "storage_message": "Processing failed - cannot store"
            }

    @staticmethod
    def _split_reports_intelligently(markdown_content: str) -> List[str]:
        """Intelligently split markdown into individual reports"""
        logger = get_clean_logger(__name__)
        
        unique_separator = "### REPORT_END ###"
        if unique_separator in markdown_content:
            reports = markdown_content.split(unique_separator)
            reports = [report.strip() for report in reports if report.strip()]
            if len(reports) > 1:
                logger.info(f"Using unique separator, found {len(reports)} reports")
                return reports

        headings = re.findall(r'^#\s+.+$', markdown_content, re.MULTILINE)
        if len(headings) > 1:
            logger.info(f"Found {len(headings)} potential reports by heading detection")
            reports = re.split(r'^(?=#\s+)', markdown_content, flags=re.MULTILINE)
            reports = [report.strip() for report in reports if report.strip() and report.startswith('#')]
            if len(reports) > 1:
                return reports

        logger.info("No clear report separators found, treating as SINGLE REPORT")
        return [markdown_content]

    @staticmethod
    @observe(as_type="generation", name="process_single_report")
    async def _process_single_report(report_md: str, file_content: bytes, original_filename: str,
                                   tmp_path: str, pdf_metadata: Dict[str, Any], 
                                   report_index: int, total_reports: int) -> Dict[str, Any]:
        """Process a single report from a MULTI-REPORT PDF"""
        logger = get_clean_logger(__name__)
        
        try:
            logger.info(f"Processing report {report_index + 1}/{total_reports}")

            file_type = pdf_metadata.get("file_type", "pdf")
            
            # Log to Langfuse
            if LANGFUSE_AVAILABLE:
                client = get_langfuse_client()
                if client:
                    try:
                        client.update_current_trace(
                            name=f"process_report_{report_index + 1}",
                            metadata={
                                "report_number": report_index + 1,
                                "total_reports": total_reports,
                                "file_name": original_filename,
                                "file_type": file_type
                            },
                            tags=["multi_report", file_type, f"report_{report_index + 1}"]
                        )
                    except Exception:
                        pass  # Silently fail if not in trace context

            initial_state: ProcessingState = {
                "file_path": tmp_path,
                "file_name": f"{original_filename}_report_{report_index + 1}",
                "file_content": file_content,
                "extracted_markdown": report_md,
                "form_type": None,
                "chunks": [],
                "analysis_result": None,
                "graph_suggestions": None,
                "form_id": "",
                "metadata": pdf_metadata,
                "insertion_date": "",
                "current_step": "start",
                "errors": [],
                "file_validation": {"is_valid": True, "validation_skipped": True},
                "is_valid_content": None,
                "content_validation": None
            }

            final_state = processing_workflow.invoke(initial_state)

            report_response = {
                "report_number": report_index + 1,
                "file_name": original_filename,
                "form_id": "",
                "form_type": final_state.get("form_type", ""),
                "extracted_content": final_state.get("extracted_markdown", ""),
                "analysis": final_state.get("analysis_result", {}),
                "graph_suggestions": final_state.get("graph_suggestions", {}),
                "chunks": final_state.get("chunks", []),
                "processing_metrics": {
                    "chunk_count": len(final_state.get("chunks", [])),
                    "processing_steps": final_state.get("current_step", ""),
                    "workflow_completed": True,
                    "storage_ready": True
                },
                "errors": final_state.get("errors", []),
                "validation": {
                    "content_validation": final_state.get("content_validation")
                },
                "storage_status": "ready_for_approval",
                "storage_message": "Analysis completed. Use /api/storage/preview to review and /api/storage/approve to store."
            }

            # Log metrics
            if LANGFUSE_AVAILABLE:
                update_trace_with_metrics({
                    "report_number": report_index + 1,
                    "success": len(final_state["errors"]) == 0,
                    "error_count": len(final_state["errors"]),
                    "chart_count": len(final_state.get("graph_suggestions", {}).get("suggested_charts", []))
                })

            if final_state["errors"]:
                logger.processing_error(f"Report {report_index + 1}", f"Report completed with errors")
            else:
                logger.processing_success(f"Report {report_index + 1}", "Report processed successfully")

            flush_langfuse()

            return report_response

        except Exception as e:
            logger.processing_error(f"Report {report_index + 1}", f"Failed: {str(e)}")
            
            if LANGFUSE_AVAILABLE:
                from src.monitoring.trace.langfuse_helper import update_trace_with_error
                update_trace_with_error(e, {
                    "report_number": report_index + 1,
                    "file_name": original_filename
                })
            
            flush_langfuse()
            
            return {
                "report_number": report_index + 1,
                "file_name": original_filename,
                "form_id": "",
                "form_type": "",
                "extracted_content": "",
                "analysis": {},
                "graph_suggestions": {},
                "processing_metrics": {},
                "errors": [f"Report processing failed: {str(e)}"],
                "validation": {"content_validation": None},
                "storage_status": "failed",
                "storage_message": "Processing failed - cannot store"
            }

    @staticmethod
    def _generate_cross_report_suggestions(all_reports: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate graph suggestions that compare multiple reports"""
        try:
            if len(all_reports) <= 1:
                return {"cross_report_suggestions": []}
            
            performance_data = []
            product_types = set()
            
            for report in all_reports:
                analysis = report.get("analysis", {})
                basic_info = analysis.get("basic_info", {})
                perf_analysis = analysis.get("performance_analysis", {})
                calculated = perf_analysis.get("calculated_metrics", {})
                
                relative_improvement = calculated.get("relative_improvement_percent")
                improvement_percent = (
                    relative_improvement
                    if isinstance(relative_improvement, (int, float))
                    else calculated.get("improvement_percent", 0)
                )

                performance_data.append({
                    "report_number": report.get("report_number"),
                    "product": basic_info.get("product", "Unknown Product"),
                    "location": basic_info.get("location", "Unknown Location"),
                    "improvement_percent": improvement_percent,
                    "control_average": calculated.get("control_average", 0),
                    "leads_average": calculated.get("leads_average", 0),
                    "form_type": report.get("form_type", "unknown")
                })
                product_types.add(report.get("form_type", "unknown"))
            
            cross_report_charts = MultiReportHandler._create_cross_report_charts(performance_data, product_types)
            
            return {
                "cross_report_suggestions": cross_report_charts,
                "summary": f"Generated {len(cross_report_charts)} cross-report charts comparing {len(performance_data)} reports"
            }
            
        except Exception as e:
            logger.warning(f"Failed to generate cross-report suggestions: {str(e)}")
            return {"cross_report_suggestions": []}

    @staticmethod
    def _create_cross_report_charts(performance_data: List[Dict], product_types: set) -> List[Dict]:
        """Create cross-report charts based on data patterns"""
        charts = []
        
        improvement_data = sorted(performance_data, key=lambda x: x['improvement_percent'], reverse=True)
        
        charts.append({
            "chart_id": "cross_report_improvement_ranked",
            "chart_type": "bar_chart",
            "title": f"Performance Improvement Across {len(improvement_data)} Demos",
            "priority": "high",
            "description": "Ranked comparison of performance improvement percentages",
            "chart_data": {
                "labels": [f"Report {data['report_number']}: {data['product']}" for data in improvement_data],
                "datasets": [{
                    "label": "Improvement %",
                    "data": [data["improvement_percent"] for data in improvement_data],
                    "backgroundColor": MultiReportHandler._get_improvement_colors(improvement_data),
                    "borderColor": MultiReportHandler._get_improvement_colors(improvement_data),
                    "borderWidth": 1
                }]
            }
        })
        
        return charts

    @staticmethod
    def _get_improvement_colors(improvement_data: List[Dict]) -> List[str]:
        """Get colors based on improvement percentage"""
        colors = []
        for data in improvement_data:
            improvement = data["improvement_percent"]
            if improvement >= 25:
                colors.append("#27ae60")
            elif improvement >= 15:
                colors.append("#f39c12")
            else:
                colors.append("#e74c3c")
        return colors

    @staticmethod
    def _get_category_colors(categories: Dict) -> List[str]:
        """Get consistent colors for categories"""
        color_palette = ["#36a2eb", "#ff6384", "#4caf50", "#ffeb3b", "#9c27b0", "#ff9800"]
        return [color_palette[i % len(color_palette)] for i in range(len(categories))]