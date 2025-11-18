from crewai import Agent, Task, Crew, Process, LLM
from src.utils.clean_logger import get_clean_logger
from src.utils.config import GEMINI_MODEL, GOOGLE_API_KEY, LANGFUSE_CONFIGURED
import json
import os

logger = get_clean_logger(__name__)

# Import Langfuse decorator if available (v3 API)
if LANGFUSE_CONFIGURED:
    try:
        from langfuse import observe, get_client
        LANGFUSE_AVAILABLE = True
    except ImportError:
        LANGFUSE_AVAILABLE = False
        def observe(*args, **kwargs):
            def decorator(func):
                return func
            return decorator
        def get_client():
            return None
else:
    LANGFUSE_AVAILABLE = False
    def observe(*args, **kwargs):
        def decorator(func):
            return func
        return decorator
    def get_client():
        return None

def create_evaluation_crew():
    """Create specialized evaluation crew with 4 expert agents"""
    
    # Debug and configure CrewAI API key
    if not GOOGLE_API_KEY:
        logger.error("❌ GOOGLE_API_KEY is not configured in config.py!")
        logger.error("❌ Check if GEMINI_APIKEY is set in your .env file")
        raise ValueError("Google API key required for CrewAI")
    
    # Configure CrewAI LLM using the proper LLM class (not string)
    gemini_model_name = f"gemini/{GEMINI_MODEL}" if not GEMINI_MODEL.startswith("gemini/") else GEMINI_MODEL
    
    # Create CrewAI LLM instance with explicit API key
    gemini_llm = LLM(
        model=gemini_model_name,  # e.g., 'gemini/gemini-2.5-flash'
        api_key=GOOGLE_API_KEY
    )
    
    logger.info(f"🔑 CrewAI LLM configured: {gemini_model_name}")
    logger.debug(f"🔑 API key length: {len(GOOGLE_API_KEY) if GOOGLE_API_KEY else 0} chars")
    
    # Context Analysis Agent
    context_analyst = Agent(
        role="Document Context Analyst",
        goal="Analyze document type, data quality, and extraction completeness for agricultural reports",
        backstory="""You are an expert at understanding agricultural documents and 
        assessing data quality. You can identify when data is missing due to source 
        limitations (like incomplete forms) vs extraction issues (like OCR problems). 
        You understand different types of agricultural documents: demo reports, 
        trial reports, invoices, letters, etc.""",
        llm=gemini_llm,
        verbose=False,
        allow_delegation=False,
        max_iter=2
    )
    
    # Quality Assessment Agent  
    quality_assessor = Agent(
        role="Output Quality Evaluator",
        goal="Evaluate analysis accuracy, completeness, and reliability for agricultural data",
        backstory="""You specialize in agricultural data analysis quality. You know 
        what makes a good agricultural analysis - proper calculations, complete summaries, 
        clear interpretations, and proper handling of missing data. You can spot 
        calculation errors, incomplete summaries, or unclear interpretations. You 
        understand agricultural metrics like yield, treatment effects, statistical significance.""",
        llm=gemini_llm,
        verbose=False,
        allow_delegation=False,
        max_iter=2
    )
    
    # Strategic Decision Agent
    strategy_planner = Agent(
        role="Processing Strategy Advisor", 
        goal="Determine optimal next steps based on quality assessment and retry constraints",
        backstory="""You are a workflow optimization expert for agricultural data processing. 
        Based on quality findings, you decide whether to retry analysis/graphs, proceed with 
        current results, or use alternative approaches. You balance quality standards with 
        practical constraints like retry limits (max 2 attempts), processing time, and user needs.""",
        llm=gemini_llm,
        verbose=False,
        allow_delegation=False,
        max_iter=2
    )
    
    # Final Decision Coordinator
    decision_coordinator = Agent(
        role="Evaluation Decision Coordinator",
        goal="Synthesize team input into final evaluation decision with proper JSON format",
        backstory="""You coordinate the evaluation team and make final decisions 
        based on all agent inputs. You balance quality standards with practical 
        constraints like retry limits. You always provide responses in the required 
        JSON format for system compatibility. You understand confidence scoring (0.0-1.0), 
        issue classification, and decision options.""",
        llm=gemini_llm,
        verbose=False,
        allow_delegation=False,
        max_iter=2
    )
    
    return {
        'context_analyst': context_analyst,
        'quality_assessor': quality_assessor, 
        'strategy_planner': strategy_planner,
        'decision_coordinator': decision_coordinator
    }


