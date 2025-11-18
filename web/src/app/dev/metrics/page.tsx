/* Metrics Dashboard (dev) */
"use client"
import React, { useEffect, useMemo, useState } from "react"

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:7901"

export default function MetricsPage() {
  const [summary, setSummary] = useState<any>(null)
  const [series, setSeries] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [route, setRoute] = useState<string>("")

  async function load() {
    setLoading(true); setError(null)
    try {
      const s = await fetch(`${BACKEND_URL}/api/metrics/summary`).then(r=>r.json())
      if (!s.ok) throw new Error(s.error || "summary error")
      setSummary(s.summary)
      const q = new URLSearchParams()
      if (route) q.set("path", route)
      const ser = await fetch(`${BACKEND_URL}/api/metrics/series?${q.toString()}`).then(r=>r.json())
      if (!ser.ok) throw new Error(ser.error || "series error")
      setSeries(ser.series)
    } catch (e:any) {
      setError(String(e.message||e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(()=>{ load() }, [route])

  const kpis = useMemo(()=>{
    if (!summary) return []
    return [
      { label: "Requests (1h)", value: summary.total_requests },
      { label: "Error rate", value: `${summary.error_rate_pct}%` },
      { label: "Avg latency", value: `${summary.avg_ms} ms` },
    ]
  }, [summary])

  function Bar({ value, max }: { value:number, max:number }) {
    const pct = max>0 ? Math.round((value/max)*100) : 0
    return <div className="h-2 bg-gray-200 rounded"><div className="h-2 bg-[color:var(--c-green-600)] rounded" style={{width:`${pct}%`}}/></div>
  }

  function Sparkline({ data }: { data:number[] }) {
    const max = Math.max(1, ...data)
    const points = data.map((v, i) => `${i*4},${20 - Math.round((v/max)*20)}`).join(" ")
    return <svg width={data.length*4} height={20}><polyline fill="none" stroke="#22c55e" strokeWidth="2" points={points}/></svg>
  }

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="text-2xl font-bold mb-4 text-[color:var(--c-green-800)]">Metrics Dashboard</div>
      <div className="flex items-center gap-3 mb-4">
        <input value={route} onChange={e=>setRoute(e.target.value)} placeholder="Filter by route (e.g., /api/numbers/set-cell-value)" className="border rounded px-3 py-2 w-full"/>
        <button onClick={load} className="px-3 py-2 rounded bg-[color:var(--c-green-700)] text-white">Refresh</button>
      </div>
      {loading ? <div>Loading...</div> : error ? <div className="text-red-600">Error: {error}</div> : (
        <>
          <div className="grid grid-cols-3 gap-4 mb-6">
            {kpis.map(k => (
              <div key={k.label} className="rounded-2xl border-2 border-[color:var(--c-green-200)] bg-white p-4">
                <div className="text-sm text-[color:var(--c-green-600)]">{k.label}</div>
                <div className="text-2xl font-bold text-[color:var(--c-green-800)]">{k.value}</div>
              </div>
            ))}
          </div>
          <div className="grid grid-cols-2 gap-6">
            <div className="rounded-2xl border-2 border-[color:var(--c-green-200)] bg-white p-4">
              <div className="font-semibold text-[color:var(--c-green-800)] mb-2">Top Routes (1h)</div>
              <div className="space-y-2">
                {summary?.top_routes?.map((r:any)=>(
                  <div key={r.path}>
                    <div className="flex justify-between text-sm"><span>{r.path}</span><span>{r.count} • {r.avg_ms} ms</span></div>
                    <Bar value={r.count} max={summary.top_routes[0]?.count||1}/>
                  </div>
                ))}
              </div>
            </div>
            <div className="rounded-2xl border-2 border-[color:var(--c-green-200)] bg-white p-4">
              <div className="font-semibold text-[color:var(--c-green-800)] mb-2">Top Events (1h)</div>
              <div className="space-y-2">
                {summary?.top_events?.map((e:any)=>(
                  <div key={e.name} className="flex justify-between text-sm">
                    <span>{e.name}</span><span>{e.count}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
          <div className="rounded-2xl border-2 border-[color:var(--c-green-200)] bg-white p-4 mt-6">
            <div className="font-semibold text-[color:var(--c-green-800)] mb-2">Traffic (counts & avg ms)</div>
            <div className="flex items-center gap-4">
              <div>
                <div className="text-xs text-gray-600 mb-1">Requests/min</div>
                <Sparkline data={series?.count||[]}/>
              </div>
              <div>
                <div className="text-xs text-gray-600 mb-1">Avg ms</div>
                <Sparkline data={series?.avg_ms||[]}/>
              </div>
              <div>
                <div className="text-xs text-gray-600 mb-1">Errors/min</div>
                <Sparkline data={series?.errors||[]}/>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  )
}

