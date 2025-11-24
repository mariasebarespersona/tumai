# RAMA AI - Agentic Property Management Assistant

<div align="center">

![RAMA Country Living](web/public/rama-logo.png)

**AI-powered conversational assistant for rural property investment management**

[![Live Demo](https://img.shields.io/badge/🌐_Live_Demo-Vercel-black?style=for-the-badge)](https://rama-agentic-ai.vercel.app)
[![Backend API](https://img.shields.io/badge/⚡_API-Render-46E3B7?style=for-the-badge)](https://rama-backend.onrender.com)
[![Documentation](https://img.shields.io/badge/📚_Docs-Technical-blue?style=for-the-badge)](docs/TECHNICAL_ARCHITECTURE.md)

</div>

---

## 🎯 What is RAMA AI?

RAMA AI is an intelligent assistant that helps real estate teams manage property portfolios through **natural conversation**. Built with LangGraph and GPT-4o, it automates:

- 📄 **Document Management** - Upload, organize, and chat with property documents (RAG Q&A)
- 🔢 **Financial Analysis** - Excel-like number crunching with AI (scenarios, break-even, ROI)
- 📊 **Professional Reports** - Generate investor-ready PDFs with charts and summaries
- ✉️ **Email Automation** - Share documents, Excel exports, and reports instantly
- 🗣️ **Voice Support** - Speech-to-text and text-to-speech for hands-free interaction

**Use Case:** Complete property investment analysis in minutes instead of days.

---

## 🚀 Quick Access

### 🌐 **Live Application**

| Service | URL | Description |
|---------|-----|-------------|
| **Frontend** | [rama-agentic-ai.vercel.app](https://rama-agentic-ai.vercel.app) | Next.js chat interface |
| **Backend API** | [rama-backend.onrender.com](https://rama-backend.onrender.com) | FastAPI + LangGraph agents |

> **Note:** First request may take 30s (Render free tier cold start)

---

## 🏗️ Architecture

```mermaid
graph LR
    %% Styles
    classDef frontend fill:#dbfafe,stroke:#0ea5e9,stroke-width:2px,color:#000;
    classDef backend fill:#fef3c7,stroke:#d97706,stroke-width:2px,color:#000;
    classDef ailayer fill:#dcfce7,stroke:#22c55e,stroke-width:2px,color:#000;
    classDef data fill:#fee2e2,stroke:#ef4444,stroke-width:2px,color:#000;
    classDef external fill:#f3f4f6,stroke:#6b7280,stroke-width:2px,color:#000;

    subgraph Frontend [Frontend]
        direction TB
        UI[UI<br/>Next.js + React<br/>Tailwind CSS]:::frontend
    end

    subgraph Backend [Backend]
        direction TB
        API[API<br/>FastAPI<br/>Python 3.11]:::backend
        Router[Intent Router<br/>Active Router]:::backend
        Spec[Spec<br/>Supabase<br/>Storage]:::backend
        
        API --- Router
        Router --- Spec
    end

    subgraph AILayer [AI Layer]
        direction TB
        MainAgent[MainAgent<br/>LangGraph]:::ailayer
        Specialized[Specialized<br/>Agents<br/>ReAct Loops]:::ailayer
        
        MainAgent --- Specialized
    end

    subgraph Data [Data]
        direction TB
        DB[DB<br/>Supabase<br/>PostgreSQL]:::data
    end

    subgraph External [External]
        direction TB
        OpenAI[OpenAI<br/>GPT-4o]:::external
        Log[Log<br/>Logfire<br/>Observability]:::external
    end

    %% Connections matching your diagram
    UI -->|REST API| API
    API --> MainAgent
    Router --> Specialized
    Spec --> DB

    %% Styling for subgraphs
    style Frontend fill:#eff6ff,stroke:#3b82f6,stroke-dasharray: 5 5
    style Backend fill:#fffbeb,stroke:#f59e0b,stroke-dasharray: 5 5
    style AILayer fill:#f0fdf4,stroke:#22c55e,stroke-dasharray: 5 5
    style Data fill:#fef2f2,stroke:#ef4444,stroke-dasharray: 5 5
    style External fill:#f9fafb,stroke:#9ca3af,stroke-dasharray: 5 5
```

### System Overview

### Key Components

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Frontend** | Next.js 14 + TypeScript + Tailwind | Chat UI, file upload, voice recording |
| **Backend** | FastAPI + Python 3.11 | REST API, agent orchestration |
| **AI Layer** | LangGraph + GPT-4o | Multi-agent coordination with ReAct loops |
| **Intent Router** | Active Router (classification) | Routes user queries to correct agent |
| **Database** | Supabase PostgreSQL | Property data, documents metadata, numbers |
| **Storage** | Supabase Storage | PDF/DOCX files, generated charts |
| **Observability** | Pydantic Logfire | Real-time tracing, metrics, debugging |
| **Deployment** | Vercel (frontend) + Render (backend) | Zero-config CI/CD |

---

## 🧠 What Makes RAMA AI Unique?

### 1. **Multi-Agent with ReAct Loops**
Each specialized agent uses **ReAct (Reason + Act)** loops:
- **Reason:** LLM decides what tool to use
- **Act:** Execute the tool
- **Observe:** Feed results back to LLM
- **Repeat** until task complete

This ensures the AI **always uses tools** when needed (no hallucinations).

### 2. **Intent-Based Routing**
The **ActiveRouter** classifies user intent (e.g., "upload document" → `DocsAgent`) and maintains **conversation continuity** across multi-turn interactions.

### 3. **Modular Prompt System**
Prompts are stored as `.md` files, loaded dynamically by intent:

```
prompts/
  agents/
    docs_agent/
      _base.md           # Base instructions
      send_email.md      # Email-specific flow
      list.md            # Document listing
```

**Benefits:**
- Edit prompts without touching code
- A/B test different instructions
- Version control for prompts

### 4. **PostgreSQL-Backed Memory**
Conversations persist across sessions using LangGraph's **checkpointer** (stored in Supabase):
- Full conversation history retained
- Survives backend restarts
- Multi-turn continuity (e.g., AI asks for email → user provides → AI remembers)

---

## 🛠️ Tech Stack Summary

### Backend
- **LangGraph** - Stateful agent orchestration (StateGraph, checkpointer)
- **LangChain** - Tool calling, LLM integration, RAG
- **FastAPI** - High-performance Python web framework
- **Pydantic** - Data validation (BaseModel)
- **Supabase SDK** - PostgreSQL client, storage, RLS
- **OpenAI SDK** - GPT-4o / GPT-4o-mini API
- **Logfire** - Observability (by Pydantic)

### Frontend
- **Next.js 14** - React with App Router
- **TypeScript** - Type-safe development
- **TailwindCSS** - Utility-first styling
- **React Hooks** - State management

### Data & Storage
- **PostgreSQL** (Supabase) - Multi-schema per property
- **Supabase Storage** - Document storage with signed URLs
- **pgvector** - Vector embeddings for RAG

### AI & ML
- **GPT-4o** - Primary reasoning model
- **GPT-4o-mini** - Lightweight tasks (summaries, embeddings)
- **text-embedding-3-small** - Document embeddings for RAG

### Libraries
- **openpyxl** - Excel generation
- **ReportLab** - PDF generation
- **Plotly + Kaleido** - Charts
- **python-pptx** - PowerPoint (optional)

### DevOps
- **Vercel** - Frontend hosting (Edge CDN)
- **Render** - Backend hosting (Docker)
- **GitHub Actions** - CI/CD
- **Logfire** - Real-time observability

---

## 📊 Dashboard & Metrics

### Real-Time Observability with Pydantic Logfire

RAMA AI integrates **[Pydantic Logfire](https://logfire.pydantic.dev)** for comprehensive observability:

#### 🔍 What We Track

| Metric Category | What's Logged | Use Case |
|-----------------|---------------|----------|
| **Agent Execution** | LLM calls, tool usage, latency (ms) | Debug why agent didn't use a tool |
| **Routing Decisions** | Intent classification, confidence scores | Improve routing accuracy |
| **Tool Performance** | Tool name, inputs, outputs, duration | Identify slow tools |
| **LLM Token Usage** | Prompt tokens, completion tokens, cost | Monitor OpenAI spend |
| **Errors & Exceptions** | Stack traces, context, user session | Debug production issues |
| **Conversation Flow** | User input → agent response → tools called | Replay entire user sessions |

#### 📈 Example Metrics

```
✅ DocsAgent execution:        245ms
   ├─ LLM call (GPT-4o):       180ms (1,234 tokens)
   ├─ Tool: list_docs:          45ms (15 documents)
   └─ Tool: signed_url_for:     20ms (1 URL)

⚠️  NumbersAgent execution:   1,520ms
   ├─ LLM call (GPT-4o):       220ms
   ├─ Tool: get_numbers:        80ms
   └─ Tool: generate_chart:  1,200ms ⚠️ (slow!)
```

#### 🎯 Why This Matters

- **Debug in Production:** See exact LLM prompts and responses for any user session
- **Cost Tracking:** Monitor OpenAI API spend per agent/tool
- **Performance Optimization:** Identify bottlenecks (e.g., chart generation taking 1.2s)
- **User Experience:** Track end-to-end latency from user input to final response

#### 🔗 Access Dashboard

Live metrics dashboard: **[Logfire Console](https://logfire.pydantic.dev)** (requires authentication)

Example queries you can run:
```python
# Find all sessions where DocsAgent failed
filter: agent_name="DocsAgent" AND status="error"

# Track average LLM latency per agent
agg: avg(llm_latency_ms) group_by agent_name

# Calculate OpenAI cost over last 7 days
agg: sum(total_tokens * 0.00001) where date > now() - 7d
```

---

## 📚 Full Documentation

For deep technical details:

| Document | Description |
|----------|-------------|
| [TECHNICAL_ARCHITECTURE.md](docs/TECHNICAL_ARCHITECTURE.md) | 100+ pages: agent architecture, prompts, ReAct loops, routing, database schema |
| [ARCHITECTURE_VISUAL_GUIDE.md](docs/ARCHITECTURE_VISUAL_GUIDE.md) | Visual guide with 9 Mermaid diagrams for presentations |
| [docs/README.md](docs/README.md) | Documentation index and navigation |

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.11+**
- **Node.js 18+**
- **Supabase account** (free tier works)
- **OpenAI API key**

### Quick Start (5 minutes)

#### 1. Clone Repository
```bash
git clone https://github.com/mariasebarespersona/tumai.git
cd rama-agentic-ai
```

#### 2. Backend Setup
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Create `.env`:
```env
OPENAI_API_KEY=sk-...
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJh...
DATABASE_URL=postgresql://postgres:xxx@...
```

Run backend:
```bash
uvicorn app:app --reload --port 7901
```

#### 3. Frontend Setup
```bash
cd web
npm install
```

Create `web/.env.local`:
```env
NEXT_PUBLIC_API_URL=http://127.0.0.1:7901
```

Run frontend:
```bash
npm run dev
```

Visit: **http://localhost:3000**

---

## 💬 Example Conversation

```
User: "Show me my properties"
AI: You have 3 properties: Casa Rural Segovia, Finca Madrid, Casa Toledo

User: "Switch to Casa Rural Segovia"
AI: ✅ Working with Casa Rural Segovia. What would you like to do?

User: "List documents"
AI: [Shows table with ✓ uploaded and ⏳ pending documents]

User: "Upload the title deed"
AI: [File upload prompt appears]

User: "Summarize the architect contract"
AI: [AI-generated summary using RAG]

User: "Show me the numbers"
AI: [Displays financial template with current values]

User: "Set sale price to 250000"
AI: ✅ Sale price updated. Net profit: €45,230 | ROI: 18.5%

User: "Send the numbers by email to investor@example.com"
AI: ✅ Email sent with attachment: numbers_framework.xlsx
```

---

## 🎨 Screenshots

### Chat Interface
![Chat UI](docs/screenshots/chat.png)

### Document Management
![Documents](docs/screenshots/docs.png)

### Numbers Framework
![Numbers](docs/screenshots/numbers.png)

---

## 🔒 Security

- ✅ **Row Level Security (RLS)** enabled on all Supabase tables
- ✅ **Signed URLs** for time-limited document access
- ✅ **Environment variables** for secrets (never committed)
- ✅ **Multi-schema isolation** per property
- ✅ **No data invention** - agent only uses real data

---

## 🛣️ Roadmap

### ✅ Completed
- [x] Multi-agent architecture with ReAct loops
- [x] Intent-based routing
- [x] Modular prompt system
- [x] PostgreSQL-backed memory
- [x] Document management (RAG Q&A)
- [x] Numbers framework (Excel AI)
- [x] PDF report generation
- [x] Email automation
- [x] Voice support
- [x] Logfire observability

### 🔮 Coming Soon
- [ ] Portfolio rollups (multi-property aggregation)
- [ ] Time series projections (cashflow forecasting)
- [ ] Mobile app (iOS/Android)
- [ ] Webhook integrations (Zapier, Make.com)
- [ ] Document OCR (extract data from scans)
- [ ] White-label (custom branding per agency)

---

## 📖 Citation

If you use RAMA AI in your research or product:

```bibtex
@software{rama_ai_2024,
  title = {RAMA AI: Multi-Agent Property Management Assistant},
  author = {RAMA Country Living},
  year = {2024},
  url = {https://github.com/mariasebarespersona/tumai}
}
```

---

## 📄 License

Proprietary - All rights reserved by RAMA Country Living.

---

## 🤝 Support

- **📧 Email:** support@ramacountryliving.com
- **📚 Docs:** [Technical Architecture](docs/TECHNICAL_ARCHITECTURE.md)
- **🐛 Issues:** [GitHub Issues](https://github.com/mariasebarespersona/tumai/issues)

---

<div align="center">

**Built with ❤️ for rural property investors**

[![GitHub](https://img.shields.io/badge/GitHub-mariasebarespersona-black?style=flat-square&logo=github)](https://github.com/mariasebarespersona/tumai)
[![Live Demo](https://img.shields.io/badge/Live_Demo-Vercel-black?style=flat-square)](https://rama-agentic-ai.vercel.app)

[⬆ Back to top](#rama-ai---agentic-property-management-assistant)

</div>
