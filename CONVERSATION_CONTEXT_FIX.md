# Fix: Agente no seguía el contexto de conversación

## Problema Original

El agente no estaba siguiendo el contexto de la conversación correctamente. Específicamente:

1. **Ignoraba mensajes anteriores del usuario**: Cuando el usuario mencionaba que tenía documentos subidos y luego pedía resumirlos, el agente respondía diciendo que no existían.

2. **No verificaba antes de negar**: Decía "no hay documento" sin usar la herramienta `list_docs` para verificar.

3. **Usaba la herramienta incorrecta**: Para solicitudes de resumen, usaba `qa_with_citations` (RAG) en lugar de `summarize_document`, fallando si el documento no estaba indexado en el vector store.

### Ejemplo del Problema (de la imagen)

```
Usuario: "Documentos ya subidos: Escritura notarial, Contrato arquitecto"
Usuario: "resume la escritura notarial"
Agente: "Trabajaremos con la propiedad: Casa Demo 6..."  (respuesta genérica)
Usuario: "resume el documento escritura notarial"
Agente: "Parece que no hay un documento subido para 'Escritura Notarial'"  ❌
```

## Cambios Realizados

### 1. `agentic.py` - Mejorado SYSTEM_PROMPT

#### Sección de Memoria y Contexto (líneas 17-25)
```python
**MEMORIA Y CONTEXTO - CRÍTICO**
- Tienes acceso COMPLETO a todo el historial de conversación con este usuario.
- SIEMPRE revisa los mensajes anteriores antes de responder.
- Si el usuario menciona documentos, información, o cualquier dato en mensajes anteriores, CRÉELE y actúa en consecuencia.
- Si el usuario dice "tengo estos documentos subidos: X, Y, Z", entonces esos documentos EXISTEN - no digas que no existen.
- Cuando el usuario menciona que tiene documentos y luego pide resumirlos o consultarlos, USA LAS HERRAMIENTAS INMEDIATAMENTE para buscar y procesar esos documentos.
```

**Por qué:** Hace explícito que el agente debe confiar en lo que el usuario dice y actuar inmediatamente.

#### Sección de Flujo de Documentos (líneas 57-69)
```python
FLUJO: DOCUMENTOS
- **ANTES DE DECIR QUE UN DOCUMENTO NO EXISTE:** SIEMPRE llama a `list_docs` primero para verificar qué documentos están realmente subidos. NO asumas que algo no existe sin verificarlo.
- Si el usuario menciona que tiene documentos subidos y luego pregunta sobre ellos, USA `list_docs` para encontrarlos y luego procesa la solicitud.
- QA y Resúmenes: 
  * Para "resume el documento X" o "resumir X" → usa `summarize_document` con el documento específico
  * Para preguntas concretas sobre un documento → `qa_document`
  * Si no encuentras el documento exacto por nombre, usa `list_docs` para ver nombres similares y sugiérelos al usuario
```

**Por qué:** Especifica claramente el flujo correcto: verificar primero, luego actuar.

#### Sección de Fallback (líneas 92-97)
```python
FALLBACK Y DESAMBIGUACIÓN (CRÍTICO)
- Si no puedes mapear un documento/celda o un ítem de números, PRIMERO usa `list_docs` o `get_numbers` para ver qué opciones existen, luego muestra 2–3 candidatos más probables y pide que el usuario elija.
- **Si el usuario pide resumir o consultar un documento que mencionó antes:** NO digas que no existe. Usa `list_docs` para buscar documentos con nombres similares y procesa el más probable.
```

**Por qué:** Refuerza que NUNCA debe decir "no existe" sin verificar.

#### Ejemplo de Flujo Correcto (líneas 105-112)
```python
EJEMPLO DE FLUJO CORRECTO PARA RESÚMENES:
Usuario: "Tengo estos documentos: Escritura notarial, Contrato arquitecto"
Usuario: "Resume la escritura notarial"
TÚ: [Llamas a `list_docs` para ver qué documentos hay] → [Encuentras "Escritura notarial" en el grupo "Compra"] → [Llamas a `summarize_document` con property_id, "Compra", "", "Escritura notarial"] → [Devuelves el resumen al usuario]

NUNCA hagas esto:
Usuario: "Resume la escritura notarial"
TÚ: "Parece que no hay un documento subido para 'Escritura Notarial'" [SIN VERIFICAR CON list_docs PRIMERO]
```

