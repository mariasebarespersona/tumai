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
    
    def __init__(self, name: str, model: str = "gpt-4o", temperature: float = 0.7):
        """Initialize the agent.
        
        Args:
            name: Agent name (e.g., "PropertyAgent")
            model: LLM model to use
            temperature: Temperature for LLM
        """
        self.name = name
        self.model = model
        self.temperature = temperature
        self.llm = ChatOpenAI(model=model, temperature=temperature)
        logger.info(f"[{self.name}] Initialized with model={model}, temp={temperature}")
    
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
            # Try to pass property_name and numbers_template to system prompt if available in context
            property_name = context.get("property_name") if context else None
            numbers_template = context.get("numbers_template") if context else None
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
                messages.extend(context["history"])
            
            # Add user message
            messages.append(HumanMessage(content=user_input))
            
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
                        
                        # Add tool result to messages
                        messages.append(ToolMessage(
                            content=str(tool_result),
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
                from tools.metrics_collector import record_llm_call
                
                # Extract token usage if available
                prompt_tokens = 0
                completion_tokens = 0
                cost_usd = 0.0
                
                if hasattr(response, "response_metadata"):
                    metadata = response.response_metadata
                    if "token_usage" in metadata:
                        usage = metadata["token_usage"]
                        prompt_tokens = usage.get("prompt_tokens", 0)
                        completion_tokens = usage.get("completion_tokens", 0)
                        
                        # Calculate cost based on model
                        if "gpt-4o" in self.model:
                            # GPT-4o pricing: $2.50 per 1M input tokens, $10.00 per 1M output tokens
                            cost_usd = (prompt_tokens * 0.0000025) + (completion_tokens * 0.00001)
                        elif "gpt-4o-mini" in self.model:
                            # GPT-4o-mini pricing: $0.150 per 1M input tokens, $0.600 per 1M output tokens
                            cost_usd = (prompt_tokens * 0.00000015) + (completion_tokens * 0.0000006)
                
                record_llm_call(
                    model=self.model,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    cost_usd=cost_usd,
                    latency_ms=llm_latency_ms,
                    agent=self.name
                )
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

