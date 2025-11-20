# 🏗️ RAMA AI - Arquitectura de Evaluación

## 📊 Visión General del Sistema

```
┌──────────────────────────────────────────────────────────────────────────┐
│                           USER INTERACTION                               │
│                                                                          │
│  User: "Añade Casa Demo 15 en Calle Mayor 1"                           │
│                                  ↓                                       │
│  [Chat UI] ← 👍/👎 + Comment                                            │
└──────────────────────────────────────────────────────────────────────────┘
                                  ↓
┌──────────────────────────────────────────────────────────────────────────┐
│                          AGENT PROCESSING                                │
│                                                                          │
│  1. MainAgent receives request                                          │
│  2. Routes to PropertyAgent                                             │
│  3. PropertyAgent.run()                                                 │
│     → calls add_property tool                                           │
│     → returns response                                                   │
│  4. Response sent to user                                               │
│                                                                          │
│  📝 Captured Data:                                                       │
│     - user_message: "Añade Casa Demo 15..."                            │
│     - agent_name: "PropertyAgent"                                       │
│     - agent_response: "✅ Propiedad creada..."                         │
│     - tool_calls: [{"name": "add_property", ...}]                      │
│     - tool_results: {"id": "abc-123", ...}                             │
└──────────────────────────────────────────────────────────────────────────┘
                                  ↓
┌──────────────────────────────────────────────────────────────────────────┐
│                       EVALUATION PIPELINE (Async)                        │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────┐        │
│  │  Layer 1: USER FEEDBACK (Real-time)                        │        │
│  │  - User clicks 👍/👎                                        │        │
│  │  - Optional comment                                         │        │
│  │  → Store in agent_feedback.rating, .comment                │        │
│  └────────────────────────────────────────────────────────────┘        │
│                               ↓                                          │
│  ┌────────────────────────────────────────────────────────────┐        │
│  │  Layer 2: TOOL SELECTION EVAL (Automated)                  │        │
│  │  - Compare tool_calls vs expected_tools                    │        │
│  │  - Calculate accuracy, precision                           │        │
│  │  → Store in agent_feedback.tool_eval                       │        │
│  └────────────────────────────────────────────────────────────┘        │
│                               ↓                                          │
│  ┌────────────────────────────────────────────────────────────┐        │
│  │  Layer 3: RESPONSE QUALITY (LLM-as-Judge)                  │        │
│  │  - GPT-4o judges: relevance, completeness, accuracy, tone │        │
│  │  - Returns JSON with scores 0-1                            │        │
│  │  → Store in agent_feedback.response_eval                   │        │
│  └────────────────────────────────────────────────────────────┘        │
│                               ↓                                          │
│  ┌────────────────────────────────────────────────────────────┐        │
│  │  Layer 4: TASK SUCCESS (Verifier)                          │        │
│  │  - Check DB/system state post-action                       │        │
│  │  - Verify task completed successfully                      │        │
│  │  → Store in agent_feedback.task_success_eval               │        │
│  └────────────────────────────────────────────────────────────┘        │
└──────────────────────────────────────────────────────────────────────────┘
                                  ↓
┌──────────────────────────────────────────────────────────────────────────┐
│                          STORAGE & ANALYTICS                             │
│                                                                          │
│  Supabase Table: agent_feedback                                         │
│  ┌──────────────────────────────────────────────────────────┐          │
│  │  id, property_id, user_id, message_id                    │          │
│  │  agent_name, user_message, agent_response                │          │
│  │  tool_calls, rating, comment                             │          │
│  │  tool_eval, response_eval, task_success_eval             │          │
│  │  created_at, updated_at                                  │          │
│  └──────────────────────────────────────────────────────────┘          │
│                               ↓                                          │
│  Aggregations & Metrics:                                                │
│  - Satisfaction Rate (% 👍)                                             │
│  - Tool Accuracy (% correct tools)                                      │
│  - Response Quality (avg scores)                                        │
│  - Task Success Rate (% verified)                                       │
└──────────────────────────────────────────────────────────────────────────┘
                                  ↓
┌──────────────────────────────────────────────────────────────────────────┐
│                         DASHBOARD & MONITORING                           │
│                                                                          │
│  /dashboard/evals                                                        │
│  ┌────────────────────────────────────────────────────────────┐        │
│  │  📊 KPIs                                                     │        │
│  │  👍 User Satisfaction: 82%                                  │        │
│  │  🎯 Tool Accuracy: 91%                                      │        │
│  │  📝 Response Quality: 0.87/1.0                              │        │
│  │  ✅ Task Success: 94%                                       │        │
│  │                                                             │        │
│  │  📈 Trends (7 days)                                         │        │
│  │  [Line chart showing improvement over time]                │        │
│  │                                                             │        │
│  │  👎 Recent Negative Feedback                               │        │
│  │  - "No entendió mi pregunta" (PropertyAgent)              │        │
│  │  - "Falta información de costes" (NumbersAgent)           │        │
│  │  - [Click to see full conversation]                        │        │
│  └────────────────────────────────────────────────────────────┘        │
└──────────────────────────────────────────────────────────────────────────┘
                                  ↓
┌──────────────────────────────────────────────────────────────────────────┐
│                        CONTINUOUS LEARNING LOOP                          │
│                                                                          │
│  1. Weekly review of negative feedback                                  │
│  2. Identify top 3 failure patterns                                     │
│  3. Update prompts / tool descriptions                                  │
│  4. Measure improvement in next week                                    │
│  5. Repeat                                                              │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 🔄 Data Flow: Step-by-Step

### Step 1: User Interaction
```
User → Frontend (Next.js) → Backend (FastAPI) → Agent
```

### Step 2: Agent Processing
```python
# BaseAgent.run() - Already implemented
response = llm_with_tools.invoke(messages)
tool_calls = response.tool_calls  # ← Captured

