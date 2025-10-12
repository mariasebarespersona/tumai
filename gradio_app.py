# gradio_app.py
import env_loader  # loads .env first
import base64, os, uuid, re, unicodedata
import gradio as gr

from agentic import build_graph
from tools.property_tools import list_frameworks, list_properties as db_list_properties, add_property as db_add_property
from tools.property_tools import search_properties as db_search_properties
from tools.docs_tools import propose_slot, upload_and_link, list_docs, slot_exists
from tools.registry import transcribe_audio_tool  # decorator tool (Google STT)
from tools.rag_tool import summarize_document as rag_summarize, qa_document as rag_qa, qa_payment_schedule as rag_qa_pay
from tools.email_tool import send_email

agent = build_graph()

# simple in-memory UI state
STATE = {
    "property_id": None,
    "pending_proposal": None,
    "pending_file": None,
    "pending_files": [],  # list of dicts: {filename, data_bytes, proposal}
    "search_hits": [],     # last property search results for numeric selection
    "last_uploaded_doc": None,  # remembers last uploaded doc triple for quick follow-ups
    "session_id": str(uuid.uuid4()),
    "pending_create": False,  # awaiting name+address to create a property
    "last_listed_docs": [],   # cached list of doc lines for pagination
    "docs_list_pointer": 0,   # current pagination index
    "rag_backfilled": False,   # whether we've indexed all docs once
}

def _extract_final_ai_message(out: dict) -> str:
    """Extract the final AI message content from agent output."""
    if not isinstance(out, dict):
        return str(out)
    msgs = out.get("messages")
    if isinstance(msgs, list):
        for msg in reversed(msgs):
            if isinstance(msg, str):
                return msg
            content = getattr(msg, "content", None)
            tool_calls = getattr(msg, "tool_calls", None)
            if content and not tool_calls:
                return str(content)
    tr = out.get("tool_result")
    if tr is not None:
        return str(tr)
    return str(out)


def _normalize(s: str) -> str:
    """Lowercase + remove diacritics for robust matching (es/en)."""
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
    patterns = [
        r"\b(list|show|see|display)\s+(all\s+)?properties\b",
        r"\b(which|what)\s+properties\b",
        r"\b(propiedades?)\b.*\b(lista|listar|ver|mostrar|muestrame|mostrame|ensename|ensenarme)\b",
        r"\b(cuales|cuales|que|qué)\s+propiedades\b",
        r"\b(ensename|ensenarme|muestrame|mostrame)\b.*\bpropiedades\b",
        r"\bpropiedades\b.*\b(base\s+de\s+datos|bd)\b",
    ]
    for p in patterns:
        if re.search(p, t):
            return True
    if "propiedades" in t and any(v in t for v in ("lista", "listar", "ver", "mostrar", "muestrame", "mostrame", "ensename", "ensenarme")):
        return True
    if "properties" in t and any(v in t for v in ("list", "show", "see", "display", "which", "what")):
        return True
    return False


def _wants_missing_docs(text: str) -> bool:
    t = _normalize(text)
    patterns = [
        "falta", "faltan", "pendiente", "pendientes", "por subir",
        "necesito", "tengo que subir", "debo subir",
        "no he subido", "aun no he subido", "aún no he subido", "todavia no he subido", "todavía no he subido",
    ]
    return (
        ("documentos" in t and any(x in t for x in patterns))
        or re.search(r"\b(what|which)\s+documents\b", t) is not None
        or "documents to upload" in t
    )


def _wants_uploaded_docs(text: str) -> bool:
    t = _normalize(text)
    # Avoid matching phrases that imply missing/pending uploads
    negatives = [
        "no he subido", "aun no he subido", "aún no he subido",
        "todavia no he subido", "todavía no he subido",
        "no subidos", "no subido", "pendiente", "pendientes", "por subir",
    ]
    if any(neg in t for neg in negatives):
        return False
    return (
        ("documentos" in t and any(x in t for x in ("subido", "subidos", "cargado", "cargados", "ya", "he subido", "subi")))
        or ("documents" in t and ("uploaded" in t or "already" in t or "have uploaded" in t))
    )


def _wants_more(text: str) -> bool:
    t = _normalize(text)
    return any(p in t for p in ("mas", "más", "siguiente", "more", "next", "otro", "otra", "otra cosa"))


