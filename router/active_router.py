"""
Active Router - Routes requests to specialized agents.

This router:
1. Classifies user intent with confidence using keywords (fast path)
2. Falls back to LLM classification for ambiguous cases (slow path)
3. Routes to specialized agents (PropertyAgent, NumbersAgent, DocsAgent)
4. Falls back to MainAgent for low confidence or complex queries

Architecture:
- predict_keywords(): Fast keyword-based classification (~0ms)
- predict_llm(): LLM-based classification for ambiguous cases (~200ms)
- predict(): Hybrid approach - keywords first, LLM fallback if low confidence
"""

from __future__ import annotations
import re
import os
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

# Threshold below which we use LLM fallback
LLM_FALLBACK_THRESHOLD = 0.70

# All available intents with descriptions for LLM classification
INTENT_DESCRIPTIONS = {
    # Property intents
    "property.create": "Usuario quiere CREAR una nueva propiedad (casa, piso, villa, etc.)",
    "property.switch": "Usuario quiere CAMBIAR a otra propiedad existente (trabajar con, meterse en, entrar)",
    "property.list": "Usuario quiere VER LISTA de todas sus propiedades",
    "property.delete": "Usuario quiere ELIMINAR/BORRAR una propiedad",
    
    # Numbers intents
    "numbers.set_cell": "Usuario quiere ACTUALIZAR un valor en una celda específica (B5, C5, etc.) de la plantilla de números",
    "numbers.clear_cell": "Usuario quiere BORRAR el valor de una celda específica de la plantilla de números",
    "numbers.export": "Usuario quiere EXPORTAR/DESCARGAR la plantilla de números a Excel",
    "numbers.delete_template": "Usuario quiere ELIMINAR la plantilla de números completa",
    "numbers.upload": "Usuario quiere SUBIR un archivo Excel con datos de números",
    "numbers.select_template": "Usuario quiere SELECCIONAR o TRABAJAR CON la plantilla de números (R2B, Promoción, etc.)",
    "numbers.focus": "Usuario solo dice 'números' o 'plantilla' para enfocarse en esa sección",
    "numbers.send_email": "Usuario quiere ENVIAR la plantilla de números por EMAIL",
    
    # Docs intents
    "docs.set_strategy": "Usuario quiere ELEGIR ESTRATEGIA documental: R2B (reformar y vender) o Promoción (obra nueva). NO confundir con números.",
    "docs.qa": "Usuario hace una PREGUNTA sobre el CONTENIDO de un documento (qué dice, cuándo, cuánto, etc.)",
    "docs.send_email": "Usuario quiere ENVIAR un documento o resumen por EMAIL",
    "docs.upload": "Usuario quiere SUBIR un documento (contrato, factura, escritura, etc.)",
    "docs.list": "Usuario quiere VER LISTA de documentos (subidos o pendientes)",
    "docs.list_pending": "Usuario quiere ver qué documentos FALTAN por subir",
    "docs.list_facturas": "Usuario quiere ver FACTURAS asociadas a un contrato",
    "docs.focus": "Usuario solo dice 'documentos' o 'docs' para enfocarse en esa sección",
    
    # General intents
    "general.help": "Usuario pide AYUDA o quiere saber qué puede hacer el asistente",
    "general.chat": "Conversación GENERAL que no encaja en ninguna categoría específica",
}

# LLM classification prompt
LLM_CLASSIFICATION_PROMPT = """Eres un clasificador de intents para una app de gestión inmobiliaria.

CONTEXTO:
- Propiedad actual: {property_name}
- Documentos subidos: {num_uploaded}
- Estrategia actual: {strategy}

INTENTS DISPONIBLES:
{intent_list}

REGLAS CRÍTICAS:
1. "R2B" en contexto de DOCUMENTOS (elegir camino, estrategia, no tengo más docs) → docs.set_strategy
2. "R2B" en contexto de NÚMEROS (plantilla, celda, B5, Excel) → numbers.select_template
3. Si el usuario habla de "reformar", "vender", "obra nueva" sin mencionar números → docs.set_strategy
4. Si el usuario pregunta sobre el CONTENIDO de un documento → docs.qa
5. Si el usuario quiere LISTAR documentos → docs.list
6. Si el usuario quiere CAMBIAR de propiedad → property.switch

MENSAJE DEL USUARIO:
"{user_text}"

Responde SOLO con el nombre del intent (ej: "docs.set_strategy"). Nada más."""


