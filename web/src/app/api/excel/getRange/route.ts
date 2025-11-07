import { NextRequest, NextResponse } from 'next/server'

export async function POST(req: NextRequest) {
  const t0 = Date.now()
  try {
    const { workbookId, address, worksheet } = await req.json()
    const fileId = String(workbookId || process.env.EXCEL_FILE_ID || '')
    const token = process.env.GRAPH_ACCESS_TOKEN || ''
    const sheetName = String(worksheet || 'Sheet1')

    if (fileId && token) {
      try {
        // Create persistent session
        const s = await fetch(`https://graph.microsoft.com/v1.0/me/drive/items/${encodeURIComponent(fileId)}/workbook/createSession`, {
          method: 'POST',
          headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
          body: JSON.stringify({ persistChanges: true })
        })
        const sPayload = await s.json()
        const sessionId = sPayload?.id
        const url = `https://graph.microsoft.com/v1.0/me/drive/items/${encodeURIComponent(fileId)}/workbook/worksheets('${encodeURIComponent(sheetName)}')/range(address='${encodeURIComponent(address)}')`
        const resp = await fetch(url, { headers: { 'Authorization': `Bearer ${token}`, 'workbook-session-id': sessionId } })
        const data = await resp.json()
        if (!resp.ok) return NextResponse.json({ ok: false, error: 'graph_get_failed', details: data, ms: Date.now() - t0 }, { status: resp.status })
        return NextResponse.json({ ok: true, mode: 'GRAPH-REAL', workbookId: fileId, address, values: data?.values || null, ms: Date.now() - t0 })
      } catch (err: any) {
        return NextResponse.json({ ok: false, error: 'graph_exception', details: err?.message || String(err), ms: Date.now() - t0 }, { status: 500 })
      }
    }

    // Mock fallback
    return NextResponse.json({
      ok: true,
      address: String(address || 'A1:B2'),
      workbookId: String(fileId || 'mock-file-id'),
      values: [["mock", 123], ["data", 456]],
      ms: Date.now() - t0,
      mode: 'GRAPH-MOCK',
    })
  } catch (e: any) {
    return NextResponse.json({ ok: false, error: e?.message || String(e) }, { status: 400 })
  }
}