def _wants_email(text: str) -> bool:
    """Detect if user wants to send something via email."""
    t = _normalize(text)
    patterns = [
        "manda", "mandame", "envia", "enviame", "envía", "envíame",
        "manda.*email", "manda.*correo", "envia.*email", "envia.*correo",
        "por email", "por correo", "al email", "al correo",
        "send.*email", "email.*this", "email me"
    ]
    return any(p in t for p in patterns) or re.search(r"\b(manda|envia|enviame|mandame|send)\b.*\b(email|correo|mail)\b", t) is not None


def _extract_email(text: str) -> str | None:
    """Extract email address from text."""
    pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    match = re.search(pattern, text)
    return match.group(0) if match else None


def _wants_summary_this(text: str) -> bool:
    t = _normalize(text)
    return (
        ("resumen" in t or "resumeme" in t or "resume" in t or "sumariza" in t or "summary" in t)
        and ("este" in t or "ese" in t or "this" in t or "that" in t or "documento" in t or "document" in t)
    )


def _wants_index_all(text: str) -> bool:
    t = _normalize(text)
    return (
        ("indexa" in t or "indexar" in t or "reindexa" in t or "reindexar" in t)
        and ("documentos" in t or "todo" in t or "todos" in t)
    )


def _match_document_from_text(pid: str, text: str):
    """Best-effort: find a document mentioned in free text by matching tokens
    against `document_name`, and weakly against group/subgroup.
    Returns {group, subgroup, name} or None.
    """
    try:
        rows = list_docs(pid)
    except Exception:
        return None
    t = _normalize(text)
    
    # Remove common connector words that don't help matching
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
        group = _normalize(r.get("document_group", ""))
        subgroup = _normalize(r.get("document_subgroup", ""))
        
        # Clean document name too
        name_clean = name
        for sw in stopwords:
            name_clean = name_clean.replace(f" {sw} ", " ")
        
        score = 0
        name_tokens = [tok for tok in name_clean.split() if len(tok) > 2]
        
        # Perfect match: all significant tokens present
        if name_tokens and all(tok in t_clean for tok in name_tokens):
            score += 5
        # Good match: most tokens present
        elif name_tokens:
            matched = sum(1 for tok in name_tokens if tok in t_clean)
            if matched >= len(name_tokens) * 0.7:  # 70% match
                score += 4
            elif matched >= 2:  # At least 2 keywords
                score += 3
            elif matched == 1:
                score += 1
        
        # Bonus for subgroup/group match
        if subgroup:
            subgroup_tokens = [tok for tok in subgroup.split() if len(tok) > 2]
            if any(tok in t_clean for tok in subgroup_tokens):
                score += 1
        if group:
            group_tokens = [tok for tok in group.split() if len(tok) > 2]
            if any(tok in t_clean for tok in group_tokens):
                score += 0.5
        
        if score > best_score:
            best_score = score
            best = {
                "document_group": r.get("document_group", ""),
                "document_subgroup": r.get("document_subgroup", ""),
                "document_name": r.get("document_name", ""),
            }
    return best if best_score >= 3 else None


def _wants_property_search(text: str) -> bool:
    t = _normalize(text)
    # Evita confundir peticiones generales de "propiedades" con búsqueda de una propiedad concreta
    if "propiedades" in t or "properties" in t:
        return False
    # Busca expresiones que señalan una propiedad específica por nombre/dirección
    return bool(
        re.search(r"\bpropiedad\b", t)
        and re.search(r"(llama|llamada|nombre|direcci[oó]n|address)", t)
    )


def _wants_create_property(text: str) -> bool:
    t = _normalize(text)
    if "propiedad" not in t:
        return False
    patterns = [
        r"\b(crear|crea|crear\s+una\s+nueva|nueva|alta|dar\s+de\s+alta|anadir|añadir|agregar|add|create|add\s+property|create\s+property)\b",
        r"\b(nueva\s+propiedad)\b",
        r"\b(quiero|me\s+gustaria|me\s+gustaría|deseo).*\b(crear|nueva)\b",
    ]
    for p in patterns:
        if re.search(p, t):
            return True
    return False


