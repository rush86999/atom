import { v4 as uuid } from 'uuid';

import { dayjs } from '@lib/date-utils';

// dayjs.extend(utc)

import { ApolloClient, gql, NormalizedCacheObject } from '@apollo/client';
import { EventType } from '@lib/dataTypes/EventType';
import removeCategoriesForEvent from '@lib/apollo/gql/removeCategoriesForEvent';
import {
  CategoryType,
  DefaultRemindersType,
  DefaultTimeBlockingType,
  DefaultTimePreferenceTypes,
} from '@lib/dataTypes/CategoryType';
import createCategoryMutation from '@lib/apollo/gql/createCategoryMutation';
import listCategoriesForUser from '@lib/apollo/gql/listCategoriesForUser';
import updateCategoryForName from '@lib/apollo/gql/updateCategoryForName';
import deleteCategoryById from '@lib/apollo/gql/deleteCategoryById';
import removeEventConnectionsForCategoryMutation from '@lib/apollo/gql/removeEventConnectionsForCategoryMutation';
import listCategoriesForEventId from '@lib/apollo/gql/listCategoriesForEventId';
import listEventsForCategoryQuery from '@lib/apollo/gql/listEventsForCategoryQuery';
import removeCategoryEventConnection from '@lib/apollo/gql/removeCategoryEventConnection';
import getCategoryById from '@lib/apollo/gql/getCategoryById';
import { CategoryEventType } from '@lib/dataTypes/Category_EventType';
import _ from 'lodash';
// import {
//   category_eventType,
// } from '@dataTypes/category_eventType'
// import {
//   CategoryType,
// } from '@dataTypes/CategoryType'

export const createCategory = async (
  client: ApolloClient<NormalizedCacheObject>,
  category: string,
  userId: string
) => {
  try {
    const newCategoryValue = {
      id: uuid(),
      userId,
      name: category,
      updatedAt: dayjs().toISOString(),
      createdDate: dayjs().toISOString(),
    };

    const { data } = await client.mutate<{ insert_Category_one: CategoryType }>(
      {
        mutation: createCategoryMutation,
        variables: newCategoryValue,
      }
    );

    console.log(data, ' successfully inserted category');
    return data?.insert_Category_one;
  } catch (e) {
    console.log(e, ' unable to create category');
  }
};

export const listUserCategories = async (
  client: ApolloClient<NormalizedCacheObject>,
  userId: string
) => {
  try {
    const { data } = await client.query<{
      Category: CategoryType[];
    }>({
      query: listCategoriesForUser,
      variables: {
        userId,
      },
      fetchPolicy: 'no-cache',
    });

    console.log(data, ' successfully listed categories');
    return data?.Category;
  } catch (e) {
    console.log(e, ' unable to listUserCategories');
  }
};

export const updateCategoryName = async (
  client: ApolloClient<NormalizedCacheObject>,
  newName: string,
  categoryId: string
) => {
  try {
    const { data } = await client.mutate<{
      update_Category_by_pk: CategoryType;
    }>({
      mutation: updateCategoryForName,
      variables: {
        id: categoryId,
        name: newName,
        updatedAt: dayjs().toISOString(),
      },
    });

    console.log(data, ' successfully updated category');
    return data?.update_Category_by_pk;
  } catch (e) {
    console.log(e, ' unable to update category');
  }
};

export const removeCategory = async (
  client: ApolloClient<NormalizedCacheObject>,
  categoryId: string
) => {
  try {
    const { data } = await client.mutate<{
      delete_Category_by_pk: CategoryType;
    }>({
      mutation: deleteCategoryById,
      variables: {
        id: categoryId,
      },
    });

    console.log(data, ' successfully removed category');
    return data?.delete_Category_by_pk;
  } catch (e) {
    console.log(e, ' unable to remove category');
  }
};

