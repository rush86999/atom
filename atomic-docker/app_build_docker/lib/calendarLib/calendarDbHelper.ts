import { CalendarType } from '@lib/dataTypes/CalendarType';
import { CalendarListItemResponseType } from '@lib/calendarLib/types';
import { googleResourceName } from '@lib/calendarLib/constants';
import _ from 'lodash';
import { ApolloClient, gql, NormalizedCacheObject } from '@apollo/client';
import deleteCalendarById from '@lib/apollo/gql/deleteCalendarById';
import deleteEventsByCalendarIdMutation from '@lib/apollo/gql/deleteEventsByCalendarIdMutation';
import deleteCalendarsByIds from '@lib/apollo/gql/deleteCalendarsByIds';
import getCalendarWithResource from '@lib/apollo/gql/getCalendarWithResource';
import { EventType } from '@lib/dataTypes/EventType';
import getEventById from '@lib/apollo/gql/getEventById';

export const upsertCalendar = async (
  client: ApolloClient<NormalizedCacheObject>,
  calendar: CalendarType
) => {
  try {
    console.log('upsertCalendar called');
    console.log(calendar, ' calendar inside upsertCalendar');
    const upsertCalendarMutation = gql`
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
    let valueToUpsert: any = {
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

    const { data } = await client.mutate<{
      insert_Calendar: { returning: CalendarType[]; affected_rows: number };
    }>({
      mutation: upsertCalendarMutation,
      variables: {
        calendars: [valueToUpsert],
      },
      update(cache, { data }) {
        if (
          data?.insert_Calendar?.affected_rows &&
          data?.insert_Calendar?.affected_rows > 0
        ) {
          console.log('insert_Calendar?.affected_rows', data);
        }

        cache.modify({
          fields: {
            Calendar(existingCalendars = []) {
              const newCalendarRef = cache.writeFragment({
                data: data?.insert_Calendar?.returning?.[0],
                fragment: gql`
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
              const filteredCalendars =
                existingCalendars?.filter(
                  (e: CalendarType) =>
                    e?.id !== data?.insert_Calendar?.returning?.[0]?.id
                ) || [];
              console.log(
                filteredCalendars,
                ' filteredCalendars inside atomicUpsertCalendarInDb'
              );
              if (filteredCalendars?.length > 0) {
                return filteredCalendars.concat([newCalendarRef]);
              }
              return [newCalendarRef];
            },
          },
        });
      },
    });
    console.log(
      data && data.insert_Calendar.returning[0],
      ' post upsertCalendar'
    );
    return data && data.insert_Calendar.returning[0];
  } catch (error) {
    console.log(error, ' error inside upsertCalendar');
  }
};
export const upsertGoogleCalendarInDb = async (
  client: ApolloClient<NormalizedCacheObject>,
  calendarItemResponse: CalendarListItemResponseType,
  userId: string
) => {
  try {
    console.log(userId, ' userId inside upsertGoogleCalendarInDb');
    const calendar: CalendarType = {
      id: calendarItemResponse.id,
      title: calendarItemResponse.summary,
      backgroundColor: calendarItemResponse?.backgroundColor,
      foregroundColor: calendarItemResponse?.foregroundColor,
      colorId: calendarItemResponse?.colorId,
      resource: googleResourceName,
      accessLevel: calendarItemResponse?.accessRole,
      defaultReminders: calendarItemResponse?.defaultReminders,
      modifiable: true,
      deleted: false,
      createdDate: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      userId,
    };

    return upsertCalendar(client, calendar);
  } catch (e) {
    console.log(e, 'createCalendarInDb');
  }
};

export const deleteGoogleCalendarInDb = async (
  client: ApolloClient<NormalizedCacheObject>,
  calendarId: string
) => {
  try {
    await client.mutate<{ delete_Calendar_by_pk: CalendarType }>({
      mutation: deleteCalendarById,
      variables: {
        id: calendarId,
      },
    });
    console.log('deleted calendar in db');
  } catch (e) {
    console.log(e, 'deleteGoogleCalendarInDb');
  }
};

export const deleteEventsByCalendarId = async (
  client: ApolloClient<NormalizedCacheObject>,
  calendarId: string
) => {
  try {
    const { data } = await client.mutate<{
      delete_Event: { affected_rows: number };
    }>({
      mutation: deleteEventsByCalendarIdMutation,
      variables: {
        calendarId,
      },
    });

    console.log(data?.delete_Event?.affected_rows, ' deleted events in db');
  } catch (e) {
    console.log(e, ' unable to delete event by calendarId');
  }
};

export const bulkRemoveCalendarsInDb = async (
  client: ApolloClient<NormalizedCacheObject>,
  items: string[]
) => {
  try {
    const { data } = await client.mutate<{
      delete_Calendar: { affected_rows: number };
    }>({
      mutation: deleteCalendarsByIds,
      variables: {
        ids: items,
      },
    });
    console.log(
      data?.delete_Calendar?.affected_rows,
      ' successfully removed bulk calendar items'
    );
  } catch (e) {
    console.log(e, ' unable to bulk remove');
  }
};

export const bulkCreateCalendarsInDb = async (
  client: ApolloClient<NormalizedCacheObject>,
  items: CalendarType[]
) => {
  try {
    const upsertCalendarMutation = gql`
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

    console.log(
      data.insert_Calendar.affected_rows,
      ' successfully bulk inserted calendar items'
    );
    return data.insert_Calendar.affected_rows;
  } catch (e) {
    console.log(e, ' unable to bulk create calendars in db');
  }
};

export const getItemsToRemove = async (
  client: ApolloClient<NormalizedCacheObject>,
  userId: string,
  resource: string
) => {
  try {
    return (
      await client.query<{ Calendar: CalendarType[] }>({
        query: getCalendarWithResource,
        variables: {
          userId,
          resource,
        },
      })
    ).data?.Calendar;
  } catch (e) {
    console.log(e, ' unable to get items to remove for calendar');
  }
};

export const getEventWithId = async (
  client: ApolloClient<NormalizedCacheObject>,
  eventId: string
): Promise<EventType | undefined> => {
  try {
    if (!eventId) {
      console.log('no eventId inside getEventWithId');
    }
    return (
      await client.query<{ Event_by_pk: EventType }>({
        query: getEventById,
        variables: {
          id: eventId,
        },
      })
    ).data?.Event_by_pk;
  } catch (e) {
    console.log(e, ' unable to get event with id');
  }
};
