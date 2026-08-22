/**
 * Analytics Panel (MenuBar / Desktop)
 *
 * Round 80v — desktop parity: dashboard KPIs from the live backend,
 * mirroring the mobile AnalyticsDashboardScreen via
 * GET /api/analytics/dashboard/kpis?time_window=…
 */

import React, { useCallback, useEffect, useState } from "react";

interface DashboardKPIs {
  total_executions: number;
  successful_executions: number;
  failed_executions: number;
  success_rate: number;
  average_duration_ms?: number;
  average_duration_seconds?: number;
  unique_workflows?: number;
  unique_users?: number;
  error_rate?: number;
}

type TimeWindow = "1h" | "24h" | "7d" | "30d";

const WINDOWS: TimeWindow[] = ["1h", "24h", "7d", "30d"];

interface AnalyticsPanelProps {
  serverUrl?: string;
  /** JWT for auth-gated calls. */
  token?: string | null;
}

export default function AnalyticsPanel({
  serverUrl,
  token,
}: AnalyticsPanelProps) {
  const [kpis, setKpis] = useState<DashboardKPIs | null>(null);
  const [window_, setWindow] = useState<TimeWindow>("24h");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const base = (serverUrl || "http://localhost:8000").replace(/\/$/, "");

  const load = useCallback(
    async (tw: TimeWindow) => {
      setLoading(true);
      setError(null);
      try {
        const headers: Record<string, string> = {};
        if (token) headers.Authorization = `Bearer ${token}`;
        const res = await fetch(
          `${base}/api/analytics/dashboard/kpis?time_window=${tw}`,
          { headers }
        );
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        setKpis(await res.json());
      } catch (e: any) {
        setError(e?.message || "Failed to load analytics");
      } finally {
        setLoading(false);
      }
    },
    [base, token]
  );

  useEffect(() => {
    load(window_);
  }, [load, window_]);

  const successPct =
    kpis?.success_rate != null
      ? kpis.success_rate <= 1
        ? Math.round(kpis.success_rate * 100)
        : Math.round(kpis.success_rate)
      : null;

  return (
    <div className="analytics-panel" data-testid="analytics-panel">
      <div className="analytics-summary-header">
        <span className="analytics-title">Analytics</span>
        <span className="analytics-windows" role="tablist">
          {WINDOWS.map((w) => (
            <button
              key={w}
              className={`analytics-window ${w === window_ ? "active" : ""}`}
              onClick={() => setWindow(w)}
              data-testid={`analytics-window-${w}`}
            >
              {w}
            </button>
          ))}
        </span>
      </div>

      {error && (
        <div className="analytics-error" role="alert">
          {error}
        </div>
      )}

      {loading && (
        <div className="analytics-loading" data-testid="analytics-loading">
          Loading…
        </div>
      )}

      {!loading && kpis && (
        <div className="kpi-grid" data-testid="kpi-grid">
          <div className="kpi" data-testid="kpi-total-executions">
            <div className="kpi-value">{kpis.total_executions}</div>
            <div className="kpi-label">Executions</div>
          </div>
          <div className="kpi" data-testid="kpi-success-rate">
            <div className="kpi-value">{successPct ?? "—"}%</div>
            <div className="kpi-label">Success rate</div>
          </div>
          <div className="kpi" data-testid="kpi-failed">
            <div className="kpi-value">{kpis.failed_executions}</div>
            <div className="kpi-label">Failures</div>
          </div>
          {kpis.average_duration_seconds != null && (
            <div className="kpi" data-testid="kpi-duration">
              <div className="kpi-value">
                {Math.round(kpis.average_duration_seconds)}s
              </div>
              <div className="kpi-label">Avg duration</div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
