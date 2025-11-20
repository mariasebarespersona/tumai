'use client'

import { useEffect, useState } from 'react'

interface EvalMetrics {
  summary: {
    total_feedbacks: number
    positive_count: number
    negative_count: number
    satisfaction_rate: number | null
    avg_tool_accuracy: number | null
    avg_response_quality: number | null
    task_success_rate: number | null
  }
  recent_negative: Array<{
    id: string
    created_at: string
    agent_name: string
    user_message: string
    comment: string | null
  }>
  by_agent: Record<string, {
    total: number
    positive: number
    negative: number
    satisfaction_rate: number
  }>
}

export default function EvalsPage() {
  const [metrics, setMetrics] = useState<EvalMetrics | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [timeRange, setTimeRange] = useState(24) // hours

  useEffect(() => {
    loadMetrics()
  }, [timeRange])

  const loadMetrics = async () => {
    try {
      setLoading(true)
      setError(null)

      const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:7901'
      const response = await fetch(`${BACKEND_URL}/api/dashboard/evals?time_range_hours=${timeRange}`)

      if (!response.ok) {
        throw new Error(`Failed to load metrics: ${response.status}`)
      }

      const data = await response.json()
      setMetrics(data)
    } catch (err: any) {
      console.error('Error loading metrics:', err)
      setError(err?.message || String(err))
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-[color:var(--c-green-50)] to-[color:var(--c-green-100)]">
        <div className="text-center">
          <div className="animate-spin rounded-full h-16 w-16 border-4 border-[color:var(--c-green-200)] border-t-[color:var(--c-green-600)] mx-auto mb-4"></div>
          <div className="text-[color:var(--c-green-800)] font-semibold">Cargando métricas...</div>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-[color:var(--c-green-50)] to-[color:var(--c-green-100)]">
        <div className="max-w-md mx-auto p-8 rounded-2xl bg-white border-2 border-red-300 nature-shadow">
          <div className="text-center">
            <div className="text-4xl mb-4">❌</div>
            <div className="text-lg font-bold text-red-800 mb-2">Error</div>
            <div className="text-sm text-red-600 mb-4">{error}</div>
            <button
              onClick={loadMetrics}
              className="px-6 py-2 rounded-xl bg-[color:var(--c-green-600)] text-white font-semibold hover:bg-[color:var(--c-green-700)]"
            >
              Reintentar
            </button>
          </div>
        </div>
      </div>
    )
  }

  if (!metrics) {
    return null
  }

  const { summary, recent_negative, by_agent } = metrics

  return (
    <div className="min-h-screen bg-gradient-to-br from-[color:var(--c-green-50)] to-[color:var(--c-green-100)] p-8">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-4xl font-bold text-[color:var(--c-green-800)] mb-2">
              📊 Evaluaciones del Agente
            </h1>
            <p className="text-[color:var(--c-green-600)]">
              Métricas de calidad y feedback de usuarios
            </p>
          </div>

          {/* Time range selector */}
          <div className="flex items-center gap-2">
            <span className="text-sm text-[color:var(--c-green-700)] font-medium">Período:</span>
            <select
              value={timeRange}
              onChange={(e) => setTimeRange(Number(e.target.value))}
              className="px-4 py-2 rounded-xl border-2 border-[color:var(--c-green-300)] bg-white font-semibold text-[color:var(--c-green-800)] focus:ring-2 focus:ring-[color:var(--c-green-500)]"
            >
              <option value={1}>Última hora</option>
              <option value={24}>Últimas 24h</option>
              <option value={168}>Última semana</option>
              <option value={720}>Último mes</option>
            </select>
          </div>
        </div>

        {/* KPI Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {/* User Satisfaction */}
          <div className="rounded-2xl bg-white border-2 border-[color:var(--c-green-300)] p-6 nature-shadow">
            <div className="flex items-center gap-3 mb-3">
              <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-[color:var(--c-green-500)] to-[color:var(--c-green-600)] flex items-center justify-center text-2xl">
                👍
              </div>
              <div className="text-sm font-semibold text-[color:var(--c-green-700)]">
                Satisfacción
              </div>
            </div>
            <div className="text-4xl font-bold text-[color:var(--c-green-800)] mb-2">
              {summary.satisfaction_rate !== null ? `${summary.satisfaction_rate}%` : 'N/A'}
            </div>
            <div className="text-sm text-[color:var(--c-green-600)]">
              {summary.positive_count} 👍 / {summary.negative_count} 👎
            </div>
          </div>

          {/* Tool Accuracy */}
          <div className="rounded-2xl bg-white border-2 border-blue-300 p-6 nature-shadow">
            <div className="flex items-center gap-3 mb-3">
              <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-blue-500 to-blue-600 flex items-center justify-center text-2xl">
                🎯
              </div>
              <div className="text-sm font-semibold text-blue-700">
                Precisión Tools
              </div>
            </div>
            <div className="text-4xl font-bold text-blue-800 mb-2">
              {summary.avg_tool_accuracy !== null ? `${(summary.avg_tool_accuracy * 100).toFixed(1)}%` : 'N/A'}
            </div>
            <div className="text-sm text-blue-600">
              Herramientas correctas
            </div>
          </div>

          {/* Response Quality */}
          <div className="rounded-2xl bg-white border-2 border-purple-300 p-6 nature-shadow">
            <div className="flex items-center gap-3 mb-3">
              <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-purple-500 to-purple-600 flex items-center justify-center text-2xl">
                📝
              </div>
              <div className="text-sm font-semibold text-purple-700">
                Calidad
              </div>
            </div>
            <div className="text-4xl font-bold text-purple-800 mb-2">
              {summary.avg_response_quality !== null ? `${(summary.avg_response_quality * 100).toFixed(0)}%` : 'N/A'}
            </div>
            <div className="text-sm text-purple-600">
              LLM-as-Judge
            </div>
          </div>

          {/* Task Success */}
          <div className="rounded-2xl bg-white border-2 border-amber-300 p-6 nature-shadow">
            <div className="flex items-center gap-3 mb-3">
              <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-amber-500 to-amber-600 flex items-center justify-center text-2xl">
                ✅
              </div>
              <div className="text-sm font-semibold text-amber-700">
                Éxito
              </div>
            </div>
            <div className="text-4xl font-bold text-amber-800 mb-2">
              {summary.task_success_rate !== null ? `${summary.task_success_rate}%` : 'N/A'}
            </div>
            <div className="text-sm text-amber-600">
              Tareas completadas
            </div>
          </div>
        </div>

        {/* By Agent Breakdown */}
        {Object.keys(by_agent).length > 0 && (
          <div className="rounded-2xl bg-white border-2 border-[color:var(--c-green-300)] p-6 nature-shadow">
            <h2 className="text-xl font-bold text-[color:var(--c-green-800)] mb-4">
              📊 Por Agente
            </h2>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b-2 border-[color:var(--c-green-200)]">
                    <th className="text-left py-3 px-4 text-sm font-semibold text-[color:var(--c-green-700)]">
                      Agente
                    </th>
                    <th className="text-center py-3 px-4 text-sm font-semibold text-[color:var(--c-green-700)]">
                      Total
                    </th>
                    <th className="text-center py-3 px-4 text-sm font-semibold text-[color:var(--c-green-700)]">
                      Positivo
                    </th>
                    <th className="text-center py-3 px-4 text-sm font-semibold text-[color:var(--c-green-700)]">
                      Negativo
                    </th>
                    <th className="text-center py-3 px-4 text-sm font-semibold text-[color:var(--c-green-700)]">
                      Satisfacción
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(by_agent).map(([agentName, stats]) => (
                    <tr key={agentName} className="border-b border-[color:var(--c-green-100)] hover:bg-[color:var(--c-green-50)]">
                      <td className="py-3 px-4 font-medium text-[color:var(--c-green-800)]">
                        {agentName}
                      </td>
                      <td className="text-center py-3 px-4 text-[color:var(--c-green-700)]">
                        {stats.total}
                      </td>
                      <td className="text-center py-3 px-4 text-[color:var(--c-green-600)]">
                        {stats.positive} 👍
                      </td>
                      <td className="text-center py-3 px-4 text-red-600">
                        {stats.negative} 👎
                      </td>
                      <td className="text-center py-3 px-4">
                        <span className={`px-3 py-1 rounded-full font-semibold text-sm ${
                          stats.satisfaction_rate >= 80 ? 'bg-[color:var(--c-green-100)] text-[color:var(--c-green-700)]' :
                          stats.satisfaction_rate >= 60 ? 'bg-amber-100 text-amber-700' :
                          'bg-red-100 text-red-700'
                        }`}>
                          {stats.satisfaction_rate.toFixed(1)}%
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Recent Negative Feedback */}
        {recent_negative.length > 0 && (
          <div className="rounded-2xl bg-white border-2 border-red-300 p-6 nature-shadow">
            <h2 className="text-xl font-bold text-red-800 mb-4">
              👎 Feedback Negativo Reciente
            </h2>
            <div className="space-y-3">
              {recent_negative.map((feedback) => (
                <div
                  key={feedback.id}
                  className="rounded-xl border-2 border-red-200 bg-red-50 p-4 hover:border-red-300 transition-all"
                >
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <span className="px-2 py-1 rounded-lg bg-red-200 text-red-800 text-xs font-semibold">
                        {feedback.agent_name}
                      </span>
                      <span className="text-xs text-red-600">
                        {new Date(feedback.created_at).toLocaleString('es-ES')}
                      </span>
                    </div>
                  </div>
                  <div className="text-sm text-red-900 mb-2 font-medium">
                    📝 Usuario: "{feedback.user_message}"
                  </div>
                  {feedback.comment && (
                    <div className="text-sm text-red-700 italic">
                      💬 "{feedback.comment}"
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* No data message */}
        {summary.total_feedbacks === 0 && (
          <div className="rounded-2xl bg-white border-2 border-[color:var(--c-green-300)] p-12 nature-shadow text-center">
            <div className="text-6xl mb-4">📊</div>
            <div className="text-2xl font-bold text-[color:var(--c-green-800)] mb-2">
              No hay datos aún
            </div>
            <div className="text-[color:var(--c-green-600)] mb-6">
              Los usuarios aún no han dado feedback. Aparecerá aquí cuando empiecen a usar los botones 👍/👎 en el chat.
            </div>
            <button
              onClick={loadMetrics}
              className="px-6 py-3 rounded-xl bg-[color:var(--c-green-600)] text-white font-semibold hover:bg-[color:var(--c-green-700)] transition-all"
            >
              Recargar
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

