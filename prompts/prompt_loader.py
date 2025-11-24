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
        agent_name: Name of agent (e.g., "docs_agent", "property_agent")
        intent: Optional intent for specialized instructions (e.g., "docs.send_email")
    
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
        # Map intent to file name
        # Examples: "docs.send_email" -> "send_email.md"
        #           "docs.list" -> "list.md"
        intent_file = intent.split(".")[-1] + ".md"  # Get last part after dot
        intent_path = f"agents/{agent_name}/{intent_file}"
        
        try:
            specific = load_prompt(intent_path)
            parts.append("\n\n---\n## 🎯 TAREA ACTUAL\n\n" + specific)
            logger.info(f"[prompt_loader] Added intent-specific prompt: {intent}")
        except FileNotFoundError:
            logger.warning(f"[prompt_loader] No specific prompt for intent '{intent}', using base only")
    
    return "\n\n".join(parts)


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

