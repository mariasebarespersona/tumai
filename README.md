# RAMA Agentic AI - Property Management Assistant

<div align="center">

![RAMA Country Living](web/public/rama-logo.png)

**An intelligent, conversational agent for managing rural property investments**

[Features](#features) • [Architecture](#architecture) • [Getting Started](#getting-started) • [User Guide](#user-guide) • [Technical Details](#technical-details)

</div>

---

## 🌟 Overview

RAMA Agentic AI is a conversational assistant for real estate companies, built with LangGraph and powered by GPT‑4o. Its goal is to make it effortless to complete the three core templates for every property — **Documents**, **Numbers**, and **Summary** — while automating many day‑to‑day property management tasks.

It helps teams organize documentation, perform financial calculations, generate professional reports, and maintain complete transparency across the entire property lifecycle — all through natural language.

---

## 🚀 Public Demo Deployment

Click to deploy both backend (FastAPI) and frontend (Next.js) on Render using the provided Blueprint:

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/mariasebarespersona/tumai)

After clicking:
- For the backend service (`rama-backend`), add at least `OPENAI_API_KEY`. Optionally add `SUPABASE_URL`, `SUPABASE_KEY`, `DATABASE_URL` (for persistence), and SMTP variables if you want email sending.
- The frontend service (`rama-frontend`) will automatically get `BACKEND_URL` pointing to the backend URL.
- Once both services are live, share the frontend URL (e.g., `https://rama-frontend.onrender.com`) with recruiters.

Alternative (Vercel + Render):
- Deploy backend on Render (as above) and copy its URL.
- Deploy frontend on Vercel (root: `web/`) and set `BACKEND_URL` in Vercel Project Settings → Environment Variables to the backend URL.

---

## 🔄 What's new (Nov 2025)

### Document Framework V2 (I/II/III/IV)
- Section I (R2B) is now mandatory for all properties.
- Sections II, III or IV: the user completes only ONE; the agent asks which one.
- Extended JSON schema for documents: `document_kind`, `parent_document_id`, `due_date`, `placeholder`, `auto_generated`.
- New SQL migration: `migrations/2025-11-03_document_framework_v2.sql` (idempotent, with SECURITY DEFINER RPCs).

### Automatic factura placeholders (RAG → dates → placeholders)
- On upload of any document marked "+ facturas" (e.g., `Contrato arquitecto`), the agent:
  1) runs `qa_payment_schedule` (RAG) to extract cadence and day of payment,
  2) creates placeholders with `document_kind=factura`, linked via `parent_document_id`,
  3) sets `due_date`, `placeholder=true`, `auto_generated=true`.
- Frequency is detected dynamically: monthly, quarterly, yearly, every_15_days, or explicit "N cuotas".
- Count of placeholders adapts to contract: e.g., 12 mensuales (1 año), 4 trimestrales, 1 anual, 6 cuotas, etc. (capped at 36).

### RPC-only DB access (fixes PostgREST cache issues)
- Reading documents always goes through `public.list_property_documents(p_id uuid)`.
- Updating storage link uses `public.update_property_document_link(...)`.
- NEW: Inserting placeholders uses `public.insert_property_document(...)` → avoids `PGRST205`.
- Permissions: grants added for per-property schemas; RPCs are `SECURITY DEFINER` and `SET search_path = public`.

### Smarter upload classification for invoices
- `propose_doc_slot` now accepts `property_id` and, if the filename contains "factura", it:
  - extracts date from filename (e.g., `2025-11-05`),
  - searches existing factura placeholders and proposes the matching placeholder name (e.g., `Facturas arquitecto — 2025-11-05`).

### Frontend UX
- Chat highlights the rule “Elegir una entre II/III/IV”.
- Markdown headings/lists rendered for readability.

### LLM & Rate-limits
- Default model switched to `gpt-4o-mini` with token caps to reduce 429s.

---

## ⬆️ Upgrade guide (DF V2)

