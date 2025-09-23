from langchain.prompts import PromptTemplate

# Extractor Template
def formatting_template():
    return PromptTemplate.from_template(
"""Extract and format the document content into valid Markdown. 
Follow this exact structure strictly.

# [Document Title]

## Fields
- **Field Name**: Value
- **Field Name**: Value
- **Field Name**: Value

## [Table Name if applicable]
| Column 1 | Column 2 | Column 3 |
|----------|----------|----------|
| Data     | Data     | Data     |
| Data     | Data     | Data     |

## Notes
- Use "# Title" at the start
- Always use "##" for section headings
- Represent fields as bullet list with **bold field name**
- Represent all tables as valid Markdown tables
- Preserve order of appearance from the document
- If a field has no value, write "N/A"
- Keep one blank line between sections
- Do not add extra commentary, only structured Markdown
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

