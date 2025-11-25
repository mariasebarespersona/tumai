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
                        # CRITICAL: Detect "send this/that content by email" requests
                        # OR email continuation (user just provided email address)
                        # Extract the most recent AI response BEFORE truncating history
                        user_input_lower = user_input.lower()
                        is_contextual_email = any(ref in user_input_lower for ref in ['este', 'ese', 'esto', 'eso', 'esta', 'esa'])
                        is_email_request = any(kw in user_input_lower for kw in ['manda', 'envía', 'enviar', 'mandame', 'enviame', 'email', 'correo'])
                        
                        # NEW: Also detect if user is providing ONLY an email (continuation)
                        import re
                        email_pattern = r'[\w\.-]+@[\w\.-]+\.\w+'
                        is_email_continuation = False
                        if re.search(email_pattern, user_input):
                            words_in_message = user_input.split()
                            if len(words_in_message) <= 3:
                                is_email_continuation = True
                                logger.info(f"[orchestrator] 🎯 Detected email continuation - will extract previous response")
                        
                        if (is_contextual_email and is_email_request) or is_email_continuation:
                            # STRATEGY: Find the most recent SUBSTANTIVE AI response
                            # Skip: confirmations, questions, document lists, tool results
                            all_messages = state.values["messages"]
                            last_ai_response = None
                            
                            for msg in reversed(all_messages):
                                if isinstance(msg, AIMessage) and msg.content and len(str(msg.content).strip()) > 50:
                                    content_str = str(msg.content).lower()
                                    
                                    # SKIP: Questions asking for information
                                    if any(question in content_str for question in ['¿a qué correo', '¿qué email', 'proporciona el correo', 'proporciona el email', 'proporciona la dirección', 'necesito que me proporciones']):
                                        logger.debug(f"[orchestrator] Skipping question: {content_str[:80]}")
                                        continue
                                    
                                    # SKIP: Confirmations, greetings
                                    if any(skip in content_str for skip in ['✅', 'he enviado', 'trabajando en:', 'estamos en:']):
                                        continue
                                    
                                    # SKIP: Document lists (multiple bullet points)
                                    if content_str.count('•') > 3 or content_str.count('-') > 5:
                                        logger.debug(f"[orchestrator] Skipping document list")
                                        continue
                                    
                                    # SKIP: Short confirmations or simple responses
                                    if len(content_str) < 100 and any(word in content_str for word in ['ok', 'vale', 'entendido', 'perfecto']):
                                        continue
                                    
                                    # PREFER: Substantive content (explanations, summaries, RAG responses)
                                    # Check if it's a RAG response or substantive content
                                    has_substantive_content = any(indicator in content_str for indicator in [
                                        'documento', 'contrato', 'establece', 'según', 'contenido', 
                                        'información', 'datos', 'detalles', 'indica', 'menciona', 'señal', 'arras'
                                    ])
                                    
                                    if has_substantive_content or len(content_str) > 200:
                                        last_ai_response = str(msg.content)
                                        logger.info(f"[orchestrator] 🎯 Found substantive response: {content_str[:80]}...")
                                        break
                            
                            if last_ai_response:
                                full_context["previous_response"] = last_ai_response
                                logger.info(f"[orchestrator] 🎯 Detected contextual email request - extracted previous response ({len(last_ai_response)} chars)")
                            else:
                                logger.warning(f"[orchestrator] ⚠️ Could not find substantive previous response for contextual email")
                        
                        # Get last 10 messages for context (not too many to avoid bloat)
                        messages = state.values["messages"][-10:]
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
                # Check if we should continue with a specialized agent from previous turn
                # This enables multi-turn conversations with specialized agents
                continue_with_agent = None
                if full_context.get("history"):
                    try:
                        last_messages = full_context["history"][-2:]  # Last 2 messages (AI question + user answer)
                        if len(last_messages) >= 2:
                            last_ai = last_messages[-2]
                            last_human = last_messages[-1]
                            
                            # Check if last AI message was a question from a specialized agent
                            if isinstance(last_ai, AIMessage) and isinstance(last_human, HumanMessage):
                                ai_content = str(last_ai.content).lower()
                                human_content = str(last_human.content).lower()
                                
                                # Pattern: AI asked for email, user provided email
                                if "correo" in ai_content or "email" in ai_content:
                                    if "@" in human_content and len(human_content.split()) <= 3:
                                        # User is likely responding with an email
                                        # Check what the previous intent was
                                        if len(full_context["history"]) >= 3:
                                            prev_human = full_context["history"][-3]
                                            if isinstance(prev_human, HumanMessage):
                                                prev_content = str(prev_human.content).lower()
                                                # If previous message was about documents, continue with DocsAgent
                                                if any(kw in prev_content for kw in ["documento", "email", "correo", "manda", "envia", "envía"]):
                                                    continue_with_agent = "DocsAgent"
                                                    logger.info(f"[orchestrator] 🔄 Continuing multi-turn conversation with DocsAgent")
                    except Exception as e:
                        logger.warning(f"[orchestrator] Error checking conversation continuity: {e}")
                
                if continue_with_agent:
                    current_agent_name = continue_with_agent
                    agent_path.append(current_agent_name)
                    routing = None
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