1) Run the migration in Supabase SQL editor:
```
-- open file migrations/2025-11-03_document_framework_v2.sql and run contents
```
2) Reload PostgREST schema cache:
```sql
select pg_notify('pgrst', 'reload schema');
```
3) Restart backend (no hot-reload) so it picks new code:
```bash
pkill -9 uvicorn || true
cd /path/to/rama-agentic-ai
source .venv/bin/activate
uvicorn app:app --host 0.0.0.0 --port 7901
```
4) Point the frontend to your backend during local dev:
```bash
cd web
export NEXT_PUBLIC_API_URL=http://127.0.0.1:7901
npm run dev
```
5) Test: upload `Contrato arquitecto` and ask “¿Hay facturas asociadas…?” → placeholders should appear.

---

## 🔄 What's new (Oct 2025)

- Prompt-as-code (modular): `prompts/core.md` + `prompts/policies/*` + `prompts/contracts/*` + `prompts/examples/*`.
- LLM orchestrates 100% of the flow; the backend only applies the state returned by `set_current_property`.
- Runtime checkers:
  - Verify-before-deny (forces `list_docs` before denying)
  - List-integrity (rebuilds Uploaded/Pending by `storage_key`)
- Typed responses: `AgentReply` (Pydantic) for consistent final messages.
- Restored flows:
  - On entering a property: standard message “Documents and Numbers” (no auto‑listing of docs)
  - Shortcuts: “Documents/Numbers template” calls `list_docs`/`get_numbers` directly
- Stability: fixed `GraphRecursionError` and simplified the post‑tools graph.
- Bulk delete: `delete_properties([ids])` with name → id resolution via `search_properties`.
- Performance and 429: fewer rounds per turn and client‑side backoff retries in the LLM client.

---

## 🧭 Suggested Conversation Flow

- "Show me the list of properties"
- "Switch to property <Property Name>"
- "Show me which documents I've already uploaded"
- "I want to upload this document" (then drag-and-drop in the UI)
- "Summarize the document <Document Name>"
- "Send me this document by email to you@example.com"
- "I want to complete the Numbers template"
- "Set <item_key> to 1000.0"
- "Send me the Numbers template by email"
- "I want to add and work on a new property"

---

## ✨ Key Features

### 🏡 Property Management
- **Multi-property support**: Manage unlimited properties with isolated data per property
- **Smart property search**: Natural language search with fuzzy matching and auto-suggestions
- **Automatic framework provisioning**: Each property gets pre-configured templates for documents, numbers, and summaries
- **Property context retention**: The agent remembers which property you're working on and maintains state across sessions

### 🔔 Smart Reminders (NEW!)
- **Automatic date extraction**: The agent reads documents and extracts payment dates automatically
- **Scheduled reminders**: Create reminders that are emailed automatically on the configured date(s)
- **Full management**: List, cancel, and modify reminders easily
- **Document integration**: Link reminders to specific documents for full context

### 📄 Document Framework
- **Structured document organization**: Documents organized by group/subgroup/name taxonomy
- **Guided upload workflow**: The agent proposes appropriate slots based on your input
- **RAG-powered Q&A**: Ask questions about your documents in natural language
- **Document summarization**: Get AI-generated summaries of uploaded documents
- **Payment schedule extraction**: Automatically extract and track payment deadlines
- **Document status tracking**: See what's uploaded vs. what's pending at a glance
- **Signed URL generation**: Secure, time-limited access to documents stored in Supabase

### 🔢 Numbers Framework (Excel AI Agent)

A powerful financial analysis engine that brings Excel-like intelligence to property investment analysis:

#### Core Capabilities
- **Dynamic data entry**: "pon precio de venta a 250000" - natural language commands
- **Auto-calculated metrics**: 
  - `impuestos_total`, `costes_totales`, `gross_margin`, `net_profit`, `roi_pct`, `urbano_ratio`, `price_per_m2`
- **Data validation & anomaly detection**:
  - `impuestos_pct` must be in range [0, 0.25]
  - Non-negative constraints on numeric fields
  - Flags when `total_pagado > precio_venta`
  - Warns on `net_profit < 0`
- **Audit trail**: Every calculation is logged with inputs, outputs, timestamp, and trigger

