# 📊 RAMA AI - Estrategia de Evaluación (Evals)

## 🎯 Objetivo

Implementar un sistema robusto de evaluación para asegurar que el agente:
1. **Responde adecuadamente** a las preguntas del usuario
2. **Selecciona y usa las herramientas correctas** para cada tarea
3. **Aprende de la retroalimentación** del usuario en tiempo real

---

## 🔬 Research Summary

### Frameworks Analizados

| Framework | Pros | Contras | Aplicabilidad |
|-----------|------|---------|---------------|
| **RAGAS** | Evaluación automática sin referencias, métricas para RAG | Enfocado en RAG, no evalúa tool selection | ❌ Limitado |
| **DeepEval** | 14+ métricas, auto-explicativas, integración con tests | Enfocado en RAG y debugging | ⚠️ Parcial |
| **IntellAgent** | Simulaciones realistas, diagnósticos detallados | Curva de aprendizaje, overhead | ⚠️ Complejo |
| **OpenAI Evals** | Integración directa, flexiblCustom framework specifically designed for our architecture | Mayor esfuerzo inicial, pero máxima flexibilidad | ✅ **RECOMENDADO** |

### Decisión: **Custom Framework + LLM-as-Judge**

**Razón**: Nuestro sistema es **multi-agentic** con **tool selection** crítica. Los frameworks existentes están diseñados para RAG o single-agent, no para:
- Routing entre múltiples agentes especializados
- Evaluación de selección de herramientas (77+ tools)
- Confirmaciones explícitas (safety layer)
- Validación de exports (verifier pattern)

---

## 🏗️ Arquitectura de Evaluación

### 1. **User Feedback Layer** (Real-time)
Captura feedback directo del usuario en cada respuesta del chat.

**Componentes**:
- 👍/👎 buttons en cada mensaje del agente
- Campo de comentarios opcional
- Almacenamiento en Supabase `agent_feedback` table

**Métricas**:
- **Satisfaction Rate**: % de 👍 vs total
- **Feedback Volume**: # de feedback recibidos
- **Negative Patterns**: Análisis de comentarios negativos

---

### 2. **Tool Selection Eval** (Automated)
Evalúa si el agente seleccionó la herramienta correcta para la tarea.

**Método**: 
- Capturar `tool_calls` en cada respuesta del agente (ya existe en `BaseAgent.run()`)
- Comparar con **expected tools** definidos por task type
- Usar **LLM-as-Judge** (GPT-4o) para evaluar tool choice relevance

**Métricas**:
- **Tool Accuracy**: ¿Se llamó la herramienta esperada?
- **Tool Precision**: ¿Se evitaron herramientas innecesarias?
- **Tool Latency**: Tiempo hasta seleccionar la herramienta

**Ejemplo**:
```python
User: "Añade Casa Demo 15 en Calle Mayor 1"
Expected Tools: ["add_property"]
Actual Tools: ["add_property"] ✅
Score: 1.0

User: "¿Cuánto cuesta la obra?"
Expected Tools: ["get_numbers", "calc_numbers"]
Actual Tools: ["list_properties", "get_numbers"] ⚠️
Score: 0.5 (partial match, includes irrelevant tool)
```

---

### 3. **Response Quality Eval** (LLM-as-Judge)
Evalúa la calidad de la respuesta final del agente.

**Criterios**:
1. **Relevance** (0-1): ¿Responde a la pregunta del usuario?
2. **Completeness** (0-1): ¿Proporciona toda la información necesaria?
3. **Accuracy** (0-1): ¿La información es correcta? (verificable con DB/tools)
4. **Tone** (0-1): ¿Mantiene el tono profesional esperado?

**Método**:
- Usar GPT-4o como juez
- Prompt especial con criterios claros
- Output estructurado (JSON)

**Ejemplo Prompt**:
```
You are an expert evaluator for an AI real estate assistant.

USER REQUEST: "Añade Casa Demo 15"
AGENT RESPONSE: "✅ Propiedad creada: Casa Demo 15 (ID: abc-123)"
TOOLS USED: ["add_property"]
TOOL RESULTS: {"id": "abc-123", "name": "Casa Demo 15"}

Evaluate the agent's response on these criteria (0-1 scale):
1. Relevance: Did it address the user's request?
2. Completeness: Did it provide necessary information?
3. Accuracy: Is the information correct based on tool results?
4. Tone: Is it professional and friendly?

Output JSON:
{
  "relevance": 1.0,
  "completeness": 1.0,
  "accuracy": 1.0,
  "tone": 1.0,
  "overall": 1.0,
  "reasoning": "..."
}
```

