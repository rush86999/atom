'use client';

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { useToast } from '@/components/ui/use-toast';
import { authFetch } from '@/lib/auth-headers';
import { fetchRecentJobs, runIngestJob, type IngestJob } from '@/lib/ingest-jobs';
import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  Database,
  FileSpreadsheet,
  Loader2,
  PlugZap,
  RefreshCw,
  RotateCcw,
} from 'lucide-react';

interface ConnectionStatus {
  is_connected: boolean;
  email?: string | null;
  reason?: string | null;
  scope?: string | null;
  token_provider?: string | null;
}

interface DocumentItem {
  id: string;
  title?: string;
  file_type?: string;
  source?: string;
  created_at?: string;
}

function nestedResult(job: IngestJob): any {
  return job.result?.result ?? job.result ?? {};
}

function jobFileName(job: IngestJob): string {
  const result = nestedResult(job);
  return result.file_name || job.result?.file_name || job.file_id || job.kind || 'ingestion';
}

function jobPreview(job: IngestJob): string {
  const result = nestedResult(job);
  return result.text_preview || job.result?.text_preview || '';
}

function jobChars(job: IngestJob): number | null {
  const result = nestedResult(job);
  const value = result.chars_ingested ?? job.result?.chars_ingested;
  return typeof value === 'number' ? value : null;
}

function sheetLines(job: IngestJob): string[] {
  return jobPreview(job)
    .split('\n')
    .map(line => line.trim())
    .filter(line => line.startsWith('- '));
}

function jobUnchanged(job: IngestJob): boolean {
  return Boolean(job.result?.unchanged ?? nestedResult(job).unchanged);
}

function elapsedLabel(startedAt?: string | null, finishedAt?: string | null): string {
  if (!startedAt) return '';
  const start = new Date(startedAt).getTime();
  const end = finishedAt ? new Date(finishedAt).getTime() : Date.now();
  const seconds = Math.max(0, Math.round((end - start) / 1000));
  if (seconds < 60) return `${seconds}s`;
  return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
}