#### Scenario & Sensitivity Analysis
- **What-if scenarios**: "escenario: -10% en precio y +12% en construcción"
  - Apply percentage deltas to multiple inputs
  - See impact on net profit and ROI
  - Scenarios are saved as snapshots for comparison
- **Break-even analysis**: "punto de equilibrio de precio"
  - Solver finds the `precio_venta` where `net_profit = 0`
  - Uses binary search for fast convergence
- **Sensitivity analysis**: "sensibilidad (precio vs construcción)"
  - Generates 2D grid showing `net_profit` for varying inputs
  - Produces heatmap visualization
  - Helps identify optimal pricing strategies

#### Visual Charts (Auto-generated)
- **Waterfall chart**: Shows cumulative impact from revenue to net profit
- **Stacked 100% bar**: Composition of costs breakdown
- **Sensitivity heatmap**: 2D grid of profit vs. two varying parameters
- All charts rendered with Plotly and cached as PNGs in Supabase Storage

#### Export & Communication
- **Excel export**: Full framework with inputs, derived metrics, anomalies, scenarios, and sensitivity grids
- **Email integration**: "envíalo por email a nombre@dominio.com" - instant delivery as .xlsx attachment
- **Natural language interface**: All actions available through Spanish conversational commands

### 📊 Summary Framework (Professional PDF Reports)

Generates beautiful, investor-ready PDF summaries with:

#### Report Structure (5 pages)
1. **Cover Page**
   - Property name and address
   - RAMA Country Living branding
   - Generation date
   - Professional green/earth color palette

2. **Property Photos**
   - High-quality demo images (Unsplash countryside houses)
   - Clearly labeled as reference images
   - Clean, modern layout

3. **Executive Summary**
   - AI-generated narrative summary (GPT-4o-mini) based on actual data
   - Three key metric cards: Precio Venta, Net Profit, ROI
   - List of uploaded documents with checkmarks
   - No data invention - only uses available information

4. **Location Map**
   - Static map with property location pin (Mapbox API)
   - Address display
   - Fallback to text if map unavailable

5. **Numbers Framework Table**
   - Complete financial data in professional table format
   - Color-coded headers and alternating rows
   - Currency formatting
   - Groups and labels clearly displayed

#### Design Features
- **Professional color palette**: Green/earth tones matching countryside theme
- **Modern typography**: Helvetica with bold headers
- **Structured layout**: Consistent spacing and alignment
- **Visual hierarchy**: Clear sections with distinct styling
- **Print-ready**: A4 format, high-quality output

### 🎙️ Voice Integration
- **Speech-to-text**: Upload audio files for automatic transcription
- **Text-to-speech**: Convert agent responses to audio
- **Natural conversation flow**: Voice messages appear in chat like text

### 📧 Email & Communication
- **Document sharing**: Send signed URLs for document access
- **Excel delivery**: Automatic .xlsx attachment for numbers framework
- **PDF reports**: Summary reports delivered as email attachments
- **Smart recipient handling**: Remembers last email used for quick resend

### 🧠 Advanced Intelligence

#### Context & Memory Management
- **PostgreSQL-backed persistence**: Conversation state persists across sessions and server restarts
- **Full conversation history**: Agent has access to entire chat history with the user
- **Document reference tracking**: Remembers last mentioned documents
- **Property context**: Automatically maintains active property context
- **Confirmation workflows**: Proposes actions and waits for user approval when needed

#### Natural Language Understanding
- **Multi-strategy fuzzy matching**: Handles typos and variations in property/document names
- **Intent recognition**: Understands commands in natural Spanish
- **Synonym mapping**: Recognizes multiple ways to refer to the same field (e.g., "impuestos", "IVA", "ITP")
- **Context-aware parsing**: Extracts emails, property names, numeric values from free text

#### Error Handling & Resilience
- **Graceful degradation**: Falls back to alternatives when primary methods fail
- **User-friendly error messages**: Never shows technical errors to users
- **Retry logic**: Handles temporary network issues transparently
- **Data validation**: Prevents invalid inputs before they reach the database

---

## 🧩 Prompt as code

