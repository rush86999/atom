"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.getEventWithId = exports.getItemsToRemove = exports.bulkCreateCalendarsInDb = exports.bulkRemoveCalendarsInDb = exports.deleteEventsByCalendarId = exports.deleteGoogleCalendarInDb = exports.upsertGoogleCalendarInDb = exports.upsertCalendar = void 0;
const constants_1 = require("@lib/calendarLib/constants");
const client_1 = require("@apollo/client");
const deleteCalendarById_1 = __importDefault(require("@lib/apollo/gql/deleteCalendarById"));
const deleteEventsByCalendarIdMutation_1 = __importDefault(require("@lib/apollo/gql/deleteEventsByCalendarIdMutation"));
const deleteCalendarsByIds_1 = __importDefault(require("@lib/apollo/gql/deleteCalendarsByIds"));
const getCalendarWithResource_1 = __importDefault(require("@lib/apollo/gql/getCalendarWithResource"));
const getEventById_1 = __importDefault(require("@lib/apollo/gql/getEventById"));
const upsertCalendar = async (client, calendar) => {
    try {
        console.log('upsertCalendar called');
        console.log(calendar, ' calendar inside upsertCalendar');
        const upsertCalendarMutation = (0, client_1.gql) `
        mutation InsertCalendar($calendars: [Calendar_insert_input!]!) {
            insert_Calendar(objects: $calendars, on_conflict: {constraint: Calendar_pkey, update_columns: [
                ${calendar?.title ? 'title,' : ''} 
                ${calendar?.colorId ? 'colorId,' : ''} 
                ${calendar?.account ? 'account,' : ''} 
                ${calendar?.accessLevel ? 'accessLevel,' : ''} 
                ${calendar?.resource ? 'resource,' : ''} 
                ${calendar?.modifiable !== undefined ? 'modifiable,' : ''} 
                ${calendar?.defaultReminders && calendar?.defaultReminders?.length > 0 ? 'defaultReminders,' : ''} 
                ${calendar?.globalPrimary !== undefined ? 'globalPrimary,' : ''} 
                ${calendar?.backgroundColor ? 'backgroundColor,' : ''} 
                ${calendar?.foregroundColor ? 'foregroundColor,' : ''} 
                ${calendar?.deleted !== undefined ? 'deleted,' : ''} 
                ${calendar?.updatedAt ? 'updatedAt,' : ''}
                ${calendar?.pageToken ? 'pageToken,' : ''} 
                ${calendar?.syncToken ? 'syncToken,' : ''} 
            ]}) {
                returning {
                    id
                    title
                    colorId
                    account
                    accessLevel
                    modifiable
                    resource
                    defaultReminders
                    globalPrimary
                    deleted
                    createdDate
                    updatedAt
                    userId
                    foregroundColor
                    backgroundColor
                    pageToken
                    syncToken
                }
                affected_rows
            }
        }
        `;
        let valueToUpsert = {
            id: calendar?.id,
            createdDate: calendar?.createdDate,
            updatedAt: calendar?.updatedAt,
            userId: calendar?.userId,
            deleted: calendar?.deleted,
        };
        if (calendar?.title) {
            valueToUpsert = {
                ...valueToUpsert,
                title: calendar.title,
            };
        }
        if (calendar?.colorId) {
            valueToUpsert = {
                ...valueToUpsert,
                colorId: calendar.colorId,
            };
        }
        if (calendar?.account) {
            valueToUpsert = {
                ...valueToUpsert,
                account: calendar.account,
            };
        }
        if (calendar?.accessLevel) {
            valueToUpsert = {
                ...valueToUpsert,
                accessLevel: calendar.accessLevel,
            };
        }
        if (calendar?.resource) {
            valueToUpsert = {
                ...valueToUpsert,
                resource: calendar.resource,
            };
        }
        if (calendar?.modifiable !== undefined) {
            valueToUpsert = {
                ...valueToUpsert,
                modifiable: calendar.modifiable,
            };
        }
        if (calendar?.defaultReminders && calendar?.defaultReminders?.length > 0) {
            valueToUpsert = {
                ...valueToUpsert,
                defaultReminders: calendar.defaultReminders,
            };
        }
        if (calendar?.globalPrimary !== undefined) {
            valueToUpsert = {
                ...valueToUpsert,
                globalPrimary: calendar.globalPrimary,
            };
        }
        if (calendar?.backgroundColor) {
            valueToUpsert = {
                ...valueToUpsert,
                backgroundColor: calendar.backgroundColor,
            };
        }
        if (calendar?.foregroundColor) {
            valueToUpsert = {
                ...valueToUpsert,
                foregroundColor: calendar.foregroundColor,
            };
        }
        if (calendar?.deleted !== undefined) {
            valueToUpsert = {
                ...valueToUpsert,
                deleted: calendar.deleted,
            };
        }
        if (calendar?.updatedAt) {
            valueToUpsert = {
                ...valueToUpsert,
                updatedAt: calendar.updatedAt,
            };
        }
        if (calendar?.pageToken) {
            valueToUpsert = {
                ...valueToUpsert,
                pageToken: calendar.pageToken,
            };
        }
        if (calendar?.syncToken) {
            valueToUpsert = {
                ...valueToUpsert,
                syncToken: calendar.syncToken,
            };
        }
        const { data } = await client.mutate({
            mutation: upsertCalendarMutation,
            variables: {
                calendars: [valueToUpsert],
            },
            update(cache, { data }) {
                if (data?.insert_Calendar?.affected_rows &&
                    data?.insert_Calendar?.affected_rows > 0) {
                    console.log('insert_Calendar?.affected_rows', data);
                }
                cache.modify({
                    fields: {
                        Calendar(existingCalendars = []) {
                            const newCalendarRef = cache.writeFragment({
                                data: data?.insert_Calendar?.returning?.[0],
                                fragment: (0, client_1.gql) `
                  fragment NewCalendar on Calendar {
                    id
                    title
                    colorId
                    account
                    accessLevel
                    modifiable
                    resource
                    defaultReminders
                    globalPrimary
                    deleted
                    createdDate
                    updatedAt
                    userId
                    foregroundColor
                    backgroundColor
                    pageToken
                    syncToken
                  }
                `,
                            });
                            const filteredCalendars = existingCalendars?.filter((e) => e?.id !== data?.insert_Calendar?.returning?.[0]?.id) || [];
                            console.log(filteredCalendars, ' filteredCalendars inside atomicUpsertCalendarInDb');
                            if (filteredCalendars?.length > 0) {
                                return filteredCalendars.concat([newCalendarRef]);
                            }
                            return [newCalendarRef];
                        },
                    },
                });
            },
        });
        console.log(data && data.insert_Calendar.returning[0], ' post upsertCalendar');
        return data && data.insert_Calendar.returning[0];
    }
    catch (error) {
        console.log(error, ' error inside upsertCalendar');
    }
};
exports.upsertCalendar = upsertCalendar;
const upsertGoogleCalendarInDb = async (client, calendarItemResponse, userId) => {
    try {
        console.log(userId, ' userId inside upsertGoogleCalendarInDb');
        const calendar = {
            id: calendarItemResponse.id,
            title: calendarItemResponse.summary,
            backgroundColor: calendarItemResponse?.backgroundColor,
            foregroundColor: calendarItemResponse?.foregroundColor,
            colorId: calendarItemResponse?.colorId,
            resource: constants_1.googleResourceName,
            accessLevel: calendarItemResponse?.accessRole,
            defaultReminders: calendarItemResponse?.defaultReminders,
            modifiable: true,
            deleted: false,
            createdDate: new Date().toISOString(),
            updatedAt: new Date().toISOString(),
            userId,
        };
        return (0, exports.upsertCalendar)(client, calendar);
    }
    catch (e) {
        console.log(e, 'createCalendarInDb');
    }
};
exports.upsertGoogleCalendarInDb = upsertGoogleCalendarInDb;
const deleteGoogleCalendarInDb = async (client, calendarId) => {
    try {
        await client.mutate({
            mutation: deleteCalendarById_1.default,
            variables: {
                id: calendarId,
            },
        });
        console.log('deleted calendar in db');
    }
    catch (e) {
        console.log(e, 'deleteGoogleCalendarInDb');
    }
};
exports.deleteGoogleCalendarInDb = deleteGoogleCalendarInDb;
const deleteEventsByCalendarId = async (client, calendarId) => {
    try {
        const { data } = await client.mutate({
            mutation: deleteEventsByCalendarIdMutation_1.default,
            variables: {
                calendarId,
            },
        });
        console.log(data?.delete_Event?.affected_rows, ' deleted events in db');
    }
    catch (e) {
        console.log(e, ' unable to delete event by calendarId');
    }
};
exports.deleteEventsByCalendarId = deleteEventsByCalendarId;
const bulkRemoveCalendarsInDb = async (client, items) => {
    try {
        const { data } = await client.mutate({
            mutation: deleteCalendarsByIds_1.default,
            variables: {
                ids: items,
            },
        });
        console.log(data?.delete_Calendar?.affected_rows, ' successfully removed bulk calendar items');
    }
    catch (e) {
        console.log(e, ' unable to bulk remove');
    }
};
exports.bulkRemoveCalendarsInDb = bulkRemoveCalendarsInDb;
const bulkCreateCalendarsInDb = async (client, items) => {
    try {
        const upsertCalendarMutation = (0, client_1.gql) `
      mutation InsertCalendar($calendars: [Calendar_insert_input!]!) {
        insert_Calendar(
          objects: $calendars
          on_conflict: {
            constraint: Calendar_pkey
            update_columns: [
              title
              colorId
              account
              accessLevel
              resource
              modifiable
              defaultReminders
              globalPrimary
              backgroundColor
              foregroundColor
              deleted
              updatedAt
              pageToken
              syncToken
            ]
          }
        ) {
          affected_rows
        }
      }
    `;
        const { data } = await client.mutate({
            mutation: upsertCalendarMutation,
            variables: {
                calendars: items,
            },
        });
        console.log(data.insert_Calendar.affected_rows, ' successfully bulk inserted calendar items');
        return data.insert_Calendar.affected_rows;
    }
    catch (e) {
        console.log(e, ' unable to bulk create calendars in db');
    }
};
exports.bulkCreateCalendarsInDb = bulkCreateCalendarsInDb;
const getItemsToRemove = async (client, userId, resource) => {
    try {
        return (await client.query({
            query: getCalendarWithResource_1.default,
            variables: {
                userId,
                resource,
            },
        })).data?.Calendar;
    }
    catch (e) {
        console.log(e, ' unable to get items to remove for calendar');
    }
};
exports.getItemsToRemove = getItemsToRemove;
const getEventWithId = async (client, eventId) => {
    try {
        if (!eventId) {
            console.log('no eventId inside getEventWithId');
        }
        return (await client.query({
            query: getEventById_1.default,
            variables: {
                id: eventId,
            },
        })).data?.Event_by_pk;
    }
    catch (e) {
        console.log(e, ' unable to get event with id');
    }
};
exports.getEventWithId = getEventWithId;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiY2FsZW5kYXJEYkhlbHBlci5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImNhbGVuZGFyRGJIZWxwZXIudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7Ozs7O0FBRUEsMERBQWdFO0FBRWhFLDJDQUEwRTtBQUMxRSw0RkFBb0U7QUFDcEUsd0hBQWdHO0FBQ2hHLGdHQUF3RTtBQUN4RSxzR0FBOEU7QUFFOUUsZ0ZBQXdEO0FBRWpELE1BQU0sY0FBYyxHQUFHLEtBQUssRUFDakMsTUFBMkMsRUFDM0MsUUFBc0IsRUFDdEIsRUFBRTtJQUNGLElBQUksQ0FBQztRQUNILE9BQU8sQ0FBQyxHQUFHLENBQUMsdUJBQXVCLENBQUMsQ0FBQztRQUNyQyxPQUFPLENBQUMsR0FBRyxDQUFDLFFBQVEsRUFBRSxpQ0FBaUMsQ0FBQyxDQUFDO1FBQ3pELE1BQU0sc0JBQXNCLEdBQUcsSUFBQSxZQUFHLEVBQUE7OztrQkFHcEIsUUFBUSxFQUFFLEtBQUssQ0FBQyxDQUFDLENBQUMsUUFBUSxDQUFDLENBQUMsQ0FBQyxFQUFFO2tCQUMvQixRQUFRLEVBQUUsT0FBTyxDQUFDLENBQUMsQ0FBQyxVQUFVLENBQUMsQ0FBQyxDQUFDLEVBQUU7a0JBQ25DLFFBQVEsRUFBRSxPQUFPLENBQUMsQ0FBQyxDQUFDLFVBQVUsQ0FBQyxDQUFDLENBQUMsRUFBRTtrQkFDbkMsUUFBUSxFQUFFLFdBQVcsQ0FBQyxDQUFDLENBQUMsY0FBYyxDQUFDLENBQUMsQ0FBQyxFQUFFO2tCQUMzQyxRQUFRLEVBQUUsUUFBUSxDQUFDLENBQUMsQ0FBQyxXQUFXLENBQUMsQ0FBQyxDQUFDLEVBQUU7a0JBQ3JDLFFBQVEsRUFBRSxVQUFVLEtBQUssU0FBUyxDQUFDLENBQUMsQ0FBQyxhQUFhLENBQUMsQ0FBQyxDQUFDLEVBQUU7a0JBQ3ZELFFBQVEsRUFBRSxnQkFBZ0IsSUFBSSxRQUFRLEVBQUUsZ0JBQWdCLEVBQUUsTUFBTSxHQUFHLENBQUMsQ0FBQyxDQUFDLENBQUMsbUJBQW1CLENBQUMsQ0FBQyxDQUFDLEVBQUU7a0JBQy9GLFFBQVEsRUFBRSxhQUFhLEtBQUssU0FBUyxDQUFDLENBQUMsQ0FBQyxnQkFBZ0IsQ0FBQyxDQUFDLENBQUMsRUFBRTtrQkFDN0QsUUFBUSxFQUFFLGVBQWUsQ0FBQyxDQUFDLENBQUMsa0JBQWtCLENBQUMsQ0FBQyxDQUFDLEVBQUU7a0JBQ25ELFFBQVEsRUFBRSxlQUFlLENBQUMsQ0FBQyxDQUFDLGtCQUFrQixDQUFDLENBQUMsQ0FBQyxFQUFFO2tCQUNuRCxRQUFRLEVBQUUsT0FBTyxLQUFLLFNBQVMsQ0FBQyxDQUFDLENBQUMsVUFBVSxDQUFDLENBQUMsQ0FBQyxFQUFFO2tCQUNqRCxRQUFRLEVBQUUsU0FBUyxDQUFDLENBQUMsQ0FBQyxZQUFZLENBQUMsQ0FBQyxDQUFDLEVBQUU7a0JBQ3ZDLFFBQVEsRUFBRSxTQUFTLENBQUMsQ0FBQyxDQUFDLFlBQVksQ0FBQyxDQUFDLENBQUMsRUFBRTtrQkFDdkMsUUFBUSxFQUFFLFNBQVMsQ0FBQyxDQUFDLENBQUMsWUFBWSxDQUFDLENBQUMsQ0FBQyxFQUFFOzs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7U0F3QmhELENBQUM7UUFDTixJQUFJLGFBQWEsR0FBUTtZQUN2QixFQUFFLEVBQUUsUUFBUSxFQUFFLEVBQUU7WUFDaEIsV0FBVyxFQUFFLFFBQVEsRUFBRSxXQUFXO1lBQ2xDLFNBQVMsRUFBRSxRQUFRLEVBQUUsU0FBUztZQUM5QixNQUFNLEVBQUUsUUFBUSxFQUFFLE1BQU07WUFDeEIsT0FBTyxFQUFFLFFBQVEsRUFBRSxPQUFPO1NBQzNCLENBQUM7UUFFRixJQUFJLFFBQVEsRUFBRSxLQUFLLEVBQUUsQ0FBQztZQUNwQixhQUFhLEdBQUc7Z0JBQ2QsR0FBRyxhQUFhO2dCQUNoQixLQUFLLEVBQUUsUUFBUSxDQUFDLEtBQUs7YUFDdEIsQ0FBQztRQUNKLENBQUM7UUFFRCxJQUFJLFFBQVEsRUFBRSxPQUFPLEVBQUUsQ0FBQztZQUN0QixhQUFhLEdBQUc7Z0JBQ2QsR0FBRyxhQUFhO2dCQUNoQixPQUFPLEVBQUUsUUFBUSxDQUFDLE9BQU87YUFDMUIsQ0FBQztRQUNKLENBQUM7UUFFRCxJQUFJLFFBQVEsRUFBRSxPQUFPLEVBQUUsQ0FBQztZQUN0QixhQUFhLEdBQUc7Z0JBQ2QsR0FBRyxhQUFhO2dCQUNoQixPQUFPLEVBQUUsUUFBUSxDQUFDLE9BQU87YUFDMUIsQ0FBQztRQUNKLENBQUM7UUFFRCxJQUFJLFFBQVEsRUFBRSxXQUFXLEVBQUUsQ0FBQztZQUMxQixhQUFhLEdBQUc7Z0JBQ2QsR0FBRyxhQUFhO2dCQUNoQixXQUFXLEVBQUUsUUFBUSxDQUFDLFdBQVc7YUFDbEMsQ0FBQztRQUNKLENBQUM7UUFFRCxJQUFJLFFBQVEsRUFBRSxRQUFRLEVBQUUsQ0FBQztZQUN2QixhQUFhLEdBQUc7Z0JBQ2QsR0FBRyxhQUFhO2dCQUNoQixRQUFRLEVBQUUsUUFBUSxDQUFDLFFBQVE7YUFDNUIsQ0FBQztRQUNKLENBQUM7UUFFRCxJQUFJLFFBQVEsRUFBRSxVQUFVLEtBQUssU0FBUyxFQUFFLENBQUM7WUFDdkMsYUFBYSxHQUFHO2dCQUNkLEdBQUcsYUFBYTtnQkFDaEIsVUFBVSxFQUFFLFFBQVEsQ0FBQyxVQUFVO2FBQ2hDLENBQUM7UUFDSixDQUFDO1FBRUQsSUFBSSxRQUFRLEVBQUUsZ0JBQWdCLElBQUksUUFBUSxFQUFFLGdCQUFnQixFQUFFLE1BQU0sR0FBRyxDQUFDLEVBQUUsQ0FBQztZQUN6RSxhQUFhLEdBQUc7Z0JBQ2QsR0FBRyxhQUFhO2dCQUNoQixnQkFBZ0IsRUFBRSxRQUFRLENBQUMsZ0JBQWdCO2FBQzVDLENBQUM7UUFDSixDQUFDO1FBRUQsSUFBSSxRQUFRLEVBQUUsYUFBYSxLQUFLLFNBQVMsRUFBRSxDQUFDO1lBQzFDLGFBQWEsR0FBRztnQkFDZCxHQUFHLGFBQWE7Z0JBQ2hCLGFBQWEsRUFBRSxRQUFRLENBQUMsYUFBYTthQUN0QyxDQUFDO1FBQ0osQ0FBQztRQUVELElBQUksUUFBUSxFQUFFLGVBQWUsRUFBRSxDQUFDO1lBQzlCLGFBQWEsR0FBRztnQkFDZCxHQUFHLGFBQWE7Z0JBQ2hCLGVBQWUsRUFBRSxRQUFRLENBQUMsZUFBZTthQUMxQyxDQUFDO1FBQ0osQ0FBQztRQUVELElBQUksUUFBUSxFQUFFLGVBQWUsRUFBRSxDQUFDO1lBQzlCLGFBQWEsR0FBRztnQkFDZCxHQUFHLGFBQWE7Z0JBQ2hCLGVBQWUsRUFBRSxRQUFRLENBQUMsZUFBZTthQUMxQyxDQUFDO1FBQ0osQ0FBQztRQUVELElBQUksUUFBUSxFQUFFLE9BQU8sS0FBSyxTQUFTLEVBQUUsQ0FBQztZQUNwQyxhQUFhLEdBQUc7Z0JBQ2QsR0FBRyxhQUFhO2dCQUNoQixPQUFPLEVBQUUsUUFBUSxDQUFDLE9BQU87YUFDMUIsQ0FBQztRQUNKLENBQUM7UUFFRCxJQUFJLFFBQVEsRUFBRSxTQUFTLEVBQUUsQ0FBQztZQUN4QixhQUFhLEdBQUc7Z0JBQ2QsR0FBRyxhQUFhO2dCQUNoQixTQUFTLEVBQUUsUUFBUSxDQUFDLFNBQVM7YUFDOUIsQ0FBQztRQUNKLENBQUM7UUFFRCxJQUFJLFFBQVEsRUFBRSxTQUFTLEVBQUUsQ0FBQztZQUN4QixhQUFhLEdBQUc7Z0JBQ2QsR0FBRyxhQUFhO2dCQUNoQixTQUFTLEVBQUUsUUFBUSxDQUFDLFNBQVM7YUFDOUIsQ0FBQztRQUNKLENBQUM7UUFFRCxJQUFJLFFBQVEsRUFBRSxTQUFTLEVBQUUsQ0FBQztZQUN4QixhQUFhLEdBQUc7Z0JBQ2QsR0FBRyxhQUFhO2dCQUNoQixTQUFTLEVBQUUsUUFBUSxDQUFDLFNBQVM7YUFDOUIsQ0FBQztRQUNKLENBQUM7UUFFRCxNQUFNLEVBQUUsSUFBSSxFQUFFLEdBQUcsTUFBTSxNQUFNLENBQUMsTUFBTSxDQUVqQztZQUNELFFBQVEsRUFBRSxzQkFBc0I7WUFDaEMsU0FBUyxFQUFFO2dCQUNULFNBQVMsRUFBRSxDQUFDLGFBQWEsQ0FBQzthQUMzQjtZQUNELE1BQU0sQ0FBQyxLQUFLLEVBQUUsRUFBRSxJQUFJLEVBQUU7Z0JBQ3BCLElBQ0UsSUFBSSxFQUFFLGVBQWUsRUFBRSxhQUFhO29CQUNwQyxJQUFJLEVBQUUsZUFBZSxFQUFFLGFBQWEsR0FBRyxDQUFDLEVBQ3hDLENBQUM7b0JBQ0QsT0FBTyxDQUFDLEdBQUcsQ0FBQyxnQ0FBZ0MsRUFBRSxJQUFJLENBQUMsQ0FBQztnQkFDdEQsQ0FBQztnQkFFRCxLQUFLLENBQUMsTUFBTSxDQUFDO29CQUNYLE1BQU0sRUFBRTt3QkFDTixRQUFRLENBQUMsaUJBQWlCLEdBQUcsRUFBRTs0QkFDN0IsTUFBTSxjQUFjLEdBQUcsS0FBSyxDQUFDLGFBQWEsQ0FBQztnQ0FDekMsSUFBSSxFQUFFLElBQUksRUFBRSxlQUFlLEVBQUUsU0FBUyxFQUFFLENBQUMsQ0FBQyxDQUFDO2dDQUMzQyxRQUFRLEVBQUUsSUFBQSxZQUFHLEVBQUE7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7O2lCQW9CWjs2QkFDRixDQUFDLENBQUM7NEJBQ0gsTUFBTSxpQkFBaUIsR0FDckIsaUJBQWlCLEVBQUUsTUFBTSxDQUN2QixDQUFDLENBQWUsRUFBRSxFQUFFLENBQ2xCLENBQUMsRUFBRSxFQUFFLEtBQUssSUFBSSxFQUFFLGVBQWUsRUFBRSxTQUFTLEVBQUUsQ0FBQyxDQUFDLENBQUMsRUFBRSxFQUFFLENBQ3RELElBQUksRUFBRSxDQUFDOzRCQUNWLE9BQU8sQ0FBQyxHQUFHLENBQ1QsaUJBQWlCLEVBQ2pCLG9EQUFvRCxDQUNyRCxDQUFDOzRCQUNGLElBQUksaUJBQWlCLEVBQUUsTUFBTSxHQUFHLENBQUMsRUFBRSxDQUFDO2dDQUNsQyxPQUFPLGlCQUFpQixDQUFDLE1BQU0sQ0FBQyxDQUFDLGNBQWMsQ0FBQyxDQUFDLENBQUM7NEJBQ3BELENBQUM7NEJBQ0QsT0FBTyxDQUFDLGNBQWMsQ0FBQyxDQUFDO3dCQUMxQixDQUFDO3FCQUNGO2lCQUNGLENBQUMsQ0FBQztZQUNMLENBQUM7U0FDRixDQUFDLENBQUM7UUFDSCxPQUFPLENBQUMsR0FBRyxDQUNULElBQUksSUFBSSxJQUFJLENBQUMsZUFBZSxDQUFDLFNBQVMsQ0FBQyxDQUFDLENBQUMsRUFDekMsc0JBQXNCLENBQ3ZCLENBQUM7UUFDRixPQUFPLElBQUksSUFBSSxJQUFJLENBQUMsZUFBZSxDQUFDLFNBQVMsQ0FBQyxDQUFDLENBQUMsQ0FBQztJQUNuRCxDQUFDO0lBQUMsT0FBTyxLQUFLLEVBQUUsQ0FBQztRQUNmLE9BQU8sQ0FBQyxHQUFHLENBQUMsS0FBSyxFQUFFLDhCQUE4QixDQUFDLENBQUM7SUFDckQsQ0FBQztBQUNILENBQUMsQ0FBQztBQTlOVyxRQUFBLGNBQWMsa0JBOE56QjtBQUNLLE1BQU0sd0JBQXdCLEdBQUcsS0FBSyxFQUMzQyxNQUEyQyxFQUMzQyxvQkFBa0QsRUFDbEQsTUFBYyxFQUNkLEVBQUU7SUFDRixJQUFJLENBQUM7UUFDSCxPQUFPLENBQUMsR0FBRyxDQUFDLE1BQU0sRUFBRSx5Q0FBeUMsQ0FBQyxDQUFDO1FBQy9ELE1BQU0sUUFBUSxHQUFpQjtZQUM3QixFQUFFLEVBQUUsb0JBQW9CLENBQUMsRUFBRTtZQUMzQixLQUFLLEVBQUUsb0JBQW9CLENBQUMsT0FBTztZQUNuQyxlQUFlLEVBQUUsb0JBQW9CLEVBQUUsZUFBZTtZQUN0RCxlQUFlLEVBQUUsb0JBQW9CLEVBQUUsZUFBZTtZQUN0RCxPQUFPLEVBQUUsb0JBQW9CLEVBQUUsT0FBTztZQUN0QyxRQUFRLEVBQUUsOEJBQWtCO1lBQzVCLFdBQVcsRUFBRSxvQkFBb0IsRUFBRSxVQUFVO1lBQzdDLGdCQUFnQixFQUFFLG9CQUFvQixFQUFFLGdCQUFnQjtZQUN4RCxVQUFVLEVBQUUsSUFBSTtZQUNoQixPQUFPLEVBQUUsS0FBSztZQUNkLFdBQVcsRUFBRSxJQUFJLElBQUksRUFBRSxDQUFDLFdBQVcsRUFBRTtZQUNyQyxTQUFTLEVBQUUsSUFBSSxJQUFJLEVBQUUsQ0FBQyxXQUFXLEVBQUU7WUFDbkMsTUFBTTtTQUNQLENBQUM7UUFFRixPQUFPLElBQUEsc0JBQWMsRUFBQyxNQUFNLEVBQUUsUUFBUSxDQUFDLENBQUM7SUFDMUMsQ0FBQztJQUFDLE9BQU8sQ0FBQyxFQUFFLENBQUM7UUFDWCxPQUFPLENBQUMsR0FBRyxDQUFDLENBQUMsRUFBRSxvQkFBb0IsQ0FBQyxDQUFDO0lBQ3ZDLENBQUM7QUFDSCxDQUFDLENBQUM7QUEzQlcsUUFBQSx3QkFBd0IsNEJBMkJuQztBQUVLLE1BQU0sd0JBQXdCLEdBQUcsS0FBSyxFQUMzQyxNQUEyQyxFQUMzQyxVQUFrQixFQUNsQixFQUFFO0lBQ0YsSUFBSSxDQUFDO1FBQ0gsTUFBTSxNQUFNLENBQUMsTUFBTSxDQUEwQztZQUMzRCxRQUFRLEVBQUUsNEJBQWtCO1lBQzVCLFNBQVMsRUFBRTtnQkFDVCxFQUFFLEVBQUUsVUFBVTthQUNmO1NBQ0YsQ0FBQyxDQUFDO1FBQ0gsT0FBTyxDQUFDLEdBQUcsQ0FBQyx3QkFBd0IsQ0FBQyxDQUFDO0lBQ3hDLENBQUM7SUFBQyxPQUFPLENBQUMsRUFBRSxDQUFDO1FBQ1gsT0FBTyxDQUFDLEdBQUcsQ0FBQyxDQUFDLEVBQUUsMEJBQTBCLENBQUMsQ0FBQztJQUM3QyxDQUFDO0FBQ0gsQ0FBQyxDQUFDO0FBZlcsUUFBQSx3QkFBd0IsNEJBZW5DO0FBRUssTUFBTSx3QkFBd0IsR0FBRyxLQUFLLEVBQzNDLE1BQTJDLEVBQzNDLFVBQWtCLEVBQ2xCLEVBQUU7SUFDRixJQUFJLENBQUM7UUFDSCxNQUFNLEVBQUUsSUFBSSxFQUFFLEdBQUcsTUFBTSxNQUFNLENBQUMsTUFBTSxDQUVqQztZQUNELFFBQVEsRUFBRSwwQ0FBZ0M7WUFDMUMsU0FBUyxFQUFFO2dCQUNULFVBQVU7YUFDWDtTQUNGLENBQUMsQ0FBQztRQUVILE9BQU8sQ0FBQyxHQUFHLENBQUMsSUFBSSxFQUFFLFlBQVksRUFBRSxhQUFhLEVBQUUsdUJBQXVCLENBQUMsQ0FBQztJQUMxRSxDQUFDO0lBQUMsT0FBTyxDQUFDLEVBQUUsQ0FBQztRQUNYLE9BQU8sQ0FBQyxHQUFHLENBQUMsQ0FBQyxFQUFFLHVDQUF1QyxDQUFDLENBQUM7SUFDMUQsQ0FBQztBQUNILENBQUMsQ0FBQztBQWxCVyxRQUFBLHdCQUF3Qiw0QkFrQm5DO0FBRUssTUFBTSx1QkFBdUIsR0FBRyxLQUFLLEVBQzFDLE1BQTJDLEVBQzNDLEtBQWUsRUFDZixFQUFFO0lBQ0YsSUFBSSxDQUFDO1FBQ0gsTUFBTSxFQUFFLElBQUksRUFBRSxHQUFHLE1BQU0sTUFBTSxDQUFDLE1BQU0sQ0FFakM7WUFDRCxRQUFRLEVBQUUsOEJBQW9CO1lBQzlCLFNBQVMsRUFBRTtnQkFDVCxHQUFHLEVBQUUsS0FBSzthQUNYO1NBQ0YsQ0FBQyxDQUFDO1FBQ0gsT0FBTyxDQUFDLEdBQUcsQ0FDVCxJQUFJLEVBQUUsZUFBZSxFQUFFLGFBQWEsRUFDcEMsMkNBQTJDLENBQzVDLENBQUM7SUFDSixDQUFDO0lBQUMsT0FBTyxDQUFDLEVBQUUsQ0FBQztRQUNYLE9BQU8sQ0FBQyxHQUFHLENBQUMsQ0FBQyxFQUFFLHdCQUF3QixDQUFDLENBQUM7SUFDM0MsQ0FBQztBQUNILENBQUMsQ0FBQztBQXBCVyxRQUFBLHVCQUF1QiwyQkFvQmxDO0FBRUssTUFBTSx1QkFBdUIsR0FBRyxLQUFLLEVBQzFDLE1BQTJDLEVBQzNDLEtBQXFCLEVBQ3JCLEVBQUU7SUFDRixJQUFJLENBQUM7UUFDSCxNQUFNLHNCQUFzQixHQUFHLElBQUEsWUFBRyxFQUFBOzs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7S0EyQmpDLENBQUM7UUFDRixNQUFNLEVBQUUsSUFBSSxFQUFFLEdBQUcsTUFBTSxNQUFNLENBQUMsTUFBTSxDQUFDO1lBQ25DLFFBQVEsRUFBRSxzQkFBc0I7WUFDaEMsU0FBUyxFQUFFO2dCQUNULFNBQVMsRUFBRSxLQUFLO2FBQ2pCO1NBQ0YsQ0FBQyxDQUFDO1FBRUgsT0FBTyxDQUFDLEdBQUcsQ0FDVCxJQUFJLENBQUMsZUFBZSxDQUFDLGFBQWEsRUFDbEMsNENBQTRDLENBQzdDLENBQUM7UUFDRixPQUFPLElBQUksQ0FBQyxlQUFlLENBQUMsYUFBYSxDQUFDO0lBQzVDLENBQUM7SUFBQyxPQUFPLENBQUMsRUFBRSxDQUFDO1FBQ1gsT0FBTyxDQUFDLEdBQUcsQ0FBQyxDQUFDLEVBQUUsd0NBQXdDLENBQUMsQ0FBQztJQUMzRCxDQUFDO0FBQ0gsQ0FBQyxDQUFDO0FBaERXLFFBQUEsdUJBQXVCLDJCQWdEbEM7QUFFSyxNQUFNLGdCQUFnQixHQUFHLEtBQUssRUFDbkMsTUFBMkMsRUFDM0MsTUFBYyxFQUNkLFFBQWdCLEVBQ2hCLEVBQUU7SUFDRixJQUFJLENBQUM7UUFDSCxPQUFPLENBQ0wsTUFBTSxNQUFNLENBQUMsS0FBSyxDQUErQjtZQUMvQyxLQUFLLEVBQUUsaUNBQXVCO1lBQzlCLFNBQVMsRUFBRTtnQkFDVCxNQUFNO2dCQUNOLFFBQVE7YUFDVDtTQUNGLENBQUMsQ0FDSCxDQUFDLElBQUksRUFBRSxRQUFRLENBQUM7SUFDbkIsQ0FBQztJQUFDLE9BQU8sQ0FBQyxFQUFFLENBQUM7UUFDWCxPQUFPLENBQUMsR0FBRyxDQUFDLENBQUMsRUFBRSw2Q0FBNkMsQ0FBQyxDQUFDO0lBQ2hFLENBQUM7QUFDSCxDQUFDLENBQUM7QUFsQlcsUUFBQSxnQkFBZ0Isb0JBa0IzQjtBQUVLLE1BQU0sY0FBYyxHQUFHLEtBQUssRUFDakMsTUFBMkMsRUFDM0MsT0FBZSxFQUNpQixFQUFFO0lBQ2xDLElBQUksQ0FBQztRQUNILElBQUksQ0FBQyxPQUFPLEVBQUUsQ0FBQztZQUNiLE9BQU8sQ0FBQyxHQUFHLENBQUMsa0NBQWtDLENBQUMsQ0FBQztRQUNsRCxDQUFDO1FBQ0QsT0FBTyxDQUNMLE1BQU0sTUFBTSxDQUFDLEtBQUssQ0FBNkI7WUFDN0MsS0FBSyxFQUFFLHNCQUFZO1lBQ25CLFNBQVMsRUFBRTtnQkFDVCxFQUFFLEVBQUUsT0FBTzthQUNaO1NBQ0YsQ0FBQyxDQUNILENBQUMsSUFBSSxFQUFFLFdBQVcsQ0FBQztJQUN0QixDQUFDO0lBQUMsT0FBTyxDQUFDLEVBQUUsQ0FBQztRQUNYLE9BQU8sQ0FBQyxHQUFHLENBQUMsQ0FBQyxFQUFFLDhCQUE4QixDQUFDLENBQUM7SUFDakQsQ0FBQztBQUNILENBQUMsQ0FBQztBQW5CVyxRQUFBLGNBQWMsa0JBbUJ6QiIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7IENhbGVuZGFyVHlwZSB9IGZyb20gJ0BsaWIvZGF0YVR5cGVzL0NhbGVuZGFyVHlwZSc7XG5pbXBvcnQgeyBDYWxlbmRhckxpc3RJdGVtUmVzcG9uc2VUeXBlIH0gZnJvbSAnQGxpYi9jYWxlbmRhckxpYi90eXBlcyc7XG5pbXBvcnQgeyBnb29nbGVSZXNvdXJjZU5hbWUgfSBmcm9tICdAbGliL2NhbGVuZGFyTGliL2NvbnN0YW50cyc7XG5pbXBvcnQgXyBmcm9tICdsb2Rhc2gnO1xuaW1wb3J0IHsgQXBvbGxvQ2xpZW50LCBncWwsIE5vcm1hbGl6ZWRDYWNoZU9iamVjdCB9IGZyb20gJ0BhcG9sbG8vY2xpZW50JztcbmltcG9ydCBkZWxldGVDYWxlbmRhckJ5SWQgZnJvbSAnQGxpYi9hcG9sbG8vZ3FsL2RlbGV0ZUNhbGVuZGFyQnlJZCc7XG5pbXBvcnQgZGVsZXRlRXZlbnRzQnlDYWxlbmRhcklkTXV0YXRpb24gZnJvbSAnQGxpYi9hcG9sbG8vZ3FsL2RlbGV0ZUV2ZW50c0J5Q2FsZW5kYXJJZE11dGF0aW9uJztcbmltcG9ydCBkZWxldGVDYWxlbmRhcnNCeUlkcyBmcm9tICdAbGliL2Fwb2xsby9ncWwvZGVsZXRlQ2FsZW5kYXJzQnlJZHMnO1xuaW1wb3J0IGdldENhbGVuZGFyV2l0aFJlc291cmNlIGZyb20gJ0BsaWIvYXBvbGxvL2dxbC9nZXRDYWxlbmRhcldpdGhSZXNvdXJjZSc7XG5pbXBvcnQgeyBFdmVudFR5cGUgfSBmcm9tICdAbGliL2RhdGFUeXBlcy9FdmVudFR5cGUnO1xuaW1wb3J0IGdldEV2ZW50QnlJZCBmcm9tICdAbGliL2Fwb2xsby9ncWwvZ2V0RXZlbnRCeUlkJztcblxuZXhwb3J0IGNvbnN0IHVwc2VydENhbGVuZGFyID0gYXN5bmMgKFxuICBjbGllbnQ6IEFwb2xsb0NsaWVudDxOb3JtYWxpemVkQ2FjaGVPYmplY3Q+LFxuICBjYWxlbmRhcjogQ2FsZW5kYXJUeXBlXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zb2xlLmxvZygndXBzZXJ0Q2FsZW5kYXIgY2FsbGVkJyk7XG4gICAgY29uc29sZS5sb2coY2FsZW5kYXIsICcgY2FsZW5kYXIgaW5zaWRlIHVwc2VydENhbGVuZGFyJyk7XG4gICAgY29uc3QgdXBzZXJ0Q2FsZW5kYXJNdXRhdGlvbiA9IGdxbGBcbiAgICAgICAgbXV0YXRpb24gSW5zZXJ0Q2FsZW5kYXIoJGNhbGVuZGFyczogW0NhbGVuZGFyX2luc2VydF9pbnB1dCFdISkge1xuICAgICAgICAgICAgaW5zZXJ0X0NhbGVuZGFyKG9iamVjdHM6ICRjYWxlbmRhcnMsIG9uX2NvbmZsaWN0OiB7Y29uc3RyYWludDogQ2FsZW5kYXJfcGtleSwgdXBkYXRlX2NvbHVtbnM6IFtcbiAgICAgICAgICAgICAgICAke2NhbGVuZGFyPy50aXRsZSA/ICd0aXRsZSwnIDogJyd9IFxuICAgICAgICAgICAgICAgICR7Y2FsZW5kYXI/LmNvbG9ySWQgPyAnY29sb3JJZCwnIDogJyd9IFxuICAgICAgICAgICAgICAgICR7Y2FsZW5kYXI/LmFjY291bnQgPyAnYWNjb3VudCwnIDogJyd9IFxuICAgICAgICAgICAgICAgICR7Y2FsZW5kYXI/LmFjY2Vzc0xldmVsID8gJ2FjY2Vzc0xldmVsLCcgOiAnJ30gXG4gICAgICAgICAgICAgICAgJHtjYWxlbmRhcj8ucmVzb3VyY2UgPyAncmVzb3VyY2UsJyA6ICcnfSBcbiAgICAgICAgICAgICAgICAke2NhbGVuZGFyPy5tb2RpZmlhYmxlICE9PSB1bmRlZmluZWQgPyAnbW9kaWZpYWJsZSwnIDogJyd9IFxuICAgICAgICAgICAgICAgICR7Y2FsZW5kYXI/LmRlZmF1bHRSZW1pbmRlcnMgJiYgY2FsZW5kYXI/LmRlZmF1bHRSZW1pbmRlcnM/Lmxlbmd0aCA+IDAgPyAnZGVmYXVsdFJlbWluZGVycywnIDogJyd9IFxuICAgICAgICAgICAgICAgICR7Y2FsZW5kYXI/Lmdsb2JhbFByaW1hcnkgIT09IHVuZGVmaW5lZCA/ICdnbG9iYWxQcmltYXJ5LCcgOiAnJ30gXG4gICAgICAgICAgICAgICAgJHtjYWxlbmRhcj8uYmFja2dyb3VuZENvbG9yID8gJ2JhY2tncm91bmRDb2xvciwnIDogJyd9IFxuICAgICAgICAgICAgICAgICR7Y2FsZW5kYXI/LmZvcmVncm91bmRDb2xvciA/ICdmb3JlZ3JvdW5kQ29sb3IsJyA6ICcnfSBcbiAgICAgICAgICAgICAgICAke2NhbGVuZGFyPy5kZWxldGVkICE9PSB1bmRlZmluZWQgPyAnZGVsZXRlZCwnIDogJyd9IFxuICAgICAgICAgICAgICAgICR7Y2FsZW5kYXI/LnVwZGF0ZWRBdCA/ICd1cGRhdGVkQXQsJyA6ICcnfVxuICAgICAgICAgICAgICAgICR7Y2FsZW5kYXI/LnBhZ2VUb2tlbiA/ICdwYWdlVG9rZW4sJyA6ICcnfSBcbiAgICAgICAgICAgICAgICAke2NhbGVuZGFyPy5zeW5jVG9rZW4gPyAnc3luY1Rva2VuLCcgOiAnJ30gXG4gICAgICAgICAgICBdfSkge1xuICAgICAgICAgICAgICAgIHJldHVybmluZyB7XG4gICAgICAgICAgICAgICAgICAgIGlkXG4gICAgICAgICAgICAgICAgICAgIHRpdGxlXG4gICAgICAgICAgICAgICAgICAgIGNvbG9ySWRcbiAgICAgICAgICAgICAgICAgICAgYWNjb3VudFxuICAgICAgICAgICAgICAgICAgICBhY2Nlc3NMZXZlbFxuICAgICAgICAgICAgICAgICAgICBtb2RpZmlhYmxlXG4gICAgICAgICAgICAgICAgICAgIHJlc291cmNlXG4gICAgICAgICAgICAgICAgICAgIGRlZmF1bHRSZW1pbmRlcnNcbiAgICAgICAgICAgICAgICAgICAgZ2xvYmFsUHJpbWFyeVxuICAgICAgICAgICAgICAgICAgICBkZWxldGVkXG4gICAgICAgICAgICAgICAgICAgIGNyZWF0ZWREYXRlXG4gICAgICAgICAgICAgICAgICAgIHVwZGF0ZWRBdFxuICAgICAgICAgICAgICAgICAgICB1c2VySWRcbiAgICAgICAgICAgICAgICAgICAgZm9yZWdyb3VuZENvbG9yXG4gICAgICAgICAgICAgICAgICAgIGJhY2tncm91bmRDb2xvclxuICAgICAgICAgICAgICAgICAgICBwYWdlVG9rZW5cbiAgICAgICAgICAgICAgICAgICAgc3luY1Rva2VuXG4gICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgICAgIGFmZmVjdGVkX3Jvd3NcbiAgICAgICAgICAgIH1cbiAgICAgICAgfVxuICAgICAgICBgO1xuICAgIGxldCB2YWx1ZVRvVXBzZXJ0OiBhbnkgPSB7XG4gICAgICBpZDogY2FsZW5kYXI/LmlkLFxuICAgICAgY3JlYXRlZERhdGU6IGNhbGVuZGFyPy5jcmVhdGVkRGF0ZSxcbiAgICAgIHVwZGF0ZWRBdDogY2FsZW5kYXI/LnVwZGF0ZWRBdCxcbiAgICAgIHVzZXJJZDogY2FsZW5kYXI/LnVzZXJJZCxcbiAgICAgIGRlbGV0ZWQ6IGNhbGVuZGFyPy5kZWxldGVkLFxuICAgIH07XG5cbiAgICBpZiAoY2FsZW5kYXI/LnRpdGxlKSB7XG4gICAgICB2YWx1ZVRvVXBzZXJ0ID0ge1xuICAgICAgICAuLi52YWx1ZVRvVXBzZXJ0LFxuICAgICAgICB0aXRsZTogY2FsZW5kYXIudGl0bGUsXG4gICAgICB9O1xuICAgIH1cblxuICAgIGlmIChjYWxlbmRhcj8uY29sb3JJZCkge1xuICAgICAgdmFsdWVUb1Vwc2VydCA9IHtcbiAgICAgICAgLi4udmFsdWVUb1Vwc2VydCxcbiAgICAgICAgY29sb3JJZDogY2FsZW5kYXIuY29sb3JJZCxcbiAgICAgIH07XG4gICAgfVxuXG4gICAgaWYgKGNhbGVuZGFyPy5hY2NvdW50KSB7XG4gICAgICB2YWx1ZVRvVXBzZXJ0ID0ge1xuICAgICAgICAuLi52YWx1ZVRvVXBzZXJ0LFxuICAgICAgICBhY2NvdW50OiBjYWxlbmRhci5hY2NvdW50LFxuICAgICAgfTtcbiAgICB9XG5cbiAgICBpZiAoY2FsZW5kYXI/LmFjY2Vzc0xldmVsKSB7XG4gICAgICB2YWx1ZVRvVXBzZXJ0ID0ge1xuICAgICAgICAuLi52YWx1ZVRvVXBzZXJ0LFxuICAgICAgICBhY2Nlc3NMZXZlbDogY2FsZW5kYXIuYWNjZXNzTGV2ZWwsXG4gICAgICB9O1xuICAgIH1cblxuICAgIGlmIChjYWxlbmRhcj8ucmVzb3VyY2UpIHtcbiAgICAgIHZhbHVlVG9VcHNlcnQgPSB7XG4gICAgICAgIC4uLnZhbHVlVG9VcHNlcnQsXG4gICAgICAgIHJlc291cmNlOiBjYWxlbmRhci5yZXNvdXJjZSxcbiAgICAgIH07XG4gICAgfVxuXG4gICAgaWYgKGNhbGVuZGFyPy5tb2RpZmlhYmxlICE9PSB1bmRlZmluZWQpIHtcbiAgICAgIHZhbHVlVG9VcHNlcnQgPSB7XG4gICAgICAgIC4uLnZhbHVlVG9VcHNlcnQsXG4gICAgICAgIG1vZGlmaWFibGU6IGNhbGVuZGFyLm1vZGlmaWFibGUsXG4gICAgICB9O1xuICAgIH1cblxuICAgIGlmIChjYWxlbmRhcj8uZGVmYXVsdFJlbWluZGVycyAmJiBjYWxlbmRhcj8uZGVmYXVsdFJlbWluZGVycz8ubGVuZ3RoID4gMCkge1xuICAgICAgdmFsdWVUb1Vwc2VydCA9IHtcbiAgICAgICAgLi4udmFsdWVUb1Vwc2VydCxcbiAgICAgICAgZGVmYXVsdFJlbWluZGVyczogY2FsZW5kYXIuZGVmYXVsdFJlbWluZGVycyxcbiAgICAgIH07XG4gICAgfVxuXG4gICAgaWYgKGNhbGVuZGFyPy5nbG9iYWxQcmltYXJ5ICE9PSB1bmRlZmluZWQpIHtcbiAgICAgIHZhbHVlVG9VcHNlcnQgPSB7XG4gICAgICAgIC4uLnZhbHVlVG9VcHNlcnQsXG4gICAgICAgIGdsb2JhbFByaW1hcnk6IGNhbGVuZGFyLmdsb2JhbFByaW1hcnksXG4gICAgICB9O1xuICAgIH1cblxuICAgIGlmIChjYWxlbmRhcj8uYmFja2dyb3VuZENvbG9yKSB7XG4gICAgICB2YWx1ZVRvVXBzZXJ0ID0ge1xuICAgICAgICAuLi52YWx1ZVRvVXBzZXJ0LFxuICAgICAgICBiYWNrZ3JvdW5kQ29sb3I6IGNhbGVuZGFyLmJhY2tncm91bmRDb2xvcixcbiAgICAgIH07XG4gICAgfVxuXG4gICAgaWYgKGNhbGVuZGFyPy5mb3JlZ3JvdW5kQ29sb3IpIHtcbiAgICAgIHZhbHVlVG9VcHNlcnQgPSB7XG4gICAgICAgIC4uLnZhbHVlVG9VcHNlcnQsXG4gICAgICAgIGZvcmVncm91bmRDb2xvcjogY2FsZW5kYXIuZm9yZWdyb3VuZENvbG9yLFxuICAgICAgfTtcbiAgICB9XG5cbiAgICBpZiAoY2FsZW5kYXI/LmRlbGV0ZWQgIT09IHVuZGVmaW5lZCkge1xuICAgICAgdmFsdWVUb1Vwc2VydCA9IHtcbiAgICAgICAgLi4udmFsdWVUb1Vwc2VydCxcbiAgICAgICAgZGVsZXRlZDogY2FsZW5kYXIuZGVsZXRlZCxcbiAgICAgIH07XG4gICAgfVxuXG4gICAgaWYgKGNhbGVuZGFyPy51cGRhdGVkQXQpIHtcbiAgICAgIHZhbHVlVG9VcHNlcnQgPSB7XG4gICAgICAgIC4uLnZhbHVlVG9VcHNlcnQsXG4gICAgICAgIHVwZGF0ZWRBdDogY2FsZW5kYXIudXBkYXRlZEF0LFxuICAgICAgfTtcbiAgICB9XG5cbiAgICBpZiAoY2FsZW5kYXI/LnBhZ2VUb2tlbikge1xuICAgICAgdmFsdWVUb1Vwc2VydCA9IHtcbiAgICAgICAgLi4udmFsdWVUb1Vwc2VydCxcbiAgICAgICAgcGFnZVRva2VuOiBjYWxlbmRhci5wYWdlVG9rZW4sXG4gICAgICB9O1xuICAgIH1cblxuICAgIGlmIChjYWxlbmRhcj8uc3luY1Rva2VuKSB7XG4gICAgICB2YWx1ZVRvVXBzZXJ0ID0ge1xuICAgICAgICAuLi52YWx1ZVRvVXBzZXJ0LFxuICAgICAgICBzeW5jVG9rZW46IGNhbGVuZGFyLnN5bmNUb2tlbixcbiAgICAgIH07XG4gICAgfVxuXG4gICAgY29uc3QgeyBkYXRhIH0gPSBhd2FpdCBjbGllbnQubXV0YXRlPHtcbiAgICAgIGluc2VydF9DYWxlbmRhcjogeyByZXR1cm5pbmc6IENhbGVuZGFyVHlwZVtdOyBhZmZlY3RlZF9yb3dzOiBudW1iZXIgfTtcbiAgICB9Pih7XG4gICAgICBtdXRhdGlvbjogdXBzZXJ0Q2FsZW5kYXJNdXRhdGlvbixcbiAgICAgIHZhcmlhYmxlczoge1xuICAgICAgICBjYWxlbmRhcnM6IFt2YWx1ZVRvVXBzZXJ0XSxcbiAgICAgIH0sXG4gICAgICB1cGRhdGUoY2FjaGUsIHsgZGF0YSB9KSB7XG4gICAgICAgIGlmIChcbiAgICAgICAgICBkYXRhPy5pbnNlcnRfQ2FsZW5kYXI/LmFmZmVjdGVkX3Jvd3MgJiZcbiAgICAgICAgICBkYXRhPy5pbnNlcnRfQ2FsZW5kYXI/LmFmZmVjdGVkX3Jvd3MgPiAwXG4gICAgICAgICkge1xuICAgICAgICAgIGNvbnNvbGUubG9nKCdpbnNlcnRfQ2FsZW5kYXI/LmFmZmVjdGVkX3Jvd3MnLCBkYXRhKTtcbiAgICAgICAgfVxuXG4gICAgICAgIGNhY2hlLm1vZGlmeSh7XG4gICAgICAgICAgZmllbGRzOiB7XG4gICAgICAgICAgICBDYWxlbmRhcihleGlzdGluZ0NhbGVuZGFycyA9IFtdKSB7XG4gICAgICAgICAgICAgIGNvbnN0IG5ld0NhbGVuZGFyUmVmID0gY2FjaGUud3JpdGVGcmFnbWVudCh7XG4gICAgICAgICAgICAgICAgZGF0YTogZGF0YT8uaW5zZXJ0X0NhbGVuZGFyPy5yZXR1cm5pbmc/LlswXSxcbiAgICAgICAgICAgICAgICBmcmFnbWVudDogZ3FsYFxuICAgICAgICAgICAgICAgICAgZnJhZ21lbnQgTmV3Q2FsZW5kYXIgb24gQ2FsZW5kYXIge1xuICAgICAgICAgICAgICAgICAgICBpZFxuICAgICAgICAgICAgICAgICAgICB0aXRsZVxuICAgICAgICAgICAgICAgICAgICBjb2xvcklkXG4gICAgICAgICAgICAgICAgICAgIGFjY291bnRcbiAgICAgICAgICAgICAgICAgICAgYWNjZXNzTGV2ZWxcbiAgICAgICAgICAgICAgICAgICAgbW9kaWZpYWJsZVxuICAgICAgICAgICAgICAgICAgICByZXNvdXJjZVxuICAgICAgICAgICAgICAgICAgICBkZWZhdWx0UmVtaW5kZXJzXG4gICAgICAgICAgICAgICAgICAgIGdsb2JhbFByaW1hcnlcbiAgICAgICAgICAgICAgICAgICAgZGVsZXRlZFxuICAgICAgICAgICAgICAgICAgICBjcmVhdGVkRGF0ZVxuICAgICAgICAgICAgICAgICAgICB1cGRhdGVkQXRcbiAgICAgICAgICAgICAgICAgICAgdXNlcklkXG4gICAgICAgICAgICAgICAgICAgIGZvcmVncm91bmRDb2xvclxuICAgICAgICAgICAgICAgICAgICBiYWNrZ3JvdW5kQ29sb3JcbiAgICAgICAgICAgICAgICAgICAgcGFnZVRva2VuXG4gICAgICAgICAgICAgICAgICAgIHN5bmNUb2tlblxuICAgICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgICAgIGAsXG4gICAgICAgICAgICAgIH0pO1xuICAgICAgICAgICAgICBjb25zdCBmaWx0ZXJlZENhbGVuZGFycyA9XG4gICAgICAgICAgICAgICAgZXhpc3RpbmdDYWxlbmRhcnM/LmZpbHRlcihcbiAgICAgICAgICAgICAgICAgIChlOiBDYWxlbmRhclR5cGUpID0+XG4gICAgICAgICAgICAgICAgICAgIGU/LmlkICE9PSBkYXRhPy5pbnNlcnRfQ2FsZW5kYXI/LnJldHVybmluZz8uWzBdPy5pZFxuICAgICAgICAgICAgICAgICkgfHwgW107XG4gICAgICAgICAgICAgIGNvbnNvbGUubG9nKFxuICAgICAgICAgICAgICAgIGZpbHRlcmVkQ2FsZW5kYXJzLFxuICAgICAgICAgICAgICAgICcgZmlsdGVyZWRDYWxlbmRhcnMgaW5zaWRlIGF0b21pY1Vwc2VydENhbGVuZGFySW5EYidcbiAgICAgICAgICAgICAgKTtcbiAgICAgICAgICAgICAgaWYgKGZpbHRlcmVkQ2FsZW5kYXJzPy5sZW5ndGggPiAwKSB7XG4gICAgICAgICAgICAgICAgcmV0dXJuIGZpbHRlcmVkQ2FsZW5kYXJzLmNvbmNhdChbbmV3Q2FsZW5kYXJSZWZdKTtcbiAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgICByZXR1cm4gW25ld0NhbGVuZGFyUmVmXTtcbiAgICAgICAgICAgIH0sXG4gICAgICAgICAgfSxcbiAgICAgICAgfSk7XG4gICAgICB9LFxuICAgIH0pO1xuICAgIGNvbnNvbGUubG9nKFxuICAgICAgZGF0YSAmJiBkYXRhLmluc2VydF9DYWxlbmRhci5yZXR1cm5pbmdbMF0sXG4gICAgICAnIHBvc3QgdXBzZXJ0Q2FsZW5kYXInXG4gICAgKTtcbiAgICByZXR1cm4gZGF0YSAmJiBkYXRhLmluc2VydF9DYWxlbmRhci5yZXR1cm5pbmdbMF07XG4gIH0gY2F0Y2ggKGVycm9yKSB7XG4gICAgY29uc29sZS5sb2coZXJyb3IsICcgZXJyb3IgaW5zaWRlIHVwc2VydENhbGVuZGFyJyk7XG4gIH1cbn07XG5leHBvcnQgY29uc3QgdXBzZXJ0R29vZ2xlQ2FsZW5kYXJJbkRiID0gYXN5bmMgKFxuICBjbGllbnQ6IEFwb2xsb0NsaWVudDxOb3JtYWxpemVkQ2FjaGVPYmplY3Q+LFxuICBjYWxlbmRhckl0ZW1SZXNwb25zZTogQ2FsZW5kYXJMaXN0SXRlbVJlc3BvbnNlVHlwZSxcbiAgdXNlcklkOiBzdHJpbmdcbikgPT4ge1xuICB0cnkge1xuICAgIGNvbnNvbGUubG9nKHVzZXJJZCwgJyB1c2VySWQgaW5zaWRlIHVwc2VydEdvb2dsZUNhbGVuZGFySW5EYicpO1xuICAgIGNvbnN0IGNhbGVuZGFyOiBDYWxlbmRhclR5cGUgPSB7XG4gICAgICBpZDogY2FsZW5kYXJJdGVtUmVzcG9uc2UuaWQsXG4gICAgICB0aXRsZTogY2FsZW5kYXJJdGVtUmVzcG9uc2Uuc3VtbWFyeSxcbiAgICAgIGJhY2tncm91bmRDb2xvcjogY2FsZW5kYXJJdGVtUmVzcG9uc2U/LmJhY2tncm91bmRDb2xvcixcbiAgICAgIGZvcmVncm91bmRDb2xvcjogY2FsZW5kYXJJdGVtUmVzcG9uc2U/LmZvcmVncm91bmRDb2xvcixcbiAgICAgIGNvbG9ySWQ6IGNhbGVuZGFySXRlbVJlc3BvbnNlPy5jb2xvcklkLFxuICAgICAgcmVzb3VyY2U6IGdvb2dsZVJlc291cmNlTmFtZSxcbiAgICAgIGFjY2Vzc0xldmVsOiBjYWxlbmRhckl0ZW1SZXNwb25zZT8uYWNjZXNzUm9sZSxcbiAgICAgIGRlZmF1bHRSZW1pbmRlcnM6IGNhbGVuZGFySXRlbVJlc3BvbnNlPy5kZWZhdWx0UmVtaW5kZXJzLFxuICAgICAgbW9kaWZpYWJsZTogdHJ1ZSxcbiAgICAgIGRlbGV0ZWQ6IGZhbHNlLFxuICAgICAgY3JlYXRlZERhdGU6IG5ldyBEYXRlKCkudG9JU09TdHJpbmcoKSxcbiAgICAgIHVwZGF0ZWRBdDogbmV3IERhdGUoKS50b0lTT1N0cmluZygpLFxuICAgICAgdXNlcklkLFxuICAgIH07XG5cbiAgICByZXR1cm4gdXBzZXJ0Q2FsZW5kYXIoY2xpZW50LCBjYWxlbmRhcik7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnY3JlYXRlQ2FsZW5kYXJJbkRiJyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBkZWxldGVHb29nbGVDYWxlbmRhckluRGIgPSBhc3luYyAoXG4gIGNsaWVudDogQXBvbGxvQ2xpZW50PE5vcm1hbGl6ZWRDYWNoZU9iamVjdD4sXG4gIGNhbGVuZGFySWQ6IHN0cmluZ1xuKSA9PiB7XG4gIHRyeSB7XG4gICAgYXdhaXQgY2xpZW50Lm11dGF0ZTx7IGRlbGV0ZV9DYWxlbmRhcl9ieV9wazogQ2FsZW5kYXJUeXBlIH0+KHtcbiAgICAgIG11dGF0aW9uOiBkZWxldGVDYWxlbmRhckJ5SWQsXG4gICAgICB2YXJpYWJsZXM6IHtcbiAgICAgICAgaWQ6IGNhbGVuZGFySWQsXG4gICAgICB9LFxuICAgIH0pO1xuICAgIGNvbnNvbGUubG9nKCdkZWxldGVkIGNhbGVuZGFyIGluIGRiJyk7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnZGVsZXRlR29vZ2xlQ2FsZW5kYXJJbkRiJyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBkZWxldGVFdmVudHNCeUNhbGVuZGFySWQgPSBhc3luYyAoXG4gIGNsaWVudDogQXBvbGxvQ2xpZW50PE5vcm1hbGl6ZWRDYWNoZU9iamVjdD4sXG4gIGNhbGVuZGFySWQ6IHN0cmluZ1xuKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3QgeyBkYXRhIH0gPSBhd2FpdCBjbGllbnQubXV0YXRlPHtcbiAgICAgIGRlbGV0ZV9FdmVudDogeyBhZmZlY3RlZF9yb3dzOiBudW1iZXIgfTtcbiAgICB9Pih7XG4gICAgICBtdXRhdGlvbjogZGVsZXRlRXZlbnRzQnlDYWxlbmRhcklkTXV0YXRpb24sXG4gICAgICB2YXJpYWJsZXM6IHtcbiAgICAgICAgY2FsZW5kYXJJZCxcbiAgICAgIH0sXG4gICAgfSk7XG5cbiAgICBjb25zb2xlLmxvZyhkYXRhPy5kZWxldGVfRXZlbnQ/LmFmZmVjdGVkX3Jvd3MsICcgZGVsZXRlZCBldmVudHMgaW4gZGInKTtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIGRlbGV0ZSBldmVudCBieSBjYWxlbmRhcklkJyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBidWxrUmVtb3ZlQ2FsZW5kYXJzSW5EYiA9IGFzeW5jIChcbiAgY2xpZW50OiBBcG9sbG9DbGllbnQ8Tm9ybWFsaXplZENhY2hlT2JqZWN0PixcbiAgaXRlbXM6IHN0cmluZ1tdXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCB7IGRhdGEgfSA9IGF3YWl0IGNsaWVudC5tdXRhdGU8e1xuICAgICAgZGVsZXRlX0NhbGVuZGFyOiB7IGFmZmVjdGVkX3Jvd3M6IG51bWJlciB9O1xuICAgIH0+KHtcbiAgICAgIG11dGF0aW9uOiBkZWxldGVDYWxlbmRhcnNCeUlkcyxcbiAgICAgIHZhcmlhYmxlczoge1xuICAgICAgICBpZHM6IGl0ZW1zLFxuICAgICAgfSxcbiAgICB9KTtcbiAgICBjb25zb2xlLmxvZyhcbiAgICAgIGRhdGE/LmRlbGV0ZV9DYWxlbmRhcj8uYWZmZWN0ZWRfcm93cyxcbiAgICAgICcgc3VjY2Vzc2Z1bGx5IHJlbW92ZWQgYnVsayBjYWxlbmRhciBpdGVtcydcbiAgICApO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gYnVsayByZW1vdmUnKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IGJ1bGtDcmVhdGVDYWxlbmRhcnNJbkRiID0gYXN5bmMgKFxuICBjbGllbnQ6IEFwb2xsb0NsaWVudDxOb3JtYWxpemVkQ2FjaGVPYmplY3Q+LFxuICBpdGVtczogQ2FsZW5kYXJUeXBlW11cbikgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IHVwc2VydENhbGVuZGFyTXV0YXRpb24gPSBncWxgXG4gICAgICBtdXRhdGlvbiBJbnNlcnRDYWxlbmRhcigkY2FsZW5kYXJzOiBbQ2FsZW5kYXJfaW5zZXJ0X2lucHV0IV0hKSB7XG4gICAgICAgIGluc2VydF9DYWxlbmRhcihcbiAgICAgICAgICBvYmplY3RzOiAkY2FsZW5kYXJzXG4gICAgICAgICAgb25fY29uZmxpY3Q6IHtcbiAgICAgICAgICAgIGNvbnN0cmFpbnQ6IENhbGVuZGFyX3BrZXlcbiAgICAgICAgICAgIHVwZGF0ZV9jb2x1bW5zOiBbXG4gICAgICAgICAgICAgIHRpdGxlXG4gICAgICAgICAgICAgIGNvbG9ySWRcbiAgICAgICAgICAgICAgYWNjb3VudFxuICAgICAgICAgICAgICBhY2Nlc3NMZXZlbFxuICAgICAgICAgICAgICByZXNvdXJjZVxuICAgICAgICAgICAgICBtb2RpZmlhYmxlXG4gICAgICAgICAgICAgIGRlZmF1bHRSZW1pbmRlcnNcbiAgICAgICAgICAgICAgZ2xvYmFsUHJpbWFyeVxuICAgICAgICAgICAgICBiYWNrZ3JvdW5kQ29sb3JcbiAgICAgICAgICAgICAgZm9yZWdyb3VuZENvbG9yXG4gICAgICAgICAgICAgIGRlbGV0ZWRcbiAgICAgICAgICAgICAgdXBkYXRlZEF0XG4gICAgICAgICAgICAgIHBhZ2VUb2tlblxuICAgICAgICAgICAgICBzeW5jVG9rZW5cbiAgICAgICAgICAgIF1cbiAgICAgICAgICB9XG4gICAgICAgICkge1xuICAgICAgICAgIGFmZmVjdGVkX3Jvd3NcbiAgICAgICAgfVxuICAgICAgfVxuICAgIGA7XG4gICAgY29uc3QgeyBkYXRhIH0gPSBhd2FpdCBjbGllbnQubXV0YXRlKHtcbiAgICAgIG11dGF0aW9uOiB1cHNlcnRDYWxlbmRhck11dGF0aW9uLFxuICAgICAgdmFyaWFibGVzOiB7XG4gICAgICAgIGNhbGVuZGFyczogaXRlbXMsXG4gICAgICB9LFxuICAgIH0pO1xuXG4gICAgY29uc29sZS5sb2coXG4gICAgICBkYXRhLmluc2VydF9DYWxlbmRhci5hZmZlY3RlZF9yb3dzLFxuICAgICAgJyBzdWNjZXNzZnVsbHkgYnVsayBpbnNlcnRlZCBjYWxlbmRhciBpdGVtcydcbiAgICApO1xuICAgIHJldHVybiBkYXRhLmluc2VydF9DYWxlbmRhci5hZmZlY3RlZF9yb3dzO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gYnVsayBjcmVhdGUgY2FsZW5kYXJzIGluIGRiJyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBnZXRJdGVtc1RvUmVtb3ZlID0gYXN5bmMgKFxuICBjbGllbnQ6IEFwb2xsb0NsaWVudDxOb3JtYWxpemVkQ2FjaGVPYmplY3Q+LFxuICB1c2VySWQ6IHN0cmluZyxcbiAgcmVzb3VyY2U6IHN0cmluZ1xuKSA9PiB7XG4gIHRyeSB7XG4gICAgcmV0dXJuIChcbiAgICAgIGF3YWl0IGNsaWVudC5xdWVyeTx7IENhbGVuZGFyOiBDYWxlbmRhclR5cGVbXSB9Pih7XG4gICAgICAgIHF1ZXJ5OiBnZXRDYWxlbmRhcldpdGhSZXNvdXJjZSxcbiAgICAgICAgdmFyaWFibGVzOiB7XG4gICAgICAgICAgdXNlcklkLFxuICAgICAgICAgIHJlc291cmNlLFxuICAgICAgICB9LFxuICAgICAgfSlcbiAgICApLmRhdGE/LkNhbGVuZGFyO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gZ2V0IGl0ZW1zIHRvIHJlbW92ZSBmb3IgY2FsZW5kYXInKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IGdldEV2ZW50V2l0aElkID0gYXN5bmMgKFxuICBjbGllbnQ6IEFwb2xsb0NsaWVudDxOb3JtYWxpemVkQ2FjaGVPYmplY3Q+LFxuICBldmVudElkOiBzdHJpbmdcbik6IFByb21pc2U8RXZlbnRUeXBlIHwgdW5kZWZpbmVkPiA9PiB7XG4gIHRyeSB7XG4gICAgaWYgKCFldmVudElkKSB7XG4gICAgICBjb25zb2xlLmxvZygnbm8gZXZlbnRJZCBpbnNpZGUgZ2V0RXZlbnRXaXRoSWQnKTtcbiAgICB9XG4gICAgcmV0dXJuIChcbiAgICAgIGF3YWl0IGNsaWVudC5xdWVyeTx7IEV2ZW50X2J5X3BrOiBFdmVudFR5cGUgfT4oe1xuICAgICAgICBxdWVyeTogZ2V0RXZlbnRCeUlkLFxuICAgICAgICB2YXJpYWJsZXM6IHtcbiAgICAgICAgICBpZDogZXZlbnRJZCxcbiAgICAgICAgfSxcbiAgICAgIH0pXG4gICAgKS5kYXRhPy5FdmVudF9ieV9waztcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIGdldCBldmVudCB3aXRoIGlkJyk7XG4gIH1cbn07XG4iXX0=