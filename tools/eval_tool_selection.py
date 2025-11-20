"""
Tool Selection Evaluator - Evaluates if agent selected correct tools.
"""
from typing import List, Dict, Optional
import logging

from .eval_registry import get_expected_tools, classify_intent, get_intent_description

logger = logging.getLogger(__name__)


def evaluate_tool_selection(
    user_message: str,
    tool_calls: List[Dict],
    agent_name: str
) -> Dict:
    """
    Evaluate if agent selected correct tools for the task.
    
    Args:
        user_message: User's message
        tool_calls: List of tool calls made by agent
        agent_name: Name of the agent
        
    Returns:
        Dict with evaluation results:
        - accuracy: % of expected tools that were called
        - precision: % of called tools that were expected
        - expected_tools: List of expected tool names
        - actual_tools: List of actual tool names called
        - intent: Classified user intent
        - intent_description: Human-readable intent
        - missing_tools: Tools that should have been called but weren't
        - extra_tools: Tools that were called but weren't expected
    """
    
    # 1. Classify intent
    intent = classify_intent(user_message)
    intent_desc = get_intent_description(intent) if intent else "unknown"
    
    logger.info(f"[Tool Eval] Intent classified: {intent} ({intent_desc})")
    
    # 2. Get expected tools for this intent
    expected_tools = get_expected_tools(user_message)
    
    # 3. Get actual tools called
    actual_tools = [tc.get("name") for tc in tool_calls if tc.get("name")]
    
    logger.info(f"[Tool Eval] Expected: {expected_tools}, Actual: {actual_tools}")
    
    # 4. Calculate metrics
    if not expected_tools:
        # No specific expectation - can't evaluate
        return {
            "accuracy": None,
            "precision": None,
            "expected_tools": [],
            "actual_tools": actual_tools,
            "intent": intent,
            "intent_description": intent_desc,
            "missing_tools": [],
            "extra_tools": [],
            "note": "No expected tools defined for this intent"
        }
    
    # Set operations for comparison
    expected_set = set(expected_tools)
    actual_set = set(actual_tools)
    
    # Correct tools = intersection
    correct_tools = expected_set & actual_set
    
    # Missing tools = expected but not called
    missing_tools = list(expected_set - actual_set)
    
    # Extra tools = called but not expected
    extra_tools = list(actual_set - expected_set)
    
    # Accuracy (recall): % of expected tools that were called
    # accuracy = |correct| / |expected|
    accuracy = len(correct_tools) / len(expected_set) if expected_set else 1.0
    
    # Precision: % of called tools that were expected
    # precision = |correct| / |actual|
    precision = len(correct_tools) / len(actual_set) if actual_set else 1.0
    
    # F1 score for overall
    if accuracy + precision > 0:
        f1_score = 2 * (accuracy * precision) / (accuracy + precision)
    else:
        f1_score = 0.0
    
    result = {
        "accuracy": round(accuracy, 3),
        "precision": round(precision, 3),
        "f1_score": round(f1_score, 3),
        "expected_tools": expected_tools,
        "actual_tools": actual_tools,
        "correct_tools": list(correct_tools),
        "missing_tools": missing_tools,
        "extra_tools": extra_tools,
        "intent": intent,
        "intent_description": intent_desc,
    }
    
    logger.info(f"[Tool Eval] Result: accuracy={accuracy:.2f}, precision={precision:.2f}, f1={f1_score:.2f}")
    
    return result