---

### 4. **Task Success Eval** (Verifier Pattern)
Evalúa si la tarea del usuario se completó exitosamente.

**Método**:
- Extender el **verifier** existente (ya usado para `export_numbers_table`)
- Verificar estado del sistema después de la acción
- Comparar con expectativas

**Ejemplo**:
```python
Task: "Añade Casa Demo 15"
Verification:
  1. Check properties table → Casa Demo 15 exists ✅
  2. Check frameworks provisioned → 3 schemas exist ✅
  Success: True

Task: "Pon el IVA en 21%"
Verification:
  1. Check numbers_table_values → cell B5 = "21" ✅
  2. Check auto-calculated D5 → D5 has value ✅
  Success: True
```

---

## 🗄️ Data Schema

### New Table: `agent_feedback`
```sql
CREATE TABLE agent_feedback (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  property_id UUID REFERENCES properties(id),
  user_id TEXT,
  message_id TEXT NOT NULL,
  agent_name TEXT NOT NULL,
  user_message TEXT NOT NULL,
  agent_response TEXT NOT NULL,
  tool_calls JSONB DEFAULT '[]',
  
  -- User feedback
  rating INT CHECK (rating IN (-1, 1)),  -- -1 = 👎, 1 = 👍
  comment TEXT,
  
  -- Automated evals (populated asynchronously)
  tool_eval JSONB,  -- {accuracy, precision, latency_ms, expected_tools, actual_tools}
  response_eval JSONB,  -- {relevance, completeness, accuracy, tone, overall, reasoning}
  task_success_eval JSONB,  -- {success, verification_steps, failures}
  
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_agent_feedback_property ON agent_feedback(property_id);
CREATE INDEX idx_agent_feedback_agent ON agent_feedback(agent_name);
CREATE INDEX idx_agent_feedback_rating ON agent_feedback(rating);
CREATE INDEX idx_agent_feedback_created ON agent_feedback(created_at DESC);
```

---

## 🔧 Implementation Plan

### **Phase 1: User Feedback (Week 1)** ✅ PRIORITY

#### 1.1 Frontend (Next.js)
- [ ] Add `ThumbsUp`/`ThumbsDown` buttons to each agent message
- [ ] Add expandable comment textarea on thumbs down
- [ ] Store feedback in `agent_feedback` table via `/api/feedback` endpoint
- [ ] Show "Thanks for feedback!" confirmation

**File**: `web/src/components/ChatMessage.tsx` (new component)

#### 1.2 Backend (FastAPI)
- [ ] Create `/api/feedback` endpoint
- [ ] Validate and store feedback in Supabase
- [ ] Return confirmation

**File**: `app.py` (new endpoint)

#### 1.3 Database
- [ ] Run migration to create `agent_feedback` table
- [ ] Add RLS policies for user access

**File**: `migrations/2025-01-21_agent_feedback.sql`

---

### **Phase 2: Tool Selection Eval (Week 2)** 🤖

#### 2.1 Tool Call Tracking
- [ ] Extend `BaseAgent.run()` to log tool calls to `agent_feedback`
- [ ] Capture tool results alongside tool calls
- [ ] Store in `tool_calls` JSONB field

**File**: `agents/base_agent.py` (already captures `tool_calls`, just need to persist)

#### 2.2 Expected Tools Registry
- [ ] Create `EXPECTED_TOOLS_BY_INTENT` mapping
- [ ] Use pattern matching or LLM to classify user intent
- [ ] Map intent → expected tools

**File**: `tools/eval_registry.py` (new)

Example:
```python
EXPECTED_TOOLS_BY_INTENT = {
    "create_property": ["add_property"],
    "list_properties": ["list_properties"],
    "set_number": ["set_numbers_table_cell"],
    "export_numbers": ["export_numbers_table", "send_numbers_table_email"],
    "upload_document": ["propose_doc_slot", "upload_and_link"],
    # ... 
}
```

#### 2.3 Tool Accuracy Evaluator
- [ ] Implement `evaluate_tool_selection(user_message, tool_calls, expected_tools)`
- [ ] Calculate precision/recall metrics
- [ ] Store in `tool_eval` JSONB field

