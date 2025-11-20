"""
Response Quality Evaluator - Uses LLM-as-Judge to evaluate response quality.
"""
from typing import List, Dict, Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
import json
import logging

logger = logging.getLogger(__name__)

JUDGE_SYSTEM_PROMPT = """You are an expert evaluator for RAMA AI, a Spanish-language real estate assistant that helps users manage properties, documents, and financial calculations.

Your job is to evaluate the agent's response quality based on:
1. **Relevance** (0-1): Did it directly address the user's request?
2. **Completeness** (0-1): Did it provide all necessary information?
3. **Accuracy** (0-1): Is the information factually correct based on tool results?
4. **Tone** (0-1): Is it professional, friendly, and appropriate for Spanish real estate context?

Be critical but fair. A response is only accurate if tool results confirm the action was completed.

Output ONLY valid JSON, no additional text:
{
  "relevance": 0.0-1.0,
  "completeness": 0.0-1.0,
  "accuracy": 0.0-1.0,
  "tone": 0.0-1.0,
  "overall": 0.0-1.0,
  "reasoning": "Brief explanation of scores"
}
"""

JUDGE_USER_PROMPT_TEMPLATE = """Evaluate this conversation:

USER REQUEST: "{user_message}"

AGENT RESPONSE: "{agent_response}"

TOOLS USED: {tool_calls}

TOOL RESULTS: {tool_results}

Evaluate the response quality. Output ONLY JSON.
"""


def judge_response_quality(
    user_message: str,
    agent_response: str,
    tool_calls: List[Dict],
    tool_results: Optional[List[Dict]] = None
) -> Dict:
    """
    Use GPT-4o as judge to evaluate response quality.
    
    Args:
        user_message: User's message
        agent_response: Agent's response
        tool_calls: List of tools called
        tool_results: Results from tools (optional)
        
    Returns:
        Dict with scores (0-1) for relevance, completeness, accuracy, tone, overall
    """
    
    try:
        llm = ChatOpenAI(model="gpt-4o", temperature=0)
        
        # Format tool calls and results for prompt
        tool_calls_str = json.dumps(tool_calls, indent=2) if tool_calls else "[]"
        tool_results_str = json.dumps(tool_results, indent=2) if tool_results else "No results available"
        
        user_prompt = JUDGE_USER_PROMPT_TEMPLATE.format(
            user_message=user_message,
            agent_response=agent_response,
            tool_calls=tool_calls_str,
            tool_results=tool_results_str
        )
        
        messages = [
            SystemMessage(content=JUDGE_SYSTEM_PROMPT),
            HumanMessage(content=user_prompt)
        ]
        
        logger.info("[LLM Judge] Invoking GPT-4o to evaluate response...")
        response = llm.invoke(messages)
        
        # Parse JSON response
        try:
            # Try to extract JSON from response (in case there's extra text)
            content = response.content.strip()
            
            # Find JSON object in response
            start = content.find('{')
            end = content.rfind('}') + 1
            
            if start >= 0 and end > start:
                json_str = content[start:end]
                scores = json.loads(json_str)
                
                # Validate required fields
                required_fields = ["relevance", "completeness", "accuracy", "tone", "overall", "reasoning"]
                for field in required_fields:
                    if field not in scores:
                        raise ValueError(f"Missing field: {field}")
                
                # Clamp scores to 0-1
                for field in ["relevance", "completeness", "accuracy", "tone", "overall"]:
                    scores[field] = max(0.0, min(1.0, float(scores[field])))
                
                logger.info(f"[LLM Judge] Scores: {scores}")
                return scores
            else:
                raise ValueError("No JSON object found in response")
                
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"[LLM Judge] Failed to parse response: {e}")
            logger.error(f"[LLM Judge] Raw response: {response.content}")
            
            # Fallback scores
            return {
                "relevance": 0.5,
                "completeness": 0.5,
                "accuracy": 0.5,
                "tone": 0.5,
                "overall": 0.5,
                "reasoning": f"Failed to parse judge response: {str(e)}",
                "error": "parse_error"
            }
    
    except Exception as e:
        logger.error(f"[LLM Judge] Error during evaluation: {e}", exc_info=True)
        
        # Fallback scores
        return {
            "relevance": 0.5,
            "completeness": 0.5,
            "accuracy": 0.5,
            "tone": 0.5,
            "overall": 0.5,
            "reasoning": f"Judge evaluation failed: {str(e)}",
            "error": "evaluation_error"
        }

