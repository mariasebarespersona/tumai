# Fix: RAG Functionality in HTTP API

## 🐛 Problema Identificado

El agente respondía "No he encontrado información relevante en los documentos indexados" cuando se le preguntaba sobre documentos porque:

1. **Los documentos NO se estaban indexando automáticamente** después de subirlos vía HTTP API
2. El código de `gradio_app.py` SÍ indexaba automáticamente, pero `app.py` (HTTP endpoint) NO

## ✅ Solución Implementada

### Cambio en `app.py` (líneas 709-724)

Agregado **auto-indexación automática** después de subir cada documento:

```python
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
        logger.warning(f"⚠️ Document indexing returned 0 chunks")
except Exception as e:
    logger.warning(f"⚠️ Could not auto-index document (non-critical): {e}")
```

## 🎯 Cómo Funciona Ahora

### 1. **Upload Flow con Auto-Indexación**
```
User sube documento → upload_and_link() → Guarda en storage + DB
                                        ↓
                           AUTO-INDEX: index_document()
                                        ↓
                           Chunking + Embeddings → rag_chunks table
```

### 2. **Query Flow (RAG)**

Cuando el usuario pregunta sobre documentos:

```
User: "¿Qué día hay que pagar al arquitecto?"
     ↓
app.py detecta pregunta (question_words)
     ↓
Llama qa_with_citations(property_id, query, top_k=6)
     ↓
search_chunks() busca en tabla rag_chunks
     ↓
LLM responde con contexto + citations
     ↓
Respuesta al usuario con fuentes
```

## 🔧 Herramientas RAG Disponibles

El agente tiene acceso a estas herramientas (definidas en `agentic.py`):

1. **`rag_index_document`** - Indexa un documento específico
2. **`rag_index_all_documents`** - Indexa todos los documentos de una propiedad
3. **`rag_qa_with_citations`** - Responde preguntas con citas de documentos
4. **`qa_document`** - Responde preguntas sobre un documento específico
5. **`qa_payment_schedule`** - Especializado en fechas y pagos
6. **`summarize_document`** - Resume un documento

## 📊 Base de Datos

### Tabla `rag_chunks` (Supabase)

```sql
CREATE TABLE rag_chunks (
    property_id UUID,
    document_group TEXT,
    document_subgroup TEXT,
    document_name TEXT,
    chunk_index INT,
    text TEXT,
    embedding VECTOR(1536),  -- OpenAI embeddings
    PRIMARY KEY (property_id, document_group, document_subgroup, document_name, chunk_index)
);
```

## 🧪 Testing

Para probar que funciona:

1. **Sube un documento** vía HTTP API o frontend
2. **Verifica auto-indexación** en los logs:
   ```
   [INFO] 🔍 Auto-indexing document for RAG: Contrato arquitecto
   [INFO] ✅ Document indexed: 15 chunks
   ```
3. **Haz una pregunta** sobre el documento:
   ```
   User: "¿Qué día hay que pagar al arquitecto?"
   Agent: "Según el contrato, el pago debe realizarse el 15 de cada mes..."
   ```

## 🚀 Próximos Pasos (Opcional)

Si los documentos antiguos NO están indexados:

```bash
# Opción 1: Desde el frontend, dile al agente:
"Indexa todos los documentos"

# Opción 2: Manualmente desde Python:
from tools.rag_index import index_all_documents
result = index_all_documents(property_id="uuid-de-propiedad")
print(f"Indexed {result['indexed']} chunks")
```

## ✅ Estado Actual

- ✅ Auto-indexación activada en HTTP API
- ✅ Herramientas RAG disponibles para el agente
- ✅ SYSTEM_PROMPT incluye instrucciones RAG
- ✅ PostgreSQL memory funcionando
- ✅ Frontend conectado y operacional