**File**: `tools/eval_tool_selection.py` (new)

---

### **Phase 3: LLM-as-Judge Response Quality (Week 3)** 🧑‍⚖️

#### 3.1 Judge Prompt Template
- [ ] Create structured prompt for GPT-4o judge
- [ ] Define evaluation criteria (relevance, completeness, accuracy, tone)
- [ ] Request JSON output

**File**: `prompts/evals/response_judge.md` (new)

#### 3.2 Judge Executor
- [ ] Implement `judge_response_quality(user_message, agent_response, tool_calls, tool_results)`
- [ ] Call GPT-4o with judge prompt
- [ ] Parse JSON output
- [ ] Store in `response_eval` JSONB field

**File**: `tools/eval_response_quality.py` (new)

#### 3.3 Async Evaluation Pipeline
- [ ] After agent response, trigger async eval job
- [ ] Run tool selection eval + response quality eval
- [ ] Update `agent_feedback` row with results
- [ ] Log to Logfire for monitoring

**File**: `tools/eval_pipeline.py` (new)

---

### **Phase 4: Task Success Verifier (Week 4)** ✅

#### 4.1 Extend Verifier Pattern
- [ ] Generalize existing `verify_export` to `verify_task(task_type, property_id, tool_calls)`
- [ ] Add verification rules for each task type
- [ ] Store in `task_success_eval` JSONB field

**File**: `tools/verifier.py` (extend existing)

#### 4.2 Verification Rules
- [ ] `create_property`: Check property exists in DB
- [ ] `set_number`: Check cell value in numbers_table_values
- [ ] `upload_document`: Check storage_key in docs framework
- [ ] `delete_property`: Check soft_deleted flag
- [ ] ... (define for top 10-15 most critical tasks)

---

### **Phase 5: Eval Dashboard (Week 5)** 📊

#### 5.1 New Dashboard Tab: "Evaluations"
- [ ] Add `/api/dashboard/evals` endpoint
- [ ] Query `agent_feedback` with aggregations
- [ ] Show:
  - **User Satisfaction**: 👍% over time
  - **Tool Accuracy**: % of correct tool selections
  - **Response Quality**: Avg scores (relevance, completeness, etc.)
  - **Task Success Rate**: % of verified successful tasks
  - **Recent Negative Feedback**: List of 👎 with comments

**File**: `web/src/app/dashboard/evals/page.tsx` (new)

#### 5.2 Feedback Detail View
- [ ] Click on any feedback row → show full conversation
- [ ] Show user message, agent response, tools used, evals scores
- [ ] Allow manual override/annotation

---

### **Phase 6: Continuous Learning (Week 6)** 🎓

#### 6.1 Feedback Loop to Prompts
- [ ] Analyze patterns in negative feedback
- [ ] Identify common failure modes (e.g., wrong tool selection, incomplete response)
- [ ] Update system prompts to address patterns

**Process**:
1. Weekly review of negative feedback
2. Identify top 3 failure patterns
3. Update prompts/tool descriptions
4. Measure improvement in next week's evals

#### 6.2 Fine-tuning Dataset (Future)
- [ ] Export high-quality conversations (👍 feedback, high eval scores)
- [ ] Format as fine-tuning dataset for GPT-4o
- [ ] Periodically fine-tune custom model

**Format** (OpenAI fine-tuning):
```jsonl
{"messages": [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}, {"role": "assistant", "content": "...", "tool_calls": [...]}]}
```

---

## 📈 Success Metrics

### Target KPIs (3 months)

| Metric | Baseline (Today) | Target (3mo) |
|--------|------------------|--------------|
| **User Satisfaction** | ? (no data) | **80%** 👍 rate |
| **Tool Accuracy** | ? (no data) | **90%** correct tool selection |
| **Response Quality** | ? (no data) | **Avg 0.85/1.0** on all criteria |
| **Task Success Rate** | ? (no data) | **95%** verified successful |

### Leading Indicators
- **Feedback Volume**: Target 30%+ of conversations get feedback
- **Negative Feedback Response Time**: Address patterns within 1 week
- **Eval Coverage**: 100% of conversations evaluated automatically

---

## 🛡️ Evaluating the Evals (Meta-Evaluation)

