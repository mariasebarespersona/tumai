from __future__ import annotations
import env_loader  # loads .env first
import base64, os, uuid, re, unicodedata, json
from typing import Dict, Any
from fastapi import FastAPI, UploadFile, Form, File
import time
from fastapi.responses import JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from agentic import build_graph
from tools.property_tools import list_frameworks, list_properties as db_list_properties, add_property as db_add_property
from tools.property_tools import search_properties as db_search_properties
from tools.docs_tools import propose_slot, upload_and_link, list_docs, slot_exists, seed_mock_documents
from tools.docs_tools import list_related_facturas, seed_facturas_for
from tools.docs_tools import FACTURABLE_DOCS
from tools.rag_tool import summarize_document as rag_summarize, qa_document as rag_qa, qa_payment_schedule as rag_qa_pay
from tools.rag_index import qa_with_citations, index_all_documents
from tools.email_tool import send_email
from tools.summary_ppt import build_summary_ppt
from tools.property_tools import get_property as db_get_property
from tools.supabase_client import sb, BUCKET
from tools.numbers_tools import get_numbers, set_number, calc_numbers
from tools.numbers_tools import import_excel_template, get_numbers_table_structure, get_numbers_table_values, set_numbers_table_cell, clear_numbers_table_cell
from tools.numbers_agent import (
    compute_and_log as numbers_compute_and_log,
    generate_numbers_excel,
    generate_numbers_table_excel,
    what_if as numbers_what_if,
    sensitivity_grid as numbers_sensitivity_grid,
    break_even_precio as numbers_break_even,
    chart_waterfall as numbers_chart_waterfall,
    chart_cost_stack as numbers_chart_cost_stack,
    chart_sensitivity_heatmap as numbers_chart_sensitivity,
)

agent = build_graph()

# Session state management (persistent to survive reloads)
SESSIONS_FILE = ".sessions.json"

