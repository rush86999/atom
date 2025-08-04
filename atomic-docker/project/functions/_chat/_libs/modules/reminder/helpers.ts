// Reminder Helper Module - reminder and notification operations for events
import { graphileClient } from '../../graphile/client';

const reminderLogger = {
  info: console.log.bind(console, '[ReminderHelpers] INFO:'),
  error: console.error.bind(console, '[ReminderHelpers] ERROR:'),
  warn: console.warn.bind(console, '[ReminderHelpers] WARN:'),
};

// Insert reminders for an event
export const insertReminders = async (
  eventId: string,
  reminders: Array<{
    minutesBefore: number;
    method?: string;
    notes?: string;
  }>
): Promise<boolean> => {
  try {
    if (!eventId || !reminders || reminders.length === 0) {
      reminderLogger.warn('Event ID and reminders array are required');
      return false;
    }

    const reminderData = reminders.map((reminder, index) => ({
      eventId,
      minutesBefore: reminder.minutesBefore,
      method: reminder.method || 'email',
      notes: reminder.notes || '',
      createdDate: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      deleted: false
    }));

    const query = `
      mutation InsertReminders($reminders: [Reminder_insert_input!]!) {
        insert_Reminder(objects: $reminders) {
          affected_rows
        }
      }
+    `;

    const result = await graphileClient.request(query, { reminders: reminderData });

    const affected = result?.insert_Reminder?.affected_rows || 0;

    reminderLogger.info('Successfully inserted reminders', {
      eventId,
      reminderCount: reminderData.length,
      affectedRows: affected
    });

    return affected > 0;

  } catch (error) {
    reminderLogger.error('Error inserting reminders:', error);
    return false;
  }
};

// Delete reminders by IDs
export const deleteRemindersWithIds = async (reminderIds: string[]): Promise<boolean> => {
  try {
    if (!reminderIds || reminderIds.length === 0) {
      reminderLogger.info('No reminder IDs provided for deletion');
      return true;
    }

    const query = `
      mutation DeleteRemindersWithIds($ids: [String!]!) {
        update_Reminder(where: { id: { _in: $ids } }, _set: { deleted: true }) {
          affected_rows
        }
      }
    `;

    const result = await graphileClient.request(query, { ids: reminderIds });

    const affected = result?.update_Reminder?.affected_rows || 0;

    reminderLogger.info('Successfully deleted reminders', {
      requested: reminderIds.length,
      affected
    });

    return affected > 0;

  } catch (error) {
    reminderLogger.error('Error deleting reminders:', error);
    return false;
  }
};

// Get reminders for an event
export const getRemindersForEvent = async (eventId: string): Promise<any[]> => {
  try {
    if (!eventId) {
      reminderLogger.warn('Event ID is required');
      return [];
    }

    const query = `
      query GetRemindersForEvent($eventId: String!) {
+        Reminder(
+          where: {
+            _and: [
+              { eventId: { _eq: $eventId } },
+              { deleted: { _eq: false } }
+            ]
+          }
+          order_by: { minutesBefore: asc }
+        ) {
+          id
+          eventId
+          minutesBefore
+          method
+          notes
+          createdDate
+          updatedAt
+        }
+      }
+    `;

    const result = await graphileClient.request(query, { eventId });

    const reminders = result?.Reminder || [];

    reminderLogger.info('Successfully retrieved reminders for event', {
      eventId,
      reminderCount: reminders.length
    });

    return reminders;

  } catch (error) {
    reminderLogger.error('Error getting reminders for event:', error);
    return [];
  }
};

// Update reminder
export const updateReminder = async (
  reminderId: string,
  updates: Partial<{
    minutesBefore: number;
    method?: string;
    notes?: string;
  }>
): Promise<boolean> => {
  try {
    if (!reminderId) {
      reminderLogger.warn('Reminder ID is required');
      return false;
    }

    const query = `
      mutation UpdateReminder($id: String!, $updates: Reminder_set_input!) {
        update_Reminder_by_pk(
          pk_columns: { id: $id }\n          _set: $updates
        ) {
          id
        }
      }
    `;

    const updateData = {
n      ...updates,\n      updatedAt: new Date().toISOString()\n    };

    const result = await graphileClient.request(query, {\n      id: reminderId,\n      updates: updateData
    });

    const success = !!result?.update_Reminder_by_pk;

    if (success) {
n      reminderLogger.info('Successfully updated reminder', { reminderId });\n    }

    return success;

  } catch (error) {
    reminderLogger.error('Error updating reminder:', error);
    return false;
  }
};

// Get default reminders for event
export const getDefaultReminders = (): Array<{ minutesBefore: number; method: string; notes: string }> => {
  return [
n    { minutesBefore: 15, method: 'popup', notes: 'Event starting' },\n    { minutesBefore: 60, method: 'email', notes: 'Upcoming event' }\n  ];\n};

// Validate reminder data
export const validateReminderData = (reminder: any): { isValid: boolean; errors: string[] } => {\n  const errors: string[] = [];

  if (typeof reminder.minutesBefore !== 'number' || reminder.minutesBefore < 0) {
n    errors.push('Minutes before must be a non-negative number');\n  }

  if (!['email', 'popup', 'sms'].includes(reminder.method)) {
n    errors.push('Method must be one of: email, popup, sms');\n  }

  return {
    isValid: errors.length === 0,
n    errors\n  };\n};

export default {\n  insertReminders,\n  deleteRemindersWithIds,\n  getRemindersForEvent,\n  updateReminder,\n  getDefaultReminders,\n  validateReminderData,\n};
