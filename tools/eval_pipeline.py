"""
Evaluation Pipeline - Orchestrates all evaluation layers.

This pipeline runs asynchronously after an agent response to evaluate:
1. Tool Selection (Layer 2)
2. Response Quality via LLM-as-Judge (Layer 3)
3. Task Success via Verifier (Layer 4)

Layer 1 (User Feedback) is collected directly from UI.
"""
import asyncio
from typing import Dict, List, Optional
import logging

from .supabase_client import sb
from .eval_tool_selection import evaluate_tool_selection
from .eval_response_quality import judge_response_quality
from .verifier import verify_task_success
from .logfire_metrics import log_metric

logger = logging.getLogger(__name__)


async def run_eval_pipeline(feedback_id: str):
    """
    Run complete evaluation pipeline for a feedback entry.
    
    This is called asynchronously after user submits feedback (or agent responds).
    
    Args:
        feedback_id: UUID of agent_feedback row
    """
    try:
        logger.info(f"[Eval Pipeline] Starting evaluation for feedback {feedback_id}")
        
        # 1. Fetch feedback data
        result = sb.table("agent_feedback").select("*").eq("id", feedback_id).execute()
        
        if not result.data or len(result.data) == 0:
            logger.error(f"[Eval Pipeline] Feedback {feedback_id} not found")
            return
        
        feedback = result.data[0]
        
        # Extract data
        user_message = feedback.get("user_message", "")
        agent_response = feedback.get("agent_response", "")
        tool_calls = feedback.get("tool_calls", [])
        tool_results = feedback.get("tool_results", [])
        agent_name = feedback.get("agent_name", "")
        property_id = feedback.get("property_id", "")
        
        # 2. Layer 2: Tool Selection Eval
        logger.info("[Eval Pipeline] Running tool selection eval...")
        tool_eval = evaluate_tool_selection(
            user_message=user_message,
            tool_calls=tool_calls,
            agent_name=agent_name
        )
        
        # 3. Layer 3: Response Quality (LLM-as-Judge)
        logger.info("[Eval Pipeline] Running LLM-as-Judge...")
        response_eval = judge_response_quality(
            user_message=user_message,
            agent_response=agent_response,
            tool_calls=tool_calls,
            tool_results=tool_results
        )
        
        # 4. Layer 4: Task Success (Verifier)
        logger.info("[Eval Pipeline] Running task success verifier...")
        task_success_eval = None
        if property_id and tool_calls:
            task_success_eval = verify_task_success(
                property_id=property_id,
                tool_calls=tool_calls,
                agent_name=agent_name
            )
        
        # 5. Update feedback row with eval results
        logger.info("[Eval Pipeline] Updating feedback with eval results...")
        update_data = {
            "tool_eval": tool_eval,
            "response_eval": response_eval,
            "task_success_eval": task_success_eval
        }
        
        sb.table("agent_feedback").update(update_data).eq("id", feedback_id).execute()
        
        # 6. Log to Logfire for monitoring
        log_metric(
            "evaluation_completed",
            value=1,
            attributes={
                "feedback_id": feedback_id,
                "agent_name": agent_name,
                "tool_accuracy": tool_eval.get("accuracy") if tool_eval.get("accuracy") is not None else -1,
                "tool_precision": tool_eval.get("precision") if tool_eval.get("precision") is not None else -1,
                "response_quality": response_eval.get("overall", -1),
                "task_success": task_success_eval.get("success", None) if task_success_eval else None
            }
        )
        
        logger.info(f"[Eval Pipeline] ✅ Evaluation complete for feedback {feedback_id}")
        logger.info(f"[Eval Pipeline] Tool: {tool_eval.get('accuracy', 'N/A'):.2f} acc, "
                   f"Response: {response_eval.get('overall', 0):.2f}, "
                   f"Task: {'✅' if (task_success_eval and task_success_eval.get('success')) else '❌'}")
        
    except Exception as e:
        logger.error(f"[Eval Pipeline] Error in evaluation pipeline: {e}", exc_info=True)
        
        # Log error to Logfire
        log_metric(
            "evaluation_error",
            value=1,
            attributes={
                "feedback_id": feedback_id,
                "error": str(e)
            }
        )


def trigger_eval_pipeline(feedback_id: str):
    """
    Trigger eval pipeline in background (sync wrapper for async).
    
    Args:
        feedback_id: UUID of agent_feedback row
    """
    try:
        # Run in background using asyncio
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If loop is running, create task
            loop.create_task(run_eval_pipeline(feedback_id))
        else:
            # If no loop, run directly
            loop.run_until_complete(run_eval_pipeline(feedback_id))
    except Exception as e:
        logger.error(f"[Eval Pipeline] Error triggering pipeline: {e}")


async def batch_eval_missing_feedbacks(limit: int = 100):
    """
    Batch evaluate feedbacks that don't have evals yet.
    
    Useful for:
    - Backfilling evals for existing feedback
    - Running periodic re-evaluation
    
    Args:
        limit: Max number of feedbacks to process
    """
    try:
        logger.info(f"[Batch Eval] Starting batch evaluation (limit={limit})")
        
        # Find feedbacks without evals
        result = sb.table("agent_feedback") \
            .select("id") \
            .is_("tool_eval", "null") \
            .order("created_at", desc=True) \
            .limit(limit) \
            .execute()
        
        feedback_ids = [row["id"] for row in result.data]
        
        logger.info(f"[Batch Eval] Found {len(feedback_ids)} feedbacks to evaluate")
        
        # Run evals in parallel (with concurrency limit)
        semaphore = asyncio.Semaphore(5)  # Max 5 concurrent evals
        
        async def eval_with_semaphore(fid):
            async with semaphore:
                await run_eval_pipeline(fid)
        
        tasks = [eval_with_semaphore(fid) for fid in feedback_ids]
        await asyncio.gather(*tasks)
        
        logger.info(f"[Batch Eval] ✅ Batch evaluation complete ({len(feedback_ids)} feedbacks)")
        
    except Exception as e:
        logger.error(f"[Batch Eval] Error in batch evaluation: {e}", exc_info=True)

