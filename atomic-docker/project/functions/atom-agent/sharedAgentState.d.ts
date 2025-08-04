export interface PendingRequestInfo {
    fileKey: string;
    userId: string;
    hostId: string;
    singletonId: string;
    originalQuery?: string;
    submittedAt: Date;
}
export declare function storePendingRequest(jobInfo: PendingRequestInfo): Promise<void>;
export declare function retrievePendingRequest(fileKey: string): Promise<PendingRequestInfo | null>;
export declare function removePendingRequest(fileKey: string): Promise<void>;
