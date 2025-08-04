declare function searchUserEmails(userId: string, query: string, maxResults?: number): Promise<{
    gmail: any;
    outlook: any;
}>;
declare function getUserEmailContent(userId: string, emailId: string, service: 'gmail' | 'outlook'): Promise<any>;
export { searchUserEmails, getUserEmailContent };
