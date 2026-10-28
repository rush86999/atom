/**
 * Core workspace home.
 *
 * This release is a general company-data + trained-agent workspace: bring
 * data, teach an agent, ask for a result, review/correct it, reuse the work.
 * The dashboard therefore shows the user's own records and runs, not
 * platform-owned business metrics (cash, pipeline, invoices). Deferred
 * surfaces remain in the codebase but are not advertised here.
 */

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/router";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { GettingStartedCard } from "@/components/Onboarding/GettingStartedCard";
import { listGoalRuns, listGoals, GoalRun } from "@/lib/goal-run-api";
import {
  Activity,
  ArrowRight,
  Bot,
  FileText,
  Layout,
  MessageSquare,
  RefreshCw,
  Settings,
  Upload,
} from "lucide-react";

type RecentDocument = {
  id: string;
  title?: string;
  filename?: string;
  text_preview?: string;
  created_at?: string;
};

type RecentCanvas = {
  canvas_id: string;
  display_title?: string | null;
  title?: string | null;
  canvas_type?: string;
  last_updated?: string | null;
};

const asList = (payload: any): any[] => {
  if (Array.isArray(payload)) return payload;
  if (Array.isArray(payload?.data)) return payload.data;
  if (Array.isArray(payload?.canvases)) return payload.canvases;
  if (Array.isArray(payload?.items)) return payload.items;
  if (Array.isArray(payload?.agents)) return payload.agents;
  return [];
};

const fmtDate = (value?: string | null) => {
  if (!value) return "";
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? "" : d.toLocaleDateString();
};

