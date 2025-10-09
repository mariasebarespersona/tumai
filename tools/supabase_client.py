from __future__ import annotations
import os
from supabase import create_client, Client

_url = os.getenv("SUPABASE_URL")
_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
if not _url or not _key:
    raise RuntimeError("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY in env")

sb: Client = create_client(_url, _key)
BUCKET = os.getenv("SUPABASE_BUCKET", "property-docs")