def load_sessions():
    """Load sessions from file."""
    if os.path.exists(SESSIONS_FILE):
        try:
            with open(SESSIONS_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_sessions():
    """Save sessions to file."""
    try:
        print(f"[DEBUG] Saving sessions to {SESSIONS_FILE}: {len(SESSIONS)} sessions")
        with open(SESSIONS_FILE, 'w') as f:
            json.dump(SESSIONS, f, indent=2)
        print(f"[DEBUG] Sessions saved successfully")
    except Exception as e:
        print(f"[ERROR] Could not save sessions: {e}")

SESSIONS = load_sessions()

def get_session(session_id: str):
    if session_id not in SESSIONS:
        print(f"[DEBUG] Creating NEW session: {session_id}")
        SESSIONS[session_id] = {
            "property_id": None,
            "pending_proposal": None,
            "pending_file": None,
            "pending_files": [],
            "search_hits": [],
            "last_uploaded_doc": None,
            "pending_create": False,
            "last_listed_docs": [],
            "docs_list_pointer": 0,
            "rag_backfilled": False,
            "pending_email": False,
            "email_content": None,
            "email_subject": None,
            "email_document": None,
            "focus": None,  # can be "documents" | "numbers" | "summary"
            "messages": [],  # Conversation history for agent context
            "last_email_used": None,
            "last_assistant_response": None,
            "last_doc_ref": None,
        }
    else:
        print(f"[DEBUG] Using EXISTING session: {session_id}, current property_id: {SESSIONS[session_id].get('property_id')}")
        # Ensure messages field exists in old sessions
        if "messages" not in SESSIONS[session_id]:
            SESSIONS[session_id]["messages"] = []
    return SESSIONS[session_id]


def add_to_conversation(session_id: str, user_text: str, assistant_text: str):
    """Add user and assistant messages to conversation history for context."""
    from langchain_core.messages import HumanMessage, AIMessage
    STATE = get_session(session_id)
    
    if user_text:
        STATE["messages"].append(HumanMessage(content=user_text))
    if assistant_text:
        STATE["messages"].append(AIMessage(content=assistant_text))
    
    save_sessions()


def _normalize(s: str) -> str:
    s = s or ""
    return "".join(
        c for c in unicodedata.normalize("NFKD", s.lower()) if unicodedata.category(c) != "Mn"
    )


def _soft_normalize(s: str) -> str:
    """Lower + remove diacritics + strip punctuation to spaces and collapse.
    Makes intent matching resilient to quotes/typos/punctuation.
    """
    import re as _re
    t = _normalize(s)
    t = _re.sub(r"[^a-z0-9\s]", " ", t)
    t = _re.sub(r"\s+", " ", t).strip()
    return t


def _fuzzy_match(text: str, candidates: list[str], threshold: float = 0.72) -> bool:
    """Return True if text is similar to any candidate by ratio or token coverage."""
    from difflib import SequenceMatcher
    tt = _soft_normalize(text)
    for cand in candidates:
        cc = _soft_normalize(cand)
        if not cc:
            continue
        ratio = SequenceMatcher(None, tt, cc).ratio()
        if ratio >= threshold:
            return True
        tokens = cc.split()
        if tokens:
            present = sum(1 for tok in tokens if tok in tt)
            if present / max(1, len(tokens)) >= 0.6:
                return True
    return False


def _extract_uuid(s: str) -> str | None:
    if not s:
        return None
    m = re.search(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b", s)
    return m.group(0) if m else None


def _wants_list_properties(text: str) -> bool:
    t = _normalize(text)
    # Simple keyword combinations
    if "propiedades" in t or "properties" in t:
        # Check for list-like verbs or questions
        list_indicators = ["lista", "listar", "ver", "mostrar", "muestrame", "mostrame", 
                          "ensename", "ensenarme", "hay", "tienes", "tengo", "tenemos",
                          "cuales", "cuantas", "que", "todas", "list", "show", "display",
                          "cual", "cuál", "qué"]
        for indicator in list_indicators:
            if indicator in t:
                # Avoid confusion with "trabajar con propiedad X" or "crear propiedad"
                if not any(x in t for x in ["trabajar", "usar", "con la propiedad", "crear", "nueva", "add", "create"]):
                    return True
    return False


def _wants_create_property(text: str) -> bool:
    t = _normalize(text)
    # More flexible detection - allow "anadir/añadir" even without "propiedad" explicitly
    patterns = [
        r"\b(crear|crea|nueva)\s+(propiedad|property)\b",
        r"\b(anadir|añadir|agregar|add)\s+(una\s+)?(nueva\s+)?(propiedad|property)\b",
        r"\b(quiero|me\s+gustaria|me\s+gustaría|deseo)\s+(crear|anadir|añadir|agregar)\b",
        r"\b(alta|dar\s+de\s+alta)\s+(propiedad|property)\b",
        r"\b(nueva\s+propiedad)\b",
    ]
    for p in patterns:
        if re.search(p, t):
            return True
    return False


def _extract_name_address(user_text: str):
    if not user_text:
        return None, None
    s = user_text.strip()

    # Try to split by explicit dirección/address keyword first
    addr_split = re.split(r'\b(direcci[oó]n|address)\b', s, maxsplit=1, flags=re.IGNORECASE)
    
    name = None
    address = None
    
    if len(addr_split) >= 3:
        # Found dirección/address: everything before is name, everything after is address
        before = addr_split[0].strip()
        after = addr_split[2].strip()
        
        # Extract name from before (remove "nombre:" prefix if present)
        name_match = re.search(r'\bnombre\s*[:\-,]?\s*(.+)', before, flags=re.IGNORECASE)
        if name_match:
            name = name_match.group(1).strip()
        else:
            # No "nombre:" prefix, take everything before dirección
            name = before
        
        # Clean up trailing connectors/punctuation from name
        name = re.sub(r'[,;:\s]+$', '', name).strip()
        
        # Extract address from after (remove ":" or other prefix punctuation)
        address = re.sub(r'^[\s,;:\-]+', '', after).strip()
        address = re.sub(r'[,;\.]+$', '', address).strip()
    else:
        # No explicit dirección/address keyword - try original patterns
        def first_match(patterns):
            for p in patterns:
                m = re.search(p, s, flags=re.IGNORECASE)
                if m:
                    val = m.group(1).strip()
                    val = re.sub(r"(?i)\b(and|y)\b\s*$", "", val).strip()
                    return val
            return None

        # More permissive stop pattern: only stop at dirección/address keywords, not commas
        stop = r"(?=\s*(?:\by\b|\band\b|\baddress\b|\bdirecci[oó]n\b|$))"
        name_patterns = [
            rf"\bname\s*[:\-]?\s*(.+?){stop}",
            rf"\bnombre\s*[:\-]?\s*(.+?){stop}",
            rf"se\s+llama\s+(.+?){stop}",
        ]
        addr_patterns = [
            r"\baddress\s*(?:es)?\s*[:\-]?\s*(.+?)$",
            r"\bdirecci[oó]n\s*(?:es)?\s*[:\-]?\s*(.+?)$",
        ]
        name = first_match(name_patterns)
        address = first_match(addr_patterns)
    
    return name, address


def _extract_property_query(user_text: str) -> str | None:
    if not user_text:
        return None
    m = re.search(r"(?i)propiedad\s*(?:que\s*se\s*llama|llamada|de\s*nombre)?\s*([\w\s\-\.]+)", user_text)
    if m:
        candidate = m.group(1).strip()
        candidate = re.sub(r"\s*(?:para|con|en|de)\s*$", "", candidate, flags=re.IGNORECASE)
        if 2 <= len(candidate) <= 120:
            return candidate
    return None


def _extract_property_candidate_from_text(user_text: str) -> str | None:
    """Extract a likely property name when phrased as 'trabajar/usar/metete con/en X'."""
    if not user_text:
        return None
    # Common Spanish patterns with expanded verb list
    patterns = [
        # Original patterns
        r"(?i)(?:trabajar|usar|utilizar)\s+(?:con|en)\s+(?:la\s+propiedad\s+)?(.+)$",
        r"(?i)quiero\s+(?:trabajar|usar|utilizar)\s+(?:con|en)\s+(?:la\s+propiedad\s+)?(.+)$",
        # New informal patterns
        r"(?i)(?:metete|meter|vamos|voy|ir|irme|pasamos|pasar)\s+(?:en|a|con)\s+(?:la\s+propiedad\s+)?(.+)$",
        r"(?i)(?:me\s+voy|nos\s+vamos)\s+(?:a|en)\s+(?:la\s+propiedad\s+)?(.+)$",
        # Direct "casa/finca + name" extraction
        r"(?i)(?:metete|meter|vamos|voy|ir|irme|pasamos|pasar|en|a)\s+(?:la\s+)?(?:casa|finca|propiedad)\s+(.+)$",
    ]
    for p in patterns:
        m = re.search(p, user_text)
        if m:
            cand = m.group(1).strip()
            # Trim trailing polite words/punctuation
            cand = re.sub(r"[\.,;:!\?]+$", "", cand)
            cand = re.sub(r"\s+(por\s+favor|gracias)$", "", cand, flags=re.IGNORECASE)
            if 2 <= len(cand) <= 120:
                return cand
    return None


def _wants_property_search(text: str) -> bool:
    """Detecta cuando el usuario quiere EXPLÍCITAMENTE cambiar de propiedad.
    Dejamos que el agente maneje menciones simples como 'casa'."""
    t = _normalize(text)
    
    # Ignore generic plural list requests
    if "propiedades" in t or "properties" in t:
        return False
    
    # EXCLUDE if user is talking about frameworks/plantillas - they want to work WITH the property, not switch
    framework_words = ["numeros", "números", "numbers", "documento", "documentos", "documents", 
                       "plantilla", "template", "framework", "resumen", "summary"]
    if any(w in t for w in framework_words):
        return False
    
    # EXCLUDE if they say "de esta propiedad" or "de la propiedad" - they're referencing current property
    if re.search(r"\b(de\s+)?(esta|la)\s+propiedad\b", t):
        return False
    
    # Only detect EXPLICIT property switching commands with clear verbs
    if re.search(r"\b(trabajar|usar|utilizar|cambiar|switch)\b", t) and re.search(r"\b(propiedad|property|con|en)\b", t):
        return True
    # "metete en/a X", "vamos a X", "entrar en X", "quiero entrar en X" with explicit property mention
    if re.search(r"\b(metete|meter|vamos|voy|entrar|entra|quiero entrar)\b", t) and re.search(r"\b(propiedad|property|casa|finca|demo)\b", t):
        return True
    # "quiero entrar en Casa Demo 12" - detect even without explicit "propiedad" word
    if re.search(r"\b(quiero\s+)?entrar\s+en\b", t) and re.search(r"\b(casa|demo|finca|propiedad)\b", t, re.IGNORECASE):
        return True
    return False


def _wants_uploaded_docs(text: str) -> bool:
    t = _normalize(text)
    regexes = [
        r"\bque\s+documentos\s+(tengo|hay|he\s+subido)\b",
        r"\b(documentos)\b.*\b(ya|subidos|subido)\b",
        r"\b(cuales|que|qué)\s+documentos\b.*\b(tengo|hay)\b",
        r"\b(which|what)\s+documents\b.*\b(have|uploaded|already)\b",
    ]
    for rx in regexes:
        if re.search(rx, t):
            return True
    return False


def _wants_missing_docs(text: str) -> bool:
    t = _normalize(text)
    regexes = [
        # español
        r"\b(documentos?)\b.*\b(faltan|falta|pendientes|por\s+(subir|anadir|añadir|cargar))\b",
        r"\b(cuales|que|qué)\s+documentos\b.*\b(faltan|falta|pendientes)\b",
        r"\b(que|qué)\s+documentos\s+me\s+faltan\b",
        r"\b(que|qué)\s+me\s+falta\b.*\b(documentos?)\b",
        r"\b(no\s+he\s+subido|aun\s+no\s+he\s+subido|todavia\s+no\s+he\s+subido|todavía\s+no\s+he\s+subido)\b",
        # inglés
        r"\b(documents?)\b.*\b(missing|pending|to\s+upload|to\s+add)\b",
        r"\b(which|what)\s+documents?\b.*\b(missing|pending)\b",
    ]
    for rx in regexes:
        if re.search(rx, t):
            return True
    return False


def _wants_email(text: str) -> bool:
    """Detect if user wants to send something via email (avoid false positives).
    Requires mention of email/correo/mail or explicit phrases like 'email me'.
    """
    t = _normalize(text)
    # Direct phrases
    if "email me" in t or re.search(r"\bemail\b", t):
        return True
    if re.search(r"\b(correo|mail)\b", t):
        return True
    # Verb + email/correo
    if re.search(r"\b(manda|mandame|envia|enviame|env\u00eda|env\u00edame|send)\b.*\b(email|correo|mail)\b", t):
        return True
    # 'por/al email/correo'
    if re.search(r"\b(por|al)\b.*\b(email|correo|mail)\b", t):
        return True
    # Fuzzy fallback
    examples = [
        "envíamelo por email", "enviamelo por correo", "manda esto a mi correo",
        "mandamelo al email", "send by email", "email this", "enviar por mail",
        "mandar por correo", "me lo mandas por email", "enviame por email"
    ]
    return _fuzzy_match(text, examples)


def _wants_to_change_property(text: str) -> bool:
    """Detect if user explicitly wants to change/switch to a different property.
    
    Only returns True for EXPLICIT change requests like:
    - "cambia a Casa Demo 10"
    - "trabaja con Santiuste"
    - "sal de esta propiedad"
    - "quiero trabajar en otra propiedad"
    - "usar la propiedad X"
    
    Returns False for:
    - Questions about properties ("qué propiedades hay?")
    - Listing properties ("lista propiedades")
    - Any other context where property name is mentioned but not to CHANGE
    """
    t = _normalize(text)
    
    # Explicit change/switch verbs
    change_patterns = [
        r"\b(cambia|cambiar|cambiate)\s+(a|para|con)\b",  # "cambia a X"
        r"\b(trabaja|trabajar|trabajo|trabajar)\s+(con|en|sobre|en la)\b",  # "trabaja con X"
        r"\b(usa|usar|utiliza|utilizar|usame)\s+(la\s+)?(propiedad|casa)\b",  # "usa la propiedad X"
        r"\b(sal|salir|salte|salir|salirte|salirse)\s+(de|de esta|de la)\s+(propiedad|casa)\b",  # "sal de esta propiedad"
        r"\b(quiero|querria|deseo)\s+(trabajar|operar|ver)\s+(en|con|sobre|la)\s+(otra|diferente|nueva)\s+(propiedad|casa)\b",  # "quiero trabajar en otra propiedad"
        r"\b(selecciona|seleccionar|elige|elegir|escoge|escoger)\s+(la\s+)?(propiedad|casa)\b",  # "selecciona la propiedad X"
        r"\b(metete|meterse|entra|entrar)\s+(en|a)\s+(la\s+)?(propiedad|casa)\b",  # "metete en la propiedad X"
        r"\b(ahora|vamos)\s+(a|con|en)\s+(la\s+)?(propiedad|casa)\b",  # "ahora con la propiedad X"
    ]
    
    for pattern in change_patterns:
        if re.search(pattern, t):
            return True
    
    return False


def _wants_focus_documents(text: str) -> bool:
    t = _normalize(text)
    
    # Exclude if there are action words - these are specific requests, not mode switching
    action_words = ["resume", "resumen", "resumir", "resumeme", "summarize", "summary",
                    "que pone", "qué pone", "que dice", "qué dice", "lee", "leer", "read",
                    "busca", "buscar", "encuentra", "encontrar", "search", "find",
                    "envia", "envía", "enviame", "envíame", "send", "email", "correo",
                    "borra", "borrar", "elimina", "eliminar", "delete", "remove",
                    "sube", "subir", "upload", "adjunta", "adjuntar", "attach"]
    if any(w in t for w in action_words):
        return False
    
    # Exclude if it's a question about documents (has question words)
    question_words = ["qué", "que", "cual", "cuál", "cuando", "cuándo", "donde", "dónde", 
                      "cómo", "como", "por qué", "porque", "cuanto", "cuánto"]
    if any(w in t for w in question_words):
        return False
    
    # Detect if user wants to work with documents (mode switching)
    patterns = [
        r"^\s*(documento|documentos|documents|document)\s*$",  # Just "documentos" alone
        r"\bframework\s+de\s+(los\s+)?documentos\b",
        r"\b(enfocar|centrar|trabajar|empezar|iniciar|start|vamos)\s+(en|con|a)?\s*(los\s+)?(documento|documentos|documents|document)\b",
        r"\b(muestrame|muéstrame|muestra|mostrar|ver|lista|listame|ensename|enséñame)\b.*\b(plantilla|framework|esquema|docs?|documentos?)\b",
    ]
    if any(re.search(p, t) for p in patterns):
        return True
    # Fuzzy fallbacks with common phrases (robust to typos/quotes)
    examples = [
        "muestrame la plantilla de documentos",
        "muéstrame la plantilla documentos",
        "ver documentos",
        "ver docs",
        "lista documentos",
        "mostrar framework documentos",
        "esquema de documentos",
        "document framework",
        "documentos por favor",
    ]
    return _fuzzy_match(text, examples)


def _wants_focus_numbers(text: str) -> bool:
    t = _normalize(text)
    # If it's a concrete action, don't treat it as pure focus
    if _wants_list_numbers(text) or _wants_numbers_help(text) or _wants_set_number(text) or _parse_number_value(text) is not None:
        return False
    patterns = [
        r"\b(numeros|números|numbers|number)\b",
        r"\bframework\s+de\s+(los\s+)?n(ú|u)meros\b",
        r"\b(enfocar|centrar|trabajar|empezar|iniciar|start)\s+(en|con)?\s*(los\s+)?(n(ú|u)meros|numbers|number)\b",
    ]
    if any(re.search(p, t) for p in patterns):
        return True
    examples = [
        "muestrame la plantilla de numeros",
        "muéstrame el framework números",
        "ver numeros",
        "lista numeros",
        "numbers framework",
    ]
    return _fuzzy_match(text, examples)


def _wants_list_numbers(text: str) -> bool:
    t = _normalize(text)
    patterns = [
        r"\b(lista(me)?|ver|mostrar)\b.*\b(esquema|schema|items|lineas|líneas|framework|plantilla|tabla)\b.*\b(n(ú|u)meros|numbers|number)\b",
        r"\b(esquema|schema|framework|plantilla|tabla)\b.*\b(n(ú|u)meros|numbers|number)\b",
    ]
    if any(re.search(p, t) for p in patterns):
        return True
    # Also accept "numbers framework" or "framework numbers"
    if ("numbers" in t or "números" in t or "numeros" in t or "number" in t) and "framework" in t:
        return True
    examples = [
        "ver esquema de numeros", "lista plantilla numeros", "framework numeros",
        "mostrar tabla numeros", "enséñame los números", "ver numbers framework"
    ]
    return _fuzzy_match(text, examples)


def _wants_numbers_help(text: str) -> bool:
    t = _normalize(text)
    patterns = [
        r"\b(que|qué)\s+me\s+hace\s+falta\b.*\b(n(ú|u)meros|numbers|number|framework)\b",
        r"\b(que|qué)\s+datos\b.*\b(mandar|enviar|aportar)\b.*\b(framework|n(ú|u)meros|numbers|number)\b",
        r"\b(que|qué)\s+falt(a|an)\b.*\b(n(ú|u)meros|numbers|number|framework)\b",
        r"\b(completar|rellenar)\b.*\b(n(ú|u)meros|numbers|number|framework)\b",
    ]
    if any(re.search(p, t) for p in patterns):
        return True
    examples = [
        "que falta en numeros", "qué falta en números", "ayuda con los numeros",
        "completar numeros", "rellenar numeros", "que datos faltan del framework"
    ]
    return _fuzzy_match(text, examples)


def _wants_calc_numbers(text: str) -> bool:
    t = _normalize(text)
    if bool(re.search(r"\b(calcula|calcular|recalcula|recalcular|compute|calc)\b.*\b(n(ú|u)meros|numbers|totales|resumen)\b", t)):
        return True
    examples = [
        "calcula totales", "recalcula números", "compute numbers", "haz cuentas",
        "recalcula los numeros", "actualiza el resumen de numeros"
    ]
    return _fuzzy_match(text, examples)


def _wants_frameworks_info(text: str) -> bool:
    t = _normalize(text)
    return ("frameworks" in t or "esquemas" in t) and any(w in t for w in ("que", "qué", "hay", "cuales", "cuáles", "listar", "ver"))


def _parse_number_value(text: str) -> float | None:
    """Extract numeric value robustly (supports 1.234,56 | 1,234.56 | 1000.0 | 1.000 | 7%).
    
    Prioritizes numbers after "a" (e.g., "pon X a 1000" → extracts 1000).
    Ignores numbers in dates (e.g., "29 de julio" → ignores 29).
    """
    # First, try to find the number after "a" (e.g., "pon X a 1000")
    # This is the most common pattern for setting values
    after_a = re.search(r"\ba\s+([-+]?\d[\d\.,]*)\s*%?", text, re.IGNORECASE)
    if after_a:
        token = after_a.group(1).strip()
    else:
        # Fallback: find any number in the text
        m = re.search(r"[-+]?\d[\d\.,]*\s*%?", text)
        if not m:
            return None
        token = m.group(0).strip()
    token = token.replace(" ", "").replace("%", "")
    # Both separators present: last one is decimal
    if "," in token and "." in token:
        last_dot = token.rfind('.')
        last_comma = token.rfind(',')
        if last_dot > last_comma:
            token = token.replace(',', '')  # dot is decimal
        else:
            token = token.replace('.', '')
            token = token.replace(',', '.')
    elif "," in token:
        if token.count(',') > 1:
            last = token.rfind(',')
            token = token[:last].replace(',', '') + '.' + token[last+1:]
        else:
            parts = token.split(',')
            if len(parts) == 2 and len(parts[1]) == 3 and parts[0].isdigit():
                token = parts[0] + parts[1]
            else:
                token = token.replace(',', '.')
    elif "." in token:
        if token.count('.') > 1:
            last = token.rfind('.')
            token = token[:last].replace('.', '') + '.' + token[last+1:]
        else:
            before, after = token.split('.')
            if before.isdigit() and len(after) == 3:
                token = before + after
    try:
        return float(token)
    except Exception:
        return None


def _numbers_match_item(items: list[dict], text: str) -> dict | None:
    """Find the best matching item by label or key tokens in the user text."""
    t = _normalize(text)
    # 1) Quick pass by synonyms for robust Spanish phrasing
    synonyms_map = {
        "impuestos_pct": ["impuestos", "impuesto", "iva", "itp", "iba"],
        "precio_venta": ["precio de venta", "precio", "venta"],
        "costes_construccion": ["costes de construccion", "costes de construcción", "construccion", "construcción", "obra"],
        "terrenos_coste": ["terrenos", "terreno coste", "coste terreno", "suelo"],
        "project_mgmt_fees": ["project mgmt", "mgmt", "gestion proyecto", "gestión proyecto", "honorarios gestion"],
        "project_management_coste": ["project management", "gestion", "gestión", "coste gestion", "coste gestión"],
        "acometidas": ["acometidas"],
        "total_pagado": ["total pagado", "pagado", "importe total pagado", "total pagado 29 julio", "total pagado 29 de julio", "importe total pagado 29", "importe total pagado 29 julio", "importe total pagado 29 de julio"],
        "terreno_urbano": ["terreno urbano", "urbano"],
        "terreno_rustico": ["terreno rustico", "terreno rústico", "rustico", "rústico"],
    }
    key_to_item = {it.get("item_key"): it for it in items}
    for item_key, syns in synonyms_map.items():
        if item_key in key_to_item:
            if any(_normalize(s) in t for s in syns):
                return key_to_item[item_key]

    best = None
    best_score = 0
    for it in items:
        label = _normalize(it.get("item_label") or "")
        key = _normalize(it.get("item_key") or "")
        score = 0
        # Exact key or label contains
        if key and key in t:
            score += 4
        if label and label in t:
            score += 4
        # Token overlap
        tokens = [tok for tok in label.split() if len(tok) > 2]
        matched = sum(1 for tok in tokens if tok in t)
        if tokens:
            if matched == len(tokens):
                score += 3
            elif matched >= max(1, len(tokens) - 1):
                score += 3  # boost partial match to handle labels with símbolos
            elif matched >= 1:
                score += 2
        if score > best_score:
            best_score = score
            best = it
    return best if best_score >= 3 else None


# -------- Numbers NL intents (what-if, charts, break-even) --------
def _key_synonyms() -> dict[str, str]:
    return {
        # core vars
        "precio": "precio_venta",
        "precio_venta": "precio_venta",
        "precio de venta": "precio_venta",
        "venta": "precio_venta",
        "costes_construccion": "costes_construccion",
        "coste construccion": "costes_construccion",
        "construccion": "costes_construccion",
        "construcción": "costes_construccion",
    }


def _normalize_key_phrase(s: str) -> str | None:
    t = _normalize(s)
    syn = _key_synonyms()
    for k, std in syn.items():
        if k in t:
            return std
    # fallback exact normalized token
    return syn.get(t)


def _wants_numbers_what_if(text: str) -> bool:
    t = _normalize(text)
    return any(w in t for w in ["what if", "que pasa si", "qué pasa si", "si ", "escenario", "scenario", "sensitivity", "sensibilidad"]) and ("%" in text or "-" in text or "+" in text)


def _parse_percent_changes(text: str) -> dict[str, float]:
    """Extract deltas like 'precio_venta -10%' or 'costes de construcción +12%' into fractional dict."""
    out: dict[str, float] = {}
    t = text
    import re
    # Patterns like 'var -10%' or 'var +12%'
    pat = re.compile(r"([A-Za-z_áéíóúüñ\s]+?)\s*([+-]?\d+(?:[\.,]\d+)?)\s*%", re.IGNORECASE)
    for m in pat.finditer(t):
        raw_key = m.group(1).strip()
        num = m.group(2).replace(",", ".")
        try:
            frac = float(num) / 100.0
        except Exception:
            continue
        key = _normalize_key_phrase(raw_key)
        if key:
            out[key] = frac
    # Also allow verbs 'sube/baja X%' after a key mentioned before
    if not out:
        # Heuristic: look for 'sube|baja|aumenta|reduce' and the closest known key
        verbs = re.findall(r"(sube|baja|aumenta|reduce)\s*([+-]?\d+(?:[\.,]\d+)?)\s*%", t, flags=re.IGNORECASE)
        if verbs:
            # pick last mentioned known key in text
            for k in _key_synonyms().keys():
                if k in _normalize(t):
                    key = _key_synonyms()[k]
                    try:
                        frac = float(verbs[-1][1].replace(",", ".")) / 100.0
                        if verbs[-1][0].lower() in ["baja", "reduce"]:
                            frac = -abs(frac)
                        out[key] = frac
                        break
                    except Exception:
                        pass
    return out


def _wants_numbers_break_even(text: str) -> bool:
    t = _normalize(text)
    return any(w in t for w in ["break even", "break-even", "punto de equilibrio", "beneficio cero", "neto cero", "net_profit 0"]) and any(w in t for w in ["precio", "venta"])


def _wants_chart_waterfall(text: str) -> bool:
    t = _normalize(text)
    return any(w in t for w in ["waterfall", "cascada"]) or ("impacto" in t and "coste" in t)


def _wants_chart_stack(text: str) -> bool:
    t = _normalize(text)
    return any(w in t for w in ["stacked", "apilado"]) or ("composicion" in t or "composición" in t)


def _wants_chart_sensitivity(text: str) -> bool:
    t = _normalize(text)
    return any(w in t for w in ["sensibilidad", "heatmap", "matriz"])


def _wants_set_number(text: str) -> bool:
    t = _normalize(text)
    # Look for verbs or assignment patterns
    if re.search(r"\b(pon|ponme|asigna|define|actualiza|set|establece)\b", t):
        return True
    if re.search(r"=", text):
        return True
    # Pattern "X es 123"
    if re.search(r"\bes\s+[-+]?\d", t):
        return True
    # If there's a number and we are in numbers focus, we'll try to interpret later
    return False


def _extract_email(text: str) -> str | None:
    """Extract email address from text."""
    pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    match = re.search(pattern, text)
    return match.group(0) if match else None


def _wants_same_email(text: str) -> bool:
    """Check if user wants to use the same email as before."""
    t = _normalize(text)
    same_indicators = [
        "mismo email", "mismo correo", "misma direccion", "mismo",
        "el mismo", "la misma", "ese email", "ese correo", "esa direccion",
        "same email", "same address", "that email", "that address"
    ]
    return any(ind in t for ind in same_indicators)


def _match_document_from_text(pid: str, text: str, state: dict = None):
    """Match document name from text. If user says 'este/ese documento', use last uploaded doc."""
    t = _normalize(text)
    
    # Check for "este/ese/this/that documento" - use last uploaded document
    if state and state.get("last_uploaded_doc"):
        this_that_patterns = [
            r"\b(este|ese|esta|esa|this|that)\s+(documento|document)",
            r"\b(el|the)\s+ultimo\s+(documento|document)",
            r"\b(el|the)\s+(documento|document)\s+(que|that)\s+(subi|subí|uploaded?)"
        ]
        if any(re.search(p, t) for p in this_that_patterns):
            last_doc = state["last_uploaded_doc"]
            print(f"[DEBUG] Detected 'ese/este documento', looking for: {last_doc}")
            # Verify the document actually exists and is uploaded
            try:
                rows = list_docs(pid)
                print(f"[DEBUG] Found {len(rows)} total docs in property {pid}")
                for r in rows:
                    if (r.get("document_name") == last_doc["document_name"] and
                        r.get("document_group") == last_doc["document_group"] and
                        r.get("storage_key")):  # Must be uploaded
                        print(f"[DEBUG] Matched document: {r.get('document_name')}")
                        return {
                            "document_group": r.get("document_group", ""),
                            "document_subgroup": r.get("document_subgroup", ""),
                            "document_name": r.get("document_name", ""),
                            "storage_key": r.get("storage_key", ""),
                        }
                print(f"[DEBUG] Could not find matching document in list")
            except Exception as e:
                print(f"[DEBUG] Exception in last_uploaded_doc lookup: {e}")
                pass  # Fall through to normal matching
    
    # Normal document matching by name
    try:
        rows = list_docs(pid)
    except Exception:
        return None
    
    stopwords = ["de", "del", "de la", "el", "la", "los", "las", "un", "una", "sobre", "para"]
    t_clean = t
    for sw in stopwords:
        t_clean = t_clean.replace(f" {sw} ", " ")
    
    best = None
    best_score = 0
    for r in rows:
        if not r.get("storage_key"):
            continue
        name = _normalize(r.get("document_name", ""))
        name_clean = name
        for sw in stopwords:
            name_clean = name_clean.replace(f" {sw} ", " ")
        
        score = 0
        name_tokens = [tok for tok in name_clean.split() if len(tok) > 2]
        if name_tokens and all(tok in t_clean for tok in name_tokens):
            score += 5
        elif name_tokens:
            matched = sum(1 for tok in name_tokens if tok in t_clean)
            if matched >= len(name_tokens) * 0.7:
                score += 4
            elif matched >= 2:
                score += 3
            elif matched == 1:
                score += 1
        
        if score > best_score:
            best_score = score
            best = {
                "document_group": r.get("document_group", ""),
                "document_subgroup": r.get("document_subgroup", ""),
                "document_name": r.get("document_name", ""),
                "storage_key": r.get("storage_key", ""),
            }
    return best if best_score >= 3 else None


def run_turn(session_id: str, text: str = "", audio_wav_bytes: bytes | None = None,
             property_id: str | None = None, file_tuple: tuple[str, bytes] | None = None) -> Dict[str, Any]:
    # Use the existing session state instead of creating a new one
    STATE = get_session(session_id)
    
    # LangGraph with checkpointer automatically maintains message history using thread_id
    # DON'T pass messages - let the checkpointer load the full history automatically
    state = {
        "input": text,  # This will be converted to HumanMessage by prepare_input node
        "audio": audio_wav_bytes,
        "property_id": property_id or STATE.get("property_id")
    }
    
    print(f"[MEMORY DEBUG] Invoking agent with thread_id={session_id}, input={text[:50]}")
    
    # Retry logic for transient connection errors
    max_retries = 2
    for attempt in range(max_retries):
        try:
            # The checkpointer will automatically load and save the conversation history
            config = {"configurable": {"thread_id": session_id}}
            result = agent.invoke(state, config=config)
            
            msg_count = len(result.get("messages", []))
            print(f"[MEMORY DEBUG] Result has {msg_count} messages in history")
            print(f"[MEMORY DEBUG] Result property_id from agent: {result.get('property_id')}")
            
            # CRITICAL FIX: Read the FINAL state from checkpointer after agent execution
            # The post_tool hook updates property_id in the state, so we need to read it back
            try:
                final_state = agent.get_state(config)
                if final_state and final_state.values.get("property_id"):
                    result["property_id"] = final_state.values["property_id"]
                    print(f"[MEMORY DEBUG] ✅ Retrieved property_id from final state: {result['property_id']}")
                else:
                    print(f"[MEMORY DEBUG] ⚠️  Final state has no property_id: {final_state}")
            except Exception as e:
                print(f"[MEMORY DEBUG] ❌ Could not read final state: {e}")
            
            return result
        except Exception as e:
            error_str = str(e)
            # Check if it's a transient connection error
            if "server closed the connection" in error_str or "connection" in error_str.lower():
                if attempt < max_retries - 1:
                    print(f"[WARNING] Connection error on attempt {attempt + 1}, retrying...")
                    import time
                    time.sleep(0.5)  # Brief delay before retry
                    continue
                else:
                    print(f"[ERROR] Connection failed after {max_retries} attempts")
                    raise
            else:
                # Non-connection error, raise immediately
                raise


# Minimal HTTP app to support the Next.js frontend
app = FastAPI(title="RAMA AI Backend")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception handler to catch validation errors before they reach our functions
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    """Catch FastAPI validation errors and log them before returning 422."""
    import logging
    logger = logging.getLogger(__name__)
    logger.error(f"[FastAPI Validation Error] Path: {request.url.path}")
    logger.error(f"[FastAPI Validation Error] Method: {request.method}")
    logger.error(f"[FastAPI Validation Error] Headers: {dict(request.headers)}")
    logger.error(f"[FastAPI Validation Error] Error details: {exc.errors()}")
    logger.error(f"[FastAPI Validation Error] Body: {await request.body() if hasattr(request, 'body') else 'N/A'}")
    
    return JSONResponse(
        status_code=422,
        content={
            "ok": False,
            "error": "FastAPI validation error",
            "details": exc.errors(),
            "path": str(request.url.path)
        }
    )

@app.get("/")
async def healthcheck():
    return {"status": "ok", "app": "RAMA AI Backend"}

@app.get("/debug/excel-config")
async def debug_excel_config():
    """Debug endpoint to check Excel configuration (without exposing tokens)"""
    excel_file_id = os.getenv("EXCEL_FILE_ID")
    has_token = bool(os.getenv("GRAPH_ACCESS_TOKEN"))
    return {
        "excel_file_id": excel_file_id,
        "has_access_token": has_token,
        "token_length": len(os.getenv("GRAPH_ACCESS_TOKEN", "")) if has_token else 0
    }

@app.post("/ui_chat")
async def ui_chat(
    text: str = Form(""),
    session_id: str = Form("web-ui"),
    property_id: str | None = Form(None),
    files: list[UploadFile] = File(default=[]),
    audio: UploadFile | None = File(None),
):
    STATE = get_session(session_id)
    user_text = text or ""
    transcript = None  # Initialize transcript at the beginning
    
    # Debug logging for files and audio
    if files and len(files) > 0:
        print(f"[DEBUG] Received {len(files)} file(s): {[f.filename for f in files]}")
    else:
        print(f"[DEBUG] No files received")
    
    if audio:
        print(f"[DEBUG] Received audio file: {audio.filename}, size: {audio.size}")
    else:
        print(f"[DEBUG] No audio file received")
    
    def make_response(answer: str, extra: dict | None = None):
        current_pid = STATE.get("property_id")
        print(f"[DEBUG make_response] Current property_id in STATE: {current_pid}")
        resp = {"answer": answer, "property_id": current_pid}
        
        # Include property_name if we have property_id
        if current_pid:
            try:
                from tools.property_tools import get_property
                prop_info = get_property(current_pid)
                print(f"[DEBUG make_response] get_property returned: {prop_info}")
                if prop_info:
                    resp["property_name"] = prop_info["name"]
                    print(f"[DEBUG make_response] Setting property_name to: {prop_info['name']}")
            except Exception as e:
                print(f"[DEBUG make_response] Error getting property: {e}")
                pass
        
        # Always include transcript if available
        if transcript:
            resp["transcript"] = transcript
        if extra:
            resp.update(extra)
        # Return JSONResponse with no-cache headers to ensure fresh data
        return JSONResponse(
            content=resp,
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate, proxy-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
            }
        )
    
    # Process audio if present
    if audio:
        try:
            print(f"[DEBUG] Processing audio file...")
            audio_bytes = await audio.read()
            print(f"[DEBUG] Audio bytes length: {len(audio_bytes)}")
            
            # Convert to base64 for the voice tool
            import base64
            audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')
            
            # Use the voice processing function directly
            from tools.voice_tool import process_voice_input
            voice_result = process_voice_input(audio_bytes, "es")
            
            print(f"[DEBUG] Voice processing result: {voice_result}")
            
            if voice_result.get("success") and voice_result.get("text"):
                # Use the transcribed text as the user input
                user_text = voice_result["text"]
                transcript = user_text
                print(f"[DEBUG] Transcribed text: {user_text}")
                
                # Add user message to state for better context
                if "messages" not in STATE:
                    STATE["messages"] = []
                STATE["messages"].append({
                    "role": "user",
                    "content": user_text
                })
                save_sessions()
                
                # Continue with normal flow using the transcribed text
                # Don't return here, let the normal processing continue
            else:
                error_msg = voice_result.get("error", "Error procesando el audio")
                print(f"[DEBUG] Voice processing error: {error_msg}")
                return make_response(f"Lo siento, no pude procesar tu mensaje de voz: {error_msg}")
                
        except Exception as e:
            print(f"[DEBUG] Audio processing exception: {str(e)}")
            return make_response(f"Error procesando el audio: {str(e)}")
    
    # Debug logging
    print(f"[DEBUG] session_id: {session_id}, property_id: {STATE.get('property_id')}, text: {user_text[:50] if user_text else '(empty)'}")
    
    # Handle sync request (empty message from frontend to get current state)
    if not user_text.strip() and len(files) == 0 and not audio:
        current_pid = STATE.get('property_id')
        print(f"[DEBUG] Sync request - returning current property_id: {current_pid}")
        
        # Get property name if we have a property_id
        property_name = None
        if current_pid:
            try:
                from tools.property_tools import get_property
                prop_info = get_property(current_pid)
                property_name = prop_info['name'] if prop_info else None
            except:
                pass
        
        response_text = f"Trabajando en: {property_name}" if property_name else ""
        return make_response(response_text, extra=None)
    
    # If client passes property_id explicitly, pin it for this session
    if property_id:
        STATE["property_id"] = property_id
        save_sessions()
        print(f"[DEBUG] property_id provided by client: {property_id}")
    
    # Extract UUID if mentioned WITH explicit intent to change property
    mentioned_pid = _extract_uuid(user_text)
    if mentioned_pid and _wants_to_change_property(user_text):
        STATE["property_id"] = mentioned_pid
        save_sessions()
        print(f"[DEBUG] Set property_id to {mentioned_pid}")
    
    # REMOVED: Auto-selection of property by name
    # Property ID now ONLY changes with explicit user intent (see _wants_to_change_property)

    # If user referenced a filename but no file bytes arrived (e.g., UI sent only text like "📎 foo.pdf"), propose slot anyway
    if len(files) == 0 and ("📎" in user_text or re.search(r"[\w\-\.]+\.pdf", user_text, flags=re.IGNORECASE)):
        pid = STATE.get("property_id")
        if not pid:
            return make_response("¿En qué propiedad estamos trabajando? Dime el nombre de la propiedad o el UUID.")
        try:
            # Try to extract first *.pdf from text
            m = re.search(r"([\w\-\.]+\.pdf)", user_text, flags=re.IGNORECASE)
            fname = m.group(1) if m else "documento.pdf"
            proposal = propose_slot(fname, user_text)
            STATE["pending_proposal"] = {"filename": fname, "proposal": proposal}
            save_sessions()
            g = proposal["document_group"]; sg = proposal.get("document_subgroup", ""); n = proposal["document_name"]
            return make_response(f"Propongo las siguientes ubicaciones:\n{fname}: {g} / {sg} / {n}\nAdjunta el archivo y responde 'sí' para confirmar.")
        except Exception as e:
            return make_response(f"No he podido proponer ubicación: {e}")

    # Handle file uploads: propose destination and ask for confirmation
    if files and len(files) > 0:
        pid = STATE.get("property_id")
        if not pid:
            return make_response("¿En qué propiedad estamos trabajando? Dime el nombre de la propiedad o el UUID.")
        # For now handle a single file per turn (first one)
        f = files[0]
        try:
            fname = f.filename or "archivo.pdf"
            print(f"[DEBUG] Proposing slot for file: {fname}")
            # Read and store file bytes in session for later confirmation
            file_bytes = await f.read()
            import base64
            file_b64 = base64.b64encode(file_bytes).decode("utf-8")
            
            # Suggest slot using filename; we can extend hint with `user_text` context
            # IMPORTANT: Pass property_id so facturas can match with placeholders
            pid = STATE.get("property_id", "")
            proposal = propose_slot(fname, user_text, property_id=pid)
            print(f"[DEBUG] Proposal: {proposal}")
            STATE["pending_proposal"] = {
                "filename": fname,
                "proposal": proposal,
                "file_b64": file_b64,  # Store file bytes as base64
            }
            save_sessions()
            g = proposal["document_group"]
            sg = proposal.get("document_subgroup", "")
            n = proposal["document_name"]
            response_text = f"Propongo las siguientes ubicaciones:\n{fname}: {g} / {sg} / {n}\n¿Confirmas la subida? (sí/no)"
            print(f"[DEBUG] Returning response: {response_text}")
            return make_response(response_text)
        except Exception as e:
            print(f"[DEBUG] Error proposing slot: {e}")
            return make_response(f"No he podido proponer ubicación: {e}")

    # Confirmation flow for last proposal
    if STATE.get("pending_proposal"):
        t = _normalize(user_text)
        if any(w in t for w in ["si", "sí", "vale", "confirmo", "ok"]):
            pid = STATE.get("property_id")
            if not pid:
                return make_response("¿En qué propiedad estamos trabajando? Dime el nombre de la propiedad o el UUID.")
            try:
                filename = STATE["pending_proposal"]["filename"]
                proposal = STATE["pending_proposal"]["proposal"]
                file_b64 = STATE["pending_proposal"].get("file_b64")
                
                if not file_b64:
                    # Fallback: no file was stored, ask user to reattach
                    STATE["pending_proposal"] = None
                    save_sessions()
                    return make_response("No tengo el archivo guardado. Por favor, adjúntalo de nuevo.")
                
                # Decode file bytes from base64
                import base64
                file_bytes = base64.b64decode(file_b64)
                
                # Log the upload attempt with property name for debugging
                import logging
                logger = logging.getLogger(__name__)
                
                # Get property name for confirmation
                try:
                    from tools.property_tools import get_property
                    prop_info = get_property(pid)
                    prop_name = prop_info['name'] if prop_info else 'Unknown'
                except:
                    prop_name = 'Unknown'
                
                logger.info(f"📤 Attempting upload: {filename}")
                logger.info(f"📤 Property: {prop_name} (ID: {pid})")
                logger.info(f"📤 Target: {proposal['document_group']} / {proposal.get('document_subgroup', '')} / {proposal['document_name']}")
                
                out = upload_and_link(
                    pid,
                    file_bytes,
                    filename,
                    proposal["document_group"],
                    proposal.get("document_subgroup", ""),
                    proposal["document_name"],
                    metadata={}
                )
                STATE["pending_proposal"] = None
                save_sessions()
                
                # Verify document was saved by reading it back
                logger.info(f"✅ Document uploaded: {proposal['document_name']} to property {pid}")
                
                # Read back to verify
                try:
                    docs = list_docs(pid)
                    uploaded_doc = next((d for d in docs if d.get("document_name") == proposal["document_name"] and d.get("storage_key")), None)
                    if uploaded_doc:
                        logger.info(f"✅ Verified document in DB: {uploaded_doc.get('storage_key')}")
                    else:
                        logger.warning(f"⚠️ Document not found in DB after upload!")
                except Exception as e:
                    logger.error(f"❌ Error verifying document: {e}")
                
                # AUTO-INDEX for RAG: Index the document immediately after upload
                try:
                    from tools.rag_index import index_document
                    logger.info(f"🔍 Auto-indexing document for RAG: {proposal['document_name']}")
                    index_result = index_document(
                        pid,
                        proposal["document_group"],
                        proposal.get("document_subgroup", ""),
                        proposal["document_name"]
                    )
                    if index_result.get("indexed", 0) > 0:
                        logger.info(f"✅ Document indexed: {index_result['indexed']} chunks")
                    else:
                        logger.warning(f"⚠️ Document indexing returned 0 chunks: {index_result.get('error', 'unknown')}")
                except Exception as e:
                    logger.warning(f"⚠️ Could not auto-index document (non-critical): {e}")
                
                # Save reference to last uploaded document for "este documento" references
                STATE["last_uploaded_doc"] = {
                    "document_group": proposal["document_group"],
                    "document_subgroup": proposal.get("document_subgroup", ""),
                    "document_name": proposal["document_name"],
                }
                save_sessions()
                # Post-upload: try to auto-create factura placeholders via RAG if this doc is facturable
                try:
                    g = proposal["document_group"]
                    sg = proposal.get("document_subgroup", "") or ""
                    n = proposal["document_name"]
                    if (g, sg, n) in FACTURABLE_DOCS:
                        rel = list_related_facturas(pid, g, sg, n)
                        if not rel:
                            pay = rag_qa_pay(pid, g, sg, n)
                            extracted = (pay or {}).get("extracted", {})
                            dom = extracted.get("day_of_month")
                            if not dom:
                                nd = (pay or {}).get("next_due_date")
                                try:
                                    if nd:
                                        dom = int(str(nd).split("-")[-1])
                                except Exception:
                                    dom = None
                            if dom and 1 <= int(dom) <= 28:
                                seed_facturas_for(pid, g, sg, n, int(dom), 12, None)
                except Exception as _auto_err:
                    print(f"[DEBUG] Auto factura seeding skipped: {_auto_err}")
                
                # Confirm with property name so user knows where it was uploaded
                return make_response(f"✅ Subido '{proposal['document_name']}' a la propiedad '{prop_name}'.")
            except Exception as e:
                STATE["pending_proposal"] = None
                save_sessions()
                return make_response(f"No he podido subir el documento: {e}")
        elif any(w in t for w in ["no", "cambia", "otra", "diferente"]):
            STATE["pending_proposal"] = None
            save_sessions()
            return make_response("De acuerdo. Dime el grupo/subgrupo/nombre exacto o vuelve a adjuntar el archivo con una pista (por ejemplo 'Contrato arquitecto').")
    
    # Quick intent: "facturas asociadas" → list placeholders for current/mentioned doc
    if any(k in _normalize(user_text) for k in ["factura", "facturas"]) and any(k in _normalize(user_text) for k in ["asociad", "relacionad", "de este", "de ese", "de este contrato", "de ese contrato"]):
        pid = STATE.get("property_id")
        if not pid:
            return make_response("¿En qué propiedad estamos trabajando? Dime el nombre de la propiedad o el UUID.")
        # Try to resolve document
        doc_ref = _match_document_from_text(pid, user_text, STATE) or STATE.get("last_uploaded_doc")
        if not doc_ref:
            return make_response("No he podido identificar el documento. Dime el nombre exacto (p. ej., 'Contrato arquitecto').")
        g = doc_ref.get("document_group", ""); sg = doc_ref.get("document_subgroup", "") or ""; n = doc_ref.get("document_name", "")
        try:
            rel = list_related_facturas(pid, g, sg, n)
            if not rel and (g, sg, n) in FACTURABLE_DOCS:
                # Last-chance: infer and seed
                pay = rag_qa_pay(pid, g, sg, n)
                extracted = (pay or {}).get("extracted", {})
                dom = extracted.get("day_of_month")
                if not dom:
                    nd = (pay or {}).get("next_due_date")
                    try:
                        if nd:
                            dom = int(str(nd).split("-")[-1])
                    except Exception:
                        dom = None
                if dom and 1 <= int(dom) <= 28:
                    seed_facturas_for(pid, g, sg, n, int(dom), 12, None)
                    rel = list_related_facturas(pid, g, sg, n) or []
            if rel:
                lines = []
                for r in rel:
                    mark = "⧗" if r.get("placeholder") and not r.get("storage_key") else "✅"
                    due = r.get("due_date") or "(sin fecha)"
                    lines.append(f"{mark} {r.get('document_name','Factura')} — vence {due}")
                return make_response("Facturas asociadas:\n" + "\n".join(lines))
            else:
                return make_response("No hay facturas asociadas aún. Si conoces el día mensual, dime 'día X' y las creo ahora.")
        except Exception as e:
            return make_response(f"No he podido obtener las facturas asociadas: {e}")

    # -------------------------------------------------------------
    # New: Delegate all remaining intent handling to the Agent
    # -------------------------------------------------------------
    out = run_turn(session_id=session_id, text=user_text, property_id=STATE.get("property_id"))
    
    # Update property_id if the agent changed it (messages are handled by PostgreSQL checkpointer)
    if out.get("property_id") and out["property_id"] != STATE.get("property_id"):
        STATE["property_id"] = out["property_id"]
        save_sessions()
    
    answer = out.get("answer") or out.get("content") or ""
    if not answer and out.get("messages"):
        msgs = out["messages"]
        
        # Detect if THIS TURN actually called set_numbers_template
        has_set_template_tool = False
        for m in reversed(msgs):
            # Stop scanning once we hit a HumanMessage (previous turn)
            typ = getattr(m, "type", None)
            if typ == "human":
                break
            name = getattr(m, "name", None)
            if name == "set_numbers_template":
                has_set_template_tool = True
                break
        
        # 1) Prefer the set_numbers_template confirmation ONLY if the tool was called this turn
        if has_set_template_tool:
            for msg in reversed(msgs):
                if isinstance(msg, dict):
                    content = msg.get("content", "")
                else:
                    content = getattr(msg, "content", "")
                if content and isinstance(content, str) and "Usaremos la plantilla de Números" in content:
                    # Sanitize: keep ONLY the confirmation sentence
                    m = re.search(r"Usaremos la plantilla de Números:\s*([^\.\n]+)", content)
                    if m:
                        tpl = m.group(1).strip()
                        answer = f"✅ Usaremos la plantilla de Números: {tpl}."
                    else:
                        # Fallback to whole line but trimmed
                        answer = "✅ Usaremos la plantilla de Números: R2B."
                    break
        
        # 2) Otherwise, pick the last plain AI message (ignore spurious template confirmations)
        if not answer:
            for msg in reversed(msgs):
                if isinstance(msg, dict):
                    content = msg.get("content", "")
                else:
                    content = getattr(msg, "content", "")
                if content and not getattr(msg, "tool_calls", None):
                    # Ignore spurious template confirmations when no tool was called
                    if "Usaremos la plantilla de Números" in str(content):
                        continue
                    answer = str(content)
                    break
    
    # Include transcript if this was a voice input
    print(f"[DEBUG] Final transcript value: {transcript}")
    extra = {"transcript": transcript} if transcript else None
    print(f"[DEBUG] Final response extra: {extra}")
    return make_response(answer or "(sin respuesta)", extra)

    # Handle email requests - check if we're waiting for email first
    # BUT: if user is clearly asking for something else (like selecting a property), cancel pending email
    if STATE.get("pending_email") and not _wants_property_search(user_text) and not _wants_list_properties(user_text):
        email_addr = _extract_email(user_text)
        
        # Check if user wants to use the same email as before
        if not email_addr and _wants_same_email(user_text):
            email_addr = STATE.get("last_email_used")
            if email_addr:
                print(f"[DEBUG] Using previous email (from pending): {email_addr}")
        
        if email_addr:
            content_to_send = STATE.get("email_content", "")
            subject = STATE.get("email_subject", "Información de RAMA AI")
            document_ref = STATE.get("email_document")
            attachments = []
            
            # If there's a document reference, download and attach it
            if document_ref:
                try:
                    from tools.docs_tools import signed_url_for
                    import requests
                    pid = STATE.get("property_id")
                    url = signed_url_for(
                        pid,
                        document_ref["document_group"],
                        document_ref.get("document_subgroup", ""),
                        document_ref["document_name"],
                        expires=600
                    )
                    resp = requests.get(url, timeout=30)
                    resp.raise_for_status()
                    
                    if resp.content:
                        # Get the actual filename from storage_key if available
                        storage_key = document_ref.get("storage_key", "")
                        if storage_key:
                            filename = storage_key.split("/")[-1]
                        else:
                            filename = document_ref["document_name"].replace(" ", "_") + ".pdf"
                        
                        print(f"[DEBUG] Downloaded document: {filename}, size: {len(resp.content)} bytes")
                        attachments.append((filename, resp.content))
                    else:
                        print(f"[ERROR] Document downloaded but empty")
                except Exception as e:
                    print(f"[ERROR] Could not download document: {e}")
            
            try:
                # If we were waiting to send the Numbers Excel, (re)generate it now
                if (STATE.get("email_subject") or "").lower().startswith("framework de números (excel)") or (STATE.get("email_content") or "").lower().find("framework de números") >= 0:
                    try:
                        pid = STATE.get("property_id")
                        if pid:
                            xlsx_bytes = generate_numbers_excel(pid)
                            attachments.append(("numbers_framework.xlsx", xlsx_bytes))
                    except Exception:
                        pass
                send_email(
                    to=[email_addr],
                    subject=subject,
                    html=f"<html><body><pre style='font-family: sans-serif; white-space: pre-wrap;'>{content_to_send}</pre></body></html>",
                    attachments=attachments if attachments else None
                )
                msg = f"✅ Email enviado correctamente a {email_addr}"
                if attachments:
                    msg += f"\n📎 Documento adjunto: {attachments[0][0]}"
                STATE["pending_email"] = False
                STATE["email_content"] = None
                STATE["email_subject"] = None
                STATE["email_document"] = None
                STATE["pending_numbers_excel"] = False
                STATE["last_email_used"] = email_addr
                save_sessions()
                return make_response(msg)
            except Exception as e:
                STATE["pending_email"] = False
                save_sessions()
                return make_response(f"❌ Error al enviar email: {e}")
        else:
            return make_response("No he podido extraer un email válido. Por favor, proporciona tu dirección de email (ejemplo: tu@email.com)")
    
    # Handle email requests
    if _wants_email(user_text):
        email_addr = _extract_email(user_text)
        
        # Check if user wants to use the same email as before
        if not email_addr and _wants_same_email(user_text):
            email_addr = STATE.get("last_email_used")
            if email_addr:
                print(f"[DEBUG] Using previous email: {email_addr}")
        
        pid = STATE.get("property_id")
        
        # Check if user wants to send "this", "that", "the response", "the summary", etc.
        wants_last_response = any(w in _normalize(user_text) for w in ["este", "ese", "esto", "eso", "esta", "esa", "la respuesta", "el resumen", "this", "that", "the response", "the summary"])
        
        if wants_last_response:
            # User wants to send the last assistant response
            last_response = STATE.get("last_assistant_response")
            if last_response:
                if email_addr:
                    # Send last response immediately
                    try:
                        send_email(
                            to=[email_addr],
                            subject="Información de RAMA AI",
                            html=f"<html><body><pre style='font-family: sans-serif; white-space: pre-wrap;'>{last_response}</pre></body></html>",
                        )
                        STATE["last_email_used"] = email_addr
                        save_sessions()
                        return make_response(f"✅ Email enviado correctamente a {email_addr}")
                    except Exception as e:
                        return make_response(f"❌ Error al enviar email: {e}")
                else:
                    # Ask for email
                    STATE["pending_email"] = True
                    STATE["email_content"] = last_response
                    STATE["email_subject"] = "Información de RAMA AI"
                    STATE["email_document"] = None
                    save_sessions()
                    return make_response("Por supuesto. ¿A qué dirección de email te lo envío?")
            else:
                return make_response("No hay ninguna respuesta anterior para enviar. ¿Qué información te gustaría que te enviara?")
        
        # Check if user mentions a specific document
        document_ref = _match_document_from_text(pid, user_text, STATE) if pid else None
        
        # If the user asks to send the numbers framework, generate Excel by default
        if STATE.get("focus") == "numbers" or ("framework" in _normalize(user_text) and ("numbers" in _normalize(user_text) or "numeros" in _normalize(user_text) or "números" in _normalize(user_text))):
            if not pid:
                return make_response("¿En qué propiedad estamos trabajando? Dime el nombre de la propiedad o el UUID.")
            try:
                # Generate Excel and email
                xlsx_bytes = generate_numbers_excel(pid)
                if email_addr:
                    try:
                        # Always attach freshly generated Excel for numbers framework
                        xlsx_bytes = generate_numbers_excel(pid)
                        send_email(
                            to=[email_addr],
                            subject="Framework de números (Excel)",
                            html="<html><body><p>Adjunto el framework de números en Excel.</p></body></html>",
                            attachments=[("numbers_framework.xlsx", xlsx_bytes)]
                        )
                        STATE["last_email_used"] = email_addr
                        save_sessions()
                        return make_response(f"✅ Enviado el framework de números en Excel a {email_addr}")
                    except Exception as e:
                        return make_response(f"❌ Error al enviar el Excel: {e}")
                else:
                    # Ask for email, store attachment content in session temporarily (not persisted long-term)
                    STATE["pending_email"] = True
                    STATE["email_content"] = "Adjunto: framework de números (Excel)"
                    STATE["email_subject"] = "Framework de números (Excel)"
                    STATE["email_document"] = None
                    # Stash the file bytes in memory for this session turn would require extra infra; fallback to recompute on submit.
                    save_sessions()
                    return make_response("¿A qué dirección de email te lo envío? Enviaré un Excel (.xlsx).")
            except Exception as e:
                return make_response(f"No he podido generar el Excel: {e}")

        # For now, use a simple approach: if there's a document mentioned, offer to send it
        if document_ref:
            if email_addr:
                # Send document immediately
                try:
                    from tools.docs_tools import signed_url_for
                    import requests
                    url = signed_url_for(
                        pid,
                        document_ref["document_group"],
                        document_ref.get("document_subgroup", ""),
                        document_ref["document_name"],
                        expires=600
                    )
                    resp = requests.get(url, timeout=30)
                    resp.raise_for_status()  # Raise error if download failed
                    
                    # Ensure we have content
                    if not resp.content:
                        return make_response("❌ Error: el documento descargado está vacío")
                    
                    # Get the actual filename from storage_key if available
                    storage_key = document_ref.get("storage_key", "")
                    if storage_key:
                        # Extract the actual filename from the storage key
                        filename = storage_key.split("/")[-1]
                    else:
                        filename = document_ref["document_name"].replace(" ", "_") + ".pdf"
                    
                    print(f"[DEBUG] Sending document: {filename}, size: {len(resp.content)} bytes")
                    
                    send_email(
                        to=[email_addr],
                        subject=f"Documento: {document_ref['document_name']}",
                        html=f"<html><body><p>Aquí está el documento que solicitaste: {document_ref['document_name']}</p></body></html>",
                        attachments=[(filename, resp.content)]
                    )
                    STATE["last_email_used"] = email_addr
                    save_sessions()
                    return make_response(f"✅ Email enviado correctamente a {email_addr}\n📎 Documento adjunto: {filename}")
                except Exception as e:
                    return make_response(f"❌ Error al enviar email: {e}")
            else:
                # Ask for email
                STATE["pending_email"] = True
                STATE["email_content"] = f"Documento: {document_ref['document_name']}"
                STATE["email_subject"] = f"Documento: {document_ref['document_name']}"
                STATE["email_document"] = document_ref
                save_sessions()
                return make_response("Por supuesto. ¿A qué dirección de email te lo envío?")
        else:
            return make_response("¿Qué información te gustaría que te enviara por email? Especifica el documento o la información.")
    
    # Build summary PowerPoint on explicit request
    if re.search(r"\b(ficha\s+resumen\s+propiedad|resumen\s+en\s+ppt|powerpoint|pptx)\b", _normalize(user_text)):
        pid = STATE.get("property_id")
        if not pid:
            return make_response("¿En qué propiedad estamos trabajando? Dime el nombre de la propiedad o el UUID.")
        try:
            # Fetch property info if available
            prop = None
            try:
                prop = db_get_property(pid)
            except Exception:
                prop = None
            name = (prop or {}).get("name") if isinstance(prop, dict) else None
            address = (prop or {}).get("address") if isinstance(prop, dict) else None
            data = build_summary_ppt(pid, name, address, format="pdf")
            # Upload to storage and share URL
            import time
            key = f"summaries/{pid}/summary_{int(time.time())}.pdf"
            sb.storage.from_(BUCKET).upload(key, data, {"content-type": "application/pdf", "upsert": "true"})
            url = sb.storage.from_(BUCKET).create_signed_url(key, 3600)["signedURL"]
            return make_response(f"Resumen (PDF) listo: {url}\nSi quieres te lo envío por email en este momento.")
        except Exception as e:
            return make_response(f"No he podido generar la ficha resumen: {e}")

    # Seed mock documents on request (simple trigger phrase)
    if _normalize(user_text) in ["sembrar docs mock", "crear docs mock", "mock documentos", "rellena docs mock", "genera documentos mock"] or re.search(r"\b(mock|falsos|simulados)\b.*\b(documentos|docs)\b", _normalize(user_text)):
        pid = STATE.get("property_id")
        if not pid:
            return make_response("¿En qué propiedad trabajamos? Dime el nombre o el UUID.")
        try:
            res = seed_mock_documents(pid, index_after=True)
            return make_response(f"✅ Documentos mock creados: {res.get('seeded', 0)}. {(len(res.get('errors', [])))} errores.")
        except Exception as e:
            return make_response(f"No he podido crear los documentos mock: {e}")
    
    # List all properties
    if _wants_list_properties(user_text):
        # Cancel any transient flows
        STATE["pending_email"] = False
        STATE["pending_create"] = False
        STATE["email_content"] = None
        STATE["email_subject"] = None
        STATE["email_document"] = None
        STATE["focus"] = None
        try:
            rows = db_list_properties(limit=30)
            if not rows:
                return make_response("No hay propiedades en la base de datos todavía.")
            lines = [f"- {r.get('name','(sin nombre)')} — {r.get('address','')}" for r in rows]
            return make_response("Propiedades encontradas:\n" + "\n".join(lines))
        except Exception as e:
            return make_response(f"Error al listar propiedades: {e}")

    # Destructive: by default, purge documents ONLY for current property unless user explicitly says "todas las propiedades"
    norm = _normalize(user_text)
    if re.search(r"\b(borra|elimina|purga)\b", norm) and re.search(r"\b(documentos)\b", norm) and not re.search(r"\b(?:de\s+)?todas\s+las\s+propiedades\b", norm):
        pid = STATE.get("property_id")
        if not pid:
            return make_response("Primero selecciona una propiedad para poder borrar sus documentos.")
        try:
            from tools.docs_tools import purge_property_documents
            res = purge_property_documents(pid)
            return make_response(
                f"✅ Eliminados los documentos de la propiedad actual. Ficheros borrados: {res.get('removed_files',0)}; celdas limpiadas: {res.get('cleared_rows',0)}."
            )
        except Exception as e:
            return make_response(f"❌ No he podido borrar los documentos de esta propiedad: {e}")

    # Destructive: purge all documents for all properties (requires explicit confirmation phrase)
    if re.search(r"\b(confir|confirmo|borra|elimina|purga)\b", norm) and re.search(r"\b(?:de\s+)?todas\s+las\s+propiedades\b", norm):
        try:
            from tools.docs_tools import purge_all_documents
            res = purge_all_documents()
            return make_response(f"✅ Eliminados documentos de {res.get('properties',0)} propiedades. Ficheros borrados: {res.get('removed_files',0)}; celdas limpiadas: {res.get('cleared_rows',0)}.")
        except Exception as e:
            return make_response(f"❌ No he podido borrar los documentos: {e}")
    
    # If we were in a create flow but the user is clearly switching/listing, cancel create flow
    if STATE.get("pending_create") and (_wants_property_search(user_text) or _wants_list_properties(user_text)):
        STATE["pending_create"] = False
        save_sessions()

    # Create new property - check if we're in pending_create mode first
    if STATE.get("pending_create") or _wants_create_property(user_text):
        STATE["pending_create"] = True
        name_val, addr_val = _extract_name_address(user_text)
        name_val = name_val or _extract_property_query(user_text)
        
        # If we already extracted both in this turn, create immediately
        if name_val and addr_val:
            try:
                row = db_add_property(name_val, addr_val)
                STATE["property_id"] = row["id"]
                STATE["pending_create"] = False
                save_sessions()
                fr = list_frameworks(row["id"])
                return make_response(
                    f"Trabajaremos con la propiedad: {row['name']} — {row['address']}\n"
                    f"He creado 2 plantillas por completar: Documentos y Números. ¿Por dónde quieres empezar?",
                    {"property_id": row["id"]},
                )
            except Exception as e:
                STATE["pending_create"] = False
                save_sessions()
                return make_response(f"No he podido crear la propiedad: {e}")
        else:
            # Ask for missing info
            save_sessions()
            return make_response("Por favor, proporciona el nombre y la dirección de la propiedad. Ejemplo: 'nombre: Casa Demo 6 y dirección: Calle Alameda 22'")
    
    # EARLY EXIT FROM FOCUS MODE: If user wants to change property/context while in focus mode
    # This allows flexibility to switch tasks mid-flow
    if STATE.get("focus"):
        if _wants_property_search(user_text) or _wants_list_properties(user_text) or _wants_create_property(user_text):
            # User wants to change property/context, exit focus mode
            STATE["focus"] = None
            save_sessions()
            print(f"[DEBUG] Exiting focus mode because user wants to change context: {user_text[:50]}")
            # Continue processing the property change request below
    
    # Search/switch to a specific property (takes precedence over create if both present)
    if _wants_property_search(user_text):
        # Clear transient flows
        STATE["pending_email"] = False
        STATE["pending_create"] = False
        STATE["email_content"] = None
        STATE["email_subject"] = None
        STATE["email_document"] = None
        STATE["focus"] = None
        
        name_val, addr_val = _extract_name_address(user_text)
        prop_q = _extract_property_query(user_text) or _extract_property_candidate_from_text(user_text)
        query = prop_q or name_val or addr_val or user_text
        try:
            hits = db_search_properties(query, limit=5)
            if not hits:
                rows = db_list_properties(limit=10)
                if rows:
                    lines = [f"- {r.get('name','(sin nombre)')} — {r.get('address','')}" for r in rows]
                    return make_response("No encontré coincidencias exactas. ¿Quisiste decir alguna de estas?\n" + "\n".join(lines) + "\n\nPuedes responder con el nombre tal cual, por ejemplo: 'Casa Demo 6'.")
                return make_response("No encontré propiedades que coincidan. Prueba con otro nombre o dirección.")
            if len(hits) == 1:
                chosen = hits[0]
                STATE["property_id"] = chosen["id"]
                save_sessions()
                print(f"[DEBUG] Property search - Set property_id to {chosen['id']} for session {session_id}")
                fr = list_frameworks(chosen["id"])
                return make_response(
                    f"Trabajaremos con la propiedad: {chosen.get('name','(sin nombre)')} — {chosen.get('address','')}\n"
                    f"Tienes 2 plantillas por completar: Documentos y Números. ¿Por dónde quieres empezar?",
                    {"property_id": chosen["id"]},
                )
            STATE["search_hits"] = hits
            lines = [f"{i+1}. {h['name']} — {h.get('address','')}" for i, h in enumerate(hits)]
            return make_response("He encontrado estas propiedades:\n" + "\n".join(lines) + "\n\nResponde con el número para continuar.")
        except Exception as e:
            return make_response(f"No he podido buscar propiedades: {e}")
    
    # List uploaded documents
    if _wants_uploaded_docs(user_text):
        pid = STATE.get("property_id")
        if not pid:
            return make_response("¿En qué propiedad estamos trabajando? Dime el nombre de la propiedad o el UUID.")
        try:
            rows = list_docs(pid)
            uploaded = [r for r in rows if r.get('storage_key')]
            if uploaded:
                lines = [f"- {r['document_group']} / {r.get('document_subgroup','')} / {r['document_name']}" for r in uploaded[:10]]
                more_hint = f"\n\n({len(uploaded)} documentos en total)" if len(uploaded) > 10 else ""
                
                # Save reference to last document if there's only one, for "ese documento" references
                if len(uploaded) == 1:
                    STATE["last_uploaded_doc"] = {
                        "document_group": uploaded[0].get("document_group", ""),
                        "document_subgroup": uploaded[0].get("document_subgroup", ""),
                        "document_name": uploaded[0].get("document_name", ""),
                    }
                    save_sessions()
                
                return make_response("Documentos ya subidos:\n" + "\n".join(lines) + more_hint)
            return make_response("Aún no hay documentos subidos para esta propiedad.")
        except Exception as e:
            return make_response(f"No he podido consultar los documentos: {e}")

    # Focus documents mode
    if _wants_focus_documents(user_text):
        STATE["focus"] = "documents"
        save_sessions()
        pid = STATE.get("property_id")
        if not pid:
            return make_response("¿En qué propiedad estamos trabajando? Dime el nombre de la propiedad o el UUID.")
        try:
            rows = list_docs(pid)
            uploaded = [r for r in rows if r.get('storage_key')]
            missing = [r for r in rows if not r.get('storage_key')]
            
            response = "📄 **Framework de Documentos**\n\n"
            
            if uploaded:
                response += f"✅ **Documentos subidos** ({len(uploaded)}):\n"
                lines = [f"- {r['document_group']} / {r.get('document_subgroup','')} / {r['document_name']}" for r in uploaded[:10]]
                response += "\n".join(lines)
                if len(uploaded) > 10:
                    response += f"\n... y {len(uploaded) - 10} más"
                response += "\n\n"
            
            if missing:
                response += f"⏳ **Documentos pendientes** ({len(missing)}):\n"
                lines = [f"- {r['document_group']} / {r.get('document_subgroup','')} / {r['document_name']}" for r in missing[:10]]
                response += "\n".join(lines)
                if len(missing) > 10:
                    response += f"\n... y {len(missing) - 10} más"
                response += "\n\n"
            
            if not uploaded and not missing:
                response += "No hay documentos configurados para esta propiedad.\n\n"
            
            response += "**Puedes pedirme:**\n"
            response += "- Subir un documento (adjunta el archivo)\n"
            response += "- Ver documentos subidos o pendientes\n"
            response += "- Resumir un documento específico\n"
            response += "- Hacer preguntas sobre los documentos\n"
            response += "- Enviar un documento por email"
            
            return make_response(response)
        except Exception as e:
            return make_response(f"No he podido listar los documentos: {e}")
    
    # CRÍTICO: NO interceptar NADA relacionado con números aquí
    # Dejar que el agente LangGraph procese TODO:
    # - Selección de plantilla (Guarda 0)
    # - Listado de números
    # - Comandos "pon X a Y" (el agente los procesará con set_number)
    # El router SOLO procesa comandos "pon X a Y" como fallback rápido si el template está seleccionado
    # PERO la prioridad es que el agente procese TODO
    
    # List numbers schema/items - DELEGAR AL AGENTE
    # El agente procesará todo con get_numbers y set_number

    # Calculate numbers on demand
    if STATE.get("focus") == "numbers" and _wants_calc_numbers(user_text):
        pid = STATE.get("property_id")
        if not pid:
            return make_response("¿En qué propiedad estamos trabajando? Dime el nombre de la propiedad o el UUID.")
        try:
            # Use new Numbers Agent compute (persist outputs/logs) in addition to DB calc if present
            _ = numbers_compute_and_log(pid, triggered_by="user", trigger_type="manual")
            # Keep legacy calc for compatibility if available
            try:
                _ = calc_numbers(pid)
            except Exception:
                pass
            return make_response("✅ Cálculo realizado. He registrado el cálculo y validado anomalías. Puedes volver a pedir el esquema o solicitar gráficos o Excel.")
        except Exception as e:
            return make_response(f"No he podido calcular los números: {e}")

    # Numbers help: what is missing/how to complete
    if STATE.get("focus") == "numbers" and _wants_numbers_help(user_text):
        pid = STATE.get("property_id")
        if not pid:
            return make_response("¿En qué propiedad estamos trabajando? Dime el nombre de la propiedad o el UUID.")
        try:
            items = get_numbers(pid)
            missing = [it for it in items if it.get("amount") in (None, 0, "", "null")]
            if not missing:
                return make_response("¡Genial! El esquema de números ya está completo. Puedes actualizar valores diciendo, por ejemplo: 'pon presupuesto reforma a 25000'.")
            lines = [f"- {it['group_name']} / {it['item_label']} ({it['item_key']})" for it in missing[:20]]
            more_hint = f"\n\n({len(missing)} valores pendientes en total)" if len(missing) > 20 else ""
            return make_response("Te faltan por completar estos valores:\n" + "\n".join(lines) + more_hint + "\n\nPuedes decir: 'pon <item> a <valor>'.")
        except Exception as e:
            return make_response(f"No he podido revisar los números: {e}")

    # Set/update a number value (solo con orden explícita: pon/actualiza/...)
    # CRÍTICO: DELEGAR TODO AL AGENTE - el router SOLO procesa como fallback rápido
    # El agente procesará los comandos "pon X a Y" usando set_number
    # El router puede procesar como fallback rápido si el template está seleccionado Y el focus está en "numbers"
    # PERO la prioridad es que el agente procese TODO
    # 
    # Fallback rápido SOLO si:
    # - El template está seleccionado (verificado en el estado del agente)
    # - El focus está en "numbers"
    # - NO es una petición de selección de plantilla
    if _wants_set_number(user_text):
        # Verificar si hay un template seleccionado en el estado del agente
        try:
            from agentic import agent
            final_state = agent.get_state({"configurable": {"thread_id": session_id}})
            has_template = final_state and final_state.values.get("numbers_template")
        except Exception:
            has_template = False
        
        # Check if user is asking to SELECT a template (not set a value)
        is_template_selection = any(kw in user_text.lower() for kw in [
            "plantilla numeros", "plantilla números", "numbers template", "number template",
            "quiero completar", "quiero empezar", "quiero rellenar", "completar plantilla",
            "empezar plantilla", "rellenar plantilla", "muestrame la plantilla", "muéstrame la plantilla",
            "show me the template", "quiero ver", "quiero trabajar"
        ])
        
        # Si hay template seleccionado Y NO es una petición de selección, procesar como fallback rápido
        # Si NO hay template O es una petición de selección, delegar al agente
        if has_template and not is_template_selection and STATE.get("focus") == "numbers":
            # Fallback rápido: procesar directamente
            if STATE.get("focus") != "numbers":
                STATE["focus"] = "numbers"
                save_sessions()
            
            pid = STATE.get("property_id") or property_id
            if not pid:
                return make_response("¿En qué propiedad estamos trabajando? Dime el nombre de la propiedad o el UUID.")
            try:
                items = get_numbers(pid)
                item = _numbers_match_item(items, user_text)
                value = _parse_number_value(user_text)
                if not item or value is None:
                    # If we can't infer item/value, delegate to agent
                    pass  # Fall through to agent
                else:
                    # Persist
                    result = set_number(pid, item["item_key"], float(value))
                    # Auto-recalculate and log using Numbers Agent (no invented values)
                    try:
                        comp = numbers_compute_and_log(pid, triggered_by="user", trigger_type="set_number")
                        anomalies = comp.get("anomalies") or []
                        warn = ("\n⚠️ Anomalías: " + "; ".join(anomalies)) if anomalies else ""
                    except Exception:
                        warn = ""
                    return make_response(f"✅ Actualizado {item['item_label']} ({item['item_key']}) a {value}{warn}")
            except Exception as e:
                # Fall through to agent on error
                pass
        # Si NO hay template O es una petición de selección, delegar al agente (Guarda 0 ofrecerá las opciones)
    
    # List missing documents
    if _wants_missing_docs(user_text):
        pid = STATE.get("property_id")
        if not pid:
            return make_response("¿En qué propiedad estamos trabajando? Dime el nombre de la propiedad o el UUID.")
        try:
            rows = list_docs(pid)
            missing = [r for r in rows if not r.get('storage_key')]
            if missing:
                lines = [f"- {r['document_group']} / {r.get('document_subgroup','')} / {r['document_name']}" for r in missing[:15]]
                more_hint = f"\n\n({len(missing)} documentos pendientes en total)" if len(missing) > 15 else ""
                return make_response("Documentos pendientes de subir:\n" + "\n".join(lines) + more_hint)
            return make_response("¡Genial! Ya has subido todos los documentos para esta propiedad.")
        except Exception as e:
            return make_response(f"No he podido consultar los documentos: {e}")
    
    # Check for explicit summarize/resume request first
    qnorm = _normalize(user_text)
    is_summarize_request = bool(re.search(r"\b(resume|resumen|resumeme|resumir|summarize|summary)\b", qnorm))
    
    pid = STATE.get("property_id")
    if is_summarize_request and pid:
        # User wants a summary of a document
        doc_ref = _match_document_from_text(pid, user_text, STATE)
        
        # Fallback: if no doc found but user said "ese/este documento" and we have a last doc reference, use it
        if not doc_ref:
            t_norm = _normalize(user_text)
            generic_refs = ["ese documento", "este documento", "el documento", "ese doc", "este doc"]
            if any(ref in t_norm for ref in generic_refs) and STATE.get("last_uploaded_doc"):
                # Try to find the last_uploaded_doc in the database
                try:
                    rows = list_docs(pid)
                    last_doc = STATE["last_uploaded_doc"]
                    for r in rows:
                        if (r.get("document_name") == last_doc["document_name"] and
                            r.get("document_group") == last_doc["document_group"] and
                            r.get("storage_key")):
                            doc_ref = {
                                "document_group": r.get("document_group", ""),
                                "document_subgroup": r.get("document_subgroup", ""),
                                "document_name": r.get("document_name", ""),
                                "storage_key": r.get("storage_key", ""),
                            }
                            break
                except Exception as e:
                    print(f"[DEBUG] Could not retrieve last_uploaded_doc: {e}")
        
        if doc_ref:
            try:
                result = rag_summarize(
                    property_id=pid,
                    group=doc_ref.get("document_group", ""),
                    subgroup=doc_ref.get("document_subgroup", ""),
                    name=doc_ref.get("document_name", ""),
                    max_sentences=5
                )
                if result.get("summary"):
                    answer_text = result["summary"]
                    STATE["last_assistant_response"] = answer_text
                    save_sessions()
                    return make_response(answer_text)
            except Exception as e:
                print(f"[DEBUG] Summarize failed: {e}, falling back to agent")
                # Fall through to agent if summarize fails
        else:
            # No document found - provide helpful message
            try:
                rows = list_docs(pid)
                uploaded = [r for r in rows if r.get('storage_key')]
                if uploaded:
                    doc_names = [r.get('document_name', '') for r in uploaded[:5]]
                    return make_response(
                        f"No he podido identificar qué documento quieres resumir. "
                        f"Documentos disponibles: {', '.join(doc_names)}. "
                        f"Por favor, especifica cuál quieres resumir."
                    )
                else:
                    return make_response("No hay documentos subidos aún para esta propiedad. ¿Quieres subir uno?")
            except Exception:
                pass  # Fall through to agent
    
    # Document question/RAG - Priority: any question about documents (but not summarize)
    question_words = ["qué", "que", "cual", "cuál", "cuando", "cuándo", "donde", "dónde", 
                      "cómo", "como", "por qué", "porque", "cuanto", "cuánto", "cuanta", "cuánta",
                      "quien", "quién", "lee el", "que pone", "qué pone", "que dice", "qué dice",
                      "dime", "explicame", "explícame", "di", "día", "dia"]
    
    # Excluir si hay palabras de acción que no son preguntas
    action_words = ["borra", "borrar", "elimina", "eliminar", "delete", "remove", "crea", "crear",
                    "add", "añadir", "anadir", "agrega", "agregar", "sube", "subir", "upload",
                    "pon", "poner", "set", "actualiza", "actualizar", "calcula", "calcular"]
    has_action = any(w in qnorm for w in action_words)
    
    is_question = any(w in qnorm for w in question_words) and not is_summarize_request and not has_action
    
    if is_question and pid:
        # Prioritize document mentioned in current text
        doc_ref = _match_document_from_text(pid, user_text, STATE)
        try:
            if doc_ref:
                # Search in specific document
                result = qa_with_citations(
                    property_id=pid,
                    query=user_text,
                    top_k=6,
                    document_name=doc_ref.get("document_name"),
                    document_group=doc_ref.get("document_group"),
                    document_subgroup=doc_ref.get("document_subgroup")
                )
            else:
                # Search across ALL documents for the property
                result = qa_with_citations(
                    property_id=pid,
                    query=user_text,
                    top_k=6
                )
            
            if result.get("answer"):
                answer_text = result["answer"]
                if result.get("citations"):
                    # citations is a list of dicts, format them properly
                    cit_strs = [f"{c['document_group']}/{c.get('document_subgroup','')}/{c['document_name']} (trozo {c['chunk_index']})" for c in result['citations']]
                    answer_text += f"\n\nFuentes:\n" + "\n".join(f"- {s}" for s in cit_strs)
                
                # Save this response for potential email sending
                STATE["last_assistant_response"] = answer_text
                save_sessions()
                
                return make_response(answer_text)
        except Exception as e:
            print(f"[DEBUG] QA with citations failed: {e}, falling back to agent")
            # Fall through to agent if QA fails
    
    # If no specific intent matched, try Numbers NL router globally (even fuera de números)
    wants_what_if = _wants_numbers_what_if(user_text)
    wants_be = _wants_numbers_break_even(user_text)
    wants_wf = _wants_chart_waterfall(user_text)
    wants_stack = _wants_chart_stack(user_text)
    wants_sens = _wants_chart_sensitivity(user_text)

    if STATE.get("focus") == "numbers" or wants_what_if or wants_be or wants_wf or wants_stack or wants_sens:
        pid = STATE.get("property_id")
        if not pid:
            return make_response("¿En qué propiedad estamos trabajando? Dime el nombre de la propiedad o el UUID.")
        # Garantiza que quedamos en modo números
        if STATE.get("focus") != "numbers":
            STATE["focus"] = "numbers"
            save_sessions()
        # what-if
        if wants_what_if:
            deltas = _parse_percent_changes(user_text)
            if not deltas:
                return make_response("No he podido entender los cambios. Dime, por ejemplo: 'precio de venta -10% y construcción +12%'.")
            try:
                out = numbers_what_if(pid, deltas, name="what_if_chat")
                ans = "Escenario calculado. Net profit: {}".format(out.get("outputs", {}).get("net_profit"))
                return make_response(ans)
            except Exception as e:
                return make_response(f"No he podido calcular el escenario: {e}")
        # break-even
        if wants_be:
            try:
                out_be = numbers_break_even(pid, 1.0)
                if out_be.get("error"):
                    return make_response("No hay datos suficientes para calcular el break-even.")
                return make_response(f"Break-even en precio_venta ≈ {out_be['precio_venta']:.2f} (net_profit {out_be['net_profit']:.2f}).")
            except Exception as e:
                return make_response(f"No he podido calcular el break-even: {e}")
        # charts
        if wants_wf:
            out_wf = numbers_chart_waterfall(pid)
            if out_wf.get("signed_url"):
                return make_response(f"Waterfall listo: {out_wf['signed_url']}")
            return make_response("No he podido generar el waterfall.")
        if wants_stack:
            out_st = numbers_chart_cost_stack(pid)
            if out_st.get("signed_url"):
                return make_response(f"Composición de costes lista: {out_st['signed_url']}")
            return make_response("No he podido generar el gráfico de composición.")
        if wants_sens:
            # default vectors
            precio_vec = [-0.2, -0.1, -0.05, 0.0, 0.05, 0.1, 0.2]
            costes_vec = [-0.15, -0.1, -0.05, 0.0, 0.05, 0.1, 0.15]
            out_sens = numbers_chart_sensitivity(pid, precio_vec, costes_vec)
            if out_sens.get("signed_url"):
                return make_response(f"Sensibilidad lista: {out_sens['signed_url']}")
            return make_response("No he podido generar el heatmap de sensibilidad.")

    out = run_turn(session_id=session_id, text=user_text, property_id=STATE.get("property_id"))
    
    # Update property_id if the agent changed it (messages are handled by PostgreSQL checkpointer)
    print(f"[DEBUG] Before update - STATE property_id: {STATE.get('property_id')}")
    print(f"[DEBUG] After run_turn - out property_id: {out.get('property_id')}")
    
    # CRITICAL: Read the final state from the LangGraph checkpointer to get the updated property_id
    try:
        final_state = agent.get_state({"configurable": {"thread_id": session_id}})
        if final_state and final_state.values.get("property_id"):
            final_prop_id = final_state.values["property_id"]
            print(f"[DEBUG] ✅ Found property_id in final state: {final_prop_id}")
            if final_prop_id != STATE.get("property_id"):
                print(f"[DEBUG] Property changed! Updating STATE from {STATE.get('property_id')} to {final_prop_id}")
                STATE["property_id"] = final_prop_id
                save_sessions()
                # Also update the out dict so make_response uses it
                out["property_id"] = final_prop_id
        else:
            print(f"[DEBUG] ⚠️  No property_id in final state")
    except Exception as e:
        print(f"[DEBUG] ❌ Error reading final state: {e}")
        # Fallback to old logic
        if out.get("property_id") and out["property_id"] != STATE.get("property_id"):
            print(f"[DEBUG] Property changed! Updating STATE from {STATE.get('property_id')} to {out['property_id']}")
            STATE["property_id"] = out["property_id"]
            save_sessions()
    
    print(f"[DEBUG] Final STATE property_id before make_response: {STATE.get('property_id')}")
    
    answer = out.get("answer") or out.get("content") or ""
    if not answer and out.get("messages"):
        msgs = out["messages"]
        for msg in reversed(msgs):
            if isinstance(msg, dict):
                content = msg.get("content", "")
            else:
                content = getattr(msg, "content", "")
            if content and not getattr(msg, "tool_calls", None):
                answer = str(content)
                break
    
    # Include transcript if this was a voice input
    print(f"[DEBUG] Final transcript value: {transcript}")
    extra = {"transcript": transcript} if transcript else None
    print(f"[DEBUG] Final response extra: {extra}")
    return make_response(answer or "(sin respuesta)", extra)
# --- Minimal Numbers Agent endpoints for testing and UI integration ---
@app.get("/api/numbers")
async def get_numbers_api(property_id: str, template_key: str | None = None):
    """Get all numbers for a property. Returns the template structure even if values are NULL."""
    try:
        from tools.numbers_tools import get_numbers
        data = get_numbers(property_id, template_key)
        return JSONResponse(data)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ----------------- Realtime values (SQLite-backed) -----------------
import sqlite3
from pathlib import Path
import json
import asyncio

_DB_PATH = os.path.join(os.path.dirname(__file__), "realtime_values.db")
_QUEUES: dict = {}

def _init_db():
    conn = sqlite3.connect(_DB_PATH)
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS realtime_values (
        property_id TEXT,
        address TEXT,
        value TEXT,
        updated_at TEXT,
        PRIMARY KEY(property_id, address)
    )
    """)
    conn.commit()
    conn.close()

_init_db()

def db_get_range(property_id: str, address_start: str, address_end: str | None = None):
    # simplistic: return all values for property; filtering by range not implemented yet
    conn = sqlite3.connect(_DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT address, value FROM realtime_values WHERE property_id = ?", (property_id,))
    rows = cur.fetchall()
    conn.close()
    return {r[0]: r[1] for r in rows}

def db_set_value(property_id: str, address: str, value: str):
    ts = time.strftime('%Y-%m-%dT%H:%M:%S')
    conn = sqlite3.connect(_DB_PATH)
    cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO realtime_values(property_id,address,value,updated_at) VALUES(?,?,?,?)", (property_id, address, str(value), ts))
    conn.commit()
    conn.close()
    # notify queues
    q = _QUEUES.get(property_id)
    if q:
        try:
            q.put_nowait(json.dumps({"type": "valueChanged", "property_id": property_id, "address": address, "value": value, "updated_at": ts}))
        except Exception:
            pass


@app.get("/api/values")
async def api_get_values(property_id: str, address_range: str | None = None):
    try:
        if not property_id:
            return JSONResponse({"error": "property_id required"}, status_code=400)
        data = db_get_range(property_id, 'A1', address_range)
        # Return as values matrix by parsing addresses (simple A1.. mapping not full range parsing)
        return JSONResponse({"ok": True, "data": data})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/values")
async def api_set_value(property_id: str = Form(...), address: str = Form(...), value: str = Form(...)):
    try:
        db_set_value(property_id, address, value)
        return JSONResponse({"ok": True, "address": address, "value": value})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get('/api/values/stream')
async def values_stream(request: Request, property_id: str):
    # Server-Sent Events stream for a property
    if not property_id:
        return JSONResponse({"error": "property_id required"}, status_code=400)

    q = _QUEUES.get(property_id)
    if not q:
        q = asyncio.Queue()
        _QUEUES[property_id] = q

    async def event_generator():
        try:
            while True:
                # If client disconnected, exit
                if await request.is_disconnected():
                    break
                try:
                    item = await asyncio.wait_for(q.get(), timeout=15.0)
                    yield f"data: {item}\n\n"
                except asyncio.TimeoutError:
                    # send a comment to keep connection alive
                    yield ': keepalive\n\n'
        finally:
            return

    return StreamingResponse(event_generator(), media_type='text/event-stream')


# ==================== Numbers Table Framework Endpoints ====================

@app.get("/api/numbers/template-structure")
async def api_get_template_structure(property_id: str, template_key: str):
    """Get the structure JSON for a Numbers template."""
    try:
        structure = get_numbers_table_structure(property_id, template_key)
        # Log for debugging
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Template structure request: property_id={property_id}, template_key={template_key}, structure_keys={list(structure.keys()) if structure else 'empty'}")
        return JSONResponse({"ok": True, "structure": structure})
    except Exception as e:
        import logging
        logging.error(f"Error getting template structure: {e}", exc_info=True)
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.get("/api/numbers/table-values")
async def api_get_table_values(property_id: str, template_key: str):
    """Get all cell values for a property's Numbers table."""
    try:
        values = get_numbers_table_values(property_id, template_key)
        return JSONResponse({"ok": True, "values": values})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.post("/api/numbers/set-cell-value")
async def api_set_cell_value(
    property_id: str = Form(...),
    template_key: str = Form(...),
    cell_address: str = Form(...),
    value: str = Form(""),
    row_label: str | None = Form(None),
    col_label: str | None = Form(None)
):
    """Set a cell value in the Numbers table.
    Accepts FormData with property_id, template_key, cell_address, and value."""
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"[api_set_cell_value] ⚡ Function called!")
    logger.info(f"[api_set_cell_value] Received: property_id={property_id}, template_key={template_key}, cell_address={cell_address}, value={value}")
    
    try:
        format_json = None  # Can be added later if needed
        
        if not property_id or not template_key or not cell_address:
            error_msg = f"property_id, template_key, and cell_address are required. Got: property_id={property_id}, template_key={template_key}, cell_address={cell_address}"
            logger.error(f"[api_set_cell_value] {error_msg}")
            return JSONResponse({
                "ok": False, 
                "error": error_msg
            }, status_code=400)
        
        result = set_numbers_table_cell(property_id, template_key, cell_address, value or "", row_label, col_label, format_json)
        if result.get("ok"):
            return JSONResponse(result)
        else:
            return JSONResponse(result, status_code=500)
    except Exception as e:
        import logging
        logging.error(f"Error in api_set_cell_value: {e}", exc_info=True)
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.post("/api/numbers/clear-cell-value")
async def api_clear_cell_value(request: Request):
    """Clear/delete a cell value in the Numbers table.
    Supports both form data and JSON body."""
    try:
        content_type = request.headers.get("content-type", "")
        
        # Support JSON body
        if content_type.startswith("application/json"):
            data = await request.json()
            property_id = data.get("property_id")
            template_key = data.get("template_key")
            cell_address = data.get("cell_address")
        else:
            # Support FormData
            form_data = await request.form()
            property_id = form_data.get("property_id")
            template_key = form_data.get("template_key")
            cell_address = form_data.get("cell_address")
            
            # Convert to strings if they exist
            if property_id:
                property_id = str(property_id)
            if template_key:
                template_key = str(template_key)
            if cell_address:
                cell_address = str(cell_address)
        
        if not property_id or not template_key or not cell_address:
            return JSONResponse({
                "ok": False, 
                "error": f"property_id, template_key, and cell_address are required. Got: property_id={property_id}, template_key={template_key}, cell_address={cell_address}"
            }, status_code=400)
        
        result = clear_numbers_table_cell(property_id, template_key, cell_address)
        if result.get("ok"):
            return JSONResponse(result)
        else:
            return JSONResponse(result, status_code=500)
    except Exception as e:
        import logging
        logging.error(f"Error in api_clear_cell_value: {e}", exc_info=True)
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.post("/api/numbers/save-template-structure")
async def api_save_template_structure(request: Request):
    """Save template structure JSON to Supabase.
    This endpoint is called by Next.js import-template route after reading Excel."""
    try:
        data = await request.json()
        property_id = data.get("property_id")
        template_key = data.get("template_key")
        structure_json = data.get("structure_json")
        
        if not property_id or not template_key or not structure_json:
            return JSONResponse({
                "ok": False,
                "error": "property_id, template_key, and structure_json are required"
            }, status_code=400)
        
        # Save to Supabase
        from tools.supabase_client import get_supabase_client
        sb = get_supabase_client()
        sb.postgrest.schema = "public"
        
        template_data = {
            "template_key": template_key,
            "property_id": property_id,
            "structure_json": structure_json
        }
        
        # Upsert template
        existing = sb.table("numbers_templates").select("id").eq("template_key", template_key).eq("property_id", property_id).execute()
        if existing.data:
            sb.table("numbers_templates").update(template_data).eq("id", existing.data[0]["id"]).execute()
        else:
            sb.table("numbers_templates").insert(template_data).execute()
        
        return JSONResponse({"ok": True, "message": "Template structure saved"})
    except Exception as e:
        import logging
        logging.error(f"Error saving template structure: {e}", exc_info=True)
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.post("/api/numbers/import-template")
async def api_import_template(
    property_id: str = Form(...),
    template_key: str = Form(...),
    excel_file_id: str = Form(""),
    access_token: str = Form(""),
    excel_file: UploadFile = File(None)
):
    """Import Excel template structure.
    Supports two methods:
    1. Upload Excel file directly (preferred - no auth needed)
    2. Import from Microsoft Graph API (requires excel_file_id and access_token)
    """
    import os
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        # Method 1: Upload Excel file directly (preferred)
        if excel_file and excel_file.filename:
            logger.info(f"Importing from uploaded file: {excel_file.filename}")
            file_bytes = await excel_file.read()
            from tools.numbers_tools import import_excel_from_file
            result = import_excel_from_file(file_bytes, property_id, template_key)
            logger.info(f"File import result: ok={result.get('ok')}, cells={result.get('cells_imported', 0)}")
            if result.get("ok"):
                return JSONResponse(result)
            else:
                return JSONResponse(result, status_code=500)
        
        # Method 2: Import from Graph API (fallback)
        if not excel_file_id:
            excel_file_id = os.getenv("EXCEL_FILE_ID", "")
        if not access_token:
            access_token = os.getenv("GRAPH_ACCESS_TOKEN", "")
        
        if not excel_file_id or not access_token:
            return JSONResponse({
                "ok": False, 
                "error": "Either upload an Excel file, or configure EXCEL_FILE_ID and GRAPH_ACCESS_TOKEN in backend .env file"
            }, status_code=400)
        
        result = import_excel_template(property_id, template_key, excel_file_id, access_token)
        if result.get("ok"):
            return JSONResponse(result)
        else:
            return JSONResponse(result, status_code=500)
    except Exception as e:
        logger.error(f"Error in import-template endpoint: {e}", exc_info=True)
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.post("/numbers/compute")
async def numbers_compute(property_id: str = Form(...)):
    try:
        out = numbers_compute_and_log(property_id, triggered_by="api", trigger_type="manual")
        return JSONResponse(out)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/numbers/excel")
