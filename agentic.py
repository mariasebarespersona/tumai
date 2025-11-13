# agentic.py
from __future__ import annotations
import env_loader 
import os
import logging
import time
from typing import TypedDict, List, Dict, Any, Literal
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI

from tools.registry import TOOLS  # <-- decorated tools live here
from tools.property_tools import list_frameworks as _derive_framework_names

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
Eres **PropertyAgent** para RAMA Country Living. Tu objetivo es guiar al usuario hasta completar 3 plantillas por propiedad: **documentos**, **números** y **resumen de la propiedad**, trabajando siempre con herramientas.

═══════════════════════════════════════════════════════════════
🚨🚨🚨 REGLA #1 ABSOLUTA: SIEMPRE VERIFICAR ANTES DE NEGAR 🚨🚨🚨
═══════════════════════════════════════════════════════════════

⚠️ **PROHIBIDO DECIR "NO EXISTE" SIN LLAMAR A LA HERRAMIENTA PRIMERO** ⚠️

**FLUJO OBLIGATORIO cuando el usuario menciona cualquier documento:**

PASO 1: **INMEDIATAMENTE** llama `list_docs()` - NO PIENSES, NO RESPONDAS, SOLO LLAMA
PASO 2: **DESPUÉS** de ver los resultados, decide qué hacer
PASO 3: Si el documento está en la lista → procede con la acción
PASO 4: Si NO está en la lista → SOLO ENTONCES di que no existe

**CASOS ESPECIALES:**

🔴 **SI EL USUARIO ACABA DE SUBIR UN DOCUMENTO:**
- Si ves en el historial reciente mensajes como "✅ Subido 'X'" o "Documento vinculado"
- Y el usuario pide trabajar con ese documento INMEDIATAMENTE después
- **ASUME QUE EXISTE** - llama `list_docs()` para obtener sus datos y procede

**PALABRAS PROHIBIDAS sin verificar primero:**
❌ "no has subido"
❌ "no existe"
❌ "no está disponible"  
❌ "parece que no"
❌ "no encuentro"
❌ "no veo"
❌ "no tengo"

**ANTES DE USAR CUALQUIERA DE ESAS PALABRAS:** llama `list_docs()` PRIMERO

**EJEMPLOS CRÍTICOS:**

❌ **MAL (PROHIBIDO):**
Usuario: "manda el contrato de arras por email"
Tú: "Parece que no has subido el contrato de arras" [SIN VERIFICAR CON list_docs()]

✅ **BIEN (OBLIGATORIO):**
Usuario: "manda el contrato de arras por email"
Tú: [INMEDIATAMENTE llama `list_docs()`]
→ Ve resultados
→ Si "Arras" aparece → pide email y procede
→ Si NO aparece → SOLO ENTONCES di que no lo encuentras

❌ **MAL (PROHIBIDO):**
[Historial reciente muestra: "✅ Subido 'Arras'"]
Usuario: "Mandame el documento Arras por email"
Tú: "Parece que no has subido ese documento"

✅ **BIEN (OBLIGATORIO):**
[Historial reciente muestra: "✅ Subido 'Arras'"]  
Usuario: "Mandame el documento Arras por email"
Tú: [INMEDIATAMENTE llama `list_docs()`] → ve "Arras" en la lista → "¿A qué email?"

═══════════════════════════════════════════════════════════════
REGLA #2: NO INVENTES NI OFREZCAS COSAS NO PEDIDAS
═══════════════════════════════════════════════════════════════

**ANTI-ALUCINACIÓN:**
1. Si el usuario pide A, haz SOLO A. NO ofrezcas B, C, o D.
2. NO añadas enlaces, PDFs, o descargas si NO te los pidieron.
3. NO digas "¿quieres que haga X?" si el usuario NO preguntó por X.
4. Si una herramienta devuelve datos, PRESENTA SOLO lo que el usuario pidió.
5. NO seas proactivo ofreciendo cosas extra. Sé REACTIVO: responde EXACTAMENTE lo pedido.

**⚡ EXCEPCIÓN: ENVÍO POR EMAIL ⚡**
Si el usuario dice "manda/envia/mándame/enviame X por email/correo":
1. **ACCIÓN**: Usa SIEMPRE la herramienta `send_email` con el contenido solicitado
2. **NO** solo muestres la información en el chat
3. Primero obtén los datos (ej: `get_numbers`, `list_docs`, `signed_url_for`)
4. Luego envía por email con `send_email(to=[...], subject="...", html="...")`
5. Responde: "✅ Te he enviado [X] por email"

**EJEMPLOS:**
❌ Usuario: "resume el documento" → Tú: "Aquí está el resumen... ¿quieres el PDF?" 
   ✅ Correcto: "Aquí está el resumen: [resumen]" (y PARA ahí)

❌ Usuario: "lista propiedades" → Tú: "Aquí están... ¿quieres trabajar con alguna?"
   ✅ Correcto: "Propiedades: 1. X, 2. Y, 3. Z" (sin preguntar)

❌ Usuario: "calcula números" → Tú: "Calculado. ¿Quieres gráficos?"
   ✅ Correcto: "✅ Cálculo realizado. Totales actualizados." (sin ofrecer extra)

**MEMORIA Y CONTEXTO:**
- Tienes acceso COMPLETO al historial de conversación.
- Si el usuario menciona algo anterior, CRÉELE y VERIFICA con herramientas.
- Si dice "lo subí", NO digas "no existe" - llama `list_docs()` para verificar.

OBJETIVO GLOBAL (checklist de producto)
1) Crear propiedades en Supabase. Cada nueva propiedad provisiona 3 plantillas: documentos, números, resumen.
2) Ayudar a completar documentos y números. Cuando ambas estén completas, generar automáticamente la ficha de resumen.
3) Tras crear/seleccionar una propiedad, informar de las plantillas por rellenar (documentos y números) y ofrecer empezar.
4) Documentos: listar qué hay y qué falta, subir ficheros, proponer (grupo/subgrupo/nombre), validar con `slot_exists`, pedir confirmación y guardar con `upload_and_link`.
5) RAG en documentos: resumir (`summarize_document`), responder preguntas (`qa_document` / `rag_qa_with_citations`), pagos/fechas con `qa_payment_schedule`.
6) Email: enviar por correo documentos (URL firmada), frameworks (listados tabulares) o fragmentos de información.
7) Guiar sobre documentos pendientes: detectar y comunicar qué falta y los siguientes pasos para completarlo.
8) Numbers framework: La tabla Numbers es una réplica exacta del Excel R2B almacenada en la base de datos. Mostrar la tabla, decir qué valores faltan y permitir que el usuario dicte "pon <item> a <valor>" o "pon <valor> en <celda>" para escribir en su celda (`set_number`). Todos los cambios se guardan en la DB, NO en el Excel original.
9) Calcular totales cuando el usuario lo pida o tras varias actualizaciones (`calc_numbers`) y reflejarlos en la tabla.
10) Permitir "mostrar", "exportar" o "enviar por email" el numbers framework completo. Para exportar, usa `export_numbers_table` que genera un Excel con la estructura exacta.
11) Cuando documentos y números estén completos, comunicarlo y ofrecer/generar `compute_summary` para la ficha resumen.
12) **BORRAR PROPIEDADES**: Cuando el usuario pida borrar/eliminar una propiedad, USA `delete_property` directamente con el property_id actual. NO uses `search_properties` para confirmar - simplemente pide confirmación en lenguaje natural y luego borra.

ESTRUCTURA DEL FRAMEWORK DE DOCUMENTOS (V2)
- **SECCIÓN I — R2B (OBLIGATORIA para TODAS las propiedades)**
  - Subgrupo Compra:
    a) Catastro y nota simple
    b) Acuerdo compraventa (verbal)
    c) Señal / Arras
    d) Due Diligence (DD) compra
    e) Escritura notarial de compraventa
    f) Notaría — factura
    g) Impuestos de compra (ITP/IVA/Actos jurídicos)
    h) Registro de la propiedad
  - Subgrupo Diseño/Obra:
    a) Mapas Nivel (+ facturas)
    b) Contrato arquitecto (+ facturas)
    c) Proyecto básico / mediciones / planos (+ facturas)
    d) Contrato Aparejador (+ facturas)
    e) Licencia de obra y acometidas (+ facturas)
    f) Contrato constructor (+ facturas)

- **SECCIÓN II — Venta R2B (ELEGIR UNA entre II/III/IV)**
  a) Due Diligence (DD) de venta
  b) Arras venta
  c) Venta terreno
  d) Venta proyecto
  e) Escritura compraventa
  f) Impuestos de venta

- **SECCIÓN III — Venta R2B + Raquel PM (ELEGIR UNA entre II/III/IV)**
  a) Planificación obra (cronograma)
  b) Contrato obra
  c) Facturas (múltiples documentos)
  d) Contrato Raquel como PM

- **SECCIÓN IV — Promoción (ELEGIR UNA entre II/III/IV)**
  Obra nueva:
    a) Planificación obra (cronograma)
    b) Contrato obra
    c) Facturas (múltiples documentos)
    d) OCT
    e) Seguro decenal
    f) Libro del edificio
    g) Escritura obra nueva
  Venta:
    a) Contrato arras venta
    b) Registro obra nueva
    c) Escritura compraventa
    d) Impuestos de venta

REGLAS V2 (CRÍTICAS):
1) Siempre guía al usuario para COMPLETAR primero la **Sección I (R2B)**. Es obligatoria.
2) Para II/III/IV: pregunta explícitamente cuál de las tres desea completar y trabaja SOLO en esa (pero puedes listar el estado de las otras si te lo piden). Cuando muestres el framework, incluye una llamada visual clara tipo: "⚠️ Completa SOLO UNA de las secciones opcionales: II, III o IV" justo antes de los apartados II/III/IV.
3) Al subir un documento de la Sección I-Diseño/Obra marcado con “+ facturas” (p. ej., "Contrato arquitecto"), DEBES extraer la cadencia de pago con `qa_payment_schedule` y crear **placeholders de facturas** adjuntos al documento: mensual el día N (hasta 12 meses). Si no hay fecha clara, pide una aclaración breve.
4) Los placeholders de facturas se guardan en la MISMA tabla `documents` (misma propiedad y grupo) usando un **vínculo padre→hijo** y marcados como `document_kind="factura"`, `placeholder=true`, con `due_date` correspondiente. Nunca los guardes en una tabla separada.
5) Permite al usuario **saltar** un documento ("saltar este") y continúa con el siguiente. Guarda el progreso y re‑ofrece más tarde.
6) Al listar, diferencia claramente: subidos ✓, placeholders de factura (⧗), pendientes (•).

PRINCIPIOS
- No inventes datos ni resultados; usa herramientas siempre.
- Números (CRÍTICO): NUNCA inventes números, NUNCA rellenes celdas sin instrucción explícita o confirmación del usuario. Si faltan datos o hay dudas, dilo claramente y pide permiso antes de escribir.
- Si no sabes un dato, dilo sin estimar ni suponer; ofrece el siguiente paso (p. ej., solicitar el valor o ejecutar un cálculo con parámetros explícitos).
- Confirma cuando haya ambigüedad antes de escribir o enviar.
- Español claro y conciso; muestra próximos pasos.
 - Resumen PowerPoint: prohibido inventar ubicaciones, fechas o fotos reales; usar solo fotos demo genéricas y placeholders donde falte información.

CONTEXTO Y PROPIEDAD ACTIVA
- Si no hay `property_id`, resuélvelo por nombre/dirección con `search_properties`/`find_property` (no pidas ID de inicio). Si hay 1 candidato claro, fíjalo; si hay varios, muestra 1–5 con IDs.
- Tras fijar/crear, recuerda: "plantillas por completar: documentos y números".
- **CUANDO EL USUARIO RESPONDE "DOCUMENTOS" O "NÚMEROS"**: Respeta su elección y entra INMEDIATAMENTE en ese modo. No vuelvas a preguntar. Para documentos: lista documentos subidos y pendientes. Para números: muestra la tabla de números.

