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
        super().__init__(name="NumbersAgent", model="gpt-4o", temperature=0.3)
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
        """Override run to intercept template selection responses."""
        import logging
        logger = logging.getLogger(__name__)
        
        text_lower = user_input.lower().strip()
        
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
            
            # Force tool call
            try:
                result = set_numbers_template_tool(property_id=property_id, template_key=template_key)
                logger.info(f"[NumbersAgent] ✅ Template set result: {result}")
                
                return {
                    "action": "complete",
                    "agent": self.name,
                    "response": f"✅ Plantilla {template_key} seleccionada. Ahora puedes empezar a completar los valores.",
                    "tool_calls": [{
                        "name": "set_numbers_template",
                        "args": {"property_id": property_id, "template_key": template_key},
                        "result": result
                    }],
                    "latency_ms": 0,
                    "success": True
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
        
        # Check if user wants to select template (without specifying which one)
        if any(phrase in text_lower for phrase in ["completar plantilla", "plantilla numeros", "plantilla números", "trabajar con números"]):
            # Check if they specified a template
            has_template = any(t in text_lower for t in template_map.keys())
            if not has_template:
                self._waiting_for_template = True
        
        # Default: use parent's run method
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

