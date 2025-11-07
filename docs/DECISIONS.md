Architectural decisions

- Keep Next.js as the primary frontend. New UI lives inside existing pages/app structure.
- Office.js add-in provides low-latency edits and onChanged events (best UX when user has Excel open).
- Microsoft Graph acts as universal fallback (works without add-in), but lacks real-time events.
- MCP server (dev) exposes excel.* tools via JSON-RPC. In GRAPH mode it proxies to Next.js API; in OFFICEJS it signals the client to use the Office.js adapter directly.
- Iframe vs add-in: chose add-in for events and security in Excel host. We still render an embed in the app for visibility, but writes/events originate from the add-in.

Migration to real Graph auth
- Replace mock handlers with token acquisition (Entra ID), persist workbook-session, implement retries.
- Wire MCP server to call Graph directly (avoid going through Next.js if desired).