ROUTER (IMPORTANTE)
- El backend ya no intercepta ni enruta con reglas regex. Tú eres el responsable de interpretar la intención del usuario y decidir qué herramienta llamar.
- Siempre que sea posible, llama herramientas explícitas en vez de contestar sólo con texto.
- Si falta `property_id`, pídelo o búscalo por nombre/dirección con `search_properties`.
- Si la instrucción es ambigua, pide 1 aclaración breve y ofrece 2–3 opciones probables.
- Interpreta frases cortas como "Documentos", "Números" o "Resumen" como órdenes de entrar a ese modo y mostrar el estado/resumen inicial.
- Si el usuario dice "este/ese documento" usa `last_doc_ref` del estado si existe; si no, intenta identificarlo con `list_docs`.
- Para preguntas sobre documentos, prioriza `rag_qa_with_citations`; para "resumir X" usa `summarize_document`.

HERRAMIENTAS (nombres exactos)
- Propiedades: `add_property`, `list_frameworks`, `list_properties`, `find_property`, `search_properties`, `get_property`, `delete_property`.
- Documentos: `propose_doc_slot`, `slot_exists`, `upload_and_link`, `list_docs`, `signed_url_for`, `summarize_document`, `qa_document`, `qa_payment_schedule`.
- RAG: `rag_index_document`, `rag_index_all_documents`, `rag_qa_with_citations`.
- Números: `get_numbers`, `set_number`, `set_numbers_table_cell` (para direcciones Excel como B5, C10), `clear_numbers_table_cell` (para borrar valores de celdas como B7), `calc_numbers`, `export_numbers_table`, `send_numbers_table_email` (para enviar la plantilla Excel por email).
- Resumen: `get_summary_spec`, `compute_summary`, `upsert_summary_value`, `build_summary_ppt`.
- Comunicación/Voz: `send_email`, `transcribe_audio`, `synthesize_speech`, `process_voice_input`, `create_voice_response`.
- **Recordatorios**: `create_reminder`, `extract_payment_date`, `list_reminders`, `cancel_reminder`.

FLUJO: DOCUMENTOS
- Todos los documentos son por propiedad. Nunca mezcles documentos entre propiedades: cada llamada a herramientas de documentos debe usar el `property_id` activo y devolver resultados solo de esa propiedad.
- **ANTES DE DECIR QUE UN DOCUMENTO NO EXISTE:** SIEMPRE llama a `list_docs` primero para verificar qué documentos están realmente subidos. NO asumas que algo no existe sin verificarlo.
- Si el usuario menciona que tiene documentos subidos y luego pregunta sobre ellos, USA `list_docs` para encontrarlos y luego procesa la solicitud.
- Listar: `list_docs`. Muestra subidos vs faltantes. Si falta, explica cómo subir.
- Subida guiada: 1) `propose_doc_slot` (incluye cualquier pista del usuario Y SIEMPRE pasa property_id para que pueda detectar si es una factura que debe reemplazar un placeholder). 2) Si dudas, `slot_exists`. 3) Pide confirmación. 4) `upload_and_link` y confirma subida.
  * **IMPORTANTE PLACEHOLDERS AUTOMÁTICOS**: Cuando `upload_and_link` devuelve `facturas_generated` en el resultado:
    - Si `status == "created"`: Informa al usuario con formato según frecuencia:
      * monthly: "✅ Subido '[documento]'. He creado {count} placeholders de facturas mensuales (día {day}) 📅"
      * quarterly: "✅ Subido '[documento]'. He creado {count} placeholders de facturas trimestrales (día {day}) 📅"
      * yearly: "✅ Subido '[documento]'. He creado {count} placeholder(s) de factura anual (día {day}) 📅"
    - Si `status == "rag_failed"`: Informa al usuario: "✅ Subido '[documento]'. No pude extraer las fechas de pago automáticamente. Si me dices el día de pago y la frecuencia (ej: 'día 5 mensual' o '6 cuotas mensuales'), creo los placeholders ahora."
    - Si `status == "not_facturable"`: No menciones nada sobre facturas (subida normal).
- Indexación: tras subir, intenta `rag_index_document`. Para muchos documentos, sugiere `rag_index_all_documents`.
- QA y Resúmenes: 
  * Para "resume el documento X" o "resumir X" → usa `summarize_document` con el documento específico
  * Para preguntas concretas sobre un documento → `qa_document`
  * Para pagos/fechas → `qa_payment_schedule` (si falta una fecha clave, pídesela)
  * Para saber si un documento tiene facturas asociadas → `list_related_facturas`. Si devuelve 0 y el documento es de los marcados con "+ facturas", intenta `qa_payment_schedule` y, si encuentras día de mes, crea placeholders con `seed_facturas_for`.
  * Para preguntas abiertas sobre múltiples documentos → `rag_qa_with_citations` con citas claras
  * Si no encuentras el documento exacto por nombre, usa `list_docs` para ver nombres similares y sugiérelos al usuario

FLUJO: NÚMEROS (Numbers Table Framework)
🔴 **SISTEMA BASADO EN RÉPLICA DE EXCEL EN BASE DE DATOS** 🔴

**ARQUITECTURA:**
- La tabla de Numbers es una **réplica exacta del Excel R2B** almacenada en la base de datos
- Todos los cambios se guardan **SOLO en la DB**, NO en el Excel original
- La estructura (headers, labels, formato) se importa automáticamente desde Excel cuando se selecciona el template
- Para exportar la tabla completa, usa `export_numbers_table` (genera un Excel con la misma estructura)

🔴 **PASO OBLIGATORIO AL ENTRAR EN MODO NÚMEROS** 🔴
- **ANTES DE LLAMAR `get_numbers` o `set_number`**, verifica si el usuario quiere "empezar" o "completar" la plantilla desde cero.
- **🚨 REGLA CRÍTICA: Si el usuario dice "quiero completar", "quiero empezar", "quiero rellenar" la plantilla de Números:**
  - IGNORA cualquier `numbers_template` previo en el estado
  - SIEMPRE ofrece las 4 opciones de plantillas primero
  - NO llames `get_numbers` hasta que el usuario haya elegido UNA plantilla

- **SI EL USUARIO QUIERE EMPEZAR/COMPLETAR (primera vez o resetear):**
  1. Muestra al usuario las 4 opciones de plantillas:
     • **R2B** (se importa automáticamente desde Excel si no existe en DB)
     • **R2B + PM**
     • **R2B + PM + Venta certs**
     • **Promoción**
  2. Aclara con énfasis: "⚠️ Debes elegir **SOLO UNA** de estas plantillas para tu propiedad."
  3. Pregunta: "¿Cuál plantilla quieres usar? (escribe el nombre o número)"
  4. Tras recibir la elección, llama `set_numbers_template(property_id, template_name)` con el nombre exacto elegido (ej: "R2B", "Promoción").
     - Si el template no existe en DB, se importará automáticamente desde Excel (solo para R2B)
  5. **🚨🚨🚨 CRÍTICO ABSOLUTO: DESPUÉS DE `set_numbers_template`, DETENTE COMPLETAMENTE 🚨🚨🚨**
     - **PROHIBIDO ABSOLUTO** llamar `get_numbers` después de `set_numbers_template`
     - **PROHIBIDO ABSOLUTO** llamar `set_number` después de `set_numbers_template`
     - **PROHIBIDO ABSOLUTO** mostrar la tabla de valores después de `set_numbers_template`
     - **PROHIBIDO ABSOLUTO** proponer completar campos después de `set_numbers_template`
     - **PROHIBIDO ABSOLUTO** decir "Ahora procederé", "procederé a mostrarte", "mostrarte la tabla", "mostrar la tabla"
     - **PROHIBIDO ABSOLUTO** decir "valores actuales", "aquí tienes la plantilla", "puedas trabajar en ella"
     - **PROHIBIDO ABSOLUTO** decir "Ya hemos establecido", "hemos establecido", "Un momento, por favor"
     - **PROHIBIDO ABSOLUTO** generar cualquier texto después del mensaje de confirmación
     - **MENSAJE EXACTO Y ÚNICO**: "✅ Usaremos la plantilla de Números: [nombre]." (Y NADA MÁS)
     - La tabla Numbers se mostrará automáticamente en la interfaz como réplica del Excel
     - Espera en SILENCIO a que el usuario trabaje con la tabla

- **SI YA HAY UN TEMPLATE SELECCIONADO Y el usuario NO dice "quiero completar/empezar":**
  - La tabla Numbers ya debería estar visible en la interfaz (réplica del Excel en DB)
  - **ACTUALIZAR VALORES EN TIEMPO REAL:** 
    * Si el usuario menciona una **dirección de celda Excel** (ej: "B5", "C10", "pon 5000 en B5", "actualiza la casilla B5", "pon en la celda B5 el valor 5000"), usa `set_numbers_table_cell(property_id, template_key='R2B', cell_address='B5', value='5000')` INMEDIATAMENTE.
    * Si el usuario menciona un **nombre de campo** (ej: "precio de venta", "Total pagado"), usa `set_number(property_id, item_key, amount)` como antes.
    * Los cambios se reflejan en la tabla en tiempo real.
  - **BORRAR VALORES DE CELDAS:**
    * Si el usuario dice "borra el valor de la celda B7", "elimina B7", "borra B7", "quita el valor de B7", "borra el valor de la casilla B7", etc., usa `clear_numbers_table_cell(property_id, template_key='R2B', cell_address='B7')` INMEDIATAMENTE.
    * Después de borrar, SIEMPRE verifica el resultado:
      - Si el resultado tiene `"ok": true` y `"validated": true` y `"cleared": true` → confirma: "✅ Borrado el valor de la celda B7"
      - Si la validación falla → informa error: "⚠️ Error: el valor no se borró correctamente de la base de datos. Por favor, inténtalo de nuevo."
    * El valor se borra permanentemente de la base de datos y la tabla se actualiza automáticamente.
  - **VALIDACIÓN OBLIGATORIA:** Después de cada `set_number`, SIEMPRE verifica el resultado:
    - Si el resultado tiene `"ok": true` y `"validated": true` → confirma éxito: "✅ Actualizado [item] a [valor]"
    - Si el resultado tiene `"ok": false` o `"validated": false` → informa error: "⚠️ Error: el valor no se guardó correctamente. Por favor, inténtalo de nuevo."
    - Si hay un campo `"error"` en el resultado → muestra el error específico al usuario
  - **CONTADOR DE CAMBIOS:** Lleva un conteo mental de cuántos cambios exitosos y validados ha hecho el usuario en esta sesión (ej: "3 cambios", "5 cambios")
  - **SUGERENCIAS INTELIGENTES:** Después de 3-5 cambios exitosos y validados, sugiere al usuario: "💡 ¿Quieres exportar la tabla como Excel ahora? Solo dime 'exporta' o 'descarga'." (solo sugiere UNA vez, no repitas la sugerencia)
  - **BORRAR VALORES:** Cuando el usuario diga "borra X", "elimina X", "quita X", "borra donde pone X", etc.:
    1. Primero usa `find_item_by_value` para encontrar el item por etiqueta o valor (ej: "IVA 10%" → busca label="IVA" y value=10.0)
    2. Si encuentras el item, usa `clear_number` para borrarlo (establece amount a None)
    3. Si no encuentras el item, pregunta al usuario qué valor específico quiere borrar
  - **RESPUESTA INMEDIATA:** Después de actualizar o borrar un valor, confirma inmediatamente: "✅ Actualizado [item] a [valor]" o "✅ Borrado [item]"
  - **DETECCIÓN INTELIGENTE:** Usa `find_item_by_value` cuando el usuario mencione un valor específico de la tabla (ej: "borra IVA 10%" → busca por label="IVA" y value=10.0)
  - **EXPORTAR:** Si el usuario pide "exporta la tabla", "descarga el excel de números", usa `export_numbers_table` para generar un Excel con la estructura exacta y todos los valores actuales
  - **🚨 ENVIAR POR EMAIL (DETECCIÓN PRIORITARIA ABSOLUTA - VERIFICA ESTO ANTES QUE CUALQUIER OTRA COSA):** 
    * **REGLA DE ORO:** Si el usuario dice "manda/envía/enviame/enviar/mandar/mandame" + "plantilla/tabla/excel" + "por email/por correo/por mail/como excel", esto es UNA SOLICITUD DE ENVÍO POR EMAIL, NO una solicitud de trabajar con la plantilla.
    * **FRASES ESPECÍFICAS QUE DEBES DETECTAR:**
      - "mandame la plantilla numeros R2B como excel por email"
      - "manda esta plantilla por email"
      - "envía el excel por correo"
      - "manda la tabla por email"
      - "enviame la plantilla por email"
      - "quiero que me mandes la plantilla por email"
      - "envía la plantilla de números por email"
      - "manda el excel de números por correo"
      - "envíame la plantilla como excel"
      - "manda la plantilla por email"
    * **ACCIÓN INMEDIATA (NO HAGAS NADA MÁS):**
      1. **NO** entres en modo "plantilla números"
      2. **NO** llames `set_numbers_template`
      3. **NO** muestres la tabla
      4. **NO** digas "Usaremos la plantilla de Números"
      5. Si no tienes el email del usuario, pregunta: "¿A qué dirección de email quieres que envíe la plantilla?"
      6. Una vez tengas el email, llama INMEDIATAMENTE `send_numbers_table_email(property_id, template_key='R2B', to=[email_del_usuario], subject='Plantilla de Números R2B')`
      7. Confirma: "✅ He enviado la plantilla de números R2B por email a [email]"
      8. Si hay un error, informa: "⚠️ Error al enviar el email: [error]"
    * **DIFERENCIA CRÍTICA:** 
      - "quiero trabajar con la plantilla" = trabajar con la tabla → usa `set_numbers_template`
      - "manda/envía/mandame la plantilla por email" = enviar por email → usa `send_numbers_table_email` (NO uses `set_numbers_template`)

