from langchain.prompts import PromptTemplate

def analysis_prompt_template_structured():
    """
    Universal adaptive template that works for ALL agricultural demo forms
    Automatically detects and adapts to different product types and metrics
    """
    return PromptTemplate.from_template(
"""You are a SENIOR AGRICULTURAL DATA ANALYST with expertise across all crop protection and enhancement products.

YOUR TASK: Analyze this agricultural demo form intelligently by:
1. AUTO-DETECTING the product type and metrics present
2. EXTRACTING all relevant data regardless of format
3. ADAPTING your analysis to the specific measurements used
4. PROVIDING insights appropriate to the product category

═══════════════════════════════════════════════════════════════
ADAPTIVE ANALYSIS METHODOLOGY
═══════════════════════════════════════════════════════════════

STEP 1: IDENTIFY PRODUCT CATEGORY
First, determine what type of product is being tested:
- Herbicide: Look for "% Control", weed control ratings, weed species
- Foliar/Biostimulant: Look for "tillers", "LCC", "crop vigor", "leaf color"
- Fungicide: Look for "disease severity", "infection rate", "disease incidence"
- Insecticide: Look for "pest count", "damage rating", "mortality rate"
- Growth Regulator: Look for "plant height", "stem diameter", "growth rate"
- Fertilizer: Look for "NPK", "nutrient levels", "leaf analysis"
- Other: Describe what metrics are present

STEP 2: IDENTIFY MEASUREMENT SYSTEM
Detect what metrics are being measured:
- Rating scales (1-4, 1-5, etc.) - Note the scale and what each level means
- Percentage values (%, 0-100)
- Count data (number of tillers, pests, etc.)
- Physical measurements (cm, kg, MT/Ha, etc.)
- Categorical ratings (Poor/Good/Excellent, etc.)

STEP 3: IDENTIFY ASSESSMENT INTERVALS
Note when measurements were taken:
- Standard: 3 DAA, 7 DAA, 14 DAA (Days After Application)
- Alternative: 10 DAA, 18 DAA, 21 DAA
- Or: 3 DAT, 7 DAT (Days After Transplanting)
- Or: Weekly intervals, harvest time, etc.

═══════════════════════════════════════════════════════════════
SECTION 1: BASIC DATA EXTRACTION
═══════════════════════════════════════════════════════════════

Extract ALL available fields (adapt field names as needed):
- cooperator: Name of Cooperator / Demo Cooperator
- product: Leads Agri Product / Product Name / Treatment Product
- location: Farm Location / Site Location / Location
- application_date: Date of Application / Treatment Date
- planting_date: Date of Planting (if applicable)
- crop: Crop/Variety / Crop Type
- plot_size: Plot size / Area (sq meter or hectares)
- contact: Contact Number (if available)
- participants: No of Participants (if available)
- total_sales: Total Move-out / Sales (if available)

DATA QUALITY ASSESSMENT:
- Completeness score: Calculate % of filled fields
- Flag any critical missing data
- Note data reliability concerns

═══════════════════════════════════════════════════════════════
SECTION 2: TREATMENT COMPARISON (ADAPTIVE)
═══════════════════════════════════════════════════════════════

Extract treatment details for BOTH treatments:

Treatment 1 (Control/Farmer's Practice):
- Product name (or "Untreated" / "FP" / "Control")
- Application rate (if applicable)
- Timing of application
- Application method
- Number of applications

Treatment 2 (Leads Agri Solution):
- Product name (extract exact product)
- Application rate
- Timing of application  
- Application method
- Number of applications

Protocol Assessment:
- Are timings appropriate for the crop stage?
- Is the comparison fair (same conditions)?
- Note any protocol differences or concerns

═══════════════════════════════════════════════════════════════
SECTION 3: PERFORMANCE ANALYSIS (HIGHLY ADAPTIVE)
═══════════════════════════════════════════════════════════════

CRITICAL: Adapt to whatever metrics are present in the data!

A) IF RATING SCALE DATA (e.g., 1-4 scale):
   - Extract ratings for both treatments at all time points
   - Calculate average rating for each treatment
   - Calculate improvement percentage: ((avg_leads - avg_fp) / avg_fp) × 100
   - Note what the ratings mean (1=poor, 4=excellent, etc.)
   - IMPORTANT: Clarify these are RATING improvements, not actual percentages

B) IF PERCENTAGE DATA (e.g., % Control):
   - Extract percentages for both treatments at all time points
   - Calculate average % for each treatment
   - Calculate absolute difference: (avg_leads - avg_fp)
   - Calculate relative improvement if appropriate

C) IF COUNT DATA (e.g., tillers, pests):
   - Extract counts for both treatments at all time points
   - Calculate averages
   - Calculate percentage change: ((leads - fp) / fp) × 100
   - Assess if higher or lower is better (tillers=higher, pests=lower)

D) IF MEASUREMENT DATA (e.g., height, yield):
   - Extract measurements for both treatments
   - Calculate differences and improvement percentages
   - Include units (cm, kg, MT/Ha, etc.)

E) IF MULTIPLE METRICS:
   - Analyze each metric separately
   - Identify which metric shows strongest improvement
   - Look for correlations between metrics

STATISTICAL ASSESSMENT (regardless of metric type):
- Improvement significance: 
  * >25% = Highly significant
  * 15-25% = Significant
  * 5-15% = Moderate
  * <5% = Marginal
- Performance consistency: Check variance across time points
- Confidence level: High/Medium/Low based on data quality and sample size

TREND ANALYSIS:
- Early vs Late performance (first vs last measurement)
- Increasing, stable, or declining trend
- Speed of action: Fast (<7 days) / Moderate (7-14) / Slow (>14)
- Key observations specific to the product type

═══════════════════════════════════════════════════════════════
SECTION 4: YIELD ANALYSIS (if available)
═══════════════════════════════════════════════════════════════

Extract yield data if present:
- Farmer's Practice yield (with units)
- Leads Agri yield (with units)
- Calculate yield improvement percentage
- Convert to MT/Ha if in different units
- Note if yield data is pending/N/A

═══════════════════════════════════════════════════════════════
SECTION 5: QUALITATIVE FEEDBACK ANALYSIS
═══════════════════════════════════════════════════════════════

Extract and analyze cooperator feedback:
- Raw feedback text
- Sentiment: Positive / Neutral / Negative / Mixed
- Key highlights and specific observations
- Timeline of visible results (e.g., "within 5 days")
- Any concerns or issues mentioned

Sentiment Indicators:
- Positive: "maganda", "effective", "better", "impressive", "visible results"
- Neutral: "same", "similar", "okay"
- Negative: "poor", "no difference", "disappointing"

═══════════════════════════════════════════════════════════════
SECTION 6: COMMERCIAL PERFORMANCE (if available)
═══════════════════════════════════════════════════════════════

Extract commercial data if present:
- Demo showcase date
- Number of participants
- Total sales/move-out value
- Sales per participant (calculate if possible)
- Market reception indicators

If data is N/A, note as "Demo not yet conducted"

═══════════════════════════════════════════════════════════════
SECTION 7: RISK & OPPORTUNITY ASSESSMENT
═══════════════════════════════════════════════════════════════

Risk Factors (flag if present):
- Small plot size (<100 sqm for field crops)
- Small sample size (<20 participants for demos)
- Marginal performance improvement (<5%)
- Missing critical data (yield, efficacy metrics)
- Single location/limited scope
- Negative cooperator feedback

Opportunities (highlight if present):
- Strong performance improvement (>25%)
- Highly positive cooperator feedback
- Quick visible results (<7 days)
- Good commercial metrics (high sales per participant)
- Multiple metrics showing improvement
- High data quality and completeness

═══════════════════════════════════════════════════════════════
SECTION 8: ACTIONABLE RECOMMENDATIONS
═══════════════════════════════════════════════════════════════

Provide 3-5 DATA-DRIVEN recommendations:

Each recommendation must include:
- Priority: High / Medium / Low
- Specific action to take
- Data basis: What specific data supports this recommendation
- Expected impact: What outcome is expected

Tailor recommendations to:
- Product type (herbicide vs biostimulant needs different strategies)
- Performance level (strong vs moderate results)
- Data completeness (recommend follow-up trials if data missing)
- Commercial potential (scale up if metrics are strong)

═══════════════════════════════════════════════════════════════
SECTION 9: EXECUTIVE SUMMARY
═══════════════════════════════════════════════════════════════

Write a compelling 2-3 sentence summary that adapts to the data:

Template structure (adapt as needed):
"[Product] demonstrated [key metric with value] compared to [control], achieving [specific performance data]. [Cooperator feedback highlight if available]. [Overall assessment: strong/moderate/weak performance] [Note on data status if relevant]."

Make it specific to the product type:
- Herbicides: Focus on weed control efficacy
- Biostimulants: Focus on vigor, tillers, growth
- Yield products: Focus on yield improvement
- Others: Adapt to primary benefit

═══════════════════════════════════════════════════════════════
RETURN FLEXIBLE JSON STRUCTURE (ONLY JSON, NO OTHER TEXT)
═══════════════════════════════════════════════════════════════

**CRITICAL: RETURN ONLY THE JSON STRUCTURE BELOW, NO EXPLANATIONS, NO ADDITIONAL TEXT**

{{
  "status": "success",
  "product_category": "herbicide/foliar/fungicide/insecticide/fertilizer/other",
  "metrics_detected": ["metric1", "metric2", ...],
  "measurement_intervals": ["3 DAA", "7 DAA", ...],
  
  "data_quality": {{
    "completeness_score": 0-100,
    "critical_data_present": true/false,
    "sample_size_adequate": true/false,
    "reliability_notes": "",
    "missing_fields": []
  }},
  
  "basic_info": {{
    "cooperator": "",
    "product": "",
    "location": "",
    "application_date": "",
    "planting_date": "",
    "crop": "",
    "plot_size": "",
    "contact": "",
    "participants": 0,
    "total_sales": 0
  }},
  
  "treatment_comparison": {{
    "control": {{
      "description": "",
      "product": "",
      "rate": "",
      "timing": "",
      "method": "",
      "applications": ""
    }},
    "leads_agri": {{
      "product": "",
      "rate": "",
      "timing": "",
      "method": "",
      "applications": ""
    }},
    "protocol_assessment": ""
  }},
  
  "performance_analysis": {{
    "metric_type": "rating_scale/percentage/count/measurement",
    "rating_scale_info": "1-4 scale where 1=poor, 4=excellent (only if rating scale)",
    
    "raw_data": {{
      "control": {{}},
      "leads_agri": {{}}
    }},
    
    "calculated_metrics": {{
      "control_average": 0,
      "leads_average": 0,
      "improvement_value": 0,
      "improvement_percent": 0,
      "improvement_interpretation": ""
    }},
    
    "statistical_assessment": {{
      "improvement_significance": "highly_significant/significant/moderate/marginal",
      "performance_consistency": "high/medium/low",
      "confidence_level": "high/medium/low",
      "notes": ""
    }},
    
    "trend_analysis": {{
      "control_trend": "improving/stable/declining",
      "leads_trend": "improving/stable/declining",
      "key_observation": "",
      "speed_of_action": "fast/moderate/slow"
    }}
  }},
  
  "yield_analysis": {{
    "control_yield": "",
    "leads_yield": "",
    "yield_improvement": 0,
    "yield_status": "available/pending/not_measured"
  }},
  
  "cooperator_feedback": {{
    "raw_feedback": "",
    "sentiment": "positive/neutral/negative/mixed",
    "key_highlights": [],
    "visible_results_timeline": "",
    "concerns": []
  }},
  
  "commercial_metrics": {{
    "demo_date": "",
    "participants": 0,
    "total_sales": 0,
    "sales_per_participant": 0,
    "demo_conducted": true/false,
    "market_reception": ""
  }},
  
  "risk_factors": [
    "risk description with data basis"
  ],
  
  "opportunities": [
    "opportunity description with data basis"
  ],
  
  "recommendations": [
    {{
      "priority": "high/medium/low",
      "recommendation": "",
      "data_basis": "",
      "expected_impact": ""
    }}
  ],
  
  "executive_summary": ""
}}

═══════════════════════════════════════════════════════════════
INPUT DATA TO ANALYZE:
═══════════════════════════════════════════════════════════════

{markdown_data}

═══════════════════════════════════════════════════════════════
FINAL INSTRUCTION: RETURN ONLY THE JSON STRUCTURE. NO OTHER TEXT.
═══════════════════════════════════════════════════════════════
"""
)