export const removeEventConnectionsForCategory = async (
  client: ApolloClient<NormalizedCacheObject>,
  categoryId: string
) => {
  try {
    const { data } = await client.mutate<{
      delete_Category_Event: {
        affected_rows: number;
        returning: CategoryEventType[];
      };
    }>({
      mutation: removeEventConnectionsForCategoryMutation,
      variables: {
        categoryId,
      },
      // refetchQueries: [
      //   listCategoriesForEventId,
      //   'listCategoriesForEventId'
      // ],
      update(cache, { data }) {
        const deletedCategoryEvents = data?.delete_Category_Event?.returning;
        const normalizedIds = deletedCategoryEvents.map((c) =>
          cache.identify({ id: c.id, __typename: c.__typename })
        );
        normalizedIds.forEach((id) => cache.evict({ id }));
        cache.gc();
      },
    });

    console.log(data, ' successfully removed event connections for category');
    return data?.delete_Category_Event;
  } catch (e) {
    console.log(e, ' unable to remove events for category');
  }
};
export const upsertCategoryEventConnection = async (
  client: ApolloClient<NormalizedCacheObject>,
  userId: string,
  categoryId: string,
  eventId: string
) => {
  try {
    console.log(categoryId, ' categoryId inside upsertCategoryEventConnection');
    const upsertCategoryEvent = gql`
        mutation InsertCategory_Event($category_events: [Category_Event_insert_input!]!) {
          insert_Category_Event(
            objects: $category_events,
            on_conflict: {
                constraint: Category_Event_pkey,
                update_columns: [
                  ${categoryId ? 'categoryId,' : ''}
                  ${eventId ? 'eventId,' : ''} 
                  deleted, 
                  updatedAt,
                ]
            }){
            returning {
              id
              categoryId
              createdDate
              deleted
              eventId
              updatedAt
              userId
              Category {
                color
                copyAvailability
                copyIsBreak
                copyIsExternalMeeting
                copyIsMeeting
                copyModifiable
                copyPriorityLevel
                copyReminders
                copyTimeBlocking
                copyTimePreference
                createdDate
                defaultAvailability
                defaultExternalMeetingModifiable
                defaultIsBreak
                defaultIsExternalMeeting
                defaultIsMeeting
                defaultMeetingModifiable
                defaultModifiable
                defaultPriorityLevel
                defaultReminders
                defaultTimeBlocking
                defaultTimePreference
                deleted
                id
                name
                updatedAt
                userId
              }
            }
            affected_rows
          }
        } 
      `;

    const variables = {
      category_events: [
        {
          id: uuid(),
          userId,
          categoryId,
          eventId,
          deleted: false,
          updatedAt: dayjs().toISOString(),
          createdDate: dayjs().toISOString(),
        },
      ],
    };

    const { data } = await client.mutate<{
      insert_Category_Event: {
        returning: CategoryEventType[];
        affected_rows: number;
      };
    }>({
      mutation: upsertCategoryEvent,
      variables,
      update(cache, { data }) {
        if (data?.insert_Category_Event?.affected_rows > 0) {
          console.log('insert_Category_Event', data);
        }

        cache.modify({
          fields: {
            Category_Event(existingCategoryEvents = []) {
              const newCategoryEventRefs =
                data?.insert_Category_Event?.returning.map((c) =>
                  cache.writeFragment({
                    data: c,
                    fragment: gql`
                      fragment NewCategory_Event on Category_Event {
                        id
                        categoryId
                        createdDate
                        deleted
                        eventId
                        updatedAt
                        userId
                      }
                    `,
                  })
                );
              return [...existingCategoryEvents, ...newCategoryEventRefs];
            },
          },
        });
      },
    });

    console.log(data, ' successfully upserted category event connection');
  } catch (e) {
    console.log(e, ' unable to create category event');
  }
};

export const listEventsForCategory = async (
  client: ApolloClient<NormalizedCacheObject>,
  categoryId: string
) => {
  try {
    const { data } = await client.query<{
      Event: EventType[];
    }>({
      query: listEventsForCategoryQuery,
      variables: {
        categoryId,
      },
    });

    console.log(data, ' successfully listed events for category');
    return data?.Event;
  } catch (e) {
    console.log(e, ' unable to listEventsForCategory');
  }
};

export const listCategoriesForEvent = async (
  client: ApolloClient<NormalizedCacheObject>,
  eventId: string
) => {
  try {
    const categoryData = await client.query<{ Category: CategoryType[] }>({
      query: listCategoriesForEventId,
      variables: {
        eventId: eventId,
      },
    });
    console.log(categoryData, ' categoryData inside listCategoriesForEvent');
    const categories = categoryData?.data?.Category;
    console.log(categories, ' successfully listed categories for event');
    return categories;
  } catch (e) {
    console.log(e, ' unable to listCategoriesForEvent');
  }
};

