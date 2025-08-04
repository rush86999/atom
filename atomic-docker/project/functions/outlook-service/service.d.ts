import { Client } from '@microsoft/microsoft-graph-client';
export declare function getAuthenticatedClient(userId: string): Promise<Client>;
export declare function searchUserOutlookEmails(userId: string, query: string, maxResults?: number): Promise<any>;
export declare function getUserOutlookEmailContent(userId: string, emailId: string): Promise<any>;
