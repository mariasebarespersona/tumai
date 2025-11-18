"""
Base Agent class for all specialized agents.

All agents inherit from this base class and override:
- get_system_prompt()
- get_tools()
"""

from typing import Dict, List, Any, Optional
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_openai import ChatOpenAI
import logging
import time

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
            
            # Check if multi-domain task (escalate to MainAgent)
            if self.is_multi_domain(user_input):
                logger.info(f"[{self.name}] ⬆️ Multi-domain task detected, escalating to MainAgent")
                return {
                    "action": "escalate",
                    "reason": "multi_domain_task",
                    "original_input": user_input,
                    "from_agent": self.name,
                    "latency_ms": int((time.time() - start_time) * 1000)
                }
            
            # Build messages
            messages = [
                SystemMessage(content=self.get_system_prompt())
            ]
            
            # Add context if provided
            if context and context.get("history"):
                messages.extend(context["history"])
            
            # Add user message
            messages.append(HumanMessage(content=user_input))
            
            # Get tools
            tools = self.get_tools()
            logger.debug(f"[{self.name}] Using {len(tools)} tools")
            
            # Bind tools to LLM
            llm_with_tools = self.llm.bind_tools(tools) if tools else self.llm
            
            # Invoke LLM
            response = llm_with_tools.invoke(messages)
            
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

