import {
  createEmailReminder,
  getDueReminders,
  deleteReminder,
} from '../../reminder-service/service';

export class ReminderSkills {
  async createEmailReminder(
    userId: string,
    emailId: string,
    service: 'gmail' | 'outlook',
    remindAt: Date
  ) {
    return await createEmailReminder(userId, emailId, service, remindAt);
  }

  async getDueReminders() {
    return await getDueReminders();
  }

  async deleteReminder(id: string) {
    return await deleteReminder(id);
  }
}
