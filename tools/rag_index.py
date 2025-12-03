from __future__ import annotations
import io, math, re, requests
from typing import List, Dict, Any, Tuple

from .supabase_client import sb
from .docs_tools import signed_url_for
from .rag_tool import _extract_text  # reuse robust extractor (pdf/docx/txt)


def _normalize_text(s: str) -> str:
    s = (s or "").replace("\r", " ").replace("\n", "\n")
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def _split_into_chunks(text: str, max_chars: int = 2500, overlap: int = 200) -> List[str]:
    text = text or ""
    if len(text) <= max_chars:
        return [text]
    chunks: List[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + max_chars)
        chunk = text[start:end]
        chunks.append(chunk)
        if end == len(text):
            break
        start = max(0, end - overlap)
    return chunks


def index_document(property_id: str, document_group: str, document_subgroup: str, document_name: str) -> Dict[str, Any]:
    """Fetch the document via signed URL, extract text, chunk it and store in Supabase table `rag_chunks`.

    Table (expected): rag_chunks
      - property_id uuid
      - document_group text
      - document_subgroup text
      - document_name text
      - chunk_index int
      - text text
    """
    url = signed_url_for(property_id, document_group, document_subgroup, document_name, expires=900)
    resp = requests.get(url)
    content_type = resp.headers.get("content-type", "")
    raw_text = _extract_text(resp.content, content_type, url)
    text = _normalize_text(raw_text)
    chunks = _split_into_chunks(text)

    rows = []
    # Try to embed chunks (optional)
    try:
        # 1536 dims to match default vector(1536) schema
        from langchain_openai import OpenAIEmbeddings
        embed_model = OpenAIEmbeddings(model="text-embedding-3-small")
        vectors = embed_model.embed_documents(chunks)
    except Exception as emb_err:
        # Log embedding failure and continue without embeddings
        try:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Embedding failed for document {document_name}: {emb_err}")
        except Exception:
            pass
        vectors = [None] * len(chunks)
    for i, ch in enumerate(chunks):
        rows.append({
            "property_id": property_id,
            "document_group": document_group,
            "document_subgroup": document_subgroup or "",
            "document_name": document_name,
            "chunk_index": i,
            "text": ch,
            "embedding": vectors[i],  # may be None if embedding failed/disabled
        })

    if not rows:
        return {"indexed": 0}

    try:
        # Upsert rows into rag_chunks. If the embedding column exists, it will be stored.
        sb.table("rag_chunks").upsert(rows, on_conflict="property_id,document_group,document_subgroup,document_name,chunk_index").execute()
        return {"indexed": len(rows)}
    except Exception as e:
        # If embedding column doesn't exist, retry without it
        if "embedding" in str(e).lower():
            for r in rows:
                r.pop("embedding", None)
            try:
                sb.table("rag_chunks").upsert(rows, on_conflict="property_id,document_group,document_subgroup,document_name,chunk_index").execute()
                return {"indexed": len(rows), "warning": "embedding column missing; upserted without embeddings"}
            except Exception as e2:
                return {"indexed": 0, "error": str(e2)}
        # If the table does not exist or other error, return gracefully
        return {"indexed": 0, "error": str(e)}


def _tokenize(q: str) -> List[str]:
    q = q or ""
    q = q.lower()
    q = re.sub(r"[^a-z0-9áéíóúüñ\s]", " ", q)
    return [t for t in q.split() if len(t) > 1]


def _score_lexical(text: str, query_tokens: List[str]) -> float:
    t = text.lower()
    score = 0.0
    for tok in query_tokens:
        if tok in t:
            score += 1.0
    return score


def search_chunks(property_id: str, query: str, limit: int = 30, document_name: str | None = None, document_group: str | None = None, document_subgroup: str | None = None) -> List[Dict[str, Any]]:
    """Simple lexical retrieval across rag_chunks for this property.
    Returns a list of {meta..., text, score} sorted by score.
    Optionally filter by document_name, document_group, document_subgroup.
    """
    # Limit output chunk size to prevent context bloat
    MAX_CHUNK_LENGTH = 800 
    
    try:
        q = sb.table("rag_chunks").select("property_id,document_group,document_subgroup,document_name,chunk_index,text,embedding").eq("property_id", property_id)
        if document_name:
            q = q.eq("document_name", document_name)
        if document_group:
            q = q.eq("document_group", document_group)
        if document_subgroup:
            q = q.eq("document_subgroup", document_subgroup)
        rows = q.execute().data
    except Exception:
        # Fallback when embedding column doesn't exist
        try:
            q = sb.table("rag_chunks").select("property_id,document_group,document_subgroup,document_name,chunk_index,text").eq("property_id", property_id)
            if document_name:
                q = q.eq("document_name", document_name)
            if document_group:
                q = q.eq("document_group", document_group)
            if document_subgroup:
                q = q.eq("document_subgroup", document_subgroup)
            rows = q.execute().data
        except Exception:
            rows = []
    if not rows:
        return []
    toks = _tokenize(query)
    # Vector for query (optional)
    try:
        from langchain_openai import OpenAIEmbeddings
        qvec = OpenAIEmbeddings(model="text-embedding-3-small").embed_query(query)
    except Exception:
        qvec = None

    def cosine(a: List[float], b: List[float]) -> float:
        if not a or not b:
            return 0.0
        s = 0.0
        na = 0.0
        nb = 0.0
        for x, y in zip(a, b):
            s += x * y
            na += x * x
            nb += y * y
        if na == 0 or nb == 0:
            return 0.0
        return s / ((na ** 0.5) * (nb ** 0.5))

    scored: List[Dict[str, Any]] = []
    for r in rows:
        lex = _score_lexical(r.get("text", ""), toks)
        # Parse embedding if it's a string (Supabase returns it as string sometimes)
        emb = r.get("embedding")
        if emb and isinstance(emb, str):
            try:
                import json
                emb = json.loads(emb)
            except Exception:
                emb = None
        vec = cosine(qvec, emb) if qvec and emb and isinstance(emb, list) else 0.0
        score = 0.7 * vec + 0.3 * (lex / (len(toks) or 1))
        if score > 0:
            rr = dict(r)
            rr["score"] = score
            # Optimization: Truncate extremely long chunks in output
            if len(rr.get("text", "")) > MAX_CHUNK_LENGTH:
                 rr["text"] = rr["text"][:MAX_CHUNK_LENGTH] + "...[truncated]"
            scored.append(rr)
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:limit]


