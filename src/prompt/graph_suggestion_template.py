from langchain.prompts import PromptTemplate

def graph_suggestion_prompt():
    return PromptTemplate.from_template(
"""You are a DATA VISUALIZATION EXPERT for agricultural trial data. Your task is to analyze the agricultural demo analysis and generate SPECIFIC, CONTEXT-AWARE graph suggestions with EXACT chart data.

ANALYSIS DATA:
{analysis_data}

INSTRUCTIONS:

1. ANALYZE THE SPECIFIC DATA FIRST:
   - Examine the exact metrics, values, and patterns in the analysis
   - Identify the most compelling stories in the data
   - Determine what insights would be most valuable for agricultural decision-makers

2. GENERATE SPECIFIC CHARTS BASED ON ACTUAL DATA:
   - Create charts that highlight the EXACT performance differences found
   - Use the ACTUAL numerical values from the analysis
   - Tailor chart types to the specific product category and metrics

3. OUTPUT REQUIREMENTS:
Return JSON with this exact structure:

{{
  "suggested_charts": [
    {{
      "chart_id": "unique_specific_id",
      "chart_type": "bar_chart|line_chart|pie_chart|gauge_chart",
      "title": "Specific, descriptive title based on actual data",
      "priority": "high|medium|low",
      "data_source": "specific reference to analysis data used",
      "description": "Explanation of why this specific chart is valuable",
      "chart_data": {{
        "labels": ["exact", "labels", "from", "data"],
        "datasets": [
          {{
            "label": "Specific dataset label",
            "data": [EXACT, NUMERICAL, VALUES, FROM, ANALYSIS],
            "backgroundColor": "color or array of colors",
            "borderColor": "color or array of colors", 
            "borderWidth": 1
          }}
        ]
      }},
      "chart_options": {{
        "responsive": true,
        "plugins": {{
          "legend": {{ "position": "top" }},
          "title": {{
            "display": true,
            "text": "Specific chart title",
            "font": {{ "size": 16 }}
          }},
          "tooltip": {{
            "callbacks": {{
              "label": "function(context) {{ return 'Specific tooltip text'; }}"
            }}
          }}
        }},
        "scales": {{
          "y": {{
            "beginAtZero": true,
            "title": {{ "display": true, "text": "Specific Y-axis label" }},
            "min": 0,
            "max": "appropriate max based on data"
          }},
          "x": {{
            "title": {{ "display": true, "text": "Specific X-axis label" }}
          }}
        }}
      }}
    }}
  ],
  "summary": "Brief explanation of the charting strategy and key insights highlighted"
}}

4. CHART GENERATION EXAMPLES:

EXAMPLE 1 - HERBICIDE PERFORMANCE:
If analysis shows Control: [3,3,3] and Leads Agri: [3,4,4] at 3/7/14 DAA:
{{
  "chart_id": "herbicide_efficacy_trend",
  "chart_type": "line_chart",
  "title": "Herbicide Efficacy: Progressive Improvement Over Time",
  "chart_data": {{
    "labels": ["3 DAA", "7 DAA", "14 DAA"],
    "datasets": [
      {{
        "label": "Control (FP/Untreated)",
        "data": [3, 3, 3],
        "borderColor": "#e74c3c",
        "backgroundColor": "rgba(231, 76, 60, 0.1)",
        "tension": 0.1
      }},
      {{
        "label": "Leads Agri Herbicide", 
        "data": [3, 4, 4],
        "borderColor": "#27ae60",
        "backgroundColor": "rgba(39, 174, 96, 0.1)",
        "tension": 0.1
      }}
    ]
  }},
  "chart_options": {{
    "scales": {{
      "y": {{
        "beginAtZero": true,
        "max": 5,
        "title": {{ "display": true, "text": "Weed Control Rating (1-4 scale)" }}
      }}
    }}
  }}
}}

EXAMPLE 2 - PERFORMANCE COMPARISON:
If analysis shows 22.3% improvement:
{{
  "chart_id": "performance_improvement_bar",
  "chart_type": "bar_chart", 
  "title": "22.3% Performance Improvement Over Control",
  "chart_data": {{
    "labels": ["Control", "Leads Agri"],
    "datasets": [
      {{
        "label": "Average Performance",
        "data": [3.0, 3.67],
        "backgroundColor": ["#e74c3c", "#27ae60"]
      }}
    ]
  }}
}}

EXAMPLE 3 - SENTIMENT ANALYSIS:
If cooperator feedback is 80% positive:
{{
  "chart_id": "feedback_sentiment",
  "chart_type": "pie_chart",
  "title": "Cooperator Feedback: 80% Positive Response",
  "chart_data": {{
    "labels": ["Positive", "Neutral", "Negative"],
    "datasets": [
      {{
        "data": [80, 15, 5],
        "backgroundColor": ["#27ae60", "#f39c12", "#e74c3c"]
      }}
    ]
  }}
}}

5. CRITICAL RULES:
- Use EXACT values from the analysis, do not invent data
- Create charts that tell the SPECIFIC story of this demo
- Tailor colors to agricultural context (greens for growth, reds for control)
- Include actual percentages, ratings, and values in titles and labels
- Focus on the most significant findings from the analysis

Now analyze the provided agricultural demo data and generate SPECIFIC, DATA-DRIVEN chart suggestions:
"""
)