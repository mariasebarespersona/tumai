from __future__ import annotations
import datetime as dt
import re
from typing import Tuple

def shortid(uuid_str: str) -> str:
    return re.sub("-", "", uuid_str)[:8]

def docs_schema(pid: str) -> str:
    return f"prop_{shortid(pid)}__documents_framework"

def nums_schema(pid: str) -> str:
    return f"prop_{shortid(pid)}__numbers_framework"

def sum_schema(pid: str) -> str:
    return f"prop_{shortid(pid)}__framework_summary_property"

def utcnow_iso() -> str:
    return dt.datetime.utcnow().isoformat()
