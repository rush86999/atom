/**
 * P3.3 — Scheduled workflow UI.
 *
 * Frontend-only surface over the EXISTING backend scheduler endpoints in
 * core/workflow_endpoints.py:
 *   POST   /workflows/{workflow_id}/schedule   body: schedule_config
 *   GET    /scheduler/jobs
 *   DELETE /workflows/{workflow_id}/schedule/{job_id}
 *
 * schedule_config shape (per backend docstring):
 *   { trigger_type: 'cron'|'interval'|'date',
 *     trigger_config: { ... },
 *     input_data?: {...} }
 *
 * Interval trigger_config: { minutes: N } (also accepts seconds/hours/days).
 * Cron trigger_config: { cron_expr: "* * * * *" } OR APScheduler-style fields.
 */
import React, { useEffect, useState } from "react";
import Head from "next/head";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/components/ui/use-toast";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type TriggerType = "interval" | "cron";

interface ScheduledJob {
  id: string;
  workflow_id?: string;
  name?: string;
  next_run_time?: string | null;
  trigger?: string;
}

const SchedulePage: React.FC = () => {
  const { toast } = useToast();
  const [workflowId, setWorkflowId] = useState("");
  const [triggerType, setTriggerType] = useState<TriggerType>("interval");
  const [intervalMinutes, setIntervalMinutes] = useState("30");
  const [cronExpr, setCronExpr] = useState("*/5 * * * *");
  const [jobs, setJobs] = useState<ScheduledJob[]>([]);
  const [submitting, setSubmitting] = useState(false);

  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
  const authHeaders = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };

  const loadJobs = async () => {
    try {
      const res = await fetch(`${API_BASE}/scheduler/jobs`, { headers: authHeaders });
      if (!res.ok) return;
      const data = await res.json();
      // Endpoint returns a list or {jobs: [...]}; handle both.
      const list = Array.isArray(data) ? data : (data?.jobs ?? []);
      setJobs(list);
    } catch {
      // Silent — list just stays empty.
    }
  };

  useEffect(() => {
    loadJobs();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!workflowId.trim()) {
      toast({ title: "Workflow ID required", variant: "error" });
      return;
    }

    const trigger_config =
      triggerType === "interval"
        ? { minutes: Math.max(1, parseInt(intervalMinutes || "30", 10) || 30) }
        : { cron_expr: cronExpr.trim() };

    setSubmitting(true);
    try {
      const res = await fetch(
        `${API_BASE}/workflows/${encodeURIComponent(workflowId)}/schedule`,
        {
          method: "POST",
          headers: authHeaders,
          body: JSON.stringify({
            trigger_type: triggerType,
            trigger_config,
          }),
        }
      );
      if (!res.ok) {
        const detail = await res.json().catch(() => ({}));
        throw new Error(detail?.detail || `HTTP ${res.status}`);
      }
      const data = await res.json();
      toast({
        title: "Workflow scheduled",
        description: data?.message || `Job ${data?.job_id ?? "created"}`,
        variant: "success",
      });
      await loadJobs();
    } catch (err: any) {
      toast({
        title: "Scheduling failed",
        description: err?.message || "Please try again.",
        variant: "error",
      });
    } finally {
      setSubmitting(false);
    }
  };

  const handleRemove = async (jobId: string, wfid?: string) => {
    if (!wfid) {
      toast({ title: "Cannot remove", description: "Workflow ID missing on this job.", variant: "error" });
      return;
    }
    try {
      const res = await fetch(
        `${API_BASE}/workflows/${encodeURIComponent(wfid)}/schedule/${encodeURIComponent(jobId)}`,
        { method: "DELETE", headers: authHeaders }
      );
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }
      toast({ title: "Removed", description: "Scheduled job deleted.", variant: "success" });
      await loadJobs();
    } catch (err: any) {
      toast({ title: "Failed", description: err?.message || "Could not delete.", variant: "error" });
    }
  };

  return (
    <>
      <Head><title>Schedule Workflow | Atom</title></Head>
      <div className="container mx-auto max-w-3xl py-8 space-y-8">
        <div>
          <h1 className="text-2xl font-bold">Schedule a workflow</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Run a workflow on a recurring schedule. The scheduler runs server-side, so jobs fire even when this tab is closed.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4 rounded-lg border p-4">
          <div className="space-y-2">
            <Label htmlFor="workflow-id">Workflow ID</Label>
            <Input
              id="workflow-id"
              placeholder="e.g. wf_welcome_email"
              value={workflowId}
              onChange={(e) => setWorkflowId(e.target.value)}
              required
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="trigger-type">Trigger</Label>
            <Select value={triggerType} onValueChange={(v) => setTriggerType(v as TriggerType)}>
              <SelectTrigger id="trigger-type">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="interval">Every N minutes (interval)</SelectItem>
                <SelectItem value="cron">Cron expression</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {triggerType === "interval" ? (
            <div className="space-y-2">
              <Label htmlFor="interval-min">Interval (minutes)</Label>
              <Input
                id="interval-min"
                type="number"
                min={1}
                value={intervalMinutes}
                onChange={(e) => setIntervalMinutes(e.target.value)}
              />
            </div>
          ) : (
            <div className="space-y-2">
              <Label htmlFor="cron-expr">Cron expression</Label>
              <Input
                id="cron-expr"
                placeholder="*/5 * * * *"
                value={cronExpr}
                onChange={(e) => setCronExpr(e.target.value)}
              />
              <p className="text-xs text-muted-foreground">
                Standard 5-field cron: minute hour day-of-month month day-of-week.
              </p>
            </div>
          )}

          <div className="flex justify-end">
            <Button type="submit" disabled={submitting}>
              {submitting ? "Scheduling…" : "Schedule workflow"}
            </Button>
          </div>
        </form>

        <div>
          <div className="flex items-center justify-between mb-2">
            <h2 className="text-lg font-semibold">My scheduled workflows</h2>
            <Button variant="ghost" size="sm" onClick={loadJobs}>Refresh</Button>
          </div>
          {jobs.length === 0 ? (
            <p className="text-sm text-muted-foreground">No scheduled jobs yet. Schedule one above.</p>
          ) : (
            <ul className="divide-y rounded-lg border">
              {jobs.map((job) => (
                <li key={job.id} className="flex items-center justify-between p-3 text-sm">
                  <div className="min-w-0">
                    <p className="font-medium truncate">
                      {job.name || job.id}
                      {job.workflow_id && <span className="text-muted-foreground"> — {job.workflow_id}</span>}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {job.trigger ? `Trigger: ${job.trigger}` : null}
                      {job.next_run_time ? ` • Next: ${new Date(job.next_run_time).toLocaleString()}` : ""}
                    </p>
                  </div>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => handleRemove(job.id, job.workflow_id)}
                  >
                    Remove
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </>
  );
};

export default SchedulePage;
