# tools/registry.py
from __future__ import annotations
from typing import List, Dict, Optional, Union
from pydantic import BaseModel, Field
from langchain_core.tools import tool

# import your pure functions
from .property_tools import add_property as _add_property, list_frameworks as _list_frameworks
from .property_tools import get_property as _get_property, find_property as _find_property, list_properties as _list_properties
from .property_tools import search_properties as _search_properties
from .docs_tools import (
    propose_slot as _propose_slot,
    upload_and_link as _upload_and_link,
    list_docs as _list_docs,
    signed_url_for as _signed_url_for,
    slot_exists as _slot_exists,
)
from .numbers_tools import set_number as _set_number, get_numbers as _get_numbers, calc_numbers as _calc_numbers
from .summary_tools import get_summary_spec as _get_summary_spec, upsert_summary_value as _upsert_summary_value, compute_summary as _compute_summary
from .email_tool import send_email as _send_email
from .voice_tool import transcribe_google_wav as _transcribe_google_wav, tts_google as _tts_google
from .rag_tool import summarize_document as _summarize_document, qa_document as _qa_document, qa_payment_schedule as _qa_payment_schedule
from .rag_index import index_document as _index_document, qa_with_citations as _qa_with_citations, index_all_documents as _index_all_documents

# ---------- Schemas ----------

class AddPropertyInput(BaseModel):
    name: str = Field(..., description="Property name as shown to user")
    address: str = Field(..., description="Property full address")

@tool("add_property")
def add_property_tool(name: str, address: str) -> Dict:
    """Create a new property in Supabase (triggers provisioning of 3 frameworks)."""
    return _add_property(name, address)


class ListFrameworksInput(BaseModel):
    property_id: str = Field(..., description="UUID of the property")

@tool("list_frameworks")
def list_frameworks_tool(property_id: str) -> Dict:
    """Return schema names for the property's three frameworks."""
    return _list_frameworks(property_id)


class ProposeDocInput(BaseModel):
    filename: str
    hint: str = Field("", description="Optional free text / user hint to help classification")

@tool("propose_doc_slot")
def propose_doc_slot_tool(filename: str, hint: str = "") -> Dict:
    """Propose where a document should live in the documents framework."""
    return _propose_slot(filename, hint)


class UploadAndLinkInput(BaseModel):
    property_id: str
    filename: str
    bytes_b64: str = Field(..., description="Base64 of the file to upload")
    document_group: str
    document_subgroup: str = ""
    document_name: str
    metadata: Dict = {}

@tool("upload_and_link")
def upload_and_link_tool(property_id: str, filename: str, bytes_b64: str,
                         document_group: str, document_subgroup: str, document_name: str,
                         metadata: Dict) -> Dict:
    """Upload the file to Storage and link it to the correct row in docs framework."""
    import base64
    file_bytes = base64.b64decode(bytes_b64)
    return _upload_and_link(property_id, file_bytes, filename,
                            document_group, document_subgroup, document_name, metadata)


class ListDocsInput(BaseModel):
    property_id: str

@tool("list_docs")
def list_docs_tool(property_id: str) -> List[Dict]:
    """List all rows in the documents framework for this property."""
    return _list_docs(property_id)


class SignedUrlInput(BaseModel):
    property_id: str
    document_group: str
    document_subgroup: str = ""
    document_name: str

@tool("signed_url_for")
def signed_url_for_tool(property_id: str, document_group: str, document_subgroup: str, document_name: str) -> Dict:
    """Create a short-lived signed URL for a stored document."""
    return {"signed_url": _signed_url_for(property_id, document_group, document_subgroup, document_name)}


class SlotExistsInput(BaseModel):
    property_id: str
    document_group: str
    document_subgroup: str = ""
    document_name: str

@tool("slot_exists")
def slot_exists_tool(property_id: str, document_group: str, document_subgroup: str, document_name: str) -> Dict:
    """Check if a document slot exists in the per-property documents framework (and list available names)."""
    return _slot_exists(property_id, document_group, document_subgroup, document_name)


