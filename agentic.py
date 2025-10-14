# agentic.py
from __future__ import annotations
import env_loader 
from typing import TypedDict, List, Dict, Any, Literal
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import ToolNode
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI

from tools.registry import TOOLS  # <-- decorated tools live here
from tools.property_tools import list_frameworks as _derive_framework_names

SYSTEM_PROMPT = """
Eres **PropertyAgent**, un asistente de producción para una inmobiliaria (RAMA) que trabaja con un backend Supabase.
Tu misión es ayudar al usuario a gestionar propiedades y a rellenar tres frameworks por propiedad: **documentos**, **números** y **resumen**.
Operas dentro de un runtime con herramientas (LangGraph + function calling).

PRINCIPIOS CRÍTICOS
- **No inventes** datos, IDs, rutas de ficheros ni resultados. Si falta información, pregunta.
- **Prioriza herramientas** siempre que la acción toque datos, almacenamiento, email, voz o cálculos. Nunca simules la salida de una herramienta.
- **Seguro y explícito**: antes de escribir/enviar algo cuando haya ambigüedad, confirma.
- **Sin secretos**: nunca muestres claves, variables de entorno ni nombres internos de esquemas.

POLÍTICA DE IDIOMA
- Responde SIEMPRE en español. Usa etiquetas en español al listar ("nombre", "dirección").

CONTEXTO Y ESTADO
- Trabaja siempre sobre una propiedad concreta. Si no hay `property_id`, **resuélvelo** por nombre/dirección usando `search_properties(query)` o `find_property(name, address)`.
  Solo pide el ID si la búsqueda es ambigua y después de ofrecer 1–5 alternativas con sus IDs para elegir.
- Tras crear o fijar una propiedad, recuerda al usuario que existen tres frameworks (documentos, números, resumen) y que puede empezar por cualquiera.
- El flujo de subida de documentos puede dejar `awaiting_confirmation=true` tras una propuesta de ubicación.

HERRAMIENTAS (usa exactamente estos nombres)
- Propiedades: `add_property`, `list_frameworks`, `list_properties`, `find_property`, `search_properties`, `get_property`.
- Documentos: `propose_doc_slot`, `slot_exists`, `upload_and_link`, `list_docs`, `signed_url_for`, `summarize_document`, `qa_document`, `qa_payment_schedule`.
- RAG: `rag_index_document`, `rag_index_all_documents`, `rag_qa_with_citations`.
- Números: `get_numbers`, `set_number`, `calc_numbers`.
- Resumen: `get_summary_spec`, `compute_summary`, `upsert_summary_value`.
- Comunicación/Voz: `send_email`, `transcribe_audio`, `synthesize_speech`.

PAUTAS DE USO POR FUNCIÓN
- Propiedad activa: cuando el usuario diga “quiero trabajar/usar/cambiar a la propiedad X”, llama `search_properties`.
  Si hay 1 candidato claro, fija esa propiedad y continúa; si hay varios, muestra 1–5 y pide elegir.
- Subir documento: 1) `propose_doc_slot`; 2) si dudas de que la celda exista, `slot_exists`; 3) pide confirmación; 4) `upload_and_link`.
  Después de subir, intenta `rag_index_document` para habilitar QA. Para lotes, `rag_index_all_documents`.
- Ver/abrir documentos: `list_docs`; para abrir, `signed_url_for`.
- QA de documentos:
  - Si el usuario pregunta sobre un documento concreto (o existe `last_doc_ref`), usa `qa_document`.
  - Para pagos/fechas, usa `qa_payment_schedule` y, si falta una fecha necesaria (p.ej., firma), pídela.
  - Para preguntas abiertas que no refieren a un documento concreto, usa `rag_qa_with_citations` y devuelve **citas claras** (grupo/subgrupo/nombre + trozo).
- Números:
  - Para listar el esquema actual, `get_numbers` y muestra `group_name / item_label (item_key): amount`.
  - Para completar valores, intenta deducir el `item_key` por similitud con el texto del usuario (coincidencia por `item_label` o `item_key`) y llama `set_number`.
    Acepta formatos 25.000, 25,000, 25000, 7%, etc. Tras varios cambios, ofrece `calc_numbers` y muestra resultados clave.
  - Para “qué falta”, lista los items con `amount` nulo/cero.
- Resumen: cuando te lo pidan (o tenga sentido y lo confirmes), `compute_summary` y reporta los ítems calculados.
- Email: cuando pidan enviar información, confirma destinatarios y contenido; si el contenido procede de un resumen o respuesta, inclúyelo en HTML.
- Voz: si recibes audio, primero `transcribe_audio` y continúa con el texto.

POLÍTICA DE INTERACCIÓN
- Respuestas breves, accionables, con siguientes pasos claros. Evita detalles internos.
- Ante ambigüedad, pregunta 1 cosa concreta que desbloquee la acción.
- Si un tool falla, explica brevemente y propone alternativa (reintentar, pedir dato faltante, etc.).

ESTILO DE SALIDA
- Español claro. Cuando ejecutes acciones, indica qué hiciste y cómo seguir (p. ej., “Subido X. ¿Quieres indexarlo ahora?”).
"""

# ---------------- State ----------------
class AgentState(TypedDict, total=False):
    messages: List[Any]
    property_id: str
    awaiting_confirmation: bool
    proposal: Dict[str, Any]
    last_doc_ref: Dict[str, Any]  # remembers last referenced document slot
    input: str  # User input text to be converted to HumanMessage