const DashboardPage: React.FC = () => {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [documents, setDocuments] = useState<RecentDocument[]>([]);
  const [canvases, setCanvases] = useState<RecentCanvas[]>([]);
  const [agents, setAgents] = useState<any[]>([]);
  const [runs, setRuns] = useState<GoalRun[]>([]);
  const [goalTitles, setGoalTitles] = useState<Record<string, string>>({});

  const refresh = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    const token =
      typeof window !== "undefined"
        ? localStorage.getItem("auth_token") || localStorage.getItem("token")
        : null;
    const headers: Record<string, string> = token
      ? { Authorization: `Bearer ${token}` }
      : {};
    const get = (url: string) =>
      fetch(url, { headers }).catch((): null => null);

    try {
      const [docsRes, canvasesRes, agentsRes, runsResult, goalsResult] = await Promise.all([
        get("/api/documents"),
        get("/api/canvas/"),
        get("/api/agents/"),
        listGoalRuns({ includeTerminal: true }).catch((): GoalRun[] => []),
        listGoals({ includeTerminal: true }).catch((): any[] => []),
      ]);

      if (docsRes && docsRes.ok) {
        const payload = await docsRes.json().catch((): null => null);
        setDocuments(asList(payload));
      }
      if (canvasesRes && canvasesRes.ok) {
        const payload = await canvasesRes.json().catch((): null => null);
        setCanvases(asList(payload));
      }
      if (agentsRes && agentsRes.ok) {
        const payload = await agentsRes.json().catch((): null => null);
        setAgents(asList(payload));
      }
      setRuns(Array.isArray(runsResult) ? runsResult : []);
      setGoalTitles(
        Object.fromEntries(
          (Array.isArray(goalsResult) ? goalsResult : []).map((g: any) => [g.id, g.title])
        )
      );

      if (!docsRes?.ok && !canvasesRes?.ok && !agentsRes?.ok) {
        throw new Error("The workspace data endpoints did not respond.");
      }
    } catch (error) {
      setLoadError(
        error instanceof Error ? error.message : "Could not load the workspace."
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const activeRuns = runs.filter(
    (r) => !["achieved", "failed", "cancelled"].includes(r.status)
  );
  const failedRuns = runs.filter((r) => r.status === "failed");
  const recentRuns = runs.slice(0, 5);
  const recentDocuments = documents.slice(0, 5);
  const recentCanvases = canvases.slice(0, 5);

  const stats = [
    {
      label: "Records",
      value: documents.length,
      detail: "documents available to read",
      href: "/documents",
      icon: FileText,
    },
    {
      label: "Workspace",
      value: canvases.length,
      detail: "drafts and deliverables",
      href: "/canvas",
      icon: Layout,
    },
    {
      label: "Agents",
      value: agents.length,
      detail: "agents you can teach",
      href: "/agents",
      icon: Bot,
    },
    {
      label: "Unfinished work",
      value: activeRuns.length + failedRuns.length,
      detail:
        failedRuns.length > 0
          ? `${failedRuns.length} failed · ${activeRuns.length} in progress`
          : `${activeRuns.length} in progress`,
      href: "/goal-runs",
      icon: Activity,
    },
  ];

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 p-6">
      <div className="max-w-[1400px] mx-auto space-y-8">
        <GettingStartedCard />

        <div className="flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
          <div className="space-y-2">
            <h1
              data-testid="dashboard-welcome-message"
              className="text-4xl font-bold tracking-tight text-gray-900 dark:text-gray-100"
            >
              Your workspace
            </h1>
            <p className="text-xl text-gray-600 dark:text-gray-400">
              Bring records, teach an agent, review the result, reuse the work.
            </p>
          </div>
          <Button variant="outline" onClick={refresh} disabled={loading} className="gap-2">
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </Button>
        </div>

        {loadError && (
          <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800 dark:border-red-900 dark:bg-red-950 dark:text-red-200">
            Could not load the workspace: {loadError}{" "}
            <button className="underline" onClick={refresh}>
              retry
            </button>
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {stats.map((stat) => (
            <Link key={stat.label} href={stat.href}>
              <Card className="h-full hover:border-primary transition-colors cursor-pointer">
                <CardContent className="pt-6">
                  <div className="flex items-center justify-between text-sm font-medium text-gray-500 dark:text-gray-400">
                    <span>{stat.label}</span>
                    <stat.icon className="w-4 h-4 text-blue-600" />
                  </div>
                  <div className="mt-2 text-3xl font-bold text-gray-900 dark:text-gray-100">
                    {loading ? "—" : stat.value}
                  </div>
                  <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                    {stat.detail}
                  </p>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>

        <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
          <div className="space-y-1">
            <h2 className="text-2xl font-semibold tracking-tight">Start here</h2>
            <p className="text-gray-600 dark:text-gray-400">
              The core workspace jobs
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <Button onClick={() => router.push("/documents")} className="gap-2">
              <Upload className="w-4 h-4" /> Add data
            </Button>
            <Button variant="outline" onClick={() => router.push("/chat")} className="gap-2">
              <MessageSquare className="w-4 h-4" /> Ask an agent
            </Button>
            <Button variant="outline" onClick={() => router.push("/agents")} className="gap-2">
              <Bot className="w-4 h-4" /> Teach an agent
            </Button>
            <Button variant="outline" onClick={() => router.push("/settings")} className="gap-2">
              <Settings className="w-4 h-4" /> Settings
            </Button>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle>Recent records</CardTitle>
                <CardDescription>Data available to read and cite</CardDescription>
              </div>
              <Link href="/documents" className="text-sm text-blue-600 hover:underline">
                View all
              </Link>
            </CardHeader>
            <CardContent className="space-y-3">
              {recentDocuments.map((doc) => (
                <button
                  key={doc.id}
                  className="w-full text-left rounded-md border border-border p-3 hover:bg-muted"
                  onClick={() => router.push(`/documents/${doc.id}`)}
                >
                  <p className="text-sm font-medium truncate">
                    {doc.title || doc.filename || "Untitled record"}
                  </p>
                  <p className="text-xs text-muted-foreground line-clamp-1">
                    {doc.text_preview || "No preview recorded."}
                  </p>
                  <p className="mt-1 text-[11px] text-muted-foreground">
                    {fmtDate(doc.created_at)}
                  </p>
                </button>
              ))}
              {!loading && recentDocuments.length === 0 && (
                <p className="text-sm text-muted-foreground">
                  No records yet. Upload a text, CSV or XLSX file to begin.
                </p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle>Recent results</CardTitle>
                <CardDescription>Canvases you can review and edit</CardDescription>
              </div>
              <Link href="/canvas" className="text-sm text-blue-600 hover:underline">
                View all
              </Link>
            </CardHeader>
            <CardContent className="space-y-3">
              {recentCanvases.map((canvas) => (
                <button
                  key={canvas.canvas_id}
                  className="w-full text-left rounded-md border border-border p-3 hover:bg-muted"
                  onClick={() => router.push(`/canvas/${canvas.canvas_id}`)}
                >
                  <p className="text-sm font-medium truncate">
                    {canvas.display_title || canvas.title || canvas.canvas_id}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {canvas.canvas_type || "canvas"} · {fmtDate(canvas.last_updated)}
                  </p>
                </button>
              ))}
              {!loading && recentCanvases.length === 0 && (
                <p className="text-sm text-muted-foreground">
                  No results yet. Ask an agent to produce a canvas.
                </p>
              )}
            </CardContent>
          </Card>
        </div>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle>Recent activity</CardTitle>
              <CardDescription>
                Results, failures and work waiting for a decision
              </CardDescription>
            </div>
            <Link href="/goal-runs" className="text-sm text-blue-600 hover:underline">
              Open Activity
            </Link>
          </CardHeader>
          <CardContent className="space-y-3">
            {recentRuns.map((run) => (
              <button
                key={run.id}
                className="w-full flex items-center justify-between rounded-md border border-border p-3 text-left hover:bg-muted"
                onClick={() => router.push(`/goal-runs/${run.id}`)}
              >
                <div className="min-w-0">
                  <p className="text-sm font-medium truncate">
                    {goalTitles[run.goal_id] || run.goal_id}
                  </p>
                  <p className="text-xs text-muted-foreground">{fmtDate(run.created_at)}</p>
                </div>
                <Badge variant={run.status === "failed" ? "destructive" : "secondary"}>
                  {run.status.replace(/_/g, " ")}
                </Badge>
              </button>
            ))}
            {!loading && recentRuns.length === 0 && (
              <p className="text-sm text-muted-foreground">
                No runs recorded yet. Ask an agent to do a piece of work and it
                will appear here with its final state.
              </p>
            )}
            <div className="pt-2">
              <Link
                href="/execution-history"
                className="inline-flex items-center gap-1 text-sm text-blue-600 hover:underline"
              >
                Execution history <ArrowRight className="w-3 h-3" />
              </Link>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default DashboardPage;
