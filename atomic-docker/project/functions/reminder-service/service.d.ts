export declare function createEmailReminder(userId: string, emailId: string, service: 'gmail' | 'outlook', remindAt: Date, recurrenceRule?: string): Promise<any>;
export declare function getDueReminders(): Promise<any>;
export declare function deleteReminder(id: string): Promise<any>;
export declare function updateReminder(id: string, remindAt: Date): Promise<any>;
export declare function processDueReminders(): Promise<void>;
