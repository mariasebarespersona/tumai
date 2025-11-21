# RAMA AI - Common User Flows and Expected Behavior

## Recent Fixes (2025-11-21)

### ✅ Document Persistence
**Problem:** Documents disappeared after page refresh  
**Fix:** Added `/api/documents` REST endpoint and frontend state management  
**Status:** ✅ FIXED

### ✅ Document List Auto-Refresh
**Problem:** Document list didn't update after upload  
**Fix:** Auto-fetch documents after detecting upload confirmation in chat  
**Status:** ✅ FIXED

### ⚠️ Email Sending Flow
**Problem:** Multiple issues with email sending via DocsAgent  
**Status:** 🔧 PARTIALLY FIXED (agent prompt improved, but flow needs testing)

---

## Common User Flows

### 1. Create a New Property

**User says:** 
- "Crea una nueva propiedad"
- "Nueva propiedad" 
- "Crear ficha de propiedad"

**Expected Flow:**
1. Router detects `property.create` intent
2. `PropertyAgent` activates
3. Agent asks for property details:
   - Name (required)
   - Address (optional)
   - Notes (optional)
4. Agent creates property in Supabase
5. Agent sets `property_id` in session state
6. Frontend displays property name in header

**Success Indicators:**
- ✅ Property name appears in header badge
- ✅ Document count shows "📄 0 documentos" (if no docs yet)
- ✅ Chat confirms: "✅ Propiedad creada: [nombre]"

**What to Test:**
```
User: "Crea una propiedad llamada Casa Rural Test"
Expected: Property created, name appears in header
```

---

### 2. Upload a Document

**User says:** 
- "Sube este documento" (with file attached)
- Drag & drop file onto chat
- Click file icon and select file

**Expected Flow:**
1. User attaches file via drag-drop, file picker, or paste
2. User sends message (can be empty or describe document)
3. Frontend sends file to `/api/chat`
4. Backend detects file upload
5. `DocsAgent` or `MainAgent` processes upload:
   - Proposes matching document slot
   - Uploads file to Supabase Storage
   - Links file to slot in database
   - Auto-indexes for RAG (if PDF)
6. Chat confirms: "✅ Documento subido: [nombre]"
7. Frontend auto-fetches updated document list
8. Document count badge updates

**Success Indicators:**
- ✅ File appears in upload queue before sending
- ✅ Chat shows processing message
- ✅ Chat confirms successful upload
- ✅ Document count badge increments
- ✅ Can ask questions about document content (RAG)

**What to Test:**
```
1. Drag PDF onto chat
2. Say "Este es el contrato del arquitecto"
3. Check: Document count increases
4. Refresh page
5. Check: Document count persists
6. Ask: "¿Qué dice el contrato del arquitecto?"
7. Check: RAG retrieves content
```

---

### 3. Complete Numbers Table

**User says:**
- "Vamos a completar los números"
- "Completar la tabla de números"
- "Trabajar en números"
- "Números"

**Expected Flow:**
1. Router detects `numbers` focus intent
2. `NumbersAgent` activates
3. If no template selected yet:
   - Agent asks: "¿Qué plantilla quieres usar?"
   - Shows available templates (R2B, Promoción, etc.)
4. User selects template
5. Excel panel opens on left side
6. Chat shrinks to right side
7. User can:
   - Click cells to select
   - Say "Pon 50000 en D5" to write values
   - Ask questions about cells
   - Say "Qué fórmula tiene B3?"

**Success Indicators:**
- ✅ Excel panel opens with spreadsheet view
- ✅ Can click cells to select
- ✅ Chat recognizes cell updates: "✅ Valor actualizado en D5"
- ✅ Table auto-reloads after updates
- ✅ Can close Excel panel with ✕ button

**What to Test:**
```
1. Say "Completar números"
2. Choose template (e.g., "R2B")
3. Check: Excel panel opens
4. Click cell D5
5. Say "Pon 50000 en D5"
6. Check: Cell updates, table reloads
7. Say "Qué valor tiene D5?"
8. Check: Agent reads "50000"
```

---

### 4. Send Document by Email

**User says:**
- "Mándame el contrato arquitecto por email"
- "Envía [documento] a tumai@hotmail.com"

**Expected Flow:**
1. Router detects `docs.send_email` intent
2. `DocsAgent` activates
3. Agent checks if email was provided:
   - If NO: "¿A qué correo quieres que lo envíe?"
   - If YES: Continues to step 4
4. Agent calls `signed_url_for(document_name)`
   - This verifies document exists
   - Generates secure 24h link
5. Agent IMMEDIATELY calls `send_email` (no text between)
6. `post_tool` hook intercepts and auto-confirms
7. Chat shows: "✅ Email enviado correctamente a [email]"

**Success Indicators:**
- ✅ Agent asks for email if not provided
- ✅ Agent does NOT show document list
- ✅ Agent does NOT say "documento no ha sido subido" (checks first with signed_url_for)
- ✅ Email arrives within 30 seconds
- ✅ Email contains clickable download link
- ✅ Link works and downloads file

**What to Test:**
```
1. Upload a document first (e.g., "Contrato arquitecto")
2. Say "Mandame el contrato arquitecto por email"
3. Agent asks for email
4. Say "tumai@hotmail.com"
5. Check: No document list shown
6. Check: Chat confirms "✅ Email enviado"
7. Check email inbox
8. Click link in email
9. Check: File downloads
```

