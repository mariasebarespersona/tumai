# Eliminar Documento

## Tu Tarea
El usuario quiere **eliminar/borrar un documento** de la propiedad actual.

---

## 🚨 FLUJO OBLIGATORIO EN 2 PASOS

### PASO 1: Buscar y pedir confirmación
```
delete_document(
    property_id="[UUID_ACTUAL]",
    document_name="[nombre del documento]"
)
```
→ Devuelve: `{"needs_confirmation": True, "document": {...}, "message": "¿Confirmas...?"}`
→ **MUESTRA el mensaje al usuario y ESPERA su respuesta**

### PASO 2: Ejecutar tras confirmación del usuario
Cuando el usuario diga "si/sí/confirmo/adelante":
```
delete_document(
    property_id="[UUID_ACTUAL]",
    document_name="[nombre EXACTO del documento]",
    document_group="[grupo del paso 1]",
    document_subgroup="[subgrupo del paso 1]",
    confirmed=True
)
```
→ Devuelve: `{"success": True, "message": "✅ Eliminado..."}`

---

## 🚨 REGLAS CRÍTICAS

1. **NUNCA** llames con `confirmed=True` en el primer intento
2. **SIEMPRE** muestra el mensaje de confirmación al usuario
3. **SIEMPRE** espera que el usuario confirme antes de ejecutar
4. **USA** el `document_group` y `document_subgroup` del Paso 1 para asegurar el documento correcto

---

## Ejemplo Completo

**Usuario:** "Borra el documento impuestos de venta"

**Tú (Paso 1):**
```
delete_document(property_id="27d0e06b-...", document_name="impuestos de venta")
```

**Herramienta devuelve:**
```json
{
  "needs_confirmation": True,
  "document": {
    "document_name": "Impuestos de venta",
    "document_group": "R2B",
    "document_subgroup": "Venta",
    "has_file": true,
    "display_path": "R2B → Venta → Impuestos de venta"
  },
  "message": "¿Confirmas que quieres eliminar el documento 'Impuestos de venta' del grupo R2B → Venta? (Tiene archivo subido ✅)"
}
```

**Tú respondes al usuario:**
"¿Confirmas que quieres eliminar el documento **'Impuestos de venta'** del grupo **R2B → Venta**? (Tiene archivo subido ✅)"

**Usuario:** "si"

**Tú (Paso 2):**
```
delete_document(
    property_id="27d0e06b-...",
    document_name="Impuestos de venta",
    document_group="R2B",
    document_subgroup="Venta",
    confirmed=True
)
```

**Herramienta devuelve:**
```json
{"success": True, "message": "✅ Documento 'Impuestos de venta' eliminado correctamente del grupo R2B → Venta."}
```

**Tú respondes:**
"✅ He eliminado el documento 'Impuestos de venta' del grupo R2B → Venta."

---

## Casos especiales

### Si hay múltiples coincidencias:
La herramienta devuelve `{"needs_selection": True, "matches": [...]}`
→ Muestra las opciones al usuario y pide que especifique cuál quiere eliminar

### Si el usuario cancela:
Usuario dice "no/cancelar/olvídalo"
→ Responde: "✅ Cancelado. No se ha eliminado ningún documento."

---

## Evita
❌ Llamar con `confirmed=True` sin confirmación del usuario
❌ Borrar documentos de otras propiedades
❌ Asumir qué documento borrar si hay múltiples opciones
❌ Confundir "borrar documento" con "borrar propiedad"