export const removeCategoryConnectionForEvent = async (
  client: ApolloClient<NormalizedCacheObject>,
  categoryId: string,
  eventId: string
) => {
  try {
    const { data } = await client.mutate<{
      delete_Category_Event: {
        affected_rows: number;
        returning: CategoryEventType[];
      };
    }>({
      mutation: removeCategoryEventConnection,
      variables: {
        categoryId,
        eventId,
      },
      // refetchQueries: [
      //   listCategoriesForEventId,
      //   'listCategoriesForEventId'
      // ],
      update(cache, { data }) {
        const normalizedIds = data?.delete_Category_Event?.returning?.map((c) =>
          cache.identify({ id: c.id, __typename: c.__typename })
        );
        normalizedIds.forEach((id) => cache.evict({ id }));
        cache.gc();
      },
    });

    console.log(data, ' successfully removed category connection for event');
    return data?.delete_Category_Event;
  } catch (e) {
    console.log(e, ' unable to remove category for event');
  }
};

export const removeAllCategoriesForEvent = async (
  client: ApolloClient<NormalizedCacheObject>,
  eventId: string
) => {
  try {
    const { data } = await client.mutate<{
      delete_Category_Event: {
        affected_rows: number;
        returning: CategoryEventType[];
      };
    }>({
      mutation: removeCategoriesForEvent,
      variables: {
        eventId,
      },
      // refetchQueries: [
      //   listCategoriesForEventId,
      //   'listCategoriesForEventId'
      // ],
      update(cache, { data }) {
        const normalizedIds = data?.delete_Category_Event?.returning?.map((c) =>
          cache.identify({ id: c.id, __typename: c.__typename })
        );
        normalizedIds.forEach((id) => cache.evict({ id }));
        cache.gc();
      },
    });

    console.log(data, ' successfully removed all categories for event');
  } catch (e) {
    console.log(e, ' unable to remove all categories for event');
  }
};

export const addCategoryToUser = async (
  client: ApolloClient<NormalizedCacheObject>,
  userId: string,
  name: string
) => {
  try {
    const newCategoryValue = {
      id: uuid(),
      userId,
      name,
      updatedAt: dayjs().toISOString(),
      createdDate: dayjs().toISOString(),
    };

    const { data } = await client.mutate<{ insert_Category_one: CategoryType }>(
      {
        mutation: createCategoryMutation,
        variables: newCategoryValue,
      }
    );

    console.log(data, ' successfully inserted category');
    return data?.insert_Category_one;
  } catch (e) {
    console.log(e, ' unable to add category to user');
  }
};

export const getCategoryWithId = async (
  client: ApolloClient<NormalizedCacheObject>,
  categoryId: string
) => {
  try {
    const { data } = await client.query<{
      Category_by_pk: CategoryType;
    }>({
      query: getCategoryById,
      variables: {
        id: categoryId,
      },
    });

    console.log(data, ' successfully got category with id');
    return data?.Category_by_pk;
  } catch (e) {
    console.log(e, ' unable to get category with id');
  }
};

