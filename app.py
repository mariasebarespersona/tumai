from __future__ import annotations
import env_loader  # loads .env first
import base64, os, uuid, re, unicodedata, json
from typing import Dict, Any
from fastapi import FastAPI, UploadFile, Form, File
from fastapi.responses import JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from agentic import build_graph
from tools.property_tools import list_frameworks, list_properties as db_list_properties, add_property as db_add_property
from tools.property_tools import search_properties as db_search_properties
from tools.docs_tools import propose_slot, upload_and_link, list_docs, slot_exists
from tools.rag_tool import summarize_document as rag_summarize, qa_document as rag_qa, qa_payment_schedule as rag_qa_pay
from tools.rag_index import qa_with_citations, index_all_documents
from tools.email_tool import send_email
from tools.numbers_tools import get_numbers, set_number, calc_numbers
from tools.numbers_agent import (
    compute_and_log as numbers_compute_and_log,
    generate_numbers_excel,
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

    def first_match(patterns):
        for p in patterns:
            m = re.search(p, s, flags=re.IGNORECASE)
            if m:
                val = m.group(1).strip()
                val = re.sub(r"(?i)\b(and|y)\b\s*$", "", val).strip()
                return val
        return None

    stop = r"(?=\s*(?:,|;|\.|$|\by\b|\band\b|\baddress\b|\bdirecci[oó]n\b))"
    name_patterns = [
        rf"\bname\s*[:\-]?\s*(.+?){stop}",
        rf"\bnombre\s*[:\-]?\s*(.+?){stop}",
        rf"se\s+llama\s+(.+?){stop}",
    ]
    addr_patterns = [
        r"\baddress\s*(?:es)?\s*[:\-]?\s*(.+?)(?=\s*(?:,|;|\.|$))",
        r"\bdirecci[oó]n\s*(?:es)?\s*[:\-]?\s*(.+?)(?=\s*(?:,|;|\.|$))",
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
    t = _normalize(text)
    # Ignore generic plural list requests
    if "propiedades" in t or "properties" in t:
        return False
    # Work with / switch to a property - expanded verb list
    if re.search(r"\b(trabajar|usar|utilizar|cambiar|switch|metete|meter|vamos|voy|ir|irme|pasamos|pasar)\b", t) and (re.search(r"\bcon\b", t) or re.search(r"\ben\b", t) or re.search(r"\ba\b", t)):
        return True
    # "Quiero trabajar en/ con ...", "usar ...", "cambiar a ..."
    if re.search(r"\b(propiedad|property)\b", t) and re.search(r"(llama|llamada|nombre|direcci[oó]n|address|trabajar|usar|con|en|a|quiero|cambiar)", t):
        return True
    # Direct mention of "casa" or property name with movement verbs
    if re.search(r"\b(casa|finca|propiedad)\s+(demo|rural|[a-z]+)\s*\d+", t, re.IGNORECASE) and re.search(r"\b(metete|meter|vamos|voy|ir|irme|pasamos|pasar|en|a)\b", t):
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
    return False


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
    return any(re.search(p, t) for p in patterns)


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
    return False


def _wants_numbers_help(text: str) -> bool:
    t = _normalize(text)
    patterns = [
        r"\b(que|qué)\s+me\s+hace\s+falta\b.*\b(n(ú|u)meros|numbers|number|framework)\b",
        r"\b(que|qué)\s+datos\b.*\b(mandar|enviar|aportar)\b.*\b(framework|n(ú|u)meros|numbers|number)\b",
        r"\b(que|qué)\s+falt(a|an)\b.*\b(n(ú|u)meros|numbers|number|framework)\b",
        r"\b(completar|rellenar)\b.*\b(n(ú|u)meros|numbers|number|framework)\b",
    ]
    return any(re.search(p, t) for p in patterns)


def _wants_calc_numbers(text: str) -> bool:
    t = _normalize(text)
    return bool(re.search(r"\b(calcula|calcular|recalcula|recalcular|compute|calc)\b.*\b(n(ú|u)meros|numbers|totales|resumen)\b", t))


def _wants_frameworks_info(text: str) -> bool:
    t = _normalize(text)
    return ("frameworks" in t or "esquemas" in t) and any(w in t for w in ("que", "qué", "hay", "cuales", "cuáles", "listar", "ver"))


def _parse_number_value(text: str) -> float | None:
    """Extract numeric value robustly (supports 1.234,56 | 1,234.56 | 1000.0 | 1.000 | 7%)."""
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
        "total_pagado": ["total pagado", "pagado"],
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


def _match_document_from_text(pid: str, text: str):
    """Match document name from text."""
    try:
        rows = list_docs(pid)
    except Exception:
        return None
    t = _normalize(text)
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
    
    # The checkpointer will automatically load and save the conversation history
    result = agent.invoke(state, config={"configurable": {"thread_id": session_id}})
    
    msg_count = len(result.get("messages", []))
    print(f"[MEMORY DEBUG] Result has {msg_count} messages in history")
    
    return result


# Minimal HTTP app to support the Next.js frontend
app = FastAPI(title="RAMA AI Backend")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
        resp = {"answer": answer, "property_id": STATE.get("property_id")}
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
    print(f"[DEBUG] session_id: {session_id}, property_id: {STATE.get('property_id')}, text: {user_text[:50]}")
    
    # If client passes property_id explicitly, pin it for this session
    if property_id:
        STATE["property_id"] = property_id
        save_sessions()
        print(f"[DEBUG] property_id provided by client: {property_id}")
    
    # Extract UUID if mentioned
    mentioned_pid = _extract_uuid(user_text)
    if mentioned_pid:
        STATE["property_id"] = mentioned_pid
        save_sessions()
        print(f"[DEBUG] Set property_id to {mentioned_pid}")
    
    # Check if user is just mentioning a property name (like "Casa demo 4") at the start of message
    # and try to auto-select it if it matches
    if not STATE.get("property_id") and len(user_text.split()) <= 5:
        # Short message, might be just a property name
        try:
            hits = db_search_properties(user_text, limit=3)
            if hits and len(hits) == 1:
                # Only one match, auto-select it
                chosen = hits[0]
                STATE["property_id"] = chosen["id"]
                save_sessions()
                print(f"[DEBUG] Auto-selected property: {chosen['name']} ({chosen['id']})")
        except:
            pass  # Silently fail if search doesn't work

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
            proposal = propose_slot(fname, user_text)
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
                import logging
                logger = logging.getLogger(__name__)
                logger.info(f"✅ Document uploaded: {proposal['document_name']}")
                
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
                
                return make_response(f"✅ Subido '{proposal['document_name']}'.")
            except Exception as e:
                STATE["pending_proposal"] = None
                save_sessions()
                return make_response(f"No he podido subir el documento: {e}")
        elif any(w in t for w in ["no", "cambia", "otra", "diferente"]):
            STATE["pending_proposal"] = None
            save_sessions()
            return make_response("De acuerdo. Dime el grupo/subgrupo/nombre exacto o vuelve a adjuntar el archivo con una pista (por ejemplo 'Contrato arquitecto').")
    
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
        document_ref = _match_document_from_text(pid, user_text) if pid else None
        
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
                return make_response("Documentos ya subidos:\n" + "\n".join(lines) + more_hint)
            return make_response("Aún no hay documentos subidos para esta propiedad.")
        except Exception as e:
            return make_response(f"No he podido consultar los documentos: {e}")

    # Focus numbers mode (also accept direct mentions like "numbers framework")
    if _wants_focus_numbers(user_text) or ("framework" in _normalize(user_text) and ("numbers" in _normalize(user_text) or "numeros" in _normalize(user_text) or "números" in _normalize(user_text))):
        STATE["focus"] = "numbers"
        save_sessions()
        # Mostrar la plantilla inmediatamente + resumen de acciones en español
        pid = STATE.get("property_id")
        if not pid:
            return make_response("¿En qué propiedad estamos trabajando? Dime el nombre de la propiedad o el UUID.")
        try:
            items = get_numbers(pid)
            if not items:
                return make_response("No hay números configurados aún para esta propiedad.")
            lines = [f"- {it['group_name']} / {it['item_label']} ({it['item_key']}): {it['amount'] if it['amount'] is not None else '-'}" for it in items[:30]]
            more_hint = f"\n\n({len(items)} items en total)" if len(items) > 30 else ""
            acciones = ("\n\nPuedes pedirme: calcular, escenario (por ejemplo: -10% en precio/+12% en construcción), "
                        "punto de equilibrio, sensibilidad, gráfico en cascada, barras apiladas al 100%, o 'enviarlo por email' (Excel).")
            return make_response("Esquema de números:\n" + "\n".join(lines) + more_hint + acciones)
        except Exception as e:
            return make_response(f"No he podido listar los números: {e}")

    # List numbers schema/items
    if STATE.get("focus") == "numbers" and (_wants_list_numbers(user_text) or "esquema" in _normalize(user_text)):
        pid = STATE.get("property_id")
        if not pid:
            return make_response("¿En qué propiedad estamos trabajando? Dime el nombre de la propiedad o el UUID.")
        try:
            items = get_numbers(pid)
            if not items:
                return make_response("No hay números configurados aún para esta propiedad.")
            lines = [f"- {it['group_name']} / {it['item_label']} ({it['item_key']}): {it['amount'] if it['amount'] is not None else '-'}" for it in items[:30]]
            more_hint = f"\n\n({len(items)} items en total)" if len(items) > 30 else ""
            actions = "\n\nPuedes pedirme: calcular, escenario (por ejemplo: -10% en precio/+12% en construcción), punto de equilibrio, sensibilidad, gráfico en cascada, barras apiladas al 100%, o 'enviarlo por email' (Excel)."
            return make_response("Esquema de números:\n" + "\n".join(lines) + more_hint + actions)
        except Exception as e:
            return make_response(f"No he podido listar los números: {e}")

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
    if STATE.get("focus") == "numbers" and _wants_set_number(user_text):
        pid = STATE.get("property_id")
        if not pid:
            return make_response("¿En qué propiedad estamos trabajando? Dime el nombre de la propiedad o el UUID.")
        try:
            items = get_numbers(pid)
            item = _numbers_match_item(items, user_text)
            value = _parse_number_value(user_text)
            if not item or value is None:
                # If we can't infer item/value, guide user
                hint = "o 'pon presupuesto reforma a 25000'"
                return make_response("No he entendido qué valor quieres cambiar. Dime, por ejemplo: 'pon ITP a 12000' " + hint)
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
            return make_response(f"No he podido actualizar el número: {e}")
    
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
        doc_ref = _match_document_from_text(pid, user_text)
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
    
    # Document question/RAG - Priority: any question about documents (but not summarize)
    question_words = ["qué", "que", "cual", "cuál", "cuando", "cuándo", "donde", "dónde", 
                      "cómo", "como", "por qué", "porque", "cuanto", "cuánto", "cuanta", "cuánta",
                      "quien", "quién", "lee el", "que pone", "qué pone", "que dice", "qué dice",
                      "dime", "explicame", "explícame", "di", "día", "dia"]
    is_question = any(w in qnorm for w in question_words) and not is_summarize_request
    
    if is_question and pid:
        # Prioritize document mentioned in current text
        doc_ref = _match_document_from_text(pid, user_text)
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
    if out.get("property_id") and out["property_id"] != STATE.get("property_id"):
        STATE["property_id"] = out["property_id"]
        save_sessions()
    
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


@app.post("/numbers/what_if")
async def numbers_whatif(property_id: str = Form(...), deltas_json: str = Form(...), name: str = Form("what_if")):
    try:
        import json
        deltas = json.loads(deltas_json)
        out = numbers_what_if(property_id, deltas, name)
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



