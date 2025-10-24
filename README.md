# RAMA Agentic AI - Property Management Assistant

<div align="center">

![RAMA Country Living](web/public/rama-logo.png)

**An intelligent, conversational agent for managing rural property investments**

[Features](#features) • [Architecture](#architecture) • [Getting Started](#getting-started) • [User Guide](#user-guide) • [Technical Details](#technical-details)

</div>

---

## 🌟 Overview

RAMA Agentic AI is a sophisticated property management system built with LangGraph and powered by GPT-4o. It provides an intelligent conversational interface for managing rural property investments through three comprehensive frameworks: **Documents**, **Numbers**, and **Summary**.

The system acts as a tireless assistant that helps users organize documentation, perform complex financial calculations, generate visual reports, and maintain complete transparency across the entire property lifecycle.

---

## 🔄 What's new (Oct 2025)

- Prompt-as-code (modular): `prompts/core.md` + `prompts/policies/*` + `prompts/contracts/*` + `prompts/examples/*`.
- LLM decide 100% la orquestación; el backend solo aplica el estado devuelto por `set_current_property`.
- Checkers en runtime:
  - Verify-before-deny (obliga `list_docs` antes de negar)
  - List-integrity (reconstruye Subidos/Pendientes por `storage_key`)
- Respuestas tipadas: `AgentReply` (Pydantic) para respuestas finales consistentes.
- Flujos restaurados:
  - Al entrar en propiedad: mensaje estándar “Documentos y Números” (sin listar docs).
  - Atajos: “plantilla de Documentos/Números” llama `list_docs`/`get_numbers` directamente.
- Estabilidad: corrección de `GraphRecursionError` y simplificación del grafo post-tools.
- Borrado múltiple: `delete_properties([ids])` con resolución de nombres → ids (vía `search_properties`).
- Rendimiento y 429: menos rondas por turno y reintentos con backoff configurados en el cliente LLM.

---

## ✨ Key Features

### 🏡 Property Management
- **Multi-property support**: Manage unlimited properties with isolated data per property
- **Smart property search**: Natural language search with fuzzy matching and auto-suggestions
- **Automatic framework provisioning**: Each property gets pre-configured templates for documents, numbers, and summaries
- **Property context retention**: The agent remembers which property you're working on and maintains state across sessions

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

`SYSTEM_PROMPT` se compone en runtime desde:
- `prompts/core.md` (rol, objetivo, límites)
- `prompts/policies/safety.md` (seguridad y estilo)
- `prompts/policies/tone.md` (tono)
- `prompts/policies/properties.md` (reglas de orquestación de propiedades)

Ventajas: versionado, auditoría clara y cambios atómicos por política.

---

## ✅ Runtime Checkers

- **Verify-before-deny**: si la respuesta niega existencia de documentos sin `list_docs` reciente, se fuerza `list_docs` y se rehace la salida.
- **List-integrity**: tras `list_docs`, se renderiza “Subidos/Pendientes” por `storage_key`.
- **Numbers rendering**: tras `get_numbers`, se muestra una lista estable `item: valor`.

---

## 🛠 Stability fixes

- Eliminados bucles que provocaban `GraphRecursionError`:
  - Post-tools → vuelve a `assistant` una vez; `assistant` decide tool/end.
  - Render directo tras `list_docs`/`get_numbers` para evitar rondas extra.

---

## 🚦 Rate-Limits (429) & Performance

- Menos rondas por turno: render directo tras tools y guards que fuerzan la tool correcta.
- Retries con backoff en el cliente LLM.
- (Opcional) Planner con modelo ligero y respuesta final con modelo grande.

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

---

## 📖 User Guide

### Creating a Property

**Option 1: Natural language**
```
User: "Crear una propiedad llamada Casa Rural Demo en Calle Alameda 22"
Agent: ✅ Propiedad creada con id: xxx. Frameworks: Documentos, Números, Resumen.
```

**Option 2: Direct command**
```
User: "nueva propiedad"
Agent: ¿Cómo quieres llamar a la propiedad?
User: "Casa del Campo"
Agent: ¿Cuál es la dirección?
User: "Calle Verde 15, Segovia"
```

### Switching Properties

```
User: "trabajar con Casa Demo 6"
Agent: Trabajaremos con Casa Demo 6 — Calle Alameda 22. 
       Plantillas pendientes: Documentos, Números.
```

The agent uses fuzzy matching - "Casa Demos 6", "casa demo6", etc. all work.

### Document Framework

#### Upload a document
```
User: "subir escritura de la casa"
Agent: [Proposes slot: Compra / Escrituras / Escritura notarial]
       ¿Es correcto?
User: "sí"
Agent: [File upload prompt appears in UI]
```

#### List documents
```
User: "listar documentos"
Agent: [Shows table with uploaded ✓ and pending documents]
```

#### Summarize a document
```
User: "resume el contrato del arquitecto"
Agent: [AI-generated summary using RAG]
```

#### Ask questions about documents
```
User: "¿cuánto cuesta la licencia de obras?"
Agent: [Searches indexed documents and answers with citations]
```

#### Payment schedule extraction
```
User: "¿cuándo tengo que pagar al arquitecto?"
Agent: [Extracts dates and amounts from contract]
```

### Numbers Framework

#### View numbers template
```
User: "números"
Agent: [Shows full template with groups/items/values]
       Puedes pedirme: calcular, escenario, punto de equilibrio, 
       sensibilidad, gráfico en cascada, barras apiladas, 
       o enviarlo por email (Excel).
```

#### Set values
```
User: "pon precio de venta a 250000"
Agent: ✅ Actualizado Precio de venta a 250000.0
       [Auto-recalculates derived metrics]

User: "pon impuestos a 0.21"
Agent: ✅ Actualizado Impuestos (%) a 0.21
```

Accepts formats: `250000`, `250.000`, `250,000`, `0.21`, `21%`

#### Calculate derived metrics
```
User: "calcular"
Agent: Net profit: €45,230
       ROI: 18.5%
       Gross margin: €98,450
       ⚠️ Anomalías: total_pagado > precio_venta
```

#### What-if scenario
```
User: "escenario: -10% en precio y +12% en construcción"
Agent: Escenario calculado. Net profit: €32,100
       [Saves snapshot for comparison]
```

#### Break-even analysis
```
User: "punto de equilibrio de precio"
Agent: Break-even en precio_venta ≈ €185,430.50 (net_profit 0.00)
```

#### Sensitivity analysis
```
User: "sensibilidad (precio vs construcción)"
Agent: [Generates 2D heatmap]
       Sensibilidad lista: https://...sensitivity.png
```

#### Charts
```
User: "gráfico en cascada"
Agent: [Waterfall chart appears inline in chat]

User: "barras apiladas al 100%"
Agent: [Cost composition stacked bar chart]
```

#### Export to Excel
```
User: "envíalo por email a investor@example.com"
Agent: Email enviado con archivo adjunto: numbers_framework.xlsx
```

The Excel includes: Inputs, Derived Metrics, Anomalies, Recent Scenarios, Sensitivity Grid.

### Summary Framework

```
User: "ficha resumen propiedad"
Agent: [Generates professional PDF]
       Resumen (PDF) listo: https://...summary_xxx.pdf
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
User: "envíalo por email a stakeholder@example.com"
Agent: Email enviado con PDF adjunto.
```

### Email & Communication

The agent understands various email requests:
```
"mandame la plantilla de números por email"
"enviame el resumen a mi@correo.com"
"enviar escritura por correo electrónico"
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
       "He entendido: 'pon precio de venta a doscientos mil euros'"
       ✅ Actualizado Precio de venta a 200000.0
```

### Mock Documents (for Prototyping)

```
User: "sembrar docs mock"
Agent: ✅ Documentos mock creados: 15. 0 errores.
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
1. pon precio de venta a 250000
2. pon impuestos a 0.21
3. pon costes de construcción a 120000
4. pon terrenos coste a 40000
5. calcular
6. gráfico en cascada
7. escenario: -10% en precio y +12% en construcción
8. punto de equilibrio
9. envíalo por email a test@example.com
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