`SYSTEM_PROMPT` is composed at runtime from:
- `prompts/core.md` (role, objective, constraints)
- `prompts/policies/safety.md` (safety and style)
- `prompts/policies/tone.md` (tone)
- `prompts/policies/properties.md` (property orchestration rules)

Benefits: versioning, clear auditability, and atomic policy changes.

---

## ✅ Runtime Checkers

- **Verify-before-deny**: if a response denies the existence of documents without a recent `list_docs`, force `list_docs` and rebuild the output.
- **List-integrity**: after `list_docs`, render “Uploaded/Pending” based on `storage_key`.
- **Numbers rendering**: after `get_numbers`, render a stable list `item: value`.

---

## 🛠 Stability fixes

- Removed loops that caused `GraphRecursionError`:
  - Post-tools → return to `assistant` once; `assistant` decides tool/end.
  - Direct rendering after `list_docs`/`get_numbers` to avoid extra rounds.

---

## 🚦 Rate-Limits (429) & Performance

- Fewer rounds per turn: direct rendering after tools and guards that force the correct tool.
- Retries with backoff in the LLM client.
- (Optional) Planner with a lightweight model and final response with a larger model.

---

## 🏗️ Architecture

### Technology Stack

**Backend:**
- **LangGraph**: Orchestration framework for building stateful, multi-step agent workflows
- **LangChain**: Tool calling, LLM integration, and RAG pipelines
- **FastAPI**: High-performance Python web framework
- **Supabase**: PostgreSQL database, storage, and authentication
- **OpenAI GPT-4o**: Primary reasoning and tool-calling model
- **OpenAI GPT-4o-mini**: Lightweight model for summaries and embeddings

**Frontend:**
- **Next.js 14**: React framework with App Router
- **TypeScript**: Type-safe development
- **TailwindCSS**: Utility-first styling with custom countryside theme
- **React Hooks**: Modern state management

**Data & Storage:**
- **PostgreSQL (Supabase)**: Multi-schema per-property isolation
- **Supabase Storage**: Document and chart storage with signed URLs
- **LangGraph Checkpointer**: PostgreSQL-backed conversation state persistence

**Libraries & Tools:**
- **python-pptx**: PowerPoint generation
- **ReportLab**: Professional PDF generation
- **Plotly + Kaleido**: Interactive charts and PNG export
- **openpyxl**: Excel file generation
- **Pillow**: Image processing
- **psycopg + psycopg-pool**: PostgreSQL connection pooling

### LangGraph Agent Architecture

The agent is built using **LangGraph's StateGraph** pattern, which provides:

#### State Management
```python
class AgentState(TypedDict):
    messages: Annotated[List[Any], add_messages]  # Conversation history with reducer
    property_id: NotRequired[str]                 # Active property context
    awaiting_confirmation: NotRequired[bool]      # Workflow gates
    proposal: NotRequired[Dict[str, Any]]         # Pending actions
    last_doc_ref: NotRequired[Dict[str, Any]]     # Document reference memory
    input: NotRequired[str]                       # User input
```

The `add_messages` reducer automatically manages the conversation history, enabling full context retention.

#### Graph Nodes

1. **`prepare_input`**: Converts user text input into HumanMessage objects
2. **`router`**: Handles confirmation workflows - checks if user confirmed or cancelled pending actions
3. **`assistant`**: Core LLM reasoning node
   - Receives SystemMessage with full SYSTEM_PROMPT
   - Has access to all 40+ registered tools
   - GPT-4o with temperature=0 for consistency
   - Returns AIMessage with optional tool calls
4. **`tools`**: ToolNode that executes requested tools in parallel
5. **`post_tool`**: Post-processing hook
   - Captures tool outputs (e.g., `add_property` → auto-set `property_id`)
   - Implements smart logic like auto-selecting when `search_properties` returns 1 result
   - Sets workflow flags (e.g., `awaiting_confirmation` for document uploads)

#### Graph Flow

```
[Entry: prepare_input] 
    → [router: check confirmations]
    → [assistant: LLM reasoning + tool selection]
    → {should_call_tool?}
        → YES: [tools: execute] → [post_tool: process results] → [loop back to assistant]
        → NO: [END]
```