@observe(name="crewai_multi_agent_evaluation")
def validate_output_with_crew(state: dict) -> dict:
    """
    CrewAI-powered evaluation replacing single LLM call
    Returns same format as original validate_output()
    
    This function is traced with Langfuse @observe decorator to track:
    - CrewAI agent execution
    - Multi-agent collaboration
    - Task completion and results
    """
    logger.info("🤖 Starting CrewAI multi-agent evaluation")
    
    # ============================================
    # LANGFUSE INTEGRATION START
    # ============================================
    logger.llm_request("crewai_multi_agent", "Starting multi-agent evaluation system")
    
    # Debug API key configuration
    env_google_key = os.environ.get("GOOGLE_API_KEY")
    config_google_key = GOOGLE_API_KEY
    
    logger.debug(f"🔍 Config GOOGLE_API_KEY exists: {bool(config_google_key)}")
    logger.debug(f"🔍 Env GOOGLE_API_KEY exists: {bool(env_google_key)}")
    if config_google_key:
        logger.debug(f"🔍 Config key length: {len(config_google_key)} chars")
        logger.debug(f"🔍 Config key starts with: {config_google_key[:10]}..." if len(config_google_key) > 10 else "Key too short")
    if env_google_key:
        logger.debug(f"🔍 Env key length: {len(env_google_key)} chars")
    
    try:
        # Get evaluation context
        analysis = state.get("analysis_result", {})
        graphs = state.get("graph_suggestions", {})
        extracted_content = state.get("extracted_markdown", "")
        errors = state.get("errors", [])
        attempts = state.get("evaluation_attempts", 0)
        
        has_analysis = bool(analysis)
        has_graphs = bool(graphs)
        
        if has_analysis and not has_graphs:
            evaluation_context = "analysis"
        elif has_graphs:
            evaluation_context = "graphs"  
        else:
            evaluation_context = "unknown"
            
        logger.info(f"📋 Evaluation context: {evaluation_context}, Attempt: #{attempts + 1}")
        
        # Update Langfuse trace with CrewAI metadata
        if LANGFUSE_AVAILABLE:
            try:
                client = get_client()
                if client:
                    # Update observation with CrewAI metadata
                    client.update_current_observation(
                        metadata={
                            "crewai_agents": 4,
                            "evaluation_context": evaluation_context,
                            "attempt": attempts + 1,
                            "max_attempts": 2,
                            "has_analysis": has_analysis,
                            "has_graphs": has_graphs,
                            "content_length": len(extracted_content),
                            "error_count": len(errors)
                        }
                    )
                    # Add score for context tracking
                    client.score(
                        name="multi_agent_evaluation_context",
                        value=1.0,
                        comment=f"CrewAI evaluation - Context: {evaluation_context}, Attempt: #{attempts + 1}, Agents: 4 specialists"
                    )
            except Exception as trace_error:
                logger.debug(f"Langfuse trace update failed: {trace_error}")
        
        # Create agents
        agents = create_evaluation_crew()
        
        # Create evaluation tasks based on context
        tasks = []
        
        # Task 1: Context Analysis
        context_description = f"""
        Analyze the document context and data quality for {evaluation_context} evaluation.
        
        **Document Context:**
        - Content length: {len(extracted_content)} characters
        - Has analysis: {has_analysis}
        - Has graphs: {has_graphs}
        - Processing errors: {len(errors)} errors
        - Current attempt: #{attempts + 1}/2
        
        **Document Sample:**
        {extracted_content[:800] if extracted_content else "No content extracted"}...
        
        **Current Errors:**
        {errors if errors else "No errors reported"}
        
        **Your Analysis Task:**
        1. Assess document type and quality
        2. Identify data completeness issues
        3. Distinguish source limitations vs extraction problems
        4. Rate overall extractability (0-1 scale)
        5. Provide context for quality evaluation
        
        Focus on: Is this a proper agricultural demo/trial document? Are data gaps due to missing source info or processing issues?
        """
        
        context_task = Task(
            description=context_description,
            agent=agents['context_analyst'],
            expected_output="Context analysis with extractability assessment and document type classification"
        )
        tasks.append(context_task)
        
        # Task 2: Quality Assessment (context-specific)
        if evaluation_context == "analysis":
            quality_description = f"""
            Based on the context analysis, evaluate the ANALYSIS quality.
            
            **Analysis to Evaluate:**
            Executive Summary: {analysis.get('executive_summary', 'Not available')[:500]}...
            
            Key Metrics: {str(analysis.get('performance_analysis', {}).get('calculated_metrics', {}))[:300]}...
            
            Data Quality Notes: {analysis.get('data_quality', {}).get('reliability_notes', 'Not available')[:200]}...
            
            **Quality Assessment Criteria:**
            1. **Completeness**: Does analysis cover key aspects available in data?
            2. **Accuracy**: Are calculations and interpretations correct?
            3. **Clarity**: Is executive summary clear and useful?
            4. **Data Handling**: Are missing/incomplete data properly acknowledged?
            
            **Rate confidence 0.0-1.0:**
            - 0.8-1.0: Excellent quality, ready for user
            - 0.6-0.8: Good quality, minor issues acceptable
            - 0.4-0.6: Moderate quality, consider retry if attempts allow
            - 0.0-0.4: Poor quality, retry recommended if possible
            
            Consider: Is this good enough for agricultural professionals to use?
            """
        else:  # graphs evaluation
            chart_count = len(graphs.get('suggested_charts', []))
            chart_titles = [chart.get('title', 'Untitled') for chart in graphs.get('suggested_charts', [])]
            
            quality_description = f"""
            Based on the context analysis, evaluate the GRAPH SUGGESTIONS quality.
            
            **Graph Suggestions to Evaluate:**
            - Number of charts: {chart_count}
            - Chart titles: {chart_titles[:5]}  # Show first 5
            
            **Sample Chart Data:**
            {str(graphs.get('suggested_charts', [])[:2])[:500] if graphs.get('suggested_charts') else "No charts available"}...
            
            **Quality Assessment Criteria:**
            1. **Appropriateness**: Do chart types match the data being visualized?
            2. **Completeness**: Are there enough charts to tell the data story?
            3. **Data Quality**: Do charts have proper datasets and labels?
            4. **Clarity**: Are titles and descriptions meaningful?
            5. **Relevance**: Do graphs highlight key insights from analysis?
            
            **Rate confidence 0.0-1.0:**
            - 0.8-1.0: Excellent visualizations, ready for user
            - 0.6-0.8: Good visualizations, minor issues acceptable  
            - 0.4-0.6: Moderate quality, consider retry if attempts allow
            - 0.0-0.4: Poor quality, retry recommended if possible
            
            Consider: Will these graphs help agricultural professionals understand the data?
            """
        
        # Add explicit JSON format requirement to quality assessment
        quality_description += """
        
        **CRITICAL: RETURN STRUCTURED JSON FORMAT:**
        {
            "confidence": <float 0.0-1.0>,
            "quality_assessment": "<detailed evaluation>", 
            "key_issues": ["<list of specific issues found>"],
            "recommendations": "<improvement suggestions if confidence < 0.7>"
        }
        
        **Example:**
        {
            "confidence": 0.85,
            "quality_assessment": "Analysis shows strong data interpretation with clear executive summary",
            "key_issues": [],
            "recommendations": "No major improvements needed"
        }
        """
        
        quality_task = Task(
            description=quality_description,
            agent=agents['quality_assessor'],
            expected_output="JSON object with confidence score (0.0-1.0), quality assessment, issues, and recommendations"
        )
        tasks.append(quality_task)
        
        # Task 3: Strategic Planning
        strategy_description = f"""
        Based on context and quality analysis, determine the optimal processing strategy.
        
        **Current Situation:**
        - Evaluation context: {evaluation_context}
        - Current attempt: #{attempts + 1} of 2 maximum
        - Retries remaining: {1 - attempts} 
        
        **Strategic Considerations:**
        1. Is retry worth it given the quality issues found?
        2. Are the issues fixable with reprocessing or are they source limitations?
        3. What's the optimal next action for this specific case?
        4. Should we accept current quality or attempt retry?
        5. Consider user needs: better to have imperfect data quickly vs perfect data slowly
        
        **Decision Options:**
        - PROCEED: Accept current quality and move to next step
        - RETRY: Attempt reprocessing to improve quality (if attempts available)
        - ACCEPT_LIMITATIONS: Acknowledge source limitations but proceed
        
        Focus on: Practical decision-making balancing quality vs efficiency.
        """
        
        strategy_task = Task(
            description=strategy_description,
            agent=agents['strategy_planner'], 
            expected_output="Strategic recommendation with clear reasoning and next action proposal"
        )
        tasks.append(strategy_task)
        
        # Task 4: Final Decision Coordination
        decision_description = f"""
        Coordinate all team input and make the final evaluation decision.
        
        **Team Input to Synthesize:**
        - Context analyst: Document assessment and extractability 
        - Quality assessor: **Confidence score (0.0-1.0)** and quality metrics  
        - Strategy planner: Recommended action and reasoning
        
        **CRITICAL: Extract Quality Assessor's Confidence Score**
        The Quality Assessor provided a JSON response with a "confidence" field. 
        You MUST use that exact confidence value in your final decision.
        
        **Final Decision Requirements:**
        You MUST provide a JSON response with exactly these fields:
        {{
            "confidence": <USE QUALITY ASSESSOR'S CONFIDENCE VALUE EXACTLY>,
            "feedback": "<string: User-friendly explanation combining all team input>",
            "decision": "<string: 'store' or 're_analyze' or 'suggest_graphs'>", 
            "issue_type": "<string: 'fixable_analysis' or 'source_limitation' or 'graph_issue' or 'no_issue'>"
        }}
        
        **Decision Logic (based on Quality Assessor's confidence):**
        - confidence > 0.7: Usually proceed with "store"
        - confidence 0.4-0.7: Proceed or retry based on attempts and issue type
        - confidence < 0.4: Retry if attempts available, otherwise proceed with limitations
        
        **Issue Type Guidelines:**
        - "source_limitation": Data missing from original document (not a processing error)
        - "fixable_analysis": Analysis quality can be improved with retry
        - "graph_issue": Graph generation has problems that retry might fix  
        - "no_issue": Quality is acceptable, proceed normally
        
        **Decision Guidelines:**
        - "store": Accept current results and continue workflow
        - "re_analyze": Retry analysis step (only if evaluating analysis)
        - "suggest_graphs": Retry graph generation (only if evaluating graphs)
        
        CRITICAL: Return ONLY the JSON object, no other text or formatting.
        """
        
        decision_task = Task(
            description=decision_description,
            agent=agents['decision_coordinator'],
            expected_output="Final evaluation decision in exact JSON format required by system"
        )
        tasks.append(decision_task)
        
        # Create and execute crew
        crew = Crew(
            agents=list(agents.values()),
            tasks=tasks,
            process=Process.sequential,  # Execute tasks in order for logical flow
            verbose=True
        )
        
        logger.info(f"🚀 Executing CrewAI crew with {len(tasks)} tasks for {evaluation_context}")
        
        # ============================================
        # LANGFUSE CREW EXECUTION TRACKING
        # ============================================
        logger.llm_request("crewai_agents", f"Starting {len(tasks)}-agent collaboration: Context={evaluation_context}")
        
        # Update trace before crew execution
        if LANGFUSE_AVAILABLE:
            try:
                client = get_client()
                if client:
                    client.update_current_observation(
                        metadata={
                            "crew_execution_started": True,
                            "tasks_count": len(tasks),
                            "agents_count": len(agents),
                            "process_type": "sequential"
                        }
                    )
            except Exception as e:
                logger.debug(f"Could not update observation before crew execution: {e}")
        
        # Execute crew collaboration
        crew_result = crew.kickoff()
        
        logger.info(f"✅ CrewAI crew completed")
        logger.debug(f"Crew result type: {type(crew_result)}")
        
        # Debug CrewOutput structure
        if hasattr(crew_result, 'raw'):
            logger.debug(f"CrewOutput.raw type: {type(crew_result.raw)}, value: {str(crew_result.raw)[:200]}...")
        if hasattr(crew_result, 'tasks_output'):
            logger.debug(f"CrewOutput.tasks_output type: {type(crew_result.tasks_output)}, length: {len(crew_result.tasks_output) if crew_result.tasks_output else 0}")
        if hasattr(crew_result, '__dict__'):
            logger.debug(f"CrewOutput attributes: {list(crew_result.__dict__.keys())}")
        
        logger.debug(f"Raw crew result string: {str(crew_result)[:500]}...")
        
        # Track crew completion
        logger.llm_response("crewai_agents", "completed", f"4-agent collaboration finished for {evaluation_context}")
        
        # Update trace after crew execution
        if LANGFUSE_AVAILABLE:
            try:
                client = get_client()
                if client:
                    client.update_current_observation(
                        metadata={
                            "crew_execution_completed": True,
                            "crew_result_type": type(crew_result).__name__,
                            "crew_result_length": len(str(crew_result)) if crew_result else 0
                        }
                    )
            except Exception as e:
                logger.debug(f"Could not update observation after crew execution: {e}")
        
        # Parse the final decision (should be JSON from decision coordinator)
        try:
            # Handle CrewOutput object from CrewAI
            if hasattr(crew_result, 'raw'):
                # CrewOutput has .raw attribute containing the actual output
                raw_output = crew_result.raw
                logger.debug(f"Extracted raw output from CrewOutput: {type(raw_output)}")
                crew_result = raw_output
            elif hasattr(crew_result, 'tasks_output'):
                # Alternative: use tasks_output if available
                tasks_output = crew_result.tasks_output
                if tasks_output and len(tasks_output) > 0:
                    # Get the last task output (decision coordinator)
                    crew_result = tasks_output[-1]
                    logger.debug(f"Extracted from tasks_output: {type(crew_result)}")
            
            # Now parse the actual result (string, dict, or other)
            if isinstance(crew_result, str):
                # Try to find and extract the first valid JSON object from the string
                import re
                from src.formatter.json_helper import repair_json_string, clean_json_from_llm_response
                
                # First, try using the existing JSON cleaner (handles markdown, etc.)
                cleaned_result = clean_json_from_llm_response(crew_result)
                if cleaned_result and isinstance(cleaned_result, dict):
                    final_decision = cleaned_result
                else:
                    # Fallback: find first JSON object manually
                    # Use non-greedy match to find the first complete JSON object
                    json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', crew_result, re.DOTALL)
                    if json_match:
                        json_str = json_match.group(0)
                        # Repair JSON string to handle invalid escape sequences
                        json_str = repair_json_string(json_str)
                        # Parse only the first JSON object (stop at first valid parse)
                        try:
                            final_decision = json.loads(json_str)
                        except json.JSONDecodeError:
                            # If still fails, try to extract just the first object more carefully
                            # Find the first { and match it with its closing }
                            brace_count = 0
                            start_idx = crew_result.find('{')
                            if start_idx != -1:
                                for i in range(start_idx, len(crew_result)):
                                    if crew_result[i] == '{':
                                        brace_count += 1
                                    elif crew_result[i] == '}':
                                        brace_count -= 1
                                        if brace_count == 0:
                                            # Found complete first object
                                            json_str = crew_result[start_idx:i+1]
                                            json_str = repair_json_string(json_str)
                                            final_decision = json.loads(json_str)
                                            break
                                else:
                                    raise ValueError("No complete JSON object found in crew result")
                            else:
                                raise ValueError("No JSON found in crew result")
                    else:
                        raise ValueError("No JSON found in crew result")
            elif isinstance(crew_result, dict):
                final_decision = crew_result
            elif hasattr(crew_result, '__dict__'):
                # Try to convert object to dict
                final_decision = crew_result.__dict__
                logger.debug(f"Converted object to dict: {final_decision}")
            else:
                # Last resort: convert to string and try to extract JSON
                result_str = str(crew_result)
                logger.debug(f"Attempting to parse string representation: {result_str[:200]}...")
                import re
                from src.formatter.json_helper import repair_json_string, clean_json_from_llm_response
                
                # Try using the existing JSON cleaner first
                cleaned_result = clean_json_from_llm_response(result_str)
                if cleaned_result and isinstance(cleaned_result, dict):
                    final_decision = cleaned_result
                else:
                    # Fallback: find first JSON object manually
                    # Find the first { and match it with its closing }
                    brace_count = 0
                    start_idx = result_str.find('{')
                    if start_idx != -1:
                        for i in range(start_idx, len(result_str)):
                            if result_str[i] == '{':
                                brace_count += 1
                            elif result_str[i] == '}':
                                brace_count -= 1
                                if brace_count == 0:
                                    # Found complete first object
                                    json_str = result_str[start_idx:i+1]
                                    json_str = repair_json_string(json_str)
                                    final_decision = json.loads(json_str)
                                    break
                        else:
                            raise ValueError(f"Could not extract complete JSON from result type: {type(crew_result)}")
                    else:
                        raise ValueError(f"Could not extract JSON from result type: {type(crew_result)}")
                
            # ============================================
            # VALIDATE CONFIDENCE SCORE FROM AGENTS
            # ============================================
            if final_decision and 'confidence' in final_decision:
                confidence = final_decision.get('confidence')
                logger.info(f"🎯 CrewAI agents returned confidence score: {confidence}")
                
                # Validate confidence is numeric and in range
                try:
                    conf_value = float(confidence)
                    if 0.0 <= conf_value <= 1.0:
                        logger.info(f"✅ Confidence score validation passed: {conf_value:.3f}")
                    else:
                        logger.warning(f"⚠️ Confidence score out of range: {conf_value}, will be clamped")
                except (TypeError, ValueError):
                    logger.warning(f"⚠️ Invalid confidence score type: {confidence} (type: {type(confidence)})")
            else:
                logger.warning("⚠️ No confidence score found in CrewAI result")
                
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Failed to parse CrewAI result as JSON: {e}")
            logger.debug(f"Raw result was: {crew_result}")
            
            # Intelligent fallback based on context
            final_decision = {
                "confidence": 0.6,
                "feedback": f"CrewAI multi-agent evaluation completed successfully, but result parsing failed. Proceeding with moderate confidence. Raw output: {str(crew_result)[:200]}...",
                "decision": "store",  # Safe default
                "issue_type": "no_issue"
            }
        
        # Validate and sanitize the decision
        final_decision = _validate_crew_decision(final_decision, evaluation_context)
        
        logger.info(f"🎯 Final CrewAI decision: confidence={final_decision['confidence']:.2f}, decision={final_decision['decision']}, issue={final_decision['issue_type']}")
        
        # ============================================
        # DETAILED SCORING ANALYSIS  
        # ============================================
        confidence_level = final_decision['confidence']
        if confidence_level >= 0.8:
            logger.info(f"🌟 EXCELLENT quality (confidence: {confidence_level:.3f}) - Multi-agent system recommends proceeding")
        elif confidence_level >= 0.6:
            logger.info(f"✅ GOOD quality (confidence: {confidence_level:.3f}) - Multi-agent system finds acceptable")
        elif confidence_level >= 0.4:
            logger.info(f"⚠️ MODERATE quality (confidence: {confidence_level:.3f}) - Multi-agent system suggests caution")
        else:
            logger.info(f"❌ LOW quality (confidence: {confidence_level:.3f}) - Multi-agent system recommends retry")
        
        # Log scoring context for analysis
        logger.info(f"📊 CrewAI Scoring Summary: Context={evaluation_context}, Attempt={attempts + 1}, Decision={final_decision['decision']}")
        
        # ============================================
        # LANGFUSE COMPLETION TRACKING
        # ============================================
        logger.llm_response("crewai_multi_agent", "completed", f"Multi-agent evaluation completed - confidence: {final_decision['confidence']:.2f}")
        
        # Score the final result quality and update trace
        if LANGFUSE_AVAILABLE:
            try:
                client = get_client()
                if client:
                    # Update observation with final decision metadata
                    client.update_current_observation(
                        metadata={
                            "final_confidence": final_decision.get('confidence', 0.5),
                            "final_decision": final_decision.get('decision'),
                            "issue_type": final_decision.get('issue_type'),
                            "evaluation_completed": True
                        }
                    )
                    # Score based on confidence level
                    confidence_score = final_decision.get('confidence', 0.5)
                    client.score(
                        name="multi_agent_evaluation_confidence",
                        value=confidence_score,
                        comment=f"CrewAI decision: {final_decision['decision']}, issue: {final_decision['issue_type']}, feedback: {final_decision['feedback'][:100]}"
                    )
            except Exception as trace_error:
                logger.debug(f"Langfuse completion tracking failed: {trace_error}")
        
        return final_decision
        
    except Exception as e:
        logger.error(f"❌ CrewAI evaluation failed: {str(e)}")
        logger.debug(f"Full error details: {e}")
        
        # ============================================
        # LANGFUSE ERROR TRACKING
        # ============================================
        if LANGFUSE_AVAILABLE:
            try:
                from src.monitoring.trace.langfuse_helper import update_trace_with_error
                update_trace_with_error(e, {
                    "agent": "crewai_multi_agent",
                    "step": "evaluation",
                    "error_type": "crew_execution",
                    "crewai_enabled": True
                })
            except Exception as trace_error:
                logger.debug(f"Langfuse error tracking failed: {trace_error}")
        
        # Specific handling for API key errors
        if "API key not valid" in str(e) or "AuthenticationError" in str(e):
            logger.error("🔑 API Key issue detected - check your GEMINI_APIKEY in .env file")
            logger.error("💡 Tip: Make sure GEMINI_APIKEY is set and valid in your .env file")
        
        # Safe fallback that won't break the workflow
        return {
            "confidence": 0.5,
            "feedback": f"Multi-agent evaluation encountered an error but proceeding safely: {str(e)[:100]}",
            "decision": "store", 
            "issue_type": "no_issue"
        }


