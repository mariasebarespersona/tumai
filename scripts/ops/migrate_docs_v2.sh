#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
if ! command -v supabase >/dev/null 2>&1; then
  echo "Supabase CLI not found. Install from https://supabase.com/docs/guides/cli" >&2
  exit 1
fi
supabase db execute --file migrations/2025-11-03_document_framework_v2.sql
supabase db execute --file migrations/2025-11-17_docs_security_definer.sql
echo "✅ Docs V2 migrations executed"