#### Why LangGraph?

- **Stateful workflows**: Maintains context across multiple turns
- **Conditional branching**: Different paths based on tool results
- **Parallel tool execution**: When tools are independent
- **Built-in checkpointing**: Conversation state persists to PostgreSQL
- **Human-in-the-loop**: Easy to implement confirmation gates
- **Debuggability**: Clear graph structure with node boundaries

### Multi-Schema Database Design

Each property gets isolated PostgreSQL schemas:
- `property_{uuid}_docs`: Document metadata and storage keys
- `property_{uuid}_numbers`: Line items for numbers framework
- `property_{uuid}_summary`: Summary spec and computed values

This provides:
- **Data isolation**: One property can't see another's data
- **Scalability**: Schemas are created on-demand
- **Clean migrations**: Schema-level versioning

### Tool Registry Pattern

All agent tools are centralized in `tools/registry.py`:
```python
from langchain.tools import tool

@tool("get_numbers")
def get_numbers_tool(property_id: str) -> List[Dict]:
    """Fetch all line items from numbers framework."""
    return _get_numbers(property_id)
```

Tools are automatically:
- Registered with LangChain's tool decorator
- Type-validated with Pydantic models
- Documented with docstrings (used by LLM for tool selection)
- Bound to the LLM in `agentic.py`

This pattern ensures:
- **Single source of truth**: Tools defined once, used everywhere
- **Type safety**: Pydantic validation on inputs
- **Self-documenting**: Docstrings guide LLM tool selection
- **Easy testing**: Tools are pure functions

---

## 🚀 Getting Started

### Prerequisites

- Python 3.10+
- Node.js 18+ (for Next.js frontend)
- Supabase account (or local Supabase instance)
- OpenAI API key

### Installation

1. **Clone the repository**
```bash
git clone  https://github.com/mariasebarespersona/tumai.git
cd rama-agentic-ai
```

2. **Backend setup**
```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

3. **Frontend setup**
```bash
cd web
npm install
```

4. **Environment configuration**

Create `.env` in the project root:
```env
# OpenAI
OPENAI_API_KEY=sk-...

# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key
DATABASE_URL=postgresql://postgres.xxx:xxx@aws-0-region.pooler.supabase.com:6543/postgres

# Email (optional - for send_email tool)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your@email.com
SMTP_PASSWORD=your-password

# Google Cloud (optional - for voice tools)
GOOGLE_APPLICATION_CREDENTIALS=path/to/credentials.json
```

See `env_example.txt` for full template.

5. **Database setup**

Run the DDL scripts to create tables:
```sql
-- In your Supabase SQL editor, run:
-- tools/supabase_client.py has provisioning logic
-- Or manually create schemas per property as needed
```

For Numbers Agent tables (calc_outputs, calc_log, etc.), see `DATABASE_DDL_GUIDE.md`.

6. **Run the application**

Terminal 1 (Backend - FastAPI):
```bash
python -m uvicorn app:app --reload --host 127.0.0.1 --port 7901
# FastAPI server at http://127.0.0.1:7901
```

Terminal 2 (Frontend - Next.js):
```bash
cd web
npm run dev
# Next.js app at http://localhost:3000
```

## Web (Next.js) — Excel/MCP Dev

Run these in separate terminals during local development:

- Next.js frontend:
```bash
cd web
npm install
npm run dev
```

- MCP server (JSON-RPC):
```bash
MCP_MODE=OFFICEJS node packages/mcp-server/server.js
# or GRAPH mode to proxy to Next API routes
# MCP_MODE=GRAPH node packages/mcp-server/server.js
```

- Excel add-in (static dev server):
```bash
python3 -m http.server 4300 -d packages/excel-addin/public
# then sideload the panel at http://127.0.0.1:4300/panel.html (see docs/EXCEL_ADDIN_SETUP.md)
```

Environment (web/.env.local):
```
NEXT_PUBLIC_MCP_URL=http://127.0.0.1:4310/jsonrpc
EXCEL_FILE_ID=
# Optional embed URLs if you use the iframe panel in chat
NEXT_PUBLIC_EXCEL_EMBED_R2B=
NEXT_PUBLIC_EXCEL_EMBED_R2B_PM=
NEXT_PUBLIC_EXCEL_EMBED_R2B_PM_VENTA=
NEXT_PUBLIC_EXCEL_EMBED_PROMOCION=
```

Docs:
- docs/EXCEL_ADDIN_SETUP.md
- docs/MCP_TOOLS.md
- docs/GRAPH_MODE.md
- docs/DECISIONS.md
- docs/QA_SCRIPT.md

---

## 📖 User Guide

### Creating a Property

**Option 1: Natural language**
```
User: "Create a property named Rural House Demo at Calle Alameda 22"
Agent: ✅ Property created with id: xxx. Frameworks: Documents, Numbers, Summary.
```

**Option 2: Direct command**
```
User: "new property"
Agent: What would you like to name the property?
User: "Country House"
Agent: What's the address?
User: "Calle Verde 15, Segovia"
```

### Switching Properties

```
User: "work with Casa Demo 6"
Agent: We'll work with Casa Demo 6 — Calle Alameda 22. 
       Pending templates: Documents, Numbers.
