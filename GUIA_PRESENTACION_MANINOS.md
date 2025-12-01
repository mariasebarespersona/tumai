# 📋 GUÍA DE PRESENTACIÓN: RAMA AI x MANINOS CAPITAL
**Objetivo:** Demostrar cómo RAMA AI escala las operaciones de Maninos Capital usando sus propios manuales.

---

## 🟢 SECCIÓN 1: INTRODUCCIÓN Y CONTEXTO

### 📺 Slide 1: Portada
*   **Título:** RAMA AI x Maninos Capital
*   **Subtítulo:** Escalando vuestro portafolio de 125 a 1.000 viviendas con Inteligencia Artificial Agéntica.
*   **Visual:** Logo de RAMA y Logo de Maninos (si lo tienes) o fondo limpio.

### 📺 Slide 2: El Reto de Escalar (Vuestra Situación)
*   **Visual:** Gráfico de crecimiento o iconos de "Crecimiento vs Operaciones".
*   **Puntos Clave (Basados en vuestro Deck):**
    *   🚀 **Crecimiento Explosivo:** +1.150% en 3 años (de 10 a 125 casas).
    *   🎯 **Meta Ambiciosa:** Capital eficiente ($10M equity = ~200 unidades).
    *   ⚠️ **El Cuello de Botella:** Escalar el capital es "fácil", escalar las operaciones (cobros, onboarding, compliance) manualmente es difícil.
    *   **Mensaje:** "Para llegar a 1.000 unidades sin multiplicar vuestra plantilla por 10, necesitáis automatización inteligente."

### 📺 Slide 3: Nuestra Propuesta: RAMA AI
*   **Visual:** Captura de pantalla de la interfaz de Chat de RAMA (`web/src/app/page.tsx`).
*   **Puntos Clave:**
    *   No somos un chatbot genérico.
    *   Somos un sistema de **"Empleados Digitales" (Agentes)**.
    *   **Diferencia clave:** RAMA tiene memoria, usa herramientas reales (Excel, Email) y sigue reglas estrictas.
    *   **Promesa:** "No solo charlamos; ejecutamos trabajo."

---

## 🟡 SECCIÓN 2: LA SOLUCIÓN A MEDIDA (EL GANCHO)

### 📺 Slide 4: Automatizando vuestro Manual de Operaciones
*   **Visual:** Una imagen partida: A la izquierda una foto de la portada de su manual (`DOC-20250819...`), a la derecha 3 iconos de "Agentes".
*   **Guion (Crucial - Citar su manual):**
    "Hemos analizado vuestro manual y hemos diseñado 3 agentes para hacer cumplir vuestras reglas automáticamente:"

    1.  🏗️ **Acquisition Agent:**
        *   *Regla:* Verifica automáticamente que "Precio Compra ≤ 70% Valor Mercado" (Manual Pág. 2).
    2.  🤝 **Onboarding Agent:**
        *   *Regla:* Clasifica riesgo y asigna contratos de 24 vs 48 meses según Credit Score (Manual Pág. 4).
    3.  💸 **Collections Agent:**
        *   *Regla:* Ejecuta el protocolo de mora: SMS al día 5, Cobranzas al día 30, Reposesión al día 60 (Manual Pág. 8).

---

## 🔴 SECCIÓN 3: DEMOSTRACIÓN EN VIVO (EL "WOW")

### 📺 Slide 5: RAMA EN ACCIÓN (Slide de transición)
*   **Acción:** *Dejar de compartir presentación, compartir pantalla de la App RAMA.*

#### 🕹️ Paso 1: Gestión Documental (DocsAgent)
1.  **Contexto:** "Imagina que soy un Property Manager nuevo en Maninos y tengo una duda sobre el proceso."
2.  **Acción:** Tener el manual (`DOC-20250819...`) ya cargado en la pestaña "Documentos".
3.  **Pregunta al Chat:** *"¿Cuál es el criterio de inspección para el techo de una casa nueva?"*
4.  **Resultado Esperado:** RAMA responde citando la **Página 2** ("No structural damage...").
5.  **Pregunta 2 (Opcional):** *"¿Cuál es el DTI máximo para un inquilino?"* (Respuesta: 40%, Pág 4).

#### 🕹️ Paso 2: Dominio Financiero (NumbersAgent)
1.  **Contexto:** "Ahora necesitamos ver si una operación es rentable."
2.  **Acción:** Ir a una propiedad de demostración.
3.  **Interacción:** *"Pon el precio de compra en 30000 y el coste de reforma en 6000."*
4.  **Resultado:** Ver cómo la tabla se actualiza y recalcula el total.
5.  **Cierre Demo:** "Esto no es una calculadora muerta, es un Excel vivo conectado a vuestros procesos."

---

## 🔵 SECCIÓN 4: CONFIANZA Y CIERRE

### 📺 Slide 6: Tecnología y Seguridad (Por qué funciona)
*   **Visual:** Diagrama de Arquitectura (`docs/ARCHITECTURE_VISUAL_GUIDE.md` - Usa el diagrama principal).
*   **Puntos Clave (Para el CTO/Técnico):**
    *   🤖 **Sin Alucinaciones:** Usamos bucles "ReAct". Si el agente no encuentra el dato en la base de datos, no se lo inventa.
    *   🧠 **Memoria Infinita:** RAMA recuerda que pediste un reporte hace 2 semanas.
    *   🔒 **Seguridad Empresarial:** Vuestros datos están aislados y seguros (Row Level Security).

### 📺 Slide 7: Roadmap de Implementación
*   **Visual:** Línea de tiempo simple (Timeline).
*   **Hitos:**
    *   📅 **Semana 1 (Ya lista):** Ingesta del Manual (Base de Conocimiento RAG).
    *   📅 **Semanas 2-4:** Integración con vuestro ERP (mencionado en manual).
    *   📅 **Semana 5:** Despliegue a los Property Managers.

### 📺 Slide 8: Siguientes Pasos
*   **Visual:** Tus datos de contacto y una pregunta grande.
*   **Call to Action:**
    *   "La versión 'Base de Conocimiento' ya funciona con vuestro manual."
    *   "¿Empezamos un piloto de 48h para que vuestro equipo lo pruebe?"

---

## 💡 NOTAS PARA LA PREPARACIÓN
1.  **Antes de la reunión:** Sube el PDF del manual (`DOC-20250819-WA0096..pdf`) a tu entorno local de RAMA.
2.  **Verifica:** Haz las preguntas de la demo antes para asegurarte de que la respuesta es perfecta.
3.  **Ambiente:** Ten la app abierta en una pestaña limpia, sin conversaciones basura previas.