def _ensure_msgs(state: AgentState):
    if "messages" not in state:
        state["messages"] = []

def prepare_input(state: AgentState) -> AgentState:
    """Convert input text to HumanMessage if present."""
    _ensure_msgs(state)
    if state.get("input"):
        state["messages"].append(HumanMessage(content=state["input"]))
        # Remove input after converting so it doesn't accumulate in checkpointed state
        try:
            del state["input"]
        except Exception:
            pass
    return state

# --------------- Router ----------------
def router_node(state: AgentState) -> AgentState:
    """Check if we're awaiting confirmation and handle user's response."""
    _ensure_msgs(state)
    
    if state.get("awaiting_confirmation"):
        # Look for the last user message to see if they confirmed
        last_user = ""
        for m in reversed(state["messages"]):
            if isinstance(m, HumanMessage):
                content = m.content if isinstance(m.content, str) else str(m.content or "")
                last_user = content.lower()
                break
        
        # Check for confirmation
        if any(w in last_user for w in ("yes", "confirm", "ok", "go ahead", "sí", "si", "proceed")):
            # User confirmed - clear the flag and let assistant proceed
            state["awaiting_confirmation"] = False
            # Add a message to guide the assistant
            state["messages"].append(SystemMessage(content="User confirmed. Proceed with the proposed action."))
        elif any(w in last_user for w in ("no", "cancel", "change", "different", "nope")):
            # User cancelled - clear the flag and proposal
            state["awaiting_confirmation"] = False
            state["proposal"] = {}
            state["messages"].append(SystemMessage(content="User cancelled. Ask what they'd like to do instead."))
    
    return state

# --------------- Assistant (planner) ---------------
def assistant(state: AgentState) -> AgentState:
    _ensure_msgs(state)
    llm = ChatOpenAI(model="gpt-4o", temperature=0).bind_tools(TOOLS)
    
    # Filtra mensajes inválidos y prepara contexto
    filtered_msgs = []
    for i, msg in enumerate(state["messages"]):
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
    state["messages"].append(ai)
    return state

# --------------- Post-tool hook --------------------
def post_tool(state: AgentState) -> AgentState:
    """Interpret tool outputs and set flags for special workflows like document confirmation.
    Also captures add_property results to set property_id and inform about frameworks.
    Additionally, if `search_properties` returns un único candidato, fija `property_id` automáticamente; si devuelve varios,
    añade un mensaje para que el usuario elija.
    """
    _ensure_msgs(state)
    
    for msg in reversed(state["messages"]):
        if isinstance(msg, ToolMessage):
            if msg.name == "propose_doc_slot":
                try:
                    import json
                    data = json.loads(msg.content) if isinstance(msg.content, str) else msg.content
                    state["proposal"] = data
                    state["awaiting_confirmation"] = True
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
                        state["last_doc_ref"] = {
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
                        state["property_id"] = pid
                        frameworks = _derive_framework_names(pid)
                        state["messages"].append(
                            AIMessage(
                                content=(
                                    f"✅ Propiedad creada con id: {pid}\n"
                                    f"Frameworks: {frameworks}\n\n"
                                    "Hay tres frameworks vacíos que rellenar: documentos, números y resumen. "
                                    "¿Quieres empezar ahora (subir un documento, fijar un número, calcular el resumen) o prefieres más tarde?"
                                )
                            )
                        )
                except Exception:
                    pass
                break
            if msg.name == "search_properties":
                try:
                    import json
                    hits = json.loads(msg.content) if isinstance(msg.content, str) else msg.content
                    if isinstance(hits, list) and len(hits) == 1 and hits[0].get("id"):
                        pid = hits[0]["id"]
                        state["property_id"] = pid
                        frameworks = _derive_framework_names(pid)
                        state["messages"].append(
                            AIMessage(content=f"Usaremos la propiedad: {hits[0].get('name','(sin nombre)')} — {hits[0].get('address','')}\nid: {pid}\nFrameworks: {frameworks}")
                        )
                    elif isinstance(hits, list) and len(hits) > 1:
                        lines = [f"{i+1}. {h.get('name','(sin nombre)')} — {h.get('address','')} — id: {h.get('id')}" for i, h in enumerate(hits[:5])]
                        state["messages"].append(
                            AIMessage(content="He encontrado estas propiedades:\n" + "\n".join(lines) + "\n\nResponde con el número o pega el id para continuar.")
                        )
                except Exception:
                    pass
                break
    
    return state

# --------------- Should we call a tool? ------------
def should_call_tool(state: AgentState) -> Literal["tools", "end"]:
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and getattr(last, "tool_calls", None):
        return "tools"
    return "end"

# --------------- Should we continue looping? ------------
def should_continue(state: AgentState) -> Literal["assistant", "end"]:
    """After executing tools, decide whether to call assistant again or end."""
    # Check if the last message is a ToolMessage
    if state["messages"] and isinstance(state["messages"][-1], ToolMessage):
        # Let the assistant see the tool results and potentially call more tools or respond
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

    # Compile with a reasonable recursion limit
    app = graph.compile(
        checkpointer=MemorySaver(),
    )

    try:
        print(app.get_graph().draw_ascii())
    except Exception:
        pass
    return app
