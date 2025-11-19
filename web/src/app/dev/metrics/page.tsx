/* Metrics Dashboard v2 (dev) */
"use client"
import React, { useEffect, useMemo, useState } from "react"

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:7901"

export default function MetricsPage() {
  const [summary, setSummary] = useState<any>(null)
  const [series, setSeries] = useState<any>(null)
  const [health, setHealth] = useState<any>(null)
  const [llm, setLlm] = useState<any>(null)
  const [business, setBusiness] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [route, setRoute] = useState<string>("")
  const [autoRefresh, setAutoRefresh] = useState(true)

  async function load() {
    setLoading(true); setError(null)
    try {
      // Load all metrics in parallel
      const [h, s, ser, l, b] = await Promise.all([
        fetch(`${BACKEND_URL}/api/metrics/health`).then(r=>r.json()),
        fetch(`${BACKEND_URL}/api/metrics/summary`).then(r=>r.json()),
        fetch(`${BACKEND_URL}/api/metrics/series${route ? `?path=${route}` : ''}`).then(r=>r.json()),
        fetch(`${BACKEND_URL}/api/metrics/llm`).then(r=>r.json()),
        fetch(`${BACKEND_URL}/api/metrics/business`).then(r=>r.json())
      ])
      
      if (h.ok) setHealth(h.health)
      if (!s.ok) throw new Error(s.error || "summary error")
      setSummary(s.summary)
      if (!ser.ok) throw new Error(ser.error || "series error")
      setSeries(ser.series)
      if (l.ok) setLlm(l.llm)
      if (b.ok) setBusiness(b.business)
    } catch (e:any) {
      setError(String(e.message||e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(()=>{ load() }, [route])
  
  // Auto-refresh every 30s
  useEffect(() => {
    if (!autoRefresh) return
    const interval = setInterval(load, 30000)
    return () => clearInterval(interval)
  }, [autoRefresh, route])

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
    <div className="p-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-4">
        <div className="text-2xl font-bold text-[color:var(--c-green-800)]">Metrics Dashboard v2</div>
        <div className="flex items-center gap-2">
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={autoRefresh} onChange={e=>setAutoRefresh(e.target.checked)} />
            Auto-refresh (30s)
          </label>
        </div>
      </div>
      
      <div className="flex items-center gap-3 mb-4">
        <input value={route} onChange={e=>setRoute(e.target.value)} placeholder="Filter by route (e.g., /api/numbers/set-cell-value)" className="border rounded px-3 py-2 w-full"/>
        <button onClick={load} className="px-3 py-2 rounded bg-[color:var(--c-green-700)] text-white whitespace-nowrap">Refresh</button>
      </div>
      
      {loading && !health ? <div>Loading...</div> : error ? <div className="text-red-600">Error: {error}</div> : (
        <>
          {/* Health Status Panel */}
          {health && (
            <div className={`rounded-2xl border-2 p-6 mb-6 ${
              health.status === 'healthy' ? 'border-green-500 bg-green-50' :
              health.status === 'degraded' ? 'border-yellow-500 bg-yellow-50' :
              health.status === 'critical' ? 'border-red-500 bg-red-50' :
              'border-gray-300 bg-gray-50'
            }`}>
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className="text-4xl">
                    {health.status === 'healthy' ? '🟢' :
                     health.status === 'degraded' ? '🟡' :
                     health.status === 'critical' ? '🔴' :
                     '⚪'}
                  </div>
                  <div>
                    <div className="text-2xl font-bold capitalize">{health.status}</div>
                    <div className="text-sm text-gray-600">{health.message}</div>
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-xs text-gray-500">P95 Latency</div>
                  <div className="text-xl font-mono">{health.metrics?.p95_latency_ms}ms</div>
                </div>
              </div>
              
              {health.alerts && health.alerts.length > 0 && (
                <div className="space-y-2">
                  {health.alerts.map((alert: any, i: number) => (
                    <div key={i} className={`p-3 rounded border ${
                      alert.level === 'critical' ? 'bg-red-100 border-red-300' :
                      alert.level === 'warning' ? 'bg-yellow-100 border-yellow-300' :
                      'bg-blue-100 border-blue-300'
                    }`}>
                      <div className="font-semibold text-sm">
                        {alert.level === 'critical' ? '🚨' : '⚠️'} {alert.message}
                      </div>
                    </div>
                  ))}
                </div>
              )}
              
              <div className="grid grid-cols-4 gap-3 mt-4 pt-4 border-t border-gray-300">
                <div>
                  <div className="text-xs text-gray-600">Total Requests</div>
                  <div className="text-lg font-mono">{health.metrics?.total_requests}</div>
                </div>
                <div>
                  <div className="text-xs text-gray-600">Error Rate</div>
                  <div className="text-lg font-mono">{health.metrics?.error_rate_pct}%</div>
                </div>
                <div>
                  <div className="text-xs text-gray-600">Avg Latency</div>
                  <div className="text-lg font-mono">{health.metrics?.avg_latency_ms}ms</div>
                </div>
                <div>
                  <div className="text-xs text-gray-600">Max Latency</div>
                  <div className="text-lg font-mono">{health.metrics?.max_latency_ms}ms</div>
                </div>
              </div>
            </div>
          )}
          
          {/* LLM Cost Panel */}
          {llm && llm.total_calls > 0 && (
            <div className="rounded-2xl border-2 border-blue-200 bg-blue-50 p-6 mb-6">
              <div className="font-semibold text-blue-800 mb-3 text-lg">💰 LLM Usage & Cost (1h)</div>
              <div className="grid grid-cols-4 gap-4 mb-4">
                <div>
                  <div className="text-xs text-blue-600">Total Tokens</div>
                  <div className="text-2xl font-bold text-blue-800">{llm.total_tokens.toLocaleString()}</div>
                </div>
                <div>
                  <div className="text-xs text-blue-600">Total Cost</div>
                  <div className="text-2xl font-bold text-blue-800">${llm.total_cost_usd.toFixed(4)}</div>
                </div>
                <div>
                  <div className="text-xs text-blue-600">API Calls</div>
                  <div className="text-2xl font-bold text-blue-800">{llm.total_calls}</div>
                </div>
                <div>
                  <div className="text-xs text-blue-600">Avg Cost/Call</div>
                  <div className="text-2xl font-bold text-blue-800">${(llm.total_cost_usd / llm.total_calls).toFixed(4)}</div>
                </div>
              </div>
              
              {llm.by_agent && llm.by_agent.length > 0 && (
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <div className="text-sm font-semibold text-blue-700 mb-2">By Agent</div>
                    <div className="space-y-1">
                      {llm.by_agent.map((a: any) => (
                        <div key={a.agent} className="flex justify-between text-sm bg-white p-2 rounded">
                          <span className="font-mono">{a.agent || 'Unknown'}</span>
                          <span className="font-semibold">${a.cost_usd} ({a.tokens.toLocaleString()} tokens)</span>
                        </div>
                      ))}
                    </div>
                  </div>
                  <div>
                    <div className="text-sm font-semibold text-blue-700 mb-2">By Model</div>
                    <div className="space-y-1">
                      {llm.by_model.map((m: any) => (
                        <div key={m.model} className="flex justify-between text-sm bg-white p-2 rounded">
                          <span className="font-mono">{m.model}</span>
                          <span className="font-semibold">${m.cost_usd} ({m.calls} calls)</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}
          
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
