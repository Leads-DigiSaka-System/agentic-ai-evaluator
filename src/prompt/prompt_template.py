from langchain.prompts import PromptTemplate

# Extractor Template
def formatting_template():
    return PromptTemplate.from_template(
"""This PDF may contain MULTIPLE SEPARATE REPORTS. Each page or section is a DISTINCT report.

EXTRACTION RULES FOR MULTIPLE REPORTS:
1. PROCESS EACH REPORT AS A SEPARATE ENTITY
2. For each report, create a SEPARATE Markdown section
3. Use exactly '### REPORT_END ###' as a separator between reports
4. Each report must follow the structure below

FOR EACH INDIVIDUAL REPORT:

# [Document Title - for THIS report only]

## Fields
- **Field Name**: Value (from this report only)
- **Field Name**: Value

## [Table Name if applicable]
| Column 1 | Column 2 | Column 3 |
|----------|----------|----------|
| Data     | Data     | Data     |

## Notes
- Extract each report COMPLETELY SEPARATELY
- Do not mix data between pages/reports
- If a field has no value, write "N/A"
- Use exactly '### REPORT_END ###' to separate each complete report

If there is only one report, then do not use any separators.

CRITICAL: Only use '### REPORT_END ###' between complete reports, never within a report.
"""
)



# For Synthesizer 
def synthesizer_template():
    return PromptTemplate.from_template(
"""You are a data synthesizer for agricultural trial data. 
Synthesize information from multiple retrieved document chunks into a coherent summary.

### Context
You are working with retrieved chunks from a vector database search. Each chunk contains partial information about agricultural trials.

### Instructions
1. **Analyze Retrieved Context**: Review all provided document chunks and identify key themes
2. **Merge Related Information**: Combine information about the same trials, products, or locations
3. **Handle Conflicts**: If chunks contain conflicting information, note the variations
4. **Preserve Key Data**: Keep all trial tables, results, and quantitative data intact
5. **Structure Output**: Organize by trial type, product, or chronological order

### Retrieved Context:
{retrieved_context}

### Query Focus:
{user_query}

### Output Format:
# Synthesized Agricultural Trial Summary

## Overview
[Brief summary of main findings from all retrieved documents]

## Trial Results
[Preserve and merge all trial tables from retrieved chunks]

## Key Observations
- Product: [Synthesized information]
- Efficacy: [Combined results]
- Conditions: [Merged trial conditions]
- Recommendations: [Based on multiple sources]

## Data Sources
- Retrieved from {chunk_count} document chunks
- Confidence: [Based on similarity scores and chunk quality]
"""
)

#For Evaluator Meticts and Insight Summary of the Output

def content_validation_template():
    """
    Optimized LLM validator - checks if content is a product demo/trial report
    Token-efficient version with same accuracy
    """
    return PromptTemplate.from_template(
"""Validate if this is a PRODUCT DEMO or TRIAL REPORT.

VALID indicators: product names, trial data, performance metrics, comparison data, location/cooperator, crop/pest info
INVALID: invoices, letters, brochures (no data), blank/garbled text, non-agricultural

CONTENT:
{extracted_content}

Return JSON:
{{
  "is_valid_demo": true/false,
  "confidence": 0.0-1.0,
  "content_type": "product_demo"|"trial_report"|"invoice"|"letter"|"blank"|"unknown",
  "reasoning": "brief explanation",
  "detected_elements": {{"has_product_info": bool, "has_trial_data": bool, "has_numeric_results": bool, "has_location_info": bool}},
  "feedback": "user-friendly message"
}}

Examples:
Valid demo: {{"is_valid_demo": true, "confidence": 0.95, "content_type": "product_demo", "reasoning": "Contains trial data with control/treatment comparison", "detected_elements": {{"has_product_info": true, "has_trial_data": true, "has_numeric_results": true, "has_location_info": true}}, "feedback": "Valid product demo detected. Proceeding."}}

Invalid invoice: {{"is_valid_demo": false, "confidence": 0.90, "content_type": "invoice", "reasoning": "Financial document, no trial data", "detected_elements": {{"has_product_info": false, "has_trial_data": false, "has_numeric_results": true, "has_location_info": false}}, "feedback": "This is an invoice. Upload a trial report with product performance data."}}

Return only valid JSON, no extra text."""
)
