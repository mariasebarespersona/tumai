"""
OrchestrationRouter - Manages agent routing with bidirectional communication.

Handles:
- Initial routing based on intent
- Redirect/escalate loops from agents
- Fallback to MainAgent
- Loop prevention (max 3 redirects)
- Direct agent execution (Phase 2b)
"""

import logging
import time
from typing import Dict, Any, Optional
from router.active_router import ActiveRouter
# Metrics removed - using Logfire instead
def log_event(*args, **kwargs): pass  # No-op for now
from agents.property_agent import PropertyAgent
from agents.numbers_agent import NumbersAgent
from agents.docs_agent import DocsAgent

logger = logging.getLogger("orchestrator")


class OrchestrationRouter:
    """
    Orchestrates agent routing with bidirectional communication support.
    """
    
    def __init__(self):
        """Initialize orchestration router."""
        self.active_router = ActiveRouter()
        self.max_redirects = 3
        
        # Initialize specialized agents
        self.property_agent = PropertyAgent()
        self.numbers_agent = NumbersAgent()
        self.docs_agent = DocsAgent()
        
        # Agent registry
        self.agents = {
            "PropertyAgent": self.property_agent,
            "NumbersAgent": self.numbers_agent,
            "DocsAgent": self.docs_agent
        }
        
        logger.info(f"[orchestrator] Initialized with {len(self.agents)} specialized agents, max_redirects=3")
    
    async def route_and_execute(
        self,
        user_input: str,
        session_id: str,
        property_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        use_main_agent: bool = False,
        direct_execution: bool = False  # NEW: Enable Phase 2b direct execution
    ) -> Dict[str, Any]:
        """
        Route user input to appropriate agent and handle redirects.
        
        Args:
            user_input: User's message
            session_id: Session ID for tracking
            property_id: Current property ID
            context: Additional context
            use_main_agent: If True, skip routing and use MainAgent directly
            direct_execution: If True, agents execute directly (Phase 2b)
        
        Returns:
            Dict with response, agent_path, redirects, and metadata
        """
        start_time = time.time()
        redirect_count = 0
        agent_path = []  # Track which agents were used
        current_input = user_input
        
        try:
            # Prepare context
            full_context = context or {}
            full_context["session_id"] = session_id
            full_context["property_id"] = property_id
            
            # Add property_name to context so agent knows which property it's working with
            if property_id:
                try:
                    from tools.property_tools import get_property
                    prop_info = get_property(property_id)
                    if prop_info:
                        full_context["property_name"] = prop_info.get("name")
                        logger.info(f"[orchestrator] Working with property: {full_context['property_name']} ({property_id})")
                except Exception as e:
                    logger.warning(f"[orchestrator] Could not get property name: {e}")
            
            # If use_main_agent is True, skip routing entirely
            if use_main_agent:
                logger.info(f"[orchestrator] Using MainAgent directly (skip routing)")
                log_event("routing", "skip_routing", "success", extra={"session": session_id})
                
                return {
                    "status": "use_main_agent",
                    "agent_path": ["MainAgent"],
                    "redirects": 0,
                    "total_latency_ms": int((time.time() - start_time) * 1000)
                }
            
            # Get initial routing decision
            routing = await self.active_router.decide(current_input, full_context)
            current_agent_name = routing["target_agent"]
            agent_path.append(current_agent_name)
            
            logger.info(
                f"[orchestrator] Initial routing: {routing['intent']} "
                f"(conf={routing['confidence']:.2f}) → {current_agent_name}"
            )
            
            # Log routing decision
            log_event("routing", "route_decision", "success", 
                      ms=int((time.time() - start_time) * 1000),
                      extra={
                          "session": session_id,
                          "intent": routing["intent"],
                          "confidence": routing["confidence"],
                          "agent": current_agent_name,
                          "fallback": routing.get("fallback_reason") is not None
                      })
            
            # === PHASE 2b: DIRECT EXECUTION ===
            if direct_execution and current_agent_name in self.agents:
                logger.info(f"[orchestrator] 🚀 Starting direct execution with {current_agent_name}")
                
                # Bidirectional routing loop
                while redirect_count < self.max_redirects:
                    agent = self.agents[current_agent_name]
                    
                    logger.info(f"[orchestrator] Executing {current_agent_name} (redirect #{redirect_count})")
                    
                    # Execute agent
                    result = agent.run(
                        user_input=current_input,
                        property_id=property_id,
                        context=full_context
                    )
                    
                    action = result.get("action")
                    logger.info(f"[orchestrator] {current_agent_name} returned action={action}")
                    
                    # Handle different actions
                    if action == "complete":
                        # Agent completed successfully
                        logger.info(f"[orchestrator] ✅ Task completed by {current_agent_name}")
                        log_event("agent", "task_complete", "success",
                                  ms=result.get("latency_ms", 0),
                                  extra={
                                      "session": session_id,
                                      "agent": current_agent_name,
                                      "redirects": redirect_count
                                  })
                        
                        orchestrator_result = {
                            "status": "completed",
                            "response": result.get("response"),
                            "agent_path": agent_path,
                            "redirects": redirect_count,
                            "final_agent": current_agent_name,
                            "tool_calls": result.get("tool_calls", []),
                            "total_latency_ms": int((time.time() - start_time) * 1000)
                        }
                        
                        # If agent returned a property_id (e.g., after switching properties), include it
                        if result.get("property_id"):
                            orchestrator_result["property_id"] = result["property_id"]
                            logger.info(f"[orchestrator] 📍 Property changed to: {result['property_id']}")
                        
                        return orchestrator_result
                    
                    elif action == "redirect":
                        # Agent redirected to another agent
                        to_agent = result.get("to_agent")
                        reason = result.get("reason", "unknown")
                        
                        logger.info(f"[orchestrator] 🔄 {current_agent_name} redirecting to {to_agent} (reason: {reason})")
                        log_event("agent", "redirect", "success",
                                  extra={
                                      "session": session_id,
                                      "from_agent": current_agent_name,
                                      "to_agent": to_agent,
                                      "reason": reason
                                  })
                        
                        # Check if target agent exists
                        if to_agent not in self.agents and to_agent != "MainAgent":
                            logger.warning(f"[orchestrator] ⚠️ Unknown agent {to_agent}, falling back to MainAgent")
                            to_agent = "MainAgent"
                        
                        # Update for next iteration
                        current_agent_name = to_agent
                        agent_path.append(to_agent)
                        redirect_count += 1
                        
                        # If redirecting to MainAgent, break loop
                        if to_agent == "MainAgent":
                            logger.info(f"[orchestrator] ⬆️ Escalating to MainAgent after {redirect_count} redirects")
                            break
                    
                    elif action == "escalate":
                        # Agent escalated to MainAgent (multi-domain task)
                        reason = result.get("reason", "unknown")
                        
                        logger.info(f"[orchestrator] ⬆️ {current_agent_name} escalating to MainAgent (reason: {reason})")
                        log_event("agent", "escalate", "success",
                                  extra={
                                      "session": session_id,
                                      "from_agent": current_agent_name,
                                      "reason": reason
                                  })
                        
                        agent_path.append("MainAgent")
                        break
                    
                    elif action == "error":
                        # Agent encountered error, fallback to MainAgent
                        error = result.get("error", "unknown")
                        
                        logger.error(f"[orchestrator] ❌ {current_agent_name} error: {error}, falling back to MainAgent")
                        log_event("agent", "error", "error",
                                  extra={
                                      "session": session_id,
                                      "agent": current_agent_name,
                                      "error": error
                                  })
                        
                        agent_path.append("MainAgent")
                        break
                    
                    else:
                        # Unknown action, fallback
                        logger.warning(f"[orchestrator] ⚠️ Unknown action {action}, falling back to MainAgent")
                        agent_path.append("MainAgent")
                        break
                
                # Check if max redirects reached
                if redirect_count >= self.max_redirects:
                    logger.warning(f"[orchestrator] ⚠️ Max redirects ({self.max_redirects}) reached, falling back to MainAgent")
                    agent_path.append("MainAgent")
                    log_event("routing", "max_redirects", "warning",
                              extra={"session": session_id, "redirects": redirect_count})
                
                # Return final status
                return {
                    "status": "use_main_agent",  # Falls back to MainAgent
                    "agent_path": agent_path,
                    "redirects": redirect_count,
                    "total_latency_ms": int((time.time() - start_time) * 1000),
                    "reason": "redirected_to_main_agent"
                }
            
            # === PHASE 2a: ROUTING ONLY (No direct execution) ===
            else:
                return {
                    "status": "routed",
                    "intent": routing["intent"],
                    "confidence": routing["confidence"],
                    "target_agent": current_agent_name,
                    "agent_path": agent_path,
                    "redirects": redirect_count,
                    "total_latency_ms": int((time.time() - start_time) * 1000),
                    "fallback_reason": routing.get("fallback_reason")
                }
        
        except Exception as e:
            logger.error(f"[orchestrator] Error during routing: {e}", exc_info=True)
            log_event("routing", "error", "error",
                      ms=int((time.time() - start_time) * 1000),
                      extra={"session": session_id, "error": str(e)})
            
            return {
                "status": "error",
                "error": str(e),
                "agent_path": agent_path or ["MainAgent"],
                "redirects": redirect_count,
                "total_latency_ms": int((time.time() - start_time) * 1000)
            }


# Global orchestrator instance
orchestrator = OrchestrationRouter()