return {
    "agent": self.name,
    "response": response.content,
    "tool_calls": tool_calls,
    "success": True
}
```

### Step 3: Response Display + Feedback UI
```tsx
// ChatMessage.tsx - NEW
<div className="agent-message">
  <p>{response}</p>
  
  {/* NEW: Feedback buttons */}
  <div className="feedback-buttons">
    <button onClick={() => handleFeedback(1)}>👍</button>
    <button onClick={() => handleFeedback(-1)}>👎</button>
  </div>
  
  {/* NEW: Comment box (shows on 👎) */}
  {showCommentBox && (
    <textarea 
      placeholder="¿Qué salió mal?" 
      onChange={(e) => setComment(e.target.value)}
    />
  )}
</div>
```

### Step 4: Store Feedback (Synchronous)
```python
# POST /api/feedback
@app.post("/api/feedback")
def submit_feedback(
    message_id: str,
    rating: int,  # -1 or 1
    comment: Optional[str] = None
):
    # Store in Supabase agent_feedback
    supabase.table("agent_feedback").insert({
        "message_id": message_id,
        "rating": rating,
        "comment": comment,
        # ... other fields
    }).execute()
    
    # Trigger async eval pipeline
    trigger_eval_pipeline(message_id)
```

### Step 5: Async Evaluation Pipeline
```python
# tools/eval_pipeline.py - NEW
async def eval_pipeline(message_id: str):
    # Fetch conversation data
    feedback = get_feedback(message_id)
    
    # Layer 2: Tool Selection Eval
    tool_eval = evaluate_tool_selection(
        user_message=feedback["user_message"],
        tool_calls=feedback["tool_calls"],
        agent_name=feedback["agent_name"]
    )
    
    # Layer 3: Response Quality (LLM-as-Judge)
    response_eval = judge_response_quality(
        user_message=feedback["user_message"],
        agent_response=feedback["agent_response"],
        tool_calls=feedback["tool_calls"]
    )
    
    # Layer 4: Task Success (Verifier)
    task_eval = verify_task_success(
        property_id=feedback["property_id"],
        tool_calls=feedback["tool_calls"]
    )
    
    # Update feedback row with eval results
    update_feedback(message_id, {
        "tool_eval": tool_eval,
        "response_eval": response_eval,
        "task_success_eval": task_eval
    })
```

---

## 🧩 Component Breakdown

### 🎨 Frontend (Next.js)

#### New Component: `ChatMessage.tsx`
```tsx
interface ChatMessageProps {
  message: {
    id: string;
    role: "user" | "assistant";
    content: string;
    agent?: string;
  };
}

