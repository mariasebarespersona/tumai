'use client'

import { useState } from 'react'
import { mcpExcel } from '@/lib/mcp/client'

export default function ExcelInspector() {
  const [out, setOut] = useState<any>(null)
  const [addr, setAddr] = useState('A1:B2')

  return (
    <div className="p-6 space-y-4">
      <h2 className="text-xl font-bold text-[color:var(--c-green-800)]">Excel Inspector (dev)</h2>
      <div className="flex gap-2 items-center">
        <input className="border rounded px-3 py-2" value={addr} onChange={e => setAddr(e.target.value)} />
        <button onClick={async () => setOut(await mcpExcel.getRange(addr))} className="px-4 py-2 rounded bg-[color:var(--c-green-600)] text-white">Leer rango</button>
      </div>
      <pre className="bg-white rounded p-3 border text-xs overflow-auto">{JSON.stringify(out, null, 2)}</pre>
    </div>
  )
}


