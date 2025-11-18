"""
Active Router - Routes requests to specialized agents.

This router:
1. Classifies user intent with confidence
2. Routes to specialized agents (PropertyAgent, NumbersAgent, DocsAgent)
3. Falls back to MainAgent for low confidence or complex queries
"""

from __future__ import annotations
import re
import logging
from time import perf_counter
from typing import Tuple, Dict, Optional

logger = logging.getLogger("active_router")

# Cell reference pattern
CELL_RE = re.compile(r"\b([A-Z]{1,3}[0-9]{1,4})\b", re.I)

# Confidence thresholds for routing to specialized agents
CONFIDENCE_THRESHOLDS = {
    "property": 0.75,
    "numbers": 0.80,
    "docs": 0.85
}


class ActiveRouter:
    """
    Active router that classifies intent and routes to specialized agents.
    """
    
    def predict(self, user_text: str, context: Optional[Dict] = None) -> Tuple[str, float, str]:
        """
        Predict intent, confidence, and target agent.
        
        Args:
            user_text: User's message
            context: Optional context dict
        
        Returns:
            Tuple of (intent, confidence, target_agent)
        """
        s = (user_text or "").lower()
        
        # ========== PROPERTY OPERATIONS ==========
        if any(phrase in s for phrase in ["crear propiedad", "nueva propiedad", "crea casa", "crea villa"]):
            return ("property.create", 0.95, "PropertyAgent")
        
        if any(phrase in s for phrase in ["cambiar a", "cambio a", "trabajar con", "usar propiedad", "selecciona"]):
            if not any(x in s for x in ["números", "plantilla", "r2b"]):  # Not about numbers template
                return ("property.switch", 0.90, "PropertyAgent")
        
        if any(phrase in s for phrase in ["lista propiedades", "mis propiedades", "qué propiedades"]):
            return ("property.list", 0.92, "PropertyAgent")
        
        if "elimina propiedad" in s or "borra propiedad" in s:
            return ("property.delete", 0.90, "PropertyAgent")
        
        # ========== NUMBERS OPERATIONS ==========
        # High-priority: cell updates
        if any(verb in s for verb in ["pon", "escribe", "actualiza", "coloca"]) and CELL_RE.search(s):
            return ("numbers.set_cell", 0.95, "NumbersAgent")
        
        # Clear cell
        if any(verb in s for verb in ["borra", "elimina", "limpia"]) and CELL_RE.search(s):
            return ("numbers.clear_cell", 0.90, "NumbersAgent")
        
        # Export
        if any(word in s for word in ["exporta", "descarga"]) and ("r2b" in s or "números" in s or "plantilla" in s):
            if "email" not in s:
                return ("numbers.export", 0.88, "NumbersAgent")
        
        # Delete template
        if "elimina" in s and ("tabla" in s or "plantilla de números" in s):
            return ("numbers.delete_template", 0.85, "NumbersAgent")
        
        # Select template
        if ("números" in s or "r2b" in s or "plantilla" in s) and not any(x in s for x in ["email", "enviar"]):
            return ("numbers.select_template", 0.82, "NumbersAgent")
        
        # Send numbers by email
        if any(word in s for word in ["manda", "envía", "enviar"]) and ("números" in s or "r2b" in s or "plantilla" in s):
            return ("numbers.send_email", 0.90, "NumbersAgent")
        
        # ========== DOCS OPERATIONS ==========
        # Upload document
        if any(word in s for word in ["sube", "subir", "upload"]):
            return ("docs.upload", 0.92, "DocsAgent")
        
        # Send document by email (high priority)
        if any(word in s for word in ["manda", "envía", "enviar", "mandame", "enviame"]):
            # Check for document keywords
            if any(doc in s for doc in ["contrato", "factura", "escritura", "certificado", "documento", "plantilla"]):
                # But NOT if it's about números/R2B (already handled above)
                if not any(x in s for x in ["números", "r2b", "tabla"]):
                    return ("docs.send_email", 0.90, "DocsAgent")
        
        # List documents
        if "lista" in s and ("documentos" in s or "docs" in s):
            return ("docs.list", 0.88, "DocsAgent")
        
        # List facturas
        if "facturas" in s and ("asociadas" in s or "relacionadas" in s):
            return ("docs.list_facturas", 0.85, "DocsAgent")
        
        # ========== GENERAL/FALLBACK ==========
        if any(word in s for word in ["ayuda", "help", "qué puedes hacer", "cómo funciona"]):
            return ("general.help", 0.75, "MainAgent")
        
        # Default fallback
        return ("general.chat", 0.50, "MainAgent")
    
    async def decide(self, user_text: str, context: Optional[Dict] = None) -> Dict:
        """
        Decide which agent to route to.
        
        Args:
            user_text: User's message
            context: Optional context dict
        
        Returns:
            Dict with intent, confidence, target_agent, and latency_ms
        """
        t0 = perf_counter()
        intent, confidence, target_agent = self.predict(user_text, context or {})
        latency_ms = int((perf_counter() - t0) * 1000)
        
        decision = {
            "intent": intent,
            "confidence": confidence,
            "target_agent": target_agent,
            "latency_ms": latency_ms,
            "fallback_reason": None
        }
        
        # Check if confidence is too low for specialized agent
        if target_agent != "MainAgent":
            agent_category = intent.split(".")[0]  # e.g., "property", "numbers", "docs"
            threshold = CONFIDENCE_THRESHOLDS.get(agent_category, 0.8)
            
            if confidence < threshold:
                logger.warning(f"[active_router] Confidence {confidence:.2f} < threshold {threshold} for {agent_category}, falling back to MainAgent")
                decision["target_agent"] = "MainAgent"
                decision["fallback_reason"] = f"low_confidence ({confidence:.2f} < {threshold})"
        
        logger.info(
            f"[active_router] '{user_text[:40]}...' -> "
            f"intent={intent}, conf={confidence:.2f}, agent={decision['target_agent']}, "
            f"latency={latency_ms}ms, session={context.get('session_id') if context else None}"
        )
        
        return decision

