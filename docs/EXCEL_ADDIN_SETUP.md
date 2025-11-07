Excel Add-in Setup (Dev)

This repo ships a minimal Office.js task pane add-in used for real-time events and local writes.

- Files live in `packages/excel-addin/public/`.
- Dev server: `python3 -m http.server 4300 -d packages/excel-addin/public`
- Manifest: create a sideload manifest that points to `http://localhost:4300/panel.html` (left as TODO).

Steps (sideloading)
1. Start dev server (see scripts in README).
2. In Excel Web/Desktop, sideload a task pane add-in using a manifest that references the above URL.
3. Click "Suscribirse a cambios" then edit cells to emit `postMessage` events back to the web app.

Permissions
- Taskpane add-ins require minimal permissions. Start with `ReadWriteDocument` for write.

Known limitations
- Cross-origin messaging is allowed with `*` in dev; restrict in production.
- Not packaged; production requires AppSource packaging or centralized deployment.

