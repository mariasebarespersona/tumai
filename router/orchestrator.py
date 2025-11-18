"""
OrchestrationRouter - Manages agent routing with bidirectional communication.

Handles:
- Initial routing based on intent
- Redirect/escalate loops from agents
- Fallback to MainAgent
- Loop prevention (max 3 redirects)
"""

import logging
import time
from typing import Dict, Any, Optional
from router.active_router import ActiveRouter
from tools.metrics import log_event, record_latency

logger = logging.getLogger("orchestrator")


class OrchestrationRouter:
    """
    Orchestrates agent routing with bidirectional communication support.
    """
    
    def __init__(self):
        """Initialize orchestration router."""
        self.active_router = ActiveRouter()
        self.max_redirects = 3
        logger.info("[orchestrator] Initialized with max_redirects=3")
    
    async def route_and_execute(
        self,
        user_input: str,
        session_id: str,
        property_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        use_main_agent: bool = False
    ) -> Dict[str, Any]:
        """
        Route user input to appropriate agent and handle redirects.
        
        Args:
            user_input: User's message
            session_id: Session ID for tracking
            property_id: Current property ID
            context: Additional context
            use_main_agent: If True, skip routing and use MainAgent directly
        
        Returns:
            Dict with response, agent_path, redirects, and metadata
        """
        start_time = time.time()
        redirect_count = 0
        agent_path = []  # Track which agents were used
        responses = []
        
        try:
            # Prepare context
            full_context = context or {}
            full_context["session_id"] = session_id
            full_context["property_id"] = property_id
            
            # If use_main_agent is True, skip routing entirely
            if use_main_agent:
                logger.info(f"[orchestrator] Using MainAgent directly (skip routing)")
                log_event("orchestrator.skip_routing", {"session": session_id})
                
                return {
                    "status": "use_main_agent",
                    "agent_path": ["MainAgent"],
                    "redirects": 0,
                    "total_latency_ms": int((time.time() - start_time) * 1000)
                }
            
            # Get initial routing decision
            routing = await self.active_router.decide(user_input, full_context)
            current_agent = routing["target_agent"]
            agent_path.append(current_agent)
            
            logger.info(
                f"[orchestrator] Initial routing: {routing['intent']} "
                f"(conf={routing['confidence']:.2f}) → {current_agent}"
            )
            
            # Log routing decision
            log_event("orchestrator.route", {
                "session": session_id,
                "intent": routing["intent"],
                "confidence": routing["confidence"],
                "agent": current_agent,
                "fallback": routing.get("fallback_reason") is not None
            })
            
            # For now, we return the routing decision and let the existing
            # LangGraph agent handle execution. Full agent execution will be
            # implemented in Phase 3.
            #
            # This allows gradual integration:
            # Phase 2a: Router decides agent (✅ this)
            # Phase 2b: Specialized agents execute (future)
            
            return {
                "status": "routed",
                "intent": routing["intent"],
                "confidence": routing["confidence"],
                "target_agent": current_agent,
                "agent_path": agent_path,
                "redirects": redirect_count,
                "total_latency_ms": int((time.time() - start_time) * 1000),
                "fallback_reason": routing.get("fallback_reason")
            }
        
        except Exception as e:
            logger.error(f"[orchestrator] Error during routing: {e}", exc_info=True)
            log_event("orchestrator.error", {"session": session_id, "error": str(e)})
            
            return {
                "status": "error",
                "error": str(e),
                "agent_path": agent_path or ["MainAgent"],
                "redirects": redirect_count,
                "total_latency_ms": int((time.time() - start_time) * 1000)
            }


# Global orchestrator instance
orchestrator = OrchestrationRouter()

