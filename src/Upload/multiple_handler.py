import os
import tempfile
import re
from typing import List, Dict, Any
from src.workflow.state import ProcessingState
from src.workflow.graph import processing_workflow
from src.Upload.form_extractor import extract_pdf_with_gemini, extract_pdf_metadata

class MultiReportHandler:
    """Handler for processing PDFs with multiple reports"""
    
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
            return await MultiReportHandler._process_reports(
                extracted_markdown, file_content, original_filename, tmp_path, pdf_metadata
            )

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

        # If we found only one report, double-check if it's really multiple
        if len(reports_markdown) == 1:
            reports_markdown = MultiReportHandler._fallback_single_report_check(extracted_markdown)

        # Process each report
        all_reports_response = []
        for i, report_md in enumerate(reports_markdown):
            report_response = await MultiReportHandler._process_single_report(
                report_md, file_content, original_filename, tmp_path, pdf_metadata, i, len(reports_markdown)
            )
            all_reports_response.append(report_response)

        return {
            "status": "success",
            "total_reports": len(all_reports_response),
            "reports": all_reports_response
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
                print(f"🔍 Using unique separator, found {len(reports)} reports")
                return reports

        # If no unique separator found, check for multiple # headings (potential reports)
        headings = re.findall(r'^#\s+.+$', markdown_content, re.MULTILINE)
        if len(headings) > 1:
            print(f"🔍 Found {len(headings)} potential reports by heading detection")
            # Split by main headings (# )
            reports = re.split(r'^(?=#\s+)', markdown_content, flags=re.MULTILINE)
            reports = [report.strip() for report in reports if report.strip() and report.startswith('#')]
            if len(reports) > 1:
                return reports

        # If all else fails, treat as single report
        print("🔍 No clear report separators found, treating as single report")
        return [markdown_content]

    @staticmethod
    def _fallback_single_report_check(markdown_content: str) -> List[str]:
        """
        Additional checks for single reports that might actually be multiple
        """
        # Check for common patterns that indicate multiple reports
        patterns = [
            r'Name of Cooperator',  # Common field in demo forms
            r'Leads Agri Product',
            r'Farm Location',
            r'% Control',
            r'Remarks/Cooperator Feedback'
        ]
        
        # Count occurrences of these patterns
        pattern_count = sum(len(re.findall(pattern, markdown_content)) for pattern in patterns)
        
        # If we see these patterns multiple times, it might be multiple reports
        if pattern_count > 3:  # Arbitrary threshold, adjust based on testing
            print(f"⚠️  Detected {pattern_count} repeated patterns, might be multiple reports")
            # Try splitting by double newlines as last resort
            sections = re.split(r'\n\s*\n', markdown_content)
            significant_sections = [section.strip() for section in sections 
                                  if section.strip() and len(section.strip()) > 100]
            if len(significant_sections) > 1:
                print(f"🔍 Found {len(significant_sections)} significant sections")
                return significant_sections
        
        return [markdown_content]

    @staticmethod
    async def _process_single_report(report_md: str, file_content: bytes, original_filename: str,
                                   tmp_path: str, pdf_metadata: Dict[str, Any], 
                                   report_index: int, total_reports: int) -> Dict[str, Any]:
        """
        Process a single report from the multi-report PDF
        """
        try:
            print(f"🔄 Processing report {report_index + 1}/{total_reports}...")

            # Initialize state for the workflow with pre-extracted markdown
            initial_state: ProcessingState = {
                "file_path": tmp_path,
                "file_name": f"{original_filename}_report_{report_index + 1}",
                "file_content": file_content,
                "extracted_markdown": report_md,
                "form_type": None,
                "chunks": [],
                "analysis_result": None,
                "form_id": "",
                "metadata": pdf_metadata,
                "insertion_date": "",
                "current_step": "start",
                "errors": []
            }

            # Execute the workflow
            final_state = processing_workflow.invoke(initial_state)

            # Check for errors in this report
            if final_state["errors"]:
                print(f"❌ Report {report_index + 1} completed with errors: {final_state['errors']}")
            else:
                print(f"✅ Report {report_index + 1} processed successfully")

            # Build response for this report
            return {
                "report_number": report_index + 1,
                "file_name": original_filename,
                "form_id": final_state.get("form_id", ""),
                "form_type": final_state.get("form_type", ""),
                "extracted_content": final_state.get("extracted_markdown", ""),
                "analysis": final_state.get("analysis_result", {}),
                "processing_metrics": {
                    "chunk_count": len(final_state.get("chunks", [])),
                    "processing_steps": final_state.get("current_step", ""),
                    "insertion_date": final_state.get("insertion_date", "")
                },
                "errors": final_state.get("errors", [])
            }

        except Exception as e:
            # Catch error for this specific report and continue
            print(f"❌ Failed to process report {report_index + 1}: {str(e)}")
            return {
                "report_number": report_index + 1,
                "file_name": original_filename,
                "form_id": "",
                "form_type": "",
                "extracted_content": "",
                "analysis": {},
                "processing_metrics": {},
                "errors": [f"Report processing failed: {str(e)}"]
            }