def qa_with_citations(property_id: str, query: str, top_k: int = 5, model: str | None = None, document_name: str | None = None, document_group: str | None = None, document_subgroup: str | None = None) -> Dict[str, Any]:
    """Answer a question using retrieved chunks; return answer and citations.
    Citations: list of {group, subgroup, name, chunk_index}.
    Optionally filter by document_name, document_group, document_subgroup to search only in specific document(s).
    """
    hits = search_chunks(property_id, query, limit=60, document_name=document_name, document_group=document_group, document_subgroup=document_subgroup)
    if not hits:
        return {"answer": "No he encontrado información relevante en los documentos indexados."}
    
    # Optimization: Reduce context overhead
    # Only include text and minimal citation info in the context sent to LLM
    ctx_hits = hits[:top_k]
    context_parts = []
    for i, h in enumerate(ctx_hits, 1):
         # Minimal header: DocName (Chunk X)
         header = f"[#{i}] {h['document_name']} (p.{h.get('chunk_index',0)})"
         text = h['text']
         context_parts.append(f"{header}:\n{text}")
    
    context = "\n\n".join(context_parts)

    prompt = (
        "Eres un asistente experto en análisis de documentos. Responde en español de forma clara y completa.\n"
        "Tu tarea es responder a la pregunta del usuario usando SOLO la información del contexto proporcionado.\n\n"
        "INSTRUCCIONES:\n"
        "- Lee cuidadosamente todos los fragmentos del contexto\n"
        "- Busca información relevante que responda directa o indirectamente la pregunta\n"
        "- Si encuentras información relevante, responde de forma completa y natural\n"
        "- Si la pregunta es sobre pagos, fechas, formas de pago, etc., extrae TODA la información relacionada\n"
        "- Incluye detalles específicos como fechas, cantidades, métodos de pago, plazos, etc.\n"
        "- Solo responde 'No aparece en los documentos' si realmente no hay NINGUNA información relacionada\n\n"
        f"PREGUNTA: {query}\n\n"
        f"CONTEXTO:\n{context}\n\n"
        "RESPUESTA:"
    )
    from langchain_openai import ChatOpenAI
    llm = ChatOpenAI(model=model or "gpt-4o", temperature=0)
    answer = llm.invoke(prompt).content
    citations = [
        {
            "document_group": h["document_group"],
            "document_subgroup": h.get("document_subgroup", ""),
            "document_name": h["document_name"],
            "chunk_index": h["chunk_index"],
        }
        for h in ctx_hits
    ]
    return {"answer": answer, "citations": citations}


def index_all_documents(property_id: str) -> Dict[str, Any]:
    """Index all documents with storage_key for a property.
    Returns {indexed, details: [{doc, indexed, error?}]} for diagnóstico.
    """
    from .docs_tools import list_docs
    try:
        rows = list_docs(property_id)
    except Exception as e:
        return {"indexed": 0, "error": str(e), "details": []}
    count = 0
    details: List[Dict[str, Any]] = []
    for r in rows:
        if r.get("storage_key"):
            out = index_document(property_id, r["document_group"], r.get("document_subgroup", ""), r["document_name"])
            count += int(out.get("indexed", 0) or 0)
            details.append({
                "doc": f"{r['document_group']} / {r.get('document_subgroup','')} / {r['document_name']}",
                "indexed": out.get("indexed", 0),
                "error": out.get("error"),
                "warning": out.get("warning"),
            })
        else:
            details.append({
                "doc": f"{r['document_group']} / {r.get('document_subgroup','')} / {r['document_name']}",
                "indexed": 0,
                "warning": "no storage_key (no hay fichero subido)",
            })
    return {"indexed": count, "details": details}


