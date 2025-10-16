# agentic.py
from __future__ import annotations
import env_loader 
import os
from typing import TypedDict, List, Dict, Any, Literal
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI

from tools.registry import TOOLS  # <-- decorated tools live here
from tools.property_tools import list_frameworks as _derive_framework_names

SYSTEM_PROMPT = """
Eres **PropertyAgent** para RAMA Country Living. Tu objetivo es guiar al usuario hasta completar 3 plantillas por propiedad: **documentos**, **números** y **resumen de la propiedad**, trabajando siempre con herramientas.

**MEMORIA Y CONTEXTO**
- Tienes acceso COMPLETO a todo el historial de conversación con este usuario.
- SIEMPRE revisa los mensajes anteriores antes de responder.
- Si el usuario te pregunta sobre algo que mencionó antes, búscalo en el historial.
- NUNCA digas "no tengo acceso a conversaciones pasadas" - SÍ lo tienes.
- Mantén coherencia con lo que el usuario te ha dicho en mensajes anteriores.

OBJETIVO GLOBAL (checklist de producto)
1) Crear propiedades en Supabase. Cada nueva propiedad provisiona 3 plantillas: documentos, números, resumen.
2) Ayudar a completar documentos y números. Cuando ambas estén completas, generar automáticamente la ficha de resumen.
3) Tras crear/seleccionar una propiedad, informar de las plantillas por rellenar (documentos y números) y ofrecer empezar.
4) Documentos: listar qué hay y qué falta, subir ficheros, proponer (grupo/subgrupo/nombre), validar con `slot_exists`, pedir confirmación y guardar con `upload_and_link`.
5) RAG en documentos: resumir (`summarize_document`), responder preguntas (`qa_document` / `rag_qa_with_citations`), pagos/fechas con `qa_payment_schedule`.
6) Email: enviar por correo documentos (URL firmada), frameworks (listados tabulares) o fragmentos de información.
7) Guiar sobre documentos pendientes: detectar y comunicar qué falta y los siguientes pasos para completarlo.
8) Numbers framework: mostrar la tabla, decir qué valores faltan y permitir que el usuario dicte “pon <item> a <valor>” para escribir en su celda (`set_number`).
9) Calcular totales cuando el usuario lo pida o tras varias actualizaciones (`calc_numbers`) y reflejarlos en la tabla.
10) Permitir “mostrar” o “enviar por email” el numbers framework completo.
11) Cuando documentos y números estén completos, comunicarlo y ofrecer/generar `compute_summary` para la ficha resumen.

PRINCIPIOS
- No inventes datos ni resultados; usa herramientas siempre.
- Confirma cuando haya ambigüedad antes de escribir o enviar.
- Español claro y conciso; muestra próximos pasos.

CONTEXTO Y PROPIEDAD ACTIVA
- Si no hay `property_id`, resuélvelo por nombre/dirección con `search_properties`/`find_property` (no pidas ID de inicio). Si hay 1 candidato claro, fíjalo; si hay varios, muestra 1–5 con IDs.
- Tras fijar/crear, recuerda: “plantillas por completar: documentos y números”.

HERRAMIENTAS (nombres exactos)
- Propiedades: `add_property`, `list_frameworks`, `list_properties`, `find_property`, `search_properties`, `get_property`.
- Documentos: `propose_doc_slot`, `slot_exists`, `upload_and_link`, `list_docs`, `signed_url_for`, `summarize_document`, `qa_document`, `qa_payment_schedule`.
- RAG: `rag_index_document`, `rag_index_all_documents`, `rag_qa_with_citations`.
- Números: `get_numbers`, `set_number`, `calc_numbers`.
- Resumen: `get_summary_spec`, `compute_summary`, `upsert_summary_value`.
- Comunicación/Voz: `send_email`, `transcribe_audio`, `synthesize_speech`, `process_voice_input`, `create_voice_response`.

FLUJO: DOCUMENTOS
- Todos los documentos son por propiedad. Nunca mezcles documentos entre propiedades: cada llamada a herramientas de documentos debe usar el `property_id` activo y devolver resultados solo de esa propiedad. Si una propiedad no tiene documentos subidos, dilo explícitamente.
- Listar: `list_docs`. Muestra subidos vs faltantes. Si falta, explica cómo subir.
- Subida guiada: 1) `propose_doc_slot` (incluye cualquier pista del usuario). 2) Si dudas, `slot_exists`. 3) Pide confirmación. 4) `upload_and_link` y confirma subida (y firma URL).
- Indexación: tras subir, intenta `rag_index_document`. Para muchos documentos, sugiere `rag_index_all_documents`.
- QA: preguntas concretas → `qa_document`. Pagos/fechas → `qa_payment_schedule` (si falta una fecha clave, pídesela). Preguntas abiertas → `rag_qa_with_citations` con citas claras.

FLUJO: NÚMEROS
- Mostrar tabla: `get_numbers` como “grupo / etiqueta (item_key): valor”.
- Qué falta: items con `amount` nulo/cero; comunícalos en lista.
- Escribir valores: intenta mapear el texto del usuario al `item_key` por similitud (etiqueta o clave) y llama `set_number`. Acepta 25.000, 25,000, 25000, 7%, etc.
- Cálculo: cuando lo pida o tras varias escrituras, llama `calc_numbers` y comunica que los totales están actualizados.
- Mostrar/enviar: si pide “enviar/mostrar el framework de números”, genera un listado y envíalo (HTML) o muéstralo.

FLUJO: RESUMEN
- Cuando documentos y números estén completos, indícalo y ofrece `compute_summary`. Tras computar, comunica resultados principales.

EMAIL
- Si el usuario pide enviar por correo, confirma destinatario(s) y contenido. Para documentos, usa `signed_url_for`. Para frameworks o respuestas, envía HTML tabular o texto.

FLUJO: VOZ
- Cuando recibas audio del usuario, usa `process_voice_input` para transcribir el mensaje vocal a texto.
- El texto transcrito debe aparecer en el chat como un mensaje del usuario.
- Responde normalmente al mensaje transcrito usando todas las herramientas disponibles.
- Si el usuario solicita una respuesta de voz, usa `create_voice_response` para generar audio de tu respuesta.
- Siempre confirma que has entendido correctamente el mensaje vocal antes de proceder.
- Si la transcripción no es clara, pide al usuario que repita o aclare.

FALLBACK Y DESAMBIGUACIÓN (CRÍTICO)
- Si NO entiendes con certeza la intención del usuario, **no respondas de forma inventada**: pide 1–2 aclaraciones específicas (p. ej., “¿Quieres ver los documentos pendientes o subir uno nuevo?”).
- Si no puedes mapear un documento/celda o un ítem de números, muestra 2–3 candidatos más probables y pide que el usuario elija.
- Si QA/RAG no encuentra evidencia suficiente: responde “No he encontrado información suficiente en los documentos” y sugiere el siguiente paso (especificar documento, indexar, subir el documento, reintentar con más contexto).
- Si no hay propiedad activa, pide nombre/dirección para localizarla antes de continuar.

ERRORES Y MANEJO DE FALLOS
- Si una herramienta falla, informa brevemente y sugiere el siguiente paso (reintentar, aportar dato, etc.).
- Si `list_docs` devuelve 0 elementos para la propiedad activa, responde "No hay documentos subidos en esta propiedad" y ofrece subir o listar los que faltan.
- Si `search_properties` o `list_properties` devuelven lista vacía, puede ser un error temporal de conexión. Informa al usuario que hay un problema de conexión y pídele que reintente en un momento.
- NUNCA muestres errores técnicos como "[Errno 8]" o "Network is unreachable" al usuario. En su lugar, di "Hay un problema temporal de conexión. Por favor, inténtalo de nuevo en un momento."
"""