### How do we know our evals are good?

#### 1. **Correlation with User Feedback**
- Compare LLM-as-Judge scores with user 👍/👎
- High correlation → judge is accurate
- Low correlation → refine judge prompt

**Metric**: Pearson correlation between `response_eval.overall` and `rating`
**Target**: r > 0.7

#### 2. **Inter-Rater Reliability** (Human Baseline)
- Sample 100 conversations
- 2 human annotators rate each (0-1 scale)
- Compare human scores with LLM-as-Judge scores

**Metric**: Cohen's Kappa
**Target**: κ > 0.6 (substantial agreement)

#### 3. **A/B Testing Eval Changes**
- Change judge prompt → measure impact on correlation
- Change tool registry → measure impact on tool accuracy
- Iterate based on data

---

## 🚀 Quick Start (MVP)

### **Week 1 MVP: Just User Feedback**

**Goal**: Get thumbs up/down working ASAP to start collecting data.

**Tasks**:
1. ✅ Create `agent_feedback` table
2. ✅ Add thumbs up/down buttons to frontend
3. ✅ Create `/api/feedback` endpoint
4. ✅ Show feedback in simple dashboard tab

**Time**: 2-3 days
**Value**: Start collecting real user data immediately

---

## 🔄 Iteration Strategy

### Agile Eval Development

**Sprint 1 (Week 1)**: User feedback only → **collect data**
**Sprint 2 (Week 2)**: Add tool eval → **measure tool accuracy**
**Sprint 3 (Week 3)**: Add LLM judge → **measure response quality**
**Sprint 4 (Week 4)**: Add verifier → **measure task success**
**Sprint 5 (Week 5)**: Dashboard → **visualize all evals**
**Sprint 6 (Week 6)**: Iterate on prompts based on patterns

**Key Principle**: Ship fast, measure, iterate. Don't wait for perfect evals.

---

## 💡 Advanced: Multi-Agent Eval

Since RAMA AI uses **specialized agents** (PropertyAgent, DocsAgent, NumbersAgent), we need **agent-specific evals**.

### Agent-Specific Metrics

**PropertyAgent**:
- Property creation success rate
- Property search accuracy (find_property)

**DocsAgent**:
- Document upload success rate
- Document classification accuracy (propose_slot)
- Email delivery success rate

**NumbersAgent**:
- Cell value accuracy (set_numbers_table_cell)
- Auto-calculation correctness (formula cascade)
- Export format correctness (verify_export)

### Router Eval
- **Routing Accuracy**: Did MainAgent route to correct specialized agent?
- **Escalation Correctness**: Did specialized agent correctly escalate multi-domain tasks?

**File**: `router/eval_routing.py` (new)

---

## 📚 References

- [OpenAI Evals Framework](https://github.com/openai/evals)
- [LangSmith Evaluation Guide](https://docs.smith.langchain.com/evaluation)
- [RAGAS Paper](https://arxiv.org/abs/2309.15217)
- [LLM-as-Judge Pattern](https://arxiv.org/abs/2306.05685)
- [Pydantic AI Logfire Docs](https://ai.pydantic.dev/logfire/)

---

## ✅ Decision Log

| Date | Decision | Reasoning |
|------|----------|-----------|
| 2025-01-20 | Use custom framework over RAGAS/DeepEval | Need tool selection eval + multi-agent routing eval |
| 2025-01-20 | Use LLM-as-Judge (GPT-4o) for response quality | More flexible than rule-based, can understand context |
| 2025-01-20 | Store all feedback in Supabase `agent_feedback` | Centralized, queryable, supports RLS for multi-tenant |
| 2025-01-20 | Start with user feedback MVP (Week 1) | Fastest way to start collecting real data |
| 2025-01-20 | Use verifier pattern for task success | Already implemented for exports, easy to extend |

---

## 🤝 Next Steps

**Decision Required from User**:
1. ✅ **Approve MVP Plan (Week 1: User Feedback)**
   - Start with thumbs up/down + comments
   - Get data flowing immediately
2. ⏸️ **Approve Full Plan (Weeks 2-6)**
   - Tool eval, LLM judge, verifier, dashboard
   - More comprehensive but longer timeline

**Recommendation**: **Start with MVP (Week 1)** to validate approach and collect data, then decide on full implementation based on initial learnings.

**What do you think?** 🚀

