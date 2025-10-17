Recommended Supabase tables (public schema) for Numbers Agent

1) calc_outputs
- property_id uuid primary key
- outputs jsonb not null
- anomalies jsonb not null default '[]'
- updated_at timestamptz default now()

2) calc_log
- id uuid primary key default gen_random_uuid()
- property_id uuid not null
- inputs jsonb not null
- outputs jsonb not null
- anomalies jsonb not null default '[]'
- triggered_by text not null
- trigger_type text not null
- created_at timestamptz default now()
Indexes: (property_id, created_at desc)

3) scenario_snapshots
- id uuid primary key default gen_random_uuid()
- property_id uuid not null
- name text not null
- deltas jsonb
- outputs jsonb
- created_at timestamptz default now()
Indexes: (property_id, created_at desc)

4) chart_cache
- id uuid primary key default gen_random_uuid()
- property_id uuid not null
- chart_type text not null
- params jsonb
- storage_key text not null
- created_at timestamptz default now()
Indexes: (property_id, chart_type, created_at desc)

Note: All writes are best-effort in code; creating these tables ensures full persistence. Apply SQL in Supabase SQL editor.


