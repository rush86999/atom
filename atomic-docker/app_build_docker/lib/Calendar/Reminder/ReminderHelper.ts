import { v4 as uuid } from 'uuid'
import { dayjs } from '@lib/date-utils'

// dayjs.extend(utc)
// dayjs.extend(timezone)

import { ApolloClient, gql, NormalizedCacheObject } from '@apollo/client'
import deleteRemindersForEventId from '@lib/apollo/gql/deleteRemindersForEventId'
import listRemindersForEventId from '@lib/apollo/gql/listRemindersForEventId'
import deleteRemindersForEventIds from '@lib/apollo/gql/deleteRemindersForEventIds'
import { ReminderType } from '@lib/dataTypes/ReminderType'


export const deleteRemindersForEvents = async (
  client: ApolloClient<NormalizedCacheObject>,
  eventIds: string[],
  userId: string,
) => {
  try {
    const results = (await client.mutate<{ delete_Reminder: { affected_rows: number } }>({
      mutation: deleteRemindersForEventIds,
      variables: {
        eventIds,
        userId,
      },
    })).data?.delete_Reminder?.affected_rows
    return results
  } catch (e) {
    console.log(e, ' error removing reminders')
  }
}
export const removeRemindersForEvent = async (
  client: ApolloClient<NormalizedCacheObject>,
  eventId: string,
) => {
  try {
    const results = (await client.mutate<{ delete_Reminder: { affected_rows: number, returning: ReminderType[] } }>({
      mutation: deleteRemindersForEventId,
      variables: {
        eventId,
      },
      update(cache, { data }) {
        const deletedReminders = data?.delete_Reminder?.returning
        const normalizedIds = deletedReminders.map(c => cache.identify({ id: c.id, __typename: c.__typename }))
        normalizedIds.forEach(id => cache.evict({ id }))
        cache.gc()
      }
    })).data?.delete_Reminder?.affected_rows
    console.log(results, ' results inside removeRemindersForEvent')
    return results
  } catch (e) {
    console.log(e, ' error removing reminders')
  }
}

export const updateRemindersForEvent = async (
  client: ApolloClient<NormalizedCacheObject>,
  eventId: string,
  userId: string,
  alarms?: string[] | number[],
  timezone?: string,
  useDefaultAlarms?: boolean,
) => {
  try {
    console.log(alarms, ' alarms inside updateRemindersForEvent')
    await removeRemindersForEvent(client, eventId)
    if (alarms) {
      const reminderValues = alarms?.map((a) => generateReminderValues(
        userId,
        eventId,
        (typeof a === 'string') && a,
        timezone || dayjs.tz.guess(),
        (typeof a === 'number') && a,
        useDefaultAlarms,
      ))
      await createRemindersForEvent(client, reminderValues)
    }
  } catch (e) {
    console.log(e, ' error updating reminders')
  }
}

const generateReminderValues = (
  userId: string,
  eventId: string,
  reminderDate?: string,
  timezone?: string,
  minutes?: number,
  useDefault?: boolean,
) => {
  const reminderValueToUpsert: any = {
    id: uuid(),
    userId,
    eventId,
    deleted: false,
    updatedAt: dayjs().toISOString(),
    createdDate: dayjs().toISOString()
  }

  /**
   *  reminderDate,
    timezone,
    minutes,
    useDefault,
   */
  if (reminderDate) {
    reminderValueToUpsert.reminderDate = reminderDate
  }

  if (timezone) {
    reminderValueToUpsert.timezone = timezone
  }

  if (minutes) {
    reminderValueToUpsert.minutes = minutes
  }

  if (useDefault !== undefined) {
    reminderValueToUpsert.useDefault = useDefault
  }

  return reminderValueToUpsert
}

