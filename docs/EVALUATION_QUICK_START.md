# 🚀 RAMA AI Evals - Quick Start Guide

## ⚡ TL;DR

**Objetivo**: Saber si el agente funciona bien midiendo:
- ✅ Satisfacción del usuario (👍/👎)
- ✅ Selección correcta de herramientas
- ✅ Calidad de respuestas
- ✅ Éxito de tareas

**Plan MVP (3 días)**: Implementar solo 👍/👎 buttons para empezar a recoger data YA.

---

## 📋 Decisión: Custom Framework vs RAGAS/DeepEval

| Criterio | RAGAS | DeepEval | Custom |
|----------|-------|----------|--------|
| **Evalúa RAG** | ✅ | ✅ | ✅ |
| **Evalúa Tool Selection** | ❌ | ❌ | ✅ |
| **Evalúa Multi-Agent** | ❌ | ❌ | ✅ |
| **User Feedback** | ❌ | ❌ | ✅ |
| **Listo para usar** | ✅ | ✅ | ❌ (build) |
| **Fit for RAMA** | 🟡 Partial | 🟡 Partial | 🟢 Perfect |

**Decisión: Custom Framework** (con LLM-as-Judge para calidad)

**Razón**: RAMA AI tiene 77+ tools y 4 agentes especializados. Ningún framework existente evalúa tool selection ni routing multi-agent.

---

## 🎯 MVP: Week 1 (3 días)

### Qué Implementar

1. **Frontend**: 👍/👎 buttons + comment box
2. **Backend**: `/api/feedback` endpoint
3. **Database**: `agent_feedback` table
4. **Dashboard**: Simple tab para ver feedback

### Qué NO Implementar (aún)

- ❌ Tool selection eval (Week 2)
- ❌ LLM-as-Judge (Week 3)
- ❌ Task verifier (Week 4)
- ❌ Advanced dashboard (Week 5)

---

## 🛠️ Implementation Checklist

### Day 1: Database + Backend

- [ ] Create migration `2025-01-21_agent_feedback.sql`
- [ ] Run migration on Supabase
- [ ] Add `/api/feedback` endpoint in `app.py`
- [ ] Test endpoint with Postman/curl

### Day 2: Frontend

- [ ] Create `ChatMessage.tsx` component
- [ ] Add thumbs up/down buttons
- [ ] Add comment textarea (shows on 👎)
- [ ] Wire up to `/api/feedback` endpoint
- [ ] Add toast notification "Gracias por tu feedback!"

### Day 3: Dashboard

- [ ] Create `/dashboard/evals` page
- [ ] Show KPI: Satisfaction Rate (% 👍)
- [ ] Show KPI: Total Feedback Count
- [ ] List recent feedback with filters (👍/👎)
- [ ] Click row → show full conversation

---

## 📊 Expected Metrics (After 2 Weeks)

| Metric | Target | Reality Check |
|--------|--------|---------------|
| **Feedback Rate** | 30%+ | ¿Los usuarios dan feedback? |
| **Satisfaction** | 70%+ | ¿Están satisfechos? |
| **Volume** | 50+ feedback | ¿Suficiente data? |

**Decision Point After 2 Weeks**:
- ✅ If targets met → Proceed with full plan (Weeks 2-6)
- ❌ If not → Pivot strategy (incentives? different UI?)

---

## 🔧 Code Snippets

### Migration (Day 1)

```sql
-- migrations/2025-01-21_agent_feedback.sql
CREATE TABLE agent_feedback (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  property_id UUID REFERENCES properties(id),
  user_id TEXT,
  message_id TEXT NOT NULL UNIQUE,
  agent_name TEXT NOT NULL,
  user_message TEXT NOT NULL,
  agent_response TEXT NOT NULL,
  tool_calls JSONB DEFAULT '[]',
  rating INT CHECK (rating IN (-1, 1)),
  comment TEXT,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_agent_feedback_created ON agent_feedback(created_at DESC);
CREATE INDEX idx_agent_feedback_rating ON agent_feedback(rating);
```

### Backend Endpoint (Day 1)

```python
# app.py
from pydantic import BaseModel
from typing import Optional

class FeedbackRequest(BaseModel):
    message_id: str
    rating: int  # -1 or 1
    comment: Optional[str] = None
    property_id: Optional[str] = None
    agent_name: str
    user_message: str
    agent_response: str

@app.post("/api/feedback")
def submit_feedback(req: FeedbackRequest):
    result = supabase.table("agent_feedback").insert({
        "message_id": req.message_id,
        "rating": req.rating,
        "comment": req.comment,
        "property_id": req.property_id,
        "agent_name": req.agent_name,
        "user_message": req.user_message,
        "agent_response": req.agent_response,
    }).execute()
    
    return {"ok": True, "feedback_id": result.data[0]["id"]}
```

### Frontend Component (Day 2)

