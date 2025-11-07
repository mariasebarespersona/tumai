Graph mode (fallback)

Environment (.env.example)
- MCP_MODE=GRAPH
- GRAPH_TENANT_ID=...
- GRAPH_CLIENT_ID=...
- GRAPH_CLIENT_SECRET=...
- EXCEL_FILE_ID=...  # OneDrive/SharePoint file id

Handlers
- app/api/excel/getRange
- app/api/excel/setRange
- app/api/excel/appendRow

These handlers currently mock responses when no token is available. Replace the internals with calls to:
- GET/POST https://graph.microsoft.com/v1.0/me/drive/items/{fileId}/workbook/...

Persistent sessions
- Use workbook session header: `workbook-session-id` to persist changes.
- Start with `createSession` endpoint; store id in server memory.

Scopes (Entra ID)
- Files.ReadWrite, offline_access.