class SetNumberInput(BaseModel):
    property_id: str
    item_key: str
    amount: float

@tool("set_number")
def set_number_tool(property_id: str, item_key: str, amount: float) -> Dict:
    """Set a numeric input in the numbers framework."""
    return _set_number(property_id, item_key, amount)


class GetNumbersInput(BaseModel):
    property_id: str

@tool("get_numbers")
def get_numbers_tool(property_id: str) -> List[Dict]:
    """Return all inputs in numbers framework."""
    return _get_numbers(property_id)


class CalcNumbersInput(BaseModel):
    property_id: str

@tool("calc_numbers")
def calc_numbers_tool(property_id: str) -> List[Dict]:
    """Compute derived metrics using the schema-local calc() function."""
    return _calc_numbers(property_id)


class GetSummarySpecInput(BaseModel):
    property_id: str

@tool("get_summary_spec")
def get_summary_spec_tool(property_id: str) -> List[Dict]:
    """Return the summary spec rows (for the agent to compute later)."""
    return _get_summary_spec(property_id)


class UpsertSummaryValueInput(BaseModel):
    property_id: str
    item_key: str
    amount: float
    provenance: Dict = {}

@tool("upsert_summary_value")
def upsert_summary_value_tool(property_id: str, item_key: str, amount: float, provenance: Dict) -> Dict:
    """Write a summary result value for a given item_key."""
    return _upsert_summary_value(property_id, item_key, amount, provenance)


class SendEmailInput(BaseModel):
    to: List[str]
    subject: str
    html: str

@tool("send_email")
def send_email_tool(to: List[str], subject: str, html: str) -> Dict:
    """Send an email (no attachments by default)."""
    return _send_email(to, subject, html)


# --- compute_summary tool ---
class ComputeSummaryInput(BaseModel):
    property_id: str
    only_items: Optional[List[str]] = Field(default=None, description="Optional list of item_keys to compute only those")

@tool("compute_summary")
def compute_summary_tool(property_id: str, only_items: Optional[List[str]] = None) -> Dict:
    """Compute summary_values per summary_spec: pulls from documents & numbers, evaluates formulas, upserts results."""
    return _compute_summary(property_id, only_items)

# --- Google voice tools ---
class TranscribeAudioInput(BaseModel):
    bytes_b64: str
    language_code: Optional[str] = None

@tool("transcribe_audio")
def transcribe_audio_tool(bytes_b64: str, language_code: Optional[str] = None) -> Dict:
    """Speech-to-Text using Google Cloud Speech. Returns {'text': ...}."""
    import base64
    text = _transcribe_google_wav(base64.b64decode(bytes_b64), language_code)
    return {"text": text}

class SynthesizeSpeechInput(BaseModel):
    text: str
    language_code: Optional[str] = None
    voice_name: Optional[str] = None

@tool("synthesize_speech")
def synthesize_speech_tool(text: str, language_code: Optional[str] = None, voice_name: Optional[str] = None) -> Dict:
    """Text-to-Speech using Google Cloud TTS. Returns {'audio_b64_mp3': ...}."""
    import base64
    audio = _tts_google(text, language_code, voice_name)
    return {"audio_b64_mp3": base64.b64encode(audio).decode("utf-8")}

# --- property query tools ---
class GetPropertyInput(BaseModel):
    property_id: str

@tool("get_property")
def get_property_tool(property_id: str) -> Optional[Dict]:
    """Fetch a property row by UUID."""
    return _get_property(property_id)


class FindPropertyInput(BaseModel):
    name: str
    address: str

@tool("find_property")
def find_property_tool(name: str, address: str) -> Optional[Dict]:
    """Find a property by name and address (exact match)."""
    return _find_property(name, address)


class ListPropertiesInput(BaseModel):
    limit: int = Field(20, ge=1, le=100)

@tool("list_properties")
def list_properties_tool(limit: int = 20) -> List[Dict]:
    """List recent properties for verification and selection."""
    return _list_properties(limit)

class SearchPropertiesInput(BaseModel):
    query: str = Field(..., description="Free text to match name or address (ilike).")
    limit: int = Field(5, ge=1, le=50)