```tsx
// web/src/components/ChatMessage.tsx
import { useState } from "react";
import { toast } from "react-hot-toast";

export function ChatMessage({ message }) {
  const [rated, setRated] = useState(false);
  const [showComment, setShowComment] = useState(false);
  const [comment, setComment] = useState("");
  
  const handleFeedback = async (rating: 1 | -1) => {
    if (rating === -1) {
      setShowComment(true);
      return;
    }
    
    await submitFeedback(rating, null);
  };
  
  const submitFeedback = async (rating: number, comment: string | null) => {
    await fetch("/api/feedback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message_id: message.id,
        rating,
        comment,
        agent_name: message.agent,
        user_message: message.userMessage,
        agent_response: message.content,
      }),
    });
    
    setRated(true);
    toast.success("¡Gracias por tu feedback!");
  };
  
  if (message.role !== "assistant") return <div>{message.content}</div>;
  
  return (
    <div className="message">
      <p>{message.content}</p>
      
      {!rated && (
        <div className="feedback-buttons">
          <button onClick={() => handleFeedback(1)}>👍</button>
          <button onClick={() => handleFeedback(-1)}>👎</button>
        </div>
      )}
      
      {showComment && (
        <div className="comment-box">
          <textarea 
            placeholder="¿Qué podríamos mejorar?"
            value={comment}
            onChange={(e) => setComment(e.target.value)}
          />
          <button onClick={() => submitFeedback(-1, comment)}>
            Enviar
          </button>
        </div>
      )}
    </div>
  );
}
```

### Dashboard Page (Day 3)

```tsx
// web/src/app/dashboard/evals/page.tsx
export default async function EvalsPage() {
  const { data } = await supabase
    .from("agent_feedback")
    .select("*")
    .order("created_at", { ascending: false })
    .limit(100);
  
  const positiveCount = data.filter(f => f.rating === 1).length;
  const totalCount = data.length;
  const satisfactionRate = (positiveCount / totalCount * 100).toFixed(1);
  
  return (
    <div>
      <h1>📊 Agent Evaluations</h1>
      
      <div className="kpi-cards">
        <div className="kpi-card">
          <h2>User Satisfaction</h2>
          <p className="kpi-value">{satisfactionRate}%</p>
          <p className="kpi-detail">
            {positiveCount} 👍 / {totalCount - positiveCount} 👎
          </p>
        </div>
        
        <div className="kpi-card">
          <h2>Total Feedback</h2>
          <p className="kpi-value">{totalCount}</p>
        </div>
      </div>
      
      <table>
        <thead>
          <tr>
            <th>Date</th>
            <th>Agent</th>
            <th>Rating</th>
            <th>Comment</th>
          </tr>
        </thead>
        <tbody>
          {data.map(fb => (
            <tr key={fb.id}>
              <td>{new Date(fb.created_at).toLocaleString()}</td>
              <td>{fb.agent_name}</td>
              <td>{fb.rating === 1 ? "👍" : "👎"}</td>
              <td>{fb.comment || "-"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

---

## 🎬 Testing Script

### Manual Test Flow

1. **Open chat** → Send message: "Añade Casa Demo Test"
2. **Agent responds** → See 👍/👎 buttons appear
3. **Click 👎** → Comment box appears
4. **Type comment**: "No me gustó la respuesta"
5. **Click "Enviar"** → Toast: "Gracias por tu feedback!"
6. **Go to `/dashboard/evals`** → See feedback in table

### Automated Test

```python
# tests/test_feedback.py
def test_feedback_flow():
    # 1. Submit feedback
    response = client.post("/api/feedback", json={
        "message_id": "test-123",
        "rating": -1,
        "comment": "Not helpful",
        "agent_name": "PropertyAgent",
        "user_message": "Test",
        "agent_response": "Test response"
    })
    assert response.status_code == 200
    
    # 2. Check stored in DB
    result = supabase.table("agent_feedback").select("*").eq("message_id", "test-123").execute()
    assert len(result.data) == 1
    assert result.data[0]["rating"] == -1
```

---

## 🚀 Launch Checklist

### Pre-Launch

- [ ] Migration tested on dev database
- [ ] Endpoint tested with Postman
- [ ] Frontend tested in local dev
- [ ] Dashboard accessible at `/dashboard/evals`

### Launch

- [ ] Run migration on prod database
- [ ] Deploy backend with new endpoint
- [ ] Deploy frontend with feedback buttons
- [ ] Verify feedback flow works end-to-end

### Post-Launch (Week 1)

- [ ] Monitor feedback volume daily
- [ ] Check for any errors in logs
- [ ] Review first 10 feedback comments
- [ ] Share early results with team

---

## 📈 Success Criteria (2 Weeks)

**Minimum Viable Success**:
- ✅ 30+ feedback received (50+ ideal)
- ✅ No critical bugs in feedback flow
- ✅ Dashboard shows accurate metrics

**Decision Point**:
- If success → Proceed to Phase 2 (Tool Eval)
- If failure → Iterate on MVP (better UI? incentives?)

---

## 🔗 Resources

- Full Strategy: `docs/EVALUATION_STRATEGY.md`
- Architecture: `docs/EVALUATION_ARCHITECTURE.md`
- Executive Summary: `docs/EVALUATION_EXECUTIVE_SUMMARY.md`

---

**Ready to start Day 1?** 🚀

**First Command**:
```bash
# Create migration file
cat > migrations/2025-01-21_agent_feedback.sql << 'SQL'
CREATE TABLE agent_feedback (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  property_id UUID REFERENCES properties(id),
  message_id TEXT NOT NULL UNIQUE,
  agent_name TEXT NOT NULL,
  user_message TEXT NOT NULL,
  agent_response TEXT NOT NULL,
  rating INT CHECK (rating IN (-1, 1)),
  comment TEXT,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_agent_feedback_created ON agent_feedback(created_at DESC);
CREATE INDEX idx_agent_feedback_rating ON agent_feedback(rating);
SQL
```