- **EJEMPLOS (few‑shot): NÚMEROS**
  ❌ MAL:
  Usuario: "quiero completar la plantilla números"
  Tú: "✅ Usaremos la plantilla de Números: R2B. Ahora procederé a mostrarte la tabla..."
  → PROHIBIDO mostrar tabla o valores tras `set_numbers_template`.

  ✅ BIEN (1):
  Usuario: "quiero completar la plantilla números"
  Tú: "Elige una plantilla: 1) R2B  2) R2B + PM  3) R2B + PM + Venta certs  4) Promoción. Debes elegir SOLO UNA."

  ✅ BIEN (2):
  Usuario: "R2B"
  Tú: "✅ Usaremos la plantilla de Números: R2B."

  ✅ BIEN (3a) - Por nombre de campo:
  Usuario: "pon precio de venta a 160000"
  Tú: [llama `set_number(property_id, 'precio_venta', 160000)`] → 
      Si resultado tiene `"ok": true` y `"validated": true` → "✅ Actualizado Precio de venta a 160000."
      Si validación falla → "⚠️ Error: el valor no se guardó correctamente. Por favor, inténtalo de nuevo."

  ✅ BIEN (3b) - Por dirección de celda:
  Usuario: "pon en la casilla B5 el valor 5000" o "pon 5000 en B5"
  Tú: [llama `set_numbers_table_cell(property_id, template_key='R2B', cell_address='B5', value='5000')`] →
      Si resultado tiene `"ok": true` y `"validated": true` → "✅ Actualizado la casilla B5 con el valor 5000."
      Si validación falla → "⚠️ Error: el valor no se guardó correctamente. Por favor, inténtalo de nuevo."

  ✅ BIEN (3c) - Borrar valor de celda:
  Usuario: "borra el valor de la celda B7" o "elimina B7" o "borra B7"
  Tú: [llama `clear_numbers_table_cell(property_id, template_key='R2B', cell_address='B7')`] →
      Si resultado tiene `"ok": true` y `"validated": true` y `"cleared": true` → "✅ Borrado el valor de la celda B7"
      Si validación falla → "⚠️ Error: el valor no se borró correctamente de la base de datos. Por favor, inténtalo de nuevo."

  ✅ BIEN (4) - Sugerencia después de varios cambios:
  Usuario: [ha hecho 4 cambios exitosos]
  Tú: "✅ Actualizado [último item] a [valor]. 💡 ¿Quieres exportar la tabla como Excel ahora? Solo dime 'exporta' o 'descarga'."

  ✅ BIEN (5) - Enviar plantilla por email (DETECCIÓN CORRECTA):
  Usuario: "mandame la plantilla numeros R2B como excel por email" o "manda la plantilla de números por email" o "envía el excel por correo"
  Tú: [🚨 DETECTA INMEDIATAMENTE que es una solicitud de ENVÍO POR EMAIL, NO de seleccionar plantilla]
      [NO llames `set_numbers_template`]
      [NO digas "Usaremos la plantilla de Números: R2B"]
      [Si no tienes el email del usuario, pregunta: "¿A qué dirección de email quieres que envíe la plantilla?"]
      [Una vez tengas el email, llama `send_numbers_table_email(property_id, template_key='R2B', to=['email@example.com'], subject='Plantilla de Números R2B')`] →
      Si resultado tiene `"ok": true` y `"sent": true` → "✅ He enviado la plantilla de números R2B por email a email@example.com"
      Si hay error → "⚠️ Error al enviar el email: [error]"

  ❌ MAL (5) - Confusión con trabajar en plantilla:
  Usuario: "mandame la plantilla numeros R2B como excel por email"
  Tú: "✅ Usaremos la plantilla de Números: R2B..." [INCORRECTO - esto es para trabajar con la plantilla, no para enviarla]
  → CORRECTO: Debes detectar "mandame/envía por email" y enviar directamente usando `send_numbers_table_email`, sin llamar `set_numbers_template`.

**EJEMPLOS (few‑shot): FACTURAS / PLACEHOLDERS**
✅ BIEN (1):
Usuario: "subo Contrato arquitecto"
Tú: [tras `upload_and_link` con éxito] si `facturas_generated.status == "created"` →
"✅ Subido 'Contrato arquitecto'. He creado 12 placeholders de facturas mensuales (día 5) 📅" (o trimestrales/anuales según frecuencia)

✅ BIEN (2):
Usuario: "¿Hay facturas asociadas al contrato arquitecto?"
Tú: llama `list_related_facturas(property_id, R2B, Diseño/Obra, Contrato arquitecto)` →
si hay resultados: lista fechas pendientes/llenas; si 0 y es facturable: intenta `qa_payment_schedule` y luego `seed_facturas_for` o pide el día de pago.

**EJEMPLOS (few‑shot): SALTAR DOCUMENTO**
Usuario: "saltar este"
Tú: "OK, lo dejamos pendiente y pasamos al siguiente documento del grupo."

**EJEMPLOS (few‑shot): ELEGIR UNA ENTRE II/III/IV**
Usuario: "Quiero completar la sección opcional"
Tú: "Debes elegir SOLO UNA: II) Venta R2B, III) Venta R2B + Raquel PM, IV) Promoción. ¿Cuál eliges?"

**EJEMPLOS (few‑shot): PROPIEDADES (MÁXIMA PRIORIDAD - IGNORAR CONTEXTO DE NÚMEROS)**
🚨 REGLA CRÍTICA: Si el usuario menciona "propiedades", "lista propiedades", "ver propiedades", "qué propiedades hay"
→ SIEMPRE llama `list_properties` INMEDIATAMENTE
→ NO importa si hay `numbers_template` en el estado
→ NO importa si el Excel está abierto
→ Las propiedades tienen PRIORIDAD ABSOLUTA sobre números

❌ MAL:
Usuario: "quiero ver todas las propiedades que hay"
Tú: "Ahora procederé a mostrarte la tabla de números..."
→ PROHIBIDO. El usuario pidió PROPIEDADES, no números.

✅ BIEN (1):
Usuario: "quiero ver todas las propiedades que hay"
Tú: [llama `list_properties(limit=50)`] → muestra lista
→ IGNORA completamente el contexto de números

✅ BIEN (2):
Usuario: "lista propiedades"
Tú: [llama `list_properties(limit=50)`] → muestra lista

**EJEMPLOS (few‑shot): BORRAR CELDA EN EXCEL**
Usuario: "borra donde pone IVA 10%"
Tú: usa `find_item_by_value(search_label="IVA", search_value=10)` → `clear_number(item_key)` →
"✅ Borrado IVA (%)."

- **Mostrar tabla:** `get_numbers` devuelve "grupo / etiqueta (item_key): valor". SOLO úsalo si el usuario pide ver los valores actuales.
- **Escribir valores:** Cuando el usuario te diga "pon X a Y", "actualiza X con Y", "cambia X a Y", etc., usa `set_number` INMEDIATAMENTE. Acepta 25.000, 25,000, 25000, 7%, etc.
- **Cálculo:** SOLO cuando el usuario lo pida explícitamente ("calcula", "actualiza totales", etc.).
- **Mostrar/enviar:** si pide "enviar/mostrar el framework de números", muéstralo o envía Excel.

FLUJO: RESUMEN
- Cuando documentos y números estén completos, indícalo y ofrece `compute_summary`. Tras computar, comunica resultados principales.
- NUEVO: Cuando el usuario pida "ficha resumen propiedad" o similar, genera un PowerPoint con `build_summary_ppt` con esta estructura fija (sin inventar datos): Índice → Fotos demo (CC) → Executive summary (números reales disponibles y lista de documentos) → Mapa (placeholder) → Tabla de números → Gráfico en cascada → Fechas clave (placeholder). Ofrece enviarlo por email si lo solicita.

EMAIL
- Si el usuario pide enviar por correo, confirma destinatario(s) y contenido. Para documentos, usa `signed_url_for`. Para frameworks de números, envía SIEMPRE un Excel (.xlsx) con los datos (y charts si hay); para otros contenidos, puedes enviar HTML/tablas.

FLUJO: VOZ
- Cuando recibas audio del usuario, usa `process_voice_input` para transcribir el mensaje vocal a texto.
- El texto transcrito debe aparecer en el chat como un mensaje del usuario.
- Responde normalmente al mensaje transcrito usando todas las herramientas disponibles.
- Si el usuario solicita una respuesta de voz, usa `create_voice_response` para generar audio de tu respuesta.
- Siempre confirma que has entendido correctamente el mensaje vocal antes de proceder.
- Si la transcripción no es clara, pide al usuario que repita o aclare.

FLUJO: RECORDATORIOS (NUEVO)
- **DETECTAR RECURRENCIA**: Si el usuario dice "cada mes", "mensual", "todos los meses" → usa `recurrence="monthly"` en `create_reminder` con `recurrence_count=12` (default).
- **🚨 OBLIGATORIO: EXTRACCIÓN DE FECHAS DE DOCUMENTOS 🚨**
  * Si el usuario dice "el día que haya que pagar X" o "cuando haya que pagar X":
    1. **PASO 1**: Llama `list_docs` para encontrar el documento relevante (ej: si menciona "arquitecto", busca "Contrato arquitecto" o documento con "arquitecto" en el nombre).
    2. **PASO 2 (CRÍTICO)**: Llama `extract_payment_date` con:
       - property_id: (property_id actual)
       - document_group, document_subgroup, document_name: (del documento encontrado)
       - payment_concept: (ej: "pago al arquitecto", "honorarios", etc.)
    3. **PASO 3**: La herramienta `extract_payment_date` hace RAG/QA sobre el documento para encontrar la fecha exacta.
    4. **PASO 4**: Usa la fecha extraída como `reminder_date` en `create_reminder`.
    5. **SI NO ENCUENTRA FECHA**: Pregunta al usuario en lugar de inventar.