```

The agent uses fuzzy matching - "Casa Demos 6", "casa demo6", etc. all work.

### Document Framework

#### Upload a document
```
User: "upload the title deed"
Agent: [Proposes slot: Purchase / Deeds / Notarial deed]
       Is that correct?
User: "yes"
Agent: [File upload prompt appears in the UI]
```

#### List documents
```
User: "list documents"
Agent: [Shows table with uploaded ✓ and pending documents]
```

#### Summarize a document
```
User: "summarize the architect contract"
Agent: [AI-generated summary using RAG]
```

#### Ask questions about documents
```
User: "how much does the building permit cost?"
Agent: [Searches indexed documents and answers with citations]
```

#### Payment schedule extraction
```
User: "when do I have to pay the architect?"
Agent: [Extracts dates and amounts from contract]
```

### Numbers Framework

#### View numbers template
```
User: "numbers"
Agent: [Shows full template with groups/items/values]
       You can ask me to: calculate, run a scenario, break-even, 
       sensitivity, waterfall chart, 100% stacked bars, 
       or send it by email (Excel).
```

#### Set values
```
User: "set sale_price to 250000"
Agent: ✅ Sale price updated to 250000.0
       [Auto-recalculates derived metrics]

User: "set taxes to 0.21"
Agent: ✅ Taxes (%) updated to 0.21
```

Accepts formats: `250000`, `250.000`, `250,000`, `0.21`, `21%`

#### Calculate derived metrics
```
User: "calculate"
Agent: Net profit: €45,230
       ROI: 18.5%
       Gross margin: €98,450
       ⚠️ Anomalies: total_paid > sale_price
```

#### What-if scenario
```
User: "scenario: -10% on price and +12% on construction"
Agent: Scenario calculated. Net profit: €32,100
       [Saves snapshot for comparison]
```

#### Break-even analysis
```
User: "price break-even"
Agent: Break-even at sale_price ≈ €185,430.50 (net_profit 0.00)
```

#### Sensitivity analysis
```
User: "sensitivity (price vs construction)"
Agent: [Generates 2D heatmap]
       Sensitivity ready: https://...sensitivity.png
```

#### Charts
```
User: "waterfall chart"
Agent: [Waterfall chart appears inline in chat]

User: "100% stacked bars"
Agent: [Cost composition stacked bar chart]
```

#### Export to Excel
```
User: "send it by email to investor@example.com"
Agent: Email sent with attachment: numbers_framework.xlsx
```

The Excel includes: Inputs, Derived Metrics, Anomalies, Recent Scenarios, Sensitivity Grid.

### Summary Framework

```
User: "property summary report"
Agent: [Generates professional PDF]
       Summary (PDF) ready: https://...summary_xxx.pdf
       [Download button appears in UI]
