from __future__ import annotations
import json, os, logging
from typing import Tuple, Dict, Any

logger = logging.getLogger(__name__)

_registry_cache: Dict[str, Any] | None = None

def _load_registry() -> Dict[str, Any]:
    global _registry_cache
    if _registry_cache is not None:
        return _registry_cache
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "tool_registry.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            _registry_cache = json.load(f)
    except Exception as e:
        logger.warning(f"[contracts] Could not load tool_registry.json: {e}")
        _registry_cache = {}
    return _registry_cache

def validate_tool_call(tool_name: str, args: Dict[str, Any]) -> Tuple[bool, str]:
    reg = _load_registry()
    spec = reg.get(tool_name)
    if not spec:
        # Skip unknown tools to avoid false negatives/noise
        return True, "skip"
    expected: Dict[str, str] = spec.get("input_schema", {})
    missing = [k for k, t in expected.items() if not k.endswith("?") and k not in args]
    if missing:
        return False, f"missing fields: {missing}"
    return True, "ok"

