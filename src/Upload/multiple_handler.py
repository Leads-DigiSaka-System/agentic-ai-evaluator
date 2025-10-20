import os
import tempfile
import re
from typing import List, Dict, Any
from src.workflow.state import ProcessingState
from src.workflow.graph import processing_workflow
from src.Upload.form_extractor import extract_pdf_with_gemini, extract_pdf_metadata
from src.database.insert_analysis import analysis_storage 
class MultiReportHandler:
    """Handler for processing PDFs with multiple reports including graph suggestions"""
    
    @staticmethod
    async def process_multi_report_pdf(file_content: bytes, original_filename: str) -> Dict[str, Any]:
        """
        Process a PDF that may contain multiple reports
        """
        tmp_path = None
        try:
            # Save uploaded PDF to temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                tmp_file.write(file_content)
                tmp_path = tmp_file.name

            # Extract the entire PDF to markdown (with multiple reports)
            print("🚀 Extracting PDF with multiple reports...")
            extracted_markdown = extract_pdf_with_gemini(tmp_path)
            if not extracted_markdown:
                raise Exception("Failed to extract content from PDF")

            # Extract metadata for the entire PDF
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
        """
        # Use the unique separator for splitting
        reports_markdown = MultiReportHandler._split_reports_intelligently(extracted_markdown)

        print(f"📄 Found {len(reports_markdown)} reports in PDF")

        # CRITICAL FIX: Handle single vs multiple reports differently
        if len(reports_markdown) == 1:
            # For SINGLE REPORT, use simpler processing without pre-extracted markdown
            print("📋 Processing as SINGLE REPORT (letting workflow handle extraction)")
            report_response = await MultiReportHandler._process_single_report_direct(
                tmp_path, file_content, original_filename, pdf_metadata
            )
            
            result = {
                "status": "success",
                "total_reports": 1,
                "reports": [report_response],
                "cross_report_analysis": {"cross_report_suggestions": []}  # No cross-report for single
            }
            
            # ✅ STORE ANALYSIS RESULTS
            storage_success = analysis_storage.insert_multi_report_response(result)
            result["analysis_storage_status"] = "success" if storage_success else "failed"
            print(f"📊 Analysis storage: {result['analysis_storage_status']}")
            
            return result
        
        # For MULTIPLE REPORTS, use the pre-extracted markdown approach
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
        
        # ✅ STORE ANALYSIS RESULTS
        storage_success = analysis_storage.insert_multi_report_response(result)
        result["analysis_storage_status"] = "success" if storage_success else "failed"
        print(f"📊 Analysis storage: {result['analysis_storage_status']}")
        
        return result

    @staticmethod
    async def _process_single_report_direct(tmp_path: str, file_content: bytes, 
                                           original_filename: str, pdf_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a SINGLE report PDF by letting the workflow handle extraction
        This fixes the issue where single reports weren't being analyzed correctly
        """
        try:
            print("📄 Processing SINGLE REPORT with full workflow...")

            # Initialize state WITHOUT pre-extracted markdown
            # Let the workflow extract it properly
            initial_state: ProcessingState = {
                "file_path": tmp_path,
                "file_name": original_filename,
                "file_content": file_content,
                "extracted_markdown": None,  # CRITICAL: Let workflow extract this
                "form_type": None,
                "chunks": [],
                "analysis_result": None,
                "graph_suggestions": None,
                "form_id": "",
                "metadata": {},  # Will be populated by extraction node
                "insertion_date": "",
                "current_step": "start",
                "errors": []
            }

            # Execute the workflow (extraction -> analysis -> graphs -> chunking -> storage)
            final_state = processing_workflow.invoke(initial_state)

            # Build response
            report_response = {
                "report_number": 1,
                "file_name": original_filename,
                "form_id": final_state.get("form_id", ""),
                "form_type": final_state.get("form_type", ""),
                "extracted_content": final_state.get("extracted_markdown", ""),
                "analysis": final_state.get("analysis_result", {}),
                "graph_suggestions": final_state.get("graph_suggestions", {}),
                "processing_metrics": {
                    "chunk_count": len(final_state.get("chunks", [])),
                    "processing_steps": final_state.get("current_step", ""),
                    "insertion_date": final_state.get("insertion_date", "")
                },
                "errors": final_state.get("errors", [])
            }

            if final_state["errors"]:
                print(f"⚠️ Single report completed with errors: {final_state['errors']}")
            else:
                chart_count = len(final_state.get("graph_suggestions", {}).get("suggested_charts", []))
                print(f"✅ Single report processed successfully with {chart_count} chart suggestions")

            return report_response

        except Exception as e:
            print(f"❌ Failed to process single report: {str(e)}")
            import traceback
            traceback.print_exc()
            return {
                "report_number": 1,
                "file_name": original_filename,
                "form_id": "",
                "form_type": "",
                "extracted_content": "",
                "analysis": {},
                "graph_suggestions": {},
                "processing_metrics": {},
                "errors": [f"Single report processing failed: {str(e)}"]
            }

    @staticmethod
    def _split_reports_intelligently(markdown_content: str) -> List[str]:
        """
        Intelligently split markdown into individual reports
        """
        # First, try splitting by the unique separator
        unique_separator = "### REPORT_END ###"
        if unique_separator in markdown_content:
            reports = markdown_content.split(unique_separator)
            reports = [report.strip() for report in reports if report.strip()]
            if len(reports) > 1:
                print(f"📑 Using unique separator, found {len(reports)} reports")
                return reports

        # If no unique separator found, check for multiple # headings (potential reports)
        headings = re.findall(r'^#\s+.+$', markdown_content, re.MULTILINE)
        if len(headings) > 1:
            print(f"📑 Found {len(headings)} potential reports by heading detection")
            # Split by main headings (# )
            reports = re.split(r'^(?=#\s+)', markdown_content, flags=re.MULTILINE)
            reports = [report.strip() for report in reports if report.strip() and report.startswith('#')]
            if len(reports) > 1:
                return reports

        # If all else fails, treat as single report
        print("📋 No clear report separators found, treating as SINGLE REPORT")
        return [markdown_content]

    @staticmethod
    async def _process_single_report(report_md: str, file_content: bytes, original_filename: str,
                                   tmp_path: str, pdf_metadata: Dict[str, Any], 
                                   report_index: int, total_reports: int) -> Dict[str, Any]:
        """
        Process a single report from a MULTI-REPORT PDF (with pre-extracted markdown)
        """
        try:
            print(f"📄 Processing report {report_index + 1}/{total_reports}...")

            # Initialize state for the workflow with pre-extracted markdown
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
                "errors": []
            }

            # Execute the workflow
            final_state = processing_workflow.invoke(initial_state)

            # Build response for this report
            report_response = {
                "report_number": report_index + 1,
                "file_name": original_filename,
                "form_id": final_state.get("form_id", ""),
                "form_type": final_state.get("form_type", ""),
                "extracted_content": final_state.get("extracted_markdown", ""),
                "analysis": final_state.get("analysis_result", {}),
                "graph_suggestions": final_state.get("graph_suggestions", {}),
                "processing_metrics": {
                    "chunk_count": len(final_state.get("chunks", [])),
                    "processing_steps": final_state.get("current_step", ""),
                    "insertion_date": final_state.get("insertion_date", "")
                },
                "errors": final_state.get("errors", [])
            }

            if final_state["errors"]:
                print(f"⚠️ Report {report_index + 1} completed with errors: {final_state['errors']}")
            else:
                chart_count = len(final_state.get("graph_suggestions", {}).get("suggested_charts", []))
                print(f"✅ Report {report_index + 1} processed successfully with {chart_count} chart suggestions")

            return report_response

        except Exception as e:
            print(f"❌ Failed to process report {report_index + 1}: {str(e)}")
            import traceback
            traceback.print_exc()
            return {
                "report_number": report_index + 1,
                "file_name": original_filename,
                "form_id": "",
                "form_type": "",
                "extracted_content": "",
                "analysis": {},
                "graph_suggestions": {},
                "processing_metrics": {},
                "errors": [f"Report processing failed: {str(e)}"]
            }

    @staticmethod
    def _generate_cross_report_suggestions(all_reports: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generate graph suggestions that compare multiple reports
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
                
                performance_data.append({
                    "report_number": report.get("report_number"),
                    "product": basic_info.get("product", "Unknown Product"),
                    "location": basic_info.get("location", "Unknown Location"),
                    "improvement_percent": calculated.get("improvement_percent", 0),
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
            print(f"⚠️ Failed to generate cross-report suggestions: {str(e)}")
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
        
        # Additional charts only for multiple product types...
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