```

The PDF includes:
- Cover page with branding
- Demo photos (countryside houses)
- AI-generated executive summary
- Key metrics in visual cards
- Document list
- Location map (Madrid)
- Complete numbers table

Then:
```
User: "send it by email to stakeholder@example.com"
Agent: Email sent with PDF attached.
```

### Email & Communication

The agent understands various email requests:
```
"send me the numbers template by email"
"send the summary to me@example.com"
"send the deed by email"
```

It will:
1. Ask for email if not provided
2. Remember the last email used
3. Generate appropriate attachments (Excel, PDF, or document links)
4. Confirm sending

### Voice Interaction

Upload an audio file via the UI:
```
Agent: [Transcribes audio]
       "I'm hearing: 'set sale price to two hundred thousand euros'"
       ✅ Sale price updated to 200000.0
```

### Mock Documents (for Prototyping)

```
User: "seed mock docs"
Agent: ✅ Mock documents created: 15. 0 errors.
```

Creates placeholder text files for all pending document slots, allowing you to:
- Test the Summary Framework without real documents
- Prototype RAG Q&A flows
- Demonstrate the complete workflow

---

## 🧪 Testing & Development

### Mock Document Generation

For development/demo purposes:
```python
from tools.docs_tools import seed_mock_documents
seed_mock_documents(property_id, index_after=True)
```

This creates lightweight placeholders marked with `metadata: {mock: True}` that can be easily removed later.

### Numbers Agent Testing

Quick test sequence:
```
1. set sale price to 250000
2. set taxes to 0.21
3. set construction costs to 120000
4. set land cost to 40000
5. calculate
6. waterfall chart
7. scenario: -10% on price and +12% on construction
8. break-even
9. send it by email to test@example.com
```

Expected: All commands succeed, charts render, Excel arrives by email.

### Debugging Agent Behavior

Enable debug output:
```python
# In app.py or agentic.py
import logging
logging.basicConfig(level=logging.DEBUG)
```

Check LangGraph state:
```python
# The checkpointer stores full state in PostgreSQL
# Query: SELECT * FROM checkpoints WHERE thread_id = 'session_xxx';
```

---

## 📐 Technical Details

### Numbers Agent: Derived Metrics Formulas

From `tools/numbers_agent.py`:

```python
# Tax calculation
impuestos_total = precio_venta * impuestos_pct

# Total costs
costes_totales = (
    terrenos_coste + 
    project_management_coste + 
    acometidas + 
    costes_construccion + 
    impuestos_total
)

# Margins
gross_margin = precio_venta - costes_totales
net_profit = gross_margin  # (no additional deductions yet)

# ROI
roi_pct = (net_profit / costes_totales * 100) if costes_totales else 0

# Ratios
urbano_ratio = (terreno_urbano / (terreno_urbano + terreno_rustico)) if (terreno_urbano + terreno_rustico) else 0

# Price per m²
price_per_m2 = (precio_venta / total_m2) if total_m2 else 0
```

### Anomaly Detection Rules

1. `impuestos_pct` not in [0, 0.25] → "impuestos_pct fuera de rango"
2. Any negative value in cost fields → "valor negativo en {field}"
3. `total_pagado > precio_venta` → "total_pagado excede precio_venta"
4. `net_profit < 0` → "net_profit negativo"

### Break-Even Solver

Binary search implementation:
```python
def break_even_precio(property_id: str, tolerance: float = 1.0) -> Dict:
    low, high = 0.0, 1e9
    for _ in range(50):
        mid = (low + high) / 2
        # Set precio_venta = mid, recalculate
        net = compute_derived_from_inputs(...)["net_profit"]
        if abs(net) < tolerance:
            return {"precio_venta": mid, "net_profit": net}
        elif net < 0:
            low = mid
        else:
            high = mid