export function ChatMessage({ message }: ChatMessageProps) {
  const [rating, setRating] = useState<number | null>(null);
  const [comment, setComment] = useState("");
  const [showCommentBox, setShowCommentBox] = useState(false);
  
  const handleFeedback = async (value: 1 | -1) => {
    setRating(value);
    
    if (value === -1) {
      setShowCommentBox(true);
    } else {
      // Submit immediately for 👍
      await submitFeedback(message.id, value, null);
    }
  };
  
  const submitFeedback = async (
    messageId: string, 
    rating: number, 
    comment: string | null
  ) => {
    await fetch("/api/feedback", {
      method: "POST",
      body: JSON.stringify({ 
        message_id: messageId, 
        rating, 
        comment 
      })
    });
    
    // Show confirmation
    toast.success("¡Gracias por tu feedback!");
  };
  
  return (
    <div className="message">
      <Markdown>{message.content}</Markdown>
      
      {message.role === "assistant" && (
        <div className="feedback-section">
          <button 
            onClick={() => handleFeedback(1)}
            disabled={rating !== null}
          >
            👍
          </button>
          <button 
            onClick={() => handleFeedback(-1)}
            disabled={rating !== null}
          >
            👎
          </button>
          
          {showCommentBox && (
            <div className="comment-box">
              <textarea 
                placeholder="¿Qué podríamos mejorar?"
                value={comment}
                onChange={(e) => setComment(e.target.value)}
              />
              <button 
                onClick={() => submitFeedback(message.id, rating!, comment)}
              >
                Enviar
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
```

---

### ⚙️ Backend (FastAPI)

#### New Endpoint: `/api/feedback`
```python
# app.py
from pydantic import BaseModel
from typing import Optional

class FeedbackRequest(BaseModel):
    message_id: str
    rating: int  # -1 or 1
    comment: Optional[str] = None
    property_id: Optional[str] = None

@app.post("/api/feedback")
async def submit_feedback(req: FeedbackRequest):
    """Store user feedback and trigger eval pipeline"""
    
    # 1. Store feedback
    result = supabase.table("agent_feedback").insert({
        "message_id": req.message_id,
        "rating": req.rating,
        "comment": req.comment,
        "property_id": req.property_id,
        "created_at": datetime.now().isoformat()
    }).execute()
    
    feedback_id = result.data[0]["id"]
    
    # 2. Trigger async evaluation (background task)
    from tools.eval_pipeline import eval_pipeline
    background_tasks.add_task(eval_pipeline, feedback_id)
    
    # 3. Return confirmation
    return {
        "ok": True,
        "feedback_id": feedback_id,
        "message": "Feedback recibido. Gracias!"
    }
```

---

### 🗄️ Database Schema

```sql
-- migrations/2025-01-21_agent_feedback.sql
CREATE TABLE agent_feedback (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  
  -- Context
  property_id UUID REFERENCES properties(id),
  user_id TEXT,
  message_id TEXT NOT NULL UNIQUE,
  agent_name TEXT NOT NULL,
  
  -- Conversation data
  user_message TEXT NOT NULL,
  agent_response TEXT NOT NULL,
  tool_calls JSONB DEFAULT '[]',
  
  -- User feedback (Layer 1)
  rating INT CHECK (rating IN (-1, 1)),  -- -1 = 👎, 1 = 👍
  comment TEXT,
  
  -- Automated evals (Layers 2-4, populated async)
  tool_eval JSONB,  
  -- {
  --   "accuracy": 0.9,
  --   "precision": 1.0,
  --   "expected_tools": ["add_property"],
  --   "actual_tools": ["add_property"],
  --   "latency_ms": 234
  -- }
  
  response_eval JSONB,
  -- {
  --   "relevance": 1.0,
  --   "completeness": 0.9,
  --   "accuracy": 1.0,
  --   "tone": 0.95,
  --   "overall": 0.96,
  --   "reasoning": "Response addressed request fully..."
  -- }
  
  task_success_eval JSONB,
  -- {
  --   "success": true,
  --   "verification_steps": [
  --     {"check": "property_exists", "passed": true},
  --     {"check": "frameworks_provisioned", "passed": true}
  --   ],
  --   "failures": []
  -- }
  
  -- Timestamps
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for fast queries
CREATE INDEX idx_agent_feedback_property ON agent_feedback(property_id);
CREATE INDEX idx_agent_feedback_agent ON agent_feedback(agent_name);
CREATE INDEX idx_agent_feedback_rating ON agent_feedback(rating);
CREATE INDEX idx_agent_feedback_created ON agent_feedback(created_at DESC);
CREATE INDEX idx_agent_feedback_message ON agent_feedback(message_id);

-- RLS policies (multi-tenant support)
ALTER TABLE agent_feedback ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view their own feedback" 
  ON agent_feedback FOR SELECT 
  USING (auth.uid()::text = user_id);

CREATE POLICY "Users can insert their own feedback" 
  ON agent_feedback FOR INSERT 
  WITH CHECK (auth.uid()::text = user_id);
```

---

### 🤖 Evaluation Modules

#### 1. Tool Selection Evaluator
```python
# tools/eval_tool_selection.py - NEW
from typing import List, Dict

def evaluate_tool_selection(
    user_message: str,
    tool_calls: List[Dict],
    agent_name: str
) -> Dict:
    """Evaluate if agent selected correct tools"""
    
    # 1. Classify intent (use LLM or pattern matching)
    intent = classify_intent(user_message)
    
    # 2. Get expected tools for intent
    from tools.eval_registry import EXPECTED_TOOLS_BY_INTENT
    expected_tools = EXPECTED_TOOLS_BY_INTENT.get(intent, [])
    
    # 3. Get actual tools called
    actual_tools = [tc["name"] for tc in tool_calls]
    
    # 4. Calculate metrics
    correct_tools = set(expected_tools) & set(actual_tools)
    accuracy = len(correct_tools) / len(expected_tools) if expected_tools else 1.0
    precision = len(correct_tools) / len(actual_tools) if actual_tools else 0.0
    
    return {
        "accuracy": accuracy,
        "precision": precision,
        "expected_tools": expected_tools,
        "actual_tools": actual_tools,
        "intent": intent
    }
```

#### 2. LLM-as-Judge Response Quality
```python
# tools/eval_response_quality.py - NEW
from langchain_openai import ChatOpenAI
import json

JUDGE_PROMPT = """You are an expert evaluator for an AI real estate assistant.

USER REQUEST: {user_message}
AGENT RESPONSE: {agent_response}
TOOLS USED: {tool_calls}

Evaluate the agent's response on these criteria (0-1 scale):
1. Relevance: Did it address the user's request?
2. Completeness: Did it provide necessary information?
3. Accuracy: Is the information correct?
4. Tone: Is it professional and friendly?

Output ONLY valid JSON:
{{
  "relevance": 0.0-1.0,
  "completeness": 0.0-1.0,
  "accuracy": 0.0-1.0,
  "tone": 0.0-1.0,
  "overall": 0.0-1.0,
  "reasoning": "..."
}}
"""

def judge_response_quality(
    user_message: str,
    agent_response: str,
    tool_calls: List[Dict]
) -> Dict:
    """Use GPT-4o as judge to evaluate response quality"""
    
    llm = ChatOpenAI(model="gpt-4o", temperature=0)
    
    prompt = JUDGE_PROMPT.format(
        user_message=user_message,
        agent_response=agent_response,
        tool_calls=json.dumps(tool_calls, indent=2)
    )
    
    response = llm.invoke(prompt)
    
    # Parse JSON response
    try:
        scores = json.loads(response.content)
        return scores
    except:
        # Fallback if parsing fails
        return {
            "relevance": 0.5,
            "completeness": 0.5,
            "accuracy": 0.5,
            "tone": 0.5,
            "overall": 0.5,
            "reasoning": "Failed to parse judge response"
        }
```

#### 3. Task Success Verifier
```python
# tools/verifier.py - EXTEND EXISTING
def verify_task_success(
    property_id: str,
    tool_calls: List[Dict]
) -> Dict:
    """Verify task completed successfully in system"""
    
    verification_steps = []
    failures = []
    
    for tool_call in tool_calls:
        tool_name = tool_call["name"]
        
        # Route to specific verifier
        if tool_name == "add_property":
            result = verify_property_creation(property_id)
        elif tool_name == "set_numbers_table_cell":
            result = verify_cell_update(property_id, tool_call["args"])
        elif tool_name == "upload_and_link":
            result = verify_document_upload(property_id, tool_call["args"])
        else:
            result = {"check": tool_name, "passed": True, "note": "No verifier"}
        
        verification_steps.append(result)
        
        if not result["passed"]:
            failures.append(result)
    
    return {
        "success": len(failures) == 0,
        "verification_steps": verification_steps,
        "failures": failures
    }
```

---

## 📊 Dashboard Integration

### New Tab: `/dashboard/evals`

```tsx
// web/src/app/dashboard/evals/page.tsx - NEW
export default async function EvalsPage() {
  const data = await fetch("/api/dashboard/evals?time_range=7d");
  const metrics = await data.json();
  
  return (
    <div className="dashboard-evals">
      <h1>📊 Agent Evaluations</h1>
      
      {/* KPI Cards */}
      <div className="kpi-grid">
        <KPICard 
          title="User Satisfaction" 
          value={`${metrics.satisfaction_rate}%`}
          icon="👍"
        />
        <KPICard 
          title="Tool Accuracy" 
          value={`${metrics.tool_accuracy}%`}
          icon="🎯"
        />
        <KPICard 
          title="Response Quality" 
          value={metrics.avg_response_quality.toFixed(2)}
          icon="📝"
        />
        <KPICard 
          title="Task Success" 
          value={`${metrics.task_success_rate}%`}
          icon="✅"
        />
      </div>
      
      {/* Trends Chart */}
      <LineChart 
        data={metrics.trends}
        title="Satisfaction Rate (7 days)"
      />
      
      {/* Recent Negative Feedback */}
      <FeedbackTable 
        data={metrics.negative_feedback}
        onClickRow={(id) => router.push(`/dashboard/evals/${id}`)}
      />
    </div>
  );
}
```

---

## 🔄 Continuous Learning Loop

```
┌──────────────────────────────────────────────────┐
│  1. Collect Data (agent_feedback table)         │
│     - 100+ conversations/week                    │
└──────────────────────────────────────────────────┘
                    ↓
┌──────────────────────────────────────────────────┐
│  2. Weekly Analysis                              │
│     - Filter rating=-1 (thumbs down)            │
│     - Group by agent_name, tool_calls           │
│     - Identify top 3 failure patterns           │
└──────────────────────────────────────────────────┘
                    ↓
┌──────────────────────────────────────────────────┐
│  3. Root Cause Analysis                          │
│     Example patterns:                            │
│     - "PropertyAgent confuses search/list"      │
│     - "NumbersAgent doesn't auto-calc D5"       │
│     - "DocsAgent can't find uploaded files"     │
└──────────────────────────────────────────────────┘
                    ↓
┌──────────────────────────────────────────────────┐
│  4. Implement Fixes                              │
│     - Update system prompts                      │
│     - Clarify tool descriptions                  │
│     - Add examples to prompts                    │
│     - Fix actual bugs if found                   │
└──────────────────────────────────────────────────┘
                    ↓
┌──────────────────────────────────────────────────┐
│  5. Measure Improvement                          │
│     - Compare satisfaction rate week-over-week  │
│     - Target: +5% per iteration                 │
│     - If no improvement, rollback and try again │
└──────────────────────────────────────────────────┘
                    ↓
                 REPEAT
```

---

## ✅ Summary

**4-Layer Evaluation System**:
1. 👍/👎 User Feedback (real-time, manual)
2. 🎯 Tool Selection Eval (automated, rule-based)
3. 📝 Response Quality (automated, LLM-as-Judge)
4. ✅ Task Success (automated, verifier)

**MVP (Week 1)**: Just Layer 1 (user feedback)
**Full (Weeks 2-6)**: All 4 layers + dashboard + continuous learning

**Decision Point**: Start with MVP, evaluate after 2 weeks, then decide on full plan.

---

**Ready to implement MVP?** 🚀

