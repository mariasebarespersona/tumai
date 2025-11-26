#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
import argparse
import json
import time
from typing import Optional, Tuple, Dict, Any

import requests

# Import dynamic client helpers without altering the global sb
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from tools.supabase_client import get_supabase_client  # noqa: E402
from tools.supabase_client import get_staging_client, get_bucket_name  # noqa: E402


def log(msg: str):
    print(f"[clone_to_staging] {msg}", flush=True)


def get_source_and_dest_clients() -> Tuple[Any, Any, str]:
    """Return (source_client, dest_client, bucket_name)."""
    # Source: default SUPABASE_URL / SERVICE_ROLE
    src = get_supabase_client()
    # Dest: staging
    dst = get_staging_client()
    bucket = os.getenv("STAGING_SUPABASE_BUCKET") or get_bucket_name("property-docs")
    return src, dst, bucket


def resolve_property_id(sb_client, name_hint: Optional[str], explicit_id: Optional[str]) -> Tuple[str, Dict]:
    """Resolve a property id from either explicit uuid or by name (exact match) or unique row."""
    sb_client.postgrest.schema = "public"
    if explicit_id:
        row = sb_client.table("properties").select("*").eq("id", explicit_id).limit(1).execute().data
        if not row:
            raise RuntimeError(f"Property id not found: {explicit_id}")
        return explicit_id, row[0]
    if name_hint:
        rows = (sb_client.table("properties")
                .select("*")
                .ilike("name", name_hint)
                .limit(5)
                .execute().data or [])
        if not rows:
            # Try exact also
            rows = (sb_client.table("properties")
                    .select("*")
                    .eq("name", name_hint)
                    .limit(5)
                    .execute().data or [])
        if not rows:
            raise RuntimeError(f"Property named '{name_hint}' not found in source")
        # Prefer exact case-insensitive match
        exact = [r for r in rows if r.get("name", "").lower() == name_hint.lower()]
        row = exact[0] if exact else rows[0]
        return row["id"], row
    # Fallback: if there's exactly one property
    rows = sb_client.table("properties").select("*").limit(2).execute().data or []
    if len(rows) == 0:
        raise RuntimeError("No properties found in source project")
    if len(rows) > 1:
        raise RuntimeError("Multiple properties found; please specify --source-name or --property-id")
    return rows[0]["id"], rows[0]


def ensure_dest_property(dst, src_property: Dict) -> Tuple[str, bool]:
    """
    Create the property in destination with the same id if possible.
    Returns (dest_property_id, created_new)
    """
    dst.postgrest.schema = "public"
    pid = src_property["id"]
    exists = dst.table("properties").select("id").eq("id", pid).limit(1).execute().data
    if exists:
        return pid, False
    # Try inserting with explicit id
    payload = {
        "id": pid,
        "name": src_property.get("name"),
        "address": src_property.get("address"),
        "strategy": src_property.get("strategy")
    }
    try:
        dst.table("properties").insert(payload).execute()
        return pid, True
    except Exception:
        # Insert without id (let DB generate), then return the new id
        ins = dst.table("properties").insert({
            "name": src_property.get("name"),
            "address": src_property.get("address"),
            "strategy": src_property.get("strategy")
        }).execute()
        new_id = ins.data[0]["id"]
        log(f"Could not reuse source id; created new property id in staging: {new_id}")
        return new_id, True