class ActiveRouter:
    """
    Active router that classifies intent and routes to specialized agents.
    
    Uses a hybrid approach:
    1. Fast keyword-based classification (predict_keywords)
    2. LLM fallback for ambiguous cases (predict_llm)
    """
    
    def __init__(self):
        """Initialize the router."""
        self._llm = None  # Lazy-loaded LLM for classification
    
    def _get_llm(self):
        """Lazy-load the LLM for classification."""
        if self._llm is None:
            try:
                from langchain_openai import ChatOpenAI
                # Use gpt-4o-mini for fast, cheap classification
                self._llm = ChatOpenAI(
                    model="gpt-4o-mini",
                    temperature=0,
                    max_tokens=50  # We only need the intent name
                )
                logger.info("[active_router] LLM classifier initialized (gpt-4o-mini)")
            except Exception as e:
                logger.error(f"[active_router] Failed to initialize LLM: {e}")
                self._llm = None
        return self._llm
    
    def predict_keywords(self, user_text: str, context: Optional[Dict] = None) -> Tuple[str, float, str]:
        """
        Fast keyword-based intent classification.
        
        Args:
            user_text: User's message
            context: Optional context dict
        
        Returns:
            Tuple of (intent, confidence, target_agent)
        """
        s = (user_text or "").lower()
        ctx = context or {}
        
        # ========== CONVERSATION CONTINUATION DETECTION ==========
        # Check if user is responding to a previous agent question
        # This ensures we route back to the same agent for multi-turn flows
        history = ctx.get("history", [])
        if history:
            # Get last AI message
            last_ai_content = None
            last_ai_msg = None
            for msg in reversed(history):
                if hasattr(msg, 'type') and msg.type == 'ai' and hasattr(msg, 'content') and msg.content:
                    last_ai_content = msg.content.lower()
                    last_ai_msg = msg.content  # Keep original case for extraction
                    break
            
            if last_ai_content:
                # ============================================================
                # CONFIRMATION RESPONSES (si, sí, no, confirmo, etc.)
                # These MUST be checked FIRST before any other patterns
                # ============================================================
                confirmation_yes = ["si", "sí", "yes", "confirmo", "adelante", "ok", "vale", "claro", "por supuesto", "hazlo", "dale"]
                confirmation_no = ["no", "cancelar", "cancela", "olvídalo", "olvidalo", "mejor no"]
                
                is_confirmation = s.strip() in confirmation_yes or s.strip() in confirmation_no
                
                if is_confirmation:
                    # Property deletion confirmation
                    if ("¿estás seguro" in last_ai_content or "estas seguro" in last_ai_content) and "eliminar" in last_ai_content:
                        intent = "property.delete_confirm" if s.strip() in confirmation_yes else "property.delete_cancel"
                        logger.info(f"[active_router] 🔄 Continuation: PropertyAgent delete confirmation ({s})")
                        return (intent, 0.98, "PropertyAgent")
                    
                    # Property creation confirmation
                    if ("crear" in last_ai_content or "añadir" in last_ai_content) and "propiedad" in last_ai_content and "?" in last_ai_content:
                        intent = "property.create_confirm" if s.strip() in confirmation_yes else "property.create_cancel"
                        logger.info(f"[active_router] 🔄 Continuation: PropertyAgent create confirmation ({s})")
                        return (intent, 0.98, "PropertyAgent")
                    
                    # Document upload confirmation
                    if ("confirmas" in last_ai_content or "subir" in last_ai_content) and ("documento" in last_ai_content or "archivo" in last_ai_content):
                        intent = "docs.upload_confirm" if s.strip() in confirmation_yes else "docs.upload_cancel"
                        logger.info(f"[active_router] 🔄 Continuation: DocsAgent upload confirmation ({s})")
                        return (intent, 0.98, "DocsAgent")
                    
                    # Email send confirmation
                    if ("enviar" in last_ai_content or "mandar" in last_ai_content) and ("email" in last_ai_content or "correo" in last_ai_content):
                        intent = "docs.email_confirm" if s.strip() in confirmation_yes else "docs.email_cancel"
                        logger.info(f"[active_router] 🔄 Continuation: DocsAgent email confirmation ({s})")
                        return (intent, 0.98, "DocsAgent")
                    
                    # Numbers template confirmation
                    if "plantilla" in last_ai_content and ("números" in last_ai_content or "numeros" in last_ai_content):
                        intent = "numbers.template_confirm" if s.strip() in confirmation_yes else "numbers.template_cancel"
                        logger.info(f"[active_router] 🔄 Continuation: NumbersAgent template confirmation ({s})")
                        return (intent, 0.98, "NumbersAgent")
                    
                    # Generic confirmation - check for any question mark and detect context
                    if "?" in last_ai_content:
                        if any(kw in last_ai_content for kw in ["propiedad", "inmueble", "casa", "piso"]):
                            logger.info(f"[active_router] 🔄 Continuation: Generic PropertyAgent confirmation")
                            return ("property.confirm", 0.95, "PropertyAgent")
                        elif any(kw in last_ai_content for kw in ["documento", "archivo", "pdf", "contrato"]):
                            logger.info(f"[active_router] 🔄 Continuation: Generic DocsAgent confirmation")
                            return ("docs.confirm", 0.95, "DocsAgent")
                        elif any(kw in last_ai_content for kw in ["número", "plantilla", "excel", "celda"]):
                            logger.info(f"[active_router] 🔄 Continuation: Generic NumbersAgent confirmation")
                            return ("numbers.confirm", 0.95, "NumbersAgent")
                
                # ============================================================
                # NON-CONFIRMATION CONTINUATIONS
                # ============================================================
                
                # PropertyAgent continuation: Asked for property name/address
                property_ask_phrases = [
                    "nombre y la dirección", "nombre y dirección",
                    "proporciona el nombre", "proporciona nombre",
                    "qué nombre", "que nombre", "cómo se llama", "como se llama",
                    "nombre de la propiedad", "dirección de la propiedad"
                ]
                if any(phrase in last_ai_content for phrase in property_ask_phrases):
                    logger.info(f"[active_router] 🔄 Continuation: PropertyAgent asked for name/address")
                    return ("property.create_continue", 0.95, "PropertyAgent")
                
                # NumbersAgent continuation: Asked for template selection
                numbers_ask_phrases = [
                    "qué plantilla", "que plantilla", "elige una",
                    "1) r2b", "2) r2b", "3) r2b", "4) promoción"
                ]
                if any(phrase in last_ai_content for phrase in numbers_ask_phrases):
                    # User might be responding with template choice
                    template_responses = ["r2b", "promoción", "promocion", "1", "2", "3", "4", "opción", "opcion", "primera", "segunda"]
                    if any(resp in s for resp in template_responses):
                        logger.info(f"[active_router] 🔄 Continuation: NumbersAgent template selection")
                        return ("numbers.select_template", 0.95, "NumbersAgent")
                
                # DocsAgent continuation: Asked for email
                email_ask_phrases = [
                    "qué correo", "que correo", "qué email", "que email",
                    "a qué dirección", "a que dirección", "proporciona el email"
                ]
                if any(phrase in last_ai_content for phrase in email_ask_phrases):
                    # Check if user provided an email
                    email_pattern = r'[\w\.-]+@[\w\.-]+\.\w+'
                    if re.search(email_pattern, s):
                        logger.info(f"[active_router] 🔄 Continuation: DocsAgent email response")
                        return ("docs.send_email", 0.95, "DocsAgent")
        
        # ========== PROPERTY OPERATIONS ==========
        # Create property - expanded synonyms
        create_property_phrases = [
            # Direct commands
            "crear propiedad", "crea propiedad", "nueva propiedad", "añadir propiedad", "agregar propiedad",
            "crea una propiedad", "crear una propiedad", "añade una propiedad", "agrega una propiedad",
            # Property types
            "crea casa", "crear casa", "crea villa", "crear villa", "crea piso", "crear piso",
            "crea apartamento", "crear apartamento", "crea local", "crear local",
            "crea terreno", "crear terreno", "crea finca", "crear finca",
            "crea una casa", "crear una casa", "crea un piso", "crear un piso",
            "crea un apartamento", "crear un apartamento", "crea un local", "crear un local",
            "crea una finca", "crear una finca", "crea un terreno", "crear un terreno",
            # Natural variations
            "quiero crear", "necesito crear", "vamos a crear", "dame de alta",
            "registrar propiedad", "registra propiedad", "registrar una propiedad",
            "tengo una propiedad nueva", "compré", "he comprado", "acabo de comprar"
        ]
        if any(phrase in s for phrase in create_property_phrases):
            return ("property.create", 0.95, "PropertyAgent")
        
        # Switch property - expanded synonyms
        switch_property_phrases = [
            # Direct commands
            "cambiar a", "cambio a", "trabajar con", "usar propiedad", "selecciona",
            "metete en", "entrar en", "entra en", "entrar a", "entra a",
            # Natural variations
            "abre", "abrir", "ve a", "ir a", "vamos a", "pasemos a",
            "quiero ver", "quiero trabajar", "cambia de propiedad",
            "otra propiedad", "siguiente propiedad", "propiedad anterior"
        ]
        if any(phrase in s for phrase in switch_property_phrases):
            # Not about numbers template
            if not any(x in s for x in ["números", "plantilla", "r2b", "tabla"]):
                return ("property.switch", 0.90, "PropertyAgent")
        
        # List properties - expanded synonyms
        list_property_keywords = [
            "lista", "listar", "ver", "mostrar", "muestrame", "muéstrame",
            "cuales", "cuáles", "cuántas", "cuantas", "qué", "que", "mis",
            "tengo", "hay", "todas", "disponibles"
        ]
        if "propiedades" in s or "properties" in s or "inmuebles" in s or "casas" in s:
            if any(w in s for w in list_property_keywords):
                if not any(x in s for x in ["trabajar", "usar", "crear", "nueva"]):
                    return ("property.list", 0.92, "PropertyAgent")
        
        # Delete property - expanded synonyms
        delete_property_phrases = [
            "elimina propiedad", "eliminar propiedad", "borra propiedad", "borrar propiedad",
            "quita propiedad", "quitar propiedad", "elimina la propiedad", "borra la propiedad"
        ]
        if any(phrase in s for phrase in delete_property_phrases):
            return ("property.delete", 0.90, "PropertyAgent")
        
        # ========== DOCUMENT STRATEGY SELECTION (HIGH PRIORITY - BEFORE NUMBERS) ==========
        # CRITICAL: Detect when user wants to change document strategy (R2B vs Promoción)
        # This MUST be checked BEFORE numbers operations to avoid confusion
        
        # Keywords that indicate document strategy context (NOT numbers)
        doc_strategy_keywords = [
            # Decision verbs
            "elegir", "elijo", "eliges", "elige", "escoger", "escojo", "escoge",
            "optar", "opto", "optas", "decidir", "decido", "decides",
            # Path/strategy words
            "camino", "estrategia", "ruta", "vía", "via", "opción", "opcion",
            "seguir por", "ir por", "tomar", "coger",
            # Intent phrases
            "voy a", "quiero", "prefiero", "me decanto", "vamos por",
            # Document context
            "documentos", "docs", "compra", "promoción", "promocion", "obra nueva",
            # Transition phrases
            "no tengo más", "no tengo mas", "por ahora", "de momento",
            "dejar", "pasar a", "pasemos a", "siguiente nivel", "siguiente fase",
            "terminé", "termine", "acabé", "acabe", "terminado", "acabado",
            # Reform/build context (indicates R2B or Promoción)
            "reformar", "reforma", "reformas", "rehabilitar", "rehabilitación",
            "construir", "construcción", "obra", "edificar"
        ]
        
        # Strategy keywords (R2B, Promoción, etc.)
        strategy_keywords = ["r2b", "promoción", "promocion", "reforma", "obra nueva"]
        
        if any(kw in s for kw in strategy_keywords):
            # Check if it's about document strategy, NOT numbers
            has_doc_context = any(kw in s for kw in doc_strategy_keywords)
            has_numbers_context = any(kw in s for kw in ["números", "numeros", "plantilla", "celda", "b5", "c5", "excel", "tabla"])
            
            if has_doc_context and not has_numbers_context:
                logger.info(f"[active_router] 🎯 Detected document strategy selection: R2B/Promoción")
                return ("docs.set_strategy", 0.95, "DocsAgent")
        
        # ========== NUMBERS OPERATIONS ==========
        # Cell update verbs - expanded synonyms
        cell_update_verbs = [
            "pon", "poner", "escribe", "escribir", "actualiza", "actualizar",
            "coloca", "colocar", "asigna", "asignar", "mete", "meter",
            "cambia", "cambiar", "modifica", "modificar", "establece", "establecer",
            "pon el valor", "cambia el valor", "el valor es", "vale"
        ]
        if any(verb in s for verb in cell_update_verbs) and CELL_RE.search(s):
            return ("numbers.set_cell", 0.95, "NumbersAgent")
        
        # Clear cell - expanded synonyms
        cell_clear_verbs = [
            "borra", "borrar", "elimina", "eliminar", "limpia", "limpiar",
            "vacía", "vaciar", "quita", "quitar", "resetea", "resetear"
        ]
        if any(verb in s for verb in cell_clear_verbs) and CELL_RE.search(s):
            return ("numbers.clear_cell", 0.90, "NumbersAgent")
        
        # Export numbers FIRST - explicit export verbs take priority
        export_verbs = [
            "exporta", "exportar", "descarga", "descargar", "guarda como", "guardar como",
            "genera excel", "generar excel", "dame el excel", "dame el archivo", "obtener excel"
        ]
        numbers_keywords = ["números", "numeros", "plantilla", "excel", "hoja de cálculo", "hoja de calculo", "tabla de números", "r2b"]
        if any(verb in s for verb in export_verbs) and any(kw in s for kw in numbers_keywords):
            if "email" not in s and "correo" not in s:
                return ("numbers.export", 0.88, "NumbersAgent")
        
        # Select/work with numbers template
        # "quiero completar la plantilla números" should show template options
        numbers_focus_keywords = ["números", "numeros", "plantilla números", "plantilla numeros", "tabla de números", "tabla de numeros"]
        numbers_work_keywords = [
            "trabajar", "completar", "rellenar", "editar", "modificar",
            "ver", "abrir", "mostrar", "enseña", "enséñame", "abre", "completa",
            "quiero", "necesito", "vamos a", "empezar", "comenzar", "usar"
        ]
        
        # Check for "completar/trabajar/etc + plantilla/números"
        if any(kw in s for kw in numbers_focus_keywords) or ("plantilla" in s and any(n in s for n in ["número", "números", "numeros"])):
            # Exclude document-related contexts
            doc_exclusions = ["email", "enviar", "documento", "documentos", "compra", "elegir", "camino", "estrategia"]
            if not any(x in s for x in doc_exclusions):
                # Focus mode if just "números" or "plantilla números" alone
                if s.strip() in ["números", "numeros", "plantilla", "plantilla números", "plantilla numeros"]:
                    return ("numbers.focus", 0.85, "NumbersAgent")
                # Work/complete mode - should show template options
                if any(action in s for action in numbers_work_keywords):
                    return ("numbers.select_template", 0.90, "NumbersAgent")
        
        # Also detect "plantilla R2B" or "tabla de números R2B" - explicit template selection
        if "r2b" in s and any(kw in s for kw in ["plantilla", "tabla", "números", "numeros"]):
            # Exclude document strategy context AND export context
            if not any(x in s for x in ["elegir", "elijo", "camino", "compra", "documentos", "exporta", "descarga"]):
                return ("numbers.select_template", 0.92, "NumbersAgent")
        
        # Delete template - expanded synonyms
        delete_verbs = ["elimina", "eliminar", "borra", "borrar", "quita", "quitar", "resetea", "resetear"]
        template_keywords = ["tabla", "plantilla de números", "plantilla de numeros", "plantilla números", "plantilla numeros"]
        if any(verb in s for verb in delete_verbs) and any(kw in s for kw in template_keywords):
            return ("numbers.delete_template", 0.85, "NumbersAgent")
        
        # Upload numbers template - expanded synonyms
        upload_verbs = [
            "sube", "subir", "upload", "cargar", "carga", "importa", "importar",
            "adjunta", "adjuntar", "añade", "añadir"
        ]
        numbers_file_keywords = ["r2b", "números", "numeros", "plantilla", "excel", "xlsx", "xls", "hoja"]
        if any(verb in s for verb in upload_verbs) and any(kw in s for kw in numbers_file_keywords):
            # Exclude document uploads
            if not any(doc in s for doc in ["contrato", "factura", "escritura", "certificado"]):
                return ("numbers.upload", 0.90, "NumbersAgent")
        
        # Send numbers by email - expanded synonyms
        send_verbs = [
            "manda", "mandar", "envía", "enviar", "mandame", "enviame",
            "comparte", "compartir", "remite", "remitir"
        ]
        if any(verb in s for verb in send_verbs) and any(kw in s for kw in numbers_focus_keywords):
            return ("numbers.send_email", 0.90, "NumbersAgent")
        
        # ========== DOCS OPERATIONS ==========
        
        # Expanded document keywords
        doc_keywords = [
            # Document types
            "contrato", "contratos", "factura", "facturas", "escritura", "escrituras",
            "certificado", "certificados", "documento", "documentos", "doc", "docs",
            "licencia", "licencias", "permiso", "permisos", "informe", "informes",
            "presupuesto", "presupuestos", "plano", "planos", "proyecto", "proyectos",
            # Professional documents
            "arquitecto", "abogado", "notario", "ingeniero", "aparejador",
            # Specific document names
            "arras", "señal", "nota simple", "ibi", "icio", "tasación", "cédula",
            "cfe", "boletín", "boletin", "certificado energético"
        ]
        
        # HIGHEST PRIORITY: Send by email (must be before list!)
        # "mandame el documento por email" should NOT be classified as docs.list
        send_email_verbs = [
            "manda", "mandar", "envía", "enviar", "mandame", "enviame",
            "comparte", "compartir", "remite", "remitir", "hazme llegar",
            "pásame", "pasame", "reenvía", "reenvia"
        ]
        email_destinations = ["email", "correo", "mail", "e-mail", "gmail", "hotmail", "outlook", "yahoo"]
        
        if any(verb in s for verb in send_email_verbs):
            has_email_dest = any(dest in s for dest in email_destinations)
            has_doc_keyword = any(doc in s for doc in doc_keywords)
            has_context_ref = any(ref in s for ref in ["este", "ese", "esto", "eso", "esta", "esa"])
            has_content_keyword = any(kw in s for kw in ["resumen", "contenido", "información", "datos"])
            
            if has_email_dest or has_doc_keyword or has_context_ref or has_content_keyword:
                # But NOT if it's about números/R2B
                if not any(x in s for x in ["números", "numeros", "r2b", "tabla", "plantilla"]):
                    return ("docs.send_email", 0.96, "DocsAgent")
        
        # SECOND: Check for list operations (higher priority than QA for "qué documentos tengo")
        # List documents - these should be checked BEFORE content questions
        doc_list_keywords = ["documentos", "documento", "docs", "archivos", "ficheros", "papeles"]
        list_action_keywords = [
            "lista", "listar", "mostrar", "muestrame", "muéstrame", "ver",
            "dame", "enseña", "enséñame", "dime", "cuales", "cuáles"
        ]
        list_query_keywords = ["tengo", "hay", "subido", "subidos", "pendiente", "pendientes"]
        
        # "qué documentos tengo" = list (not QA about content)
        if any(kw in s for kw in doc_list_keywords):
            # Check for list intent patterns
            if any(w in s for w in list_action_keywords):
                return ("docs.list", 0.95, "DocsAgent")
            # "qué documentos tengo/hay" = list, not QA
            if any(w in s for w in list_query_keywords):
                return ("docs.list", 0.92, "DocsAgent")
            # "qué documentos" alone without content verb = list
            if ("qué" in s or "que" in s or "cuáles" in s or "cuales" in s):
                # Only list if NOT asking about content
                content_verbs_check = ["dice", "pone", "contiene", "menciona", "explica", "establece", "indica"]
                if not any(verb in s for verb in content_verbs_check):
                    return ("docs.list", 0.90, "DocsAgent")
        
        # SECOND: Document content questions (RAG/QA)
        # Questions about document CONTENT should go to DocsAgent (it has RAG tools)
        
        # Expanded question words
        question_words = [
            "qué", "que", "cuándo", "cuando", "cuánto", "cuanto", "cuántos", "cuantos",
            "cómo", "como", "dónde", "donde", "quién", "quien", "cuál", "cual",
            "por qué", "porque", "para qué", "para que"
        ]
        
        # Content verbs - indicate asking about what's IN the document
        content_verbs = [
            "dice", "decir", "pone", "poner", "contiene", "contener",
            "menciona", "mencionar", "explica", "explicar", "especifica", "especificar",
            "establece", "establecer", "indica", "indicar", "señala", "señalar",
            "describe", "describir", "detalla", "detallar", "incluye", "incluir"
        ]
        
        # Payment/date terms - indicate asking about specific content
        payment_terms = [
            "pagar", "pago", "pagos", "fecha", "fechas", "vencimiento", "vencimientos",
            "plazo", "plazos", "día", "dia", "mes", "año", "vence", "vencen",
            "cuota", "cuotas", "importe", "importes", "cantidad", "cantidades",
            "precio", "precios", "coste", "costes", "costo", "costos"
        ]
        
        has_specific_doc = any(kw in s for kw in doc_keywords if kw not in ["documento", "documentos", "doc", "docs"])
        has_question = any(qw in s for qw in question_words)
        has_content_verb = any(verb in s for verb in content_verbs)
        has_payment_term = any(term in s for term in payment_terms)
        
        # QA requires: specific document + (content verb OR payment term)
        # OR: specific document + question about content (not just "qué documentos")
        if has_specific_doc and (has_content_verb or has_payment_term):
            return ("docs.qa", 0.90, "DocsAgent")
        
        # Also QA if asking specific question about a specific document
        if has_specific_doc and has_question:
            # Make sure it's not a list request
            if not any(w in s for w in list_query_keywords):
                return ("docs.qa", 0.88, "DocsAgent")
        
        # ========== EMAIL CONTINUATION ==========
        # Detect when user ONLY provides an email address (continuation of email flow)
        email_pattern = r'[\w\.-]+@[\w\.-]+\.\w+'
        if re.search(email_pattern, s):
            words_in_message = s.split()
            if len(words_in_message) <= 5:
                logger.info(f"[active_router] 🎯 Detected email continuation: {s}")
                return ("docs.send_email", 0.95, "DocsAgent")
        
        # Upload document - expanded synonyms
        upload_doc_verbs = [
            "sube", "subir", "upload", "cargar", "carga", "adjunta", "adjuntar",
            "añade", "añadir", "agrega", "agregar", "importa", "importar",
            "guarda", "guardar", "almacena", "almacenar"
        ]
        if any(verb in s for verb in upload_doc_verbs):
            # Not numbers (handled above)
            numbers_exclusions = ["r2b", "números", "numeros", "plantilla", "excel"]
            if not any(x in s for x in numbers_exclusions):
                return ("docs.upload", 0.92, "DocsAgent")
        
        # List missing/pending documents - expanded synonyms
        pending_keywords = [
            "faltan", "falta", "pendientes", "por subir", "sin subir",
            "que me quedan", "que faltan", "incompletos", "sin completar"
        ]
        if any(kw in s for kw in doc_list_keywords) and any(w in s for w in pending_keywords):
            return ("docs.list_pending", 0.88, "DocsAgent")
        
        # List facturas - expanded synonyms
        factura_keywords = ["facturas", "factura", "recibos", "recibo", "tickets", "ticket"]
        factura_relation_keywords = [
            "asociadas", "asociados", "relacionadas", "relacionados",
            "vinculadas", "vinculados", "de", "del", "para"
        ]
        if any(kw in s for kw in factura_keywords) and any(rel in s for rel in factura_relation_keywords):
            return ("docs.list_facturas", 0.85, "DocsAgent")
        
        # Focus documents mode - expanded
        docs_focus_keywords = ["documentos", "documents", "docs", "papeles", "archivos"]
        if s.strip() in docs_focus_keywords:
            return ("docs.focus", 0.85, "DocsAgent")
        
        # ========== GENERAL/FALLBACK ==========
        # Help - expanded synonyms
        help_keywords = [
            "ayuda", "help", "qué puedes hacer", "que puedes hacer",
            "cómo funciona", "como funciona", "qué haces", "que haces",
            "para qué sirves", "para que sirves", "instrucciones",
            "cómo te uso", "como te uso", "tutorial", "guía", "guia",
            "no entiendo", "no sé", "no se", "explícame", "explicame"
        ]
        if any(word in s for word in help_keywords):
            return ("general.help", 0.75, "MainAgent")
        
        # Default fallback - let MainAgent handle complex queries
        return ("general.chat", 0.50, "MainAgent")
    
    async def predict_llm(self, user_text: str, context: Optional[Dict] = None) -> Tuple[str, float, str]:
        """
        LLM-based intent classification for ambiguous cases.
        
        Uses gpt-4o-mini to understand natural language variations.
        
        Args:
            user_text: User's message
            context: Optional context dict
        
        Returns:
            Tuple of (intent, confidence, target_agent)
        """
        llm = self._get_llm()
        if llm is None:
            logger.warning("[active_router] LLM not available, falling back to keywords")
            return ("general.chat", 0.50, "MainAgent")
        
        ctx = context or {}
        
        # Build intent list for prompt
        intent_list = "\n".join([
            f"- {intent}: {desc}" 
            for intent, desc in INTENT_DESCRIPTIONS.items()
        ])
        
        # Build prompt with context
        prompt = LLM_CLASSIFICATION_PROMPT.format(
            property_name=ctx.get("property_name", "ninguna"),
            num_uploaded=ctx.get("num_uploaded", 0),
            strategy=ctx.get("strategy", "no definida"),
            intent_list=intent_list,
            user_text=user_text
        )
        
        try:
            t0 = perf_counter()
            response = await llm.ainvoke(prompt)
            latency_ms = int((perf_counter() - t0) * 1000)
            
            # Extract intent from response
            predicted_intent = response.content.strip().lower()
            
            # Validate intent exists
            if predicted_intent not in INTENT_DESCRIPTIONS:
                # Try to find closest match
                for valid_intent in INTENT_DESCRIPTIONS.keys():
                    if valid_intent in predicted_intent or predicted_intent in valid_intent:
                        predicted_intent = valid_intent
                        break
                else:
                    logger.warning(f"[active_router] LLM returned invalid intent: {predicted_intent}")
                    return ("general.chat", 0.60, "MainAgent")
            
            # Determine target agent from intent
            if predicted_intent.startswith("property."):
                target_agent = "PropertyAgent"
            elif predicted_intent.startswith("numbers."):
                target_agent = "NumbersAgent"
            elif predicted_intent.startswith("docs."):
                target_agent = "DocsAgent"
            else:
                target_agent = "MainAgent"
            
            logger.info(
                f"[active_router] 🤖 LLM classified '{user_text[:30]}...' -> "
                f"{predicted_intent} ({target_agent}) in {latency_ms}ms"
            )
            
            # LLM classifications get 0.85 confidence (high but not absolute)
            return (predicted_intent, 0.85, target_agent)
            
        except Exception as e:
            logger.error(f"[active_router] LLM classification failed: {e}")
            return ("general.chat", 0.50, "MainAgent")
    
    def predict(self, user_text: str, context: Optional[Dict] = None) -> Tuple[str, float, str]:
        """
        Hybrid intent prediction: keywords first, LLM fallback if needed.
        
        This is the SYNCHRONOUS version for backwards compatibility.
        For async code, use predict_async() instead.
        
        Args:
            user_text: User's message
            context: Optional context dict
        
        Returns:
            Tuple of (intent, confidence, target_agent)
        """
        # Always try keywords first (fast path)
        intent, confidence, target_agent = self.predict_keywords(user_text, context)
        
        # If confidence is high enough, return immediately
        if confidence >= LLM_FALLBACK_THRESHOLD:
            return (intent, confidence, target_agent)
        
        # For sync code, we can't use LLM fallback - just return keywords result
        logger.debug(
            f"[active_router] Low confidence ({confidence:.2f}), "
            f"but sync mode - returning keywords result"
        )
        return (intent, confidence, target_agent)
    
    async def predict_async(self, user_text: str, context: Optional[Dict] = None) -> Tuple[str, float, str]:
        """
        Hybrid intent prediction with LLM fallback (async version).
        
        1. Try fast keyword-based classification
        2. If confidence < 0.70, use LLM for better understanding
        
        Args:
            user_text: User's message
            context: Optional context dict
        
        Returns:
            Tuple of (intent, confidence, target_agent)
        """
        # Always try keywords first (fast path)
        intent, confidence, target_agent = self.predict_keywords(user_text, context)
        
        # If confidence is high enough, return immediately
        if confidence >= LLM_FALLBACK_THRESHOLD:
            logger.debug(f"[active_router] Keywords confident ({confidence:.2f}), skipping LLM")
            return (intent, confidence, target_agent)
        
        # Low confidence - use LLM fallback
        logger.info(
            f"[active_router] Keywords low confidence ({confidence:.2f}), "
            f"trying LLM fallback for: '{user_text[:40]}...'"
        )
        
        llm_intent, llm_confidence, llm_agent = await self.predict_llm(user_text, context)
        
        # If LLM gives better confidence, use it
        if llm_confidence > confidence:
            logger.info(
                f"[active_router] LLM improved: {intent} ({confidence:.2f}) -> "
                f"{llm_intent} ({llm_confidence:.2f})"
            )
            return (llm_intent, llm_confidence, llm_agent)
        
        # Otherwise stick with keywords
        return (intent, confidence, target_agent)
    
    async def decide(self, user_text: str, context: Optional[Dict] = None) -> Dict:
        """
        Decide which agent to route to using hybrid classification.
        
        Uses keywords first, then LLM fallback for ambiguous cases.
        
        Args:
            user_text: User's message
            context: Optional context dict
        
        Returns:
            Dict with intent, confidence, target_agent, latency_ms, and classification_method
        """
        t0 = perf_counter()
        
        # Use async hybrid prediction (keywords + LLM fallback)
        intent, confidence, target_agent = await self.predict_async(user_text, context or {})
        
        latency_ms = int((perf_counter() - t0) * 1000)
        
        # Determine if LLM was used (latency > 50ms suggests LLM call)
        classification_method = "llm" if latency_ms > 50 else "keywords"
        
        decision = {
            "intent": intent,
            "confidence": confidence,
            "target_agent": target_agent,
            "latency_ms": latency_ms,
            "classification_method": classification_method,
            "fallback_reason": None
        }
        
        # Check if confidence is too low for specialized agent
        if target_agent != "MainAgent":
            agent_category = intent.split(".")[0]  # e.g., "property", "numbers", "docs"
            threshold = CONFIDENCE_THRESHOLDS.get(agent_category, 0.8)
            
            if confidence < threshold:
                logger.warning(
                    f"[active_router] Confidence {confidence:.2f} < threshold {threshold} "
                    f"for {agent_category}, falling back to MainAgent"
                )
                decision["target_agent"] = "MainAgent"
                decision["fallback_reason"] = f"low_confidence ({confidence:.2f} < {threshold})"
        
        logger.info(
            f"[active_router] '{user_text[:40]}...' -> "
            f"intent={intent}, conf={confidence:.2f}, agent={decision['target_agent']}, "
            f"method={classification_method}, latency={latency_ms}ms"
        )
        
        return decision