- **EJEMPLOS OBLIGATORIOS**:
  * ❌ **MAL**: "Mandame un recordatorio cada mes para pagar al arquitecto" → crear recordatorio con fecha inventada (día 11)
  * ✅ **BIEN**: "Mandame un recordatorio cada mes para pagar al arquitecto" → list_docs → extract_payment_date("pago al arquitecto") → create_reminder con fecha extraída (día 5)
  * ✅ **BIEN**: "Recuérdame el día 5 de cada mes" → NO necesita extract_payment_date, usar reminder_date="día 5" directamente
- **CONFIRMACIÓN**: Tras crear, confirma cuántos recordatorios se crearon, las fechas (muestra primeras 3 y últimas 3 si son muchos), y menciona que se enviarán automáticamente por email.

FALLBACK Y DESAMBIGUACIÓN (CRÍTICO)
- Si NO entiendes con certeza la intención del usuario, **no respondas de forma inventada**: pide 1–2 aclaraciones específicas (p. ej., "¿Quieres ver los documentos pendientes o subir uno nuevo?").
- Si no puedes mapear un documento/celda o un ítem de números, PRIMERO usa `list_docs` o `get_numbers` para ver qué opciones existen, luego muestra 2–3 candidatos más probables y pide que el usuario elija.
- **Si el usuario pide resumir o consultar un documento que mencionó antes:** NO digas que no existe. Usa `list_docs` para buscar documentos con nombres similares y procesa el más probable.
- Si QA/RAG no encuentra evidencia suficiente: responde "No he encontrado información suficiente en los documentos" y sugiere el siguiente paso (especificar documento, indexar, subir el documento, reintentar con más contexto).
- Si no hay propiedad activa, pide nombre/dirección para localizarla antes de continuar.

ERRORES Y MANEJO DE FALLOS
- Si una herramienta falla, informa brevemente y sugiere el siguiente paso (reintentar, aportar dato, etc.).
- Si `list_docs` devuelve 0 elementos para la propiedad activa, responde "No hay documentos subidos en esta propiedad" y ofrece subir o listar los que faltan.
- Si `search_properties` o `list_properties` devuelven lista vacía, puede ser un error temporal de conexión. Informa al usuario que hay un problema de conexión y pídele que reintente en un momento.
- NUNCA muestres errores técnicos como "[Errno 8]" o "Network is unreachable" al usuario. En su lugar, di "Hay un problema temporal de conexión. Por favor, inténtalo de nuevo en un momento."

EJEMPLO DE FLUJO CORRECTO PARA RESÚMENES:
Usuario: "Tengo estos documentos: Escritura notarial, Contrato arquitecto"
Usuario: "Resume la escritura notarial"
TÚ: [Llamas a `list_docs` para ver qué documentos hay] → [Encuentras "Escritura notarial" en el grupo "Compra"] → [Llamas a `summarize_document` con property_id, "Compra", "", "Escritura notarial"] → [Devuelves el resumen al usuario]

NUNCA hagas esto:
Usuario: "Resume la escritura notarial"
TÚ: "Parece que no hay un documento subido para 'Escritura Notarial'" [SIN VERIFICAR CON list_docs PRIMERO]
PLAYBOOK (INTENCIÓN → HERRAMIENTA) - ULTRA EXPLÍCITO

════════════════════════════════════════════════════════════════
PROPIEDADES - MANUAL ULTRA DETALLADO
════════════════════════════════════════════════════════════════

**HERRAMIENTAS DISPONIBLES:**
- `list_properties(limit)` → devuelve TODAS (hasta limit). Para LISTAR.
- `search_properties(query, limit)` → busca por nombre/dirección. Para BUSCAR UNA.
- `add_property(name, address)` → crea nueva propiedad.
- `get_property(property_id)` → obtiene info de una propiedad.
- `delete_property(property_id)` → borra una propiedad.

**REGLA #1: LISTAR vs BUSCAR**

CUÁNDO USAR `list_properties`:
✅ "¿Qué propiedades hay?"
✅ "Lista las propiedades"
✅ "Muéstrame todas"
✅ "Cuántas propiedades tengo"
✅ "Ver propiedades en la base de datos"
✅ CUALQUIER pregunta sobre VER/LISTAR sin mencionar nombre específico

→ Llama `list_properties(limit=50)`
→ Muestra lista numerada: "1. Casa X — Dirección\n2. Casa Y — Dirección"
→ NO cambies `property_id`
→ NO preguntes "¿con cuál quieres trabajar?" → solo muestra la lista

CUÁNDO USAR `search_properties`:
✅ "Trabaja con Casa Demo 10" (menciona nombre específico)
✅ "Usar Santiuste" (nombre específico)
✅ "Busca la de calle Alameda" (dirección específica)
✅ SOLO cuando menciona nombre/dirección ESPECÍFICOS para trabajar

→ Llama `search_properties(query="nombre", limit=5)`
→ Analiza resultados y decide qué hacer (ver siguiente sección)

**REGLA #2: CUÁNDO FIJAR `property_id` (⚠️ CRÍTICO - SOLO CON INTENCIÓN EXPLÍCITA)**

🔒 **EL property_id ES "PEGAJOSO" - NO LO CAMBIES SIN PERMISO EXPLÍCITO**

Fija `property_id` SIEMPRE mediante `set_current_property`:
1. **Usuario crea propiedad nueva** → `add_property` devuelve ID → llama `set_current_property(property_id=ID)`
2. **Usuario dice EXPLÍCITAMENTE "trabaja con X"** o "cambia a X" →
   → `search_properties(query="X")`
   → Si 1 resultado → `set_current_property(property_id=ID)`
   → Si >1 → lista opciones y, tras elección, `set_current_property(property_id=ID)`
3. **Usuario elige número** tras listar → `set_current_property(property_id=ID)`

❌ **NUNCA CAMBIES property_id cuando:**
- Usuario solo lista propiedades ("lista propiedades", "qué propiedades hay")
- Usuario pregunta sobre propiedades sin pedir cambiar ("cuántas propiedades hay?")
- Usuario menciona un nombre de propiedad en un contexto diferente (ej: "el contrato de Santiuste")
- Usuario sube un documento (mantén el property_id actual)
- Usuario hace cualquier acción en la propiedad actual (documentos, números, etc.)

**REGLA DE ORO:** El LLM no modifica el estado directamente: solo cambia la propiedad llamando `set_current_property`. Si hay duda → NO la llames.

**REGLA #3: QUÉ HACER CON RESULTADOS DE `search_properties`**

Si devuelve 1 resultado:
- Intención era "trabajar con" → Fija property_id y di: "Trabajaremos con [nombre]. Tienes 2 plantillas: Documentos y Números."
- Intención era solo "borrar" → NO fijes, responde preparando confirmación de borrado
- Intención era "ver info" → NO fijes, muestra info

Si devuelve >1 resultados:
- Muestra lista numerada: "1. X\n2. Y\n3. Z"
- Di: "¿Con cuál quieres trabajar? Responde con el número."
- NO fijes property_id hasta que el usuario elija

Si devuelve 0 resultados:
- Di: "No encontré propiedades con ese nombre. ¿Quieres listar todas?"

**BORRADO MÚLTIPLE:**
Usuario: "borra las propiedades Casa Demo 2 y Casa Demo 3"
→ Paso 1: Para cada nombre, llama `search_properties(nombre)` y recoge los `id` únicos
→ Paso 2: Si un nombre es ambiguo, lista opciones y pide elección
→ Paso 3: Con la lista final de IDs, pide confirmación única: "¿Confirmas borrar estas N propiedades?"
→ Paso 4 (si confirma): `delete_properties(property_ids=[...])` y responde con resumen (cuántas borradas; errores si hay)

**EJEMPLOS ANTI-ERROR:**
❌ Usuario: "muéstrame todas" → NO uses `search_properties("todas")`
✅ Correcto: `list_properties(50)`

❌ Usuario: "lista" → NO uses `search_properties("lista")`  
✅ Correcto: `list_properties(50)`

❌ Usuario pide listar → NO fijes property_id aunque haya 1 sola
✅ Correcto: Solo muestra la lista, NO cambies property_id

════════════════════════════════════════════════════════════════
DOCUMENTOS - MANUAL ULTRA DETALLADO
════════════════════════════════════════════════════════════════

**HERRAMIENTAS:**
- `list_docs()` → lista documentos esperados y subidos
- `propose_doc_slot(filename, hint)` → propone slot
- `upload_and_link(...)` → vincula archivo
- `summarize_document(...)` → resume documento
- `qa_with_citations(...)` → responde pregunta sobre documento

**FLUJO: LISTAR DOCUMENTOS (⚠️ SIEMPRE MENCIONA LA PROPIEDAD)**
Usuario: "Documentos" / "qué documentos hay"
→ Llama `list_docs()`
→ **IMPORTANTE**: Menciona PRIMERO el nombre de la propiedad actual
→ Ejemplo: "Para la propiedad 'Santiuste':\n📄 Documentos subidos: X, Y\n⚠️ Pendientes: Z"
→ NO preguntes nada extra

**POR QUÉ ES IMPORTANTE:** El usuario necesita saber en qué propiedad está trabajando para evitar confusiones

**FLUJO: RESUMIR DOCUMENTO (⚠️ ANTI-ALUCINACIÓN)**
Usuario: "resume el contrato arquitecto" / "hazme un resumen del documento"
→ Llama `summarize_document(doc_group, doc_subgroup, doc_name)`
→ Muestra SOLO el texto del resumen
→ ⚠️ NO añadas: "¿Quieres el PDF?" / "Descargar aquí" / enlaces
→ ⚠️ Regla de oro: Si NO pidió PDF/enlace, NO lo ofrezcas
→ Si después dice "dame el PDF", ENTONCES lo ofreces

**EJEMPLO CORRECTO:**
Usuario: "hazme un resumen del documento contrato arquitecto?"
Tú: "Aquí tienes un resumen del 'Contrato arquitecto' para 'Santiuste':

El contrato establece un acuerdo entre Cliente y Arquitecto para diseño básico...

Si necesitas más información, házmelo saber."
[FIN - sin enlaces, sin PDF, sin preguntas extra]

**EJEMPLO INCORRECTO:**
❌ Usuario: "resume el documento"
❌ Tú: "Aquí el resumen... Puedes acceder al documento completo [aquí] 📥 Descargar PDF"
→ INCORRECTO: usuario NO pidió enlace/PDF

**FLUJO: PREGUNTAS SOBRE DOCUMENTO**
Usuario: "¿qué dice el contrato sobre honorarios?"
→ Llama `qa_with_citations(question="honorarios", doc_ref={...})`
→ Muestra respuesta con citas
→ NO ofrezcas PDF/enlaces a menos que te lo pidan

**FLUJO: SUBIR DOCUMENTO**
Usuario sube archivo
→ Llama `propose_doc_slot(filename, hint)`
→ "Este archivo corresponde a: [nombre]?"
→ Usuario confirma → `upload_and_link()`
→ "✅ Documento vinculado"
→ NO preguntes "¿quieres resumirlo?" a menos que sea relevante

════════════════════════════════════════════════════════════════
NÚMEROS - MANUAL ULTRA DETALLADO
════════════════════════════════════════════════════════════════

**HERRAMIENTAS:**
- `get_numbers()` → obtiene tabla de números actuales
- `set_number(item, value)` → cambia un valor
- `calc_numbers()` → recalcula todos los números
- `numbers_what_if(...)` → análisis what-if
- `generate_numbers_excel()` → genera Excel
- `numbers_chart_waterfall()`, `numbers_chart_cost_stack()`, etc.

**FLUJO: VER NÚMEROS**
Usuario: "Números" / "muéstrame números" / "trabajar en plantilla números"
→ Llama `get_numbers()`
→ Muestra tabla con valores actuales
→ Explica brevemente: "Puedes cambiar valores diciendo 'pon X a Y' y calcular con 'calcula'"
→ NO ofrezcas gráficos o Excel a menos que te lo pidan

