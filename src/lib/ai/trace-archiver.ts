import * as lancedb from 'vectordb';
import { DatabaseService, getDatabase } from '../database';
import { v4 as uuidv4 } from 'uuid';

/**
 * Service to manage tiered storage of agent traces.
 * Moves old traces from hot storage (Postgres) to cold storage (LanceDB on S3).
 */
export class TraceArchiverService {
    private db: DatabaseService;
    private s3Uri: string;
    private tableName = 'agent_traces_archive';

    constructor(db: DatabaseService) {
        this.db = db;
        // Ensure AWS environment variables are set for LanceDB S3 support
        const bucket = process.env.AWS_S3_BUCKET_NAME;
        if (!bucket) {
            console.warn('[TraceArchiver] AWS_S3_BUCKET_NAME not set. Archival may fail or use local fallback.');
        }
        this.s3Uri = bucket ? `s3://${bucket}/lancedb` : 'data/lancedb-local';
    }

    /**
     * Archive traces older than X days.
     * 1. Read from Postgres
     * 2. Write to LanceDB
     * 3. Delete from Postgres
     */
    async archiveOldTraces(retentionDays: number = 7): Promise<{ archived: number, errors: string[] }> {
        const errors: string[] = [];
        let archivedCount = 0;

        try {
            console.log(`[TraceArchiver] Connecting to LanceDB at ${this.s3Uri}`);
            const lance = await lancedb.connect(this.s3Uri);

            let table: lancedb.Table;
            try {
                table = await lance.openTable(this.tableName);
            } catch (e) {
                console.log('[TraceArchiver] Table not found, creating new one.');
                // Define schema implicitly by first insertion or usage
                // For now, we'll let existing implementation handling creation if supported, or create with empty data
                // LanceDB usually requires initial data to infer schema if not strict
            }

            // 1. Fetch Candidates
            const cutoffDate = new Date();
            cutoffDate.setDate(cutoffDate.getDate() - retentionDays);

            const candidates = await this.db.query(`
                SELECT id, agent_id, tenant_id, started_at, triggered_by, status, input_summary, result_summary
                FROM agent_executions
                WHERE started_at < $1
                ORDER BY started_at ASC
                LIMIT 100
            `, [cutoffDate]);

            if (candidates.rows.length === 0) {
                return { archived: 0, errors: [] };
            }

            const recordsToArchive = [];
            const executionIds = [];

            for (const execution of candidates.rows) {
                // Fetch Steps
                const stepsRes = await this.db.query(`
                    SELECT * FROM agent_trace_steps WHERE execution_id = $1 ORDER BY step_number ASC
                `, [execution.id]);

                // Flatten structure: We store the full execution + steps as a JSON block or nested fields
                // For LanceDB queryability, we might want to flatten steps if we do vector search, 
                // but for "Archive" retrieval, storing the JSON blob of steps is often sufficient.
                // However, user requested "LanceDB", implying potential future vector search.
                // We will store metadata + stringified steps for now (Cold Storage pattern).

                recordsToArchive.push({
                    execution_id: execution.id,
                    agent_id: execution.agent_id,
                    tenant_id: execution.tenant_id,
                    started_at: new Date(execution.started_at).toISOString(),
                    status: execution.status,
                    trace_data: JSON.stringify({
                        execution: execution,
                        steps: stepsRes.rows
                    }),
                    // Optional: Embedding for semantic search could be added here
                    vector: Array(1536).fill(0) // Placeholder if table requires vector
                });

                executionIds.push(execution.id);
            }

            // 2. Write to LanceDB
            if (recordsToArchive.length > 0) {
                try {
                    // Check if table exists again or create
                    const tableNames = await lance.tableNames();
                    if (!tableNames.includes(this.tableName)) {
                        await lance.createTable(this.tableName, recordsToArchive);
                    } else {
                        table = await lance.openTable(this.tableName);
                        await table.add(recordsToArchive);
                    }

                    console.log(`[TraceArchiver] Wrote ${recordsToArchive.length} records to S3.`);

                    // 3. Delete from Postgres & Update Storage Accounting
                    await this.db.query(`
                        DELETE FROM agent_executions WHERE id = ANY($1)
                    `, [executionIds]);

                    // Calculate total bytes moved for each tenant in this batch
                    // For simplicity, we assume we know the approximate size of what we deleted
                    // In a production system, we might query the size before deleting or track it
                    // Here we'll estimate based on the archived records
                    for (const record of recordsToArchive) {
                        const size = Buffer.byteLength(record.trace_data);
                        // Decrement Hot Trace, Increment Cold Archive
                        await this.db.updateStorageUsage(record.tenant_id, -size, 'agent_trace');
                        await this.db.updateStorageUsage(record.tenant_id, size, 'agent_archive');
                    }

                    archivedCount = recordsToArchive.length;

                } catch (writeErr) {
                    console.error('[TraceArchiver] Failed to write to LanceDB:', writeErr);
                    errors.push(`LanceDB Write Error: ${writeErr}`);
                }
            }

        } catch (err: any) {
            console.error('[TraceArchiver] Critical error:', err);
            errors.push(err.message);
        }

        return { archived: archivedCount, errors };
    }

    /**
     * Retrieve a specific execution from Archive
     */
    async getArchivedTrace(executionId: string): Promise<any | null> {
        try {
            const lance = await lancedb.connect(this.s3Uri);
            const table = await lance.openTable(this.tableName);

            // LanceDB filtering
            const results = await table
                .search(undefined) // No vector search
                .filter(`execution_id = '${executionId}'`)
                .limit(1)
                .execute();

            if (results.length > 0) {
                const record = results[0];
                return JSON.parse(record.trace_data as string);
            }
        } catch (err) {
            console.error(`[TraceArchiver] Failed to fetch ${executionId} from archive:`, err);
        }
        return null;
    }

    /**
     * List archived executions for an agent
     */
    async listArchivedHistory(agentId: string, limit: number = 20): Promise<any[]> {
        try {
            const lance = await lancedb.connect(this.s3Uri);
            // Check if table exists
            const tableNames = await lance.tableNames();
            if (!tableNames.includes(this.tableName)) return [];

            const table = await lance.openTable(this.tableName);

            const results = await table
                .search(undefined)
                .filter(`agent_id = '${agentId}'`)
                .limit(limit)
                .execute();

            // Transform back to lightweight history objects
            return results.map(r => {
                const data = JSON.parse(r.trace_data as string);
                return data.execution;
            });

        } catch (err) {
            console.error(`[TraceArchiver] Failed to list list history for ${agentId}:`, err);
            return [];
        }
    }
}

// Singleton
let archiver: TraceArchiverService | null = null;
export function getTraceArchiver(): TraceArchiverService {
    if (!archiver) {
        archiver = new TraceArchiverService(getDatabase());
    }
    return archiver;
}