def _validate_crew_decision(decision: dict, context: str) -> dict:
    """Validate and sanitize CrewAI decision to ensure system compatibility"""
    
    # Ensure all required fields exist
    validated = {
        "confidence": decision.get("confidence", 0.6),
        "feedback": decision.get("feedback", "CrewAI multi-agent evaluation completed"),
        "decision": decision.get("decision", "store"),
        "issue_type": decision.get("issue_type", "no_issue")
    }
    
    # Validate confidence range
    try:
        conf = float(validated["confidence"])
        validated["confidence"] = max(0.0, min(1.0, conf))  # Clamp to 0.0-1.0
    except (ValueError, TypeError):
        logger.warning(f"Invalid confidence value: {validated['confidence']}, using 0.6")
        validated["confidence"] = 0.6
    
    # Validate decision options
    valid_decisions = ["store", "re_analyze", "suggest_graphs"]
    if validated["decision"] not in valid_decisions:
        logger.warning(f"Invalid decision: {validated['decision']}, using 'store'")
        validated["decision"] = "store"
    
    # Validate issue type
    valid_issues = ["fixable_analysis", "source_limitation", "graph_issue", "no_issue"]
    if validated["issue_type"] not in valid_issues:
        logger.warning(f"Invalid issue_type: {validated['issue_type']}, using 'no_issue'")
        validated["issue_type"] = "no_issue"
    
    # Ensure feedback is a string and not too long
    if not isinstance(validated["feedback"], str):
        validated["feedback"] = str(validated["feedback"])
    validated["feedback"] = validated["feedback"][:500]  # Limit length
    
    # Context-specific validation
    if context == "analysis" and validated["decision"] == "suggest_graphs":
        logger.warning("Invalid decision 'suggest_graphs' for analysis context, changing to 're_analyze'")
        validated["decision"] = "re_analyze"
    elif context == "graphs" and validated["decision"] == "re_analyze":
        logger.warning("Invalid decision 're_analyze' for graphs context, changing to 'suggest_graphs'")
        validated["decision"] = "suggest_graphs"
    
    return validated
