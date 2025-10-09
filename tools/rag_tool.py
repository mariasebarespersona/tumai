from __future__ import annotations
import io, requests, zipfile, datetime as dt
from typing import Dict, Optional
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
        return ""


def summarize_document(property_id: str, group: str, subgroup: str, name: str, model: str = None, max_sentences: int = 5) -> Dict:
    url = signed_url_for(property_id, group, subgroup, name, expires=600)
    resp = requests.get(url)
    text = _extract_text(resp.content, resp.headers.get("content-type", ""), url)

    if not text.strip():
        # No textual content extracted; return a helpful message
        return {
            "summary": "No se pudo extraer texto del documento (p. ej., imagen o formato no compatible).",
            "signed_url": url,
        }

    # Limit size for prompt
    text = text[:40000]
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
    """
    url = signed_url_for(property_id, group, subgroup, name, expires=600)
    resp = requests.get(url)
    text = _extract_text(resp.content, resp.headers.get("content-type", ""), url)

    if not text.strip():
        return {
            "answer": "No se pudo extraer texto del documento (podría ser una imagen o un formato no compatible).",
            "signed_url": url,
        }

    today = dt.date.today().isoformat()
    text = text[:max_chars]
    llm = ChatOpenAI(model=model or "gpt-4o-mini")
    prompt = (
        "Eres un asistente legal/administrativo. Responde en español con una frase clara y directa. "
        "Si el documento no contiene la información solicitada, di explícitamente que no aparece. "
        f"Hoy es {today}. Pregunta del usuario: {question}\n\n"
        "Texto del documento (parcial):\n" + text
    )
    answer = llm.invoke(prompt).content
    return {"answer": answer, "signed_url": url}