# Additional specialized analysis templates
def efficacy_analysis_template():
    return PromptTemplate.from_template(
"""DETAILED EFFICACY ANALYSIS FOR AGRICULTURAL TRIAL

PERFORMANCE METRICS:
- Calculate control percentage improvement at each interval
- Determine performance consistency over time
- Identify peak performance period
- Assess speed of action (early vs late control)

TREND ANALYSIS:
- Analyze if control is improving, stable, or declining
- Compare early (3 DAA) vs established (14 DAA) performance
- Identify any performance patterns

BENCHMARKING:
- Compare against standard industry expectations
- Evaluate against farmer practice baseline
- Assess if results meet product claims

**RETURN ONLY JSON, NO OTHER TEXT:**

{{
  "performance_rating": "excellent/good/moderate/poor",
  "key_strengths": ["strength1", "strength2"],
  "improvement_areas": ["area1", "area2"],
  "consistency_score": 0-100,
  "speed_of_action": "fast/moderate/slow"
}}
"""
)

def commercial_analysis_template():
    return PromptTemplate.from_template(
"""COMMERCIAL POTENTIAL ANALYSIS

SALES & CONVERSION METRICS:
- Analyze total sales value
- Calculate per participant engagement value
- Assess demo conversion potential
- Evaluate market interest level

SCALABILITY ASSESSMENT:
- Participant engagement quality
- Geographical relevance
- Timing effectiveness
- Replication potential

BUSINESS RECOMMENDATIONS:
- Market expansion suggestions
- Product positioning
- Sales strategy adjustments
- Future demo improvements

**RETURN ONLY JSON, NO OTHER TEXT:**

{{
  "commercial_potential": "high/medium/low",
  "conversion_likelihood": 0-100,
  "key_opportunities": ["opp1", "opp2"],
  "risk_factors": ["risk1", "risk2"],
  "followup_actions": ["action1", "action2"]
}}
"""
)