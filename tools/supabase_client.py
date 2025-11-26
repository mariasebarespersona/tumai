from __future__ import annotations
import os
from supabase import create_client, Client

_url = os.getenv("SUPABASE_URL")
_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
if not _url or not _key:
    raise RuntimeError("Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY in env")

sb: Client = create_client(_url, _key)
BUCKET = os.getenv("SUPABASE_BUCKET", "property-docs")

# Optional helpers for dynamic clients (staging/support scripts)
def get_supabase_client(url: str | None = None, key: str | None = None) -> Client:
    """
    Return a Supabase client for given URL/key or fallback to default env.
    This does NOT change the globally imported 'sb'.
    """
    url_use = url or os.getenv("SUPABASE_URL")
    key_use = key or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url_use or not key_use:
        raise RuntimeError("Missing Supabase URL/key for client creation")
    return create_client(url_use, key_use)


def get_staging_client() -> Client:
    """
    Return a Supabase client for STAGING_* env vars.
    Expected:
      - STAGING_SUPABASE_URL
      - STAGING_SERVICE_ROLE_KEY
    """
    s_url = os.getenv("STAGING_SUPABASE_URL")
    s_key = os.getenv("STAGING_SERVICE_ROLE_KEY")
    if not s_url or not s_key:
        raise RuntimeError("Missing STAGING_SUPABASE_URL or STAGING_SERVICE_ROLE_KEY in env")
    return create_client(s_url, s_key)


def get_bucket_name(default: str = "property-docs") -> str:
    """
    Return the bucket name to use; for staging you can set SUPABASE_BUCKET or STAGING_SUPABASE_BUCKET.
    """
    return os.getenv("SUPABASE_BUCKET", default)
