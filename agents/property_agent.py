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
            current_prop_info = f"""
## 🎯 PROPIEDAD ACTUAL (FUENTE DE VERDAD)
**Nombre**: {property_name}

⚠️ **CRÍTICO**: Si el usuario pregunta "¿en qué propiedad estamos?" o similar:
- Responde SIEMPRE con "{property_name}" (el valor de arriba)
- NO uses información del historial de conversación
- El historial puede tener propiedades anteriores, IGNÓRALAS
"""
        else:
            current_prop_info = "\n⚠️ No hay propiedad activa seleccionada.\n"
        
        return f"""Eres un asistente especializado en **gestión de propiedades**.
{current_prop_info}

## Tu responsabilidad
1. **Responder sobre la propiedad actual** (usa SIEMPRE el valor de "PROPIEDAD ACTUAL" arriba)
2. **Crear nuevas propiedades** (nombre, dirección)
3. **Cambiar entre propiedades** (switch/cambiar)
4. **Listar propiedades** existentes
5. **Eliminar propiedades** (con confirmación)
6. **Buscar propiedades** por nombre

## NO manejes
- Números o plantillas R2B → NumbersAgent
- Documentos o emails → DocsAgent

## Herramientas disponibles
- `add_property(name, address)`: Crear nueva propiedad
- `set_current_property(property_id)`: Cambiar propiedad actual
- `list_properties(limit)`: Listar propiedades
- `delete_property(property_id)`: Eliminar propiedad
- `get_property(property_id)`: Obtener detalles

## ⚠️ REGLAS CRÍTICAS PARA ELIMINACIÓN

### Paso 1: Usuario pide eliminar
Usuario: "elimina Sobradiel" o "borra la propiedad X"
Tú: "⚠️ ¿Estás seguro que quieres eliminar la propiedad 'X'? Esta acción no se puede deshacer."

### Paso 2: Usuario confirma con "si/sí/confirmo/adelante"
1. Llama `list_properties()` para encontrar el ID de la propiedad
2. Busca la propiedad por nombre en los resultados
3. Llama `delete_property(property_id=ID_ENCONTRADO)`
4. Responde: "✅ He eliminado la propiedad 'X'."

### Paso 2 alternativo: Usuario dice "no/cancelar"
Tú: "✅ Cancelado. La propiedad no ha sido eliminada."

## IMPORTANTE: Flujo de conversación
- **SIEMPRE revisa el historial** para entender el contexto
- Si el mensaje anterior fue una pregunta de confirmación tuya, y el usuario dice "si" → EJECUTA la acción
- Si el usuario dice "no" → CANCELA la acción
- **NUNCA** confundas "si" con otra cosa cuando acabas de pedir confirmación

## Ejemplos completos

### Crear propiedad
Usuario: "crea propiedad 15Panes en Calle X"
Tú: [CALL add_property(name="15Panes", address="Calle X")]
Tú: "✅ He creado la propiedad '15Panes' en Calle X."

### Eliminar propiedad (flujo completo)
Usuario: "elimina Sobradiel"
Tú: "⚠️ ¿Estás seguro que quieres eliminar la propiedad 'Sobradiel'? Esta acción no se puede deshacer."
Usuario: "si"
Tú: [CALL list_properties(limit=50)]
   → Encuentra: {{"id": "abc-123", "name": "Sobradiel", ...}}
Tú: [CALL delete_property(property_id="abc-123")]
Tú: "✅ He eliminado la propiedad 'Sobradiel'."

### Listar propiedades
Usuario: "qué propiedades tengo?"
Tú: [CALL list_properties(limit=20)]
Tú: "Tienes 3 propiedades: 1) Sobradiel 4, 2) 15Panes, 3) Villa Málaga"
"""
    
    def run(self, user_input: str, property_id: str = None, context: dict = None):
        """
        Override run to handle property operations.
        
        SIMPLIFIED: Most logic is now handled by the LLM via the prompt.
        We only intercept specific cases that need direct tool calls for better UX.
        """
        import logging
        logger = logging.getLogger(__name__)
        
        text_lower = user_input.lower().strip()
        ctx = context or {}
        
        # Check if user is providing property name/address (continuation of create flow)
        # This happens when agent asked for name/address and user responds with just the data
        history = ctx.get("history", [])
        if history and len(history) >= 1:
            # Check if the last AI message was asking for property name/address
            last_ai_msg = None
            for msg in reversed(history):
                if hasattr(msg, 'content') and hasattr(msg, 'type') and msg.type == 'ai':
                    last_ai_msg = msg.content.lower() if msg.content else ""
                    break
            
            if last_ai_msg and any(phrase in last_ai_msg for phrase in [
                "nombre y la dirección", "nombre y dirección", 
                "proporciona el nombre", "proporciona nombre",
                "qué nombre", "que nombre", "cómo se llama", "como se llama"
            ]):
                # User is responding with property data - create the property directly
                logger.info(f"[PropertyAgent] 🎯 Detected property data response: '{user_input}'")
                
                # Parse name and address from input
                # Common formats: "Name - Address", "Name, Address", just "Name"
                name = user_input.strip()
                address = ""
                
                if " - " in user_input:
                    parts = user_input.split(" - ", 1)
                    name = parts[0].strip()
                    address = parts[1].strip() if len(parts) > 1 else ""
                elif ", " in user_input:
                    parts = user_input.split(", ", 1)
                    name = parts[0].strip()
                    address = parts[1].strip() if len(parts) > 1 else ""
                
                try:
                    result = add_property_tool.invoke({"name": name, "address": address})
                    logger.info(f"[PropertyAgent] ✅ Created property: {name} at {address}")
                    
                    new_property_id = result.get("id") or result.get("property_id")
                    
                    return {
                        "action": "complete",
                        "agent": self.name,
                        "response": f"✅ He creado la propiedad '{name}'" + (f" en {address}" if address else "") + ".",
                        "tool_calls": [
                            {
                                "name": "add_property",
                                "args": {"name": name, "address": address},
                                "result": result
                            }
                        ],
                        "property_id": new_property_id,
                        "latency_ms": 0,
                        "success": True
                    }
                except Exception as e:
                    logger.error(f"[PropertyAgent] ❌ Error creating property: {e}")
                    return {
                        "action": "error",
                        "agent": self.name,
                        "response": f"Error al crear la propiedad: {str(e)}",
                        "error": str(e),
                        "latency_ms": 0,
                        "success": False
                    }
        
        # Check if user wants to switch to a property
        if any(phrase in text_lower for phrase in ["trabajar con", "cambiar a", "switch to", "usar", "metete", "meterse", "entra", "entrar", "abre", "abrir", "ve a", "ir a"]):
            # Try to find the property by name using list_properties
            logger.info(f"[PropertyAgent] 🎯 Detected property switch request: '{user_input}'")
            
            try:
                # List all properties and search by name
                all_properties = list_properties_tool.invoke({"limit": 50})
                logger.info(f"[PropertyAgent] Found {len(all_properties)} properties")
                
                # Extract property name from user input
                # Remove common phrases to get just the property name
                property_name_search = text_lower
                for phrase in ["trabajar con", "cambiar a", "switch to", "usar", "metete en", "metete", "meterse en", "meterse", "entra en", "entra", "entrar en", "entrar", "abre", "abrir", "ve a", "ir a", "la propiedad", "propiedad"]:
                    property_name_search = property_name_search.replace(phrase, "").strip()
                
                logger.info(f"[PropertyAgent] Searching for property: '{property_name_search}'")
                
                # Find matching property (case-insensitive partial match)
                matching_prop = None
                for prop in all_properties:
                    prop_name_lower = prop.get("name", "").lower()
                    if property_name_search in prop_name_lower or prop_name_lower in property_name_search:
                        matching_prop = prop
                        break
                
                if matching_prop:
                    # Found property, switch to it
                    prop_id = matching_prop["id"]
                    prop_name = matching_prop["name"]
                    
                    # Set as current property
                    set_result = set_current_property_tool.invoke({"property_id": prop_id})
                    logger.info(f"[PropertyAgent] ✅ Switched to property: {prop_name} ({prop_id})")
                    
                    return {
                        "action": "complete",
                        "agent": self.name,
                        "response": f"✅ Ahora estás trabajando con '{prop_name}'.",
                        "tool_calls": [
                            {
                                "name": "list_properties",
                                "args": {"limit": 50},
                                "result": f"Found {len(all_properties)} properties"
                            },
                            {
                                "name": "set_current_property",
                                "args": {"property_id": prop_id},
                                "result": set_result
                            }
                        ],
                        "property_id": prop_id,  # Critical: return property_id so UI bar updates
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

