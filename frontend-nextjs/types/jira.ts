export interface JiraResources {
    id: string;
    name: string;
    url: string;
    scopes: string[];
    avatarUrl?: string;
    cloud_id: string;
    discovery?: {
        projects?: JiraProject[];
        issues?: JiraIssue[];
    };
}

export interface JiraProject {
    id: string;
    key: string;
    name: string;
    projectTypeKey?: string;
    avatarUrls?: {
        "48x48": string;
        "24x24"?: string;
        "16x16"?: string;
        "32x32"?: string;
        [key: string]: string | undefined;
    };
}

export interface JiraIssue {
    id: string;
    key: string;
    summary: string;
    status: string;
}

export interface JiraIntegrationStatus {
    connected: boolean;
    resourceId: string;
    resourceName: string;
    projectCount: number;
    issueCount: number;
    lastSync: string;
    status: 'active' | 'inactive' | 'error';
}