def _extract_name_address(user_text: str):
    """Extract (name, address) from flexible English/Spanish patterns."""
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
    """Extract a likely property name mentioned after the word 'propiedad'."""
    if not user_text:
        return None
    # capture text after 'propiedad' with optional phrases
    m = re.search(r"(?i)propiedad\s*(?:que\s*se\s*llama|llamada|de\s*nombre)?\s*([\w\s\-\.]+)", user_text)
    if m:
        candidate = m.group(1).strip()
        # trim trailing filler
        candidate = re.sub(r"\s*(?:para|con|en|de)\s*$", "", candidate, flags=re.IGNORECASE)
        # avoid capturing too long sentences
        if 2 <= len(candidate) <= 120:
            return candidate
    return None


def respond(user_text, history, files):
    """Main chat handler: supports normal chat, property creation, and file uploads.
    Expects and returns history in Chatbot messages format: [{"role": ..., "content": ...}].
    """
    user_text = user_text or ""

    # Normalize incoming history to messages format
    messages = []
    if isinstance(history, list):
        for m in history:
            if isinstance(m, dict) and "role" in m and "content" in m:
                messages.append({"role": m["role"], "content": m["content"]})
            elif isinstance(m, (list, tuple)) and len(m) == 2:
                user_part, assistant_part = m
                if user_part:
                    messages.append({"role": "user", "content": str(user_part)})
                if assistant_part:
                    messages.append({"role": "assistant", "content": str(assistant_part)})

    # Numeric selection for last search hits
    if STATE.get("search_hits"):
        msel = re.match(r"^\s*(?:opcion|opción|option|n|num|numero|número)?\s*(\d+)\s*$", user_text.strip(), flags=re.IGNORECASE)
        if msel:
            idx = int(msel.group(1)) - 1
            hits = STATE["search_hits"]
            if 0 <= idx < len(hits):
                chosen = hits[idx]
                STATE["property_id"] = chosen["id"]
                STATE["search_hits"] = []
                try:
                    fr = list_frameworks(chosen["id"])
                    ack = (
                        f"Trabajaremos con: {chosen.get('name','(sin nombre)')} — {chosen.get('address','')}\n"
                        f"id: {chosen['id']}\n"
                        f"Frameworks: {fr}"
                    )
                except Exception:
                    ack = f"Trabajaremos con la propiedad id: {chosen['id']}"
                messages.append({"role": "assistant", "content": ack})
                return messages, gr.update(value=None), gr.update(value="")

    # If the user mentions a UUID, set it as the active property
    mentioned_pid = _extract_uuid(user_text)
    if mentioned_pid:
        STATE["property_id"] = mentioned_pid

    filenames = []
    if files:
        for fp in (files if isinstance(files, list) else [files]):
            if fp:
                filenames.append(os.path.basename(fp))
    display_text = user_text
    if filenames:
        display_text = f"{user_text}\n\n📎 {', '.join(filenames)}"
    messages.append({"role": "user", "content": display_text})

    # Handle email requests
    if _wants_email(user_text) or STATE.get("pending_email"):
        # Check if user provided email directly in the message
        email = _extract_email(user_text)
        
        if STATE.get("pending_email"):
            # We already asked for email, waiting for response
            if email:
                # Send the pending content
                content_to_send = STATE.get("email_content", "")
                subject = STATE.get("email_subject", "Información de RAMA AI")
                try:
                    send_email(
                        to=[email],
                        subject=subject,
                        html=f"<html><body><pre style='font-family: sans-serif; white-space: pre-wrap;'>{content_to_send}</pre></body></html>"
                    )
                    messages.append({"role": "assistant", "content": f"✅ Email enviado correctamente a {email}"})
                    # Clean up state
                    STATE["pending_email"] = False
                    STATE["email_content"] = None
                    STATE["email_subject"] = None
                    return messages, gr.update(value=None), gr.update(value="")
                except Exception as e:
                    messages.append({"role": "assistant", "content": f"❌ Error al enviar email: {e}"})
                    STATE["pending_email"] = False
                    return messages, gr.update(value=None), gr.update(value="")
            else:
                messages.append({"role": "assistant", "content": "No he podido extraer un email válido. Por favor, proporciona tu dirección de email (ejemplo: tu@email.com)"})
                return messages, gr.update(value=None), gr.update(value="")
        
        elif _wants_email(user_text):
            # User wants to send something by email
            # Check if we have content from previous message
            if len(messages) >= 2 and messages[-2].get("role") == "assistant":
                # Get the last assistant message as the content to send
                content = messages[-2].get("content", "")
                if content and not any(x in content for x in ["No he podido", "No aparece en los documentos", "Error"]):
                    # If email was provided in same message, send immediately
                    if email:
                        try:
                            send_email(
                                to=[email],
                                subject="Información de RAMA AI",
                                html=f"<html><body><pre style='font-family: sans-serif; white-space: pre-wrap;'>{content}</pre></body></html>"
                            )
                            messages.append({"role": "assistant", "content": f"✅ Email enviado correctamente a {email}"})
                            return messages, gr.update(value=None), gr.update(value="")
                        except Exception as e:
                            messages.append({"role": "assistant", "content": f"❌ Error al enviar email: {e}"})
                            return messages, gr.update(value=None), gr.update(value="")
                    else:
                        # Ask for email
                        STATE["pending_email"] = True
                        STATE["email_content"] = content
                        STATE["email_subject"] = "Información de RAMA AI"
                        messages.append({"role": "assistant", "content": "Por supuesto. ¿A qué dirección de email te lo envío?"})
                        return messages, gr.update(value=None), gr.update(value="")
            # No content to send
            messages.append({"role": "assistant", "content": "¿Qué información te gustaría que te enviara por email?"})
            return messages, gr.update(value=None), gr.update(value="")

    # Primero: listados generales de propiedades
    if _wants_list_properties(user_text):
        try:
            rows = db_list_properties(limit=30)
        except Exception as e:
            messages.append({"role": "assistant", "content": f"Error al listar propiedades / Error listing properties: {e}"})
            return messages, gr.update(value=None), gr.update(value="")
        if not rows:
            messages.append({"role": "assistant", "content": "No hay propiedades en la base de datos todavía."})
            return messages, gr.update(value=None), gr.update(value="")
        lines = [f"- {r.get('name','(sin nombre)')} — {r.get('address','')} — id: {r.get('id')}" for r in rows]
        messages.append({"role": "assistant", "content": "Propiedades encontradas:\n" + "\n".join(lines)})
        return messages, gr.update(value=None), gr.update(value="")

    # Crear una nueva propiedad (intención explícita)
    if _wants_create_property(user_text):
        STATE["pending_create"] = True
        # Extrae nombre y dirección si están presentes en el mismo mensaje
        name_val, addr_val = _extract_name_address(user_text)
        name_val = name_val or _extract_property_query(user_text)
        if name_val and addr_val:
            try:
                row = db_add_property(name_val, addr_val)
                STATE["property_id"] = row["id"]
                STATE["pending_create"] = False
                fr = list_frameworks(row["id"])  # muestra los esquemas derivados
                messages.append({"role": "assistant", "content": f"✅ Propiedad creada: {row['name']} — {row['address']}\nid: {row['id']}\nFrameworks: {fr}"})
                return messages, gr.update(value=None), gr.update(value="")
            except Exception as e:
                messages.append({"role": "assistant", "content": f"No he podido crear la propiedad: {e}"})
                return messages, gr.update(value=None), gr.update(value="")
        else:
            messages.append({"role": "assistant", "content": "Para crear la propiedad necesito nombre y dirección. Ejemplo: 'nombre: Casa Demo 5 dirección: Calle Hermosilla 11'"})
            return messages, gr.update(value=None), gr.update(value="")

    # Búsqueda por nombre/dirección (propiedad concreta)
    if _wants_property_search(user_text):
        name_val, addr_val = _extract_name_address(user_text)
        prop_q = _extract_property_query(user_text)
        query = prop_q or name_val or addr_val or user_text
        try:
            hits = db_search_properties(query, limit=5)
        except Exception as e:
            messages.append({"role": "assistant", "content": f"No he podido buscar propiedades: {e}"})
            return messages, gr.update(value=None), gr.update(value="")
        if not hits:
            # Si no hay coincidencias, intenta mostrar el listado general
            try:
                rows = db_list_properties(limit=10)
                if rows:
                    lines = [f"- {r.get('name','(sin nombre)')} — {r.get('address','')} — id: {r.get('id')}" for r in rows]
                    messages.append({"role": "assistant", "content": "No encontré coincidencias. Estas son las propiedades recientes:\n" + "\n".join(lines)})
                else:
                    messages.append({"role": "assistant", "content": "No encontré propiedades que coincidan. Prueba con otro nombre o dirección."})
            except Exception:
                messages.append({"role": "assistant", "content": "No encontré propiedades que coincidan. Prueba con otro nombre o dirección."})
            return messages, gr.update(value=None), gr.update(value="")
        STATE["search_hits"] = hits
        lines = [f"{i+1}. {h['name']} — {h.get('address','')} — id: {h['id']}" for i, h in enumerate(hits)]
        messages.append({"role": "assistant", "content": "He encontrado estas propiedades:\n" + "\n".join(lines) + "\n\nResponde con el número o pega el id para continuar."})
        return messages, gr.update(value=None), gr.update(value="")

    # Indexación manual bajo demanda
    if _wants_index_all(user_text):
        pid = STATE.get("property_id")
        if not pid:
            messages.append({"role": "assistant", "content": "Primero fija una propiedad para indexar sus documentos."})
            return messages, gr.update(value=None), gr.update(value="")
        try:
            from tools.registry import rag_index_all_documents_tool as _idxall
            out = _idxall.invoke({"property_id": pid})
            STATE["rag_backfilled"] = True
            extra = ""
            if out.get("warning"):
                extra = f"\nAviso: {out.get('warning')}"
            if out.get("error"):
                extra = f"\nError: {out.get('error')}"
            detail_lines = []
            for d in (out.get("details") or [])[:8]:
                w = f" — {d.get('warning')}" if d.get('warning') else ""
                e = f" — error: {d.get('error')}" if d.get('error') else ""
                detail_lines.append(f"- {d.get('doc')} → {d.get('indexed',0)}{w}{e}")
            details = ("\n" + "\n".join(detail_lines)) if detail_lines else ""
            messages.append({"role": "assistant", "content": f"Indexación completada: {out.get('indexed', 0)} fragmentos.{extra}{details}"})
            return messages, gr.update(value=None), gr.update(value="")
        except Exception as e:
            messages.append({"role": "assistant", "content": f"No pude indexar: {e}"})
            return messages, gr.update(value=None), gr.update(value="")

    # Bilingual fallback: which documents are uploaded already
    if _wants_uploaded_docs(user_text):
        pid = STATE.get("property_id")
        if not pid:
            messages.append({"role": "assistant", "content": "¿En qué propiedad estamos trabajando? Proporcióname el UUID o elige una propiedad por nombre."})
            return messages, gr.update(value=None), gr.update(value="")
        try:
            rows = list_docs(pid)
            uploaded = [r for r in rows if r.get('storage_key')]
            if uploaded:
                # Pagina de 5 en 5 y habilita "más"
                STATE["last_listed_docs"] = [
                    f"- {r['document_group']} / {r.get('document_subgroup','')} / {r['document_name']}" for r in uploaded
                ]
                STATE["docs_list_pointer"] = 0
                chunk = STATE["last_listed_docs"][0:5]
                STATE["docs_list_pointer"] = len(chunk)
                more_hint = "\n\nEscribe 'más' para ver más." if len(STATE["last_listed_docs"]) > STATE["docs_list_pointer"] else ""
                reply = "Documentos ya subidos:\n" + "\n".join(chunk) + more_hint
                # Prepara selección numérica a partir del listado
                STATE["search_hits"] = [
                    {"id": r.get("document_name"), "name": r.get("document_name"), "address": f"{r['document_group']} / {r.get('document_subgroup','')} / {r['document_name']}"}
                    for r in uploaded
                ]
                # Si hay exactamente uno, guarda referencia para follow-up (resumen, abrir, etc.)
                if len(uploaded) == 1:
                    u = uploaded[0]
                    STATE["last_uploaded_doc"] = {
                        "document_group": u["document_group"],
                        "document_subgroup": u.get("document_subgroup", ""),
                        "document_name": u["document_name"],
                    }
            else:
                reply = "Aún no hay documentos subidos para esta propiedad."
            messages.append({"role": "assistant", "content": reply})
            return messages, gr.update(value=None), gr.update(value="")
        except Exception as e:
            messages.append({"role": "assistant", "content": f"No he podido consultar los documentos: {e}"})
            return messages, gr.update(value=None), gr.update(value="")

    # Follow-up: summarize the last uploaded document quickly (or best match)
    if _wants_summary_this(user_text):
        pid = STATE.get("property_id")
        ref = STATE.get("last_uploaded_doc") or (_match_document_from_text(pid, user_text) if pid else None)
        if pid and ref:
            try:
                out = rag_summarize(pid, ref["document_group"], ref.get("document_subgroup", ""), ref["document_name"])
                messages.append({"role": "assistant", "content": f"Resumen de {ref['document_group']} / {ref.get('document_subgroup','')} / {ref['document_name']}:\n\n{out.get('summary','(sin contenido)')}"})
                return messages, gr.update(value=None), gr.update(value="")
            except Exception as e:
                messages.append({"role": "assistant", "content": f"No he podido resumir el documento: {e}"})
                return messages, gr.update(value=None), gr.update(value="")
        # si no hay referencia, cae al flujo normal/agent
    # Generic summary intent (RAG) when user says "hazme un resumen del contrato X"
    if re.search(r"(?i)resumen|resume|resumeme|resúmeme", user_text):
        pid = STATE.get("property_id")
        if pid:
            try:
                from tools.registry import rag_qa_with_citations_tool as _ragqa
                qa = _ragqa.invoke({"property_id": pid, "query": user_text, "top_k": 6})
                messages.append({"role": "assistant", "content": qa.get("answer", "(sin respuesta)")})
                return messages, gr.update(value=None), gr.update(value="")
            except Exception:
                pass

    # Check if user is asking a question about a specific document
    # Priority: use RAG QA with citations for ANY question about ANY document
    qnorm = _normalize(user_text)
    question_words = ["qué", "que", "cual", "cuál", "cuando", "cuándo", "donde", "dónde", 
                      "cómo", "como", "por qué", "porque", "cuanto", "cuánto", "cuanta", "cuánta",
                      "quien", "quién", "lee el", "que pone", "qué pone", "que dice", "qué dice",
                      "dime", "explicame", "explícame"]
    is_question = any(w in qnorm for w in question_words)
    
    if is_question:
        pid = STATE.get("property_id")
        # Prioritize document mentioned in current text over last uploaded doc
        ref = (_match_document_from_text(pid, user_text) if pid else None) or STATE.get("last_uploaded_doc")
        if pid:
            try:
                from tools.registry import rag_qa_with_citations_tool as _ragqa
                # If we found a specific document reference, filter by it
                if ref:
                    qa = _ragqa.invoke({
                        "property_id": pid, 
                        "query": user_text, 
                        "top_k": 6,
                        "document_name": ref["document_name"],
                        "document_group": ref["document_group"],
                        "document_subgroup": ref.get("document_subgroup", "")
                    })
                else:
                    # Search across all documents
                    qa = _ragqa.invoke({"property_id": pid, "query": user_text, "top_k": 6})
                
                ans = qa.get("answer", "(sin respuesta)")
                cits = qa.get("citations") or []
                if cits:
                    lines = [f"- {c['document_group']} / {c.get('document_subgroup','')} / {c['document_name']} (trozo {c['chunk_index']})" for c in cits]
                    ans += "\n\nFuentes:\n" + "\n".join(lines)
                messages.append({"role": "assistant", "content": ans})
                return messages, gr.update(value=None), gr.update(value="")
            except Exception as e:
                messages.append({"role": "assistant", "content": f"No he podido responder: {e}"})
                return messages, gr.update(value=None), gr.update(value="")

    # Pagination: user asked for "más" after listing documents
    if _wants_more(user_text) and STATE.get("last_listed_docs"):
        docs = STATE["last_listed_docs"]
        ptr = STATE.get("docs_list_pointer", 0)
        if ptr < len(docs):
            next_chunk = docs[ptr:ptr+5]
            STATE["docs_list_pointer"] = ptr + len(next_chunk)
            more_hint = "\n\nEscribe 'más' para ver más." if len(docs) > STATE["docs_list_pointer"] else ""
            messages.append({"role": "assistant", "content": "Más documentos:\n" + "\n".join(next_chunk) + more_hint})
            return messages, gr.update(value=None), gr.update(value="")
        else:
            messages.append({"role": "assistant", "content": "No hay más documentos para mostrar."})
            return messages, gr.update(value=None), gr.update(value="")

    # Bilingual fallback: which documents are missing / need to upload
    if _wants_missing_docs(user_text):
        pid = STATE.get("property_id")
        if not pid:
            messages.append({"role": "assistant", "content": "¿En qué propiedad estamos trabajando? Proporcióname el UUID de la propiedad o di \"nueva\" para crear una."})
            return messages, gr.update(value=None), gr.update(value="")
        try:
            rows = list_docs(pid)
            missing = [
                f"- {r['document_group']} / {r.get('document_subgroup','')} / {r['document_name']}"
                for r in rows if not r.get('storage_key')
            ]
            if missing:
                reply = "Documentos pendientes de subir:\n" + "\n".join(missing)
            else:
                reply = "No hay documentos pendientes. Todos los slots tienen fichero subido."
            messages.append({"role": "assistant", "content": reply})
            return messages, gr.update(value=None), gr.update(value="")
        except Exception as e:
            messages.append({"role": "assistant", "content": f"No he podido consultar los documentos: {e}"})
            return messages, gr.update(value=None), gr.update(value="")

    # If files were provided: propose slots and ask for confirmation
    if files:
        pending_list = []
        for fp in (files if isinstance(files, list) else [files]):
            if not fp:
                continue
            with open(fp, "rb") as f:
                data = f.read()
            fname = os.path.basename(fp)
            proposal = propose_slot(fname, text_hint=user_text or "")
            # UI-side guard: check that the proposed slot exists; if no, include hint
            pid = STATE.get("property_id")
            slot_hint = ""
            if pid:
                try:
                    chk = slot_exists(pid, proposal["document_group"], proposal.get("document_subgroup", ""), proposal["document_name"])
                    if not (chk or {}).get("exists"):
                        cand = (chk or {}).get("candidates", [])
                        if cand:
                            slot_hint = f" (nota: no existe esa celda, candidatos: {', '.join(cand[:5])})"
                        else:
                            slot_hint = " (nota: no existe esa celda en este grupo/subgrupo)"
                except Exception:
                    pass
            pending_list.append({"filename": fname, "data": data, "proposal": proposal})
        STATE["pending_files"] = pending_list
        lines = []
        for p in pending_list:
            pr = p["proposal"]
            lines.append(f"{p['filename']}: {pr['document_group']} / {pr.get('document_subgroup','')} / {pr['document_name']}")
        assist = "Propongo las siguientes ubicaciones:\n- " + "\n- ".join(lines) + "\n\n¿Confirmas la subida? (sí/no)"
        messages.append({"role": "assistant", "content": assist})
        return messages, gr.update(value=None), gr.update(value="")

    # If awaiting file confirmation: handle yes/no
    text_lower = (user_text or "").strip().lower()
    if STATE.get("pending_files"):
        if any(w in text_lower for w in ("yes", "confirm", "ok", "go ahead", "si", "sí", "proceed")):
            pid = STATE.get("property_id")
            if not pid:
                messages.append({"role": "assistant", "content": "No hay propiedad activa. Crea una primero (p. ej., 'nombre: X dirección: Y')."})
                return messages, gr.update(value=None), gr.update(value="")
            uploaded_msgs = []
            last_ref = None
            for p in STATE["pending_files"]:
                prop = p["proposal"]
                out = upload_and_link(
                    pid,
                    p["data"],
                    p["filename"],
                    prop["document_group"],
                    prop.get("document_subgroup", ""),
                    prop["document_name"],
                    {},
                )
                show_name = out.get("document_name") or prop["document_name"]
                uploaded_msgs.append(f"✅ Subido '{show_name}'. URL firmada (1h): {out.get('signed_url')}")
                last_ref = {
                    "document_group": prop["document_group"],
                    "document_subgroup": prop.get("document_subgroup", ""),
                    "document_name": show_name,
                }
                # Try to index the document for RAG (best effort)
                try:
                    from tools.registry import rag_index_document_tool as _idx
                    _ = _idx.invoke({
                        "property_id": pid,
                        "document_group": prop["document_group"],
                        "document_subgroup": prop.get("document_subgroup", ""),
                        "document_name": show_name,
                    })
                except Exception:
                    pass
                # Invalida cache de listados para que "más" se regenere con todos
                STATE["last_listed_docs"] = []
                STATE["docs_list_pointer"] = 0
            STATE["pending_files"] = []
            if last_ref:
                STATE["last_uploaded_doc"] = last_ref
            messages.append({"role": "assistant", "content": "\n".join(uploaded_msgs)})
            return messages, gr.update(value=None), gr.update(value="")
        elif any(w in text_lower for w in ("no", "cancel", "change", "different")):
            STATE["pending_files"] = []
            messages.append({"role": "assistant", "content": "Hecho, cancelado. Puedes subir de nuevo o indicar detalles distintos."})
            return messages, gr.update(value=None), gr.update(value="")

    # If we were awaiting create details, try to parse name+address now
    if STATE.get("pending_create"):
        name_val, addr_val = _extract_name_address(user_text)
        name_val = name_val or _extract_property_query(user_text)
        if name_val and addr_val:
            try:
                row = db_add_property(name_val, addr_val)
                STATE["property_id"] = row["id"]
                STATE["pending_create"] = False
                fr = list_frameworks(row["id"])  # muestra los esquemas derivados
                messages.append({"role": "assistant", "content": f"✅ Propiedad creada: {row['name']} — {row['address']}\nid: {row['id']}\nFrameworks: {fr}"})
                return messages, gr.update(value=None), gr.update(value="")
            except Exception as e:
                messages.append({"role": "assistant", "content": f"No he podido crear la propiedad: {e}"})
                return messages, gr.update(value=None), gr.update(value="")

    # If the user asks an open question unrelated to UI-specific intents → use RAG QA with citations by default
    if not any([
        _wants_list_properties(user_text),
        _wants_property_search(user_text),
        _wants_uploaded_docs(user_text),
        _wants_missing_docs(user_text),
        _wants_index_all(user_text),
        files,
        STATE.get("pending_files"),
        STATE.get("pending_create"),
    ]):
        pid = STATE.get("property_id")
        if pid and user_text.strip():
            # Si aún no hemos backfilleado, intenta una vez
            if not STATE.get("rag_backfilled"):
                try:
                    from tools.registry import rag_index_all_documents_tool as _idxall
                    _idxall.invoke({"property_id": pid})
                    STATE["rag_backfilled"] = True
                except Exception:
                    pass
            try:
                from tools.registry import rag_qa_with_citations_tool as _ragqa
                qa = _ragqa.invoke({"property_id": pid, "query": user_text, "top_k": 5})
                ans = qa.get("answer", "(sin respuesta)")
                cits = qa.get("citations") or []
                if cits:
                    lines = [f"- {c['document_group']} / {c.get('document_subgroup','')} / {c['document_name']} (trozo {c['chunk_index']})" for c in cits]
                    ans += "\n\nFuentes:\n" + "\n".join(lines)
                messages.append({"role": "assistant", "content": ans})
                return messages, gr.update(value=None), gr.update(value="")
            except Exception as e:
                messages.append({"role": "assistant", "content": f"No he podido ejecutar RAG QA: {e}"})
                return messages, gr.update(value=None), gr.update(value="")

    # Normal agent chat flow
    pid = STATE.get("property_id")
    thread_id = f"property-{pid}" if pid else f"session-{STATE['session_id']}"
    config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 50}
    # Pass last uploaded doc as agent context so it can run qa_document on follow-up questions
    last_ref = STATE.get("last_uploaded_doc") or None
    payload = {"input": user_text, "property_id": pid}
    if last_ref:
        payload["last_doc_ref"] = last_ref
    out = agent.invoke(payload, config=config)

    pid_out = out.get("property_id") or ((out.get("tool_result") or {}).get("id") if isinstance(out.get("tool_result"), dict) else None)
    extra = ""
    if pid_out:
        STATE["property_id"] = pid_out
        try:
            fr = list_frameworks(pid_out)
            extra = f"\n\nFrameworks: {fr}"
        except Exception:
            extra = ""

    final_msg = _extract_final_ai_message(out) + extra
    messages.append({"role": "assistant", "content": final_msg})
    return messages, gr.update(value=None), gr.update(value="")


with gr.Blocks(title="Property Agent (LangGraph)") as demo:
    gr.Markdown("# 🏠 Property Agent — Chat")

    chat = gr.Chatbot(height=560, type="messages")
    with gr.Row():
        msg = gr.Textbox(label="Message", placeholder="Escribe aquí… p. ej., 'nombre: Casa Bonita dirección: Madrid'", scale=8)
        upload = gr.File(label="Adjuntar archivos", file_count="multiple", type="filepath", scale=2)
        send = gr.Button("Enviar", variant="primary")

    send.click(respond, inputs=[msg, chat, upload], outputs=[chat, upload, msg])
    msg.submit(respond, inputs=[msg, chat, upload], outputs=[chat, upload, msg])


demo.queue()
