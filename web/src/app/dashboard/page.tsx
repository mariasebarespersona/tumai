"use client";

import { useEffect, useState } from "react";
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:7901";

const COLORS = {
  primary: "#3b82f6",
  success: "#22c55e",
  warning: "#f59e0b",
  error: "#ef4444",
  purple: "#8b5cf6",
};

const STATUS_COLORS: Record<string, string> = {
  "200": COLORS.success,
  "201": COLORS.success,
  "422": COLORS.warning,
  "500": COLORS.error,
  "503": COLORS.error,
};

interface DashboardData {
  api: {
    request_rate: Array<{ time: string; requests: number }>;
    status_codes: Array<{ status: string; count: number }>;
    error_rate: Array<{ time: string; error_rate: number }>;
    top_endpoints: Array<{
      endpoint: string;
      requests: number;
      avg_latency_ms: number;
      max_latency_ms: number;
    }>;
  };
  llm: {
    calls_over_time: Array<{ time: string; llm_calls: number }>;
    cost: {
      by_model: Array<{
        model: string;
        calls: number;
        prompt_tokens: number;
        completion_tokens: number;
        cost_usd: number;
      }>;
      total_calls: number;
      total_cost_usd: number;
      total_tokens: number;
    };
  };
  agents: {
    performance: Array<{
      agent: string;
      total_calls: number;
      avg_latency_ms: number;
      completed: number;
      errors: number;
      success_rate: number;
    }>;
  };
}

