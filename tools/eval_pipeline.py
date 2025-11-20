"""
Evaluation Pipeline - Orchestrates all evaluation layers after user feedback.

Layers:
1. Tool Selection Accuracy - Did the agent use the right tools?
2. Response Quality (LLM-as-Judge) - Was the response helpful and accurate?
3. Task Success Verification - Did the operation complete successfully?
"""

import logging
import threading
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


def trigger_eval_pipeline(feedback_id: str):
    """
    Trigger the evaluation pipeline in a background thread.
    
    Args:
        feedback_id: UUID of the feedback record
    """
    thread = threading.Thread(target=run_eval_pipeline, args=(feedback_id,))
    thread.daemon = True
    thread.start()
    logger.info(f"[eval_pipeline] Started background evaluation for feedback {feedback_id}")


def run_eval_pipeline(feedback_id: str):
    """
    Run the full evaluation pipeline for a feedback record.
    
    This runs in a background thread to avoid blocking the API response.
    
    Args:
        feedback_id: UUID of the feedback record
    """
    try:
        from tools.supabase_client import sb
        
        logger.info(f"[eval_pipeline] Starting evaluation for feedback {feedback_id}")
        
        # 1. Fetch feedback data
        feedback_result = sb.table("agent_feedback").select("*").eq("id", feedback_id).execute()
        
        if not feedback_result.data or len(feedback_result.data) == 0:
            logger.error(f"[eval_pipeline] Feedback {feedback_id} not found")
            return
        
        feedback = feedback_result.data[0]
        
        # Extract data
        property_id = feedback.get("property_id")
        agent_name = feedback.get("agent_name")
        user_message = feedback.get("user_message")
        agent_response = feedback.get("agent_response")
        tool_calls = feedback.get("tool_calls") or []
        tool_results = feedback.get("tool_results") or []
        
        logger.info(f"[eval_pipeline] Evaluating: agent={agent_name}, property={property_id[:8] if property_id else 'None'}...")
        
        # 2. Run Tool Selection Evaluation
        tool_score = None
        try:
            tool_score = evaluate_tool_selection(
                user_message=user_message,
                agent_name=agent_name,
                tool_calls=tool_calls
            )
            logger.info(f"[eval_pipeline] Tool selection score: {tool_score}")
        except Exception as e:
            logger.error(f"[eval_pipeline] Tool selection eval failed: {e}")
        
        # 3. Run Response Quality Evaluation (LLM-as-Judge)
        quality_score = None
        quality_reasoning = None
        try:
            quality_result = evaluate_response_quality(
                user_message=user_message,
                agent_response=agent_response,
                tool_calls=tool_calls
            )
            quality_score = quality_result.get("score")
            quality_reasoning = quality_result.get("reasoning")
            logger.info(f"[eval_pipeline] Response quality score: {quality_score}")
        except Exception as e:
            logger.error(f"[eval_pipeline] Response quality eval failed: {e}")
        
        # 4. Run Task Success Verification
        task_success_score = None
        verification_details = None
        try:
            task_result = evaluate_task_success(
                user_message=user_message,
                agent_name=agent_name,
                property_id=property_id,
                tool_calls=tool_calls,
                tool_results=tool_results
            )
            task_success_score = task_result.get("score")
            verification_details = task_result.get("details")
            logger.info(f"[eval_pipeline] Task success score: {task_success_score}")
        except Exception as e:
            logger.error(f"[eval_pipeline] Task success eval failed: {e}")
        
        # 5. Update feedback record with evaluation results
        update_data = {
            "tool_selection_score": tool_score,
            "response_quality_score": quality_score,
            "task_success_score": task_success_score,
            "eval_reasoning": {
                "quality_reasoning": quality_reasoning,
                "verification_details": verification_details,
                "evaluated_at": datetime.now().isoformat()
            },
            "eval_timestamp": datetime.now().isoformat()
        }
        
        sb.table("agent_feedback").update(update_data).eq("id", feedback_id).execute()
        
        logger.info(f"[eval_pipeline] ✅ Evaluation complete for feedback {feedback_id}")
        logger.info(f"  - Tool Selection: {tool_score}")
        logger.info(f"  - Response Quality: {quality_score}")
        logger.info(f"  - Task Success: {task_success_score}")
        
    except Exception as e:
        logger.error(f"[eval_pipeline] Pipeline failed for feedback {feedback_id}: {e}", exc_info=True)


def evaluate_tool_selection(user_message: str, agent_name: str, tool_calls: list) -> Optional[float]:
    """
    Evaluate if the agent selected the right tools for the task.
    
    Returns:
        Score from 0.0 to 1.0, or None if evaluation not applicable
    """
    # Simple heuristic-based evaluation
    # TODO: Enhance with more sophisticated rules or ML model
    
    if not tool_calls:
        # No tools used - check if tools were needed
        msg_lower = user_message.lower()
        
        # If user asked for specific actions, tools should have been used
        if any(word in msg_lower for word in ["lista", "crea", "sube", "elimina", "manda", "exporta"]):
            return 0.0  # Should have used tools but didn't
        else:
            return 1.0  # No tools needed, correct
    
    # Tools were used - assume correct for now
    # In future, validate specific tool choices against expected tools
    return 1.0


