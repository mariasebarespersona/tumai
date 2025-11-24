# RAMA AI Documentation

**Welcome to the RAMA AI documentation hub!**

This directory contains comprehensive documentation for developers, stakeholders, and operators.

---

## 📚 Documentation Index

### **🏗️ Architecture & Design**

#### 1. **[TECHNICAL_ARCHITECTURE.md](./TECHNICAL_ARCHITECTURE.md)** (⭐ Start Here)
**100+ pages | For: Developers, Architects**

Complete technical documentation covering:
- Tech stack (Python, TypeScript, LangGraph, PostgreSQL)
- System architecture with detailed Mermaid diagrams
- Core components deep dive (FastAPI, LangGraph, Agents)
- Agent architecture (BaseAgent, ReAct loops, specialized agents)
- Routing system (ActiveRouter + Orchestrator)
- Modular prompt system (architecture, benefits, examples)
- Data flow with sequence diagrams
- Database schema and persistence
- Frontend architecture (Next.js, React, Tailwind)
- Deployment (Render, Vercel, env vars)
- Performance & scalability analysis
- Security considerations

**Use this when:**
- Onboarding new developers
- Conducting architecture reviews
- Planning system improvements
- Debugging complex issues

---

#### 2. **[ARCHITECTURE_VISUAL_GUIDE.md](./ARCHITECTURE_VISUAL_GUIDE.md)** (⭐ For Presentations)
**Visual reference | For: Stakeholders, Technical Presentations**

Quick reference guide with:
- One-page system overview
- 9 Mermaid diagrams (architecture, flows, routing)
- Tech stack comparison tables
- Performance metrics & cost analysis
- Security checklist
- Frontend design system
- Debugging tips
- Quick start guide

**Use this when:**
- Presenting to executives/stakeholders
- Technical demos
- Team onboarding (visual learners)
- Quick reference during development

---

### **🚀 Deployment & Operations**

#### 3. **[DEPLOY_RENDER.md](./DEPLOY_RENDER.md)**
**Backend deployment guide**

Step-by-step instructions for deploying the FastAPI backend to Render.

---

#### 4. **[DEPLOY_VERCEL.md](./DEPLOY_VERCEL.md)**
**Frontend deployment guide**

Step-by-step instructions for deploying the Next.js frontend to Vercel.

---

#### 5. **[DEPLOYMENT_CHECKLIST.md](../DEPLOYMENT_CHECKLIST.md)**
**Pre-deployment checklist**

Complete checklist before going to production.

---

#### 6. **[OPS.md](./OPS.md)**
**Operations runbook**

Day-to-day operational procedures, monitoring, and troubleshooting.

---

### **📊 Evaluation & Quality**

#### 7. **[EVALUATION_ARCHITECTURE.md](./EVALUATION_ARCHITECTURE.md)**
**Evaluation pipeline design**

Architecture for automated agent evaluation (tool selection, response quality, task success).

---

#### 8. **[EVALUATION_STRATEGY.md](./EVALUATION_STRATEGY.md)**
**Evaluation methodology**

Strategy and metrics for continuous agent improvement.

---

#### 9. **[EVALUATION_QUICK_START.md](./EVALUATION_QUICK_START.md)**
**Evaluation setup guide**

How to set up and use the evaluation pipeline.

---

### **👥 User Guides**

#### 10. **[USER_FLOWS.md](../USER_FLOWS.md)**
**End-user workflows**

Common user workflows and expected agent behavior.

---


### **🔧 Features & Integrations**

#### 12. **[MULTI_AGENT_TOPOLOGY.md](./MULTI_AGENT_TOPOLOGY.md)**
**Multi-agent system design**

Overview of specialized agents and routing strategy.

---

#### 13. **[BIDIRECTIONAL_ROUTING.md](./BIDIRECTIONAL_ROUTING.md)**
**Bidirectional routing**

How agents can redirect/escalate to other agents.

---

#### 14. **[GRAPH_MODE.md](./GRAPH_MODE.md)**
**LangGraph mode**

Using LangGraph for stateful agent orchestration.

---

#### 15. **[LOGFIRE_SETUP.md](./LOGFIRE_SETUP.md)**
**Observability setup**

How to configure Logfire for LLM tracing and monitoring.

---

## 🎯 Quick Navigation

### I want to...

| Goal | Document |
|------|----------|
| **Understand the full system** | [TECHNICAL_ARCHITECTURE.md](./TECHNICAL_ARCHITECTURE.md) |
| **Prepare a presentation** | [ARCHITECTURE_VISUAL_GUIDE.md](./ARCHITECTURE_VISUAL_GUIDE.md) |
| **Deploy to production** | [DEPLOY_RENDER.md](./DEPLOY_RENDER.md) + [DEPLOY_VERCEL.md](./DEPLOY_VERCEL.md) |
| **Debug an issue** | [ARCHITECTURE_VISUAL_GUIDE.md](./ARCHITECTURE_VISUAL_GUIDE.md) (Debugging Tips section) |
| **Onboard a developer** | [TECHNICAL_ARCHITECTURE.md](./TECHNICAL_ARCHITECTURE.md) + [ARCHITECTURE_VISUAL_GUIDE.md](./ARCHITECTURE_VISUAL_GUIDE.md) |
| **Set up evaluation** | [EVALUATION_QUICK_START.md](./EVALUATION_QUICK_START.md) |
| **Monitor production** | [OPS.md](./OPS.md) + [LOGFIRE_SETUP.md](./LOGFIRE_SETUP.md) |
| **Understand user flows** | [USER_FLOWS.md](../USER_FLOWS.md) |
| **Add new feature** | [TECHNICAL_ARCHITECTURE.md](./TECHNICAL_ARCHITECTURE.md) (Modular Prompt System section) |

