from __future__ import annotations
import io, requests, zipfile, datetime as dt, re
from typing import Dict, Optional, Any
from urllib.parse import urlparse
from os.path import splitext
from xml.etree import ElementTree as ET
from .docs_tools import signed_url_for
from langchain_openai import ChatOpenAI

try:
    from pypdf import PdfReader
except Exception:  # pypdf is optional but present in requirements
    PdfReader = None


def _extract_text_from_docx(data: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            xml_bytes = zf.read("word/document.xml")
        root = ET.fromstring(xml_bytes)
        # DOCX paragraphs -> itertext
        return "\n".join("".join(el.itertext()) for el in root.iter())
    except Exception:
        return ""


def _extract_text(content: bytes, content_type: str, url: str) -> str:
    ext = splitext(urlparse(url).path)[1].lower()
    ct = (content_type or "").lower()

    # PDF
    if (ext == ".pdf" or "application/pdf" in ct) and PdfReader is not None:
        try:
            reader = PdfReader(io.BytesIO(content))
            pages = min(len(reader.pages), 10)
            text = []
            for i in range(pages):
                try:
                    text.append(reader.pages[i].extract_text() or "")
                except Exception:
                    pass
            return "\n".join(text)
        except Exception:
            pass

    # DOCX
    if ext == ".docx" or "officedocument.wordprocessingml.document" in ct:
        t = _extract_text_from_docx(content)
        if t:
            return t

    # TXT
    if ext == ".txt" or ct.startswith("text/"):
        try:
            return content.decode("utf-8", errors="ignore")
        except Exception:
            return ""

    # Fallback: best-effort decode
    try:
        return content.decode("utf-8", errors="ignore")
    except Exception:
        # OCR fallback for images (very basic, optional)
        try:
            import pytesseract
            from PIL import Image
            import numpy as np
            img = Image.open(io.BytesIO(content))
            return pytesseract.image_to_string(img)
        except Exception:
            return ""


def summarize_document(property_id: str, group: str, subgroup: str, name: str, model: str = None, max_sentences: int = 5) -> Dict:
    """Summarize a document. If the exact name doesn't match, tries to find a close match using list_docs."""
    import logging
    logger = logging.getLogger(__name__)
    
    # Try the exact name first
    try:
        url = signed_url_for(property_id, group, subgroup, name, expires=600)
        resp = requests.get(url)
        text = _extract_text(resp.content, resp.headers.get("content-type", ""), url)
    except Exception as e:
        logger.warning(f"Could not find document with exact name '{name}', trying fuzzy match: {e}")
        # If exact match fails, try to find similar document
        from .docs_tools import list_docs
        try:
            docs = list_docs(property_id)
            # Find documents with storage_key (uploaded)
            uploaded_docs = [d for d in docs if d.get('storage_key')]
            
            # Try case-insensitive match first
            name_lower = name.lower()
            for doc in uploaded_docs:
                doc_name = doc.get('document_name', '')
                if doc_name.lower() == name_lower:
                    logger.info(f"Found case-insensitive match: {doc_name}")
                    group = doc.get('document_group', group)
                    subgroup = doc.get('document_subgroup', subgroup)
                    name = doc_name
                    url = signed_url_for(property_id, group, subgroup, name, expires=600)
                    resp = requests.get(url)
                    text = _extract_text(resp.content, resp.headers.get("content-type", ""), url)
                    break
            else:
                # Try partial match (contains)
                for doc in uploaded_docs:
                    doc_name = doc.get('document_name', '')
                    if name_lower in doc_name.lower() or doc_name.lower() in name_lower:
                        logger.info(f"Found partial match: {doc_name}")
                        group = doc.get('document_group', group)
                        subgroup = doc.get('document_subgroup', subgroup)
                        name = doc_name
                        url = signed_url_for(property_id, group, subgroup, name, expires=600)
                        resp = requests.get(url)
                        text = _extract_text(resp.content, resp.headers.get("content-type", ""), url)
                        break
                else:
                    raise ValueError(f"No document found matching '{name}'")
        except Exception as fuzzy_error:
            logger.error(f"Fuzzy match also failed: {fuzzy_error}")
            return {
                "summary": f"No se pudo encontrar el documento '{name}'. Por favor, verifica el nombre del documento con list_docs.",
                "signed_url": None,
            }

    if not text.strip():
        # No textual content extracted; return a helpful message
        return {
            "summary": "No se pudo extraer texto del documento (p. ej., imagen o formato no compatible).",
            "signed_url": url,
        }

    # Limit size for prompt
    text = text[:40000]
    # Use gpt-4o-mini to avoid rate limiting (separate TPM quota from gpt-4o)
    llm = ChatOpenAI(model=model or "gpt-4o-mini")
    prompt = (
        f"Resume en español en un máximo de {max_sentences} frases. "
        "Incluye solo el contenido del documento, sin hablar de metadatos ni estructura del archivo.\n\n"
        f"Contenido:\n{text}"
    )
    summary = llm.invoke(prompt).content
    return {"summary": summary, "signed_url": url}


def qa_document(property_id: str, group: str, subgroup: str, name: str, question: str, model: Optional[str] = None, max_chars: int = 60000) -> Dict:
    """Answer a focused question about a single stored document.

    Fetches the document via a signed URL, extracts text, and uses an LLM to
    answer the user's question in Spanish. Returns an answer and the signed URL.
    If the exact name doesn't match, tries to find a close match using list_docs.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    # Try the exact name first
    try:
        url = signed_url_for(property_id, group, subgroup, name, expires=600)
        resp = requests.get(url)
        text = _extract_text(resp.content, resp.headers.get("content-type", ""), url)
    except Exception as e:
        logger.warning(f"Could not find document with exact name '{name}', trying fuzzy match: {e}")
        # If exact match fails, try to find similar document
        from .docs_tools import list_docs
        try:
            docs = list_docs(property_id)
            uploaded_docs = [d for d in docs if d.get('storage_key')]
            
            # Try case-insensitive match first
            name_lower = name.lower()
            for doc in uploaded_docs:
                doc_name = doc.get('document_name', '')
                if doc_name.lower() == name_lower:
                    logger.info(f"Found case-insensitive match: {doc_name}")
                    group = doc.get('document_group', group)
                    subgroup = doc.get('document_subgroup', subgroup)
                    name = doc_name
                    url = signed_url_for(property_id, group, subgroup, name, expires=600)
                    resp = requests.get(url)
                    text = _extract_text(resp.content, resp.headers.get("content-type", ""), url)
                    break
            else:
                # Try partial match (contains)
                for doc in uploaded_docs:
                    doc_name = doc.get('document_name', '')
                    if name_lower in doc_name.lower() or doc_name.lower() in name_lower:
                        logger.info(f"Found partial match: {doc_name}")
                        group = doc.get('document_group', group)
                        subgroup = doc.get('document_subgroup', subgroup)
                        name = doc_name
                        url = signed_url_for(property_id, group, subgroup, name, expires=600)
                        resp = requests.get(url)
                        text = _extract_text(resp.content, resp.headers.get("content-type", ""), url)
                        break
                else:
                    raise ValueError(f"No document found matching '{name}'")
        except Exception as fuzzy_error:
            logger.error(f"Fuzzy match also failed: {fuzzy_error}")
            return {
                "answer": f"No se pudo encontrar el documento '{name}'. Por favor, verifica el nombre del documento con list_docs.",
                "signed_url": None,
            }

    if not text.strip():
        return {
            "answer": "No se pudo extraer texto del documento (podría ser una imagen o un formato no compatible).",
            "signed_url": url,
        }

    today = dt.date.today().isoformat()
    text = text[:max_chars]
    # Use gpt-4o-mini to avoid rate limiting (separate TPM quota from gpt-4o)
    llm = ChatOpenAI(model=model or "gpt-4o-mini")
    prompt = (
        "Eres un asistente legal/administrativo. Responde en español con una frase clara y directa. "
        "Si el documento no contiene la información solicitada, di explícitamente que no aparece. "
        f"Hoy es {today}. Pregunta del usuario: {question}\n\n"
        "Texto del documento (parcial):\n" + text
    )
    answer = llm.invoke(prompt).content
    return {"answer": answer, "signed_url": url}


def _norm(s: str) -> str:
    s = s.lower()
    mapping = {
        "á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u", "ñ": "n",
    }
    for k, v in mapping.items():
        s = s.replace(k, v)
    return s


SPAN_WORD_TO_NUM = {
    "uno": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6,
    "siete": 7, "ocho": 8, "nueve": 9, "diez": 10, "once": 11, "doce": 12,
    "trece": 13, "catorce": 14, "quince": 15, "dieciseis": 16, "dieciséis": 16,
    "diecisiete": 17, "dieciocho": 18, "diecinueve": 19, "veinte": 20,
    "veintiuno": 21, "veintidos": 22, "veintidós": 22, "veintitres": 23, "veintitrés": 23,
    "veinticuatro": 24, "veinticinco": 25, "veintiseis": 26, "veintiséis": 26,
    "veintisiete": 27, "veintiocho": 28, "veintinueve": 29, "treinta": 30,
    "treinta y uno": 31,
}


def _extract_payment_info(text: str) -> Dict[str, Any]:
    t = _norm(text)
    info: Dict[str, Any] = {"amounts_eur": []}

    # Amounts like 1.200,00 € or 1500 €
    for m in re.finditer(r"(\d{1,3}(?:[\.\s]\d{3})*(?:,\d{1,2})?|\d+(?:,\d{1,2})?)\s*(?:€|eur|euros)", t):
        amt = m.group(1)
        amt_norm = float(amt.replace(".", "").replace(" ", "").replace(",", "."))
        info["amounts_eur"].append(amt_norm)

    # Frequency / cadence
    if re.search(r"\banual(?:mente)?(es)?\b|cada\s+a[nñ]o\b|una\s+vez\s+al\s+a[nñ]o", t):
        info["frequency"] = "yearly"
    elif re.search(r"\btrimestral(?:mente)?(es)?\b|cada\s+trimestre\b|cada\s+3\s+meses\b", t):
        info["frequency"] = "quarterly"
    elif re.search(r"\bmensual(?:mente)?(es)?\b|cada\s+mes\b", t):
        info["frequency"] = "monthly"
    elif re.search(r"\bquincenal|cada\s+15\s*dias\b", t):
        info["frequency"] = "every_15_days"
    elif re.search(r"\bsemanal|cada\s+semana\b", t):
        info["frequency"] = "weekly"
    
    # Number of payments / installments
    # "6 cuotas", "12 pagos", "en 3 plazos"
    m = re.search(r"(\d{1,2})\s*(?:cuotas?|pagos?|plazos?|mensualidades?|facturas?)", t)
    if m:
        info["total_payments"] = int(m.group(1))
    
    # Contract duration: "durante 1 año", "por 2 años", "contrato de 3 años"
    m = re.search(r"(?:durante|por|de)\s+(\d{1,2})\s+a[nñ]os?", t)
    if m:
        info["contract_years"] = int(m.group(1))

    # Day of month patterns
    # 1) "dia 15 de cada mes" / "el 10 de cada mes" / "el día 5 de cada mes"
    m = re.search(r"(?:dia|d[ii]a)\s+(\d{1,2})\s+de\s+cada\s+mes", t)
    if m:
        try:
            info["day_of_month"] = int(m.group(1))
            info.setdefault("frequency", "monthly")
        except Exception:
            pass

    # Alternative phrasing: "el 5 de cada mes" / "el día 5 de cada mes"
    m = re.search(r"\bel\s+(?:dia\s+)?(\d{1,2})\s+de\s+cada\s+mes\b", t)
    if m and "day_of_month" not in info:
        try:
            info["day_of_month"] = int(m.group(1))
            info.setdefault("frequency", "monthly")
        except Exception:
            pass

    # 2) "el 5 del mes" / "dia 5 del mes"
    m = re.search(r"(?:el\s+)?(?:dia\s+)?(\d{1,2})\s+del\s+mes", t)
    if m and "day_of_month" not in info:
        try:
            info["day_of_month"] = int(m.group(1))
            info.setdefault("frequency", "monthly")
        except Exception:
            pass

    # Spelled number: "el dia cinco de cada mes"
    m = re.search(r"\bel\s+(?:dia\s+)?([a-z\s]+?)\s+de\s+cada\s+mes\b", t)
    if m and "day_of_month" not in info:
        word = m.group(1).strip()
        if word in SPAN_WORD_TO_NUM:
            info["day_of_month"] = SPAN_WORD_TO_NUM[word]
            info.setdefault("frequency", "monthly")

    # Spelled number with "del mes": "el cinco del mes"
    m = re.search(r"\bel\s+([a-z\s]+?)\s+del\s+mes\b", t)
    if m and "day_of_month" not in info:
        word = m.group(1).strip()
        if word in SPAN_WORD_TO_NUM:
            info["day_of_month"] = SPAN_WORD_TO_NUM[word]
            info.setdefault("frequency", "monthly")

    # "mensual ... día 5" pattern (allow some words between)
    m = re.search(r"mensual(?:mente)?[^.\n]{0,40}?(?:dia|d[ií]a|el)\s+(\d{1,2})", t)
    if m and "day_of_month" not in info:
        try:
            info["day_of_month"] = int(m.group(1))
            info.setdefault("frequency", "monthly")
        except Exception:
            pass

    # Method of payment (transferencia, domiciliacion, efectivo, cheque...)
    if "transferencia" in t or "iban" in t:
        info["method"] = "transferencia bancaria"
    elif "domiciliacion" in t or "domiciliación" in t:
        info["method"] = "domiciliación bancaria"
    elif "efectivo" in t:
        info["method"] = "efectivo"
    elif "cheque" in t:
        info["method"] = "cheque"

    # Every N days
    m = re.search(r"cada\s+(\d{1,3})\s*dias", t)
    if m:
        info["every_n_days"] = int(m.group(1))

    # Triggers
    triggers = []
    if "a la firma" in t or "a la formalizacion" in t or "a la formalizacion" in t:
        triggers.append("at_signing")
    if "al inicio" in t or "al comienzo" in t:
        triggers.append("at_start")
    if "al finalizar" in t or "a la finalizacion" in t or "a la finalizacion" in t:
        triggers.append("at_completion")
    if "certificacion" in t or "certificado" in t:
        triggers.append("upon_certification")
    if triggers:
        info["triggers"] = triggers

    # Possible contract date near "firma"
    date_match = re.search(r"firma.*?(\d{1,2}[\-/\. ]\d{1,2}[\-/\. ]\d{2,4})", t)
    if date_match:
        raw = date_match.group(1).replace(" ", "/").replace("-", "/").replace(".", "/")
        parts = raw.split("/")
        try:
            d = dt.date(int(parts[2]) if len(parts[2]) == 4 else 2000 + int(parts[2]), int(parts[1]), int(parts[0]))
            info["signature_date"] = d.isoformat()
        except Exception:
            pass

    return info


def _compute_next_due(info: Dict[str, Any], today: dt.date) -> Dict[str, Any]:
    result: Dict[str, Any] = {"next_due_date": None, "reason": None}
    # Monthly day-of-month
    if info.get("frequency") == "monthly" and info.get("day_of_month"):
        dom = max(1, min(28, int(info["day_of_month"])) )
        month = today.month
        year = today.year
        if today.day <= dom:
            next_date = dt.date(year, month, dom)
        else:
            if month == 12:
                next_date = dt.date(year + 1, 1, dom)
            else:
                next_date = dt.date(year, month + 1, dom)
        result["next_due_date"] = next_date.isoformat()
        return result

    # Every N days requires a start anchor
    if info.get("every_n_days"):
        start_iso = info.get("signature_date")
        if start_iso:
            try:
                start = dt.date.fromisoformat(start_iso)
                delta = (today - start).days
                n = max(1, int(info["every_n_days"]))
                k = delta // n + 1
                next_date = start + dt.timedelta(days=k * n)
                result["next_due_date"] = next_date.isoformat()
                return result
            except Exception:
                pass
        result["reason"] = "missing_start_date"
        return result

    # Trigger-only info (e.g., at signing)
    if "at_signing" in info.get("triggers", []):
        result["next_due_date"] = today.isoformat()
        result["reason"] = "due_at_signing_if_unpaid"
        return result

    result["reason"] = "insufficient_data"
    return result


def qa_payment_schedule(property_id: str, group: str, subgroup: str, name: str, today_iso: Optional[str] = None) -> Dict:
    """Extract payment cadence and compute next due date based on document text.
    Returns structured fields and a short Spanish answer.
    """
    url = signed_url_for(property_id, group, subgroup, name, expires=600)
    resp = requests.get(url)
    text = _extract_text(resp.content, resp.headers.get("content-type", ""), url)
    out: Dict[str, Any] = {"signed_url": url}

    if not text.strip():
        out["answer"] = "No se pudo extraer texto del documento (p. ej., imagen o formato no compatible)."
        return out

    info = _extract_payment_info(text)
    out["extracted"] = info

    today = dt.date.fromisoformat(today_iso) if today_iso else dt.date.today()
    due = _compute_next_due(info, today)
    out.update(due)

    # Compose short natural answer and include evidence snippet when available
    bits = []
    if info.get("frequency") == "monthly":
        if info.get("day_of_month"):
            bits.append(f"Pago mensual el día {info['day_of_month']} de cada mes")
        else:
            bits.append("Pago mensual")
    elif info.get("every_n_days"):
        bits.append(f"Pago cada {info['every_n_days']} días")
    if info.get("triggers"):
        human_triggers = []
        if "at_signing" in info["triggers"]:
            human_triggers.append("a la firma")
        if "upon_certification" in info["triggers"]:
            human_triggers.append("tras certificación")
        if human_triggers:
            bits.append(", ".join(human_triggers))
    if info.get("method"):
        bits.append(f"por {info['method']}")
    if info.get("amounts_eur"):
        bits.append(f"importe aprox. {info['amounts_eur'][0]:.2f} €")

    # Evidence
    ev = None
    m_ev = re.search(r"(?:dia\s+\d{1,2}|el\s+(?:dia\s+)?\d{1,2})\s+de\s+cada\s+mes", _norm(text))
    if m_ev:
        i = m_ev.start()
        ev = text[max(0, i-60):min(len(text), i+80)]

    base = "; ".join(bits)
    if due.get("next_due_date"):
        answer = (base + (". " if base else "") + f"Próximo pago: {due['next_due_date']}").strip()
    elif due.get("reason") == "missing_start_date":
        if base:
            answer = (base + ". Necesito la fecha de firma para calcular el próximo pago.").strip()
        else:
            answer = "Necesito la fecha de firma para calcular el próximo pago."
    else:
        # Si al menos sabemos el método, dilo
        if base:
            answer = (base + ". No hay datos suficientes para calcular la próxima fecha.").strip()
        else:
            answer = "No hay datos suficientes para calcular la próxima fecha."

    out["answer"] = answer
    if ev:
        out["evidence"] = ev
    return out