export const createRemindersForEvent = async (
  client: ApolloClient<NormalizedCacheObject>,
  reminderValuesToUpsert: ReminderType[],
) => {
  try {
    console.log(reminderValuesToUpsert, ' reminderValuesToUpsert inside createRemindersForEvent')
    // ASSUMPTION: A custom mutation 'bulkUpsertReminders' is defined in PostGraphile
    const upsertReminder = gql`
    mutation BulkUpsertReminders($reminders: [ReminderInput!]!) {
      bulkUpsertReminders(input: { reminders: $reminders }) {
        # Assuming the custom function returns a list of the upserted reminders
        results: reminders { # Or similar, depending on PG function and PostGraphile schema
          id
          reminderDate
          eventId
          timezone
          method
          minutes
          useDefault
          deleted
          createdDate
          updatedAt
          userId
        }
        # affectedCount # If the function returns a count
      }
    }
  `
    // Adjust generic type for client.mutate based on actual PostGraphile mutation payload
    const resultsData = (await client.mutate<{ bulkUpsertReminders: { results: ReminderType[] } }>({
      mutation: upsertReminder,
      variables: {
        reminders: reminderValuesToUpsert,
      },
      update(cache, { data }) {
        const upsertedReminders = data?.bulkUpsertReminders?.results;
        if (upsertedReminders && upsertedReminders.length > 0) {
          console.log('bulkUpsertReminders results', upsertedReminders);

          // The original cache logic was modifying a root field 'Reminder'.
          // This is less common with PostGraphile which usually uses connection types like 'allReminders'.
          // This part is highly dependent on your actual queries and PostGraphile schema.
          // It will need to be verified and likely adjusted.
          cache.modify({
            fields: {
              // This field name 'Reminder' is likely incorrect for PostGraphile.
              // It would typically be 'allReminders' or a specific query name.
              Reminder: (existingReminders = []) => { // Placeholder for existing cache update logic
                const newReminderRefs = upsertedReminders.map((c) =>
                  cache.writeFragment({
                    data: c,
                    fragment: gql`
                      fragment NewReminder on Reminder {
                        # Type name 'Reminder' should be checked
                        id
                        reminderDate
                        eventId
                        timezone
                        method
                        minutes
                        useDefault
                        deleted
                        createdDate
                        updatedAt
                        userId
                      }
                    `,
                  }),
                );
                return [...existingReminders, ...newReminderRefs];
              },
            },
          });
        }
      },
    });

    console.log(resultsData, ' results inside createRemindersForEvent');
    return resultsData;
  } catch (e) {
    console.log(e, ' error creating reminders');
  }
};

export const createReminderForEvent = async (
  client: ApolloClient<NormalizedCacheObject>,
  userId: string,
  eventId: string,
  reminderDate?: string,
  timezone?: string,
  minutes?: number,
  useDefault?: boolean,
) => {
  try {
    const reminderValueToUpsert: any = {
      id: uuid(),
      userId,
      eventId,
      deleted: false,
      updatedAt: dayjs().toISOString(),
      createdDate: dayjs().toISOString(),
    };

    /**
     *  reminderDate,
      timezone,
      minutes,
      useDefault,
     */
    if (reminderDate) {
      reminderValueToUpsert.reminderDate = reminderDate;
    }

    if (timezone) {
      reminderValueToUpsert.timezone = timezone;
    }

    if (minutes) {
      reminderValueToUpsert.minutes = minutes;
    }

    if (useDefault !== undefined) {
      reminderValueToUpsert.useDefault = useDefault;
    }

    // ASSUMPTION: A custom mutation 'upsertReminder' is defined in PostGraphile for single upsert
    // The dynamic update_columns logic is now handled by the PG function.
    const upsertReminderMutation = gql`
      mutation UpsertReminder($reminder: ReminderInput!) {
        upsertReminder(input: { reminder: $reminder }) {
          # Or input: $reminder directly, depends on PG func
          reminder {
            # Standard PostGraphile payload
            id
            reminderDate
            eventId
            timezone
            method
            minutes
            useDefault
            deleted
            createdDate
            updatedAt
            userId
          }
        }
      }
    `;
    // Adjust generic type for client.mutate based on actual PostGraphile mutation payload
    const resultsData = await client.mutate<{
      upsertReminder: { reminder: ReminderType };
    }>({
      mutation: upsertReminderMutation,
      variables: {
        reminder: reminderValueToUpsert, // Pass the single object
      },
      update(cache, { data }) {
        const upsertedReminder = data?.upsertReminder?.reminder;
        if (upsertedReminder) {
          console.log('upsertReminder result', upsertedReminder);

          // Similar cache update considerations as above.
          cache.modify({
            fields: {
              // Field name 'Reminder' is likely incorrect for PostGraphile list queries.
              Reminder: (existingReminders = []) => {
                // Placeholder
                // Logic to update or add the single reminder to the cache
                const newReminderRef = cache.writeFragment({
                  data: upsertedReminder,
                  fragment: gql`
                    fragment NewSingleReminder on Reminder {
                      # Type name 'Reminder' should be checked
                      id
                      reminderDate
                      eventId
                      timezone
                      method
                      minutes
                      useDefault
                      deleted
                      createdDate
                      updatedAt
                      userId
                    }
                  `,
                });
                return [...existingReminders, newReminderRef];
              },
            },
          });
        }
      },
    });

    console.log(resultsData, ' results inside createReminderForEvent');
    return resultsData;
  } catch (e) {
    console.log(e, ' unable to create reminder for event')
  }
}

export const listRemindersForEvent = async (
  client: ApolloClient<NormalizedCacheObject>,
  eventId: string
) => {
  try {
    const results = (await client.query<{ Reminder: ReminderType[] }>({
      query: listRemindersForEventId,
      variables: {
        eventId,
      },
    })).data?.Reminder
    console.log(results, ' Reminder - inside listRemindersForEvents')
    return results
  } catch (e) {
    console.log(e, ' unable to list reminders for event')
  }
}
/** end */
