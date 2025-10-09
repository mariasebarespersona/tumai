from __future__ import annotations
import base64
from typing import Dict, Any
from agentic import build_graph

agent = build_graph()

def run_turn(session_id: str, text: str = "", audio_wav_bytes: bytes | None = None,
             property_id: str | None = None, file_tuple: tuple[str, bytes] | None = None) -> Dict[str, Any]:
    state = {"messages": [], "input": text, "audio": audio_wav_bytes, "property_id": property_id}
    # If there is a file to classify, the planner will likely propose_doc_slot first.
    # If you already confirmed, call with action 'link_doc' from UI.
    result = agent.invoke(state, config={"configurable": {"thread_id": session_id}})
    return result

