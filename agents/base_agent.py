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
    
    def run(self, 
            user_input: str, 
            property_id: Optional[str] = None,
            context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Run the agent on user input.
        
        Args:
            user_input: User's message
            property_id: Current property ID
            context: Additional context (history, etc.)
        
        Returns:
            Dict with response, tool_calls, metadata
        """
        start_time = time.time()
        
        try:
            logger.info(f"[{self.name}] Processing: '{user_input[:50]}...'")
            
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
                "agent": self.name,
                "response": f"Lo siento, ocurrió un error: {str(e)}",
                "tool_calls": [],
                "latency_ms": int((time.time() - start_time) * 1000),
                "error": str(e),
                "success": False
            }
    
    def __repr__(self):
        return f"<{self.name} model={self.model}>"

