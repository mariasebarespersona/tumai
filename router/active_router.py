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
        ctx = context or {}
        
        # ========== PROPERTY OPERATIONS ==========
        # Create property
        if any(phrase in s for phrase in ["crear propiedad", "nueva propiedad", "crea casa", "crea villa", "añadir propiedad", "agregar propiedad"]):
            return ("property.create", 0.95, "PropertyAgent")
        
        # Switch property (explicit change commands)
        if any(phrase in s for phrase in ["cambiar a", "cambio a", "trabajar con", "usar propiedad", "selecciona", "metete en", "entrar en"]):
            # Not about numbers template
            if not any(x in s for x in ["números", "plantilla", "r2b", "tabla"]):
                return ("property.switch", 0.90, "PropertyAgent")
        
        # List properties
        if "propiedades" in s or "properties" in s:
            if any(w in s for w in ["lista", "listar", "ver", "mostrar", "cuales", "cuántas", "qué", "mis"]):
                if not any(x in s for x in ["trabajar", "usar", "crear", "nueva"]):
                    return ("property.list", 0.92, "PropertyAgent")
        
        # Delete property
        if "elimina propiedad" in s or "borra propiedad" in s:
            return ("property.delete", 0.90, "PropertyAgent")
        
        # ========== NUMBERS OPERATIONS ==========
        # High-priority: cell updates (pon B5 a 1000)
        if any(verb in s for verb in ["pon", "escribe", "actualiza", "coloca", "asigna"]) and CELL_RE.search(s):
            return ("numbers.set_cell", 0.95, "NumbersAgent")
        
        # Clear cell (borra B5, elimina el valor de B7)
        if any(verb in s for verb in ["borra", "elimina", "limpia"]) and CELL_RE.search(s):
            return ("numbers.clear_cell", 0.90, "NumbersAgent")
        
        # Export numbers (exporta R2B, descarga números)
        if any(word in s for word in ["exporta", "descarga"]) and ("r2b" in s or "números" in s or "plantilla" in s):
            if "email" not in s:
                return ("numbers.export", 0.88, "NumbersAgent")
        
        # Delete template (elimina la tabla de números)
        if any(word in s for word in ["elimina", "borra"]) and any(x in s for x in ["tabla", "plantilla de números", "plantilla de numeros"]):
            return ("numbers.delete_template", 0.85, "NumbersAgent")
        
        # Upload numbers template (upload Excel, subir R2B)
        if any(word in s for word in ["sube", "subir", "upload", "cargar"]) and any(x in s for x in ["r2b", "números", "numeros", "plantilla", "excel"]):
            return ("numbers.upload", 0.90, "NumbersAgent")
        
        # Select/focus numbers template (números, R2B, plantilla)
        if ("números" in s or "numeros" in s or "r2b" in s or "plantilla" in s) and not any(x in s for x in ["email", "enviar", "documento"]):
            # Focus mode if just "números" alone
            if s.strip() in ["números", "numeros", "r2b", "plantilla"]:
                return ("numbers.focus", 0.85, "NumbersAgent")
            return ("numbers.select_template", 0.82, "NumbersAgent")
        
        # Send numbers by email
        if any(word in s for word in ["manda", "envía", "enviar", "mandame", "enviame"]) and ("números" in s or "numeros" in s or "r2b" in s or "plantilla" in s):
            return ("numbers.send_email", 0.90, "NumbersAgent")
        
        # ========== DOCS OPERATIONS ==========
        # Document content questions (RAG/QA) - HIGHEST PRIORITY for DocsAgent
        # Questions about document content should go to DocsAgent (it has RAG tools now)
        doc_keywords = ["contrato", "factura", "escritura", "certificado", "documento", "arquitecto", "abogado", "obra"]
        question_words = ["qué", "que", "cuándo", "cuando", "cuánto", "cuanto", "cómo", "como", "dónde", "donde", "quién", "quien"]
        content_verbs = ["dice", "pone", "contiene", "menciona", "explica", "especifica", "establece"]
        payment_terms = ["pagar", "pago", "pagos", "fecha", "vencimiento", "plazo", "día", "dia", "mes", "vence"]
        
        has_doc_keyword = any(kw in s for kw in doc_keywords)
        has_question = any(qw in s for qw in question_words)
        has_content_verb = any(verb in s for verb in content_verbs)
        has_payment_term = any(term in s for term in payment_terms)
        
        # If it's a question about document content (not about listing or sending)
        if has_doc_keyword and (has_question or has_content_verb or has_payment_term):
            # Exclude list/send operations
            is_list_request = any(w in s for w in ["lista", "listar", "mostrar", "muestrame", "ver", "dame", "cuales", "tengo", "hay"])
            is_send_request = any(w in s for w in ["manda", "envía", "enviar", "mandame", "enviame"])
            
            # If it's NOT just a list/send, it's a content question → DocsAgent with RAG
            if not (is_list_request and not (has_question or has_content_verb or has_payment_term)) and not is_send_request:
                return ("docs.qa", 0.90, "DocsAgent")
        
        # ========== EMAIL CONTINUATION (HIGH PRIORITY) ==========
        # CRITICAL: Detect when user ONLY provides an email address (continuation of email flow)
        # This happens after agent asks "¿A qué correo?" and user replies with just the email
        import re
        email_pattern = r'[\w\.-]+@[\w\.-]+\.\w+'
        if re.search(email_pattern, s):
            # Check if message is MOSTLY just the email (with minimal extra words)
            words_in_message = s.split()
            if len(words_in_message) <= 3:  # e.g., "tumai2025@hotmail.com" or "mi email es test@mail.com"
                logger.info(f"[active_router] 🎯 Detected email continuation: {s}")
                return ("docs.send_email", 0.95, "DocsAgent")
        
        # ========== SEND BY EMAIL (HIGH PRIORITY - BEFORE docs.list) ==========
        # CRITICAL: Check for "manda X por email" BEFORE checking "documento" → "docs.list"
        # This prevents "Mandame el documento X por email" from being classified as docs.list
        if any(word in s for word in ["manda", "envía", "enviar", "mandame", "enviame"]):
            # Check if it's explicitly about email/correo
            has_email_dest = any(dest in s for dest in ["email", "correo", "mail", "e-mail"])
            
            # Check for various things to send:
            # 1. Specific documents (contrato, factura, etc.)
            # 2. Contextual references (este, ese, esto, eso, la respuesta)
            # 3. Summaries/content (resumen, contenido)
            has_doc_keyword = any(doc in s for doc in ["contrato", "factura", "escritura", "certificado", "documento"])
            has_context_ref = any(ref in s for ref in ["este", "ese", "esto", "eso", "esta", "esa", "la respuesta", "el resumen"])
            has_content_keyword = any(kw in s for kw in ["resumen", "contenido", "información", "datos"])
            
            # If any of the above AND (explicitly mentions email OR omits destination)
            if (has_doc_keyword or has_context_ref or has_content_keyword) or has_email_dest:
                # But NOT if it's about números/R2B (already handled above)
                if not any(x in s for x in ["números", "numeros", "r2b", "tabla", "plantilla"]):
                    return ("docs.send_email", 0.96, "DocsAgent")  # Higher confidence than docs.list (0.92)
        
        # Upload document (sube contrato, subir factura)
        if any(word in s for word in ["sube", "subir", "upload", "cargar"]):
            # Not numbers (handled above)
            if not any(x in s for x in ["r2b", "números", "numeros", "plantilla"]):
                return ("docs.upload", 0.92, "DocsAgent")
        
        # List documents (PRIORITY: must catch all variations)
        # Direct list requests: "lista documentos", "muestrame documentos", "ver documentos"
        if "documentos" in s or "documento" in s:
            # List/show commands
            if any(w in s for w in ["lista", "listar", "mostrar", "muestrame", "ver", "dame", "enseña", "enséñame"]):
                return ("docs.list", 0.95, "DocsAgent")
            # Query about documents: "qué documentos", "cuáles documentos", "tengo documentos"
            if any(w in s for w in ["qué", "que", "cuales", "cuáles", "tengo", "hay", "subido", "subidos"]):
                return ("docs.list", 0.92, "DocsAgent")
        
        # List missing/pending documents
        if "documentos" in s and any(w in s for w in ["faltan", "falta", "pendientes", "por subir"]):
            return ("docs.list_pending", 0.88, "DocsAgent")
        
        # List facturas
        if "facturas" in s and ("asociadas" in s or "relacionadas" in s):
            return ("docs.list_facturas", 0.85, "DocsAgent")
        
        # Focus documents mode
        if s.strip() in ["documentos", "documents", "docs"]:
            return ("docs.focus", 0.85, "DocsAgent")
        
        # ========== GENERAL/FALLBACK ==========
        if any(word in s for word in ["ayuda", "help", "qué puedes hacer", "cómo funciona"]):
            return ("general.help", 0.75, "MainAgent")
        
        # Default fallback - let MainAgent handle complex queries
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