def copy_documents(src, dst, bucket: str, src_property_id: str, dst_property_id: str):
    """Copy uploaded documents (files + links) using signed URLs."""
    # Ensure schema exists in destination
    try:
        dst.postgrest.schema = "public"
        dst.rpc("ensure_documents_schema_v2", {"p_id": dst_property_id}).execute()
    except Exception:
        pass
    # list source docs
    src.rpc("list_property_documents", {"p_id": src_property_id}).execute()
    rows = src.rpc("list_property_documents", {"p_id": src_property_id}).execute().data or []
    uploaded = [r for r in rows if r.get("storage_key")]
    log(f"Found {len(uploaded)} uploaded document(s) to copy")
    for r in uploaded:
        g = r.get("document_group")
        sg = r.get("document_subgroup") or ""
        n = r.get("document_name")
        storage_key = r.get("storage_key")
        content_type = r.get("content_type") or "application/octet-stream"
        # Build source signed URL and download
        try:
            signed = src.storage.from_(bucket).create_signed_url(storage_key, 60 * 10)
            url = signed.get("signedURL")
            if not url:
                log(f"  ⚠️ No signed URL for {storage_key}, skipping")
                continue
            resp = requests.get(url, timeout=60)
            resp.raise_for_status()
            data = resp.content
        except Exception as e:
            log(f"  ⚠️ Download failed for {storage_key}: {e}")
            continue
        # Map storage key to new property id if it contains /property/{id}/
        new_key = storage_key
        src_prefix = f"/property/{src_property_id}/"
        if src_prefix in storage_key:
            new_key = storage_key.replace(src_prefix, f"/property/{dst_property_id}/")
        # Upload to destination
        try:
            dst.storage.from_(bucket).upload(new_key, data, {"content-type": content_type, "upsert": "true"})
        except Exception as e:
            log(f"  ⚠️ Upload failed for {new_key}: {e}")
            continue
        # Link in destination DB
        try:
            payload = {
                "p_id": dst_property_id,
                "g": g,
                "sg": sg,
                "n": n,
                "storage_key": new_key,
                "content_type": content_type,
                "metadata": r.get("metadata") or {},
                "signed_url": None,
                "expires_at": None
            }
            dst.rpc("update_property_document_link", payload).execute()
            log(f"  ✅ Copied: {g}/{sg}/{n}")
        except Exception as e:
            log(f"  ⚠️ Link update failed for {g}/{sg}/{n}: {e}")


def copy_numbers(src, dst, src_property_id: str, dst_property_id: str):
    """Copy numbers templates and table values to destination."""
    dst.postgrest.schema = "public"
    src.postgrest.schema = "public"
    # Copy template structures
    try:
        templates = src.table("numbers_templates").select("*").eq("property_id", src_property_id).execute().data or []
        for t in templates:
            payload = {
                "template_key": t.get("template_key"),
                "property_id": dst_property_id,
                "structure_json": t.get("structure_json")
            }
            # Upsert
            existing = dst.table("numbers_templates").select("id").eq("template_key", payload["template_key"]).eq("property_id", dst_property_id).execute().data
            if existing:
                dst.table("numbers_templates").update(payload).eq("id", existing[0]["id"]).execute()
            else:
                dst.table("numbers_templates").insert(payload).execute()
        log(f"Copied {len(templates)} numbers template structure(s)")
    except Exception as e:
        log(f"  ⚠️ Copy numbers templates failed: {e}")
    # Copy table values
    try:
        values = dst.table("numbers_table_values").select("id").eq("property_id", dst_property_id).execute().data or []
        # If destination already has values, skip copying (avoid overwriting tester changes)
        if values:
            log("Destination already has numbers_table_values; skipping value copy")
            return
        values_src = src.table("numbers_table_values").select("*").eq("property_id", src_property_id).execute().data or []
        for v in values_src:
            payload = v.copy()
            payload["property_id"] = dst_property_id
            # remove PK if any
            payload.pop("id", None)
            dst.table("numbers_table_values").insert(payload).execute()
        log(f"Copied {len(values_src)} numbers table value(s)")
    except Exception as e:
        log(f"  ⚠️ Copy numbers values failed: {e}")


def main():
    parser = argparse.ArgumentParser(description="Clone a property (DB + Storage + Numbers) from source Supabase to STAGING Supabase.")
    parser.add_argument("--property-id", help="Source property UUID (optional)")
    parser.add_argument("--source-name", help="Source property name to match (e.g., '15Panes')", default="15Panes")
    parser.add_argument("--bucket", help="Bucket name (defaults to env SUPABASE_BUCKET or 'property-docs')", default=None)
    args = parser.parse_args()

    src, dst, default_bucket = get_source_and_dest_clients()
    bucket = args.bucket or default_bucket
    log(f"Using bucket: {bucket}")

    # Resolve source property
    src_property_id, src_property = resolve_property_id(src, args.source_name, args.property_id)
    log(f"Source property: {src_property.get('name')} ({src_property_id})")

    # Create/resolve dest property (same id if possible)
    dst_property_id, created_new = ensure_dest_property(dst, src_property)
    log(f"Destination property id: {dst_property_id} (created_new={created_new})")

    # Copy documents (files + links)
    copy_documents(src, dst, bucket, src_property_id, dst_property_id)
    # Copy numbers (templates + values)
    copy_numbers(src, dst, src_property_id, dst_property_id)

    log("✅ Clone complete.")
    print(json.dumps({
        "ok": True,
        "source_property_id": src_property_id,
        "dest_property_id": dst_property_id,
        "bucket": bucket
    }, indent=2))


if __name__ == "__main__":
    main()


