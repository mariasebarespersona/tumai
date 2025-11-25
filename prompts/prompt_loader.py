"""
Modular Prompt Loader with Cache

Loads prompts from markdown files and combines them based on agent + intent.
Implements caching for performance.
"""

import os
from pathlib import Path
from typing import Optional, Dict
import logging

logger = logging.getLogger(__name__)

# Cache for loaded prompts (file_path -> content)
_PROMPT_CACHE: Dict[str, str] = {}


def load_prompt(relative_path: str, use_cache: bool = True) -> str:
    """
    Load a prompt from a markdown file.
    
    Args:
        relative_path: Path relative to prompts/ directory (e.g., "agents/docs_agent/_base.md")
        use_cache: Whether to use cached version (default: True)
    
    Returns:
        Prompt content as string
    
    Raises:
        FileNotFoundError: If prompt file doesn't exist
    """
    # Get absolute path to prompts directory
    prompts_dir = Path(__file__).parent
    file_path = prompts_dir / relative_path
    
    # Check cache first
    cache_key = str(file_path)
    if use_cache and cache_key in _PROMPT_CACHE:
        logger.debug(f"[prompt_loader] Cache hit: {relative_path}")
        return _PROMPT_CACHE[cache_key]
    
    # Load from file
    if not file_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {file_path}")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read().strip()
    
    # Cache it
    _PROMPT_CACHE[cache_key] = content
    logger.debug(f"[prompt_loader] Loaded and cached: {relative_path}")
    
    return content


def build_agent_prompt(agent_name: str, intent: Optional[str] = None) -> str:
    """
    Build complete prompt for an agent based on intent.
    
    Args:
        agent_name: Name of agent (e.g., "docs_agent", "property_agent", "main_agent")
        intent: Optional intent for specialized instructions (e.g., "docs.send_email", "general.chat")
    
    Returns:
        Complete system prompt
    """
    parts = []
    
    # 1. Load base prompt (always included)
    try:
        base = load_prompt(f"agents/{agent_name}/_base.md")
        parts.append(base)
        logger.info(f"[prompt_loader] Built prompt for {agent_name} (base only)")
    except FileNotFoundError:
        logger.error(f"[prompt_loader] Base prompt not found for {agent_name}")
        raise
    
    # 2. If intent provided, try to load intent-specific prompt
    if intent:
        # Special mapping for main_agent intents that involve email
        # This ensures we load the email.md module for any email-related intent
        if agent_name == "main_agent":
            intent_modules = _get_main_agent_modules(intent)
        else:
            # For specialized agents (docs_agent, etc.), use simple mapping
            # Examples: "docs.send_email" -> "send_email.md"
            #           "docs.list" -> "list.md"
            intent_modules = [intent.split(".")[-1]]  # Get last part after dot
        
        # Load all relevant modules
        for module_name in intent_modules:
            intent_file = module_name if module_name.endswith(".md") else f"{module_name}.md"
            intent_path = f"agents/{agent_name}/{intent_file}"
            
            try:
                specific = load_prompt(intent_path)
                parts.append("\n\n---\n## 🎯 TAREA ACTUAL\n\n" + specific)
                logger.info(f"[prompt_loader] Added module: {module_name} for intent '{intent}'")
            except FileNotFoundError:
                logger.debug(f"[prompt_loader] Module '{module_name}' not found, skipping")
        
        if not any("🎯 TAREA ACTUAL" in part for part in parts):
            logger.warning(f"[prompt_loader] No specific prompt modules found for intent '{intent}', using base only")
    
    return "\n\n".join(parts)


def _get_main_agent_modules(intent: str) -> list[str]:
    """
    Map main_agent intents to prompt modules.
    
    Returns list of module names to load (without .md extension).
    """
    # Intent mappings for main_agent
    # Key: intent pattern, Value: list of modules to load
    intent_map = {
        # Email-related intents
        "docs.email": ["email"],
        "docs.send_email": ["email"],
        "email": ["email"],
        
        # Document intents
        "docs.list": ["documents"],
        "docs.upload": ["documents"],
        
        # Numbers intents
        "numbers.set_cell": ["numbers"],
        "numbers.get": ["numbers"],
        "numbers.export": ["numbers"],
        
        # Property intents
        "property.create": ["property"],
        "property.list": ["property"],
        "property.select": ["property"],
        
        # General/fallback
        "general.chat": [],  # Base only
    }
    
    # Try exact match first
    if intent in intent_map:
        return intent_map[intent]
    
    # Try partial matches (e.g., if intent is "docs.email.something", match "docs.email")
    for pattern, modules in intent_map.items():
        if intent.startswith(pattern):
            return modules
    
    # Fallback: try to extract module name from intent
    # E.g., "docs.send_email" -> ["send_email"]
    if "." in intent:
        return [intent.split(".")[-1]]
    
    # No match, return empty (base only)
    return []


def clear_cache():
    """Clear the prompt cache. Useful for development/testing."""
    global _PROMPT_CACHE
    _PROMPT_CACHE.clear()
    logger.info("[prompt_loader] Cache cleared")


def get_cache_stats() -> Dict[str, int]:
    """Get cache statistics."""
    return {
        "cached_prompts": len(_PROMPT_CACHE),
        "total_chars": sum(len(v) for v in _PROMPT_CACHE.values())
    }

