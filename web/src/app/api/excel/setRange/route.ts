import { NextRequest, NextResponse } from 'next/server'

export async function POST(req: NextRequest) {
  const t0 = Date.now()
  try {
    const { workbookId, address, values, worksheet } = await req.json()
    if (!address) {
      return NextResponse.json({ ok: false, error: 'address_required' }, { status: 400 })
    }

    const fileId = String(workbookId || process.env.EXCEL_FILE_ID || '')
    const token = process.env.GRAPH_ACCESS_TOKEN || ''
    const sheetName = String(worksheet || 'Sheet1')

    if (fileId && token) {
      try {
        // Create persistent session so changes are committed and visible in Excel Online
        const s = await fetch(`https://graph.microsoft.com/v1.0/me/drive/items/${encodeURIComponent(fileId)}/workbook/createSession`, {
          method: 'POST',
          headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
          body: JSON.stringify({ persistChanges: true })
        })
        const sPayload = await s.json()
        const sessionId = sPayload?.id

        // Normalize values to 2D array per Graph API
        const bodyValues = Array.isArray(values)
          ? values
          : [[values]]
        const url = `https://graph.microsoft.com/v1.0/me/drive/items/${encodeURIComponent(fileId)}/workbook/worksheets('${encodeURIComponent(sheetName)}')/range(address='${encodeURIComponent(address)}')`
        const resp = await fetch(url, {
          method: 'PATCH',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
            ,'workbook-session-id': sessionId
          },
          body: JSON.stringify({ values: bodyValues })
        })
        const text = await resp.text()
        let payload: any = null
        try { payload = JSON.parse(text) } catch { payload = text }
        if (!resp.ok) {
          return NextResponse.json({ ok: false, error: 'graph_write_failed', details: payload, ms: Date.now() - t0 }, { status: resp.status })
        }
        return NextResponse.json({ ok: true, mode: 'GRAPH-REAL', workbookId: fileId, address, wrote: bodyValues, ms: Date.now() - t0, response: payload })
      } catch (err: any) {
        return NextResponse.json({ ok: false, error: 'graph_exception', details: err?.message || String(err), ms: Date.now() - t0 }, { status: 500 })
      }
    }

    // Fallback mock if no token/fileId
    return NextResponse.json({
      ok: true,
      workbookId: String(fileId || 'mock-file-id'),
      address: String(address),
      wrote: values ?? null,
      ms: Date.now() - t0,
      mode: 'GRAPH-MOCK',
    })
  } catch (e: any) {
    return NextResponse.json({ ok: false, error: e?.message || String(e) }, { status: 400 })
  }
}