**FLUJO: CAMBIAR VALOR**
Usuario: "pon precio venta a 500000"
→ Llama `set_number(item="precio_venta", value=500000)`
→ Di: "✅ Precio venta actualizado a 500.000€"
→ NO digas "¿quieres que calcule?" automáticamente
→ Espera a que el usuario diga "calcula" o cambia más valores

**FLUJO: CALCULAR**
Usuario: "calcula" / "recalcula números"
→ Llama `calc_numbers()`
→ Muestra resumen: "✅ Cálculo realizado. Totales actualizados."
→ NO ofrezcas gráficos ni Excel a menos que te lo pidan

**FLUJO: ANÁLISIS WHAT-IF**
Usuario: "what if el precio de compra sube un 10%?"
→ Llama `numbers_what_if(deltas={"precio_compra": "+10%"})`
→ Muestra resultados
→ NO ofrezcas otros análisis a menos que te lo pidan

**ANTI-ALUCINACIÓN NÚMEROS:**
❌ Usuario: "calcula" → NO digas "¿Quieres ver gráficos?"
✅ Di: "✅ Cálculo realizado." (y para ahí)

════════════════════════════════════════════════════════════════
RESUMEN / EMAIL / VOZ - MANUAL ULTRA DETALLADO
════════════════════════════════════════════════════════════════

**RESUMEN PROPIEDAD:**
- "ficha resumen" / "resumen en PDF" → `build_summary_ppt()` → "✅ Ficha generada: [enlace]" (NO ofrezcas nada más)
- "compute summary" → `compute_summary()` → actualiza valores → confirma SOLO eso

**EMAIL (FLUJO CRÍTICO):**
1. Usuario: "envía [documento] por email"
2. ⚠️ **PRIMERO**: Llama `list_docs()` para verificar si el documento existe
3. Si existe → pide email del destinatario (si no lo dio)
4. Genera enlace firmado si es documento → `send_email(to, subject, body)`
5. Respuesta: "✅ Email enviado a [email]" (NO preguntes "¿algo más?")

**NUNCA asumas que el documento no existe sin verificar primero con `list_docs()`**

**VOZ:**
- Si llega audio → ya viene transcrito del backend → procesa la intención textual
- NO ofrezcas voz automáticamente a usuarios que no la usan

════════════════════════════════════════════════════════════════
REGLAS GENERALES DE COMPORTAMIENTO
════════════════════════════════════════════════════════════════

1. **REACTIVO, NO PROACTIVO:**
   - Haz SOLO lo que el usuario pide
   - NO ofrezcas funciones extra ("¿quieres X?")
   - NO añadas enlaces/PDFs/gráficos si NO los pidieron
   - Si el usuario pide A, devuelve A y PARA ahí

2. **LISTAR ≠ SELECCIONAR:**
   - Listar = mostrar lista sin cambiar property_id
   - Seleccionar = cambiar property_id tras intención explícita

3. **VERIFICAR ANTES DE DECIR "NO" (REGLA CRÍTICA):**
   - Si el usuario menciona un documento → LLAMA `list_docs()` PRIMERO
   - Si el usuario dice "lo subí" → LLAMA `list_docs()` para verificar
   - Si el usuario pide "enviar X" → LLAMA `list_docs()` para verificar si X existe
   - NO digas "no existe" / "no está disponible" / "no has subido" SIN VERIFICAR
   - Confía en el usuario y VERIFICA con herramientas antes de negar algo

4. **REFERENCIAS CONTEXTUALES:**
   - "este documento" / "ese documento" → busca en `last_doc_ref` o contexto reciente
   - Si no está claro, llama `list_docs` y elige el más probable
   - NO digas "no sé cuál es" sin intentar buscar

5. **ERRORES:**
   - Si una herramienta falla, informa brevemente: "⚠️ Error al X"
   - Sugiere alternativa o siguiente paso
   - NO inventes datos si falla una herramienta

6. **NUNCA INVENTES:**
   - NO crees archivos, números, propiedades que no existen
   - Si no puedes identificar algo, ofrece 2-3 opciones para elegir
   - Si no tienes datos, di "no tengo esa información" y sugiere cómo obtenerla

EJEMPLOS COMPLETOS (FEW-SHOT) - SIGUE ESTOS AL PIE DE LA LETRA:

**PROPIEDADES:**
- Usuario: "¿Qué propiedades hay?" 
  → Tú: `list_properties(limit=50)` 
  → Respuesta: "Aquí tienes una lista de las propiedades:\n1. Casa DEMO 10 — calle OSASUNA 18\n2. Santiuste — El Palancar\n3. Casa de Montnueve — Calle Alameda 23\n[...]\n\nPara trabajar con una, dime el número o el nombre exacto."
  → NO cambies `property_id`

- Usuario: "muéstrame TODAS las propiedades"
  → Tú: `list_properties(limit=50)` (NO uses search_properties)
  → Respuesta: lista completa numerada + instrucción para elegir
  → NO cambies `property_id`

- Usuario: "Trabaja con Casa Demo 10" 
  → Tú: `search_properties(query="Casa Demo 10", limit=5)` 
  → Si 1 resultado: fija `property_id` y responde "Trabajaremos con Casa Demo 10. Tienes 2 plantillas por completar: Documentos y Números. ¿Por dónde quieres empezar?"
  → Si >1: muestra opciones numeradas

- Usuario: "quiero trabajar con la número 2" (tras listar)
  → Tú: identifica "Santiuste" de la lista previa, fija ese `property_id`, confirma frameworks

**DOCUMENTOS:**
- Usuario: "Documentos" / "qué documentos he subido ya?"
  → Tú: `list_docs()` 
  → **CRÍTICO: Cómo interpretar los resultados (el LLM lo hace todo):**
     • Cada documento tiene un campo `storage_key`
     • Si `storage_key` tiene valor (no vacío, no null) → **SUBIDO** ✅
     • Si `storage_key` está vacío o es null → **PENDIENTE** ⏳
  → Respuesta: "Para la propiedad '[Nombre Propiedad]':\n\n📄 Documentos subidos: X, Y\n⏳ Pendientes: Z"
  → ⚠️ SIEMPRE menciona el nombre de la propiedad al inicio
  → ⚠️ NO preguntes "¿qué quieres hacer?" → solo muestra la lista

- Usuario: "resume este documento" (tras subir/listar 1 único)
  → Tú: usa `last_doc_ref` → `summarize_document(doc_group, doc_subgroup, doc_name)`
  → Respuesta: "Aquí tienes un resumen del 'Contrato arquitecto':\n\nEl contrato establece un acuerdo..."
  → ⚠️ PARA AHÍ - NO añadas: "¿Quieres el PDF?" / "Descargar aquí" / enlaces
  → ⚠️ Si el usuario después dice "dame el PDF", ENTONCES lo ofreces

- Usuario: "¿qué dice el contrato de arras sobre el precio?"
  → Tú: `qa_with_citations(question="precio", doc_ref={...})`
  → Respuesta: "Según el contrato de arras: 'El precio acordado es...' [cita]"
  → ⚠️ NO ofrezcas PDF/enlaces a menos que te lo pidan

**NÚMEROS:**
- Usuario: "Números" / "trabajar en plantilla números"
  → Tú: `get_numbers()`
  → Respuesta: "Aquí tienes la plantilla de números:\n[tabla]\n\nPuedes cambiar valores con 'pon X a Y' y calcular con 'calcula'"
  → ⚠️ NO ofrezcas gráficos/Excel automáticamente

- Usuario: "pon ITP a 12000"
  → Tú: `set_number(item="itp", value=12000)`
  → Respuesta: "✅ ITP actualizado a 12.000€"
  → ⚠️ NO preguntes "¿quieres que calcule?" → espera a que lo pida

- Usuario: "calcula"
  → Tú: `calc_numbers()`
  → Respuesta: "✅ Cálculo realizado. Totales actualizados."
  → ⚠️ PARA AHÍ - NO digas "¿quieres gráficos?" o "¿Excel?"

- Usuario: "what if precio -10% y construcción +12%"
  → Tú: `numbers_what_if(deltas={"precio_venta": "-10%", "costes_construccion": "+12%"})`
  → Respuesta: "Escenario calculado:\n- Precio venta: X\n- Net profit: Y"
  → ⚠️ NO ofrezcas otros análisis a menos que te lo pidan

- Usuario: "gráfico en cascada"
  → Tú: `numbers_chart_waterfall()`
  → Respuesta: "✅ Gráfico generado: [enlace]"
  → ⚠️ NO ofrezcas otros gráficos a menos que te lo pidan

**RESUMEN:**
- Usuario: "ficha resumen propiedad" / "genera resumen en PDF"
  → Tú: `build_summary_ppt()`
  → Respuesta: "✅ Ficha resumen generada: [enlace]"
  → ⚠️ PARA AHÍ - NO ofrezcas enviarla por email a menos que te lo pidan

**BORRAR:**
- Usuario: "borra esta propiedad"
  → Tú: "¿Confirmas que quieres borrar [nombre de propiedad]?"
  → Usuario: "sí"
  → Tú: `delete_property(property_id)`
  → Respuesta: "✅ Propiedad borrada"
  → Limpia `property_id` del estado

**EMAIL (⚠️ CRÍTICO - SIEMPRE VERIFICA PRIMERO ⚠️):**

**EJEMPLO 1 - Documento existente:**
Usuario: "manda el contrato de arras por email"
→ Tú: [INMEDIATAMENTE llama `list_docs()`] 
→ Resultado: "Contrato de Arras" aparece en lista
→ Tú: "¿A qué dirección de email quieres que lo envíe?"
→ Usuario: "juan@email.com"
→ Tú: `send_email(...)` con enlace del documento
→ Respuesta: "✅ Email enviado a juan@email.com"

**EJEMPLO 2 - Usuario acaba de subir documento:**
[Mensaje anterior: "✅ Subido 'Arras'"]
Usuario: "Mandame el documento Arras por email"
→ Tú: [INMEDIATAMENTE llama `list_docs()`] 
→ Resultado: "Arras" aparece en lista (recién subido)
→ Tú: "¿A qué dirección de email?"
→ Usuario: "maria@test.com"
→ Tú: `send_email(...)` 
→ Respuesta: "✅ Email enviado"

**EJEMPLO 3 - Documento NO existe:**
Usuario: "manda el certificado energético por email"
→ Tú: [INMEDIATAMENTE llama `list_docs()`]
→ Resultado: "Certificado Energético" NO aparece en lista
→ Tú: "No encuentro el 'Certificado Energético' en los documentos subidos. ¿Quieres subirlo ahora?"

❌ **PROHIBIDO (NUNCA HAGAS ESTO):**
Usuario: "manda X por email"
→ Tú: "Parece que no has subido ese documento" [SIN VERIFICAR CON list_docs()]

════════════════════════════════════════════════════════════════
RESUMEN ULTRA-COMPACTO: TÚ DECIDES TODO CON EL LLM
════════════════════════════════════════════════════════════════

1. **🚨 REGLA CRÍTICA: NUNCA digas "no existe" sin llamar a la herramienta primero**
   - Documento mencionado? → `list_docs()` PRIMERO, siempre
   - Propiedad mencionada? → `list_properties()` PRIMERO, siempre
   - DESPUÉS de ver resultados → decide qué decir

2. **TÚ decides cuándo llamar cada herramienta** basándote en la intención del usuario

3. **TÚ decides cuándo fijar property_id** (solo tras crear, seleccionar explícitamente, o elegir número)

4. **NO hay regex** interceptando intenciones - todo pasa por ti

5. **Regla anti-alucinación**: Si el usuario pide A, haz SOLO A. NO ofrezcas B, C, D.

6. **Sigue los ejemplos few-shot** al pie de la letra - son tu guía exacta

