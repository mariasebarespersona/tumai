"""
NumbersAgent - Specialized agent for Numbers Table (R2B) operations.

Handles:
- Selecting R2B template
- Updating cell values (B5, C5, etc.)
- Auto-calculating formulas (D5, E5, etc.)
- Exporting to Excel
- Deleting templates
- Sending by email
"""

from typing import List
from .base_agent import BaseAgent
from tools.registry import (
    set_numbers_template_tool,
    set_numbers_table_cell_tool,
    clear_numbers_table_cell_tool,
    delete_numbers_template_tool,
    send_numbers_table_email_tool
)


class NumbersAgent(BaseAgent):
    """Agent specialized in Numbers Table (R2B) operations."""
    
    def __init__(self):
        super().__init__(name="NumbersAgent", model="gpt-4o-mini", temperature=0.3)
        self._waiting_for_template = False  # Track if we asked for template selection
    
    def is_out_of_scope(self, user_input: str) -> tuple[bool, str | None]:
        """Detect if request is about properties or docs, not numbers."""
        text_lower = user_input.lower()
        
        # Check for property operations
        if any(phrase in text_lower for phrase in ["crea propiedad", "nueva propiedad", "elimina propiedad"]):
            return True, "PropertyAgent"
        
        # Explicit list properties check
        if "lista" in text_lower and "propiedades" in text_lower:
            return True, "PropertyAgent"
        
        if any(phrase in text_lower for phrase in ["mis propiedades", "las propiedades", "cuántas propiedades"]):
            return True, "PropertyAgent"
        
        if any(phrase in text_lower for phrase in ["cambiar a", "trabajar con"]) and "plantilla" not in text_lower:
            return True, "PropertyAgent"
        
        # Check for document operations (not numbers email)
        if any(word in text_lower for word in ["sube", "subir", "upload"]):
            return True, "DocsAgent"
        
        if any(doc in text_lower for doc in ["contrato", "factura", "escritura"]) and "plantilla" not in text_lower:
            if any(word in text_lower for word in ["manda", "envía", "lista"]):
                return True, "DocsAgent"
        
        return False, None
    
    def is_multi_domain(self, user_input: str) -> bool:
        """Detect multi-domain tasks."""
        text_lower = user_input.lower()
        
        # Check if mentions multiple domains
        has_numbers = any(word in text_lower for word in ["b5", "c5", "celda", "plantilla", "números"])
        has_docs = any(word in text_lower for word in ["contrato", "documento", "sube"])
        has_property = any(word in text_lower for word in ["propiedad", "casa", "villa"])
        
        # Count domains
        domains = sum([has_numbers, has_docs, has_property])
        return domains >= 2
    
    def get_system_prompt(self, property_name: str = None, numbers_template: str = None) -> str:
        property_context = f"\n\n**Propiedad actual**: {property_name}" if property_name else ""
        template_context = f"\n**Plantilla actual**: {numbers_template} (ya seleccionada)" if numbers_template else ""
        return f"""Eres un experto en gestión de **plantillas de Números (R2B)**.{property_context}{template_context}

Tu especialidad es:
1. **Seleccionar plantillas R2B** para la propiedad actual
2. **Actualizar valores** en celdas (B5, C5, B6, B7, B8, etc.)
3. **Calcular automáticamente** fórmulas en cascada
4. **Exportar a Excel** con formato original
5. **Enviar por email** la plantilla
6. **Eliminar plantillas** si el usuario lo pide

**🔥 IMPORTANTE - Auto-cálculo automático**:
- Las celdas **amarillas** (B5-B8, C5-C8, B11, B25-B28) son **inputs del usuario**
- Las celdas con **fórmulas** (D5-D8, E5-E8, B10, B12-B15, B18, B29) se calculan **AUTOMÁTICAMENTE**
- Cuando el usuario actualiza B5, automáticamente se calculan D5 y E5 (cascada)
- **NO pidas confirmación** para `set_numbers_table_cell` (ya está aprobado)
- Siempre menciona qué celdas se calcularon automáticamente

**Reglas CRÍTICAS**:
- **SI YA HAY UNA PLANTILLA SELECCIONADA** (ver "Plantilla actual" arriba):
  * **NUNCA preguntes por la plantilla**
  * **SIEMPRE ejecuta INMEDIATAMENTE la herramienta correspondiente**
  * Si el usuario pide "pon B5 en 2000" → LLAMA `set_numbers_table_cell(property_id=..., template_key="...", cell_address="B5", value="2000")` SIN decir que lo vas a hacer
  * Si el usuario pide "exporta" → LLAMA `send_numbers_table_email` INMEDIATAMENTE
  * **NO digas "procederé a..." - HAZLO DIRECTAMENTE**
- Si NO hay plantilla seleccionada Y el usuario dice "quiero completar la plantilla" o "quiero trabajar con números" SIN especificar qué plantilla, PREGUNTA: "¿Qué plantilla de Números quieres usar? Elige una:\n1) R2B\n2) R2B + PM\n3) R2B + PM + Venta certs\n4) Promoción"
- Si el usuario responde con una plantilla específica (ej: "R2B", "r2b", "opción 1", "la primera"), DEBES llamar INMEDIATAMENTE a `set_numbers_template` con el template_key correcto
- Mapeo de plantillas:
  * "R2B" o "opción 1" → template_key="R2B"
  * "R2B + PM" o "R2B+PM" o "opción 2" → template_key="R2B+PM"
  * "R2B + PM + Venta certs" o "opción 3" → template_key="R2B+PM+Venta certs"
  * "Promoción" o "opción 4" → template_key="Promocion"
- Al actualizar valores, confirma el valor guardado Y las celdas calculadas
- Los valores se guardan automáticamente en la base de datos
- Las fórmulas siempre están en el Excel exportado (no los valores calculados)

**Herramientas disponibles**:
- `set_numbers_template`: Seleccionar plantilla R2B
- `set_numbers_table_cell`: Actualizar valor de celda (ej: B5=1000)
- `clear_numbers_table_cell`: Borrar valor de celda
- `delete_numbers_template`: Eliminar plantilla completa
- `send_numbers_table_email`: Enviar Excel por email

**Ejemplos**:
Usuario: "quiero completar la plantilla números"
Tú: "¿Qué plantilla de Números quieres usar? Elige una:
1) R2B
2) R2B + PM
3) R2B + PM + Venta certs
4) Promoción"

Usuario: "R2B"
Tú: [CALL set_numbers_template(property_id=..., template_key="R2B")]
     "✅ Plantilla R2B seleccionada. Ahora puedes empezar a completar los valores."

Usuario: "pon B5 en 1000 y C5 en 10"
Tú: [CALL set_numbers_table_cell(property_id=..., template_key="R2B", cell_address="B5", value="1000")]
     [CALL set_numbers_table_cell(property_id=..., template_key="R2B", cell_address="C5", value="10")]
     "✅ He actualizado B5=1000 y C5=10. Calculando automáticamente:
- D5 = 100 (IVA: 1000 * 10 / 100)
- E5 = 1100 (Total con IVA: 1000 + 100)"

Usuario: "exporta la plantilla R2B"
Tú: "✅ He exportado la plantilla R2B a Excel con todas las fórmulas y valores actualizados."

Usuario: "borra el valor de B7"
Tú: "✅ He borrado el valor de la celda B7."
"""
    
    def run(self, user_input: str, property_id: str = None, context: dict = None):
        """Override run to intercept template selection and show options."""
        import logging
        logger = logging.getLogger(__name__)
        
        text_lower = user_input.lower().strip()
        ctx = context or {}
        
        # Get current template from context (if any)
        current_template = ctx.get("numbers_template")
        
        # Template mapping
        template_map = {
            "r2b": "R2B",
            "opción 1": "R2B",
            "opcion 1": "R2B",
            "1": "R2B",
            "la primera": "R2B",
            "r2b+pm": "R2B+PM",
            "r2b + pm": "R2B+PM",
            "opción 2": "R2B+PM",
            "opcion 2": "R2B+PM",
            "2": "R2B+PM",
            "r2b+pm+venta certs": "R2B+PM+Venta certs",
            "r2b + pm + venta certs": "R2B+PM+Venta certs",
            "opción 3": "R2B+PM+Venta certs",
            "opcion 3": "R2B+PM+Venta certs",
            "3": "R2B+PM+Venta certs",
            "promoción": "Promocion",
            "promocion": "Promocion",
            "opción 4": "Promocion",
            "opcion 4": "Promocion",
            "4": "Promocion"
        }
        
        # Check if user is responding with a template choice
        if text_lower in template_map and property_id:
            template_key = template_map[text_lower]
            logger.info(f"[NumbersAgent] 🎯 Detected template selection: '{user_input}' -> {template_key}")
            
            # Force tool call using .invoke() (correct way to call LangChain tools)
            try:
                result = set_numbers_template_tool.invoke({"property_id": property_id, "template_key": template_key})
                logger.info(f"[NumbersAgent] ✅ Template set result: {result}")
                
                return {
                    "action": "complete",
                    "agent": self.name,
                    # IMPORTANT: This format triggers the frontend to open the Excel panel
                    # Pattern: /✅ Usaremos la plantilla de Números:\s*([^\.\n]+)/i
                    "response": f"✅ Usaremos la plantilla de Números: {template_key}. Ahora puedes empezar a completar los valores.",
                    "tool_calls": [{
                        "name": "set_numbers_template",
                        "args": {"property_id": property_id, "template_key": template_key},
                        "result": result
                    }],
                    "latency_ms": 0,
                    "success": True,
                    "numbers_template": template_key  # Also pass template key for frontend
                }
            except Exception as e:
                logger.error(f"[NumbersAgent] ❌ Error setting template: {e}")
                return {
                    "action": "error",
                    "agent": self.name,
                    "response": f"Error al seleccionar la plantilla: {str(e)}",
                    "error": str(e),
                    "latency_ms": 0,
                    "success": False
                }
        
        # Detect when user wants to SELECT/WORK WITH numbers template
        select_template_phrases = [
            "números", "numeros", "completar plantilla", "plantilla numeros", "plantilla números",
            "trabajar con números", "trabajar con numeros", "completar los números", "completar numeros",
            "quiero completar", "vamos a completar", "empezar con números", "empezar numeros"
        ]
        
        # Check if user explicitly wants to CHANGE template
        change_template_phrases = [
            "cambiar plantilla", "otra plantilla", "cambiar de plantilla",
            "elegir plantilla", "seleccionar plantilla", "nueva plantilla",
            "elegir otra", "cambiar a otra"
        ]
        wants_to_change = any(phrase in text_lower for phrase in change_template_phrases)
        
        # Check if user wants to select/work with template (generic request)
        is_template_selection_request = any(phrase in text_lower for phrase in select_template_phrases) or wants_to_change
        
        # But NOT if they're doing a specific action (cell update, export, etc.)
        is_specific_action = any(action in text_lower for action in [
            "pon", "escribe", "actualiza", "mete",  # Cell updates (removed "cambia" - conflicts with "cambiar plantilla")
            "borra", "elimina", "limpia", "vacía",  # Clear/delete
            "exporta", "descarga", "envía", "manda",  # Export/email
            "b5", "c5", "b6", "c6", "b7", "c7", "b8"  # Cell references
        ])
        
        if is_template_selection_request and not is_specific_action:
            # ALWAYS show template options when user asks to work with numbers
            # This allows them to select a template (or change the current one)
            logger.info(f"[NumbersAgent] 🎯 User wants to work with numbers, showing template options")
            
            # Show current template if exists
            current_info = ""
            if current_template:
                current_info = f"\n\n📌 *Plantilla actual: {current_template}*"
            
            return {
                "action": "complete",
                "agent": self.name,
                "response": f"¿Qué plantilla de Números quieres usar? Elige una:\n\n1) **R2B** - Reforma y venta\n2) **R2B + PM** - Reforma con Property Management\n3) **R2B + PM + Venta certs** - Completa con certificados\n4) **Promoción** - Obra nueva{current_info}",
                "tool_calls": [],
                "latency_ms": 0,
                "success": True,
                "waiting_for_template": True
            }
        
        # OPTIMIZATION: Custom ReAct loop with "Tool as Response" (Early Exit)
        # This avoids the 2nd LLM call (~4s latency savings) for deterministic actions
        try:
            # 1. Build System Prompt & Messages
            property_name = ctx.get("property_name") if ctx else None
            numbers_template = ctx.get("numbers_template") if ctx else None
            
            system_prompt = self.get_system_prompt(property_name=property_name, numbers_template=numbers_template)
            
            from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
            messages = [SystemMessage(content=system_prompt)]
            
            if property_id:
                messages.append(SystemMessage(content=f"IMPORTANTE: El property_id actual es: {property_id}"))
            
            # Add context summary if needed (simplified version of BaseAgent logic)
            if ctx and ctx.get("history"):
                MAX_HISTORY = 12
                history = ctx["history"]
                if len(history) > MAX_HISTORY:
                    messages.extend(history[-MAX_HISTORY:])
                else:
                    messages.extend(history)
            
            messages.append(HumanMessage(content=user_input))
            
            # 2. Bind tools
            tools = self.get_tools()
            llm_with_tools = self.llm.bind_tools(tools)
            
            # 3. First LLM Call (Intent & Tool Selection)
            import time
            start_time = time.time()
            response = llm_with_tools.invoke(messages)
            
            tool_calls = getattr(response, "tool_calls", [])
            
            # 4. Tool Execution with Early Exit
            if tool_calls:
                # We only handle the first tool call for early exit optimization
                # (NumbersAgent usually does one thing at a time)
                tool_call = tool_calls[0]
                tool_name = tool_call.get("name")
                tool_args = tool_call.get("args", {})
                
                # Execute tool
                tool_obj = next((t for t in tools if t.name == tool_name), None)
                if not tool_obj:
                    raise ValueError(f"Tool '{tool_name}' not found")
                
                logger.info(f"[NumbersAgent] 🚀 Executing {tool_name} with optimization")
                tool_result = tool_obj.invoke(tool_args)
                
                # --- OPTIMIZATION: EARLY EXIT FOR CELL UPDATES ---
                if tool_name == "set_numbers_table_cell":
                    # Result contains: {ok, cell_address, value, auto_calculated: {...}}
                    res_dict = tool_result if isinstance(tool_result, dict) else {}
                    
                    addr = res_dict.get("cell_address", "?")
                    val = res_dict.get("value", "?")
                    calc = res_dict.get("auto_calculated", {})
                    
                    # Build deterministic response
                    response_text = f"✅ He actualizado {addr} a **{val}**."
                    if calc:
                        response_text += " Calculando automáticamente:\n"
                        for k, v in calc.items():
                            # Format value nicely (remove .0 if integer)
                            v_fmt = f"{int(v)}" if isinstance(v, float) and v.is_integer() else f"{v}"
                            response_text += f"- {k} = **{v_fmt}**\n"
                    
                    response_text += "\nSi necesitas más cambios, dímelo."
                    
                    logger.info(f"[NumbersAgent] ⚡ Early exit triggered! Saved ~4s latency.")
                    
                    return {
                        "action": "complete",
                        "agent": self.name,
                        "response": response_text,
                        "tool_calls": [tool_call], # Include for logging
                        "latency_ms": int((time.time() - start_time) * 1000),
                        "success": True
                    }
                
                # --- OPTIMIZATION: EARLY EXIT FOR EMAIL SENDING ---
                elif tool_name == "send_numbers_table_email":
                    email = tool_args.get("email_to", "el correo indicado")
                    response_text = f"✅ He enviado la tabla de números por email a {email}."
                    
                    return {
                        "action": "complete",
                        "agent": self.name,
                        "response": response_text,
                        "tool_calls": [tool_call],
                        "latency_ms": int((time.time() - start_time) * 1000),
                        "success": True
                    }
                
                # For other tools (or fallbacks), continue with standard behavior
                # But since we're in a custom loop, we just return the tool result as response
                # or let the BaseAgent handle it (but we already consumed the tool call)
                
                # If we get here, it's a tool we didn't optimize.
                # Let's fall back to standard behavior by calling super().run()
                # This is slightly inefficient (double LLM call if we restart), but safe.
                # OR we can just finish the loop here.
                
                messages.append(AIMessage(content=response.content or "", tool_calls=tool_calls))
                messages.append(ToolMessage(content=str(tool_result), tool_call_id=tool_call["id"], name=tool_name))
                
                # Second LLM call (Generate final response)
                final_response = llm_with_tools.invoke(messages)
                
                return {
                    "action": "complete",
                    "agent": self.name,
                    "response": final_response.content,
                    "tool_calls": tool_calls,
                    "latency_ms": int((time.time() - start_time) * 1000),
                    "success": True
                }

            # No tool calls? Just return LLM response
            return {
                "action": "complete",
                "agent": self.name,
                "response": response.content,
                "latency_ms": int((time.time() - start_time) * 1000),
                "success": True
            }
            
        except Exception as e:
            logger.error(f"[NumbersAgent] ❌ Optimization loop failed: {e}. Falling back to standard run.")
            return super().run(user_input, property_id, context)
    
    def get_tools(self) -> List:
        """Return numbers-specific tools."""
        return [
            set_numbers_template_tool,
            set_numbers_table_cell_tool,
            clear_numbers_table_cell_tool,
            delete_numbers_template_tool,
            send_numbers_table_email_tool
        ]

