"""
PropertyAgent - Specialized agent for property management.

Handles:
- Creating new properties
- Switching between properties
- Listing properties
- Deleting properties
"""

from typing import List
from .base_agent import BaseAgent
from tools.registry import (
    add_property_tool,
    set_current_property_tool,
    list_properties_tool,
    delete_property_tool,
    find_property_tool,
    get_property_tool
)


class PropertyAgent(BaseAgent):
    """Agent specialized in property management operations."""
    
    def __init__(self):
        super().__init__(name="PropertyAgent", model="gpt-4o", temperature=0.5)
    
    def get_system_prompt(self, property_name: str = None) -> str:
        current_prop_info = ""
        if property_name:
            current_prop_info = f"\n**Propiedad actual**: {property_name}\n"
        
        return f"""Eres un asistente especializado en **gestión de propiedades**.
{current_prop_info}
Tu **única responsabilidad** es ayudar al usuario con:
1. **Responder sobre la propiedad actual** (si te preguntan "¿en qué propiedad estamos?", responde con la propiedad actual)
2. **Crear nuevas propiedades** (nombre, dirección)
3. **Cambiar entre propiedades** (switch/cambiar a otra propiedad)
4. **Listar propiedades** existentes
5. **Eliminar propiedades** (con confirmación)
6. **Buscar propiedades** por nombre o dirección

**NO manejes**:
- Números o plantillas R2B (eso es para NumbersAgent)
- Documentos o emails (eso es para DocsAgent)
- Cálculos o fórmulas (eso es para NumbersAgent)

**Reglas**:
- Si el usuario pregunta "¿en qué propiedad estamos?" o similar, responde DIRECTAMENTE con la propiedad actual (no uses herramientas)
- Cuando crees una propiedad, **EJECUTA INMEDIATAMENTE** `add_property` (no pidas confirmación)
- Al cambiar de propiedad, confirma siempre cuál es la propiedad activa después
- Al eliminar, SIEMPRE pide confirmación explícita primero
- Sé conciso y directo
- **NO pidas confirmación** para crear propiedades - hazlo directamente

**Herramientas disponibles**:
- `add_property`: Crear nueva propiedad
- `set_current_property`: Cambiar propiedad actual
- `list_properties`: Listar todas las propiedades
- `delete_property`: Eliminar propiedad (requiere confirmación)
- `find_property`: Buscar propiedad por nombre/dirección
- `get_property`: Obtener detalles de una propiedad

**Ejemplos**:
Usuario: "¿en qué propiedad estamos trabajando?"
Tú: "Estamos trabajando con '{property_name or 'ninguna propiedad activa'}'."

Usuario: "crea propiedad 15Panes con dirección Calle X"
Tú: [CALL add_property(name="15Panes", address="Calle X")]
Tú: "✅ He creado la propiedad '15Panes' en Calle X."

Usuario: "crea casa demo 20"
Tú: [CALL add_property(name="Casa Demo 20", address="")]
Tú: "✅ He creado la propiedad 'Casa Demo 20'."

Usuario: "cambia a villa málaga"
Tú: "✅ Ahora estás trabajando con 'Villa Málaga'."

Usuario: "lista mis propiedades"
Tú: "Tienes 5 propiedades: Casa Demo 12, Villa Málaga, ..."

Usuario: "elimina la propiedad X"
Tú: "⚠️ ¿Estás seguro que quieres eliminar la propiedad 'X'? Esta acción no se puede deshacer."
"""
    
    def run(self, user_input: str, property_id: str = None, context: dict = None):
        """Override run to intercept property switching requests."""
        import logging
        logger = logging.getLogger(__name__)
        
        text_lower = user_input.lower().strip()
        
        # Check if user wants to switch to a property
        if any(phrase in text_lower for phrase in ["trabajar con", "cambiar a", "switch to", "usar"]):
            # Try to find the property by name
            logger.info(f"[PropertyAgent] 🎯 Detected property switch request: '{user_input}'")
            
            try:
                # Call find_property to search by name
                result = find_property_tool(query=user_input)
                logger.info(f"[PropertyAgent] Search result: {result}")
                
                if result.get("matches") and len(result["matches"]) > 0:
                    # Found property, switch to it
                    prop = result["matches"][0]
                    prop_id = prop["id"]
                    prop_name = prop["name"]
                    
                    # Set as current property
                    set_result = set_current_property_tool(property_id=prop_id)
                    logger.info(f"[PropertyAgent] ✅ Switched to property: {prop_name} ({prop_id})")
                    
                    return {
                        "action": "complete",
                        "agent": self.name,
                        "response": f"✅ Ahora estás trabajando con '{prop_name}'.",
                        "tool_calls": [
                            {
                                "name": "find_property",
                                "args": {"query": user_input},
                                "result": result
                            },
                            {
                                "name": "set_current_property",
                                "args": {"property_id": prop_id},
                                "result": set_result
                            }
                        ],
                        "property_id": prop_id,  # Critical: return property_id so it's updated
                        "latency_ms": 0,
                        "success": True
                    }
                else:
                    return {
                        "action": "complete",
                        "agent": self.name,
                        "response": f"No encontré ninguna propiedad que coincida con '{user_input}'. ¿Quieres que liste todas las propiedades disponibles?",
                        "tool_calls": [],
                        "latency_ms": 0,
                        "success": True
                    }
            except Exception as e:
                logger.error(f"[PropertyAgent] ❌ Error switching property: {e}")
                return {
                    "action": "error",
                    "agent": self.name,
                    "response": f"Error al cambiar de propiedad: {str(e)}",
                    "error": str(e),
                    "latency_ms": 0,
                    "success": False
                }
        
        # Default: use parent's run method
        return super().run(user_input, property_id, context)
    
    def get_tools(self) -> List:
        """Return property-specific tools."""
        return [
            add_property_tool,
            set_current_property_tool,
            list_properties_tool,
            delete_property_tool,
            find_property_tool,
            get_property_tool
        ]

