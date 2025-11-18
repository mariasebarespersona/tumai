# Operación y Runbooks

## Entornos
- Backend (FastAPI) local:
  - `uvicorn app:app --reload --port 7901`
  - CORS por defecto: `http://localhost:3000,3004,3005,3006` (configurable con `WEB_BASE` o `ALLOW_ALL_CORS=1`)
  - Memoria (LangGraph checkpointer): SQLite en `data/checkpoints.db` (opcional `DATABASE_URL` para Postgres)
- Frontend (Next.js) local:
  - `cd web && NEXT_PUBLIC_API_URL=http://127.0.0.1:7901 npm run dev`

## Numbers (R2B) – DB-only
1) Subir Excel R2B una vez (UI). Se replica en Supabase (`numbers_templates`, `numbers_table_values`).
2) Escribir valores por chat (celdas amarillas). Cálculo en cascada automático.
3) Exportar: `export_numbers_table`.

## Migraciones Supabase
- Ejecutar en el SQL Editor:
  - `migrations/2025-11-03_document_framework_v2.sql`
  - `migrations/2025-11-17_docs_security_definer.sql`
  - `migrations/2025-11-17_numbers_indexes.sql`
- CLI (opcional):
```bash
supabase db execute --file migrations/2025-11-03_document_framework_v2.sql
supabase db execute --file migrations/2025-11-17_docs_security_definer.sql
supabase db execute --file migrations/2025-11-17_numbers_indexes.sql
```

## Recordatorios (cron)
- En local/staging, ejecuta:
```bash
python send_reminders_cron.py
```
- Scripts de apoyo:
  - `scripts/cron/reminders.sh` (shell wrapper)
  - `setup_reminders.py` (wrapper para inicialización)

## Observabilidad
- Cada request loguea: `method path status ms`.
- Verifier (log-only) tras set_cell: confirma persistencia y valores numéricos calculados.

## Carpeta vendor/
- Binarios de terceros (`vendor/ffmpeg`, `vendor/ffmpeg.7z`). Solo usados por herramientas multimedia; no afectan a Numbers ni Docs.


