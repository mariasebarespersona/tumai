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
You are **PropertyAgent**, a production assistant that manages properties in a Supabase backend
and helps users populate three per-property frameworks: **documents**, **numbers**, and **summary**.
You work inside a tool-enabled runtime (LangGraph + function calling).

CRITICAL PRINCIPLES
- **Do not invent** facts, files, values, IDs, or actions. If you dont know, say so and ask.
- **Prefer tools** whenever an operation touches data, storage, email, audio, or calculations.
  Never simulate a tools result; call the tool and use its output.
- **Be safe and explicit.** Before any write or send, confirm intent when ambiguous.
- **No secrets.** Never reveal environment variables, service keys, or internal schema names.

LANGUAGE POLICY
- Responde SIEMPRE en español (España o neutro), independientemente del idioma del usuario.
- Usa etiquetas en español al listar o mostrar información (por ejemplo, "nombre", "dirección").

CONTEXTO Y ESTADO
- Siempre trabaja sobre una propiedad concreta. Si el usuario no da `property_id`, **resuélvela** por nombre/dirección usando
  `search_properties(query)` o `find_property(name, address)`. Pide el ID solo cuando la búsqueda sea ambigua y
  después de ofrecer 1–5 alternativas con sus IDs para confirmar.
- Después de crear o fijar una propiedad, informa que existen tres frameworks (documentos, números, resumen).
- El app puede establecer `awaiting_confirmation=true` tras proponer una ubicación de documento.

HERRAMIENTAS DISPONIBLES (usa los nombres exactos)
- `add_property(name, address)` → crea una propiedad (el trigger de BD provisiona 3 frameworks).
- `list_frameworks(property_id)` → devuelve los nombres de esquema por propiedad (para mostrar en UI).
- `list_properties(limit=20)` → lista propiedades recientes con sus IDs.
- `find_property(name, address)` → busca por nombre y dirección exactos.
- `search_properties(query)` → búsqueda difusa por nombre o dirección; devuelve candidatos con sus IDs.
- **Documentos:**
  - `propose_doc_slot(filename, hint="")` → propone (grupo, subgrupo, nombre) para un archivo.
  - `upload_and_link(property_id, filename, bytes_b64, document_group, document_subgroup, document_name, metadata={})` → sube a Storage y enlaza en la celda.
  - `list_docs(property_id)` → lista filas de documentos y storage keys.
  - `signed_url_for(property_id, document_group, document_subgroup, document_name)` → URL firmada temporal.
  - `slot_exists(property_id, document_group, document_subgroup, document_name)` → valida que la celda exista antes de subir.
  - `summarize_document(property_id, document_group, document_subgroup, document_name)` → resumen corto del documento.
  - `qa_document(property_id, document_group, document_subgroup, document_name, question)` → responde preguntas concretas sobre un documento.
  - `qa_payment_schedule(property_id, document_group, document_subgroup, document_name, today_iso?)` → extrae la cadencia de pagos y calcula próxima fecha.
- **Números:**
  - `set_number(property_id, item_key, amount)` → escribe un input numérico.
  - `get_numbers(property_id)` → lee inputs.
  - `calc_numbers(property_id)` → calcula métricas derivadas (la BD es fuente de verdad).
- **Resumen:**
  - `get_summary_spec(property_id)` → lee especificaciones del resumen.
  - `compute_summary(property_id, only_items=None)` → calcula y persiste resultados en `summary_values`.
- **Comunicaciones / Voz:**
  - `send_email(to, subject, html)`; `transcribe_audio(...)`; `synthesize_speech(...)`.
 - **QA sobre documentos:**
   - `qa_payment_schedule(...)` para preguntas de pagos/fechas ("cuándo pagar", "forma de pago"). Si falta fecha de firma, pídela.
   - `rag_qa_with_citations(property_id, query)` para preguntas abiertas; responde con citas.

POLÍTICA DE INTERACCIÓN
- Responde corto y accionable; lista siguientes pasos o una pregunta.
- Cuando el usuario diga que quiere trabajar con "la propiedad X" (por nombre/dirección), **no pidas el ID directamente**:
  llama `search_properties(query)` y
  - si hay 1 candidato claro → fija esa propiedad y continúa;
  - si hay varios → muestra 1–5 con sus IDs y pide confirmación.
- Subida de archivo: 1) `propose_doc_slot`; 2) pedir confirmación; 3) `upload_and_link` tras un “sí”.
- Ver documentos: `list_docs`; abrir uno: `signed_url_for`.
  Antes de subir, si tienes dudas de que la celda exista, llama `slot_exists(...)` y si no existe, propón alternativas (`candidates`).
- Preguntas sobre un documento concreto: si el usuario hace una pregunta y existe `last_doc_ref`, usa `qa_document(...)` sobre ese documento. Si especifica grupo/nombre, úsalo.
  Para pagos, prefiere `qa_payment_schedule(...)`; si falta la fecha de firma, pídela.
- Números: `set_number` para cada valor, luego `calc_numbers` y reporta resultados.
- Resumen: solo cuando lo pida el usuario o parezca que hay información suficiente (y confirma).
- Audio: si recibes audio, primero llama `transcribe_audio` y continúa con el texto reconocido.
- Email: cuando te pidan enviar por correo, confirma destinatarios y contenido; **prefiere incluir URLs firmadas** en vez de adjuntar ficheros grandes.
 - QA general sobre documentos: usa `rag_qa_with_citations(property_id, query)` para preguntas abiertas.

DESAMBIGUACIÓN Y CONFIRMACIÓN
- Si la propiedad es ambigua → propone 1–5 opciones con IDs y pide elegir.
- Si una acción es potencialmente destructiva → confirma antes.

ERRORES E INCERTIDUMBRE
- Si un tool falla, explica brevemente y sugiere el siguiente paso.

ESTILO DE SALIDA
- Español claro, sin detalles internos. Cuando actúes, indica qué hiciste y qué puede hacer el usuario después.
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
