# Flujo: Cambiar Estrategia de Documentos (R2B vs Promoción)

El usuario quiere cambiar de sección documental o elegir una estrategia.

## Contexto
El framework de documentos tiene 3 niveles:
1. **COMPRA** (obligatorio para todas las propiedades)
2. **Estrategia**: R2B (Reformar y Vender) O Promoción (Obra Nueva)
3. **Sub-secciones** según la estrategia elegida

## Proceso

### 1. Identificar la intención del usuario
- "Voy a elegir R2B" → Quiere documentos de R2B
- "No tengo más docs de COMPRA, paso a R2B" → Quiere cambiar de sección
- "Elijo el camino Promoción" → Quiere documentos de Promoción

### 2. Llamar a set_property_strategy
```
set_property_strategy(property_id, strategy="R2B")  # o "Promocion"
```

### 3. Confirmar y guiar al usuario
Respuesta ejemplo:
```
✅ He marcado la estrategia como R2B para esta propiedad.

Ahora puedes subir los documentos de R2B:
📁 **Diseño + Facturas** (obligatorio):
- Mapas nivel
- Contrato arquitecto
- Proyecto básico
- Licencia de obra

¿Tienes alguno de estos documentos para subir?
```

## ⚠️ IMPORTANTE

### NO confundir con NumbersAgent
- "R2B" en contexto de documentos → DocsAgent (tú)
- "R2B" en contexto de números/plantilla → NumbersAgent

### Ejemplos CORRECTOS:
- "Quiero seguir por R2B" → Llama set_property_strategy, NO números
- "No tengo más docs de COMPRA, elijo R2B" → Llama set_property_strategy
- "Voy a elegir el camino Promoción" → Llama set_property_strategy

### Ejemplos que NO son para ti:
- "Quiero completar la plantilla R2B" → Eso es para NumbersAgent (números)
- "Pon B5 en 1000 en R2B" → Eso es para NumbersAgent (celdas)

## Herramienta a usar
```
set_property_strategy(property_id, strategy)
```
- strategy: "R2B" o "Promocion"

## Respuesta esperada
1. Confirmar la estrategia elegida
2. Listar los documentos disponibles para esa estrategia
3. Preguntar si tiene alguno para subir

