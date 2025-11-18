# 🔄 Multi-Agent System Integration Guide

## ✅ Integration Complete

The multi-agent routing system is now integrated into `app.py` and ready to use!

---

## 🚀 How to Enable

### Option 1: Environment Variable (Recommended)

Add to your `.env` file:
```bash
USE_MULTI_AGENT=1
```

Then restart the backend:
```bash
cd /Users/mariasebares/Documents/RAMA_AI/rama-agentic-ai
.venv/bin/uvicorn app:app --reload --port 7901
```

### Option 2: Temporarily Enable
```bash
USE_MULTI_AGENT=1 .venv/bin/uvicorn app:app --reload --port 7901
```

---

## 📊 What Happens When Enabled

### Before (USE_MULTI_AGENT=0):
```
User Input → Old Router (log-only) → MainAgent (LangGraph) → Response
```

### After (USE_MULTI_AGENT=1):
```
User Input → OrchestrationRouter → Intent Classification → Agent Selection
                                                              ↓
                    ┌─────────────────────────────────────────┤
                    │                                         │
                    ▼                                         ▼
            Specialized Agent                          MainAgent (fallback)
            (if high confidence)                       (if low confidence)
                    │                                         │
                    └─────────────────────────────────────────┤
                                                              ↓
                                         MainAgent (LangGraph) → Response
```

**Note**: Phase 2a routes to agents but still executes through MainAgent (LangGraph).  
Phase 2b (future) will have specialized agents execute directly.

---

## 🎯 Routing Examples

### Example 1: Numbers Operation (High Confidence)
```
User: "pon B5 en 1000"
→ OrchestrationRouter detects: intent=numbers.set_cell, confidence=0.95
→ Routes to: NumbersAgent
→ Logs: [ORCHESTRATOR] agent=NumbersAgent, intent=numbers.set_cell, conf=0.95
→ Executes through MainAgent (for now)
```

### Example 2: Property Operation
```
User: "lista mis propiedades"
→ OrchestrationRouter detects: intent=property.list, confidence=0.92
→ Routes to: PropertyAgent
→ Logs: [ORCHESTRATOR] agent=PropertyAgent, intent=property.list, conf=0.92
```

### Example 3: Low Confidence (Fallback)
```
User: "ayuda"
→ OrchestrationRouter detects: intent=general.help, confidence=0.75
→ Routes to: MainAgent (fallback)
→ Logs: [ORCHESTRATOR] agent=MainAgent, fallback=low_confidence
```

### Example 4: Multi-Domain (Escalate)
```
User: "crea propiedad y pon B5 en 1000"
→ OrchestrationRouter detects: multi-domain task
→ Routes to: MainAgent (can handle multiple domains)
→ Logs: [ORCHESTRATOR] agent=MainAgent, reason=multi_domain
```

---

## 📋 Logs to Watch

When `USE_MULTI_AGENT=1`, you'll see these logs in the backend:

```
[ORCHESTRATOR] Routing result: routed, agent=NumbersAgent, intent=numbers.set_cell, conf=0.95
[MEMORY DEBUG] Invoking agent with thread_id=web-ui, input=pon B5 en 1000
```

---

## 🔍 Metrics Tracked

The orchestrator automatically logs these metrics to `data/metrics.db`:

| Metric | Description |
|--------|-------------|
| `orchestrator.route` | Each routing decision (intent, confidence, agent) |
| `orchestrator.skip_routing` | When routing is skipped (use_main_agent=True) |
| `orchestrator.error` | Routing errors |

View metrics at: `http://localhost:3000/dev/metrics`

---

## 🧪 Testing Multi-Agent Routing

### Test 1: Numbers Agent
```bash
# In your chat
User: "pon B5 en 1000"

# Expected log:
[ORCHESTRATOR] agent=NumbersAgent, intent=numbers.set_cell, conf=0.95
```

### Test 2: Property Agent
```bash
User: "lista propiedades"

# Expected log:
[ORCHESTRATOR] agent=PropertyAgent, intent=property.list, conf=0.92
```

### Test 3: Docs Agent
```bash
User: "sube este contrato"

# Expected log:
[ORCHESTRATOR] agent=DocsAgent, intent=docs.upload, conf=0.92
```

### Test 4: Fallback to MainAgent
```bash
User: "qué puedes hacer?"

# Expected log:
[ORCHESTRATOR] agent=MainAgent, fallback=low_confidence
```

---

## 🔧 Debugging

### Check if multi-agent is enabled:
```bash
# In backend logs, look for:
[ORCHESTRATOR] Routing result: ...
```

If you don't see this, check:
1. Is `USE_MULTI_AGENT=1` in `.env`?
2. Did you restart the backend?
3. Are you sending text input (not empty)?

### Common Issues

**Issue**: "OrchestrationRouter not found"  
**Fix**: Make sure you're on the latest code: `git pull origin main`

**Issue**: No routing logs appear  
**Fix**: Check `USE_MULTI_AGENT` is set to `1` (not `"1"` with quotes in .env)

**Issue**: Agent always routes to MainAgent  
**Fix**: This is expected for ambiguous queries or low confidence. Try specific commands like "pon B5 en 1000"

---

## 📈 Performance Impact

### Expected Improvements (Phase 2b - when agents execute directly):
- **Latency**: -30% to -40% (fewer tools loaded)
- **Accuracy**: +10% to +15% (focused prompts)
- **Context clarity**: Significantly better

### Current Phase 2a (routing only):
- **Latency**: +10-20ms (routing overhead)
- **Accuracy**: Same (still using MainAgent)
- **Observability**: Much better (intent + confidence logged)

---

## 🎯 Roadmap

### Phase 2a: Routing (✅ CURRENT)
- ✅ Intent classification
- ✅ Agent selection
- ✅ Confidence scoring
- ✅ Metrics tracking
- ⏳ Still executes through MainAgent

### Phase 2b: Specialized Execution (NEXT)
- ⏳ PropertyAgent executes directly
- ⏳ NumbersAgent executes directly
- ⏳ DocsAgent executes directly
- ⏳ Bidirectional routing loop
- ⏳ True latency improvements

### Phase 2c: Optimization (FUTURE)
- ⏳ Parallel agent execution
- ⏳ Agent collaboration
- ⏳ Dynamic agent loading
- ⏳ Agent performance profiling

---

## 🔄 Rollback Plan

If you need to disable multi-agent routing:

1. **Quick disable**:
   ```bash
   # Set in .env
   USE_MULTI_AGENT=0
   
   # Restart backend
   ```

2. **Emergency disable** (if .env doesn't work):
   ```bash
   # Comment out in app.py line ~846
   # if os.getenv("USE_MULTI_AGENT", "0") == "1" and text:
   if False and text:  # Temporary disable
   ```

---

## 📚 Related Documentation

- **Architecture**: `docs/MULTI_AGENT_TOPOLOGY.md`
- **Bidirectional Routing**: `docs/BIDIRECTIONAL_ROUTING.md`
- **Review**: `docs/REVIEW_COMPLETO_2025.md`
- **Tests**: `tests/test_bidirectional_routing.py` (23/23 passing)

---

## ✅ Checklist for Enabling

- [ ] Add `USE_MULTI_AGENT=1` to `.env`
- [ ] Restart backend
- [ ] Test with "pon B5 en 1000"
- [ ] Check logs for `[ORCHESTRATOR]` messages
- [ ] Verify metrics at `/dev/metrics`
- [ ] Monitor for any errors
- [ ] If issues, set back to `0`

---

**Status**: ✅ Ready for testing  
**Last Updated**: January 2025 (Sprint 2 Phase 2a)

