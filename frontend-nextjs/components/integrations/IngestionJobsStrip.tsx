'use client';

import React from 'react';
import { Download } from 'lucide-react';
import type { IngestJob } from '@/lib/ingest-jobs';

interface IngestionJobsStripProps {
  jobs: IngestJob[];
  max?: number;
}

function jobLabel(job: IngestJob): string {
  if (job.kind === 'folder') {
    const count = job.folder_ids?.length ?? 0;
    return `Folder ingest (${count} folder${count === 1 ? '' : 's'})`;
  }
  if (job.kind === 'sync') return 'Full-tree sync';
  return 'File ingest';
}

/**
 * Running / recent ingestion jobs for one integration — server-side state,
 * so this survives navigating away and back mid-ingest (job ids otherwise
 * only lived in the page that started the ingest).
 */
export default function IngestionJobsStrip({ jobs, max = 3 }: IngestionJobsStripProps) {
  if (!jobs.length) return null;
  return (
    <div className="border rounded-md divide-y overflow-hidden text-xs" data-testid="ingest-jobs-strip">
      {jobs.slice(0, max).map(job => {
        const running = job.status === 'running';
        const fileCount = job.result?.files_ingested ?? (job.result?.success ? 1 : 0);
        return (
          <div
            key={job.job_id}
            className="flex items-center justify-between px-3 py-2 bg-gray-50 dark:bg-gray-800"
          >
            <span className="flex items-center gap-2 text-gray-700 dark:text-gray-300">
              <Download className={`w-3.5 h-3.5 text-blue-600 ${running ? 'animate-bounce' : ''}`} />
              {jobLabel(job)}
              {running
                ? ' in progress…'
                : job.status === 'completed'
                  ? ` completed — ${fileCount} file${fileCount === 1 ? '' : 's'}`
                  : ` failed${job.error ? `: ${job.error}` : ''}`}
            </span>
            <span className="text-gray-400">
              {new Date(job.finished_at || job.started_at || Date.now()).toLocaleTimeString()}
            </span>
          </div>
        );
      })}
    </div>
  );
}
