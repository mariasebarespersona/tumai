QA Script (manual)

1) Start dev:all (see README). Ensure:
   - Next.js at http://127.0.0.1:3000
   - MCP server at http://127.0.0.1:4310
   - Add-in static at http://127.0.0.1:4300/panel.html

2) In the chat, use Quick Actions:
   - Leer A1:B10 → result in chat + log panel
   - Escribir A1 → observe change in Excel (via add-in if active) or mock Graph response
   - Añadir fila a Tabla1 → success or clear error

3) Edit three cells manually in Excel with the add-in loaded and subscribed:
   - Chat shows three event logs (cellChanged with address/time)

4) Toggle MCP_MODE to GRAPH and restart MCP server:
   - Re-run the three actions → responses go through /api/excel/*