def evaluate_response_quality(user_message: str, agent_response: str, tool_calls: list) -> Dict[str, Any]:
    """
    Use LLM-as-Judge to evaluate response quality.
    
    Returns:
        Dict with 'score' (0.0-1.0) and 'reasoning' (str)
    """
    try:
        from openai import OpenAI
        import os
        
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        # Build evaluation prompt
        prompt = f"""You are evaluating an AI assistant's response quality.

**User's Question:**
{user_message}

**Assistant's Response:**
{agent_response}

**Tools Used:** {len(tool_calls)} tool(s)

Evaluate the response on these criteria:
1. **Relevance**: Does it address the user's question?
2. **Clarity**: Is it clear and easy to understand?
3. **Completeness**: Does it provide all necessary information?
4. **Accuracy**: Is the information correct?

Provide:
1. A score from 0.0 to 1.0 (where 1.0 is perfect)
2. Brief reasoning (2-3 sentences)

Format your response as JSON:
{{"score": 0.85, "reasoning": "The response..."}}"""
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are an expert evaluator of AI assistant responses. Always respond with valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            response_format={"type": "json_object"}
        )
        
        import json
        result = json.loads(response.choices[0].message.content)
        
        return {
            "score": float(result.get("score", 0.5)),
            "reasoning": result.get("reasoning", "")
        }
        
    except Exception as e:
        logger.error(f"[eval_response_quality] Failed: {e}")
        return {"score": None, "reasoning": f"Evaluation failed: {e}"}


def evaluate_task_success(
    user_message: str,
    agent_name: str,
    property_id: Optional[str],
    tool_calls: list,
    tool_results: list
) -> Dict[str, Any]:
    """
    Verify that the task was completed successfully by checking the database.
    
    Returns:
        Dict with 'score' (0.0-1.0) and 'details' (dict)
    """
    from tools.verifier import (
        verify_property_creation,
        verify_document_upload,
        verify_numbers_update,
        verify_property_deletion,
        verify_numbers_template_deletion
    )
    
    msg_lower = user_message.lower()
    details = {"checks_performed": []}
    
    try:
        # Detect what task was attempted
        
        # Property creation
        if any(phrase in msg_lower for phrase in ["crea propiedad", "nueva propiedad", "añadir propiedad"]):
            # Extract property name from tool results or message
            property_name = _extract_property_name(user_message, tool_results)
            if property_id and property_name:
                result = verify_property_creation(property_id, property_name)
                details["checks_performed"].append("property_creation")
                details["property_creation"] = result
                return {"score": 1.0 if result["success"] else 0.0, "details": details}
        
        # Document upload
        elif any(phrase in msg_lower for phrase in ["sube", "subir", "upload"]) and "documento" in msg_lower:
            if property_id and tool_calls:
                # Extract document info from tool calls
                doc_info = _extract_document_info(tool_calls, tool_results)
                if doc_info:
                    result = verify_document_upload(
                        property_id=property_id,
                        document_name=doc_info.get("document_name"),
                        document_group=doc_info.get("document_group")
                    )
                    details["checks_performed"].append("document_upload")
                    details["document_upload"] = result
                    return {"score": 1.0 if result["success"] else 0.0, "details": details}
        
        # Numbers table update
        elif any(phrase in msg_lower for phrase in ["pon", "escribe", "actualiza"]) and any(x in msg_lower for x in ["celda", "b5", "c5", "d5"]):
            if property_id:
                # Extract cell and value info
                cell_info = _extract_cell_info(user_message, tool_calls)
                if cell_info:
                    result = verify_numbers_update(
                        property_id=property_id,
                        template_key=cell_info.get("template_key", "R2B"),
                        updated_cell=cell_info.get("cell"),
                        expected_value=cell_info.get("value")
                    )
                    details["checks_performed"].append("numbers_update")
                    details["numbers_update"] = result
                    return {"score": 1.0 if result["success"] else 0.0, "details": details}
        
        # Property deletion
        elif any(phrase in msg_lower for phrase in ["elimina propiedad", "borra propiedad"]):
            if property_id:
                result = verify_property_deletion(property_id)
                details["checks_performed"].append("property_deletion")
                details["property_deletion"] = result
                return {"score": 1.0 if result["success"] else 0.0, "details": details}
        
        # Default: No specific verification needed or not implemented yet
        details["checks_performed"].append("no_specific_check")
        return {"score": None, "details": details}
        
    except Exception as e:
        logger.error(f"[evaluate_task_success] Failed: {e}")
        details["error"] = str(e)
        return {"score": None, "details": details}


def _extract_property_name(message: str, tool_results: list) -> Optional[str]:
    """Extract property name from message or tool results."""
    # Simple extraction - look for property name in tool results
    for result in tool_results:
        if isinstance(result, dict) and "name" in result:
            return result["name"]
    return None


def _extract_document_info(tool_calls: list, tool_results: list) -> Optional[Dict]:
    """Extract document info from tool calls/results."""
    for call in tool_calls:
        if isinstance(call, dict) and "upload_and_link" in call.get("name", ""):
            args = call.get("args", {})
            return {
                "document_name": args.get("document_name"),
                "document_group": args.get("document_group")
            }
    return None


def _extract_cell_info(message: str, tool_calls: list) -> Optional[Dict]:
    """Extract cell reference and value from message or tool calls."""
    import re
    
    # Look for cell reference (B5, C5, etc.)
    cell_match = re.search(r'\b([A-Z]{1,3}[0-9]{1,4})\b', message, re.I)
    if not cell_match:
        return None
    
    cell = cell_match.group(1).upper()
    
    # Look for value
    value = None
    for call in tool_calls:
        if isinstance(call, dict) and "set_cell" in call.get("name", ""):
            args = call.get("args", {})
            if args.get("cell") == cell:
                value = args.get("value")
                break
    
    return {
        "cell": cell,
        "value": value,
        "template_key": "R2B"  # Default
    }