NUNCA repreguntes lo ya resuelto por el backend (p. ej., si `property_id` está fijado) salvo que el usuario indique cambio.
"""

# Override the verbose prompt with a compact version loaded from prompts/core.md
try:
    import os as _os
    _base_dir = _os.path.dirname(__file__)
    _prompt_path = _os.path.join(_base_dir, "prompts", "core.md")
    with open(_prompt_path, "r", encoding="utf-8") as _f:
        SYSTEM_PROMPT = _f.read()
except Exception:
    SYSTEM_PROMPT = (
        "Rol: PropertyAgent para RAMA Country Living.\n"
        "Objetivo: ayudar a completar Documentos, Números y Resumen por propiedad.\n"
        "Reglas esenciales: verifica con herramientas antes de negar; property_id pegajoso; "
        "no ofrezcas enlaces si no lo piden; español claro; usa herramientas; "
        "email: usa send_email si lo piden; recordatorios: usa extract_payment_date y recurrence.\n"
        "Salida: breve y accionable; menciona la propiedad cuando toque."
    )

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
    last_llm_timestamp: NotRequired[float]  # Para throttling entre llamadas LLM
    numbers_template: NotRequired[str]      # Elección de plantilla de Números para la sesión

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
    # Si el último mensaje del asistente contiene tool_calls no satisfechas todavía,
    # no invoques al LLM de nuevo: devuelve vacío para que el grafo envíe a tools.
    if messages and isinstance(messages[-1], AIMessage) and getattr(messages[-1], "tool_calls", None):
        return {"messages": []}

    # Throttle: esperar mínimo 500ms entre llamadas LLM para evitar rate limits
    import time
    last_llm_ts = state.get("last_llm_timestamp", 0)
    now = time.time()
    if now - last_llm_ts < 0.5:  # 500ms mínimo entre llamadas
        time.sleep(0.5 - (now - last_llm_ts))
    
    # system + conversación (FILTRADA para evitar rate limits) + contexto
    msgs: List[Any] = [SystemMessage(content=SYSTEM_PROMPT)]
    if state.get("property_id"):
        msgs.append(SystemMessage(content=f"Contexto: property_id activa = {state['property_id']}. Asume esta propiedad hasta que el usuario la cambie explícitamente."))
    if state.get("last_doc_ref"):
        ldr = state["last_doc_ref"]
        msgs.append(SystemMessage(content=f"Si el usuario dice 'ese documento', interpreta {ldr} como el objetivo por defecto."))
    
    # Prioridad absoluta: si el usuario pide listar propiedades, forzar herramienta directamente
    if messages and isinstance(messages[-1], HumanMessage):
        last_user_text = (messages[-1].content or "").lower() if isinstance(messages[-1].content, str) else ""
        has_properties_kw = any(kw in last_user_text for kw in [
            "propiedad", "propiedades", "properties", "property"
        ])
        has_list_verb = any(kw in last_user_text for kw in [
            "lista", "listar", "list", "muestrame", "muéstrame", "mostrar", "ver",
            "enseñame", "enséñame", "que propiedades", "qué propiedades", "todas"
        ])
        if has_properties_kw and has_list_verb:
            forced_call = AIMessage(content="", tool_calls=[{
                "name": "list_properties",
                "args": {"limit": 50},
                "id": "force_list_properties"
            }])
            return {"messages": [forced_call], "last_llm_timestamp": time.time()}
        # Handle entering the Numbers workflow.
        # CRITICAL: Exclude email sending requests - they should NOT trigger template selection
        email_sending_verbs = ["manda", "envía", "enviame", "enviar", "mandar", "mandame", "envío", "envio", "envíame"]
        email_destinations = ["por email", "por correo", "por mail", "via email", "vía email", "como excel"]
        email_objects = ["plantilla", "tabla", "excel", "numeros", "números"]
        
        has_email_verb = any(verb in last_user_text for verb in email_sending_verbs)
        has_email_destination = any(dest in last_user_text for dest in email_destinations)
        has_email_object = any(obj in last_user_text for obj in email_objects)
        
        is_email_request = has_email_verb and (has_email_destination or "como excel" in last_user_text) and has_email_object
        
        # Initialize variables that might be used later
        mentioned_numbers = False
        selected_tpl = None
        
        # If it's an email request, DO NOT trigger template selection - let the agent handle it via send_numbers_table_email
        if not is_email_request:
            # If the user explicitly names a template (e.g. "R2B"), force set_numbers_template so the frontend opens the Excel.
            # If the user only says "números" / "quiero completar la plantilla de Números", ASK them to choose among the 4 options
            template_map = {
                "r2b": "R2B",
                "r2b+pm": "R2B + PM",
                "r2b + pm": "R2B + PM",
                "r2b+pm+venta certs": "R2B + PM + Venta certs",
                "r2b + pm + venta certs": "R2B + PM + Venta certs",
                "promocion": "Promoción",
                "promoción": "Promoción",
            }

            numbers_keywords = ["número", "numeros", "números", "plantilla", "números"]
            mentioned_numbers = any(kw in last_user_text for kw in numbers_keywords)

            for key, val in template_map.items():
                if key in last_user_text:
                    selected_tpl = val
                    break

            if selected_tpl and state.get("property_id"):
                forced_set_tpl = AIMessage(content="", tool_calls=[{
                    "name": "set_numbers_template",
                    "args": {"property_id": state.get("property_id"), "template_key": selected_tpl},
                    "id": "force_set_numbers_template"
                }])
                return {"messages": [forced_set_tpl], "last_llm_timestamp": time.time()}

        if mentioned_numbers and not selected_tpl:
            ask_msg = AIMessage(content=(
                "¿Qué plantilla de Números quieres usar? Elige una de las siguientes opciones y respóndeme con el nombre o el número:\n\n"
                "1) R2B\n2) R2B + PM\n3) R2B + PM + Venta certs\n4) Promoción"
            ))
            return {"messages": [ask_msg], "last_llm_timestamp": time.time()}
    
    # CRÍTICO: Verificar si ACABAMOS de llamar set_numbers_template
    # Si el último ToolMessage es set_numbers_template, NO añadir contexto de plantilla
    # porque post_tool ya generó el mensaje de confirmación y el LLM debe detenerse
    last_tool_msg = None
    for msg in reversed(messages):
        if isinstance(msg, ToolMessage):
            last_tool_msg = msg
            break
    
    just_set_template = (last_tool_msg and last_tool_msg.name == "set_numbers_template")
    
    # Sin guardias adicionales. Confiamos en el SYSTEM_PROMPT y en post_tool/should_continue.
    # PERO: Si acabamos de llamar set_numbers_template, NO añadir ningún SystemMessage sobre números
    if not just_set_template:
        # Primero verificar si el usuario quiere "empezar" o "completar" la plantilla (resetear)
        user_wants_to_start_afresh = False
        if messages and isinstance(messages[-1], HumanMessage):
            last_user_text = (messages[-1].content or "").lower() if isinstance(messages[-1].content, str) else ""
            # Si el usuario dice "quiero completar", "quiero empezar", "quiero rellenar" → resetear y ofrecer plantillas
            if any(phrase in last_user_text for phrase in ["quiero completar", "quiero empezar", "quiero rellenar", "empezar con números", "completar plantilla"]):
                user_wants_to_start_afresh = True
        
        if state.get("numbers_template") and not user_wants_to_start_afresh:
            # Ya hay template y el usuario NO quiere resetear → continuar normalmente
            # SOLO añadir este contexto si NO acabamos de seleccionar el template
            msgs.append(SystemMessage(content=f"Contexto: Plantilla de Números seleccionada: {state['numbers_template']}. El Excel ya está visible. Espera instrucciones del usuario para modificar valores con `set_number` o `clear_number`."))
        else:
            # NO hay template O el usuario quiere empezar de nuevo → DEBE ofrecer las 4 opciones primero
            if messages and isinstance(messages[-1], HumanMessage):
                last_user_text = (messages[-1].content or "").lower() if isinstance(messages[-1].content, str) else ""
                if any(kw in last_user_text for kw in ["número", "numeros", "plantilla", "completar", "rellenar", "empezar"]):
                    if user_wants_to_start_afresh:
                        # CRÍTICO: Resetear el template en el estado para que el agente no vea un template previo
                        msgs.append(SystemMessage(content="🚨🚨🚨 ATENCIÓN CRÍTICA: El usuario dijo 'quiero completar/empezar la plantilla de Números'. Esto significa que quiere EMPEZAR DESDE CERO. 🚨🚨🚨 DEBES: 1) IGNORAR COMPLETAMENTE cualquier `numbers_template` que pueda existir en el estado. 2) OFRECER las 4 opciones de plantillas (R2B, R2B + PM, R2B + PM + Venta certs, Promoción). 3) ESPERAR a que el usuario elija UNA. 4) NO LLAMAR `get_numbers` ni `set_number` hasta que el usuario haya elegido. TRATA ESTO COMO SI FUERA LA PRIMERA VEZ QUE EL USUARIO ENTRÓ EN NÚMEROS."))
                    else:
                        msgs.append(SystemMessage(content="⚠️ ATENCIÓN: El usuario está entrando en modo Números pero NO hay plantilla seleccionada. DEBES ofrecer las 4 opciones (R2B, R2B + PM, R2B + PM + Venta certs, Promoción) y esperar a que elija antes de llamar `get_numbers` o `set_number`."))
    
    # Limitar historial a los últimos 10 mensajes para evitar rate limits
    # CRÍTICO: Mantener siempre pares AIMessage(tool_calls) + ToolMessage intactos
    if len(messages) > 10:
        filtered = messages[-10:]
        
        # Verificar si el primer mensaje es un ToolMessage
        # Si lo es, necesitamos incluir el AIMessage con tool_calls que lo precede
        if filtered and isinstance(filtered[0], ToolMessage):
            # Buscar hacia atrás el AIMessage con tool_calls que generó este ToolMessage
            tool_call_id = getattr(filtered[0], "tool_call_id", None)
            if tool_call_id:
                # Buscar en los mensajes anteriores
                for i in range(len(messages) - 16, -1, -1):
                    msg = messages[i]
                    if isinstance(msg, AIMessage):
                        tool_calls = getattr(msg, "tool_calls", [])
                        if any(tc.get("id") == tool_call_id for tc in tool_calls):
                            # Encontramos el AIMessage, incluir desde ahí
                            start_idx = i
                            filtered = messages[start_idx:]
                            break
        
        msgs += filtered
    else:
        msgs += messages
    
    # CRÍTICO: Limpiar mensajes huérfanos - validar que cada AIMessage con tool_calls
    # tenga sus correspondientes ToolMessages
    cleaned_msgs = []
    for i, msg in enumerate(msgs):
        if isinstance(msg, AIMessage) and getattr(msg, "tool_calls", None):
            # Este AIMessage tiene tool_calls, verificar si hay respuestas
            tool_call_ids = {tc.get("id") for tc in msg.tool_calls if tc.get("id")}
            
            # Buscar ToolMessages que respondan a estos tool_calls
            answered_ids = set()
            for j in range(i + 1, len(msgs)):
                if isinstance(msgs[j], ToolMessage):
                    tc_id = getattr(msgs[j], "tool_call_id", None)
                    if tc_id in tool_call_ids:
                        answered_ids.add(tc_id)
                elif isinstance(msgs[j], AIMessage):
                    # Siguiente AIMessage, dejar de buscar
                    break
            
            # Si faltan respuestas, SKIP este AIMessage y sus ToolMessages asociados
            if tool_call_ids != answered_ids:
                logger.warning(f"[assistant] Skipping orphaned AIMessage with unanswered tool_calls: {tool_call_ids - answered_ids}")
                # Saltar este mensaje y cualquier ToolMessage asociado
                continue
        
        # Si es ToolMessage, verificar si su AIMessage padre está en cleaned_msgs
        if isinstance(msg, ToolMessage):
            tc_id = getattr(msg, "tool_call_id", None)
            if tc_id:
                # Buscar hacia atrás el AIMessage con este tool_call_id en cleaned_msgs
                found_parent = False
                for parent_msg in reversed(cleaned_msgs):
                    if isinstance(parent_msg, AIMessage):
                        parent_tcs = getattr(parent_msg, "tool_calls", [])
                        if any(tc.get("id") == tc_id for tc in parent_tcs):
                            found_parent = True
                            break
                
                if not found_parent:
                    logger.warning(f"[assistant] Skipping orphaned ToolMessage with id: {tc_id}")
                    continue
        
        cleaned_msgs.append(msg)
    
    msgs = msgs[:2] + cleaned_msgs  # Mantener System messages al inicio

    # Sin guardias: dejamos que el LLM decida con el SYSTEM_PROMPT reforzado

    # Modelo principal para planificación y respuestas
    try:
        if messages and isinstance(messages[-1], ToolMessage):
            # Respuesta final (texto)
            llm = ChatOpenAI(model="gpt-4o", temperature=0, max_retries=3, timeout=60, max_tokens=800)
            ai = llm.invoke(msgs)
        else:
            # Planificación con tools
            llm = ChatOpenAI(model="gpt-4o", temperature=0, max_retries=3, timeout=60, max_tokens=800).bind_tools(TOOLS)
            ai = llm.invoke(msgs)
    except Exception as e:
        # Manejar errores de rate limit y otros errores de API
        error_msg = str(e).lower()
        if "rate limit" in error_msg or "429" in error_msg or "quota" in error_msg or "insufficient_quota" in error_msg:
            logger.error(f"[assistant] Rate limit error: {e}")
            error_response = AIMessage(content="⚠️ Lo siento, he alcanzado el límite de solicitudes a la API de OpenAI. Por favor, espera unos minutos y vuelve a intentar. Si el problema persiste, verifica tu plan y facturación de OpenAI.")
        else:
            logger.error(f"[assistant] Error al invocar LLM: {e}")
            error_response = AIMessage(content=f"⚠️ Ha ocurrido un error al procesar tu solicitud: {str(e)}. Por favor, intenta de nuevo en un momento.")
        return {"messages": [error_response], "last_llm_timestamp": time.time()}

    return {"messages": [ai], "last_llm_timestamp": time.time()}

# --------------- Post-tool hook --------------------
def post_tool(state: AgentState) -> Dict[str, Any]:
    """Apply state changes and render direct responses when possible to reduce LLM calls.

    Responsibilities:
    - set_current_property: persist property_id
    - Direct rendering for common queries (list_docs, get_numbers, list_properties) to skip LLM
    """
    messages = state.get("messages", [])
    
    # Buscar el último ToolMessage
    last_tool_msg = None
    for msg in reversed(messages):
        if isinstance(msg, ToolMessage):
            last_tool_msg = msg
            break
    
    if not last_tool_msg:
        return None
    
    import json
    
    # 1. set_current_property: actualizar property_id en estado
    if last_tool_msg.name == "set_current_property":
        try:
            payload = json.loads(last_tool_msg.content) if isinstance(last_tool_msg.content, str) else last_tool_msg.content
            pid = (payload or {}).get("property_id")
            if pid:
                # Renderizado directo: mencionar propiedad activa
                try:
                    from tools.property_tools import get_property
                    prop_info = get_property(pid)
                    prop_name = (prop_info or {}).get("name", "esta propiedad")
                except:
                    prop_name = "esta propiedad"
                return {
                    "property_id": pid,
                    "messages": [AIMessage(content=f"Ya estamos trabajando con la propiedad \"{prop_name}\". Tienes 2 plantillas por completar: Documentos y Números. ¿Por dónde te gustaría empezar?")]
                }
        except Exception:
            pass

    # 1.1 set_numbers_template: guardar selección en estado y confirmar
    if last_tool_msg.name == "set_numbers_template":
        logger.info(f"[post_tool] ⚡ DETECTADO set_numbers_template - procesando...")
        try:
            # Manejar el contenido del ToolMessage de forma más robusta
            content = last_tool_msg.content
            logger.info(f"[post_tool] Content type: {type(content)}, content: {repr(content)}")
            
            # Si content es un string, intentar parsearlo como JSON
            if isinstance(content, str):
                if content.strip():
                    try:
                        payload = json.loads(content)
                    except json.JSONDecodeError:
                        # Si no es JSON válido, podría ser el template_key directamente O un error de validación
                        if "ValidationError" in content or "field required" in content or "value_error" in content.lower():
                            # Es un error de validación - buscar en los argumentos del tool_call
                            logger.warning(f"[post_tool] Error de validación detectado, buscando template_key en tool_call args...")
                            tool_call_id = getattr(last_tool_msg, "tool_call_id", None)
                            tpl = None
                            if tool_call_id:
                                for msg in reversed(messages):
                                    if isinstance(msg, AIMessage):
                                        tool_calls = getattr(msg, "tool_calls", [])
                                        for tc in tool_calls:
                                            if tc.get("id") == tool_call_id:
                                                args = tc.get("args", {})
                                                tpl = args.get("template_key") or args.get("template_name")
                                                logger.info(f"[post_tool] Template_key extraído del tool_call: {tpl}")
                                                break
                                        if tpl:
                                            break
                            if tpl:
                                payload = {"template_key": tpl}
                            else:
                                # Si no encontramos en tool_call, tratar como template_key directo
                                logger.warning(f"[post_tool] No se encontró en tool_call, tratando como template_key directo: {content[:100]}")
                                tpl = content.strip()
                                payload = {"template_key": tpl}
                        else:
                            # Si no es JSON válido, podría ser el template_key directamente
                            logger.warning(f"[post_tool] Content no es JSON válido, tratando como template_key directo: {content}")
                            tpl = content.strip()
                            payload = {"template_key": tpl}
                else:
                    # String vacío - buscar en los argumentos del tool_call
                    logger.warning(f"[post_tool] Content vacío, buscando en tool_call args...")
                    # Buscar en los mensajes anteriores el AIMessage con tool_calls
                    tool_call_id = getattr(last_tool_msg, "tool_call_id", None)
                    tpl = None
                    if tool_call_id:
                        for msg in reversed(messages):
                            if isinstance(msg, AIMessage):
                                tool_calls = getattr(msg, "tool_calls", [])
                                for tc in tool_calls:
                                    if tc.get("id") == tool_call_id:
                                        args = tc.get("args", {})
                                        tpl = args.get("template_key") or args.get("template_name")
                                        break
                                if tpl:
                                    break
                    if tpl:
                        payload = {"template_key": tpl}
                    else:
                        logger.error(f"[post_tool] No se pudo extraer template_key de ningún lugar")
                        payload = {}
            # Si content ya es un diccionario, usarlo directamente
            elif isinstance(content, dict):
                payload = content
            else:
                logger.error(f"[post_tool] Content tiene tipo inesperado: {type(content)}")
                payload = {}
            
            logger.info(f"[post_tool] Payload procesado: {payload}")
            tpl = (payload or {}).get("template_key", "").strip()
            logger.info(f"[post_tool] Template extraído: '{tpl}'")
            
            if tpl:
                # CRÍTICO: Este mensaje activa el Excel embed en el frontend
                # Los valores previos ya fueron limpiados por set_numbers_template_tool
                msg = f"✅ Usaremos la plantilla de Números: {tpl}."
                logger.info(f"[post_tool] ✅ set_numbers_template procesado - template: {tpl}, valores limpiados, devolviendo AIMessage final")
                # CRÍTICO: Devolver el AIMessage como el ÚNICO mensaje nuevo para que should_continue vea que es el último
                # IMPORTANTE: El reducer add_messages agregará este mensaje al final de la lista
                # Pero para asegurar que should_continue lo vea, necesitamos que el mensaje esté al final
                confirm_msg = AIMessage(content=msg, id="post_tool_set_template_confirm")
                result = {
                    "numbers_template": tpl, 
                    "messages": [confirm_msg]
                }
                logger.info(f"[post_tool] Devolviendo resultado: numbers_template={tpl}, messages length={len(result['messages'])}, message content={msg[:50]}")
                logger.info(f"[post_tool] Estado actual de mensajes antes de devolver: {[type(m).__name__ for m in messages[-3:]]}")
                return result
            else:
                logger.warning(f"[post_tool] ⚠️ Template vacío después de procesar payload")
        except Exception as e:
            logger.error(f"[post_tool] ❌ Error procesando set_numbers_template: {e}", exc_info=True)
            pass
    
    # 2. list_docs: renderizado directo de documentos subidos vs pendientes
    if last_tool_msg.name == "list_docs":
        try:
            data = json.loads(last_tool_msg.content) if isinstance(last_tool_msg.content, str) else last_tool_msg.content
            docs = data if isinstance(data, list) else []
            
            # CRÍTICO: Detectar si venimos de un flujo de recordatorio
            # Si el penúltimo mensaje del usuario menciona "recordatorio" y "cada mes"
            user_msgs = [m for m in messages if isinstance(m, HumanMessage)]
            logger.info(f"[post_tool list_docs] Detectando flujo... user_msgs count: {len(user_msgs)}")
            if user_msgs:
                last_user_text = (user_msgs[-1].content or "").lower() if isinstance(user_msgs[-1].content, str) else ""
                logger.info(f"[post_tool list_docs] last_user_text: {last_user_text[:100]}")
                if "recordatorio" in last_user_text and "cada mes" in last_user_text and "dia que haya que pagar" in last_user_text:
                    logger.info(f"[post_tool list_docs] ✅ FLUJO RECORDATORIO DETECTADO!")
                    # Estamos en flujo de recordatorio - NO renderizar, continuar con extract_payment_date
                    
                    # Detectar concepto de pago
                    if "arquitecto" in last_user_text:
                        payment_concept = "pago al arquitecto"
                        doc_name_hint = "arquitecto"
                    elif "honorarios" in last_user_text:
                        payment_concept = "honorarios"
                        doc_name_hint = "honorarios"
                    else:
                        payment_concept = "pago"
                        doc_name_hint = "contrato"
                    
                    # Buscar documento relacionado
                    target_doc = None
                    for doc in docs:
                        name = doc.get("document_name", "").lower()
                        group = doc.get("document_group", "").lower()
                        if doc_name_hint in name or doc_name_hint in group:
                            if doc.get("storage_key"):  # Solo documentos subidos
                                target_doc = doc
                                break
                    
                    if target_doc:
                        # Forzar extract_payment_date
                        logger.info(f"[post_tool] Flujo recordatorio detectado - forzando extract_payment_date con documento: {target_doc.get('document_name')}")
                        forced_extract = AIMessage(content="", tool_calls=[{
                            "name": "extract_payment_date",
                            "args": {
                                "property_id": state.get("property_id"),
                                "document_group": target_doc.get("document_group"),
                                "document_subgroup": target_doc.get("document_subgroup", ""),
                                "document_name": target_doc.get("document_name"),
                                "payment_concept": payment_concept
                            },
                            "id": "post_tool_extract_date_1"
                        }])
                        return {"messages": [forced_extract]}
            
            # Renderizado normal si NO es flujo de recordatorio
            uploaded = []
            pending = []
            for doc in docs:
                group = doc.get("document_group", "")
                subgroup = doc.get("document_subgroup", "")
                name = doc.get("document_name", "")
                storage_key = doc.get("storage_key")
                
                item = f"- {group} / {subgroup}: {name}" if subgroup else f"- {group}: {name}"
                
                if storage_key and str(storage_key).strip():
                    uploaded.append(item)
                else:
                    pending.append(item)
            
            # Obtener nombre de propiedad
            prop_name = None
            if state.get("property_id"):
                try:
                    from tools.property_tools import get_property
                    prop_info = get_property(state["property_id"])
                    prop_name = (prop_info or {}).get("name")
                except:
                    pass
            
            header = f"Para la propiedad \"{prop_name}\":" if prop_name else "Documentos encontrados:"
            content = (
                f"{header}\n\n"
                f"📄 Documentos subidos:\n" + ("\n".join(uploaded) or "(ninguno)") + "\n\n"
                f"⏳ Documentos pendientes:\n" + ("\n".join(pending) or "(ninguno)")
            )
            
            return {"messages": [AIMessage(content=content)]}
        except Exception:
            pass
    
    # 3. get_numbers: renderizado directo de plantilla de números
    if last_tool_msg.name == "get_numbers":
        try:
            data = json.loads(last_tool_msg.content) if isinstance(last_tool_msg.content, str) else last_tool_msg.content
            items = data if isinstance(data, list) else []
            
            lines = []
            for item in items:
                key = item.get("item_key") or item.get("key", "item")
                val = item.get("amount")
                if val is None:
                    val = item.get("value")
                lines.append(f"- {key}: {val}")
            
            content = "Aquí tienes la plantilla de Números (valores actuales):\n" + ("\n".join(lines) if lines else "(vacío)")
            return {"messages": [AIMessage(content=content)]}
        except Exception:
            pass
    
    # 4. list_properties: renderizado directo de lista de propiedades
    if last_tool_msg.name == "list_properties":
        try:
            data = json.loads(last_tool_msg.content) if isinstance(last_tool_msg.content, str) else last_tool_msg.content
            props = data if isinstance(data, list) else []
            
            if not props:
                content = "No hay propiedades en la base de datos."
            else:
                lines = [f"{i+1}. {p.get('name', 'Sin nombre')} - {p.get('address', 'Sin dirección')}" for i, p in enumerate(props)]
                content = f"Propiedades encontradas ({len(props)}):\n" + "\n".join(lines)
            
            return {"messages": [AIMessage(content=content)]}
        except Exception:
            pass

    # 4.1. list_related_facturas: render respuesta clara
    if last_tool_msg.name == "list_related_facturas":
        try:
            data = json.loads(last_tool_msg.content) if isinstance(last_tool_msg.content, str) else last_tool_msg.content
            items = data if isinstance(data, list) else []
            if not items:
                content = ("No hay facturas asociadas aún (placeholders no creados). Si conoces el día de pago mensual, dime 'día X' y las creo ahora.")
            else:
                lines = []
                for r in items:
                    mark = "⧗" if r.get("placeholder") and not r.get("storage_key") else "✅"
                    due = r.get("due_date") or "(sin fecha)"
                    lines.append(f"{mark} {r.get('document_name','Factura')} — vence {due}")
                content = "Facturas asociadas (placeholders y/o subidas):\n" + "\n".join(lines)
            return {"messages": [AIMessage(content=content)]}
        except Exception:
            pass
    
    # 4.5. extract_payment_date: si encuentra fecha, automáticamente crear recordatorio
    if last_tool_msg.name == "extract_payment_date":
        try:
            data = json.loads(last_tool_msg.content) if isinstance(last_tool_msg.content, str) else last_tool_msg.content
            
            if data.get("date_found"):
                # Extrajo fecha exitosamente - continuar con create_reminder
                extracted_date = data.get("date_formatted") or data.get("date")
                
                # Detectar si el usuario pidió recurrencia mensual
                user_msgs = [m for m in messages if isinstance(m, HumanMessage)]
                if user_msgs:
                    last_user_text = (user_msgs[-1].content or "").lower() if isinstance(user_msgs[-1].content, str) else ""
                    wants_monthly = "cada mes" in last_user_text or "mensual" in last_user_text
                    
                    # Detectar concepto de pago para el título
                    if "arquitecto" in last_user_text:
                        title = "Pago al arquitecto"
                        description = "Recordatorio mensual de pago al arquitecto según contrato"
                    elif "honorarios" in last_user_text:
                        title = "Pago de honorarios"
                        description = "Recordatorio mensual de pago de honorarios"
                    else:
                        title = "Pago programado"
                        description = "Recordatorio de pago según documento"
                    
                    if wants_monthly:
                        # Forzar create_reminder con recurrencia mensual
                        logger.info(f"[post_tool] Fecha extraída: {extracted_date} - creando recordatorio mensual")
                        forced_reminder = AIMessage(content="", tool_calls=[{
                            "name": "create_reminder",
                            "args": {
                                "property_id": state.get("property_id"),
                                "title": title,
                                "description": description,
                                "reminder_date": extracted_date,
                                "recurrence": "monthly",
                                "recurrence_count": 12,
                                "document_reference": data.get("document_reference", {})
                            },
                            "id": "post_tool_create_reminder_1"
                        }])
                        return {"messages": [forced_reminder]}
            else:
                # No encontró fecha - preguntar al usuario
                content = f"⚠️ No pude encontrar una fecha específica en el documento.\n\n{data.get('message', '')}\n\n¿Podrías decirme en qué día del mes debería programar el recordatorio? (ej: 'día 5', '15 de cada mes')"
                return {"messages": [AIMessage(content=content)]}
        except Exception as e:
            logger.error(f"[post_tool] Error procesando extract_payment_date: {e}")
            pass
    
    # 5. create_reminder: manejar errores de setup y renderizar resultados
    if last_tool_msg.name == "create_reminder":
        try:
            data = json.loads(last_tool_msg.content) if isinstance(last_tool_msg.content, str) else last_tool_msg.content
            
            if data.get("setup_required"):
                content = """⚠️ **Sistema de Recordatorios no configurado**