@tool("search_properties")
def search_properties_tool(query: str, limit: int = 5) -> List[Dict]:
    """Search properties by name or address (fuzzy, case-insensitive)."""
    return _search_properties(query, limit)

# --- summarize document (RAG-lite) ---
class SummarizeDocumentInput(BaseModel):
    property_id: str
    document_group: str
    document_subgroup: str = ""
    document_name: str
    model: Optional[str] = None
    max_sentences: int = Field(5, ge=1, le=15)

@tool("summarize_document")
def summarize_document_tool(property_id: str, document_group: str, document_subgroup: str, document_name: str, model: Optional[str] = None, max_sentences: int = 5) -> Dict:
    """Fetches the document via signed URL and returns a short summary. Use when the user asks to summarize a specific document."""
    return _summarize_document(property_id, document_group, document_subgroup, document_name, model, max_sentences)

# --- question-answer on a specific document ---
class QADocumentInput(BaseModel):
    property_id: str
    document_group: str
    document_subgroup: str = ""
    document_name: str
    question: str
    model: Optional[str] = None

@tool("qa_document")
def qa_document_tool(property_id: str, document_group: str, document_subgroup: str, document_name: str, question: str, model: Optional[str] = None) -> Dict:
    """Answer a focused question about a single stored document in Spanish."""
    return _qa_document(property_id, document_group, document_subgroup, document_name, question, model)

# --- payment schedule QA ---
class QAPaymentScheduleInput(BaseModel):
    property_id: str
    document_group: str
    document_subgroup: str = ""
    document_name: str
    today_iso: Optional[str] = None

@tool("qa_payment_schedule")
def qa_payment_schedule_tool(property_id: str, document_group: str, document_subgroup: str, document_name: str, today_iso: Optional[str] = None) -> Dict:
    """Extract payment cadence and compute next due date based on the document text."""
    return _qa_payment_schedule(property_id, document_group, document_subgroup, document_name, today_iso)

# --- RAG indexing + QA with citations ---
class IndexDocumentInput(BaseModel):
    property_id: str
    document_group: str
    document_subgroup: str = ""
    document_name: str

@tool("rag_index_document")
def rag_index_document_tool(property_id: str, document_group: str, document_subgroup: str, document_name: str) -> Dict:
    """Fetches, splits and stores document chunks for retrieval QA."""
    return _index_document(property_id, document_group, document_subgroup, document_name)

class QAWithCitationsInput(BaseModel):
    property_id: str
    query: str
    top_k: int = 5

@tool("rag_qa_with_citations")
def rag_qa_with_citations_tool(property_id: str, query: str, top_k: int = 5) -> Dict:
    """RAG QA over indexed chunks; returns answer and citations."""
    return _qa_with_citations(property_id, query, top_k)

class IndexAllDocumentsInput(BaseModel):
    property_id: str

@tool("rag_index_all_documents")
def rag_index_all_documents_tool(property_id: str) -> Dict:
    """Index all documents with file for a property. Use at session start or when results seem incomplete."""
    return _index_all_documents(property_id)

# Export the registry
TOOLS = [
    add_property_tool,
    list_frameworks_tool,
    propose_doc_slot_tool,
    upload_and_link_tool,
    list_docs_tool,
    signed_url_for_tool,
    set_number_tool,
    get_numbers_tool,
    calc_numbers_tool,
    get_summary_spec_tool,
    upsert_summary_value_tool,
    send_email_tool,
    compute_summary_tool,          # NEW
    transcribe_audio_tool,         # NEW
    synthesize_speech_tool,
    get_property_tool,             # NEW
    find_property_tool,            # NEW
    list_properties_tool,          # NEW
    search_properties_tool,        # NEW
    summarize_document_tool,       # NEW
    qa_document_tool,              # NEW
    qa_payment_schedule_tool,      # NEW
    rag_index_document_tool,       # NEW
    rag_qa_with_citations_tool,    # NEW
    rag_index_all_documents_tool,  # NEW
    slot_exists_tool,              # NEW
]
