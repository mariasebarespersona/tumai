# RAMA AI - Preparación del Pitch Deck y Análisis Técnico para Maninos Capital

## 🎯 Resumen Ejecutivo
RAMA AI es un **asistente de IA "agentic" de grado empresarial** diseñado específicamente para la gestión de activos inmobiliarios. A diferencia de los chatbots genéricos, RAMA utiliza una **arquitectura multi-agente** con estrictos mecanismos de control (bucles ReAct) para garantizar el 100% de precisión en los datos y el cumplimiento de los procesos.

**Nuestra Promesa Central:** "No solo charlamos; ejecutamos trabajo."

Para **Maninos Capital**, ofrecemos un sistema que no solo "almacena" su Manual de Operaciones, sino que **lo hace cumplir activamente** en su portafolio de más de 125 viviendas.

---

## 🚀 Capacidades Clave (La "Magia" para la Demo)

### 1. Gestión Inteligente de Documentos (DocsAgent)
*   **Problema:** "¿Dónde está la lista de verificación KYC?" o "¿Cuál es el procedimiento para la morosidad de 30 días?"
*   **Solución RAMA:**
    *   **Recuperación Instantánea:** Haz preguntas de forma natural: *"¿Cuáles son los criterios de inspección para el techo en el manual?"* -> RAMA cita la Página 2: *"Sin daños estructurales (ej. techo, cimientos, paredes)."*
    *   **Accionable:** *"Envía la plantilla del contrato de Alquiler con Opción a Compra al nuevo inquilino"* -> RAMA encuentra el archivo, genera un enlace seguro y lo envía por correo electrónico.

### 2. Dominio Financiero (NumbersAgent)
*   **Problema:** Modelar la deuda al 12% de interés anual frente a contratos de alquiler con opción a compra de 24/36/48 meses.
*   **Solución RAMA:**
    *   **Excel en Base de Datos en Vivo:** Gestionamos modelos financieros complejos directamente en la base de datos.
    *   **Planificación de Escenarios:** *"Si compramos esta casa por $30k y gastamos $6k en renovaciones, ¿cumplimos con la regla de <80% ARV?"* -> RAMA calcula al instante.
    *   **Confianza:** Utiliza fórmulas definidas (ej. Ratio de Cobertura del Servicio de la Deuda), nunca "adivina" números.

### 3. Centro de Mando del Portafolio (PropertyAgent)
*   **Problema:** Gestionar más de 125 casas móviles en Houston, Dallas, San Antonio.
*   **Solución RAMA:**
    *   **Cambio de Contexto:** Cambia sin problemas entre propiedades ("Muéstrame el informe de morosidad del parque de San Antonio").
    *   **Persistencia de Estado:** Recuerda dónde lo dejaste (ej. a mitad de la revisión de un contrato).

---

## 🛠️ Superioridad Técnica (Por qué somos el equipo adecuado)

Usa estos puntos para convencer al CTO/Stakeholders Técnicos:

1.  **Sin Alucinaciones (Bucles ReAct):**
    *   Nuestros agentes operan en bucles de **Razonar + Actuar**. *Deben* llamar a una herramienta (consulta a base de datos) para obtener hechos. No pueden inventar números o documentos.
    *   *Evidencia:* Ver `agents/base_agent.py` - la IA se ve obligada a iterar hasta tener datos reales.

2.  **Memoria a Largo Plazo (PostgreSQL Checkpointer):**
    *   El sistema recuerda el contexto para siempre. Si un cliente dice "Envíamelo", RAMA sabe que "lo" es el documento discutido hace 5 minutos y "me" es el correo electrónico proporcionado la semana pasada.

3.  **Modular y Escalable (Arquitectura LangGraph):**
    *   Usamos **LangGraph** (Estado del Arte) para la orquestación.
    *   **Prompts Modulares:** Podemos adaptar la IA a *tu* tono y reglas específicas editando simples archivos Markdown, sin reescribir código.

4.  **Seguridad Empresarial:**
    *   **Seguridad a Nivel de Fila (RLS):** Los datos están aislados a nivel de base de datos.
    *   **Logs de Auditoría:** Cada acción se rastrea en Logfire.

