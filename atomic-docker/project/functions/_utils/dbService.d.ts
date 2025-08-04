import { PendingRequestInfo } from '../sharedAgentState';
export declare function addPendingJob(jobInfo: PendingRequestInfo): Promise<void>;
export declare function getPendingJob(fileKey: string): Promise<PendingRequestInfo | null>;
export declare function deletePendingJob(fileKey: string): Promise<void>;
export declare function updatePendingJobStatus(fileKey: string, status: string): Promise<void>;
export declare function closeDbPool(): Promise<void>;