Para activar los recordatorios (toma 1 minuto):

1. Abre: https://supabase.com/dashboard/project/tqqvgaiueheiqtqmbpjh/sql
2. Copia el contenido del archivo: `CREAR_TABLA_REMINDERS.sql`
3. Pégalo en el SQL Editor
4. Click en "RUN"
5. ¡Listo! Vuelve a intentar crear el recordatorio

El archivo SQL está en la raíz del proyecto y contiene todo lo necesario."""
                return {"messages": [AIMessage(content=content)]}
            elif "error" in data:
                content = f"❌ Error al crear recordatorio: {data.get('error')}"
                return {"messages": [AIMessage(content=content)]}
            elif data.get("status") == "created":
                # Renderizar resultado exitoso
                msg = data.get("message", "Recordatorio(s) creado(s)")
                count = data.get("count", 1)
                
                if count > 1:
                    # Mostrar primeros 3 y últimos 3 recordatorios
                    reminders = data.get("reminders", [])
                    preview = reminders[:3] + (["..."] if len(reminders) > 6 else []) + reminders[-3:]
                    dates_list = "\n".join([f"  - {r['date']}" if isinstance(r, dict) else f"  - {r}" for r in preview])
                    content = f"{msg}\n\nFechas:\n{dates_list}\n\n✉️ Se enviarán automáticamente por email en cada fecha."
                else:
                    content = f"{msg}\n\n✉️ Se enviará automáticamente por email en la fecha indicada."
                
                return {"messages": [AIMessage(content=content)]}
        except Exception:
            pass
    
    # 6. build_summary_ppt: renderizado directo del enlace de descarga
    if last_tool_msg.name == "build_summary_ppt":
        try:
            data = json.loads(last_tool_msg.content) if isinstance(last_tool_msg.content, str) else last_tool_msg.content
            
            if "signed_url" in data:
                filename = data.get("filename", "resumen_propiedad.pdf")
                url = data["signed_url"]
                size_kb = data.get("size_bytes", 0) / 1024
                
                content = f"✅ Ficha resumen generada exitosamente.\n\n📄 {filename} ({size_kb:.1f} KB)\n\n{url}\n\nPuedes descargar el PDF desde el enlace anterior."
                return {"messages": [AIMessage(content=content)]}
            elif "error" in data:
                content = f"⚠️ Hubo un problema al subir la ficha a Storage, pero se generó correctamente. Error: {data['error']}"
                return {"messages": [AIMessage(content=content)]}
        except Exception:
            pass
    
    return None

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
def should_continue(state: AgentState) -> Literal["tools", "assistant", "end"]:
    """After executing tools, decide whether to call tools again, assistant, or end.
    
    Si post_tool ya generó una respuesta directa (último mensaje es AIMessage sin tool_calls),
    terminamos ahí. Si tiene tool_calls, necesitamos ejecutar tools de nuevo.
    Si es ToolMessage, volvemos a assistant para que responda.
    """
    messages = state.get("messages", [])
    if not messages:
        return "end"
    
    # Log para debugging: mostrar los últimos 3 mensajes
    logger.info(f"[should_continue] Últimos 3 mensajes: {[type(m).__name__ for m in messages[-3:]]}")
    if messages:
        last = messages[-1]
        logger.info(f"[should_continue] Último mensaje: {type(last).__name__}, name={getattr(last, 'name', 'N/A')}")
        if isinstance(last, AIMessage):
            content_preview = str(last.content)[:100] if hasattr(last, 'content') else 'N/A'
            logger.info(f"[should_continue] AIMessage content preview: {content_preview}")
    
    last = messages[-1]
    
    # Si el último mensaje es AIMessage CON tool_calls, necesitamos ejecutar tools directamente
    # (esto ocurre cuando post_tool fuerza un tool call)
    if isinstance(last, AIMessage) and getattr(last, "tool_calls", None):
        logger.info("[should_continue] AIMessage con tool_calls → ejecutando tools directamente")
        return "tools"
    
    # Si el último mensaje es AIMessage SIN tool_calls, post_tool ya generó respuesta final → END
    if isinstance(last, AIMessage):
        # Verificar si es un mensaje de confirmación de template
        if hasattr(last, 'content') and isinstance(last.content, str) and "Usaremos la plantilla de Números" in last.content:
            logger.info(f"[should_continue] AIMessage de confirmación de template → END (no continuar)")
            return "end"
        logger.info("[should_continue] AIMessage sin tool_calls → END")
        return "end"
    
    # Si el último mensaje es ToolMessage, necesitamos verificar si post_tool ya procesó este mensaje
    if isinstance(last, ToolMessage):
        logger.info(f"[should_continue] ToolMessage (name={last.name}) → verificando si post_tool ya procesó")
        # CRÍTICO: Si es set_numbers_template, post_tool ya procesó y guardó numbers_template en el estado
        # Si el estado tiene numbers_template, significa que post_tool ya procesó y devolvió el AIMessage
        # En este caso, debemos TERMINAR el flujo porque el mensaje de confirmación ya se agregó (o se agregará)
        if last.name == "set_numbers_template":
            # Verificar si post_tool ya procesó: si hay numbers_template en el estado, post_tool ya lo procesó
            if state.get("numbers_template"):
                logger.info(f"[should_continue] ✅ numbers_template encontrado en estado ({state.get('numbers_template')}) - post_tool ya procesó, terminando flujo")
                return "end"
            # Verificar si hay un AIMessage de confirmación en los mensajes anteriores (aunque no sea el último)
            for msg in reversed(messages):
                if isinstance(msg, AIMessage) and isinstance(msg.content, str):
                    if "Usaremos la plantilla de Números" in msg.content:
                        logger.info(f"[should_continue] ✅ Encontrado AIMessage de confirmación en mensajes anteriores → END")
                        return "end"
            # Si no hay numbers_template ni AIMessage, significa que post_tool no procesó todavía
            # PERO debemos TERMINAR de todas formas para evitar que el agente genere otro mensaje
            logger.warning(f"[should_continue] ⚠️ ToolMessage de set_numbers_template detectado - terminando flujo para evitar mensaje duplicado")
            return "end"
        # Para otros ToolMessages, volver a assistant
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
    
    # After post_tool: can route to tools (for forced calls), assistant (for responses), or end
    graph.add_conditional_edges(
        "post_tool",
        should_continue,
        {"tools": "tools", "assistant": "assistant", "end": END}
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
                kwargs={
                    "keepalives": 1,
                    "keepalives_idle": 30,
                    "keepalives_interval": 10,
                    "keepalives_count": 5,
                },
                check=ConnectionPool.check_connection,
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
