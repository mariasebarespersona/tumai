from __future__ import annotations
import re
from time import perf_counter
import logging

logger = logging.getLogger("router")

CELL_RE = re.compile(r"\b([A-Z]{1,3}[0-9]{1,4})\b", re.I)

class Router:
    def predict(self, user_text: str, context: dict | None = None) -> tuple[str, float]:
        s = (user_text or "").lower()
        # docs email
        if any(v in s for v in ["manda", "envía", "enviame", "mandame", "por email", "por correo", "por mail"]):
            return ("docs.send_email", 0.85)
        # numbers set cell
        if any(v in s for v in ["pon", "escribe", "actualiza", "coloca", "meter", "establece"]) and CELL_RE.search(s):
            return ("numbers.set_cell", 0.8)
        # numbers clear
        if any(v in s for v in ["borra", "elimina", "limpia"]) and CELL_RE.search(s):
            return ("numbers.clear_cell", 0.8)
        # numbers export
        if any(v in s for v in ["exporta", "descarga", "excel de números", "plantilla de números"]) and "email" not in s:
            return ("numbers.export", 0.7)
        # docs list
        if "document" in s or "documento" in s or "documentos" in s:
            return ("docs.list", 0.65)
        # fallback
        return ("general", 0.5)

    async def decide(self, user_text: str, context: dict | None = None) -> dict:
        t0 = perf_counter()
        intent, confidence = self.predict(user_text, context or {})
        latency_ms = int((perf_counter() - t0) * 1000)
        decision = {"intent": intent, "confidence": confidence, "latency_ms": latency_ms}
        logger.info(f"[router] decision={decision} session={context.get('session_id') if context else None}")
        return decision