export const updateCategoryHelper = async (
  client: ApolloClient<NormalizedCacheObject>,
  categoryId: string,
  name: string,
  copyAvailability?: boolean,
  copyTimeBlocking?: boolean,
  copyTimePreference?: boolean,
  copyReminders?: boolean,
  copyPriorityLevel?: boolean,
  copyModifiable?: boolean,
  defaultAvailability?: boolean,
  defaultTimeBlocking?: DefaultTimeBlockingType | null,
  defaultTimePreference?: DefaultTimePreferenceTypes | null,
  defaultReminders?: DefaultRemindersType | null,
  defaultPriorityLevel?: number,
  defaultModifiable?: boolean,
  copyIsBreak?: boolean,
  defaultIsBreak?: boolean,
  color?: string,
  copyIsMeeting?: boolean,
  copyIsExternalMeeting?: boolean,
  defaultIsMeeting?: boolean,
  defaultIsExternalMeeting?: boolean,
  defaultMeetingModifiable?: boolean,
  defaultExternalMeetingModifiable?: boolean
) => {
  try {
    const updateCategoryMutation = gql`
      mutation UpdateCategory(
        $id: uuid!, 
        ${name !== undefined ? '$name: String!,' : ''}
        ${color !== undefined ? '$color: String,' : ''}
        ${copyAvailability ? '$copyAvailability: Boolean,' : ''}
        ${copyIsBreak !== undefined ? '$copyIsBreak: Boolean,' : ''}
        ${copyIsExternalMeeting !== undefined ? '$copyIsExternalMeeting: Boolean,' : ''}
        ${copyIsMeeting !== undefined ? '$copyIsMeeting: Boolean,' : ''}
        ${copyModifiable !== undefined ? '$copyModifiable: Boolean,' : ''}
        ${copyPriorityLevel !== undefined ? '$copyPriorityLevel: Boolean,' : ''}
        ${copyReminders !== undefined ? '$copyReminders: Boolean,' : ''}
        ${copyTimeBlocking !== undefined ? '$copyTimeBlocking: Boolean,' : ''}
        ${copyTimePreference !== undefined ? '$copyTimePreference: Boolean,' : ''}
        ${defaultAvailability !== undefined ? '$defaultAvailability: Boolean,' : ''}
        ${defaultExternalMeetingModifiable !== undefined ? '$defaultExternalMeetingModifiable: Boolean,' : ''}
        ${defaultIsBreak !== undefined ? '$defaultIsBreak: Boolean,' : ''}
        ${defaultIsExternalMeeting !== undefined ? '$defaultIsExternalMeeting: Boolean,' : ''}
        ${defaultIsMeeting !== undefined ? '$defaultIsMeeting: Boolean,' : ''}
        ${defaultMeetingModifiable !== undefined ? '$defaultMeetingModifiable: Boolean,' : ''}
        ${defaultModifiable !== undefined ? '$defaultModifiable: Boolean,' : ''}
        ${defaultPriorityLevel !== undefined ? '$defaultPriorityLevel: Int,' : ''}
        ${defaultReminders !== undefined ? '$defaultReminders: jsonb,' : ''}
        ${defaultTimeBlocking !== undefined ? '$defaultTimeBlocking: jsonb,' : ''}
        ${defaultTimePreference !== undefined ? '$defaultTimePreference: jsonb,' : ''}
        $updatedAt: timestamptz,
      ) {
        update_Category_by_pk(pk_columns: {id: $id}, _set: {
          ${name !== undefined ? 'name: $name,' : ''} 
          updatedAt: $updatedAt, 
          ${color !== undefined ? 'color: $color,' : ''} 
          ${copyAvailability ? 'copyAvailability: $copyAvailability,' : ''} 
          ${copyIsBreak !== undefined ? 'copyIsBreak: $copyIsBreak,' : ''} 
          ${copyIsExternalMeeting !== undefined ? 'copyIsExternalMeeting: $copyIsExternalMeeting,' : ''} 
          ${copyIsMeeting !== undefined ? 'copyIsMeeting: $copyIsMeeting,' : ''} 
          ${copyModifiable !== undefined ? 'copyModifiable: $copyModifiable,' : ''} 
          ${copyPriorityLevel !== undefined ? 'copyPriorityLevel: $copyPriorityLevel,' : ''} 
          ${copyReminders !== undefined ? 'copyReminders: $copyReminders,' : ''} 
          ${copyTimeBlocking !== undefined ? 'copyTimeBlocking: $copyTimeBlocking,' : ''} 
          ${copyTimePreference !== undefined ? 'copyTimePreference: $copyTimePreference,' : ''} 
          ${defaultAvailability !== undefined ? 'defaultAvailability: $defaultAvailability,' : ''} 
          ${defaultExternalMeetingModifiable !== undefined ? 'defaultExternalMeetingModifiable: $defaultExternalMeetingModifiable,' : ''} 
          ${defaultIsBreak !== undefined ? 'defaultIsBreak: $defaultIsBreak,' : ''} 
          ${defaultIsExternalMeeting !== undefined ? 'defaultIsExternalMeeting: $defaultIsExternalMeeting,' : ''} 
          ${defaultIsMeeting !== undefined ? 'defaultIsMeeting: $defaultIsMeeting,' : ''} 
          ${defaultMeetingModifiable !== undefined ? 'defaultMeetingModifiable: $defaultMeetingModifiable,' : ''} 
          ${defaultModifiable !== undefined ? 'defaultModifiable: $defaultModifiable,' : ''} 
          ${defaultPriorityLevel !== undefined ? 'defaultPriorityLevel: $defaultPriorityLevel,' : ''} 
          ${defaultReminders !== undefined ? 'defaultReminders: $defaultReminders,' : ''} 
          ${defaultTimeBlocking !== undefined ? 'defaultTimeBlocking: $defaultTimeBlocking,' : ''} 
          ${defaultTimePreference !== undefined ? 'defaultTimePreference: $defaultTimePreference,' : ''}
        }) {
          id
          name
          deleted
          createdDate
          updatedAt
          userId
          copyAvailability
          copyTimeBlocking
          copyTimePreference
          copyReminders
          copyPriorityLevel
          copyModifiable
          defaultAvailability
          defaultTimeBlocking
          defaultTimePreference
          defaultReminders
          defaultPriorityLevel
          defaultModifiable
          copyIsBreak
          defaultIsBreak
          color
          copyIsMeeting
          copyIsExternalMeeting
          defaultIsMeeting
          defaultIsExternalMeeting
          defaultMeetingModifiable
          defaultExternalMeetingModifiable
        }
      }
    `;

    const variables: any = {
      id: categoryId,
      updatedAt: new Date().toISOString(),
    };

    if (name !== undefined) {
      variables.name = name;
    }

    if (color !== undefined) {
      variables.color = color;
    }

    if (copyAvailability !== undefined) {
      variables.copyAvailability = copyAvailability;
    }

    if (copyIsBreak !== undefined) {
      variables.copyIsBreak = copyIsBreak;
    }

    if (copyIsExternalMeeting !== undefined) {
      variables.copyIsExternalMeeting = copyIsExternalMeeting;
    }

    if (copyIsMeeting !== undefined) {
      variables.copyIsMeeting = copyIsMeeting;
    }

    if (copyModifiable !== undefined) {
      variables.copyModifiable = copyModifiable;
    }

    if (copyPriorityLevel !== undefined) {
      variables.copyPriorityLevel = copyPriorityLevel;
    }

    if (copyReminders !== undefined) {
      variables.copyReminders = copyReminders;
    }

    if (copyTimeBlocking !== undefined) {
      variables.copyTimeBlocking = copyTimeBlocking;
    }

    if (copyTimePreference !== undefined) {
      variables.copyTimePreference = copyTimePreference;
    }

    if (defaultAvailability !== undefined) {
      variables.defaultAvailability = defaultAvailability;
    }

    if (defaultExternalMeetingModifiable !== undefined) {
      variables.defaultExternalMeetingModifiable =
        defaultExternalMeetingModifiable;
    }

    if (defaultIsBreak !== undefined) {
      variables.defaultIsBreak = defaultIsBreak;
    }

    if (defaultIsExternalMeeting !== undefined) {
      variables.defaultIsExternalMeeting = defaultIsExternalMeeting;
    }

    if (defaultIsMeeting !== undefined) {
      variables.defaultIsMeeting = defaultIsMeeting;
    }

    if (defaultMeetingModifiable !== undefined) {
      variables.defaultMeetingModifiable = defaultMeetingModifiable;
    }

    if (defaultModifiable !== undefined) {
      variables.defaultModifiable = defaultModifiable;
    }

    if (defaultPriorityLevel !== undefined) {
      variables.defaultPriorityLevel = defaultPriorityLevel;
    }

    if (defaultReminders !== undefined) {
      variables.defaultReminders = defaultReminders;
    }

    if (defaultTimeBlocking !== undefined) {
      variables.defaultTimeBlocking = defaultTimeBlocking;
    }

    if (defaultTimePreference !== undefined) {
      variables.defaultTimePreference = defaultTimePreference;
    }

    const { data } = await client.mutate<{
      update_Category_by_pk: CategoryType;
    }>({
      mutation: updateCategoryMutation,
      variables,
    });

    return data.update_Category_by_pk;
  } catch (e) {
    console.log(e, ' unable to update category');
  }
};

/**
End */
