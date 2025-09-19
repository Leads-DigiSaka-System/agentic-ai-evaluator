from langchain.prompts import PromptTemplate

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