# ---------------- State ----------------
from langgraph.graph import add_messages
from typing_extensions import Annotated, NotRequired

class AgentState(TypedDict):
    # Required field with reducer
    messages: Annotated[List[Any], add_messages]
    # Optional fields
    property_id: NotRequired[str]
    awaiting_confirmation: NotRequired[bool]
    proposal: NotRequired[Dict[str, Any]]
    last_doc_ref: NotRequired[Dict[str, Any]]
    input: NotRequired[str]

def prepare_input(state: AgentState):
    """Convert input text to HumanMessage if present."""
    if state.get("input"):
        # Return new messages to be added via add_messages reducer
        return {"messages": [HumanMessage(content=state["input"])]}
    # No input, no updates - return None or empty dict is fine for optional updates
    return None

# --------------- Router ----------------
def router_node(state: AgentState) -> Dict[str, Any]:
    """Check if we're awaiting confirmation and handle user's response."""
    updates = {}
    
    if state.get("awaiting_confirmation"):
        messages = state.get("messages", [])
        # Look for the last user message to see if they confirmed
        last_user = ""
        for m in reversed(messages):
            if isinstance(m, HumanMessage):
                content = m.content if isinstance(m.content, str) else str(m.content or "")
                last_user = content.lower()
                break
        
        # Check for confirmation
        if any(w in last_user for w in ("yes", "confirm", "ok", "go ahead", "sí", "si", "proceed")):
            # User confirmed - clear the flag and let assistant proceed
            updates["awaiting_confirmation"] = False
            updates["messages"] = [SystemMessage(content="User confirmed. Proceed with the proposed action.")]
        elif any(w in last_user for w in ("no", "cancel", "change", "different", "nope")):
            # User cancelled - clear the flag and proposal
            updates["awaiting_confirmation"] = False
            updates["proposal"] = {}
            updates["messages"] = [SystemMessage(content="User cancelled. Ask what they'd like to do instead.")]
    
    return updates if updates else None