export default function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [timeRange, setTimeRange] = useState("1h");
  const [autoRefresh, setAutoRefresh] = useState(true);

  const fetchData = async () => {
    try {
      const response = await fetch(
        `${API_BASE}/api/dashboard/metrics?time_range=${timeRange}`
      );
      const json = await response.json();

      if (json.ok) {
        setData(json.data);
        setError(null);
      } else {
        setError(json.error || "Error fetching data");
      }
    } catch (err: any) {
      setError(err.message || "Network error");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();

    if (autoRefresh) {
      const interval = setInterval(fetchData, 30000); // Refresh every 30s
      return () => clearInterval(interval);
    }
  }, [timeRange, autoRefresh]);

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Cargando métricas...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="bg-red-50 border border-red-200 rounded-lg p-6 max-w-md">
          <h3 className="text-red-800 font-semibold mb-2">Error</h3>
          <p className="text-red-600">{error}</p>
          <button
            onClick={() => {
              setLoading(true);
              fetchData();
            }}
            className="mt-4 px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700"
          >
            Reintentar
          </button>
        </div>
      </div>
    );
  }

  if (!data) {
    return null;
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-[1600px] mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">
                📊 RAMA AI Dashboard
              </h1>
              <p className="text-sm text-gray-600 mt-1">
                Observability en tiempo real
              </p>
            </div>

            <div className="flex items-center gap-4">
              {/* Time Range Selector */}
              <select
                value={timeRange}
                onChange={(e) => setTimeRange(e.target.value)}
                className="px-3 py-2 border border-gray-300 rounded-lg text-sm"
              >
                <option value="15m">Últimos 15 min</option>
                <option value="1h">Última 1 hora</option>
                <option value="6h">Últimas 6 horas</option>
                <option value="24h">Últimas 24 horas</option>
              </select>

              {/* Auto Refresh Toggle */}
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={autoRefresh}
                  onChange={(e) => setAutoRefresh(e.target.checked)}
                  className="rounded"
                />
                Auto-refresh (30s)
              </label>

              {/* Manual Refresh */}
              <button
                onClick={fetchData}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm"
              >
                🔄 Refrescar
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-[1600px] mx-auto px-6 py-6 space-y-6">
        {/* Summary Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <SummaryCard
            title="Total Requests"
            value={data.api.request_rate
              .reduce((sum, d) => sum + d.requests, 0)
              .toLocaleString()}
            icon="🌐"
            color="blue"
          />
          <SummaryCard
            title="LLM Calls"
            value={data.llm.cost.total_calls.toLocaleString()}
            icon="🤖"
            color="purple"
          />
          <SummaryCard
            title="LLM Cost"
            value={`$${data.llm.cost.total_cost_usd.toFixed(4)}`}
            icon="💰"
            color="green"
          />
          <SummaryCard
            title="Total Tokens"
            value={data.llm.cost.total_tokens.toLocaleString()}
            icon="🎯"
            color="orange"
          />
        </div>

        {/* API Request Rate */}
        <div className="bg-white rounded-lg shadow-sm p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">
            📈 API Request Rate
          </h2>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={data.api.request_rate.slice().reverse()}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis
                dataKey="time"
                tickFormatter={(value) =>
                  new Date(value).toLocaleTimeString("es", {
                    hour: "2-digit",
                    minute: "2-digit",
                  })
                }
              />
              <YAxis />
              <Tooltip />
              <Legend />
              <Line
                type="monotone"
                dataKey="requests"
                stroke={COLORS.primary}
                strokeWidth={2}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Status Codes & Error Rate */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Status Codes */}
          <div className="bg-white rounded-lg shadow-sm p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">
              🥧 Status Codes
            </h2>
            <ResponsiveContainer width="100%" height={250}>
              <PieChart>
                <Pie
                  data={data.api.status_codes}
                  dataKey="count"
                  nameKey="status"
                  cx="50%"
                  cy="50%"
                  outerRadius={80}
                  label
                >
                  {data.api.status_codes.map((entry, index) => (
                    <Cell
                      key={`cell-${index}`}
                      fill={STATUS_COLORS[entry.status] || COLORS.primary}
                    />
                  ))}
                </Pie>
                <Tooltip />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </div>

          {/* Error Rate */}
          <div className="bg-white rounded-lg shadow-sm p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">
              ⚠️ Error Rate
            </h2>
            <ResponsiveContainer width="100%" height={250}>
              <LineChart data={data.api.error_rate.slice().reverse()}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis
                  dataKey="time"
                  tickFormatter={(value) =>
                    new Date(value).toLocaleTimeString("es", {
                      hour: "2-digit",
                      minute: "2-digit",
                    })
                  }
                />
                <YAxis />
                <Tooltip formatter={(value: any) => `${value.toFixed(2)}%`} />
                <Line
                  type="monotone"
                  dataKey="error_rate"
                  stroke={COLORS.error}
                  strokeWidth={2}
                  dot={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Top Endpoints */}
        <div className="bg-white rounded-lg shadow-sm p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">
            🔝 Top Endpoints
          </h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="text-left py-3 px-4">Endpoint</th>
                  <th className="text-right py-3 px-4">Requests</th>
                  <th className="text-right py-3 px-4">Avg Latency</th>
                  <th className="text-right py-3 px-4">Max Latency</th>
                </tr>
              </thead>
              <tbody>
                {data.api.top_endpoints.map((endpoint, idx) => (
                  <tr key={idx} className="border-b border-gray-100">
                    <td className="py-3 px-4 font-mono text-xs">
                      {endpoint.endpoint}
                    </td>
                    <td className="text-right py-3 px-4">
                      {endpoint.requests.toLocaleString()}
                    </td>
                    <td className="text-right py-3 px-4">
                      {endpoint.avg_latency_ms.toFixed(0)} ms
                    </td>
                    <td className="text-right py-3 px-4">
                      {endpoint.max_latency_ms.toFixed(0)} ms
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* LLM Calls & Cost */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* LLM Calls */}
          <div className="bg-white rounded-lg shadow-sm p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">
              🤖 LLM Calls
            </h2>
            <ResponsiveContainer width="100%" height={250}>
              <LineChart data={data.llm.calls_over_time.slice().reverse()}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis
                  dataKey="time"
                  tickFormatter={(value) =>
                    new Date(value).toLocaleTimeString("es", {
                      hour: "2-digit",
                      minute: "2-digit",
                    })
                  }
                />
                <YAxis />
                <Tooltip />
                <Line
                  type="monotone"
                  dataKey="llm_calls"
                  stroke={COLORS.purple}
                  strokeWidth={2}
                  dot={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>

          {/* LLM Cost by Model */}
          <div className="bg-white rounded-lg shadow-sm p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">
              💰 LLM Cost by Model
            </h2>
            <div className="space-y-3">
              {data.llm.cost.by_model.map((model, idx) => (
                <div
                  key={idx}
                  className="flex items-center justify-between p-3 bg-gray-50 rounded-lg"
                >
                  <div>
                    <div className="font-semibold text-gray-900">
                      {model.model}
                    </div>
                    <div className="text-xs text-gray-600">
                      {model.calls} calls •{" "}
                      {(
                        model.prompt_tokens + model.completion_tokens
                      ).toLocaleString()}{" "}
                      tokens
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-lg font-bold text-green-600">
                      ${model.cost_usd.toFixed(4)}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Agent Performance */}
        <div className="bg-white rounded-lg shadow-sm p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">
            🎯 Agent Performance
          </h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="text-left py-3 px-4">Agent</th>
                  <th className="text-right py-3 px-4">Calls</th>
                  <th className="text-right py-3 px-4">Avg Latency</th>
                  <th className="text-right py-3 px-4">Completed</th>
                  <th className="text-right py-3 px-4">Errors</th>
                  <th className="text-right py-3 px-4">Success Rate</th>
                </tr>
              </thead>
              <tbody>
                {data.agents.performance.map((agent, idx) => (
                  <tr key={idx} className="border-b border-gray-100">
                    <td className="py-3 px-4 font-semibold">{agent.agent}</td>
                    <td className="text-right py-3 px-4">
                      {agent.total_calls}
                    </td>
                    <td className="text-right py-3 px-4">
                      {agent.avg_latency_ms.toFixed(0)} ms
                    </td>
                    <td className="text-right py-3 px-4 text-green-600">
                      {agent.completed}
                    </td>
                    <td className="text-right py-3 px-4 text-red-600">
                      {agent.errors}
                    </td>
                    <td className="text-right py-3 px-4">
                      <span
                        className={`px-2 py-1 rounded text-xs font-semibold ${
                          agent.success_rate >= 95
                            ? "bg-green-100 text-green-800"
                            : agent.success_rate >= 80
                            ? "bg-yellow-100 text-yellow-800"
                            : "bg-red-100 text-red-800"
                        }`}
                      >
                        {agent.success_rate?.toFixed(1)}%
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}

function SummaryCard({
  title,
  value,
  icon,
  color,
}: {
  title: string;
  value: string;
  icon: string;
  color: "blue" | "purple" | "green" | "orange";
}) {
  const colorClasses = {
    blue: "bg-blue-50 border-blue-200 text-blue-900",
    purple: "bg-purple-50 border-purple-200 text-purple-900",
    green: "bg-green-50 border-green-200 text-green-900",
    orange: "bg-orange-50 border-orange-200 text-orange-900",
  };

  return (
    <div
      className={`${colorClasses[color]} border rounded-lg p-4 flex items-center gap-4`}
    >
      <div className="text-4xl">{icon}</div>
      <div>
        <div className="text-sm opacity-75">{title}</div>
        <div className="text-2xl font-bold">{value}</div>
      </div>
    </div>
  );
}

