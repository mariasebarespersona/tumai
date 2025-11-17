from __future__ import annotations
import os

BASE = os.path.join(os.path.dirname(__file__), "base_policy.md")
TASKS = {
    "numbers": os.path.join(os.path.dirname(__file__), "tasks", "numbers.md"),
    "docs": os.path.join(os.path.dirname(__file__), "tasks", "docs.md"),
}

def _read(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return ""

def load_prompt_for_intent(intent: str | None) -> str:
    """Compose a slim system prompt from base_policy + task file for the domain inferred from intent."""
    base = _read(BASE)
    if not intent:
        return base
    domain = "numbers" if str(intent).startswith("numbers") else "docs" if str(intent).startswith("docs") else None
    task = _read(TASKS.get(domain, "")) if domain else ""
    return (base + "\n\n" + task).strip()

