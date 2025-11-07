import { NextRequest, NextResponse } from 'next/server'

export async function POST(req: NextRequest) {
  const t0 = Date.now()
  try {
    const { workbookId, tableName, values } = await req.json()
    if (!tableName) {
      return NextResponse.json({ ok: false, error: 'tableName_required' }, { status: 400 })
    }
    return NextResponse.json({
      ok: true,
      workbookId: String(workbookId || process.env.EXCEL_FILE_ID || 'mock-file-id'),
      tableName: String(tableName),
      appended: Array.isArray(values) ? values : [values ?? null],
      index: Math.floor(Math.random() * 1000),
      ms: Date.now() - t0,
      mode: 'GRAPH-MOCK',
    })
  } catch (e: any) {
    return NextResponse.json({ ok: false, error: e?.message || String(e) }, { status: 400 })
  }
}