# --------------- Assistant (planner) ---------------
def assistant(state: AgentState) -> Dict[str, Any]:
    messages = state.get("messages", [])
    llm = ChatOpenAI(model="gpt-4o", temperature=0).bind_tools(TOOLS)
    
    # Filtra mensajes inválidos y prepara contexto
    filtered_msgs = []
    for i, msg in enumerate(messages):
        if isinstance(msg, ToolMessage):
            if filtered_msgs and isinstance(filtered_msgs[-1], AIMessage) and getattr(filtered_msgs[-1], "tool_calls", None):
                filtered_msgs.append(msg)
        else:
            filtered_msgs.append(msg)

    # system + conversación + contexto de propiedad activa y último doc referenciado
    msgs: List[Any] = [SystemMessage(content=SYSTEM_PROMPT)]
    if state.get("property_id"):
        msgs.append(SystemMessage(content=f"Contexto: property_id activa = {state['property_id']}. Asume esta propiedad hasta que el usuario la cambie explícitamente."))
    if state.get("last_doc_ref"):
        ldr = state["last_doc_ref"]
        msgs.append(SystemMessage(content=f"Si el usuario dice 'ese documento', interpreta {ldr} como el objetivo por defecto."))
    msgs += filtered_msgs

    ai = llm.invoke(msgs)
    return {"messages": [ai]}

# --------------- Post-tool hook --------------------
# --------------- Post-tool hook --------------------
def post_tool(state: AgentState) -> Dict[str, Any]:
    """Interpret tool outputs and set flags for special workflows like document confirmation.
    Also captures add_property results to set property_id and inform about frameworks.
    Additionally, if `search_properties` returns un único candidato, fija `property_id` automáticamente; si devuelve varios,
    añade un mensaje para que el usuario elija.
    """
    updates = {}
    messages = state.get("messages", [])
    
    for msg in reversed(messages):
        if isinstance(msg, ToolMessage):
            if msg.name == "propose_doc_slot":
                try:
                    import json
                    data = json.loads(msg.content) if isinstance(msg.content, str) else msg.content
                    updates["proposal"] = data
                    updates["awaiting_confirmation"] = True
                except Exception:
                    pass
                break
            if msg.name == "list_docs":
                # remember last referenced slot if list shows a single uploaded/missing item
                try:
                    import json
                    rows = json.loads(msg.content) if isinstance(msg.content, str) else msg.content
                    if isinstance(rows, list) and len(rows) == 1:
                        r = rows[0]
                        updates["last_doc_ref"] = {
                            "document_group": r.get("document_group"),
                            "document_subgroup": r.get("document_subgroup"),
                            "document_name": r.get("document_name"),
                        }
                except Exception:
                    pass
            if msg.name == "add_property":
                try:
                    import json
                    data = json.loads(msg.content) if isinstance(msg.content, str) else msg.content
                    pid = (data or {}).get("id")
                    if pid:
                        updates["property_id"] = pid
                        frameworks = _derive_framework_names(pid)
                        updates["messages"] = [
                            AIMessage(
                                content=(
                                    f"✅ Propiedad creada con id: {pid}\n"
                                    f"Frameworks: {frameworks}\n\n"
                                    "Hay tres frameworks vacíos que rellenar: documentos, números y resumen. "
                                    "¿Quieres empezar ahora (subir un documento, fijar un número, calcular el resumen) o prefieres más tarde?"
                                )
                            )
                        ]
                except Exception:
                    pass
                break
            if msg.name == "search_properties":
                try:
                    import json
                    hits = json.loads(msg.content) if isinstance(msg.content, str) else msg.content
                    if isinstance(hits, list) and len(hits) == 1 and hits[0].get("id"):
                        pid = hits[0]["id"]
                        updates["property_id"] = pid
                        frameworks = _derive_framework_names(pid)
                        updates["messages"] = [
                            AIMessage(content=(
                                f"Trabajaremos con la propiedad: {hits[0].get('name','(sin nombre)')} — {hits[0].get('address','')}\n"
                                f"Tienes 2 plantillas por completar: Documentos y Números. ¿Por dónde quieres empezar?"
                            ))
                        ]
                    elif isinstance(hits, list) and len(hits) > 1:
                        lines = [f"{i+1}. {h.get('name','(sin nombre)')} — {h.get('address','')}" for i, h in enumerate(hits[:5])]
                        updates["messages"] = [
                            AIMessage(content="He encontrado estas propiedades:\n" + "\n".join(lines) + "\n\nResponde con el número para continuar.")
                        ]
                except Exception:
                    pass
                break
    
    return updates if updates else None

