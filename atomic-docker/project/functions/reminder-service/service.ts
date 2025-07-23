import { createAdminGraphQLClient } from '../_utils/dbService';

const INSERT_REMINDER_MUTATION = `
mutation InsertEmailReminder($userId: uuid!, $emailId: String!, $service: String!, $remindAt: timestamptz!) {
  insert_email_reminders_one(object: {user_id: $userId, email_id: $emailId, service: $service, remind_at: $remindAt}) {
    id
  }
}
`;

const GET_DUE_REMINDERS_QUERY = `
query GetDueReminders($now: timestamptz!) {
  email_reminders(where: {remind_at: {_lte: $now}}) {
    id
    user_id
    email_id
    service
  }
}
`;

const DELETE_REMINDER_MUTATION = `
mutation DeleteEmailReminder($id: uuid!) {
  delete_email_reminders_by_pk(id: $id) {
    id
  }
}
`;

export async function createEmailReminder(userId: string, emailId: string, service: 'gmail' | 'outlook', remindAt: Date) {
  const adminGraphQLClient = createAdminGraphQLClient();
  const response = await adminGraphQLClient.request(INSERT_REMINDER_MUTATION, {
    userId,
    emailId,
    service,
    remindAt: remindAt.toISOString(),
  });
  return response.insert_email_reminders_one;
}

export async function getDueReminders() {
  const adminGraphQLClient = createAdminGraphQLClient();
  const response = await adminGraphQLClient.request(GET_DUE_REMINDERS_QUERY, {
    now: new Date().toISOString(),
  });
  return response.email_reminders;
}

export async function deleteReminder(id: string) {
  const adminGraphQLClient = createAdminGraphQLClient();
  const response = await adminGraphQLClient.request(DELETE_REMINDER_MUTATION, { id });
  return response.delete_email_reminders_by_pk;
}

// This function would be called by a cron job or a scheduler
export async function processDueReminders() {
  const dueReminders = await getDueReminders();
  for (const reminder of dueReminders) {
    // Send a notification to the user. This could be an email, a push notification, or a Slack message.
    console.log(`Sending reminder for email ${reminder.email_id} to user ${reminder.user_id}`);
    // After sending the notification, delete the reminder
    await deleteReminder(reminder.id);
  }
}