```

Converges in ~20 iterations to ±€1 precision.

### RAG Pipeline

1. **Indexing**: 
   - Extract text from PDF/DOCX/TXT
   - Chunk with RecursiveCharacterTextSplitter (chunk_size=1000, overlap=200)
   - Embed with OpenAI text-embedding-3-small
   - Store in Supabase `document_chunks` with pgvector

2. **Retrieval**:
   - Embed user query
   - Cosine similarity search → top 5 chunks
   - Pass to GPT-4o with context

3. **Augmentation**:
   - System prompt instructs: "Answer using ONLY the provided chunks. If no info, say so."
   - Return answer + citations (chunk_id, page, score)

### Multi-Schema Isolation

When a property is created:
```python
def provision_schemas(property_id: str):
    docs_schema = f"property_{property_id.replace('-', '_')}_docs"
    nums_schema = f"property_{property_id.replace('-', '_')}_numbers"
    sum_schema = f"property_{property_id.replace('-', '_')}_summary"
    
    for schema in [docs_schema, nums_schema, sum_schema]:
        sb.rpc("create_schema_if_not_exists", {"schema_name": schema}).execute()
        sb.postgrest.schema = schema
        # Create tables within schema
```

This enables:
- True multi-tenancy
- Easy data export per property
- Isolated migrations

### Context Window Management

The agent uses:
- **System prompt**: ~1,500 tokens (comprehensive instructions)
- **Conversation history**: Unbounded (relies on LangGraph checkpointer)
- **Tool outputs**: Varies (documents can be large)

If context exceeds GPT-4o's 128k limit:
- LangGraph automatically summarizes older messages
- Recent messages always retained
- Tool calls never lost

In practice, even 100+ turn conversations fit comfortably.

---

## 🎨 UI/UX Design Philosophy

### Countryside Theme

The UI uses a custom "Campo Natural" color palette:
- **Greens**: `#3d7435` (dark), `#8fcb7f` (light), `#b3dfaa`
- **Earth tones**: `#c5ac85`, `#d4c0a1`
- **Neutrals**: `#f7fdf5` (bg), `#1f3d1e` (text)

Design principles:
- **Glassmorphism**: Subtle transparency effects
- **Natural shadows**: Soft, organic shadows (not harsh)
- **Rounded corners**: 12-24px border radius for warmth
- **Generous spacing**: Airy layouts, not cramped
- **Responsive**: Mobile-first design

### Chat Interface

- **Message bubbles**: User messages in green gradient, agent in glass effect
- **Inline rendering**: Images and PDFs appear directly in chat
- **File upload**: Drag-and-drop zone with preview
- **Voice recording**: Built-in audio recorder
- **Download buttons**: Styled with green gradient for PPTX/XLSX/PDF files

---

## 🔒 Security & Privacy

- **Signed URLs**: All document access uses time-limited signed URLs (Supabase)
- **Schema isolation**: Each property's data is in separate PostgreSQL schema
- **No data invention**: Agent is strictly forbidden from making up data
- **Audit trails**: All calculations logged with provenance
- **Environment variables**: Secrets stored in `.env`, never committed

---

## 🚧 Roadmap

### Completed ✅
- [x] Multi-property management
- [x] Document framework with RAG Q&A
- [x] Numbers framework (Excel AI Agent)
- [x] Derived metrics and auto-calculation
- [x] What-if scenarios
- [x] Break-even analysis
- [x] Sensitivity analysis
- [x] Charts (waterfall, stacked, heatmap)
- [x] Excel export
- [x] Summary framework (professional PDF)
- [x] Email integration
- [x] Voice transcription
- [x] UI with countryside theme
- [x] PostgreSQL-backed persistence

### Planned 🔮
- [ ] **Portfolio rollups**: Multi-property aggregation and ranking
  - Sum `net_profit` across all properties
  - Rank by ROI
  - Portfolio-level charts
- [ ] **Time series projections**: Cashflow over time
- [ ] **Collaborative editing**: Multiple users per property
- [ ] **Mobile app**: Native iOS/Android
- [ ] **Advanced charts**: Tornado diagrams, Monte Carlo simulations
- [ ] **Document OCR**: Extract data directly from scanned documents
- [ ] **Webhook integrations**: Zapier, Make.com
- [ ] **White-label**: Customizable branding per agency

---





<div align="center">

**Built with ❤️ for rural property investors**

[⬆ Back to top](#rama-agentic-ai---property-management-assistant)

</div>