### 5. Stack Tecnológico de Primera Clase
*   **Backend:** Python 3.11, FastAPI (Alto Rendimiento).
*   **Orquestación de IA:** LangGraph (El último estándar para IA agéntica).
*   **Frontend:** Next.js 14, React, Tailwind CSS (UI moderna y rápida).
*   **Base de Datos:** Supabase (PostgreSQL) - El estándar de oro para datos relacionales.
*   **Infraestructura:** Render & Vercel (Hosting en la nube confiable y escalable).

---

## 🤝 Estrategia a Medida para Maninos Capital

**Petición del Cliente:** *"A ver si podéis manejar nuestro manual y procesos."*

**Nuestro Pitch:**
"Hemos analizado vuestro **Manual de Operaciones** (DOC-20250819-WA0096) y podemos automatizar vuestra cadena de valor principal de inmediato."

### Fase 1: Ingesta y Base de Conocimiento (Semana 1)
*   **Acción:** Ingestamos vuestro manual PDF en nuestro sistema RAG (Generación Aumentada por Recuperación).
*   **Valor:** Vuestro equipo puede chatear con el manual:
    *   *"¿Cuál es el ratio DTI objetivo para nuevos inquilinos?"* -> **RAMA:** "El ratio Deuda-Ingreso objetivo es **≤ 40%**, según la Página 4."
    *   *"¿Cuál es el plazo para la reposesión?"* -> **RAMA:** "La morosidad se escala a cobranzas después de **30 días**, con reposesión después de **60 días**, según la ley de Texas (Página 8)."

### Fase 2: Agentes de Automatización de Procesos (Semanas 2-4)
Construiremos agentes especializados que **hagan cumplir** las reglas de vuestro manual:

1.  **El "Agente de Adquisición"**
    *   **Regla del Manual:** Precio de compra ≤ 70% del valor de mercado; Renovación + Precio ≤ 80% ARV.
    *   **Automatización:** Introduces una operación (Precio: $30k, Reno: $5k, ARV: $50k).
    *   **Chequeo RAMA:** "Costo Total ($35k) es 70% del ARV. **Aprobado** según criterios del manual (Objetivo ≤ 80%)."

2.  **El "Agente de Onboarding"**
    *   **Regla del Manual:** Verificar Ingresos ≥ 3x alquiler; Umbrales de Credit Score (600+ para 24meses, <600 para 48meses).
    *   **Automatización:** Subes el PDF del solicitante. RAMA extrae ingresos/score de crédito y recomienda:
    *   **Recomendación RAMA:** "Score del Solicitante 580. Recomiendo **contrato de 48 meses** con **30% de pago inicial** según Perfil de Riesgo 'Alto' (Página 4)."

3.  **El "Agente de Cobranzas"**
    *   **Regla del Manual:** Recordatorios SMS después de 5 días.
    *   **Automatización:** RAMA se conecta a vuestra base de datos de alquileres (integración Buildium/AppFolio vía API) y automáticamente dispara borradores de SMS para aprobación cuando el pago tiene >5 días de retraso.

---

## 🎨 Visuales para la Presentación
*(Incluye estos desde nuestra carpeta `docs/`)*

1.  **Diagrama de Arquitectura:** Muestra el diagrama de `docs/ARCHITECTURE_VISUAL_GUIDE.md` para probar la robustez.
2.  **Captura de Pantalla - Interfaz de Chat:** Muestra la UI limpia (`web/src/app/page.tsx`) con una tabla financiera.
3.  **Captura de Pantalla - Móvil:** Enfatiza que funciona sobre la marcha para los administradores de propiedades que visitan las 125 casas.

---

## 📋 Próximos Pasos para el Cliente

1.  **Demo Piloto (48h):** Mostramos a RAMA respondiendo preguntas *específicamente* sobre la sección "Purchase of Mobile Homes" de vuestro manual.
2.  **Plan de Integración:** Definimos el alcance de la integración con vuestro ERP/CRM mencionado en el manual ("centralized ERP system").
3.  **Fecha de Inicio:** Podemos desplegar la versión "Base de Conocimiento" de inmediato.