**Por qué:** Da un ejemplo concreto del flujo correcto vs incorrecto.

### 2. `tools/rag_tool.py` - Fuzzy Matching de Documentos

#### `summarize_document` (líneas 74-126)
Ahora intenta múltiples estrategias para encontrar documentos:
1. **Match exacto**: Intenta el nombre exacto primero
2. **Case-insensitive match**: "escritura notarial" → "Escritura notarial"
3. **Partial match**: "escritura" → "Escritura notarial"
4. **Error útil**: Si no encuentra nada, sugiere usar `list_docs`

```python
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
```

**Por qué:** Permite que el agente encuentre documentos incluso si el usuario no usa el nombre exacto.

#### `qa_document` (líneas 147-203)
Misma lógica de fuzzy matching aplicada a las preguntas sobre documentos.

**Por qué:** Consistencia en todo el sistema.

### 3. `app.py` - Detección Correcta de Solicitudes de Resumen

#### Líneas 1119-1143
Ahora detecta explícitamente solicitudes de resumen y usa `summarize_document`:

```python
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
```

**Por qué:** Antes usaba `qa_with_citations` (RAG) para todo, incluso resúmenes. Ahora usa la herramienta correcta.

#### Líneas 1145-1188
Las preguntas normales ahora excluyen solicitudes de resumen:

```python
# Document question/RAG - Priority: any question about documents (but not summarize)
question_words = ["qué", "que", "cual", "cuál", "cuando", "cuándo", "donde", "dónde", 
                  "cómo", "como", "por qué", "porque", "cuanto", "cuánto", "cuanta", "cuánta",
                  "quien", "quién", "lee el", "que pone", "qué pone", "que dice", "qué dice",
                  "dime", "explicame", "explícame", "di", "día", "dia"]
is_question = any(w in qnorm for w in question_words) and not is_summarize_request
```

**Por qué:** Separa claramente resúmenes de preguntas generales.

## Resultado Esperado

Ahora el flujo debería ser:

```
Usuario: "Documentos ya subidos: Escritura notarial, Contrato arquitecto"
Usuario: "resume la escritura notarial"
Agente: [Detecta "resume" → busca documento con _match_document_from_text] →
        [Encuentra "Escritura notarial" usando fuzzy matching] →
        [Llama a summarize_document] →
        [Devuelve resumen completo] ✅
```

## Testing Recomendado

1. **Test de contexto básico:**
   ```
   1. Usuario lista documentos
   2. Usuario pide resumir uno de ellos
   3. Verificar que el agente resume correctamente
   ```

2. **Test de fuzzy matching:**
   ```
   1. Usuario pide "resume escritura notarial" (minúsculas)
   2. Documento en BD es "Escritura notarial" (con mayúscula)
   3. Verificar que encuentra y resume el documento
   ```

3. **Test de fallback:**
   ```
   1. Usuario pide resumir documento que no existe
   2. Verificar que el agente sugiere opciones usando list_docs
   ```

## Archivos Modificados

- `/Users/mariasebares/Documents/RAMA_AI/rama-agentic-ai/agentic.py`
- `/Users/mariasebares/Documents/RAMA_AI/rama-agentic-ai/tools/rag_tool.py`
- `/Users/mariasebares/Documents/RAMA_AI/rama-agentic-ai/app.py`

## Próximos Pasos

1. **Probar en el entorno de desarrollo** con el caso específico de la imagen
2. **Verificar logs** para confirmar que el flujo es correcto
3. **Considerar indexación automática**: Si quieres que RAG también funcione, asegúrate de que los documentos se indexan automáticamente después de subirse (esto ya está implementado en líneas 710-724 de `app.py`)

