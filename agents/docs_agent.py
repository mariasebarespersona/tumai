"""
DocsAgent - Specialized agent for document management.

Handles:
- Uploading documents
- Sending documents by email
- Listing documents
- Managing invoices (facturas)
"""

from typing import List
from .base_agent import BaseAgent
from tools.registry import (
    upload_and_link_tool,
    send_email_tool,
    list_docs_tool,
    signed_url_for_tool,
    list_related_facturas_tool,
    qa_document_tool,
    rag_qa_with_citations_tool,
    qa_payment_schedule_tool,
    summarize_document_tool,
    delete_document_tool  # NEW - Delete single document
)


class DocsAgent(BaseAgent):
    """Agent specialized in document management operations."""
    
    def __init__(self):
        # TEMPORARY: Using gpt-4o-mini to avoid rate limiting (30K TPM exceeded)
        # Can revert to gpt-4o once OpenAI account is upgraded to higher tier
        super().__init__(name="DocsAgent", model="gpt-4o-mini", temperature=0.5)
    
    # No override needed - BaseAgent.run() with ReAct loop handles everything
    def get_system_prompt(self, intent: str = None) -> str:
        """Get system prompt using modular prompt loader."""
        import sys
        import os
        
        # Add prompts directory to path
        prompts_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "prompts")
        if prompts_dir not in sys.path:
            sys.path.insert(0, prompts_dir)
        
        from prompt_loader import build_agent_prompt
        
        return build_agent_prompt("docs_agent", intent)
    
    def get_tools(self) -> List:
        """Return docs-specific tools."""
        return [
            upload_and_link_tool,
            send_email_tool,
            list_docs_tool,
            signed_url_for_tool,
            list_related_facturas_tool,
            rag_qa_with_citations_tool,
            qa_payment_schedule_tool,
            summarize_document_tool,
            qa_document_tool,
            delete_document_tool  # NEW - Delete single document
        ]