async def numbers_excel(property_id: str):
    try:
        data = generate_numbers_excel(property_id)
        return Response(content=data, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={
            "Content-Disposition": "attachment; filename=numbers_framework.xlsx"
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/numbers/export")
async def api_export_numbers_table(property_id: str, template_key: str = "R2B"):
    """Export the Numbers table as an Excel file."""
    try:
        data = generate_numbers_table_excel(property_id, template_key)
        return Response(
            content=data,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f"attachment; filename=numbers_table_{template_key}_{property_id[:8]}.xlsx"
            }
        )
    except Exception as e:
        import logging
        logging.error(f"Error exporting numbers table: {e}", exc_info=True)
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.get("/api/numbers/debug-values")
async def api_debug_values(property_id: str = None, template_key: str = "R2B"):
    """Debug endpoint to see what values are stored in the database.
    If property_id is not provided, returns all values from all properties."""
    from tools.numbers_tools import get_numbers_table_values, get_numbers_table_structure
    from tools.supabase_client import sb
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        if not property_id:
            # Return all values from all properties
            sb.postgrest.schema = "public"
            result = sb.table("numbers_table_values").select("*").eq("template_key", template_key).execute()
            all_values = {}
            for row in result.data or []:
                prop_id = str(row.get("property_id", ""))
                cell_addr = str(row.get("cell_address", "")).upper()
                if prop_id not in all_values:
                    all_values[prop_id] = {}
                all_values[prop_id][cell_addr] = {
                    "value": row.get("value", ""),
                    "row_label": row.get("row_label"),
                    "col_label": row.get("col_label"),
                    "format": row.get("format_json", {})
                }
            
            return JSONResponse({
                "ok": True,
                "message": "All values from all properties",
                "template_key": template_key,
                "properties": all_values,
                "property_count": len(all_values),
                "total_values": sum(len(vals) for vals in all_values.values())
            })
        else:
            # Return values for specific property
            values = get_numbers_table_values(property_id, template_key)
            structure = get_numbers_table_structure(property_id, template_key)
            
            logger.info(f"[debug-values] property_id={property_id}, template_key={template_key}, values_count={len(values)}")
            
            return JSONResponse({
                "ok": True,
                "property_id": property_id,
                "template_key": template_key,
                "values_count": len(values),
                "values": values,
                "structure_cells_count": len(structure.get("cells", [])) if structure else 0,
                "sample_structure_cells": structure.get("cells", [])[:5] if structure else []
            })
    except Exception as e:
        logger.error(f"Error in debug endpoint: {e}", exc_info=True)
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.post("/numbers/what_if")
async def numbers_whatif(property_id: str = Form(...), deltas_json: str = Form(...), name: str = Form("what_if")):
    try:
        import json
        deltas = json.loads(deltas_json)
        out = numbers_what_if(property_id, deltas, name)
        return JSONResponse(out)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/numbers/clear")
async def clear_numbers_api(property_id: str = Form(...)):
    """Clear all numbers for a property (dev helper)."""
    try:
        from tools.numbers_tools import clear_numbers
        out = clear_numbers(property_id)
        return JSONResponse(out)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/numbers/sensitivity")
async def numbers_sensitivity(property_id: str = Form(...), precio_vec_json: str = Form(...), costes_vec_json: str = Form(...)):
    try:
        import json
        precio_vec = json.loads(precio_vec_json)
        costes_vec = json.loads(costes_vec_json)
        out = numbers_sensitivity_grid(property_id, precio_vec, costes_vec)
        return JSONResponse(out)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/numbers/break_even")
async def numbers_breakeven(property_id: str = Form(...), tol: float = Form(1.0)):
    try:
        out = numbers_break_even(property_id, tol)
        return JSONResponse(out)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/numbers/chart/waterfall")
async def numbers_chart_wf(property_id: str = Form(...)):
    try:
        out = numbers_chart_waterfall(property_id)
        return JSONResponse(out)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/numbers/chart/stack")
async def numbers_chart_stack(property_id: str = Form(...)):
    try:
        out = numbers_chart_cost_stack(property_id)
        return JSONResponse(out)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/numbers/chart/sensitivity")
async def numbers_chart_sens(property_id: str = Form(...), precio_vec_json: str = Form(...), costes_vec_json: str = Form(...)):
    try:
        import json
        precio_vec = json.loads(precio_vec_json)
        costes_vec = json.loads(costes_vec_json)
        out = numbers_chart_sensitivity(property_id, precio_vec, costes_vec)
        return JSONResponse(out)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)



