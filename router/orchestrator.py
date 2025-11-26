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
        direct_execution: bool = False,  # NEW: Enable Phase 2b direct execution
        force_agent: Optional[str] = None  # NEW: Force a specific agent (e.g., "DocsAgent")
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
            force_agent: If set, skip routing and use this agent directly (e.g., for confirmation flows)
        
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
            
            # CRITICAL: Load conversation history from LangGraph checkpointer
            # This enables specialized agents to maintain context across turns
            if session_id:
                try:
                    from agentic import agent as langgraph_agent
                    from langchain_core.messages import HumanMessage, AIMessage
                    
                    config = {"configurable": {"thread_id": session_id}}
                    state = langgraph_agent.get_state(config)
                    
                    if state and state.values.get("messages"):
                        # STRATEGY: Let the LLM reason naturally from conversation history
                        # Instead of extracting specific messages, provide MORE context
                        # so the agent can understand the full flow
                        
                        # Increase history size for better context understanding
                        # 25 messages = ~12-13 conversation turns (enough to see RAG responses)
                        messages = state.values["messages"][-25:]
                        
                        # Filter out system messages - only keep human/AI dialogue
                        history = [m for m in messages if isinstance(m, (HumanMessage, AIMessage))]
                        full_context["history"] = history
                        logger.info(f"[orchestrator] Loaded {len(history)} messages from checkpointer for specialized agent context")
                except Exception as e:
                    logger.warning(f"[orchestrator] Could not load history from checkpointer: {e}")
            
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
            
            # If force_agent is set, skip routing and use that agent
            if force_agent:
                logger.info(f"[orchestrator] Using {force_agent} directly (force_agent, skip routing)")
                current_agent_name = force_agent
                agent_path.append(current_agent_name)
                routing = None  # No routing decision was made
            else:
                # ============================================================
                # CRITICAL: CONVERSATION CONTINUITY DETECTION
                # This enables multi-turn conversations with specialized agents
                # The router MUST detect when user is responding to agent questions
                # ============================================================
                continue_with_agent = None
                continue_intent = None
                
                if full_context.get("history"):
                    try:
                        # Get last AI message (the question) and current user input
                        last_ai = None
                        for msg in reversed(full_context["history"]):
                            if isinstance(msg, AIMessage):
                                last_ai = msg
                                break
                        
                        if last_ai:
                            ai_content = str(last_ai.content).lower()
                            user_input_lower = user_input.lower().strip()
                            
                            # ============================================================
                            # CONFIRMATION RESPONSES (si, sí, no, confirmo, etc.)
                            # ============================================================
                            confirmation_yes = ["si", "sí", "yes", "confirmo", "adelante", "ok", "vale", "claro", "por supuesto", "hazlo", "dale"]
                            confirmation_no = ["no", "cancelar", "cancela", "olvídalo", "olvidalo", "mejor no"]
                            
                            is_confirmation = user_input_lower in confirmation_yes or user_input_lower in confirmation_no
                            is_yes = user_input_lower in confirmation_yes
                            
                            if is_confirmation:
                                # PATTERN: Property deletion confirmation
                                if ("¿estás seguro" in ai_content or "estas seguro" in ai_content) and "eliminar" in ai_content:
                                    continue_with_agent = "PropertyAgent"
                                    continue_intent = "property.delete_confirm" if is_yes else "property.delete_cancel"
                                    logger.info(f"[orchestrator] 🔄 Continuing with PropertyAgent (delete confirmation: {user_input_lower})")
                                
                                # PATTERN: Property creation confirmation
                                elif ("crear" in ai_content or "añadir" in ai_content) and "propiedad" in ai_content:
                                    continue_with_agent = "PropertyAgent"
                                    continue_intent = "property.create_confirm" if is_yes else "property.create_cancel"
                                    logger.info(f"[orchestrator] 🔄 Continuing with PropertyAgent (create confirmation: {user_input_lower})")
                                
                                # PATTERN: Document upload confirmation
                                elif ("confirmas" in ai_content or "subir" in ai_content) and ("documento" in ai_content or "archivo" in ai_content):
                                    continue_with_agent = "DocsAgent"
                                    continue_intent = "docs.upload_confirm" if is_yes else "docs.upload_cancel"
                                    logger.info(f"[orchestrator] 🔄 Continuing with DocsAgent (upload confirmation: {user_input_lower})")
                                
                                # PATTERN: Email send confirmation
                                elif ("enviar" in ai_content or "mandar" in ai_content) and ("email" in ai_content or "correo" in ai_content):
                                    continue_with_agent = "DocsAgent"
                                    continue_intent = "docs.email_confirm" if is_yes else "docs.email_cancel"
                                    logger.info(f"[orchestrator] 🔄 Continuing with DocsAgent (email confirmation: {user_input_lower})")
                                
                                # PATTERN: Numbers template confirmation
                                elif "plantilla" in ai_content and ("números" in ai_content or "numeros" in ai_content):
                                    continue_with_agent = "NumbersAgent"
                                    continue_intent = "numbers.template_confirm" if is_yes else "numbers.template_cancel"
                                    logger.info(f"[orchestrator] 🔄 Continuing with NumbersAgent (template confirmation: {user_input_lower})")
                                
                                # PATTERN: Generic confirmation - check for any question mark
                                elif "?" in ai_content and not continue_with_agent:
                                    # Try to detect agent from context
                                    if any(kw in ai_content for kw in ["propiedad", "inmueble", "casa", "piso"]):
                                        continue_with_agent = "PropertyAgent"
                                        continue_intent = "property.confirm"
                                    elif any(kw in ai_content for kw in ["documento", "archivo", "pdf", "contrato"]):
                                        continue_with_agent = "DocsAgent"
                                        continue_intent = "docs.confirm"
                                    elif any(kw in ai_content for kw in ["número", "plantilla", "excel", "celda"]):
                                        continue_with_agent = "NumbersAgent"
                                        continue_intent = "numbers.confirm"
                                    
                                    if continue_with_agent:
                                        logger.info(f"[orchestrator] 🔄 Generic confirmation detected, continuing with {continue_with_agent}")
                            
                            # ============================================================
                            # NON-CONFIRMATION RESPONSES (data input, selections, etc.)
                            # ============================================================
                            if not continue_with_agent:
                                # PATTERN: PropertyAgent asked for name/address
                                property_ask_phrases = [
                                    "nombre y la dirección", "nombre y dirección",
                                    "proporciona el nombre", "proporciona nombre",
                                    "nombre de la propiedad", "dirección de la propiedad",
                                    "cómo se llama", "como se llama"
                                ]
                                if any(phrase in ai_content for phrase in property_ask_phrases):
                                    continue_with_agent = "PropertyAgent"
                                    continue_intent = "property.create_continue"
                                    logger.info(f"[orchestrator] 🔄 Continuing with PropertyAgent (name/address response)")
                                
                                # PATTERN: AI asked for email, user provided email
                                elif ("correo" in ai_content or "email" in ai_content) and ("@" in user_input_lower):
                                    continue_with_agent = "DocsAgent"
                                    continue_intent = "docs.email_continue"
                                    logger.info(f"[orchestrator] 🔄 Continuing with DocsAgent (email provided)")
                                
                                # PATTERN: NumbersAgent asked for template selection
                                numbers_ask_phrases = ["qué plantilla", "que plantilla", "elige una", "1) r2b", "1) **r2b**"]
                                if any(phrase in ai_content for phrase in numbers_ask_phrases):
                                    template_responses = ["r2b", "promoción", "promocion", "1", "2", "3", "4", "r2b+pm", "r2b + pm"]
                                    if any(resp in user_input_lower for resp in template_responses):
                                        continue_with_agent = "NumbersAgent"
                                        continue_intent = "numbers.select_template"
                                        logger.info(f"[orchestrator] 🔄 Continuing with NumbersAgent (template selection)")
                                
                                # PATTERN: DocsAgent asked for document strategy (R2B vs Promoción)
                                strategy_ask_phrases = ["r2b o promoción", "r2b o promocion", "qué estrategia", "que estrategia", "qué camino", "que camino"]
                                if any(phrase in ai_content for phrase in strategy_ask_phrases):
                                    if any(resp in user_input_lower for resp in ["r2b", "promoción", "promocion", "1", "2"]):
                                        continue_with_agent = "DocsAgent"
                                        continue_intent = "docs.set_strategy"
                                        logger.info(f"[orchestrator] 🔄 Continuing with DocsAgent (strategy selection)")
                    
                    except Exception as e:
                        logger.warning(f"[orchestrator] Error checking conversation continuity: {e}")
                
                if continue_with_agent:
                    current_agent_name = continue_with_agent
                    agent_path.append(current_agent_name)
                    # Create a synthetic routing result for continuity
                    routing = {
                        "intent": continue_intent or "continuation",
                        "confidence": 0.98,
                        "target_agent": continue_with_agent,
                        "method": "conversation_continuity"
                    }
                    # Pass the intent to context so agents know what to do
                    full_context["intent"] = continue_intent
                    full_context["is_continuation"] = True
                    logger.info(f"[orchestrator] ✅ Conversation continuity: {continue_with_agent} with intent {continue_intent}")
                else:
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
                
                # Add intent to context for modular prompts
                if routing and routing.get("intent"):
                    full_context["intent"] = routing["intent"]
                    logger.info(f"[orchestrator] Intent for modular prompts: {routing['intent']}")
                
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
                        
                        # CRITICAL: Pass original intent to MainAgent so it doesn't lose context
                        # This prevents MainAgent from misinterpreting the user's request
                        full_context["original_intent"] = routing.get("intent")
                        full_context["failed_agent"] = current_agent_name
                        logger.info(f"[orchestrator] 📋 Passing original intent to MainAgent: {routing.get('intent')}")
                        
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

