"""
Base Agent class for all specialized agents.

All agents inherit from this base class and override:
- get_system_prompt()
- get_tools()
"""

from typing import Dict, List, Any, Optional
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI
import logging
import time

# Logfire instrumentation for OpenAI (already done globally, but safe to call again)
import logfire
logfire.instrument_openai()

logger = logging.getLogger(__name__)


class BaseAgent:
    """Base class for all specialized agents."""
    
    def __init__(self, name: str, model: str = "gpt-4o-mini", temperature: float = 0.7):
        """Initialize the agent.
        
        Args:
            name: Agent name (e.g., "PropertyAgent")
            model: LLM model to use
            temperature: Temperature for LLM
        """
        self.name = name
        self.model = model
        self.temperature = temperature
        
        # Enable OpenAI Prompt Caching (reduces latency by 20-30% for repeated system prompts)
        # Using consistent seed helps maximize cache hits
        self.llm = ChatOpenAI(
            model=model, 
            temperature=temperature,
            seed=42  # Consistent seed for prompt caching
        )
        logger.info(f"[{self.name}] Initialized with model={model}, temp={temperature}, seed=42")
    
    def get_system_prompt(self) -> str:
        """Get the system prompt for this agent.
        
        Must be overridden by subclasses.
        """
        raise NotImplementedError(f"{self.name} must implement get_system_prompt()")
    
    def get_tools(self) -> List:
        """Get the list of tools this agent can use.
        
        Must be overridden by subclasses.
        """
        raise NotImplementedError(f"{self.name} must implement get_tools()")
    
    def is_out_of_scope(self, user_input: str) -> tuple[bool, Optional[str]]:
        """Check if request is out of this agent's scope.
        
        Args:
            user_input: User's message
        
        Returns:
            Tuple of (is_out_of_scope, suggested_agent)
        """
        # Default: not out of scope
        return False, None
    
    def is_multi_domain(self, user_input: str) -> bool:
        """Check if request involves multiple domains.
        
        Multi-domain tasks should be escalated to MainAgent.
        
        Args:
            user_input: User's message
        
        Returns:
            True if multi-domain task detected
        """
        # Default: not multi-domain
        return False
    
    def _prune_tool_output_for_llm(self, tool_name: str, tool_result: Any) -> str:
        """
        Prune verbose tool outputs before sending to LLM context.
        
        This reduces context size by 84% WITHOUT affecting application logic.
        The full tool_result is still available to the application.
        
        Feature can be disabled via ENABLE_CONTEXT_PRUNING=0 env var.
        
        Args:
            tool_name: Name of the tool that was executed
            tool_result: Full result from tool execution
        
        Returns:
            Pruned string representation for LLM context
        """
        import os
        
        # Feature flag for easy rollback
        if os.getenv("ENABLE_CONTEXT_PRUNING", "1") != "1":
            logger.info(f"[{self.name}] ⚠️  Context pruning DISABLED via ENABLE_CONTEXT_PRUNING=0")
            return str(tool_result)
        
        logger.debug(f"[{self.name}] 🔍 Pruning tool: {tool_name}, result type: {type(tool_result)}")
        
        # If result is not a dict/list, return as-is
        if not isinstance(tool_result, (dict, list)):
            return str(tool_result)
        
        # Calculate token savings for logging
        original_str = str(tool_result)
        original_tokens = len(original_str) // 4  # Rough estimate (4 chars per token)
        
        # Prune based on tool type
        pruned_str = original_str
        if tool_name == "list_docs":
            pruned_str = self._prune_list_docs(tool_result)
        elif tool_name == "get_numbers":
            pruned_str = self._prune_get_numbers(tool_result)
        # Other tools: return as-is (already optimal or not verbose)
        
        # Log savings if significant
        pruned_tokens = len(pruned_str) // 4
        if pruned_tokens < original_tokens * 0.5:  # More than 50% reduction
            savings_pct = int((1 - pruned_tokens / original_tokens) * 100)
            logger.info(f"[{self.name}] 🔥 Pruned {tool_name}: {original_tokens} → {pruned_tokens} tokens ({savings_pct}% reduction)")
        
        return pruned_str
    
    def _prune_list_docs(self, docs: Any) -> str:
        """
        Prune list_docs output to reduce token count by 90%.
        
        Strategy:
        - Show ALL uploaded docs (important for operations)
        - Group pending docs by category with samples
        - Preserve counts for agent reasoning
        
        Args:
            docs: Raw list_docs result (list of document dicts)
        
        Returns:
            Compact string representation
        """
        logger.debug(f"[{self.name}] 📋 _prune_list_docs called with type: {type(docs)}, len: {len(docs) if isinstance(docs, list) else 'N/A'}")
        
        if not isinstance(docs, list):
            logger.warning(f"[{self.name}] ⚠️  list_docs returned non-list: {type(docs)}")
            return str(docs)
        
        # Separate uploaded vs pending
        uploaded = [d for d in docs if d.get("storage_key")]
        pending = [d for d in docs if not d.get("storage_key")]
        
        # Build pruned output
        pruned = {
            "total": len(docs),
            "uploaded": len(uploaded),
            "pending": len(pending)
        }
        
        # Show ALL uploaded docs (these are critical for operations)
        if uploaded:
            pruned["uploaded_docs"] = [
                {
                    "name": d.get("document_name"),
                    "group": d.get("document_group"),
                    "subgroup": d.get("document_subgroup", "")
                }
                for d in uploaded[:20]  # Max 20 to prevent bloat if many uploaded
            ]
            if len(uploaded) > 20:
                pruned["uploaded_note"] = f"Showing 20 of {len(uploaded)} uploaded documents"
        
        # Group pending docs by category (much more compact)
        if pending:
            from collections import defaultdict
            pending_groups = defaultdict(list)
            
            for doc in pending:
                group = doc.get("document_group", "Unknown")
                subgroup = doc.get("document_subgroup", "")
                key = f"{group}/{subgroup}" if subgroup else group
                pending_groups[key].append(doc.get("document_name", "Unknown"))
            
            # Show first 3 docs per group, then count
            pruned["pending_by_group"] = {}
            for group_key, doc_names in pending_groups.items():
                if len(doc_names) <= 3:
                    pruned["pending_by_group"][group_key] = doc_names
                else:
                    pruned["pending_by_group"][group_key] = [
                        doc_names[0],
                        doc_names[1],
                        doc_names[2],
                        f"... and {len(doc_names) - 3} more"
                    ]
        
        return str(pruned)
    
    def _prune_get_numbers(self, numbers: Any) -> str:
        """
        Prune get_numbers output to show only non-zero values.
        
        Strategy:
        - Filter out zeros and None (not useful for LLM)
        - Show counts for context
        - Preserve all filled values (needed for calculations)
        
        Args:
            numbers: Raw get_numbers result (dict of item_key: value)
        
        Returns:
            Compact string representation
        """
        if not isinstance(numbers, dict):
            return str(numbers)
        
        # Filter out zeros and None
        filled = {k: v for k, v in numbers.items() if v and v != 0}
        empty_count = len(numbers) - len(filled)
        
        # Build pruned output
        pruned = {
            "total_items": len(numbers),
            "filled_items": len(filled),
            "empty_items": empty_count,
            "values": filled
        }
        
        if empty_count > 0:
            pruned["note"] = f"{len(filled)} filled, {empty_count} empty (zeros hidden for clarity)"
        
        return str(pruned)
    
    def run(self, 
            user_input: str, 
            property_id: Optional[str] = None,
            context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Run the agent on user input with bidirectional routing support.
        
        Args:
            user_input: User's message
            property_id: Current property ID
            context: Additional context (history, etc.)
        
        Returns:
            Dict with action, response, and routing metadata
            
            Actions:
            - "complete": Task completed successfully
            - "redirect": Needs redirection to another agent
            - "escalate": Needs escalation to MainAgent
            - "error": Error occurred, fallback needed
        """
        start_time = time.time()
        
        try:
            logger.info(f"[{self.name}] Processing: '{user_input[:50]}...'")
            
            # Check if multi-domain task FIRST (higher priority than redirect)
            if self.is_multi_domain(user_input):
                logger.info(f"[{self.name}] ⬆️ Multi-domain task detected, escalating to MainAgent")
                return {
                    "action": "escalate",
                    "reason": "multi_domain_task",
                    "original_input": user_input,
                    "from_agent": self.name,
                    "latency_ms": int((time.time() - start_time) * 1000)
                }
            
            # Check if out of scope (enables bidirectional routing)
            is_out, suggested_agent = self.is_out_of_scope(user_input)
            if is_out:
                logger.info(f"[{self.name}] 🔄 Out of scope, suggesting {suggested_agent}")
                return {
                    "action": "redirect",
                    "to_agent": suggested_agent,
                    "reason": "out_of_scope",
                    "original_input": user_input,
                    "from_agent": self.name,
                    "latency_ms": int((time.time() - start_time) * 1000)
                }
            
            # Build messages
            # Try to pass intent, property_name and numbers_template to system prompt if available in context
            intent = context.get("intent") if context else None
            property_name = context.get("property_name") if context else None
            numbers_template = context.get("numbers_template") if context else None
            
            try:
                # Try to call with all parameters (modular agents)
                system_prompt = self.get_system_prompt(intent=intent, property_name=property_name, numbers_template=numbers_template)
            except TypeError:
                try:
                    # Try with just intent (new modular agents)
                    system_prompt = self.get_system_prompt(intent=intent)
                except TypeError:
                    try:
                        # Try to call with property_name and numbers_template parameters (NumbersAgent supports this)
                        system_prompt = self.get_system_prompt(property_name=property_name, numbers_template=numbers_template)
                    except TypeError:
                        try:
                            # Try with just property_name
                            system_prompt = self.get_system_prompt(property_name=property_name)
                        except TypeError:
                            # Fallback for agents that don't accept any parameters
                            system_prompt = self.get_system_prompt()
            
            messages = [
                SystemMessage(content=system_prompt)
            ]
            
            # CRITICAL: Add property_id to context so LLM knows the actual UUID
            if property_id:
                messages.append(SystemMessage(content=f"IMPORTANTE: El property_id actual es: {property_id}\nCuando llames a herramientas que requieren property_id, usa EXACTAMENTE este valor, NO uses placeholders como 'current_property_id'."))
            
            # Add context if provided
            if context and context.get("history"):
                # CRITICAL: Detect if we're in the middle of a multi-turn flow
                # This prevents agents from showing unnecessary information to user
                history = context["history"]
                
                # Check if agent asked for email and user just provided it
                if len(history) >= 2:
                    last_ai = history[-2] if len(history) >= 2 else None
                    last_human = history[-1] if len(history) >= 1 else None
                    
                    from langchain_core.messages import AIMessage, HumanMessage
                    if isinstance(last_ai, AIMessage) and isinstance(last_human, HumanMessage):
                        ai_content = str(last_ai.content).lower()
                        human_content = str(last_human.content).lower()
                        
                        # Pattern: AI asked for email, user provided email
                        if ("correo" in ai_content or "email" in ai_content) and ("@" in human_content):
                            # Find what document was requested in previous messages
                            original_request = None
                            for msg in reversed(history[:-2]):  # Exclude last 2 (question + answer)
                                if isinstance(msg, HumanMessage):
                                    content = str(msg.content).lower()
                                    if any(kw in content for kw in ["manda", "envia", "envía", "email", "correo"]):
                                        original_request = msg.content
                                        break
                            
                            if original_request:
                                messages.append(SystemMessage(content=f"""🎯 CONTINUACIÓN DE FLUJO DETECTADA:
- Petición original: "{original_request}"
- Ya preguntaste por el email
- Usuario acaba de proporcionar: {last_human.content}

INSTRUCCIONES CRÍTICAS:
1. Llama a list_docs INTERNAMENTE (sin mostrar al usuario)
2. Busca el documento que coincida con la petición original
3. Llama a signed_url_for con los metadatos exactos
4. Llama a send_email con el email proporcionado
5. RESPONDE SOLO: "✅ He enviado [documento] a [email]"

❌ NO MUESTRES la lista de documentos al usuario
❌ NO preguntes nada más
✅ EJECUTA el flujo completo y confirma el envío"""))
                
                # CRITICAL: Smart truncation with context summary to prevent rate limit errors (429)
                # Keep last 12 messages + add a context summary for older messages
                MAX_HISTORY = 12
                
                if len(history) > MAX_HISTORY:
                    # Build context summary from older messages
                    older_messages = history[:-MAX_HISTORY]
                    recent_messages = history[-MAX_HISTORY:]
                    
                    # Extract key context from older messages
                    context_summary_parts = []
                    
                    # Get intent from context
                    intent = context.get("intent") or context.get("original_intent")
                    if intent:
                        context_summary_parts.append(f"- Intent actual: {intent}")
                    
                    # Get failed agent if this is a fallback
                    failed_agent = context.get("failed_agent")
                    if failed_agent:
                        context_summary_parts.append(f"- ⚠️ El agente {failed_agent} falló, CONTINÚA con el mismo intent")
                    
                    # Summarize what was discussed in older messages
                    topics_discussed = set()
                    for msg in older_messages:
                        content = str(getattr(msg, 'content', '')).lower()
                        if 'documento' in content or 'docs' in content:
                            topics_discussed.add("documentos")
                        if 'número' in content or 'numeros' in content or 'plantilla' in content:
                            topics_discussed.add("números/plantilla")
                        if 'propiedad' in content:
                            topics_discussed.add("propiedades")
                        if 'email' in content or 'correo' in content:
                            topics_discussed.add("emails")
                        if 'r2b' in content:
                            # Check context to determine if R2B is about docs or numbers
                            if 'documento' in content or 'compra' in content or 'estrategia' in content:
                                topics_discussed.add("estrategia documental R2B")
                            elif 'plantilla' in content or 'número' in content:
                                topics_discussed.add("plantilla números R2B")
                    
                    if topics_discussed:
                        context_summary_parts.append(f"- Temas previos: {', '.join(topics_discussed)}")
                    
                    # CRITICAL: Include last_rag_answer if available (for email sending)
                    if context.get("last_rag_answer"):
                        # Truncate if too long, but keep enough for context
                        rag_answer = context["last_rag_answer"]
                        if len(rag_answer) > 500:
                            rag_answer = rag_answer[:500] + "..."
                        context_summary_parts.append(f"\n🔍 ÚLTIMO RESUMEN RAG (para enviar por email si el usuario lo pide):\n{rag_answer}")
                        logger.info(f"[{self.name}] 📧 Added last_rag_answer to context (len={len(context['last_rag_answer'])})")
                    
                    # Add context summary as a system message
                    if context_summary_parts:
                        context_summary = "📋 RESUMEN DE CONTEXTO (mensajes anteriores truncados):\n" + "\n".join(context_summary_parts)
                        messages.append(SystemMessage(content=context_summary))
                        logger.info(f"[{self.name}] Added context summary: {context_summary_parts}")
                    
                    limited_history = recent_messages
                    logger.info(f"[{self.name}] Smart truncation: {len(history)} → {len(limited_history)} messages (+ context summary)")
                else:
                    limited_history = history
                    logger.info(f"[{self.name}] Loading {len(limited_history)} messages from history")
                    
                    # Even without truncation, add last_rag_answer if available
                    if context.get("last_rag_answer"):
                        rag_answer = context["last_rag_answer"]
                        if len(rag_answer) > 500:
                            rag_answer = rag_answer[:500] + "..."
                        messages.append(SystemMessage(content=f"🔍 ÚLTIMO RESUMEN RAG (para enviar por email si el usuario lo pide):\n{rag_answer}"))
                        logger.info(f"[{self.name}] 📧 Added last_rag_answer to context (no truncation, len={len(context['last_rag_answer'])})")
                
                messages.extend(limited_history)
            
            # Add user message
            messages.append(HumanMessage(content=user_input))
            
            # CRITICAL: Sanitize messages to remove orphaned tool_calls
            # This prevents OpenAI 400 errors when history has AIMessage with tool_calls
            # but their corresponding ToolMessages were truncated/removed
            from langchain_core.messages import AIMessage as LCAIMessage, ToolMessage as LCToolMessage
            
            cleaned_messages = []
            for i, msg in enumerate(messages):
                if isinstance(msg, LCAIMessage) and hasattr(msg, "tool_calls") and msg.tool_calls:
                    # This AIMessage has tool_calls, verify if all have responses
                    tool_call_ids = {tc.get("id") for tc in msg.tool_calls if tc.get("id")}
                    
                    # Search for ToolMessages that respond to these tool_calls
                    answered_ids = set()
                    for j in range(i + 1, len(messages)):
                        if isinstance(messages[j], LCToolMessage):
                            tc_id = getattr(messages[j], "tool_call_id", None)
                            if tc_id in tool_call_ids:
                                answered_ids.add(tc_id)
                        elif isinstance(messages[j], LCAIMessage):
                            # Next AIMessage, stop searching
                            break
                    
                    # If some tool_calls are unanswered, remove them or skip this message
                    if tool_call_ids != answered_ids:
                        logger.warning(f"[{self.name}] Skipping orphaned AIMessage with unanswered tool_calls: {tool_call_ids - answered_ids}")
                        continue
                
                # If it's a ToolMessage, verify its parent AIMessage is in cleaned_messages
                if isinstance(msg, LCToolMessage):
                    tc_id = getattr(msg, "tool_call_id", None)
                    if tc_id:
                        # Search for parent AIMessage in cleaned_messages
                        found_parent = False
                        for parent_msg in reversed(cleaned_messages):
                            if isinstance(parent_msg, LCAIMessage) and hasattr(parent_msg, "tool_calls"):
                                parent_tcs = parent_msg.tool_calls or []
                                if any(tc.get("id") == tc_id for tc in parent_tcs):
                                    found_parent = True
                                    break
                        
                        if not found_parent:
                            logger.warning(f"[{self.name}] Skipping orphaned ToolMessage with id: {tc_id}")
                            continue
                
                cleaned_messages.append(msg)
            
            messages = cleaned_messages
            logger.info(f"[{self.name}] Sanitized messages: {len(messages)} total (removed orphaned tool_calls)")
            
            # Get tools
            tools = self.get_tools()
            logger.info(f"[{self.name}] 🔧 Binding {len(tools)} tools: {[t.name for t in tools]}")
            
            # Bind tools to LLM
            llm_with_tools = self.llm.bind_tools(tools) if tools else self.llm
            
            # ReAct Loop: Execute tools until LLM says it's done
            max_iterations = 5
            iteration = 0
            llm_latency_ms = 0
            
            while iteration < max_iterations:
                iteration += 1
                logger.debug(f"[{self.name}] ReAct iteration {iteration}/{max_iterations}")
                
                # Invoke LLM
                llm_start = time.time()
                response = llm_with_tools.invoke(messages)
                llm_latency_ms += int((time.time() - llm_start) * 1000)
                
                # Check if LLM wants to use tools
                tool_calls = getattr(response, "tool_calls", [])
                
                if not tool_calls:
                    # No tools to execute, we're done
                    logger.info(f"[{self.name}] No tool calls, finishing after {iteration} iterations")
                    break
                
                # Execute tools
                logger.info(f"[{self.name}] Executing {len(tool_calls)} tool(s)")
                messages.append(AIMessage(content=response.content or "", tool_calls=tool_calls))
                
                for tool_call in tool_calls:
                    tool_name = tool_call.get("name")
                    tool_args = tool_call.get("args", {})
                    tool_id = tool_call.get("id", "unknown")
                    
                    logger.info(f"[{self.name}] Calling tool: {tool_name} with args: {tool_args}")
                    
                    try:
                        # Find and execute the tool
                        tool_obj = next((t for t in tools if t.name == tool_name), None)
                        if not tool_obj:
                            raise ValueError(f"Tool '{tool_name}' not found")
                        
                        # Execute tool
                        tool_result = tool_obj.invoke(tool_args)
                        logger.info(f"[{self.name}] Tool {tool_name} result: {str(tool_result)[:200]}")
                        
                        # Add tool result to messages (with context pruning for LLM efficiency)
                        # NOTE: tool_result object is unchanged - only LLM context is pruned
                        messages.append(ToolMessage(
                            content=self._prune_tool_output_for_llm(tool_name, tool_result),
                            tool_call_id=tool_id,
                            name=tool_name
                        ))
                        
                    except Exception as e:
                        logger.error(f"[{self.name}] Tool {tool_name} failed: {e}", exc_info=True)
                        messages.append(ToolMessage(
                            content=f"Error: {str(e)}",
                            tool_call_id=tool_id,
                            name=tool_name
                        ))
                
                # Continue loop to let LLM see tool results
            
            if iteration >= max_iterations:
                logger.warning(f"[{self.name}] Reached max iterations ({max_iterations})")
            
            # Track LLM call metrics
            try:
                # Logfire records metrics automatically via instrumentation
                # Only need to capture explicit cost if needed, but Logfire does it too
                pass
            except Exception as e:
                logger.warning(f"[{self.name}] Failed to record LLM metrics: {e}")
            
            # Extract response
            result = {
                "action": "complete",
                "agent": self.name,
                "response": response.content,
                "tool_calls": response.tool_calls if hasattr(response, "tool_calls") else [],
                "latency_ms": int((time.time() - start_time) * 1000),
                "model": self.model,
                "success": True
            }
            
            # CRITICAL: If set_current_property was called, extract property_id from tool results
            # This ensures property switches are propagated to the UI
            logger.info(f"[{self.name}] 🔍 Searching for set_current_property in {len(messages)} messages")
            for i, msg in enumerate(messages):
                if isinstance(msg, ToolMessage):
                    logger.info(f"[{self.name}] 🔍 Found ToolMessage #{i}: name={msg.name}, content_type={type(msg.content).__name__}")
                    if msg.name == "set_current_property":
                        logger.info(f"[{self.name}] 🎯 Found set_current_property! Content: {str(msg.content)[:200]}")
                        try:
                            import json
                            # Handle both string JSON and dict
                            if isinstance(msg.content, str):
                                try:
                                    tool_result = json.loads(msg.content)
                                    logger.info(f"[{self.name}] ✅ Parsed JSON: {tool_result}")
                                except json.JSONDecodeError as json_err:
                                    # If JSON parsing fails, skip this message
                                    logger.warning(f"[{self.name}] ❌ Could not parse tool result as JSON: {json_err}")
                                    continue
                            elif isinstance(msg.content, dict):
                                tool_result = msg.content
                                logger.info(f"[{self.name}] ✅ Using dict directly: {tool_result}")
                            else:
                                # Unknown type, skip
                                logger.warning(f"[{self.name}] ❌ Unknown content type: {type(msg.content)}")
                                continue
                            
                            if tool_result and isinstance(tool_result, dict) and tool_result.get("property_id"):
                                result["property_id"] = tool_result["property_id"]
                                logger.info(f"[{self.name}] 📍 Extracted property_id from set_current_property: {tool_result['property_id']}")
                                break
                            else:
                                logger.warning(f"[{self.name}] ⚠️ tool_result doesn't have property_id: {tool_result}")
                        except Exception as e:
                            logger.warning(f"[{self.name}] Failed to extract property_id from tool result: {e}", exc_info=True)
            
            logger.info(f"[{self.name}] ✅ Response generated in {result['latency_ms']}ms")
            return result
        
        except Exception as e:
            logger.error(f"[{self.name}] ❌ Error: {e}", exc_info=True)
            return {
                "action": "error",
                "agent": self.name,
                "response": f"Lo siento, ocurrió un error: {str(e)}",
                "error": str(e),
                "fallback_to": "MainAgent",
                "latency_ms": int((time.time() - start_time) * 1000),
                "success": False
            }
    
    def __repr__(self):
        return f"<{self.name} model={self.model}>"