# --------------- Should we call a tool? ------------
def should_call_tool(state: AgentState) -> Literal["tools", "end"]:
    messages = state.get("messages", [])
    if not messages:
        return "end"
    last = messages[-1]
    if isinstance(last, AIMessage) and getattr(last, "tool_calls", None):
        return "tools"
    return "end"

# --------------- Should we continue looping? ------------
def should_continue(state: AgentState) -> Literal["assistant", "end"]:
    """After executing tools, decide whether to call assistant again or end."""
    messages = state.get("messages", [])
    if messages and isinstance(messages[-1], ToolMessage):
        return "assistant"
    return "end"

# --------------- Build graph -----------------------
def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("prepare_input", prepare_input)
    graph.add_node("router", router_node)
    graph.add_node("assistant", assistant)
    graph.add_node("tools", ToolNode(TOOLS))
    graph.add_node("post_tool", post_tool)

    # Entry point: prepare user input then check for confirmations
    graph.set_entry_point("prepare_input")
    graph.add_edge("prepare_input", "router")
    graph.add_edge("router", "assistant")
    
    # After assistant: either call tools or end
    graph.add_conditional_edges(
        "assistant",
        should_call_tool,
        {"tools": "tools", "end": END},
    )
    
    # After tools: run post_tool hook
    graph.add_edge("tools", "post_tool")
    
    # After post_tool: loop back to assistant to see results and continue or end
    graph.add_conditional_edges(
        "post_tool",
        should_continue,
        {"assistant": "assistant", "end": END}
    )

    # Compile with PostgreSQL checkpointer for persistent memory
    database_url = os.getenv("DATABASE_URL")
    
    if not database_url:
        print("⚠️  WARNING: DATABASE_URL not found! Using SQLite fallback...")
        from langgraph.checkpoint.sqlite import SqliteSaver
        from sqlite3 import connect
        db_path = os.path.join(os.path.dirname(__file__), "checkpoints.db")
        conn = connect(db_path, check_same_thread=False)
        checkpointer = SqliteSaver(conn)
        checkpointer.setup()
        print(f"✅ SQLite checkpointer active: {db_path}")
    else:
        print(f"🔄 Connecting to PostgreSQL (Supabase)...")
        print(f"   Host: {database_url.split('@')[1].split('/')[0] if '@' in database_url else 'configured'}")
        
        try:
            from langgraph.checkpoint.postgres import PostgresSaver
            from psycopg_pool import ConnectionPool
            
            # Create a connection pool for PostgresSaver
            pool = ConnectionPool(
                conninfo=database_url,
                min_size=1,
                max_size=10,
                timeout=30,
                max_idle=300,
                max_lifetime=3600,
            )
            
            # Create PostgresSaver with the pool
            checkpointer = PostgresSaver(pool)
            checkpointer.setup()
            
            print(f"✅ PostgreSQL connected with connection pool!")
            print(f"✅ Persistent memory across sessions and restarts")
            
        except Exception as e:
            print(f"❌ PostgreSQL connection failed: {e}")
            print(f"⚠️  Falling back to SQLite...")
            from langgraph.checkpoint.sqlite import SqliteSaver
            from sqlite3 import connect
            db_path = os.path.join(os.path.dirname(__file__), "checkpoints.db")
            conn = connect(db_path, check_same_thread=False)
            checkpointer = SqliteSaver(conn)
            checkpointer.setup()
            print(f"✅ SQLite checkpointer active: {db_path}")
    
    app = graph.compile(checkpointer=checkpointer)

    # Skip ASCII graph drawing to avoid potential hangs
    # try:
    #     print(app.get_graph().draw_ascii())
    # except Exception:
    #     pass
    return app
