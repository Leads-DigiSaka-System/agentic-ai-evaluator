import os
import tempfile
import re
from typing import List, Dict, Any
from src.workflow.state import ProcessingState
from src.workflow.graph import processing_workflow
from src.Upload.form_extractor import extract_pdf_with_gemini, extract_pdf_metadata
from src.database.insert_analysis import analysis_storage 
from src.utils.clean_logger import get_clean_logger
# Import official Langfuse decorator - NO custom wrappers
try:
    from langfuse import observe  # Official Langfuse decorator only
    LANGFUSE_OBSERVE_AVAILABLE = True
except ImportError:
    # Fallback if langfuse not available
    def observe(*args, **kwargs):
        def decorator(func):
            return func
        return decorator
    LANGFUSE_OBSERVE_AVAILABLE = False 

logger = get_clean_logger(__name__)
class MultiReportHandler:
    """Handler for processing PDFs with multiple reports including graph suggestions"""
    #logger = get_clean_logger(__name__)
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
        #logger = get_clean_logger(__name__)
        tmp_path = None
        try:
            # ✅ FIX: Detect file type from original filename
            file_ext = original_filename.lower().split('.')[-1] if '.' in original_filename else 'pdf'
            suffix = f".{file_ext}"
            
            logger.file_upload(original_filename, len(file_content))
            
            # ✅ FIX: Save with correct extension
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix, mode='wb') as tmp_file:
                tmp_file.write(file_content)
                tmp_file.flush()  # Ensure written to disk
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
        # Note: Content validation still happens in workflow for each report
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
        
        # Analysis storage is now handled separately via API endpoint
        result["analysis_storage_status"] = "ready_for_approval"
        logger.storage_start("analysis storage", "ready for user approval")
        
        return result

    @observe(as_root=True, name="process_single_report_direct")
    @staticmethod
    async def _process_single_report_direct(tmp_path: str, file_content: bytes, 
                                           original_filename: str, pdf_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a SINGLE report PDF with FULL VALIDATION
        
        NEW BEHAVIOR:
        - Workflow now includes content validation step
        - Better error messages from validation
        - File format already validated during extraction
        
        Uses official Langfuse @observe() decorator for tracing
        """
        logger = get_clean_logger(__name__)
        
        try:
            logger.info("Processing SINGLE REPORT with full validation")
            
            # Detect file_type from metadata or filename extension
            file_type = pdf_metadata.get("file_type")
            if not file_type or file_type == "unknown":
                # Fallback: detect from filename extension
                file_ext = original_filename.lower().split('.')[-1] if '.' in original_filename else ''
                if file_ext == 'pdf':
                    file_type = "pdf"
                elif file_ext in ['png', 'jpg', 'jpeg']:
                    file_type = "image"
                else:
                    file_type = file_ext or "unknown"
            
            # @observe() decorator automatically:
            # - Creates root trace
            # - Captures function inputs/outputs
            # - Tracks execution time
            # - Handles errors
            # - Stores trace in OpenTelemetry context
            
            # Get trace_id from OpenTelemetry context (official way decorator stores it)
            # This is needed to link CallbackHandler for LLM generations
            trace_id = None
            try:
                from opentelemetry import trace as otel_trace
                span = otel_trace.get_current_span()
                if span and hasattr(span, 'context') and hasattr(span.context, 'trace_id'):
                    trace_id = format(span.context.trace_id, '032x')
                    logger.info(f"Langfuse trace ID: {trace_id}")
            except Exception as e:
                logger.debug(f"Could not get trace_id from OpenTelemetry context: {e}")

            # Initialize state WITHOUT pre-extracted markdown
            # Workflow will: extract → validate file → validate content → analyze
            initial_state: ProcessingState = {
                "file_path": tmp_path,
                "file_name": original_filename,
                "file_content": file_content,
                "extracted_markdown": None,  # Let workflow extract and validate
                "form_type": None,
                "chunks": [],
                "analysis_result": None,
                "graph_suggestions": None,
                "form_id": "",
                "metadata": {},
                "insertion_date": "",
                "current_step": "start",
                "errors": [],
                
                # Langfuse trace ID for observability
                "_langfuse_trace_id": trace_id,
                
                # Validation fields (populated by workflow)
                "file_validation": None,
                "is_valid_content": None,
                "content_validation": None
            }

            # Execute the workflow (now includes validation)
            final_state = processing_workflow.invoke(initial_state)

            # Build response with validation info (storage data prepared but not stored)
            report_response = {
                "report_number": 1,
                "file_name": original_filename,
                "form_id": "",  # Will be generated during storage approval
                "form_type": final_state.get("form_type", ""),
                "extracted_content": final_state.get("extracted_markdown", ""),
                "analysis": final_state.get("analysis_result", {}),
                "graph_suggestions": final_state.get("graph_suggestions", {}),
                "chunks": final_state.get("chunks", []),  # Include chunks for storage
                "processing_metrics": {
                    "chunk_count": len(final_state.get("chunks", [])),
                    "processing_steps": final_state.get("current_step", ""),
                    "workflow_completed": True,
                    "storage_ready": True
                },
                "errors": final_state.get("errors", []),
                
                # NEW: Include validation results in response
                "validation": {
                    "file_validation": final_state.get("file_validation"),
                    "content_validation": final_state.get("content_validation")
                },
                
                # NEW: Storage control info
                "storage_status": "ready_for_approval",
                "storage_message": "Analysis completed. Use /api/storage/preview to review and /api/storage/approve to store."
            }

            if final_state["errors"]:
                logger.processing_error(original_filename, f"Single report completed with errors: {final_state['errors']}")
            else:
                chart_count = len(final_state.get("graph_suggestions", {}).get("suggested_charts", []))
                logger.processing_success(original_filename, f"Single report processed successfully with {chart_count} chart suggestions")
                logger.storage_start("analysis storage", "ready for user approval")

            # End trace span and flush Langfuse events
            from src.utils.langfuse_helper import flush_langfuse
            trace_id = final_state.get("_langfuse_trace_id")
            if trace_id:
                logger.debug(f"Finalizing trace: {trace_id}")
            
            flush_langfuse()
            logger.info(f"✅ Workflow completed - trace available in Langfuse dashboard")

            return report_response

        except Exception as e:
            logger.processing_error(original_filename, f"Failed to process single report: {str(e)}")
            import traceback
            traceback.print_exc()
            
            # Flush Langfuse even on error to ensure trace is visible
            try:
                from src.utils.langfuse_helper import flush_langfuse
                flush_langfuse()
            except Exception as flush_err:
                logger.warning(f"Failed to flush Langfuse on error: {flush_err}")
            
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
        """
        Intelligently split markdown into individual reports
        UNCHANGED - Works as before
        """
        logger = get_clean_logger(__name__)
        
        # First, try splitting by the unique separator
        unique_separator = "### REPORT_END ###"
        if unique_separator in markdown_content:
            reports = markdown_content.split(unique_separator)
            reports = [report.strip() for report in reports if report.strip()]
            if len(reports) > 1:
                logger.info(f"Using unique separator, found {len(reports)} reports")
                return reports

        # If no unique separator found, check for multiple # headings
        headings = re.findall(r'^#\s+.+$', markdown_content, re.MULTILINE)
        if len(headings) > 1:
            logger.info(f"Found {len(headings)} potential reports by heading detection")
            reports = re.split(r'^(?=#\s+)', markdown_content, flags=re.MULTILINE)
            reports = [report.strip() for report in reports if report.strip() and report.startswith('#')]
            if len(reports) > 1:
                return reports

        # If all else fails, treat as single report
        logger.info("No clear report separators found, treating as SINGLE REPORT")
        return [markdown_content]

    @observe(as_root=True, name="process_single_report")
    @staticmethod
    async def _process_single_report(report_md: str, file_content: bytes, original_filename: str,
                                   tmp_path: str, pdf_metadata: Dict[str, Any], 
                                   report_index: int, total_reports: int) -> Dict[str, Any]:
        """
        Process a single report from a MULTI-REPORT PDF
        
        WORKS WITH VALIDATION:
        - Pre-extracted markdown provided
        - Content validation still runs in workflow
        - If content is invalid, workflow will error out gracefully
        
        Uses official Langfuse @observe() decorator for tracing
        """
        logger = get_clean_logger(__name__)
        
        try:
            logger.info(f"Processing report {report_index + 1}/{total_reports}")

            # Get trace_id from OpenTelemetry context (official way)
            trace_id = None
            try:
                from opentelemetry import trace as otel_trace
                span = otel_trace.get_current_span()
                if span and hasattr(span, 'context') and hasattr(span.context, 'trace_id'):
                    trace_id = format(span.context.trace_id, '032x')
                    logger.info(f"Langfuse trace ID for report {report_index + 1}: {trace_id}")
            except Exception as e:
                logger.debug(f"Could not get trace_id from OpenTelemetry context: {e}")
            
            # Detect file_type from metadata or filename extension
            file_type = pdf_metadata.get("file_type")
            if not file_type or file_type == "unknown":
                # Fallback: detect from filename extension
                file_ext = original_filename.lower().split('.')[-1] if '.' in original_filename else ''
                if file_ext == 'pdf':
                    file_type = "pdf"
                elif file_ext in ['png', 'jpg', 'jpeg']:
                    file_type = "image"
                else:
                    file_type = file_ext or "unknown"
            
            # @observe() decorator already created trace automatically
            # Trace is already created, just using trace_id for CallbackHandler linking

            # Initialize state with pre-extracted markdown
            # Workflow will: validate content → analyze → graphs → chunk → store
            initial_state: ProcessingState = {
                "file_path": tmp_path,
                "file_name": f"{original_filename}_report_{report_index + 1}",
                "file_content": file_content,
                "extracted_markdown": report_md,  # Pre-extracted for multi-report
                "form_type": None,
                "chunks": [],
                "analysis_result": None,
                "graph_suggestions": None,
                "form_id": "",
                "metadata": pdf_metadata,
                "insertion_date": "",
                "current_step": "start",
                "errors": [],
                
                # Langfuse trace ID for observability
                "_langfuse_trace_id": trace_id,
                
                # Validation fields (content validation will still run)
                "file_validation": {"is_valid": True, "validation_skipped": True},
                "is_valid_content": None,
                "content_validation": None
            }

            # Execute the workflow
            final_state = processing_workflow.invoke(initial_state)

            # Build response (storage data prepared but not stored)
            report_response = {
                "report_number": report_index + 1,
                "file_name": original_filename,
                "form_id": "",  # Will be generated during storage approval
                "form_type": final_state.get("form_type", ""),
                "extracted_content": final_state.get("extracted_markdown", ""),
                "analysis": final_state.get("analysis_result", {}),
                "graph_suggestions": final_state.get("graph_suggestions", {}),
                "chunks": final_state.get("chunks", []),  # Include chunks for storage
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

            if final_state["errors"]:
                logger.processing_error(f"Report {report_index + 1}", f"Report completed with errors: {final_state['errors']}")
            else:
                chart_count = len(final_state.get("graph_suggestions", {}).get("suggested_charts", []))
                logger.processing_success(f"Report {report_index + 1}", f"Report processed successfully with {chart_count} chart suggestions")
                logger.storage_start("analysis storage", "ready for user approval")

            # End trace span and flush Langfuse events
            from src.utils.langfuse_helper import flush_langfuse
            trace_id = final_state.get("_langfuse_trace_id")
            if trace_id:
                logger.debug(f"Finalizing trace for report {report_index + 1}: {trace_id}")
            
            flush_langfuse()
            logger.info(f"✅ Report {report_index + 1} completed - trace available in Langfuse dashboard")

            return report_response

        except Exception as e:
            logger.processing_error(f"Report {report_index + 1}", f"Failed to process report: {str(e)}")
            import traceback
            traceback.print_exc()
            
            # Flush Langfuse even on error to ensure trace is visible
            try:
                from src.utils.langfuse_helper import flush_langfuse
                flush_langfuse()
            except Exception as flush_err:
                logger.warning(f"Failed to flush Langfuse on error: {flush_err}")
            
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
        """
        Generate graph suggestions that compare multiple reports
        UNCHANGED - Works as before
        """
        try:
            if len(all_reports) <= 1:
                return {"cross_report_suggestions": []}
            
            # Collect performance data from all reports
            performance_data = []
            product_types = set()
            
            for report in all_reports:
                analysis = report.get("analysis", {})
                basic_info = analysis.get("basic_info", {})
                perf_analysis = analysis.get("performance_analysis", {})
                calculated = perf_analysis.get("calculated_metrics", {})
                
                # Prefer 'relative_improvement_percent' (current schema), fallback to 'improvement_percent'
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
            
            # Generate cross-report chart suggestions
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
        """Intelligently create cross-report charts based on data patterns"""
        charts = []
        
        # Chart 1: Improvement comparison (always relevant)
        improvement_data = sorted(performance_data, key=lambda x: x['improvement_percent'], reverse=True)
        
        charts.append({
            "chart_id": "cross_report_improvement_ranked",
            "chart_type": "bar_chart",
            "title": f"Performance Improvement Across {len(improvement_data)} Demos",
            "priority": "high",
            "description": "Ranked comparison of performance improvement percentages across all demo reports",
            "chart_data": {
                "labels": [f"Report {data['report_number']}: {data['product']}" for data in improvement_data],
                "datasets": [{
                    "label": "Improvement %",
                    "data": [data["improvement_percent"] for data in improvement_data],
                    "backgroundColor": MultiReportHandler._get_improvement_colors(improvement_data),
                    "borderColor": MultiReportHandler._get_improvement_colors(improvement_data),
                    "borderWidth": 1
                }]
            },
            "chart_options": {
                "responsive": True,
                "plugins": {
                    "legend": {"display": False},
                    "title": {
                        "display": True,
                        "text": f"Top Performer: {improvement_data[0]['product']} ({improvement_data[0]['improvement_percent']}% improvement)"
                    }
                },
                "scales": {
                    "y": {
                        "beginAtZero": True,
                        "title": {"display": True, "text": "Improvement %"}
                    }
                }
            }
        })
        
        # Additional charts only for multiple product types
        if len(product_types) > 1:
            categories = {}
            for data in performance_data:
                category = data["form_type"]
                categories[category] = categories.get(category, 0) + 1
            
            charts.append({
                "chart_id": "product_category_distribution",
                "chart_type": "pie_chart",
                "title": f"Product Category Distribution ({len(performance_data)} Demos)",
                "priority": "medium",
                "description": "Breakdown of demo types by product category",
                "chart_data": {
                    "labels": list(categories.keys()),
                    "datasets": [{
                        "data": list(categories.values()),
                        "backgroundColor": MultiReportHandler._get_category_colors(categories),
                        "borderColor": MultiReportHandler._get_category_colors(categories),
                        "borderWidth": 2
                    }]
                },
                "chart_options": {
                    "responsive": True,
                    "plugins": {
                        "legend": {"position": "right"},
                        "title": {
                            "display": True,
                            "text": "Demo Distribution by Product Type"
                        }
                    }
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
                colors.append("#27ae60")  # Green
            elif improvement >= 15:
                colors.append("#f39c12")  # Orange
            else:
                colors.append("#e74c3c")  # Red
        return colors

    @staticmethod
    def _get_category_colors(categories: Dict) -> List[str]:
        """Get consistent colors for categories"""
        color_palette = ["#36a2eb", "#ff6384", "#4caf50", "#ffeb3b", "#9c27b0", "#ff9800"]
        return [color_palette[i % len(color_palette)] for i in range(len(categories))]