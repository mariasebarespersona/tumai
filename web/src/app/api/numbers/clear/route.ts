import { NextRequest, NextResponse } from 'next/server'

const BACKEND_URL = (() => {
  if (process.env.BACKEND_URL) return process.env.BACKEND_URL;
  const host = process.env.BACKEND_HOST;
  if (host) return `https://${host}`;
  return 'http://127.0.0.1:7901';
})();

export async function POST(req: NextRequest) {
  try {
    const body = await req.json()
    const { property_id } = body || {}
    if (!property_id) return NextResponse.json({ error: 'property_id required' }, { status: 400 })

    const resp = await fetch(`${BACKEND_URL}/api/numbers/clear`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({ property_id })
    })
    const data = await resp.json()
    return NextResponse.json(data)
  } catch (e: any) {
    return NextResponse.json({ error: e?.message || String(e) }, { status: 500 })
  }
}


