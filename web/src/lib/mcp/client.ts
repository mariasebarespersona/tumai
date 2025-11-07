export type McpExcelResult<T=any> = {
  ok: boolean
  mode: 'OFFICEJS' | 'GRAPH' | string
  data?: T
  proxy?: string
  error?: { message: string, code?: string } | any
  ms?: number
}

const MCP_URL = process.env.NEXT_PUBLIC_MCP_URL || 'http://127.0.0.1:4310/jsonrpc'

async function rpc<T=any>(method: string, params: any): Promise<McpExcelResult<T>> {
  const t0 = Date.now()
  const res = await fetch(MCP_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id: crypto.randomUUID?.() || '1', jsonrpc: '2.0', method, params })
  })
  const payload = await res.json().catch(() => ({}))
  const result = payload?.result as McpExcelResult<T>
  if (!result) return { ok: false, mode: 'UNKNOWN', error: { message: 'no_result' }, ms: Date.now() - t0 }
  // If server asks to proxy to officejs client, try Graph fallback (Next.js API)
  if ((result as any).proxy === 'officejs-client') {
    try {
      const resp = await fetch(`/api/excel/getRange`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(params || {})
      })
      const data = await resp.json().catch(() => null)
      return { ok: true, mode: result.mode, data: data, ms: Date.now() - t0 }
    } catch (e) {
      return { ok: false, mode: result.mode, error: { message: 'officejs_proxy_failed', details: String(e) }, ms: Date.now() - t0 }
    }
  }

  return result
}

export const mcpExcel = {
  // Accept optional propertyId to route WS messages to the correct add-in instance
  getRange: (address: string, workbookId?: string, propertyId?: string) => rpc('excel.get_range', { address, workbookId, propertyId }),
  setRange: (address: string, values: any[][] | any, workbookId?: string, propertyId?: string) => rpc('excel.set_range', { address, values, workbookId, propertyId }),
  appendRow: (tableName: string, values: any[] | any, workbookId?: string, propertyId?: string) => rpc('excel.append_row', { tableName, values, workbookId, propertyId }),
}