**Known Issues to Watch For:**
- ⚠️ Agent showing document list (SHOULD NOT happen)
- ⚠️ Agent saying "documento no ha sido subido" without checking first
- ⚠️ Agent saying "ahora procederé..." instead of calling send_email directly
- ⚠️ Email not arriving (check spam, check backend logs)

---

### 5. Ask Questions About Document Content (RAG)

**User says:**
- "¿Qué día hay que pagar al arquitecto?"
- "¿Cuánto cuesta el proyecto según el contrato?"
- "Resume el contrato del arquitecto"

**Expected Flow:**
1. Router detects `docs.qa` intent (content question)
2. `DocsAgent` activates
3. Agent calls RAG tool:
   - `rag_qa_with_citations` for general questions
   - `qa_payment_schedule` for payment dates
   - `summarize_document` for summaries
4. RAG searches indexed chunks in `rag_chunks` table
5. Returns answer with citations
6. Chat shows: "[Answer]\n\nFuentes:\n- [document] (trozo X)"

**Success Indicators:**
- ✅ Agent uses RAG tool (not memory)
- ✅ Answer includes specific information from document
- ✅ Citations show which document and chunk
- ✅ Agent NEVER says "no tengo acceso al documento"

**What to Test:**
```
1. Upload a PDF with payment terms
2. Wait 5 seconds for indexing
3. Ask "¿Qué día hay que pagar?"
4. Check: Answer mentions specific date from PDF
5. Check: Citations show document name
```

---

## API Endpoints

### REST API (Direct Access)
- `GET /api/documents?property_id={id}` - Fetch all documents
- `GET /api/numbers?property_id={id}&template_key={key}` - Fetch numbers table

### Chat API (Conversational)
- `POST /ui_chat` - Main chat endpoint (handles everything)
  - Form params: `text`, `session_id`, `property_id`, `files[]`, `audio`

---

## Frontend State Management

### Key State Variables
```typescript
propertyId: string | null           // Current property UUID
propertyName: string | null         // Property display name
documents: {uploaded[], pending[]}  // Document lists (persisted)
excelTemplate: string | null        // Current numbers template
messages: ChatMessage[]             // Chat history (not persisted)
```

### Persistence
- ✅ `propertyId` → localStorage + backend session
- ✅ `propertyName` → localStorage + backend session
- ✅ `documents` → Fetched on mount, auto-refreshed
- ⚠️ `messages` → NOT persisted (resets on refresh)
- ✅ `excelTemplate` → Detected from chat, persists in session

---

## Architecture Notes

### Agent Routing
1. `OrchestrationRouter` (active_router.py) classifies intent
2. Routes to specialized agents:
   - `PropertyAgent` - Property CRUD
   - `DocsAgent` - Document management, RAG, email
   - `NumbersAgent` - Spreadsheet operations
   - `MainAgent` - Default/fallback

### RAG Pipeline
1. Document uploaded → `rag_index.py::index_document()`
2. PDF extracted → Split into chunks
3. Chunks embedded with `text-embedding-3-small`
4. Stored in `rag_chunks` table
5. Query → Embed → Similarity search → Return top chunks

### LangGraph State
- Persisted in PostgreSQL via `PostgresSaver`
- Thread ID = `session_id` (usually "web-ui")
- Stores: `property_id`, `property_name`, `messages[]`, `pending_proposal`, etc.

---

## Debugging Commands

### Check Document State
```python
# In backend
from tools.docs_tools import list_docs
docs = list_docs("property-uuid-here")
print(f"Uploaded: {len([d for d in docs if d.get('storage_key')])}")
print(f"Pending: {len([d for d in docs if not d.get('storage_key')])}")
```

### Check RAG Chunks
```sql
-- In Supabase SQL editor
SELECT property_id, document_name, COUNT(*) as chunks
FROM rag_chunks
WHERE property_id = 'property-uuid-here'
GROUP BY property_id, document_name;
```

### Check Session State
```python
# In backend
from agentic import checkpointer
state = checkpointer.get({"configurable": {"thread_id": "web-ui"}})
print(f"Property: {state.get('property_id')}")
print(f"Messages: {len(state.get('messages', []))}")
```

---

## Next Steps / TODOs

1. ✅ Document persistence - DONE
2. ✅ Document list auto-refresh - DONE
3. 🔧 Email sending flow - NEEDS TESTING
4. ⏳ Add full document list UI component
5. ⏳ Test all flows end-to-end
6. ⏳ Add chat history persistence (optional)

---

## Testing Checklist

### Document Upload Flow
- [ ] Drag file onto chat
- [ ] File shows in upload queue
- [ ] Agent confirms upload
- [ ] Document count increases
- [ ] Refresh page → count persists
- [ ] Can ask questions about content

### Email Send Flow  
- [ ] Upload document first
- [ ] Request email
- [ ] Agent asks for email (if not provided)
- [ ] Agent does NOT show document list
- [ ] Agent calls signed_url_for
- [ ] Agent calls send_email immediately
- [ ] Chat confirms "✅ Email enviado"
- [ ] Email arrives in inbox
- [ ] Link in email works

### Numbers Table Flow
- [ ] Say "completar números"
- [ ] Choose template
- [ ] Excel panel opens
- [ ] Can click cells
- [ ] Can write values via chat
- [ ] Table auto-reloads
- [ ] Can close panel

### Property Creation Flow
- [ ] Say "crear propiedad"
- [ ] Provide name
- [ ] Property appears in header
- [ ] Document count shows
- [ ] Refresh → persists

---

**Last Updated:** 2025-11-21 12:55 CET  
**Status:** Core document functionality restored, email flow needs end-to-end testing

