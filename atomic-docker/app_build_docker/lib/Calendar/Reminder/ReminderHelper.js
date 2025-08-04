"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.listRemindersForEvent = exports.createReminderForEvent = exports.createRemindersForEvent = exports.updateRemindersForEvent = exports.removeRemindersForEvent = exports.deleteRemindersForEvents = void 0;
const uuid_1 = require("uuid");
const date_utils_1 = require("@lib/date-utils");
// dayjs.extend(utc)
// dayjs.extend(timezone)
const client_1 = require("@apollo/client");
const deleteRemindersForEventId_1 = __importDefault(require("@lib/apollo/gql/deleteRemindersForEventId"));
const listRemindersForEventId_1 = __importDefault(require("@lib/apollo/gql/listRemindersForEventId"));
const deleteRemindersForEventIds_1 = __importDefault(require("@lib/apollo/gql/deleteRemindersForEventIds"));
const deleteRemindersForEvents = async (client, eventIds, userId) => {
    try {
        const results = (await client.mutate({
            mutation: deleteRemindersForEventIds_1.default,
            variables: {
                eventIds,
                userId,
            },
        })).data?.delete_Reminder?.affected_rows;
        return results;
    }
    catch (e) {
        console.log(e, ' error removing reminders');
    }
};
exports.deleteRemindersForEvents = deleteRemindersForEvents;
const removeRemindersForEvent = async (client, eventId) => {
    try {
        const results = (await client.mutate({
            mutation: deleteRemindersForEventId_1.default,
            variables: {
                eventId,
            },
            update(cache, { data }) {
                const deletedReminders = data?.delete_Reminder?.returning;
                const normalizedIds = deletedReminders.map(c => cache.identify({ id: c.id, __typename: c.__typename }));
                normalizedIds.forEach(id => cache.evict({ id }));
                cache.gc();
            }
        })).data?.delete_Reminder?.affected_rows;
        console.log(results, ' results inside removeRemindersForEvent');
        return results;
    }
    catch (e) {
        console.log(e, ' error removing reminders');
    }
};
exports.removeRemindersForEvent = removeRemindersForEvent;
const updateRemindersForEvent = async (client, eventId, userId, alarms, timezone, useDefaultAlarms) => {
    try {
        console.log(alarms, ' alarms inside updateRemindersForEvent');
        await (0, exports.removeRemindersForEvent)(client, eventId);
        if (alarms) {
            const reminderValues = alarms?.map((a) => generateReminderValues(userId, eventId, (typeof a === 'string') && a, timezone || date_utils_1.dayjs.tz.guess(), (typeof a === 'number') && a, useDefaultAlarms));
            await (0, exports.createRemindersForEvent)(client, reminderValues);
        }
    }
    catch (e) {
        console.log(e, ' error updating reminders');
    }
};
exports.updateRemindersForEvent = updateRemindersForEvent;
const generateReminderValues = (userId, eventId, reminderDate, timezone, minutes, useDefault) => {
    const reminderValueToUpsert = {
        id: (0, uuid_1.v4)(),
        userId,
        eventId,
        deleted: false,
        updatedAt: (0, date_utils_1.dayjs)().toISOString(),
        createdDate: (0, date_utils_1.dayjs)().toISOString()
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
    return reminderValueToUpsert;
};
const createRemindersForEvent = async (client, reminderValuesToUpsert) => {
    try {
        console.log(reminderValuesToUpsert, ' reminderValuesToUpsert inside createRemindersForEvent');
        // ASSUMPTION: A custom mutation 'bulkUpsertReminders' is defined in PostGraphile
        const upsertReminder = (0, client_1.gql) `
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
  `;
        // Adjust generic type for client.mutate based on actual PostGraphile mutation payload
        const resultsData = (await client.mutate({
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
                            Reminder: (existingReminders = []) => {
                                const newReminderRefs = upsertedReminders.map((c) => cache.writeFragment({
                                    data: c,
                                    fragment: (0, client_1.gql) `
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
                                }));
                                return [...existingReminders, ...newReminderRefs];
                            },
                        },
                    });
                }
            },
        }));
        console.log(resultsData, ' results inside createRemindersForEvent');
        return resultsData;
    }
    catch (e) {
        console.log(e, ' error creating reminders');
    }
};
exports.createRemindersForEvent = createRemindersForEvent;
const createReminderForEvent = async (client, userId, eventId, reminderDate, timezone, minutes, useDefault) => {
    try {
        const reminderValueToUpsert = {
            id: (0, uuid_1.v4)(),
            userId,
            eventId,
            deleted: false,
            updatedAt: (0, date_utils_1.dayjs)().toISOString(),
            createdDate: (0, date_utils_1.dayjs)().toISOString(),
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
        const upsertReminderMutation = (0, client_1.gql) `
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
        const resultsData = await client.mutate({
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
                                    fragment: (0, client_1.gql) `
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
    }
    catch (e) {
        console.log(e, ' unable to create reminder for event');
    }
};
exports.createReminderForEvent = createReminderForEvent;
const listRemindersForEvent = async (client, eventId) => {
    try {
        const results = (await client.query({
            query: listRemindersForEventId_1.default,
            variables: {
                eventId,
            },
        })).data?.Reminder;
        console.log(results, ' Reminder - inside listRemindersForEvents');
        return results;
    }
    catch (e) {
        console.log(e, ' unable to list reminders for event');
    }
};
exports.listRemindersForEvent = listRemindersForEvent;
/** end */
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiUmVtaW5kZXJIZWxwZXIuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJSZW1pbmRlckhlbHBlci50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOzs7Ozs7QUFBQSwrQkFBaUM7QUFDakMsZ0RBQXVDO0FBRXZDLG9CQUFvQjtBQUNwQix5QkFBeUI7QUFFekIsMkNBQXlFO0FBQ3pFLDBHQUFpRjtBQUNqRixzR0FBNkU7QUFDN0UsNEdBQW1GO0FBSTVFLE1BQU0sd0JBQXdCLEdBQUcsS0FBSyxFQUMzQyxNQUEyQyxFQUMzQyxRQUFrQixFQUNsQixNQUFjLEVBQ2QsRUFBRTtJQUNGLElBQUksQ0FBQztRQUNILE1BQU0sT0FBTyxHQUFHLENBQUMsTUFBTSxNQUFNLENBQUMsTUFBTSxDQUFpRDtZQUNuRixRQUFRLEVBQUUsb0NBQTBCO1lBQ3BDLFNBQVMsRUFBRTtnQkFDVCxRQUFRO2dCQUNSLE1BQU07YUFDUDtTQUNGLENBQUMsQ0FBQyxDQUFDLElBQUksRUFBRSxlQUFlLEVBQUUsYUFBYSxDQUFBO1FBQ3hDLE9BQU8sT0FBTyxDQUFBO0lBQ2hCLENBQUM7SUFBQyxPQUFPLENBQUMsRUFBRSxDQUFDO1FBQ1gsT0FBTyxDQUFDLEdBQUcsQ0FBQyxDQUFDLEVBQUUsMkJBQTJCLENBQUMsQ0FBQTtJQUM3QyxDQUFDO0FBQ0gsQ0FBQyxDQUFBO0FBakJZLFFBQUEsd0JBQXdCLDRCQWlCcEM7QUFDTSxNQUFNLHVCQUF1QixHQUFHLEtBQUssRUFDMUMsTUFBMkMsRUFDM0MsT0FBZSxFQUNmLEVBQUU7SUFDRixJQUFJLENBQUM7UUFDSCxNQUFNLE9BQU8sR0FBRyxDQUFDLE1BQU0sTUFBTSxDQUFDLE1BQU0sQ0FBNEU7WUFDOUcsUUFBUSxFQUFFLG1DQUF5QjtZQUNuQyxTQUFTLEVBQUU7Z0JBQ1QsT0FBTzthQUNSO1lBQ0QsTUFBTSxDQUFDLEtBQUssRUFBRSxFQUFFLElBQUksRUFBRTtnQkFDcEIsTUFBTSxnQkFBZ0IsR0FBRyxJQUFJLEVBQUUsZUFBZSxFQUFF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QUE7Ozs7Ozs7Ozs7Ozs7OzttQkFlWjtpQ0FDRixDQUFDLENBQUM7Z0NBQ0gsT0FBTyxDQUFDLEdBQUcsaUJBQWlCLEVBQUUsY0FBYyxDQUFDLENBQUM7NEJBQ2hELENBQUM7eUJBQ0Y7cUJBQ0YsQ0FBQyxDQUFDO2dCQUNMLENBQUM7WUFDSCxDQUFDO1NBQ0YsQ0FBQyxDQUFDO1FBRUgsT0FBTyxDQUFDLEdBQUcsQ0FBQyxXQUFXLEVBQUUsd0NBQXdDLENBQUMsQ0FBQztRQUNuRSxPQUFPLFdBQVcsQ0FBQztJQUNyQixDQUFDO0lBQUMsT0FBTyxDQUFDLEVBQUUsQ0FBQztRQUNYLE9BQU8sQ0FBQyxHQUFHLENBQUMsQ0FBQyxFQUFFLHNDQUFzQyxDQUFDLENBQUE7SUFDeEQsQ0FBQztBQUNILENBQUMsQ0FBQTtBQXBIWSxRQUFBLHNCQUFzQiwwQkFvSGxDO0FBRU0sTUFBTSxxQkFBcUIsR0FBRyxLQUFLLEVBQ3hDLE1BQTJDLEVBQzNDLE9BQWUsRUFDZixFQUFFO0lBQ0YsSUFBSSxDQUFDO1FBQ0gsTUFBTSxPQUFPLEdBQUcsQ0FBQyxNQUFNLE1BQU0sQ0FBQyxLQUFLLENBQStCO1lBQ2hFLEtBQUssRUFBRSxpQ0FBdUI7WUFDOUIsU0FBUyxFQUFFO2dCQUNULE9BQU87YUFDUjtTQUNGLENBQUMsQ0FBQyxDQUFDLElBQUksRUFBRSxRQUFRLENBQUE7UUFDbEIsT0FBTyxDQUFDLEdBQUcsQ0FBQyxPQUFPLEVBQUUsMkNBQTJDLENBQUMsQ0FBQTtRQUNqRSxPQUFPLE9BQU8sQ0FBQTtJQUNoQixDQUFDO0lBQUMsT0FBTyxDQUFDLEVBQUUsQ0FBQztRQUNYLE9BQU8sQ0FBQyxHQUFHLENBQUMsQ0FBQyxFQUFFLHFDQUFxQyxDQUFDLENBQUE7SUFDdkQsQ0FBQztBQUNILENBQUMsQ0FBQTtBQWhCWSxRQUFBLHFCQUFxQix5QkFnQmpDO0FBQ0QsVUFBVSIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7IHY0IGFzIHV1aWQgfSBmcm9tICd1dWlkJ1xuaW1wb3J0IHsgZGF5anMgfSBmcm9tICdAbGliL2RhdGUtdXRpbHMnXG5cbi8vIGRheWpzLmV4dGVuZCh1dGMpXG4vLyBkYXlqcy5leHRlbmQodGltZXpvbmUpXG5cbmltcG9ydCB7IEFwb2xsb0NsaWVudCwgZ3FsLCBOb3JtYWxpemVkQ2FjaGVPYmplY3QgfSBmcm9tICdAYXBvbGxvL2NsaWVudCdcbmltcG9ydCBkZWxldGVSZW1pbmRlcnNGb3JFdmVudElkIGZyb20gJ0BsaWIvYXBvbGxvL2dxbC9kZWxldGVSZW1pbmRlcnNGb3JFdmVudElkJ1xuaW1wb3J0IGxpc3RSZW1pbmRlcnNGb3JFdmVudElkIGZyb20gJ0BsaWIvYXBvbGxvL2dxbC9saXN0UmVtaW5kZXJzRm9yRXZlbnRJZCdcbmltcG9ydCBkZWxldGVSZW1pbmRlcnNGb3JFdmVudElkcyBmcm9tICdAbGliL2Fwb2xsby9ncWwvZGVsZXRlUmVtaW5kZXJzRm9yRXZlbnRJZHMnXG5pbXBvcnQgeyBSZW1pbmRlclR5cGUgfSBmcm9tICdAbGliL2RhdGFUeXBlcy9SZW1pbmRlclR5cGUnXG5cblxuZXhwb3J0IGNvbnN0IGRlbGV0ZVJlbWluZGVyc0ZvckV2ZW50cyA9IGFzeW5jIChcbiAgY2xpZW50OiBBcG9sbG9DbGllbnQ8Tm9ybWFsaXplZENhY2hlT2JqZWN0PixcbiAgZXZlbnRJZHM6IHN0cmluZ1tdLFxuICB1c2VySWQ6IHN0cmluZyxcbikgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IHJlc3VsdHMgPSAoYXdhaXQgY2xpZW50Lm11dGF0ZTx7IGRlbGV0ZV9SZW1pbmRlcjogeyBhZmZlY3RlZF9yb3dzOiBudW1iZXIgfSB9Pih7XG4gICAgICBtdXRhdGlvbjogZGVsZXRlUmVtaW5kZXJzRm9yRXZlbnRJZHMsXG4gICAgICB2YXJpYWJsZXM6IHtcbiAgICAgICAgZXZlbnRJZHMsXG4gICAgICAgIHVzZXJJZCxcbiAgICAgIH0sXG4gICAgfSkpLmRhdGE/LmRlbGV0ZV9SZW1pbmRlcj8uYWZmZWN0ZWRfcm93c1xuICAgIHJldHVybiByZXN1bHRzXG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIGVycm9yIHJlbW92aW5nIHJlbWluZGVycycpXG4gIH1cbn1cbmV4cG9ydCBjb25zdCByZW1vdmVSZW1pbmRlcnNGb3JFdmVudCA9IGFzeW5jIChcbiAgY2xpZW50OiBBcG9sbG9DbGllbnQ8Tm9ybWFsaXplZENhY2hlT2JqZWN0PixcbiAgZXZlbnRJZDogc3RyaW5nLFxuKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3QgcmVzdWx0cyA9IChhd2FpdCBjbGllbnQubXV0YXRlPHsgZGVsZXRlX1JlbWluZGVyOiB7IGFmZmVjdGVkX3Jvd3M6IG51bWJlciwgcmV0dXJuaW5nOiBSZW1pbmRlclR5cGVbXSB9IH0+KHtcbiAgICAgIG11dGF0aW9uOiBkZWxldGVSZW1pbmRlcnNGb3JFdmVudElkLFxuICAgICAgdmFyaWFibGVzOiB7XG4gICAgICAgIGV2ZW50SWQsXG4gICAgICB9LFxuICAgICAgdXBkYXRlKGNhY2hlLCB7IGRhdGEgfSkge1xuICAgICAgICBjb25zdCBkZWxldGVkUmVtaW5kZXJzID0gZGF0YT8uZGVsZXRlX1JlbWluZGVyPy5yZXR1cm5pbmdcbiAgICAgICAgY29uc3Qgbm9ybWFsaXplZElkcyA9IGRlbGV0ZWRSZW1pbmRlcnMubWFwKGMgPT4gY2FjaGUuaWRlbnRpZnkoeyBpZDogYy5pZCwgX190eXBlbmFtZTogYy5fX3R5cGVuYW1lIH0pKVxuICAgICAgICBub3JtYWxpemVkSWRzLmZvckVhY2goaWQgPT4gY2FjaGUuZXZpY3QoeyBpZCB9KSlcbiAgICAgICAgY2FjaGUuZ2MoKVxuICAgICAgfVxuICAgIH0pKS5kYXRhPy5kZWxldGVfUmVtaW5kZXI/LmFmZmVjdGVkX3Jvd3NcbiAgICBjb25zb2xlLmxvZyhyZXN1bHRzLCAnIHJlc3VsdHMgaW5zaWRlIHJlbW92ZVJlbWluZGVyc0ZvckV2ZW50JylcbiAgICByZXR1cm4gcmVzdWx0c1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyBlcnJvciByZW1vdmluZyByZW1pbmRlcnMnKVxuICB9XG59XG5cbmV4cG9ydCBjb25zdCB1cGRhdGVSZW1pbmRlcnNGb3JFdmVudCA9IGFzeW5jIChcbiAgY2xpZW50OiBBcG9sbG9DbGllbnQ8Tm9ybWFsaXplZENhY2hlT2JqZWN0PixcbiAgZXZlbnRJZDogc3RyaW5nLFxuICB1c2VySWQ6IHN0cmluZyxcbiAgYWxhcm1zPzogc3RyaW5nW10gfCBudW1iZXJbXSxcbiAgdGltZXpvbmU/OiBzdHJpbmcsXG4gIHVzZURlZmF1bHRBbGFybXM/OiBib29sZWFuLFxuKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc29sZS5sb2coYWxhcm1zLCAnIGFsYXJtcyBpbnNpZGUgdXBkYXRlUmVtaW5kZXJzRm9yRXZlbnQnKVxuICAgIGF3YWl0IHJlbW92ZVJlbWluZGVyc0ZvckV2ZW50KGNsaWVudCwgZXZlbnRJZClcbiAgICBpZiAoYWxhcm1zKSB7XG4gICAgICBjb25zdCByZW1pbmRlclZhbHVlcyA9IGFsYXJtcz8ubWFwKChhKSA9PiBnZW5lcmF0ZVJlbWluZGVyVmFsdWVzKFxuICAgICAgICB1c2VySWQsXG4gICAgICAgIGV2ZW50SWQsXG4gICAgICAgICh0eXBlb2YgYSA9PT0gJ3N0cmluZycpICYmIGEsXG4gICAgICAgIHRpbWV6b25lIHx8IGRheWpzLnR6Lmd1ZXNzKCksXG4gICAgICAgICh0eXBlb2YgYSA9PT0gJ251bWJlcicpICYmIGEsXG4gICAgICAgIHVzZURlZmF1bHRBbGFybXMsXG4gICAgICApKVxuICAgICAgYXdhaXQgY3JlYXRlUmVtaW5kZXJzRm9yRXZlbnQoY2xpZW50LCByZW1pbmRlclZhbHVlcylcbiAgICB9XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIGVycm9yIHVwZGF0aW5nIHJlbWluZGVycycpXG4gIH1cbn1cblxuY29uc3QgZ2VuZXJhdGVSZW1pbmRlclZhbHVlcyA9IChcbiAgdXNlcklkOiBzdHJpbmcsXG4gIGV2ZW50SWQ6IHN0cmluZyxcbiAgcmVtaW5kZXJEYXRlPzogc3RyaW5nLFxuICB0aW1lem9uZT86IHN0cmluZyxcbiAgbWludXRlcz86IG51bWJlcixcbiAgdXNlRGVmYXVsdD86IGJvb2xlYW4sXG4pID0+IHtcbiAgY29uc3QgcmVtaW5kZXJWYWx1ZVRvVXBzZXJ0OiBhbnkgPSB7XG4gICAgaWQ6IHV1aWQoKSxcbiAgICB1c2VySWQsXG4gICAgZXZlbnRJZCxcbiAgICBkZWxldGVkOiBmYWxzZSxcbiAgICB1cGRhdGVkQXQ6IGRheWpzKCkudG9JU09TdHJpbmcoKSxcbiAgICBjcmVhdGVkRGF0ZTogZGF5anMoKS50b0lTT1N0cmluZygpXG4gIH1cblxuICAvKipcbiAgICogIHJlbWluZGVyRGF0ZSxcbiAgICB0aW1lem9uZSxcbiAgICBtaW51dGVzLFxuICAgIHVzZURlZmF1bHQsXG4gICAqL1xuICBpZiAocmVtaW5kZXJEYXRlKSB7XG4gICAgcmVtaW5kZXJWYWx1ZVRvVXBzZXJ0LnJlbWluZGVyRGF0ZSA9IHJlbWluZGVyRGF0ZVxuICB9XG5cbiAgaWYgKHRpbWV6b25lKSB7XG4gICAgcmVtaW5kZXJWYWx1ZVRvVXBzZXJ0LnRpbWV6b25lID0gdGltZXpvbmVcbiAgfVxuXG4gIGlmIChtaW51dGVzKSB7XG4gICAgcmVtaW5kZXJWYWx1ZVRvVXBzZXJ0Lm1pbnV0ZXMgPSBtaW51dGVzXG4gIH1cblxuICBpZiAodXNlRGVmYXVsdCAhPT0gdW5kZWZpbmVkKSB7XG4gICAgcmVtaW5kZXJWYWx1ZVRvVXBzZXJ0LnVzZURlZmF1bHQgPSB1c2VEZWZhdWx0XG4gIH1cblxuICByZXR1cm4gcmVtaW5kZXJWYWx1ZVRvVXBzZXJ0XG59XG5cbmV4cG9ydCBjb25zdCBjcmVhdGVSZW1pbmRlcnNGb3JFdmVudCA9IGFzeW5jIChcbiAgY2xpZW50OiBBcG9sbG9DbGllbnQ8Tm9ybWFsaXplZENhY2hlT2JqZWN0PixcbiAgcmVtaW5kZXJWYWx1ZXNUb1Vwc2VydDogUmVtaW5kZXJUeXBlW10sXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zb2xlLmxvZyhyZW1pbmRlclZhbHVlc1RvVXBzZXJ0LCAnIHJlbWluZGVyVmFsdWVzVG9VcHNlcnQgaW5zaWRlIGNyZWF0ZVJlbWluZGVyc0ZvckV2ZW50JylcbiAgICAvLyBBU1NVTVBUSU9OOiBBIGN1c3RvbSBtdXRhdGlvbiAnYnVsa1Vwc2VydFJlbWluZGVycycgaXMgZGVmaW5lZCBpbiBQb3N0R3JhcGhpbGVcbiAgICBjb25zdCB1cHNlcnRSZW1pbmRlciA9IGdxbGBcbiAgICBtdXRhdGlvbiBCdWxrVXBzZXJ0UmVtaW5kZXJzKCRyZW1pbmRlcnM6IFtSZW1pbmRlcklucHV0IV0hKSB7XG4gICAgICBidWxrVXBzZXJ0UmVtaW5kZXJzKGlucHV0OiB7IHJlbWluZGVyczogJHJlbWluZGVycyB9KSB7XG4gICAgICAgICMgQXNzdW1pbmcgdGhlIGN1c3RvbSBmdW5jdGlvbiByZXR1cm5zIGEgbGlzdCBvZiB0aGUgdXBzZXJ0ZWQgcmVtaW5kZXJzXG4gICAgICAgIHJlc3VsdHM6IHJlbWluZGVycyB7ICMgT3Igc2ltaWxhciwgZGVwZW5kaW5nIG9uIFBHIGZ1bmN0aW9uIGFuZCBQb3N0R3JhcGhpbGUgc2NoZW1hXG4gICAgICAgICAgaWRcbiAgICAgICAgICByZW1pbmRlckRhdGVcbiAgICAgICAgICBldmVudElkXG4gICAgICAgICAgdGltZXpvbmVcbiAgICAgICAgICBtZXRob2RcbiAgICAgICAgICBtaW51dGVzXG4gICAgICAgICAgdXNlRGVmYXVsdFxuICAgICAgICAgIGRlbGV0ZWRcbiAgICAgICAgICBjcmVhdGVkRGF0ZVxuICAgICAgICAgIHVwZGF0ZWRBdFxuICAgICAgICAgIHVzZXJJZFxuICAgICAgICB9XG4gICAgICAgICMgYWZmZWN0ZWRDb3VudCAjIElmIHRoZSBmdW5jdGlvbiByZXR1cm5zIGEgY291bnRcbiAgICAgIH1cbiAgICB9XG4gIGBcbiAgICAvLyBBZGp1c3QgZ2VuZXJpYyB0eXBlIGZvciBjbGllbnQubXV0YXRlIGJhc2VkIG9uIGFjdHVhbCBQb3N0R3JhcGhpbGUgbXV0YXRpb24gcGF5bG9hZFxuICAgIGNvbnN0IHJlc3VsdHNEYXRhID0gKGF3YWl0IGNsaWVudC5tdXRhdGU8eyBidWxrVXBzZXJ0UmVtaW5kZXJzOiB7IHJlc3VsdHM6IFJlbWluZGVyVHlwZVtdIH0gfT4oe1xuICAgICAgbXV0YXRpb246IHVwc2VydFJlbWluZGVyLFxuICAgICAgdmFyaWFibGVzOiB7XG4gICAgICAgIHJlbWluZGVyczogcmVtaW5kZXJWYWx1ZXNUb1Vwc2VydCxcbiAgICAgIH0sXG4gICAgICB1cGRhdGUoY2FjaGUsIHsgZGF0YSB9KSB7XG4gICAgICAgIGNvbnN0IHVwc2VydGVkUmVtaW5kZXJzID0gZGF0YT8uYnVsa1Vwc2VydFJlbWluZGVycz8ucmVzdWx0cztcbiAgICAgICAgaWYgKHVwc2VydGVkUmVtaW5kZXJzICYmIHVwc2VydGVkUmVtaW5kZXJzLmxlbmd0aCA+IDApIHtcbiAgICAgICAgICBjb25zb2xlLmxvZygnYnVsa1Vwc2VydFJlbWluZGVycyByZXN1bHRzJywgdXBzZXJ0ZWRSZW1pbmRlcnMpO1xuXG4gICAgICAgICAgLy8gVGhlIG9yaWdpbmFsIGNhY2hlIGxvZ2ljIHdhcyBtb2RpZnlpbmcgYSByb290IGZpZWxkICdSZW1pbmRlcicuXG4gICAgICAgICAgLy8gVGhpcyBpcyBsZXNzIGNvbW1vbiB3aXRoIFBvc3RHcmFwaGlsZSB3aGljaCB1c3VhbGx5IHVzZXMgY29ubmVjdGlvbiB0eXBlcyBsaWtlICdhbGxSZW1pbmRlcnMnLlxuICAgICAgICAgIC8vIFRoaXMgcGFydCBpcyBoaWdobHkgZGVwZW5kZW50IG9uIHlvdXIgYWN0dWFsIHF1ZXJpZXMgYW5kIFBvc3RHcmFwaGlsZSBzY2hlbWEuXG4gICAgICAgICAgLy8gSXQgd2lsbCBuZWVkIHRvIGJlIHZlcmlmaWVkIGFuZCBsaWtlbHkgYWRqdXN0ZWQuXG4gICAgICAgICAgY2FjaGUubW9kaWZ5KHtcbiAgICAgICAgICAgIGZpZWxkczoge1xuICAgICAgICAgICAgICAvLyBUaGlzIGZpZWxkIG5hbWUgJ1JlbWluZGVyJyBpcyBsaWtlbHkgaW5jb3JyZWN0IGZvciBQb3N0R3JhcGhpbGUuXG4gICAgICAgICAgICAgIC8vIEl0IHdvdWxkIHR5cGljYWxseSBiZSAnYWxsUmVtaW5kZXJzJyBvciBhIHNwZWNpZmljIHF1ZXJ5IG5hbWUuXG4gICAgICAgICAgICAgIFJlbWluZGVyOiAoZXhpc3RpbmdSZW1pbmRlcnMgPSBbXSkgPT4geyAvLyBQbGFjZWhvbGRlciBmb3IgZXhpc3RpbmcgY2FjaGUgdXBkYXRlIGxvZ2ljXG4gICAgICAgICAgICAgICAgY29uc3QgbmV3UmVtaW5kZXJSZWZzID0gdXBzZXJ0ZWRSZW1pbmRlcnMubWFwKChjKSA9PlxuICAgICAgICAgICAgICAgICAgY2FjaGUud3JpdGVGcmFnbWVudCh7XG4gICAgICAgICAgICAgICAgICAgIGRhdGE6IGMsXG4gICAgICAgICAgICAgICAgICAgIGZyYWdtZW50OiBncWxgXG4gICAgICAgICAgICAgICAgICAgICAgZnJhZ21lbnQgTmV3UmVtaW5kZXIgb24gUmVtaW5kZXIge1xuICAgICAgICAgICAgICAgICAgICAgICAgIyBUeXBlIG5hbWUgJ1JlbWluZGVyJyBzaG91bGQgYmUgY2hlY2tlZFxuICAgICAgICAgICAgICAgICAgICAgICAgaWRcbiAgICAgICAgICAgICAgICAgICAgICAgIHJlbWluZGVyRGF0ZVxuICAgICAgICAgICAgICAgICAgICAgICAgZXZlbnRJZFxuICAgICAgICAgICAgICAgICAgICAgICAgdGltZXpvbmVcbiAgICAgICAgICAgICAgICAgICAgICAgIG1ldGhvZFxuICAgICAgICAgICAgICAgICAgICAgICAgbWludXRlc1xuICAgICAgICAgICAgICAgICAgICAgICAgdXNlRGVmYXVsdFxuICAgICAgICAgICAgICAgICAgICAgICAgZGVsZXRlZFxuICAgICAgICAgICAgICAgICAgICAgICAgY3JlYXRlZERhdGVcbiAgICAgICAgICAgICAgICAgICAgICAgIHVwZGF0ZWRBdFxuICAgICAgICAgICAgICAgICAgICAgICAgdXNlcklkXG4gICAgICAgICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgICAgICAgICBgLFxuICAgICAgICAgICAgICAgICAgfSksXG4gICAgICAgICAgICAgICAgKTtcbiAgICAgICAgICAgICAgICByZXR1cm4gWy4uLmV4aXN0aW5nUmVtaW5kZXJzLCAuLi5uZXdSZW1pbmRlclJlZnNdO1xuICAgICAgICAgICAgICB9LFxuICAgICAgICAgICAgfSxcbiAgICAgICAgICB9KTtcbiAgICAgICAgfVxuICAgICAgfSxcbiAgICB9KTtcblxuICAgIGNvbnNvbGUubG9nKHJlc3VsdHNEYXRhLCAnIHJlc3VsdHMgaW5zaWRlIGNyZWF0ZVJlbWluZGVyc0ZvckV2ZW50Jyk7XG4gICAgcmV0dXJuIHJlc3VsdHNEYXRhO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyBlcnJvciBjcmVhdGluZyByZW1pbmRlcnMnKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IGNyZWF0ZVJlbWluZGVyRm9yRXZlbnQgPSBhc3luYyAoXG4gIGNsaWVudDogQXBvbGxvQ2xpZW50PE5vcm1hbGl6ZWRDYWNoZU9iamVjdD4sXG4gIHVzZXJJZDogc3RyaW5nLFxuICBldmVudElkOiBzdHJpbmcsXG4gIHJlbWluZGVyRGF0ZT86IHN0cmluZyxcbiAgdGltZXpvbmU/OiBzdHJpbmcsXG4gIG1pbnV0ZXM/OiBudW1iZXIsXG4gIHVzZURlZmF1bHQ/OiBib29sZWFuLFxuKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3QgcmVtaW5kZXJWYWx1ZVRvVXBzZXJ0OiBhbnkgPSB7XG4gICAgICBpZDogdXVpZCgpLFxuICAgICAgdXNlcklkLFxuICAgICAgZXZlbnRJZCxcbiAgICAgIGRlbGV0ZWQ6IGZhbHNlLFxuICAgICAgdXBkYXRlZEF0OiBkYXlqcygpLnRvSVNPU3RyaW5nKCksXG4gICAgICBjcmVhdGVkRGF0ZTogZGF5anMoKS50b0lTT1N0cmluZygpLFxuICAgIH07XG5cbiAgICAvKipcbiAgICAgKiAgcmVtaW5kZXJEYXRlLFxuICAgICAgdGltZXpvbmUsXG4gICAgICBtaW51dGVzLFxuICAgICAgdXNlRGVmYXVsdCxcbiAgICAgKi9cbiAgICBpZiAocmVtaW5kZXJEYXRlKSB7XG4gICAgICByZW1pbmRlclZhbHVlVG9VcHNlcnQucmVtaW5kZXJEYXRlID0gcmVtaW5kZXJEYXRlO1xuICAgIH1cblxuICAgIGlmICh0aW1lem9uZSkge1xuICAgICAgcmVtaW5kZXJWYWx1ZVRvVXBzZXJ0LnRpbWV6b25lID0gdGltZXpvbmU7XG4gICAgfVxuXG4gICAgaWYgKG1pbnV0ZXMpIHtcbiAgICAgIHJlbWluZGVyVmFsdWVUb1Vwc2VydC5taW51dGVzID0gbWludXRlcztcbiAgICB9XG5cbiAgICBpZiAodXNlRGVmYXVsdCAhPT0gdW5kZWZpbmVkKSB7XG4gICAgICByZW1pbmRlclZhbHVlVG9VcHNlcnQudXNlRGVmYXVsdCA9IHVzZURlZmF1bHQ7XG4gICAgfVxuXG4gICAgLy8gQVNTVU1QVElPTjogQSBjdXN0b20gbXV0YXRpb24gJ3Vwc2VydFJlbWluZGVyJyBpcyBkZWZpbmVkIGluIFBvc3RHcmFwaGlsZSBmb3Igc2luZ2xlIHVwc2VydFxuICAgIC8vIFRoZSBkeW5hbWljIHVwZGF0ZV9jb2x1bW5zIGxvZ2ljIGlzIG5vdyBoYW5kbGVkIGJ5IHRoZSBQRyBmdW5jdGlvbi5cbiAgICBjb25zdCB1cHNlcnRSZW1pbmRlck11dGF0aW9uID0gZ3FsYFxuICAgICAgbXV0YXRpb24gVXBzZXJ0UmVtaW5kZXIoJHJlbWluZGVyOiBSZW1pbmRlcklucHV0ISkge1xuICAgICAgICB1cHNlcnRSZW1pbmRlcihpbnB1dDogeyByZW1pbmRlcjogJHJlbWluZGVyIH0pIHtcbiAgICAgICAgICAjIE9yIGlucHV0OiAkcmVtaW5kZXIgZGlyZWN0bHksIGRlcGVuZHMgb24gUEcgZnVuY1xuICAgICAgICAgIHJlbWluZGVyIHtcbiAgICAgICAgICAgICMgU3RhbmRhcmQgUG9zdEdyYXBoaWxlIHBheWxvYWRcbiAgICAgICAgICAgIGlkXG4gICAgICAgICAgICByZW1pbmRlckRhdGVcbiAgICAgICAgICAgIGV2ZW50SWRcbiAgICAgICAgICAgIHRpbWV6b25lXG4gICAgICAgICAgICBtZXRob2RcbiAgICAgICAgICAgIG1pbnV0ZXNcbiAgICAgICAgICAgIHVzZURlZmF1bHRcbiAgICAgICAgICAgIGRlbGV0ZWRcbiAgICAgICAgICAgIGNyZWF0ZWREYXRlXG4gICAgICAgICAgICB1cGRhdGVkQXRcbiAgICAgICAgICAgIHVzZXJJZFxuICAgICAgICAgIH1cbiAgICAgICAgfVxuICAgICAgfVxuICAgIGA7XG4gICAgLy8gQWRqdXN0IGdlbmVyaWMgdHlwZSBmb3IgY2xpZW50Lm11dGF0ZSBiYXNlZCBvbiBhY3R1YWwgUG9zdEdyYXBoaWxlIG11dGF0aW9uIHBheWxvYWRcbiAgICBjb25zdCByZXN1bHRzRGF0YSA9IGF3YWl0IGNsaWVudC5tdXRhdGU8e1xuICAgICAgdXBzZXJ0UmVtaW5kZXI6IHsgcmVtaW5kZXI6IFJlbWluZGVyVHlwZSB9O1xuICAgIH0+KHtcbiAgICAgIG11dGF0aW9uOiB1cHNlcnRSZW1pbmRlck11dGF0aW9uLFxuICAgICAgdmFyaWFibGVzOiB7XG4gICAgICAgIHJlbWluZGVyOiByZW1pbmRlclZhbHVlVG9VcHNlcnQsIC8vIFBhc3MgdGhlIHNpbmdsZSBvYmplY3RcbiAgICAgIH0sXG4gICAgICB1cGRhdGUoY2FjaGUsIHsgZGF0YSB9KSB7XG4gICAgICAgIGNvbnN0IHVwc2VydGVkUmVtaW5kZXIgPSBkYXRhPy51cHNlcnRSZW1pbmRlcj8ucmVtaW5kZXI7XG4gICAgICAgIGlmICh1cHNlcnRlZFJlbWluZGVyKSB7XG4gICAgICAgICAgY29uc29sZS5sb2coJ3Vwc2VydFJlbWluZGVyIHJlc3VsdCcsIHVwc2VydGVkUmVtaW5kZXIpO1xuXG4gICAgICAgICAgLy8gU2ltaWxhciBjYWNoZSB1cGRhdGUgY29uc2lkZXJhdGlvbnMgYXMgYWJvdmUuXG4gICAgICAgICAgY2FjaGUubW9kaWZ5KHtcbiAgICAgICAgICAgIGZpZWxkczoge1xuICAgICAgICAgICAgICAvLyBGaWVsZCBuYW1lICdSZW1pbmRlcicgaXMgbGlrZWx5IGluY29ycmVjdCBmb3IgUG9zdEdyYXBoaWxlIGxpc3QgcXVlcmllcy5cbiAgICAgICAgICAgICAgUmVtaW5kZXI6IChleGlzdGluZ1JlbWluZGVycyA9IFtdKSA9PiB7XG4gICAgICAgICAgICAgICAgLy8gUGxhY2Vob2xkZXJcbiAgICAgICAgICAgICAgICAvLyBMb2dpYyB0byB1cGRhdGUgb3IgYWRkIHRoZSBzaW5nbGUgcmVtaW5kZXIgdG8gdGhlIGNhY2hlXG4gICAgICAgICAgICAgICAgY29uc3QgbmV3UmVtaW5kZXJSZWYgPSBjYWNoZS53cml0ZUZyYWdtZW50KHtcbiAgICAgICAgICAgICAgICAgIGRhdGE6IHVwc2VydGVkUmVtaW5kZXIsXG4gICAgICAgICAgICAgICAgICBmcmFnbWVudDogZ3FsYFxuICAgICAgICAgICAgICAgICAgICBmcmFnbWVudCBOZXdTaW5nbGVSZW1pbmRlciBvbiBSZW1pbmRlciB7XG4gICAgICAgICAgICAgICAgICAgICAgIyBUeXBlIG5hbWUgJ1JlbWluZGVyJyBzaG91bGQgYmUgY2hlY2tlZFxuICAgICAgICAgICAgICAgICAgICAgIGlkXG4gICAgICAgICAgICAgICAgICAgICAgcmVtaW5kZXJEYXRlXG4gICAgICAgICAgICAgICAgICAgICAgZXZlbnRJZFxuICAgICAgICAgICAgICAgICAgICAgIHRpbWV6b25lXG4gICAgICAgICAgICAgICAgICAgICAgbWV0aG9kXG4gICAgICAgICAgICAgICAgICAgICAgbWludXRlc1xuICAgICAgICAgICAgICAgICAgICAgIHVzZURlZmF1bHRcbiAgICAgICAgICAgICAgICAgICAgICBkZWxldGVkXG4gICAgICAgICAgICAgICAgICAgICAgY3JlYXRlZERhdGVcbiAgICAgICAgICAgICAgICAgICAgICB1cGRhdGVkQXRcbiAgICAgICAgICAgICAgICAgICAgICB1c2VySWRcbiAgICAgICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgICAgICAgYCxcbiAgICAgICAgICAgICAgICB9KTtcbiAgICAgICAgICAgICAgICByZXR1cm4gWy4uLmV4aXN0aW5nUmVtaW5kZXJzLCBuZXdSZW1pbmRlclJlZl07XG4gICAgICAgICAgICAgIH0sXG4gICAgICAgICAgICB9LFxuICAgICAgICAgIH0pO1xuICAgICAgICB9XG4gICAgICB9LFxuICAgIH0pO1xuXG4gICAgY29uc29sZS5sb2cocmVzdWx0c0RhdGEsICcgcmVzdWx0cyBpbnNpZGUgY3JlYXRlUmVtaW5kZXJGb3JFdmVudCcpO1xuICAgIHJldHVybiByZXN1bHRzRGF0YTtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIGNyZWF0ZSByZW1pbmRlciBmb3IgZXZlbnQnKVxuICB9XG59XG5cbmV4cG9ydCBjb25zdCBsaXN0UmVtaW5kZXJzRm9yRXZlbnQgPSBhc3luYyAoXG4gIGNsaWVudDogQXBvbGxvQ2xpZW50PE5vcm1hbGl6ZWRDYWNoZU9iamVjdD4sXG4gIGV2ZW50SWQ6IHN0cmluZ1xuKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3QgcmVzdWx0cyA9IChhd2FpdCBjbGllbnQucXVlcnk8eyBSZW1pbmRlcjogUmVtaW5kZXJUeXBlW10gfT4oe1xuICAgICAgcXVlcnk6IGxpc3RSZW1pbmRlcnNGb3JFdmVudElkLFxuICAgICAgdmFyaWFibGVzOiB7XG4gICAgICAgIGV2ZW50SWQsXG4gICAgICB9LFxuICAgIH0pKS5kYXRhPy5SZW1pbmRlclxuICAgIGNvbnNvbGUubG9nKHJlc3VsdHMsICcgUmVtaW5kZXIgLSBpbnNpZGUgbGlzdFJlbWluZGVyc0ZvckV2ZW50cycpXG4gICAgcmV0dXJuIHJlc3VsdHNcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIGxpc3QgcmVtaW5kZXJzIGZvciBldmVudCcpXG4gIH1cbn1cbi8qKiBlbmQgKi9cbiJdfQ==