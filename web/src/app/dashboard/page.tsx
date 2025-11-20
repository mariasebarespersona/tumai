"use client";

import { useEffect, useState } from "react";
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:7901";

interface MetricsData {
  summary: {
    total_requests: number;
    total_llm_calls: number;
    total_cost: number;
    total_tokens: number;
    error_count: number;
    avg_latency_ms: number;
  };
  request_rate: Array<{ time: string; count: number }>;
  llm_calls_timeline: Array<{ time: string; count: number }>;
  status_codes: Record<string, number>;
  top_endpoints: Array<{
    endpoint: string;
    requests: number;
    avg_latency_ms: number;
    max_latency_ms: number;
  }>;
  cost_by_model: Array<{
    model: string;
    calls: number;
    cost_usd: number;
    tokens: number;
  }>;
  recent_errors: Array<{
    time: string;
    type: string;
    endpoint: string;
    message: string;
  }>;
}

export default function DashboardPage() {
  const [metrics, setMetrics] = useState<MetricsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [timeRange, setTimeRange] = useState("1h");
  const [autoRefresh, setAutoRefresh] = useState(true);

  const fetchMetrics = async () => {
    try {
      const response = await fetch(`${API_BASE}/api/dashboard/metrics?time_range=${timeRange}`);
      const data = await response.json();
      if (data.ok) {
        setMetrics(data.data);
      }
    } catch (error) {
      console.error("Error fetching metrics:", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMetrics();
  }, [timeRange]);

  useEffect(() => {
    if (autoRefresh) {
      const interval = setInterval(fetchMetrics, 30000); // Refresh every 30s
      return () => clearInterval(interval);
    }
  }, [autoRefresh, timeRange]);

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-orange-500 mx-auto mb-4"></div>
          <p className="text-gray-600">Cargando métricas...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 px-6 py-4 shadow-sm sticky top-0 z-10">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
              📊 RAMA AI Dashboard
            </h1>
            <p className="text-sm text-gray-600 mt-1">
              Observabilidad en tiempo real
            </p>
          </div>
          
          <div className="flex items-center gap-4">
            {/* Time Range Selector */}
            <select
              value={timeRange}
              onChange={(e) => setTimeRange(e.target.value)}
              className="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-orange-500"
            >
              <option value="1h">Última 1 hora</option>
              <option value="6h">Últimas 6 horas</option>
              <option value="24h">Últimas 24 horas</option>
            </select>

            {/* Auto-refresh Toggle */}
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={autoRefresh}
                onChange={(e) => setAutoRefresh(e.target.checked)}
                className="rounded"
              />
              <span className="text-gray-700">Auto-refresh (30s)</span>
            </label>

            {/* Refresh Button */}
            <button
              onClick={fetchMetrics}
              className="px-4 py-2 bg-blue-500 hover:bg-blue-600 text-white rounded-lg text-sm font-medium transition-colors"
            >
              🔄 Refrescar
            </button>

            {/* Logfire Link */}
            <a
              href="https://logfire-eu.pydantic.dev/mariasebarespersona/rama-ai/live"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 px-4 py-2 bg-orange-500 hover:bg-orange-600 text-white rounded-lg text-sm font-medium transition-colors"
            >
              🔥 Ver en Logfire
            </a>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-6 space-y-6">
        {/* Summary Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-6 gap-4">
          <div className="bg-white rounded-lg p-4 shadow-sm border border-gray-200">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Total Requests</p>
                <p className="text-2xl font-bold text-gray-900 mt-1">
                  {metrics?.summary.total_requests || 0}
                </p>
              </div>
              <div className="p-3 bg-blue-100 rounded-lg">
                <svg className="w-6 h-6 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
              </div>
            </div>
          </div>

          <div className="bg-white rounded-lg p-4 shadow-sm border border-gray-200">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">LLM Calls</p>
                <p className="text-2xl font-bold text-gray-900 mt-1">
                  {metrics?.summary.total_llm_calls || 0}
                </p>
              </div>
              <div className="p-3 bg-purple-100 rounded-lg">
                <svg className="w-6 h-6 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                </svg>
              </div>
            </div>
          </div>

          <div className="bg-white rounded-lg p-4 shadow-sm border border-gray-200">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">LLM Cost</p>
                <p className="text-2xl font-bold text-gray-900 mt-1">
                  ${(metrics?.summary.total_cost || 0).toFixed(4)}
                </p>
              </div>
              <div className="p-3 bg-green-100 rounded-lg">
                <svg className="w-6 h-6 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
            </div>
          </div>

          <div className="bg-white rounded-lg p-4 shadow-sm border border-gray-200">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Total Tokens</p>
                <p className="text-2xl font-bold text-gray-900 mt-1">
                  {(metrics?.summary.total_tokens || 0).toLocaleString()}
                </p>
              </div>
              <div className="p-3 bg-indigo-100 rounded-lg">
                <svg className="w-6 h-6 text-indigo-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 21a4 4 0 01-4-4V5a2 2 0 012-2h4a2 2 0 012 2v12a4 4 0 01-4 4zm0 0h12a2 2 0 002-2v-4a2 2 0 00-2-2h-2.343M11 7.343l1.657-1.657a2 2 0 012.828 0l2.829 2.829a2 2 0 010 2.828l-8.486 8.485M7 17h.01" />
                </svg>
              </div>
            </div>
          </div>

          <div className="bg-white rounded-lg p-4 shadow-sm border border-gray-200">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Avg Latency</p>
                <p className="text-2xl font-bold text-gray-900 mt-1">
                  {Math.round(metrics?.summary.avg_latency_ms || 0)}ms
                </p>
              </div>
              <div className="p-3 bg-yellow-100 rounded-lg">
                <svg className="w-6 h-6 text-yellow-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
            </div>
          </div>

          <div className="bg-white rounded-lg p-4 shadow-sm border border-gray-200">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Errors</p>
                <p className="text-2xl font-bold text-gray-900 mt-1">
                  {metrics?.summary.error_count || 0}
                </p>
              </div>
              <div className="p-3 bg-red-100 rounded-lg">
                <svg className="w-6 h-6 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
            </div>
          </div>
        </div>

        {/* Charts Row 1: Request Rate & LLM Calls */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Request Rate Chart */}
          <div className="bg-white rounded-lg p-6 shadow-sm border border-gray-200">
            <h3 className="font-semibold text-gray-900 mb-4">📈 API Request Rate</h3>
            <ResponsiveContainer width="100%" height={250}>
              <LineChart data={metrics?.request_rate || []}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis 
                  dataKey="time" 
                  tickFormatter={(time) => new Date(time).toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' })}
                />
                <YAxis />
                <Tooltip 
                  labelFormatter={(time) => new Date(time).toLocaleString('es-ES')}
                />
                <Legend />
                <Line type="monotone" dataKey="count" stroke="#3b82f6" name="Requests" strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          </div>

          {/* LLM Calls Timeline */}
          <div className="bg-white rounded-lg p-6 shadow-sm border border-gray-200">
            <h3 className="font-semibold text-gray-900 mb-4">🤖 LLM Calls Timeline</h3>
            <ResponsiveContainer width="100%" height={250}>
              <LineChart data={metrics?.llm_calls_timeline || []}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis 
                  dataKey="time" 
                  tickFormatter={(time) => new Date(time).toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' })}
                />
                <YAxis />
                <Tooltip 
                  labelFormatter={(time) => new Date(time).toLocaleString('es-ES')}
                />
                <Legend />
                <Line type="monotone" dataKey="count" stroke="#8b5cf6" name="LLM Calls" strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Charts Row 2: Status Codes & Top Endpoints */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Status Codes */}
          <div className="bg-white rounded-lg p-6 shadow-sm border border-gray-200">
            <h3 className="font-semibold text-gray-900 mb-4">📊 Status Codes</h3>
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={Object.entries(metrics?.status_codes || {}).map(([status, count]) => ({ status, count }))}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="status" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Bar dataKey="count" fill="#22c55e" name="Count" />
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Top Endpoints */}
          <div className="bg-white rounded-lg p-6 shadow-sm border border-gray-200">
            <h3 className="font-semibold text-gray-900 mb-4">🔝 Top Endpoints</h3>
            <div className="space-y-3 max-h-[250px] overflow-y-auto">
              {metrics?.top_endpoints.map((endpoint, idx) => (
                <div key={idx} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-900 truncate">{endpoint.endpoint}</p>
                    <p className="text-xs text-gray-600">{endpoint.requests} requests</p>
                  </div>
                  <div className="text-right ml-4">
                    <p className="text-sm font-semibold text-gray-900">{endpoint.avg_latency_ms}ms</p>
                    <p className="text-xs text-gray-600">avg</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Cost by Model */}
        {metrics?.cost_by_model && metrics.cost_by_model.length > 0 && (
          <div className="bg-white rounded-lg p-6 shadow-sm border border-gray-200">
            <h3 className="font-semibold text-gray-900 mb-4">💰 Cost by Model</h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {metrics.cost_by_model.map((model, idx) => (
                <div key={idx} className="p-4 bg-gradient-to-br from-green-50 to-emerald-50 rounded-lg border border-green-200">
                  <p className="text-sm font-medium text-gray-600">{model.model}</p>
                  <p className="text-2xl font-bold text-gray-900 mt-2">${model.cost_usd.toFixed(4)}</p>
                  <div className="mt-2 text-xs text-gray-600">
                    <span>{model.calls} calls</span>
                    <span className="mx-2">•</span>
                    <span>{model.tokens.toLocaleString()} tokens</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Recent Errors */}
        {metrics?.recent_errors && metrics.recent_errors.length > 0 && (
          <div className="bg-white rounded-lg p-6 shadow-sm border border-gray-200">
            <h3 className="font-semibold text-gray-900 mb-4">⚠️ Recent Errors</h3>
            <div className="space-y-2">
              {metrics.recent_errors.map((error, idx) => (
                <div key={idx} className="p-3 bg-red-50 border border-red-200 rounded-lg">
                  <div className="flex items-start justify-between">
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-red-900">{error.endpoint}</p>
                      <p className="text-xs text-red-700 mt-1">{error.message}</p>
                    </div>
                    <span className="text-xs text-red-600 ml-4">
                      {new Date(error.time).toLocaleString('es-ES')}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Footer Info */}
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <div className="flex items-start gap-3">
            <svg className="w-5 h-5 text-blue-600 mt-0.5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
            </svg>
            <div className="flex-1">
              <p className="text-sm text-gray-700">
                <strong className="text-blue-900">Dashboard Local + Logfire:</strong> 
                Este dashboard muestra métricas capturadas localmente. Para análisis más detallados, 
                traces completos y queries avanzados, usa{" "}
                <a href="https://logfire-eu.pydantic.dev/mariasebarespersona/rama-ai/live" target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:text-blue-800 underline">
                  Logfire
                </a>.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
