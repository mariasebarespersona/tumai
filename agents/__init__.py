"""
Multi-Agent System for RAMA.

Exports:
- PropertyAgent: Property management
- NumbersAgent: Numbers Table (R2B) operations
- DocsAgent: Document management
- BaseAgent: Base class for all agents
"""

from .base_agent import BaseAgent
from .property_agent import PropertyAgent
from .numbers_agent import NumbersAgent
from .docs_agent import DocsAgent

__all__ = [
    "BaseAgent",
    "PropertyAgent",
    "NumbersAgent",
    "DocsAgent"
]

