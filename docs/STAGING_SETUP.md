# Supabase Staging Setup & Clone Guide

This guide explains how to create a staging Supabase project and clone a property (DB + Storage + Numbers) from the current project to staging.

## 1) Environment variables

Add the following to your `.env` (do NOT replace your existing SUPABASE_*):

```
STAGING_SUPABASE_URL=...
STAGING_SERVICE_ROLE_KEY=...
STAGING_ANON_KEY=...
# Optional (defaults to 'property-docs')
STAGING_SUPABASE_BUCKET=property-docs
```

## 2) Clone command

From repo root:

```
python scripts/clone_property_to_staging.py --source-name "15Panes"
```

Options:
- `--property-id <uuid>`: use an explicit property id instead of name
- `--bucket <bucket>`: override bucket (default: STAGING_SUPABASE_BUCKET or SUPABASE_BUCKET or 'property-docs')

The script will:
1. Create the property in staging (reusing source id if possible)
2. Ensure documents schema exists in staging
3. Copy uploaded files from source Storage to staging Storage
4. Link files to the correct document cells in staging
5. Copy Numbers template structure and values (if staging already has values, value copy is skipped)

## 3) Deploy variables

When deploying the demo:
- Backend (Railway): use STAGING_SUPABASE_URL / STAGING_SERVICE_ROLE_KEY
- Frontend (Vercel): use STAGING_SUPABASE_URL / STAGING_ANON_KEY and `NEXT_PUBLIC_BACKEND_URL`
- CORS: allow the Vercel domain in backend

## 4) Rollback

To point the app back to your current project, change env vars in the deploy back to `SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY` (backend) and `SUPABASE_URL` / `SUPABASE_ANON_KEY` (frontend).

## 5) Safety

- The script never modifies your source project.
- The staging project receives a copy. You can delete it safely after the demo.