export default function ConnectedDataStatus() {
  const { toast } = useToast();
  const [connection, setConnection] = useState<ConnectionStatus | null>(null);
  const [jobs, setJobs] = useState<IngestJob[]>([]);
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [retrying, setRetrying] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [connectionResponse, recentJobs, documentsResponse] = await Promise.all([
        authFetch('/api/onedrive/connection-status'),
        fetchRecentJobs(authFetch, '/api/onedrive'),
        authFetch('/api/documents'),
      ]);
      if (!connectionResponse.ok) {
        throw new Error(`Connection status failed (${connectionResponse.status})`);
      }
      const connectionData = await connectionResponse.json();
      setConnection(connectionData);
      setJobs(recentJobs);
      if (documentsResponse.ok) {
        const documentData = await documentsResponse.json();
        const items = documentData?.data ?? documentData;
        setDocuments(Array.isArray(items) ? items : []);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Data status unavailable');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const timer = setInterval(load, 10000);
    return () => clearInterval(timer);
  }, [load]);

  const lastSuccess = useMemo(() => {
    return [...jobs]
      .filter(job => job.status === 'completed')
      .sort((a, b) => (b.finished_at || '').localeCompare(a.finished_at || ''))[0];
  }, [jobs]);

  const failedJobs = useMemo(() => jobs.filter(job => job.status === 'failed'), [jobs]);
  const runningJobs = useMemo(() => jobs.filter(job => job.status === 'running'), [jobs]);

  const retryJob = useCallback(async (job: IngestJob) => {
    if (!job.file_id) {
      toast({
        title: 'Cannot retry this job',
        description: 'Only single-file ingestion jobs expose a file id.',
        variant: 'destructive',
      });
      return;
    }
    setRetrying(job.job_id);
    try {
      const result = await runIngestJob(
        authFetch,
        '/api/onedrive/ingest-document',
        '/api/onedrive',
        {
          file_id: job.file_id,
          metadata: { name: jobFileName(job) },
        },
        'file ingest',
      );
      if (result?.success === false) {
        throw new Error(result.error || 'Ingestion failed');
      }
      toast({
        title: result?.unchanged ? 'Already current' : 'Ingestion completed',
        description: result?.unchanged
          ? 'The source bytes were unchanged; nothing was re-ingested.'
          : 'The file was re-ingested through the background job.',
      });
      await load();
    } catch (err) {
      toast({
        title: 'Retry failed',
        description: err instanceof Error ? err.message : 'Ingestion failed',
        variant: 'destructive',
      });
    } finally {
      setRetrying(null);
    }
  }, [load, toast]);

  return (
    <div className="space-y-4" data-testid="connected-data-status">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-lg font-medium flex items-center gap-2">
            <Database className="h-5 w-5" />
            Connected data
          </h3>
          <p className="text-sm text-muted-foreground">
            Real OneDrive connection, ingestion jobs and materialized coverage. No upload rows are used here.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={load} disabled={loading}>
          <RefreshCw className={`mr-2 h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          Refresh status
        </Button>
      </div>

      {error && (
        <Card className="border-destructive/40" data-testid="data-status-error">
          <CardContent className="flex items-start gap-3 pt-6">
            <AlertTriangle className="h-5 w-5 text-destructive shrink-0" />
            <div>
              <p className="font-medium">Status could not be verified</p>
              <p className="text-sm text-muted-foreground">{error}</p>
            </div>
          </CardContent>
        </Card>
      )}

      <div className="grid gap-4 md:grid-cols-3">
        <Card data-testid="connection-card">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <PlugZap className="h-4 w-4" />
              Connection
            </CardTitle>
            <CardDescription>Microsoft Graph / OneDrive</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            {loading && !connection ? (
              <span className="flex items-center gap-2 text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" /> Checking…
              </span>
            ) : connection?.is_connected ? (
              <>
                <Badge className="bg-emerald-600" data-testid="connection-state">Connected</Badge>
                <p>{connection.email || 'Authenticated account'}</p>
                <p className="text-muted-foreground break-all">
                  Scope: {connection.scope || 'granted scope not reported'}
                </p>
                {connection.token_provider && (
                  <p className="text-xs text-muted-foreground">
                    Token family: {connection.token_provider}
                  </p>
                )}
              </>
            ) : (
              <>
                <Badge variant="destructive" data-testid="connection-state">Disconnected / stale</Badge>
                <p className="text-muted-foreground">
                  {connection?.reason || 'No active OneDrive grant was found.'}
                </p>
                <p className="text-xs text-muted-foreground">
                  Cached canvas snapshots remain local, but connected operations refuse until the grant is restored.
                </p>
              </>
            )}
          </CardContent>
        </Card>

        <Card data-testid="last-success-card">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4" />
              Last successful sync
            </CardTitle>
            <CardDescription>Durable ingestion receipt</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            {lastSuccess ? (
              <>
                <p className="font-medium break-all" data-testid="last-success-file">
                  {jobFileName(lastSuccess)}
                </p>
                <p className="text-muted-foreground">
                  {lastSuccess.finished_at
                    ? new Date(lastSuccess.finished_at).toLocaleString()
                    : 'completed'}
                  {jobUnchanged(lastSuccess) ? ' · unchanged repeat' : ''}
                </p>
                <p className="text-xs text-muted-foreground">
                  {jobChars(lastSuccess)?.toLocaleString() || '—'} characters
                  {sheetLines(lastSuccess).length
                    ? ` · ${sheetLines(lastSuccess).length} sheet entries`
                    : ''}
                </p>
              </>
            ) : (
              <p className="text-muted-foreground">No completed ingestion job in this server process.</p>
            )}
          </CardContent>
        </Card>

        <Card data-testid="coverage-card">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <FileSpreadsheet className="h-4 w-4" />
              Ingested coverage
            </CardTitle>
            <CardDescription>Documents and materialized sheets</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <p><span className="font-medium">{documents.length}</span> indexed document(s)</p>
            <p className="text-muted-foreground">
              {documents.slice(0, 3).map(doc => doc.title || doc.id).join(', ') || 'None yet'}
            </p>
            <p className="text-xs text-muted-foreground">
              Unsupported files are reported by the job result, never counted as ingested.
            </p>
          </CardContent>
        </Card>
      </div>

      {failedJobs.length > 0 && (
        <Card className="border-destructive/40" data-testid="failure-banner">
          <CardContent className="flex flex-wrap items-center justify-between gap-3 pt-6">
            <div className="flex items-start gap-3">
              <AlertTriangle className="h-5 w-5 text-destructive shrink-0" />
              <div>
                <p className="font-medium">{failedJobs.length} ingestion failure(s)</p>
                <p className="text-sm text-muted-foreground">
                  {failedJobs[0].error || nestedResult(failedJobs[0]).error || 'The job did not complete.'}
                </p>
              </div>
            </div>
            {failedJobs[0].file_id && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => retryJob(failedJobs[0])}
                disabled={retrying !== null}
                data-testid="retry-failed-job"
              >
                {retrying === failedJobs[0].job_id
                  ? <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  : <RotateCcw className="mr-2 h-4 w-4" />}
                Retry failed sync
              </Button>
            )}
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium flex items-center gap-2">
            <Clock className="h-4 w-4" />
            Recent ingestion jobs
            {runningJobs.length > 0 && (
              <Badge variant="outline" className="ml-1">
                {runningJobs.length} running
              </Badge>
            )}
          </CardTitle>
          <CardDescription>
            Server-side jobs survive page navigation. A 159-second workbook ingest stays pollable here.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {jobs.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No ingestion jobs yet. Start one from the OneDrive panel, then return here.
            </p>
          ) : (
            <div className="space-y-3">
              {jobs.slice(0, 8).map(job => {
                const sheets = sheetLines(job);
                const result = nestedResult(job);
                const errorText = job.error || result.error || result.reason;
                return (
                  <div
                    key={job.job_id}
                    className="rounded-md border p-3"
                    data-testid={`ingest-job-${job.job_id}`}
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex items-center gap-2 min-w-0">
                        <Badge
                          variant={job.status === 'failed' ? 'destructive' : 'outline'}
                          className={job.status === 'completed' ? 'border-emerald-600 text-emerald-700' : ''}
                        >
                          {job.status === 'running' ? 'in progress' : job.status}
                        </Badge>
                        {jobUnchanged(job) && <Badge variant="secondary">unchanged</Badge>}
                        <span className="font-medium truncate">{jobFileName(job)}</span>
                      </div>
                      <div className="flex items-center gap-2 text-xs text-muted-foreground">
                        <span>{elapsedLabel(job.started_at, job.finished_at)}</span>
                        {job.file_id && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => retryJob(job)}
                            disabled={retrying !== null || job.status === 'running'}
                            data-testid={`retry-job-${job.job_id}`}
                          >
                            {retrying === job.job_id
                              ? <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" />
                              : <RotateCcw className="mr-1 h-3.5 w-3.5" />}
                            Sync again
                          </Button>
                        )}
                      </div>
                    </div>
                    {errorText && (
                      <p className="mt-2 text-xs text-destructive">{String(errorText)}</p>
                    )}
                    <div className="mt-2 text-xs text-muted-foreground">
                      {jobChars(job) !== null && (
                        <span>{jobChars(job)?.toLocaleString()} chars ingested</span>
                      )}
                      {sheets.length > 0 && (
                        <span> · {sheets.length} sheet coverage entries</span>
                      )}
                      {result.status && result.status !== 'ingested' && (
                        <span> · status: {result.status}</span>
                      )}
                    </div>
                    {sheets.length > 0 && (
                      <details className="mt-2" data-testid={`coverage-details-${job.job_id}`}>
                        <summary className="cursor-pointer text-xs text-muted-foreground">
                          Show per-sheet coverage
                        </summary>
                        <ul className="mt-1 space-y-0.5 text-xs text-muted-foreground">
                          {sheets.slice(0, 12).map((line, index) => (
                            <li key={`${job.job_id}-${index}`}>{line.replace(/^-\s*/, '')}</li>
                          ))}
                        </ul>
                        {sheets.length > 12 && (
                          <p className="mt-1 text-xs text-muted-foreground">
                            +{sheets.length - 12} more sheets in the ingestion receipt
                          </p>
                        )}
                      </details>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
