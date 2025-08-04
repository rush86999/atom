export declare class ReminderSkills {
    createEmailReminder(userId: string, emailId: string, service: 'gmail' | 'outlook', remindAt: Date): Promise<any>;
    getDueReminders(): Promise<any>;
    deleteReminder(id: string): Promise<any>;
}