---

## 📖 Reading Order for New Developers

1. **Start:** [ARCHITECTURE_VISUAL_GUIDE.md](./ARCHITECTURE_VISUAL_GUIDE.md) (30 min)
   - Get high-level overview
   - Understand key components
   - See visual diagrams

2. **Deep Dive:** [TECHNICAL_ARCHITECTURE.md](./TECHNICAL_ARCHITECTURE.md) (2-3 hours)
   - Read section by section
   - Understand implementation details
   - Follow code references

3. **Setup:** [DEPLOY_RENDER.md](./DEPLOY_RENDER.md) + [DEPLOY_VERCEL.md](./DEPLOY_VERCEL.md) (1 hour)
   - Set up local environment
   - Deploy to staging

4. **Practice:** [USER_FLOWS.md](../USER_FLOWS.md) (30 min)
   - Test common workflows
   - Understand expected behavior

5. **Advanced:** [MULTI_AGENT_TOPOLOGY.md](./MULTI_AGENT_TOPOLOGY.md) + [EVALUATION_ARCHITECTURE.md](./EVALUATION_ARCHITECTURE.md) (1 hour)
   - Understand advanced features
   - Learn about evaluation pipeline

**Total Time:** ~5-6 hours for complete onboarding

---

## 🆘 Getting Help

### Internal Resources
1. **Check documentation** (this folder)
2. **Check code comments** (especially in `agentic.py`, `base_agent.py`)
3. **Check Logfire dashboard** (for runtime issues)
4. **Check GitHub Issues** (for known bugs)

### External Resources
- **LangGraph Docs:** https://langchain-ai.github.io/langgraph/
- **FastAPI Docs:** https://fastapi.tiangolo.com/
- **Next.js Docs:** https://nextjs.org/docs
- **Supabase Docs:** https://supabase.com/docs

### Contact
- **Team Lead:** [Your Name]
- **DevOps:** [Your Name]
- **GitHub:** https://github.com/mariasebarespersona/tumai

---

## 🔄 Keeping Documentation Updated

### When to Update

| Change | Update These Docs |
|--------|-------------------|
| **New agent added** | TECHNICAL_ARCHITECTURE.md, ARCHITECTURE_VISUAL_GUIDE.md, MULTI_AGENT_TOPOLOGY.md |
| **New tool added** | TECHNICAL_ARCHITECTURE.md (Agent Architecture section) |
| **Deployment change** | DEPLOY_*.md, DEPLOYMENT_CHECKLIST.md |
| **New feature** | TECHNICAL_ARCHITECTURE.md, USER_FLOWS.md |
| **Architecture change** | TECHNICAL_ARCHITECTURE.md, ARCHITECTURE_VISUAL_GUIDE.md |
| **Performance optimization** | TECHNICAL_ARCHITECTURE.md (Performance section) |
| **Security update** | TECHNICAL_ARCHITECTURE.md (Security section) |

### Documentation Standards

1. **Diagrams:** Use Mermaid (renders in GitHub)
2. **Code examples:** Use syntax highlighting
3. **Tables:** Use Markdown tables for comparisons
4. **Links:** Use relative links within docs/
5. **Versioning:** Update "Last Updated" date at top of doc

---

## 📝 Documentation Style Guide

### Headings
```markdown
# H1 - Document Title
## H2 - Major Sections
### H3 - Subsections
#### H4 - Details
```

### Code Blocks
```markdown
\`\`\`python
def example():
    return "Use language tags"
\`\`\`
```

### Tables
```markdown
| Column 1 | Column 2 | Column 3 |
|----------|----------|----------|
| Value 1  | Value 2  | Value 3  |
```

### Diagrams
```markdown
\`\`\`mermaid
graph TB
    A[Start] --> B[End]
\`\`\`
```

### Callouts
```markdown
**Note:** Important information
⚠️ **Warning:** Critical warning
✅ **Success:** Positive indicator
❌ **Error:** Problem indicator
```

---

## 📊 Documentation Metrics

| Document | Pages | Words | Last Updated | Status |
|----------|-------|-------|--------------|--------|
| TECHNICAL_ARCHITECTURE.md | 100+ | 15,000+ | Nov 2024 | ✅ Complete |
| ARCHITECTURE_VISUAL_GUIDE.md | 40+ | 8,000+ | Nov 2024 | ✅ Complete |
| DEPLOY_RENDER.md | 5 | 1,000+ | Nov 2024 | ✅ Complete |
| DEPLOY_VERCEL.md | 5 | 1,000+ | Nov 2024 | ✅ Complete |
| EVALUATION_*.md | 20+ | 5,000+ | Nov 2024 | ✅ Complete |
| USER_FLOWS.md | 10+ | 2,000+ | Nov 2024 | ✅ Complete |

**Total Documentation:** ~180 pages, ~30,000 words

---

## 🎯 Documentation Goals

- ✅ **Comprehensive:** Cover all aspects of the system
- ✅ **Accessible:** Easy to find and navigate
- ✅ **Visual:** Diagrams and tables for clarity
- ✅ **Practical:** Real examples and use cases
- ✅ **Up-to-date:** Reflect current implementation
- ✅ **Scalable:** Easy to extend as system grows

---

**Last Updated:** November 2024  
**Maintained By:** RAMA AI Team  
**License:** Proprietary
