"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.updateCategoryHelper = exports.getCategoryWithId = exports.addCategoryToUser = exports.removeAllCategoriesForEvent = exports.removeCategoryConnectionForEvent = exports.listCategoriesForEvent = exports.listEventsForCategory = exports.upsertCategoryEventConnection = exports.removeEventConnectionsForCategory = exports.removeCategory = exports.updateCategoryName = exports.listUserCategories = exports.createCategory = void 0;
const uuid_1 = require("uuid");
const date_utils_1 = require("@lib/date-utils");
// dayjs.extend(utc)
const client_1 = require("@apollo/client");
const removeCategoriesForEvent_1 = __importDefault(require("@lib/apollo/gql/removeCategoriesForEvent"));
const createCategoryMutation_1 = __importDefault(require("@lib/apollo/gql/createCategoryMutation"));
const listCategoriesForUser_1 = __importDefault(require("@lib/apollo/gql/listCategoriesForUser"));
const updateCategoryForName_1 = __importDefault(require("@lib/apollo/gql/updateCategoryForName"));
const deleteCategoryById_1 = __importDefault(require("@lib/apollo/gql/deleteCategoryById"));
const removeEventConnectionsForCategoryMutation_1 = __importDefault(require("@lib/apollo/gql/removeEventConnectionsForCategoryMutation"));
const listCategoriesForEventId_1 = __importDefault(require("@lib/apollo/gql/listCategoriesForEventId"));
const listEventsForCategoryQuery_1 = __importDefault(require("@lib/apollo/gql/listEventsForCategoryQuery"));
const removeCategoryEventConnection_1 = __importDefault(require("@lib/apollo/gql/removeCategoryEventConnection"));
const getCategoryById_1 = __importDefault(require("@lib/apollo/gql/getCategoryById"));
// import {
//   category_eventType,
// } from '@dataTypes/category_eventType'
// import {
//   CategoryType,
// } from '@dataTypes/CategoryType'
const createCategory = async (client, category, userId) => {
    try {
        const newCategoryValue = {
            id: (0, uuid_1.v4)(),
            userId,
            name: category,
            updatedAt: (0, date_utils_1.dayjs)().toISOString(),
            createdDate: (0, date_utils_1.dayjs)().toISOString(),
        };
        const { data } = await client.mutate({
            mutation: createCategoryMutation_1.default,
            variables: newCategoryValue,
        });
        console.log(data, ' successfully inserted category');
        return data?.insert_Category_one;
    }
    catch (e) {
        console.log(e, ' unable to create category');
    }
};
exports.createCategory = createCategory;
const listUserCategories = async (client, userId) => {
    try {
        const { data } = await client.query({
            query: listCategoriesForUser_1.default,
            variables: {
                userId,
            },
            fetchPolicy: 'no-cache',
        });
        console.log(data, ' successfully listed categories');
        return data?.Category;
    }
    catch (e) {
        console.log(e, ' unable to listUserCategories');
    }
};
exports.listUserCategories = listUserCategories;
const updateCategoryName = async (client, newName, categoryId) => {
    try {
        const { data } = await client.mutate({
            mutation: updateCategoryForName_1.default,
            variables: {
                id: categoryId,
                name: newName,
                updatedAt: (0, date_utils_1.dayjs)().toISOString(),
            },
        });
        console.log(data, ' successfully updated category');
        return data?.update_Category_by_pk;
    }
    catch (e) {
        console.log(e, ' unable to update category');
    }
};
exports.updateCategoryName = updateCategoryName;
const removeCategory = async (client, categoryId) => {
    try {
        const { data } = await client.mutate({
            mutation: deleteCategoryById_1.default,
            variables: {
                id: categoryId,
            },
        });
        console.log(data, ' successfully removed category');
        return data?.delete_Category_by_pk;
    }
    catch (e) {
        console.log(e, ' unable to remove category');
    }
};
exports.removeCategory = removeCategory;
const removeEventConnectionsForCategory = async (client, categoryId) => {
    try {
        const { data } = await client.mutate({
            mutation: removeEventConnectionsForCategoryMutation_1.default,
            variables: {
                categoryId,
            },
            // refetchQueries: [
            //   listCategoriesForEventId,
            //   'listCategoriesForEventId'
            // ],
            update(cache, { data }) {
                const deletedCategoryEvents = data?.delete_Category_Event?.returning;
                const normalizedIds = deletedCategoryEvents.map((c) => cache.identify({ id: c.id, __typename: c.__typename }));
                normalizedIds.forEach((id) => cache.evict({ id }));
                cache.gc();
            },
        });
        console.log(data, ' successfully removed event connections for category');
        return data?.delete_Category_Event;
    }
    catch (e) {
        console.log(e, ' unable to remove events for category');
    }
};
exports.removeEventConnectionsForCategory = removeEventConnectionsForCategory;
const upsertCategoryEventConnection = async (client, userId, categoryId, eventId) => {
    try {
        console.log(categoryId, ' categoryId inside upsertCategoryEventConnection');
        const upsertCategoryEvent = (0, client_1.gql) `
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
                    id: (0, uuid_1.v4)(),
                    userId,
                    categoryId,
                    eventId,
                    deleted: false,
                    updatedAt: (0, date_utils_1.dayjs)().toISOString(),
                    createdDate: (0, date_utils_1.dayjs)().toISOString(),
                },
            ],
        };
        const { data } = await client.mutate({
            mutation: upsertCategoryEvent,
            variables,
            update(cache, { data }) {
                if (data?.insert_Category_Event?.affected_rows > 0) {
                    console.log('insert_Category_Event', data);
                }
                cache.modify({
                    fields: {
                        Category_Event(existingCategoryEvents = []) {
                            const newCategoryEventRefs = data?.insert_Category_Event?.returning.map((c) => cache.writeFragment({
                                data: c,
                                fragment: (0, client_1.gql) `
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
                            }));
                            return [...existingCategoryEvents, ...newCategoryEventRefs];
                        },
                    },
                });
            },
        });
        console.log(data, ' successfully upserted category event connection');
    }
    catch (e) {
        console.log(e, ' unable to create category event');
    }
};
exports.upsertCategoryEventConnection = upsertCategoryEventConnection;
const listEventsForCategory = async (client, categoryId) => {
    try {
        const { data } = await client.query({
            query: listEventsForCategoryQuery_1.default,
            variables: {
                categoryId,
            },
        });
        console.log(data, ' successfully listed events for category');
        return data?.Event;
    }
    catch (e) {
        console.log(e, ' unable to listEventsForCategory');
    }
};
exports.listEventsForCategory = listEventsForCategory;
const listCategoriesForEvent = async (client, eventId) => {
    try {
        const categoryData = await client.query({
            query: listCategoriesForEventId_1.default,
            variables: {
                eventId: eventId,
            },
        });
        console.log(categoryData, ' categoryData inside listCategoriesForEvent');
        const categories = categoryData?.data?.Category;
        console.log(categories, ' successfully listed categories for event');
        return categories;
    }
    catch (e) {
        console.log(e, ' unable to listCategoriesForEvent');
    }
};
exports.listCategoriesForEvent = listCategoriesForEvent;
const removeCategoryConnectionForEvent = async (client, categoryId, eventId) => {
    try {
        const { data } = await client.mutate({
            mutation: removeCategoryEventConnection_1.default,
            variables: {
                categoryId,
                eventId,
            },
            // refetchQueries: [
            //   listCategoriesForEventId,
            //   'listCategoriesForEventId'
            // ],
            update(cache, { data }) {
                const normalizedIds = data?.delete_Category_Event?.returning?.map((c) => cache.identify({ id: c.id, __typename: c.__typename }));
                normalizedIds.forEach((id) => cache.evict({ id }));
                cache.gc();
            },
        });
        console.log(data, ' successfully removed category connection for event');
        return data?.delete_Category_Event;
    }
    catch (e) {
        console.log(e, ' unable to remove category for event');
    }
};
exports.removeCategoryConnectionForEvent = removeCategoryConnectionForEvent;
const removeAllCategoriesForEvent = async (client, eventId) => {
    try {
        const { data } = await client.mutate({
            mutation: removeCategoriesForEvent_1.default,
            variables: {
                eventId,
            },
            // refetchQueries: [
            //   listCategoriesForEventId,
            //   'listCategoriesForEventId'
            // ],
            update(cache, { data }) {
                const normalizedIds = data?.delete_Category_Event?.returning?.map((c) => cache.identify({ id: c.id, __typename: c.__typename }));
                normalizedIds.forEach((id) => cache.evict({ id }));
                cache.gc();
            },
        });
        console.log(data, ' successfully removed all categories for event');
    }
    catch (e) {
        console.log(e, ' unable to remove all categories for event');
    }
};
exports.removeAllCategoriesForEvent = removeAllCategoriesForEvent;
const addCategoryToUser = async (client, userId, name) => {
    try {
        const newCategoryValue = {
            id: (0, uuid_1.v4)(),
            userId,
            name,
            updatedAt: (0, date_utils_1.dayjs)().toISOString(),
            createdDate: (0, date_utils_1.dayjs)().toISOString(),
        };
        const { data } = await client.mutate({
            mutation: createCategoryMutation_1.default,
            variables: newCategoryValue,
        });
        console.log(data, ' successfully inserted category');
        return data?.insert_Category_one;
    }
    catch (e) {
        console.log(e, ' unable to add category to user');
    }
};
exports.addCategoryToUser = addCategoryToUser;
const getCategoryWithId = async (client, categoryId) => {
    try {
        const { data } = await client.query({
            query: getCategoryById_1.default,
            variables: {
                id: categoryId,
            },
        });
        console.log(data, ' successfully got category with id');
        return data?.Category_by_pk;
    }
    catch (e) {
        console.log(e, ' unable to get category with id');
    }
};
exports.getCategoryWithId = getCategoryWithId;
const updateCategoryHelper = async (client, categoryId, name, copyAvailability, copyTimeBlocking, copyTimePreference, copyReminders, copyPriorityLevel, copyModifiable, defaultAvailability, defaultTimeBlocking, defaultTimePreference, defaultReminders, defaultPriorityLevel, defaultModifiable, copyIsBreak, defaultIsBreak, color, copyIsMeeting, copyIsExternalMeeting, defaultIsMeeting, defaultIsExternalMeeting, defaultMeetingModifiable, defaultExternalMeetingModifiable) => {
    try {
        const updateCategoryMutation = (0, client_1.gql) `
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
        const variables = {
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
        const { data } = await client.mutate({
            mutation: updateCategoryMutation,
            variables,
        });
        return data.update_Category_by_pk;
    }
    catch (e) {
        console.log(e, ' unable to update category');
    }
};
exports.updateCategoryHelper = updateCategoryHelper;
/**
End */
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiQ2F0ZWdvcnlIZWxwZXIuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJDYXRlZ29yeUhlbHBlci50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOzs7Ozs7QUFBQSwrQkFBa0M7QUFFbEMsZ0RBQXdDO0FBRXhDLG9CQUFvQjtBQUVwQiwyQ0FBMEU7QUFFMUUsd0dBQWdGO0FBT2hGLG9HQUE0RTtBQUM1RSxrR0FBMEU7QUFDMUUsa0dBQTBFO0FBQzFFLDRGQUFvRTtBQUNwRSwwSUFBa0g7QUFDbEgsd0dBQWdGO0FBQ2hGLDRHQUFvRjtBQUNwRixrSEFBMEY7QUFDMUYsc0ZBQThEO0FBRzlELFdBQVc7QUFDWCx3QkFBd0I7QUFDeEIseUNBQXlDO0FBQ3pDLFdBQVc7QUFDWCxrQkFBa0I7QUFDbEIsbUNBQW1DO0FBRTVCLE1BQU0sY0FBYyxHQUFHLEtBQUssRUFDakMsTUFBMkMsRUFDM0MsUUFBZ0IsRUFDaEIsTUFBYyxFQUNkLEVBQUU7SUFDRixJQUFJLENBQUM7UUFDSCxNQUFNLGdCQUFnQixHQUFHO1lBQ3ZCLEVBQUUsRUFBRSxJQUFBLFNBQUksR0FBRTtZQUNWLE1BQU07WUFDTixJQUFJLEVBQUUsUUFBUTtZQUNkLFNBQVMsRUFBRSxJQUFBLGtCQUFLLEdBQUUsQ0FBQyxXQUFXLEVBQUU7WUFDaEMsV0FBVyxFQUFFLElBQUEsa0JBQUssR0FBRSxDQUFDLFdBQVcsRUFBRTtTQUNuQyxDQUFDO1FBRUYsTUFBTSxFQUFFLElBQUksRUFBRSxHQUFHLE1BQU0sTUFBTSxDQUFDLE1BQU0sQ0FDbEM7WUFDRSxRQUFRLEVBQUUsZ0NBQXNCO1lBQ2hDLFNBQVMsRUFBRSxnQkFBZ0I7U0FDNUIsQ0FDRixDQUFDO1FBRUYsT0FBTyxDQUFDLEdBQUcsQ0FBQyxJQUFJLEVBQUUsaUNBQWlDLENBQUMsQ0FBQztRQUNyRCxPQUFPLElBQUksRUFBRSxtQkFBbUIsQ0FBQztJQUNuQyxDQUFDO0lBQUMsT0FBTyxDQUFDLEVBQUUsQ0FBQztRQUNYLE9BQU8sQ0FBQyxHQUFH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Q0FBQztRQUN0RCxDQUFDO1FBRUQsSUFBSSxxQkFBcUIsS0FBSyxTQUFTLEVBQUUsQ0FBQztZQUN4QyxTQUFTLENBQUMscUJBQXFCLEdBQUcscUJBQXFCLENBQUM7UUFDMUQsQ0FBQztRQUVELE1BQU0sRUFBRSxJQUFJLEVBQUUsR0FBRyxNQUFNLE1BQU0sQ0FBQyxNQUFNLENBRWpDO1lBQ0QsUUFBUSxFQUFFLHNCQUFzQjtZQUNoQyxTQUFTO1NBQ1YsQ0FBQyxDQUFDO1FBRUgsT0FBTyxJQUFJLENBQUMscUJBQXFCLENBQUM7SUFDcEMsQ0FBQztJQUFDLE9BQU8sQ0FBQyxFQUFFLENBQUM7UUFDWCxPQUFPLENBQUMsR0FBRyxDQUFDLENBQUMsRUFBRSw0QkFBNEIsQ0FBQyxDQUFDO0lBQy9DLENBQUM7QUFDSCxDQUFDLENBQUM7QUF2TlcsUUFBQSxvQkFBb0Isd0JBdU4vQjtBQUVGO01BQ00iLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgeyB2NCBhcyB1dWlkIH0gZnJvbSAndXVpZCc7XG5cbmltcG9ydCB7IGRheWpzIH0gZnJvbSAnQGxpYi9kYXRlLXV0aWxzJztcblxuLy8gZGF5anMuZXh0ZW5kKHV0YylcblxuaW1wb3J0IHsgQXBvbGxvQ2xpZW50LCBncWwsIE5vcm1hbGl6ZWRDYWNoZU9iamVjdCB9IGZyb20gJ0BhcG9sbG8vY2xpZW50JztcbmltcG9ydCB7IEV2ZW50VHlwZSB9IGZyb20gJ0BsaWIvZGF0YVR5cGVzL0V2ZW50VHlwZSc7XG5pbXBvcnQgcmVtb3ZlQ2F0ZWdvcmllc0ZvckV2ZW50IGZyb20gJ0BsaWIvYXBvbGxvL2dxbC9yZW1vdmVDYXRlZ29yaWVzRm9yRXZlbnQnO1xuaW1wb3J0IHtcbiAgQ2F0ZWdvcnlUeXBlLFxuICBEZWZhdWx0UmVtaW5kZXJzVHlwZSxcbiAgRGVmYXVsdFRpbWVCbG9ja2luZ1R5cGUsXG4gIERlZmF1bHRUaW1lUHJlZmVyZW5jZVR5cGVzLFxufSBmcm9tICdAbGliL2RhdGFUeXBlcy9DYXRlZ29yeVR5cGUnO1xuaW1wb3J0IGNyZWF0ZUNhdGVnb3J5TXV0YXRpb24gZnJvbSAnQGxpYi9hcG9sbG8vZ3FsL2NyZWF0ZUNhdGVnb3J5TXV0YXRpb24nO1xuaW1wb3J0IGxpc3RDYXRlZ29yaWVzRm9yVXNlciBmcm9tICdAbGliL2Fwb2xsby9ncWwvbGlzdENhdGVnb3JpZXNGb3JVc2VyJztcbmltcG9ydCB1cGRhdGVDYXRlZ29yeUZvck5hbWUgZnJvbSAnQGxpYi9hcG9sbG8vZ3FsL3VwZGF0ZUNhdGVnb3J5Rm9yTmFtZSc7XG5pbXBvcnQgZGVsZXRlQ2F0ZWdvcnlCeUlkIGZyb20gJ0BsaWIvYXBvbGxvL2dxbC9kZWxldGVDYXRlZ29yeUJ5SWQnO1xuaW1wb3J0IHJlbW92ZUV2ZW50Q29ubmVjdGlvbnNGb3JDYXRlZ29yeU11dGF0aW9uIGZyb20gJ0BsaWIvYXBvbGxvL2dxbC9yZW1vdmVFdmVudENvbm5lY3Rpb25zRm9yQ2F0ZWdvcnlNdXRhdGlvbic7XG5pbXBvcnQgbGlzdENhdGVnb3JpZXNGb3JFdmVudElkIGZyb20gJ0BsaWIvYXBvbGxvL2dxbC9saXN0Q2F0ZWdvcmllc0ZvckV2ZW50SWQnO1xuaW1wb3J0IGxpc3RFdmVudHNGb3JDYXRlZ29yeVF1ZXJ5IGZyb20gJ0BsaWIvYXBvbGxvL2dxbC9saXN0RXZlbnRzRm9yQ2F0ZWdvcnlRdWVyeSc7XG5pbXBvcnQgcmVtb3ZlQ2F0ZWdvcnlFdmVudENvbm5lY3Rpb24gZnJvbSAnQGxpYi9hcG9sbG8vZ3FsL3JlbW92ZUNhdGVnb3J5RXZlbnRDb25uZWN0aW9uJztcbmltcG9ydCBnZXRDYXRlZ29yeUJ5SWQgZnJvbSAnQGxpYi9hcG9sbG8vZ3FsL2dldENhdGVnb3J5QnlJZCc7XG5pbXBvcnQgeyBDYXRlZ29yeUV2ZW50VHlwZSB9IGZyb20gJ0BsaWIvZGF0YVR5cGVzL0NhdGVnb3J5X0V2ZW50VHlwZSc7XG5pbXBvcnQgXyBmcm9tICdsb2Rhc2gnO1xuLy8gaW1wb3J0IHtcbi8vICAgY2F0ZWdvcnlfZXZlbnRUeXBlLFxuLy8gfSBmcm9tICdAZGF0YVR5cGVzL2NhdGVnb3J5X2V2ZW50VHlwZSdcbi8vIGltcG9ydCB7XG4vLyAgIENhdGVnb3J5VHlwZSxcbi8vIH0gZnJvbSAnQGRhdGFUeXBlcy9DYXRlZ29yeVR5cGUnXG5cbmV4cG9ydCBjb25zdCBjcmVhdGVDYXRlZ29yeSA9IGFzeW5jIChcbiAgY2xpZW50OiBBcG9sbG9DbGllbnQ8Tm9ybWFsaXplZENhY2hlT2JqZWN0PixcbiAgY2F0ZWdvcnk6IHN0cmluZyxcbiAgdXNlcklkOiBzdHJpbmdcbikgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IG5ld0NhdGVnb3J5VmFsdWUgPSB7XG4gICAgICBpZDogdXVpZCgpLFxuICAgICAgdXNlcklkLFxuICAgICAgbmFtZTogY2F0ZWdvcnksXG4gICAgICB1cGRhdGVkQXQ6IGRheWpzKCkudG9JU09TdHJpbmcoKSxcbiAgICAgIGNyZWF0ZWREYXRlOiBkYXlqcygpLnRvSVNPU3RyaW5nKCksXG4gICAgfTtcblxuICAgIGNvbnN0IHsgZGF0YSB9ID0gYXdhaXQgY2xpZW50Lm11dGF0ZTx7IGluc2VydF9DYXRlZ29yeV9vbmU6IENhdGVnb3J5VHlwZSB9PihcbiAgICAgIHtcbiAgICAgICAgbXV0YXRpb246IGNyZWF0ZUNhdGVnb3J5TXV0YXRpb24sXG4gICAgICAgIHZhcmlhYmxlczogbmV3Q2F0ZWdvcnlWYWx1ZSxcbiAgICAgIH1cbiAgICApO1xuXG4gICAgY29uc29sZS5sb2coZGF0YSwgJyBzdWNjZXNzZnVsbHkgaW5zZXJ0ZWQgY2F0ZWdvcnknKTtcbiAgICByZXR1cm4gZGF0YT8uaW5zZXJ0X0NhdGVnb3J5X29uZTtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIGNyZWF0ZSBjYXRlZ29yeScpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgbGlzdFVzZXJDYXRlZ29yaWVzID0gYXN5bmMgKFxuICBjbGllbnQ6IEFwb2xsb0NsaWVudDxOb3JtYWxpemVkQ2FjaGVPYmplY3Q+LFxuICB1c2VySWQ6IHN0cmluZ1xuKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3QgeyBkYXRhIH0gPSBhd2FpdCBjbGllbnQucXVlcnk8e1xuICAgICAgQ2F0ZWdvcnk6IENhdGVnb3J5VHlwZVtdO1xuICAgIH0+KHtcbiAgICAgIHF1ZXJ5OiBsaXN0Q2F0ZWdvcmllc0ZvclVzZXIsXG4gICAgICB2YXJpYWJsZXM6IHtcbiAgICAgICAgdXNlcklkLFxuICAgICAgfSxcbiAgICAgIGZldGNoUG9saWN5OiAnbm8tY2FjaGUnLFxuICAgIH0pO1xuXG4gICAgY29uc29sZS5sb2coZGF0YSwgJyBzdWNjZXNzZnVsbHkgbGlzdGVkIGNhdGVnb3JpZXMnKTtcbiAgICByZXR1cm4gZGF0YT8uQ2F0ZWdvcnk7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBsaXN0VXNlckNhdGVnb3JpZXMnKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IHVwZGF0ZUNhdGVnb3J5TmFtZSA9IGFzeW5jIChcbiAgY2xpZW50OiBBcG9sbG9DbGllbnQ8Tm9ybWFsaXplZENhY2hlT2JqZWN0PixcbiAgbmV3TmFtZTogc3RyaW5nLFxuICBjYXRlZ29yeUlkOiBzdHJpbmdcbikgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IHsgZGF0YSB9ID0gYXdhaXQgY2xpZW50Lm11dGF0ZTx7XG4gICAgICB1cGRhdGVfQ2F0ZWdvcnlfYnlfcGs6IENhdGVnb3J5VHlwZTtcbiAgICB9Pih7XG4gICAgICBtdXRhdGlvbjogdXBkYXRlQ2F0ZWdvcnlGb3JOYW1lLFxuICAgICAgdmFyaWFibGVzOiB7XG4gICAgICAgIGlkOiBjYXRlZ29yeUlkLFxuICAgICAgICBuYW1lOiBuZXdOYW1lLFxuICAgICAgICB1cGRhdGVkQXQ6IGRheWpzKCkudG9JU09TdHJpbmcoKSxcbiAgICAgIH0sXG4gICAgfSk7XG5cbiAgICBjb25zb2xlLmxvZyhkYXRhLCAnIHN1Y2Nlc3NmdWxseSB1cGRhdGVkIGNhdGVnb3J5Jyk7XG4gICAgcmV0dXJuIGRhdGE/LnVwZGF0ZV9DYXRlZ29yeV9ieV9waztcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIHVwZGF0ZSBjYXRlZ29yeScpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgcmVtb3ZlQ2F0ZWdvcnkgPSBhc3luYyAoXG4gIGNsaWVudDogQXBvbGxvQ2xpZW50PE5vcm1hbGl6ZWRDYWNoZU9iamVjdD4sXG4gIGNhdGVnb3J5SWQ6IHN0cmluZ1xuKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3QgeyBkYXRhIH0gPSBhd2FpdCBjbGllbnQubXV0YXRlPHtcbiAgICAgIGRlbGV0ZV9DYXRlZ29yeV9ieV9wazogQ2F0ZWdvcnlUeXBlO1xuICAgIH0+KHtcbiAgICAgIG11dGF0aW9uOiBkZWxldGVDYXRlZ29yeUJ5SWQsXG4gICAgICB2YXJpYWJsZXM6IHtcbiAgICAgICAgaWQ6IGNhdGVnb3J5SWQsXG4gICAgICB9LFxuICAgIH0pO1xuXG4gICAgY29uc29sZS5sb2coZGF0YSwgJyBzdWNjZXNzZnVsbHkgcmVtb3ZlZCBjYXRlZ29yeScpO1xuICAgIHJldHVybiBkYXRhPy5kZWxldGVfQ2F0ZWdvcnlfYnlfcGs7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byByZW1vdmUgY2F0ZWdvcnknKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IHJlbW92ZUV2ZW50Q29ubmVjdGlvbnNGb3JDYXRlZ29yeSA9IGFzeW5jIChcbiAgY2xpZW50OiBBcG9sbG9DbGllbnQ8Tm9ybWFsaXplZENhY2hlT2JqZWN0PixcbiAgY2F0ZWdvcnlJZDogc3RyaW5nXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCB7IGRhdGEgfSA9IGF3YWl0IGNsaWVudC5tdXRhdGU8e1xuICAgICAgZGVsZXRlX0NhdGVnb3J5X0V2ZW50OiB7XG4gICAgICAgIGFmZmVjdGVkX3Jvd3M6IG51bWJlcjtcbiAgICAgICAgcmV0dXJuaW5nOiBDYXRlZ29yeUV2ZW50VHlwZVtdO1xuICAgICAgfTtcbiAgICB9Pih7XG4gICAgICBtdXRhdGlvbjogcmVtb3ZlRXZlbnRDb25uZWN0aW9uc0ZvckNhdGVnb3J5TXV0YXRpb24sXG4gICAgICB2YXJpYWJsZXM6IHtcbiAgICAgICAgY2F0ZWdvcnlJZCxcbiAgICAgIH0sXG4gICAgICAvLyByZWZldGNoUXVlcmllczogW1xuICAgICAgLy8gICBsaXN0Q2F0ZWdvcmllc0ZvckV2ZW50SWQsXG4gICAgICAvLyAgICdsaXN0Q2F0ZWdvcmllc0ZvckV2ZW50SWQnXG4gICAgICAvLyBdLFxuICAgICAgdXBkYXRlKGNhY2hlLCB7IGRhdGEgfSkge1xuICAgICAgICBjb25zdCBkZWxldGVkQ2F0ZWdvcnlFdmVudHMgPSBkYXRhPy5kZWxldGVfQ2F0ZWdvcnlfRXZlbnQ/LnJldHVybmluZztcbiAgICAgICAgY29uc3Qgbm9ybWFsaXplZElkcyA9IGRlbGV0ZWRDYXRlZ29yeUV2ZW50cy5tYXAoKGMpID0+XG4gICAgICAgICAgY2FjaGUuaWRlbnRpZnkoeyBpZDogYy5pZCwgX190eXBlbmFtZTogYy5fX3R5cGVuYW1lIH0pXG4gICAgICAgICk7XG4gICAgICAgIG5vcm1hbGl6ZWRJZHMuZm9yRWFjaCgoaWQpID0+IGNhY2hlLmV2aWN0KHsgaWQgfSkpO1xuICAgICAgICBjYWNoZS5nYygpO1xuICAgICAgfSxcbiAgICB9KTtcblxuICAgIGNvbnNvbGUubG9nKGRhdGEsICcgc3VjY2Vzc2Z1bGx5IHJlbW92ZWQgZXZlbnQgY29ubmVjdGlvbnMgZm9yIGNhdGVnb3J5Jyk7XG4gICAgcmV0dXJuIGRhdGE/LmRlbGV0ZV9DYXRlZ29yeV9FdmVudDtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIHJlbW92ZSBldmVudHMgZm9yIGNhdGVnb3J5Jyk7XG4gIH1cbn07XG5leHBvcnQgY29uc3QgdXBzZXJ0Q2F0ZWdvcnlFdmVudENvbm5lY3Rpb24gPSBhc3luYyAoXG4gIGNsaWVudDogQXBvbGxvQ2xpZW50PE5vcm1hbGl6ZWRDYWNoZU9iamVjdD4sXG4gIHVzZXJJZDogc3RyaW5nLFxuICBjYXRlZ29yeUlkOiBzdHJpbmcsXG4gIGV2ZW50SWQ6IHN0cmluZ1xuKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc29sZS5sb2coY2F0ZWdvcnlJZCwgJyBjYXRlZ29yeUlkIGluc2lkZSB1cHNlcnRDYXRlZ29yeUV2ZW50Q29ubmVjdGlvbicpO1xuICAgIGNvbnN0IHVwc2VydENhdGVnb3J5RXZlbnQgPSBncWxgXG4gICAgICAgIG11dGF0aW9uIEluc2VydENhdGVnb3J5X0V2ZW50KCRjYXRlZ29yeV9ldmVudHM6IFtDYXRlZ29yeV9FdmVudF9pbnNlcnRfaW5wdXQhXSEpIHtcbiAgICAgICAgICBpbnNlcnRfQ2F0ZWdvcnlfRXZlbnQoXG4gICAgICAgICAgICBvYmplY3RzOiAkY2F0ZWdvcnlfZXZlbnRzLFxuICAgICAgICAgICAgb25fY29uZmxpY3Q6IHtcbiAgICAgICAgICAgICAgICBjb25zdHJhaW50OiBDYXRlZ29yeV9FdmVudF9wa2V5LFxuICAgICAgICAgICAgICAgIHVwZGF0ZV9jb2x1bW5zOiBbXG4gICAgICAgICAgICAgICAgICAke2NhdGVnb3J5SWQgPyAnY2F0ZWdvcnlJZCwnIDogJyd9XG4gICAgICAgICAgICAgICAgICAke2V2ZW50SWQgPyAnZXZlbnRJZCwnIDogJyd9IFxuICAgICAgICAgICAgICAgICAgZGVsZXRlZCwgXG4gICAgICAgICAgICAgICAgICB1cGRhdGVkQXQsXG4gICAgICAgICAgICAgICAgXVxuICAgICAgICAgICAgfSl7XG4gICAgICAgICAgICByZXR1cm5pbmcge1xuICAgICAgICAgICAgICBpZFxuICAgICAgICAgICAgICBjYXRlZ29yeUlkXG4gICAgICAgICAgICAgIGNyZWF0ZWREYXRlXG4gICAgICAgICAgICAgIGRlbGV0ZWRcbiAgICAgICAgICAgICAgZXZlbnRJZFxuICAgICAgICAgICAgICB1cGRhdGVkQXRcbiAgICAgICAgICAgICAgdXNlcklkXG4gICAgICAgICAgICAgIENhdGVnb3J5IHtcbiAgICAgICAgICAgICAgICBjb2xvclxuICAgICAgICAgICAgICAgIGNvcHlBdmFpbGFiaWxpdHlcbiAgICAgICAgICAgICAgICBjb3B5SXNCcmVha1xuICAgICAgICAgICAgICAgIGNvcHlJc0V4dGVybmFsTWVldGluZ1xuICAgICAgICAgICAgICAgIGNvcHlJc01lZXRpbmdcbiAgICAgICAgICAgICAgICBjb3B5TW9kaWZpYWJsZVxuICAgICAgICAgICAgICAgIGNvcHlQcmlvcml0eUxldmVsXG4gICAgICAgICAgICAgICAgY29weVJlbWluZGVyc1xuICAgICAgICAgICAgICAgIGNvcHlUaW1lQmxvY2tpbmdcbiAgICAgICAgICAgICAgICBjb3B5VGltZVByZWZlcmVuY2VcbiAgICAgICAgICAgICAgICBjcmVhdGVkRGF0ZVxuICAgICAgICAgICAgICAgIGRlZmF1bHRBdmFpbGFiaWxpdHlcbiAgICAgICAgICAgICAgICBkZWZhdWx0RXh0ZXJuYWxNZWV0aW5nTW9kaWZpYWJsZVxuICAgICAgICAgICAgICAgIGRlZmF1bHRJc0JyZWFrXG4gICAgICAgICAgICAgICAgZGVmYXVsdElzRXh0ZXJuYWxNZWV0aW5nXG4gICAgICAgICAgICAgICAgZGVmYXVsdElzTWVldGluZ1xuICAgICAgICAgICAgICAgIGRlZmF1bHRNZWV0aW5nTW9kaWZpYWJsZVxuICAgICAgICAgICAgICAgIGRlZmF1bHRNb2RpZmlhYmxlXG4gICAgICAgICAgICAgICAgZGVmYXVsdFByaW9yaXR5TGV2ZWxcbiAgICAgICAgICAgICAgICBkZWZhdWx0UmVtaW5kZXJzXG4gICAgICAgICAgICAgICAgZGVmYXVsdFRpbWVCbG9ja2luZ1xuICAgICAgICAgICAgICAgIGRlZmF1bHRUaW1lUHJlZmVyZW5jZVxuICAgICAgICAgICAgICAgIGRlbGV0ZWRcbiAgICAgICAgICAgICAgICBpZFxuICAgICAgICAgICAgICAgIG5hbWVcbiAgICAgICAgICAgICAgICB1cGRhdGVkQXRcbiAgICAgICAgICAgICAgICB1c2VySWRcbiAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgfVxuICAgICAgICAgICAgYWZmZWN0ZWRfcm93c1xuICAgICAgICAgIH1cbiAgICAgICAgfSBcbiAgICAgIGA7XG5cbiAgICBjb25zdCB2YXJpYWJsZXMgPSB7XG4gICAgICBjYXRlZ29yeV9ldmVudHM6IFtcbiAgICAgICAge1xuICAgICAgICAgIGlkOiB1dWlkKCksXG4gICAgICAgICAgdXNlcklkLFxuICAgICAgICAgIGNhdGVnb3J5SWQsXG4gICAgICAgICAgZXZlbnRJZCxcbiAgICAgICAgICBkZWxldGVkOiBmYWxzZSxcbiAgICAgICAgICB1cGRhdGVkQXQ6IGRheWpzKCkudG9JU09TdHJpbmcoKSxcbiAgICAgICAgICBjcmVhdGVkRGF0ZTogZGF5anMoKS50b0lTT1N0cmluZygpLFxuICAgICAgICB9LFxuICAgICAgXSxcbiAgICB9O1xuXG4gICAgY29uc3QgeyBkYXRhIH0gPSBhd2FpdCBjbGllbnQubXV0YXRlPHtcbiAgICAgIGluc2VydF9DYXRlZ29yeV9FdmVudDoge1xuICAgICAgICByZXR1cm5pbmc6IENhdGVnb3J5RXZlbnRUeXBlW107XG4gICAgICAgIGFmZmVjdGVkX3Jvd3M6IG51bWJlcjtcbiAgICAgIH07XG4gICAgfT4oe1xuICAgICAgbXV0YXRpb246IHVwc2VydENhdGVnb3J5RXZlbnQsXG4gICAgICB2YXJpYWJsZXMsXG4gICAgICB1cGRhdGUoY2FjaGUsIHsgZGF0YSB9KSB7XG4gICAgICAgIGlmIChkYXRhPy5pbnNlcnRfQ2F0ZWdvcnlfRXZlbnQ/LmFmZmVjdGVkX3Jvd3MgPiAwKSB7XG4gICAgICAgICAgY29uc29sZS5sb2coJ2luc2VydF9DYXRlZ29yeV9FdmVudCcsIGRhdGEpO1xuICAgICAgICB9XG5cbiAgICAgICAgY2FjaGUubW9kaWZ5KHtcbiAgICAgICAgICBmaWVsZHM6IHtcbiAgICAgICAgICAgIENhdGVnb3J5X0V2ZW50KGV4aXN0aW5nQ2F0ZWdvcnlFdmVudHMgPSBbXSkge1xuICAgICAgICAgICAgICBjb25zdCBuZXdDYXRlZ29yeUV2ZW50UmVmcyA9XG4gICAgICAgICAgICAgICAgZGF0YT8uaW5zZXJ0X0NhdGVnb3J5X0V2ZW50Py5yZXR1cm5pbmcubWFwKChjKSA9PlxuICAgICAgICAgICAgICAgICAgY2FjaGUud3JpdGVGcmFnbWVudCh7XG4gICAgICAgICAgICAgICAgICAgIGRhdGE6IGMsXG4gICAgICAgICAgICAgICAgICAgIGZyYWdtZW50OiBncWxgXG4gICAgICAgICAgICAgICAgICAgICAgZnJhZ21lbnQgTmV3Q2F0ZWdvcnlfRXZlbnQgb24gQ2F0ZWdvcnlfRXZlbnQge1xuICAgICAgICAgICAgICAgICAgICAgICAgaWRcbiAgICAgICAgICAgICAgICAgICAgICAgIGNhdGVnb3J5SWRcbiAgICAgICAgICAgICAgICAgICAgICAgIGNyZWF0ZWREYXRlXG4gICAgICAgICAgICAgICAgICAgICAgICBkZWxldGVkXG4gICAgICAgICAgICAgICAgICAgICAgICBldmVudElkXG4gICAgICAgICAgICAgICAgICAgICAgICB1cGRhdGVkQXRcbiAgICAgICAgICAgICAgICAgICAgICAgIHVzZXJJZFxuICAgICAgICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgICAgICAgICAgYCxcbiAgICAgICAgICAgICAgICAgIH0pXG4gICAgICAgICAgICAgICAgKTtcbiAgICAgICAgICAgICAgcmV0dXJuIFsuLi5leGlzdGluZ0NhdGVnb3J5RXZlbnRzLCAuLi5uZXdDYXRlZ29yeUV2ZW50UmVmc107XG4gICAgICAgICAgICB9LFxuICAgICAgICAgIH0sXG4gICAgICAgIH0pO1xuICAgICAgfSxcbiAgICB9KTtcblxuICAgIGNvbnNvbGUubG9nKGRhdGEsICcgc3VjY2Vzc2Z1bGx5IHVwc2VydGVkIGNhdGVnb3J5IGV2ZW50IGNvbm5lY3Rpb24nKTtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIGNyZWF0ZSBjYXRlZ29yeSBldmVudCcpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgbGlzdEV2ZW50c0ZvckNhdGVnb3J5ID0gYXN5bmMgKFxuICBjbGllbnQ6IEFwb2xsb0NsaWVudDxOb3JtYWxpemVkQ2FjaGVPYmplY3Q+LFxuICBjYXRlZ29yeUlkOiBzdHJpbmdcbikgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IHsgZGF0YSB9ID0gYXdhaXQgY2xpZW50LnF1ZXJ5PHtcbiAgICAgIEV2ZW50OiBFdmVudFR5cGVbXTtcbiAgICB9Pih7XG4gICAgICBxdWVyeTogbGlzdEV2ZW50c0ZvckNhdGVnb3J5UXVlcnksXG4gICAgICB2YXJpYWJsZXM6IHtcbiAgICAgICAgY2F0ZWdvcnlJZCxcbiAgICAgIH0sXG4gICAgfSk7XG5cbiAgICBjb25zb2xlLmxvZyhkYXRhLCAnIHN1Y2Nlc3NmdWxseSBsaXN0ZWQgZXZlbnRzIGZvciBjYXRlZ29yeScpO1xuICAgIHJldHVybiBkYXRhPy5FdmVudDtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIGxpc3RFdmVudHNGb3JDYXRlZ29yeScpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgbGlzdENhdGVnb3JpZXNGb3JFdmVudCA9IGFzeW5jIChcbiAgY2xpZW50OiBBcG9sbG9DbGllbnQ8Tm9ybWFsaXplZENhY2hlT2JqZWN0PixcbiAgZXZlbnRJZDogc3RyaW5nXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBjYXRlZ29yeURhdGEgPSBhd2FpdCBjbGllbnQucXVlcnk8eyBDYXRlZ29yeTogQ2F0ZWdvcnlUeXBlW10gfT4oe1xuICAgICAgcXVlcnk6IGxpc3RDYXRlZ29yaWVzRm9yRXZlbnRJZCxcbiAgICAgIHZhcmlhYmxlczoge1xuICAgICAgICBldmVudElkOiBldmVudElkLFxuICAgICAgfSxcbiAgICB9KTtcbiAgICBjb25zb2xlLmxvZyhjYXRlZ29yeURhdGEsICcgY2F0ZWdvcnlEYXRhIGluc2lkZSBsaXN0Q2F0ZWdvcmllc0ZvckV2ZW50Jyk7XG4gICAgY29uc3QgY2F0ZWdvcmllcyA9IGNhdGVnb3J5RGF0YT8uZGF0YT8uQ2F0ZWdvcnk7XG4gICAgY29uc29sZS5sb2coY2F0ZWdvcmllcywgJyBzdWNjZXNzZnVsbHkgbGlzdGVkIGNhdGVnb3JpZXMgZm9yIGV2ZW50Jyk7XG4gICAgcmV0dXJuIGNhdGVnb3JpZXM7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBsaXN0Q2F0ZWdvcmllc0ZvckV2ZW50Jyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCByZW1vdmVDYXRlZ29yeUNvbm5lY3Rpb25Gb3JFdmVudCA9IGFzeW5jIChcbiAgY2xpZW50OiBBcG9sbG9DbGllbnQ8Tm9ybWFsaXplZENhY2hlT2JqZWN0PixcbiAgY2F0ZWdvcnlJZDogc3RyaW5nLFxuICBldmVudElkOiBzdHJpbmdcbikgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IHsgZGF0YSB9ID0gYXdhaXQgY2xpZW50Lm11dGF0ZTx7XG4gICAgICBkZWxldGVfQ2F0ZWdvcnlfRXZlbnQ6IHtcbiAgICAgICAgYWZmZWN0ZWRfcm93czogbnVtYmVyO1xuICAgICAgICByZXR1cm5pbmc6IENhdGVnb3J5RXZlbnRUeXBlW107XG4gICAgICB9O1xuICAgIH0+KHtcbiAgICAgIG11dGF0aW9uOiByZW1vdmVDYXRlZ29yeUV2ZW50Q29ubmVjdGlvbixcbiAgICAgIHZhcmlhYmxlczoge1xuICAgICAgICBjYXRlZ29yeUlkLFxuICAgICAgICBldmVudElkLFxuICAgICAgfSxcbiAgICAgIC8vIHJlZmV0Y2hRdWVyaWVzOiBbXG4gICAgICAvLyAgIGxpc3RDYXRlZ29yaWVzRm9yRXZlbnRJZCxcbiAgICAgIC8vICAgJ2xpc3RDYXRlZ29yaWVzRm9yRXZlbnRJZCdcbiAgICAgIC8vIF0sXG4gICAgICB1cGRhdGUoY2FjaGUsIHsgZGF0YSB9KSB7XG4gICAgICAgIGNvbnN0IG5vcm1hbGl6ZWRJZHMgPSBkYXRhPy5kZWxldGVfQ2F0ZWdvcnlfRXZlbnQ/LnJldHVybmluZz8ubWFwKChjKSA9PlxuICAgICAgICAgIGNhY2hlLmlkZW50aWZ5KHsgaWQ6IGMuaWQsIF9fdHlwZW5hbWU6IGMuX190eXBlbmFtZSB9KVxuICAgICAgICApO1xuICAgICAgICBub3JtYWxpemVkSWRzLmZvckVhY2goKGlkKSA9PiBjYWNoZS5ldmljdCh7IGlkIH0pKTtcbiAgICAgICAgY2FjaGUuZ2MoKTtcbiAgICAgIH0sXG4gICAgfSk7XG5cbiAgICBjb25zb2xlLmxvZyhkYXRhLCAnIHN1Y2Nlc3NmdWxseSByZW1vdmVkIGNhdGVnb3J5IGNvbm5lY3Rpb24gZm9yIGV2ZW50Jyk7XG4gICAgcmV0dXJuIGRhdGE/LmRlbGV0ZV9DYXRlZ29yeV9FdmVudDtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIHJlbW92ZSBjYXRlZ29yeSBmb3IgZXZlbnQnKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IHJlbW92ZUFsbENhdGVnb3JpZXNGb3JFdmVudCA9IGFzeW5jIChcbiAgY2xpZW50OiBBcG9sbG9DbGllbnQ8Tm9ybWFsaXplZENhY2hlT2JqZWN0PixcbiAgZXZlbnRJZDogc3RyaW5nXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCB7IGRhdGEgfSA9IGF3YWl0IGNsaWVudC5tdXRhdGU8e1xuICAgICAgZGVsZXRlX0NhdGVnb3J5X0V2ZW50OiB7XG4gICAgICAgIGFmZmVjdGVkX3Jvd3M6IG51bWJlcjtcbiAgICAgICAgcmV0dXJuaW5nOiBDYXRlZ29yeUV2ZW50VHlwZVtdO1xuICAgICAgfTtcbiAgICB9Pih7XG4gICAgICBtdXRhdGlvbjogcmVtb3ZlQ2F0ZWdvcmllc0ZvckV2ZW50LFxuICAgICAgdmFyaWFibGVzOiB7XG4gICAgICAgIGV2ZW50SWQsXG4gICAgICB9LFxuICAgICAgLy8gcmVmZXRjaFF1ZXJpZXM6IFtcbiAgICAgIC8vICAgbGlzdENhdGVnb3JpZXNGb3JFdmVudElkLFxuICAgICAgLy8gICAnbGlzdENhdGVnb3JpZXNGb3JFdmVudElkJ1xuICAgICAgLy8gXSxcbiAgICAgIHVwZGF0ZShjYWNoZSwgeyBkYXRhIH0pIHtcbiAgICAgICAgY29uc3Qgbm9ybWFsaXplZElkcyA9IGRhdGE/LmRlbGV0ZV9DYXRlZ29yeV9FdmVudD8ucmV0dXJuaW5nPy5tYXAoKGMpID0+XG4gICAgICAgICAgY2FjaGUuaWRlbnRpZnkoeyBpZDogYy5pZCwgX190eXBlbmFtZTogYy5fX3R5cGVuYW1lIH0pXG4gICAgICAgICk7XG4gICAgICAgIG5vcm1hbGl6ZWRJZHMuZm9yRWFjaCgoaWQpID0+IGNhY2hlLmV2aWN0KHsgaWQgfSkpO1xuICAgICAgICBjYWNoZS5nYygpO1xuICAgICAgfSxcbiAgICB9KTtcblxuICAgIGNvbnNvbGUubG9nKGRhdGEsICcgc3VjY2Vzc2Z1bGx5IHJlbW92ZWQgYWxsIGNhdGVnb3JpZXMgZm9yIGV2ZW50Jyk7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byByZW1vdmUgYWxsIGNhdGVnb3JpZXMgZm9yIGV2ZW50Jyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBhZGRDYXRlZ29yeVRvVXNlciA9IGFzeW5jIChcbiAgY2xpZW50OiBBcG9sbG9DbGllbnQ8Tm9ybWFsaXplZENhY2hlT2JqZWN0PixcbiAgdXNlcklkOiBzdHJpbmcsXG4gIG5hbWU6IHN0cmluZ1xuKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3QgbmV3Q2F0ZWdvcnlWYWx1ZSA9IHtcbiAgICAgIGlkOiB1dWlkKCksXG4gICAgICB1c2VySWQsXG4gICAgICBuYW1lLFxuICAgICAgdXBkYXRlZEF0OiBkYXlqcygpLnRvSVNPU3RyaW5nKCksXG4gICAgICBjcmVhdGVkRGF0ZTogZGF5anMoKS50b0lTT1N0cmluZygpLFxuICAgIH07XG5cbiAgICBjb25zdCB7IGRhdGEgfSA9IGF3YWl0IGNsaWVudC5tdXRhdGU8eyBpbnNlcnRfQ2F0ZWdvcnlfb25lOiBDYXRlZ29yeVR5cGUgfT4oXG4gICAgICB7XG4gICAgICAgIG11dGF0aW9uOiBjcmVhdGVDYXRlZ29yeU11dGF0aW9uLFxuICAgICAgICB2YXJpYWJsZXM6IG5ld0NhdGVnb3J5VmFsdWUsXG4gICAgICB9XG4gICAgKTtcblxuICAgIGNvbnNvbGUubG9nKGRhdGEsICcgc3VjY2Vzc2Z1bGx5IGluc2VydGVkIGNhdGVnb3J5Jyk7XG4gICAgcmV0dXJuIGRhdGE/Lmluc2VydF9DYXRlZ29yeV9vbmU7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBhZGQgY2F0ZWdvcnkgdG8gdXNlcicpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgZ2V0Q2F0ZWdvcnlXaXRoSWQgPSBhc3luYyAoXG4gIGNsaWVudDogQXBvbGxvQ2xpZW50PE5vcm1hbGl6ZWRDYWNoZU9iamVjdD4sXG4gIGNhdGVnb3J5SWQ6IHN0cmluZ1xuKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3QgeyBkYXRhIH0gPSBhd2FpdCBjbGllbnQucXVlcnk8e1xuICAgICAgQ2F0ZWdvcnlfYnlfcGs6IENhdGVnb3J5VHlwZTtcbiAgICB9Pih7XG4gICAgICBxdWVyeTogZ2V0Q2F0ZWdvcnlCeUlkLFxuICAgICAgdmFyaWFibGVzOiB7XG4gICAgICAgIGlkOiBjYXRlZ29yeUlkLFxuICAgICAgfSxcbiAgICB9KTtcblxuICAgIGNvbnNvbGUubG9nKGRhdGEsICcgc3VjY2Vzc2Z1bGx5IGdvdCBjYXRlZ29yeSB3aXRoIGlkJyk7XG4gICAgcmV0dXJuIGRhdGE/LkNhdGVnb3J5X2J5X3BrO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gZ2V0IGNhdGVnb3J5IHdpdGggaWQnKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IHVwZGF0ZUNhdGVnb3J5SGVscGVyID0gYXN5bmMgKFxuICBjbGllbnQ6IEFwb2xsb0NsaWVudDxOb3JtYWxpemVkQ2FjaGVPYmplY3Q+LFxuICBjYXRlZ29yeUlkOiBzdHJpbmcsXG4gIG5hbWU6IHN0cmluZyxcbiAgY29weUF2YWlsYWJpbGl0eT86IGJvb2xlYW4sXG4gIGNvcHlUaW1lQmxvY2tpbmc/OiBib29sZWFuLFxuICBjb3B5VGltZVByZWZlcmVuY2U/OiBib29sZWFuLFxuICBjb3B5UmVtaW5kZXJzPzogYm9vbGVhbixcbiAgY29weVByaW9yaXR5TGV2ZWw/OiBib29sZWFuLFxuICBjb3B5TW9kaWZpYWJsZT86IGJvb2xlYW4sXG4gIGRlZmF1bHRBdmFpbGFiaWxpdHk/OiBib29sZWFuLFxuICBkZWZhdWx0VGltZUJsb2NraW5nPzogRGVmYXVsdFRpbWVCbG9ja2luZ1R5cGUgfCBudWxsLFxuICBkZWZhdWx0VGltZVByZWZlcmVuY2U/OiBEZWZhdWx0VGltZVByZWZlcmVuY2VUeXBlcyB8IG51bGwsXG4gIGRlZmF1bHRSZW1pbmRlcnM/OiBEZWZhdWx0UmVtaW5kZXJzVHlwZSB8IG51bGwsXG4gIGRlZmF1bHRQcmlvcml0eUxldmVsPzogbnVtYmVyLFxuICBkZWZhdWx0TW9kaWZpYWJsZT86IGJvb2xlYW4sXG4gIGNvcHlJc0JyZWFrPzogYm9vbGVhbixcbiAgZGVmYXVsdElzQnJlYWs/OiBib29sZWFuLFxuICBjb2xvcj86IHN0cmluZyxcbiAgY29weUlzTWVldGluZz86IGJvb2xlYW4sXG4gIGNvcHlJc0V4dGVybmFsTWVldGluZz86IGJvb2xlYW4sXG4gIGRlZmF1bHRJc01lZXRpbmc/OiBib29sZWFuLFxuICBkZWZhdWx0SXNFeHRlcm5hbE1lZXRpbmc/OiBib29sZWFuLFxuICBkZWZhdWx0TWVldGluZ01vZGlmaWFibGU/OiBib29sZWFuLFxuICBkZWZhdWx0RXh0ZXJuYWxNZWV0aW5nTW9kaWZpYWJsZT86IGJvb2xlYW5cbikgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IHVwZGF0ZUNhdGVnb3J5TXV0YXRpb24gPSBncWxgXG4gICAgICBtdXRhdGlvbiBVcGRhdGVDYXRlZ29yeShcbiAgICAgICAgJGlkOiB1dWlkISwgXG4gICAgICAgICR7bmFtZSAhPT0gdW5kZWZpbmVkID8gJyRuYW1lOiBTdHJpbmchLCcgOiAnJ31cbiAgICAgICAgJHtjb2xvciAhPT0gdW5kZWZpbmVkID8gJyRjb2xvcjogU3RyaW5nLCcgOiAnJ31cbiAgICAgICAgJHtjb3B5QXZhaWxhYmlsaXR5ID8gJyRjb3B5QXZhaWxhYmlsaXR5OiBCb29sZWFuLCcgOiAnJ31cbiAgICAgICAgJHtjb3B5SXNCcmVhayAhPT0gdW5kZWZpbmVkID8gJyRjb3B5SXNCcmVhazogQm9vbGVhbiwnIDogJyd9XG4gICAgICAgICR7Y29weUlzRXh0ZXJuYWxNZWV0aW5nICE9PSB1bmRlZmluZWQgPyAnJGNvcHlJc0V4dGVybmFsTWVldGluZzogQm9vbGVhbiwnIDogJyd9XG4gICAgICAgICR7Y29weUlzTWVldGluZyAhPT0gdW5kZWZpbmVkID8gJyRjb3B5SXNNZWV0aW5nOiBCb29sZWFuLCcgOiAnJ31cbiAgICAgICAgJHtjb3B5TW9kaWZpYWJsZSAhPT0gdW5kZWZpbmVkID8gJyRjb3B5TW9kaWZpYWJsZTogQm9vbGVhbiwnIDogJyd9XG4gICAgICAgICR7Y29weVByaW9yaXR5TGV2ZWwgIT09IHVuZGVmaW5lZCA/ICckY29weVByaW9yaXR5TGV2ZWw6IEJvb2xlYW4sJyA6ICcnfVxuICAgICAgICAke2NvcHlSZW1pbmRlcnMgIT09IHVuZGVmaW5lZCA/ICckY29weVJlbWluZGVyczogQm9vbGVhbiwnIDogJyd9XG4gICAgICAgICR7Y29weVRpbWVCbG9ja2luZyAhPT0gdW5kZWZpbmVkID8gJyRjb3B5VGltZUJsb2NraW5nOiBCb29sZWFuLCcgOiAnJ31cbiAgICAgICAgJHtjb3B5VGltZVByZWZlcmVuY2UgIT09IHVuZGVmaW5lZCA/ICckY29weVRpbWVQcmVmZXJlbmNlOiBCb29sZWFuLCcgOiAnJ31cbiAgICAgICAgJHtkZWZhdWx0QXZhaWxhYmlsaXR5ICE9PSB1bmRlZmluZWQgPyAnJGRlZmF1bHRBdmFpbGFiaWxpdHk6IEJvb2xlYW4sJyA6ICcnfVxuICAgICAgICAke2RlZmF1bHRFeHRlcm5hbE1lZXRpbmdNb2RpZmlhYmxlICE9PSB1bmRlZmluZWQgPyAnJGRlZmF1bHRFeHRlcm5hbE1lZXRpbmdNb2RpZmlhYmxlOiBCb29sZWFuLCcgOiAnJ31cbiAgICAgICAgJHtkZWZhdWx0SXNCcmVhayAhPT0gdW5kZWZpbmVkID8gJyRkZWZhdWx0SXNCcmVhazogQm9vbGVhbiwnIDogJyd9XG4gICAgICAgICR7ZGVmYXVsdElzRXh0ZXJuYWxNZWV0aW5nICE9PSB1bmRlZmluZWQgPyAnJGRlZmF1bHRJc0V4dGVybmFsTWVldGluZzogQm9vbGVhbiwnIDogJyd9XG4gICAgICAgICR7ZGVmYXVsdElzTWVldGluZyAhPT0gdW5kZWZpbmVkID8gJyRkZWZhdWx0SXNNZWV0aW5nOiBCb29sZWFuLCcgOiAnJ31cbiAgICAgICAgJHtkZWZhdWx0TWVldGluZ01vZGlmaWFibGUgIT09IHVuZGVmaW5lZCA/ICckZGVmYXVsdE1lZXRpbmdNb2RpZmlhYmxlOiBCb29sZWFuLCcgOiAnJ31cbiAgICAgICAgJHtkZWZhdWx0TW9kaWZpYWJsZSAhPT0gdW5kZWZpbmVkID8gJyRkZWZhdWx0TW9kaWZpYWJsZTogQm9vbGVhbiwnIDogJyd9XG4gICAgICAgICR7ZGVmYXVsdFByaW9yaXR5TGV2ZWwgIT09IHVuZGVmaW5lZCA/ICckZGVmYXVsdFByaW9yaXR5TGV2ZWw6IEludCwnIDogJyd9XG4gICAgICAgICR7ZGVmYXVsdFJlbWluZGVycyAhPT0gdW5kZWZpbmVkID8gJyRkZWZhdWx0UmVtaW5kZXJzOiBqc29uYiwnIDogJyd9XG4gICAgICAgICR7ZGVmYXVsdFRpbWVCbG9ja2luZyAhPT0gdW5kZWZpbmVkID8gJyRkZWZhdWx0VGltZUJsb2NraW5nOiBqc29uYiwnIDogJyd9XG4gICAgICAgICR7ZGVmYXVsdFRpbWVQcmVmZXJlbmNlICE9PSB1bmRlZmluZWQgPyAnJGRlZmF1bHRUaW1lUHJlZmVyZW5jZToganNvbmIsJyA6ICcnfVxuICAgICAgICAkdXBkYXRlZEF0OiB0aW1lc3RhbXB0eixcbiAgICAgICkge1xuICAgICAgICB1cGRhdGVfQ2F0ZWdvcnlfYnlfcGsocGtfY29sdW1uczoge2lkOiAkaWR9LCBfc2V0OiB7XG4gICAgICAgICAgJHtuYW1lICE9PSB1bmRlZmluZWQgPyAnbmFtZTogJG5hbWUsJyA6ICcnfSBcbiAgICAgICAgICB1cGRhdGVkQXQ6ICR1cGRhdGVkQXQsIFxuICAgICAgICAgICR7Y29sb3IgIT09IHVuZGVmaW5lZCA/ICdjb2xvcjogJGNvbG9yLCcgOiAnJ30gXG4gICAgICAgICAgJHtjb3B5QXZhaWxhYmlsaXR5ID8gJ2NvcHlBdmFpbGFiaWxpdHk6ICRjb3B5QXZhaWxhYmlsaXR5LCcgOiAnJ30gXG4gICAgICAgICAgJHtjb3B5SXNCcmVhayAhPT0gdW5kZWZpbmVkID8gJ2NvcHlJc0JyZWFrOiAkY29weUlzQnJlYWssJyA6ICcnfSBcbiAgICAgICAgICAke2NvcHlJc0V4dGVybmFsTWVldGluZyAhPT0gdW5kZWZpbmVkID8gJ2NvcHlJc0V4dGVybmFsTWVldGluZzogJGNvcHlJc0V4dGVybmFsTWVldGluZywnIDogJyd9IFxuICAgICAgICAgICR7Y29weUlzTWVldGluZyAhPT0gdW5kZWZpbmVkID8gJ2NvcHlJc01lZXRpbmc6ICRjb3B5SXNNZWV0aW5nLCcgOiAnJ30gXG4gICAgICAgICAgJHtjb3B5TW9kaWZpYWJsZSAhPT0gdW5kZWZpbmVkID8gJ2NvcHlNb2RpZmlhYmxlOiAkY29weU1vZGlmaWFibGUsJyA6ICcnfSBcbiAgICAgICAgICAke2NvcHlQcmlvcml0eUxldmVsICE9PSB1bmRlZmluZWQgPyAnY29weVByaW9yaXR5TGV2ZWw6ICRjb3B5UHJpb3JpdHlMZXZlbCwnIDogJyd9IFxuICAgICAgICAgICR7Y29weVJlbWluZGVycyAhPT0gdW5kZWZpbmVkID8gJ2NvcHlSZW1pbmRlcnM6ICRjb3B5UmVtaW5kZXJzLCcgOiAnJ30gXG4gICAgICAgICAgJHtjb3B5VGltZUJsb2NraW5nICE9PSB1bmRlZmluZWQgPyAnY29weVRpbWVCbG9ja2luZzogJGNvcHlUaW1lQmxvY2tpbmcsJyA6ICcnfSBcbiAgICAgICAgICAke2NvcHlUaW1lUHJlZmVyZW5jZSAhPT0gdW5kZWZpbmVkID8gJ2NvcHlUaW1lUHJlZmVyZW5jZTogJGNvcHlUaW1lUHJlZmVyZW5jZSwnIDogJyd9IFxuICAgICAgICAgICR7ZGVmYXVsdEF2YWlsYWJpbGl0eSAhPT0gdW5kZWZpbmVkID8gJ2RlZmF1bHRBdmFpbGFiaWxpdHk6ICRkZWZhdWx0QXZhaWxhYmlsaXR5LCcgOiAnJ30gXG4gICAgICAgICAgJHtkZWZhdWx0RXh0ZXJuYWxNZWV0aW5nTW9kaWZpYWJsZSAhPT0gdW5kZWZpbmVkID8gJ2RlZmF1bHRFeHRlcm5hbE1lZXRpbmdNb2RpZmlhYmxlOiAkZGVmYXVsdEV4dGVybmFsTWVldGluZ01vZGlmaWFibGUsJyA6ICcnfSBcbiAgICAgICAgICAke2RlZmF1bHRJc0JyZWFrICE9PSB1bmRlZmluZWQgPyAnZGVmYXVsdElzQnJlYWs6ICRkZWZhdWx0SXNCcmVhaywnIDogJyd9IFxuICAgICAgICAgICR7ZGVmYXVsdElzRXh0ZXJuYWxNZWV0aW5nICE9PSB1bmRlZmluZWQgPyAnZGVmYXVsdElzRXh0ZXJuYWxNZWV0aW5nOiAkZGVmYXVsdElzRXh0ZXJuYWxNZWV0aW5nLCcgOiAnJ30gXG4gICAgICAgICAgJHtkZWZhdWx0SXNNZWV0aW5nICE9PSB1bmRlZmluZWQgPyAnZGVmYXVsdElzTWVldGluZzogJGRlZmF1bHRJc01lZXRpbmcsJyA6ICcnfSBcbiAgICAgICAgICAke2RlZmF1bHRNZWV0aW5nTW9kaWZpYWJsZSAhPT0gdW5kZWZpbmVkID8gJ2RlZmF1bHRNZWV0aW5nTW9kaWZpYWJsZTogJGRlZmF1bHRNZWV0aW5nTW9kaWZpYWJsZSwnIDogJyd9IFxuICAgICAgICAgICR7ZGVmYXVsdE1vZGlmaWFibGUgIT09IHVuZGVmaW5lZCA/ICdkZWZhdWx0TW9kaWZpYWJsZTogJGRlZmF1bHRNb2RpZmlhYmxlLCcgOiAnJ30gXG4gICAgICAgICAgJHtkZWZhdWx0UHJpb3JpdHlMZXZlbCAhPT0gdW5kZWZpbmVkID8gJ2RlZmF1bHRQcmlvcml0eUxldmVsOiAkZGVmYXVsdFByaW9yaXR5TGV2ZWwsJyA6ICcnfSBcbiAgICAgICAgICAke2RlZmF1bHRSZW1pbmRlcnMgIT09IHVuZGVmaW5lZCA/ICdkZWZhdWx0UmVtaW5kZXJzOiAkZGVmYXVsdFJlbWluZGVycywnIDogJyd9IFxuICAgICAgICAgICR7ZGVmYXVsdFRpbWVCbG9ja2luZyAhPT0gdW5kZWZpbmVkID8gJ2RlZmF1bHRUaW1lQmxvY2tpbmc6ICRkZWZhdWx0VGltZUJsb2NraW5nLCcgOiAnJ30gXG4gICAgICAgICAgJHtkZWZhdWx0VGltZVByZWZlcmVuY2UgIT09IHVuZGVmaW5lZCA/ICdkZWZhdWx0VGltZVByZWZlcmVuY2U6ICRkZWZhdWx0VGltZVByZWZlcmVuY2UsJyA6ICcnfVxuICAgICAgICB9KSB7XG4gICAgICAgICAgaWRcbiAgICAgICAgICBuYW1lXG4gICAgICAgICAgZGVsZXRlZFxuICAgICAgICAgIGNyZWF0ZWREYXRlXG4gICAgICAgICAgdXBkYXRlZEF0XG4gICAgICAgICAgdXNlcklkXG4gICAgICAgICAgY29weUF2YWlsYWJpbGl0eVxuICAgICAgICAgIGNvcHlUaW1lQmxvY2tpbmdcbiAgICAgICAgICBjb3B5VGltZVByZWZlcmVuY2VcbiAgICAgICAgICBjb3B5UmVtaW5kZXJzXG4gICAgICAgICAgY29weVByaW9yaXR5TGV2ZWxcbiAgICAgICAgICBjb3B5TW9kaWZpYWJsZVxuICAgICAgICAgIGRlZmF1bHRBdmFpbGFiaWxpdHlcbiAgICAgICAgICBkZWZhdWx0VGltZUJsb2NraW5nXG4gICAgICAgICAgZGVmYXVsdFRpbWVQcmVmZXJlbmNlXG4gICAgICAgICAgZGVmYXVsdFJlbWluZGVyc1xuICAgICAgICAgIGRlZmF1bHRQcmlvcml0eUxldmVsXG4gICAgICAgICAgZGVmYXVsdE1vZGlmaWFibGVcbiAgICAgICAgICBjb3B5SXNCcmVha1xuICAgICAgICAgIGRlZmF1bHRJc0JyZWFrXG4gICAgICAgICAgY29sb3JcbiAgICAgICAgICBjb3B5SXNNZWV0aW5nXG4gICAgICAgICAgY29weUlzRXh0ZXJuYWxNZWV0aW5nXG4gICAgICAgICAgZGVmYXVsdElzTWVldGluZ1xuICAgICAgICAgIGRlZmF1bHRJc0V4dGVybmFsTWVldGluZ1xuICAgICAgICAgIGRlZmF1bHRNZWV0aW5nTW9kaWZpYWJsZVxuICAgICAgICAgIGRlZmF1bHRFeHRlcm5hbE1lZXRpbmdNb2RpZmlhYmxlXG4gICAgICAgIH1cbiAgICAgIH1cbiAgICBgO1xuXG4gICAgY29uc3QgdmFyaWFibGVzOiBhbnkgPSB7XG4gICAgICBpZDogY2F0ZWdvcnlJZCxcbiAgICAgIHVwZGF0ZWRBdDogbmV3IERhdGUoKS50b0lTT1N0cmluZygpLFxuICAgIH07XG5cbiAgICBpZiAobmFtZSAhPT0gdW5kZWZpbmVkKSB7XG4gICAgICB2YXJpYWJsZXMubmFtZSA9IG5hbWU7XG4gICAgfVxuXG4gICAgaWYgKGNvbG9yICE9PSB1bmRlZmluZWQpIHtcbiAgICAgIHZhcmlhYmxlcy5jb2xvciA9IGNvbG9yO1xuICAgIH1cblxuICAgIGlmIChjb3B5QXZhaWxhYmlsaXR5ICE9PSB1bmRlZmluZWQpIHtcbiAgICAgIHZhcmlhYmxlcy5jb3B5QXZhaWxhYmlsaXR5ID0gY29weUF2YWlsYWJpbGl0eTtcbiAgICB9XG5cbiAgICBpZiAoY29weUlzQnJlYWsgIT09IHVuZGVmaW5lZCkge1xuICAgICAgdmFyaWFibGVzLmNvcHlJc0JyZWFrID0gY29weUlzQnJlYWs7XG4gICAgfVxuXG4gICAgaWYgKGNvcHlJc0V4dGVybmFsTWVldGluZyAhPT0gdW5kZWZpbmVkKSB7XG4gICAgICB2YXJpYWJsZXMuY29weUlzRXh0ZXJuYWxNZWV0aW5nID0gY29weUlzRXh0ZXJuYWxNZWV0aW5nO1xuICAgIH1cblxuICAgIGlmIChjb3B5SXNNZWV0aW5nICE9PSB1bmRlZmluZWQpIHtcbiAgICAgIHZhcmlhYmxlcy5jb3B5SXNNZWV0aW5nID0gY29weUlzTWVldGluZztcbiAgICB9XG5cbiAgICBpZiAoY29weU1vZGlmaWFibGUgIT09IHVuZGVmaW5lZCkge1xuICAgICAgdmFyaWFibGVzLmNvcHlNb2RpZmlhYmxlID0gY29weU1vZGlmaWFibGU7XG4gICAgfVxuXG4gICAgaWYgKGNvcHlQcmlvcml0eUxldmVsICE9PSB1bmRlZmluZWQpIHtcbiAgICAgIHZhcmlhYmxlcy5jb3B5UHJpb3JpdHlMZXZlbCA9IGNvcHlQcmlvcml0eUxldmVsO1xuICAgIH1cblxuICAgIGlmIChjb3B5UmVtaW5kZXJzICE9PSB1bmRlZmluZWQpIHtcbiAgICAgIHZhcmlhYmxlcy5jb3B5UmVtaW5kZXJzID0gY29weVJlbWluZGVycztcbiAgICB9XG5cbiAgICBpZiAoY29weVRpbWVCbG9ja2luZyAhPT0gdW5kZWZpbmVkKSB7XG4gICAgICB2YXJpYWJsZXMuY29weVRpbWVCbG9ja2luZyA9IGNvcHlUaW1lQmxvY2tpbmc7XG4gICAgfVxuXG4gICAgaWYgKGNvcHlUaW1lUHJlZmVyZW5jZSAhPT0gdW5kZWZpbmVkKSB7XG4gICAgICB2YXJpYWJsZXMuY29weVRpbWVQcmVmZXJlbmNlID0gY29weVRpbWVQcmVmZXJlbmNlO1xuICAgIH1cblxuICAgIGlmIChkZWZhdWx0QXZhaWxhYmlsaXR5ICE9PSB1bmRlZmluZWQpIHtcbiAgICAgIHZhcmlhYmxlcy5kZWZhdWx0QXZhaWxhYmlsaXR5ID0gZGVmYXVsdEF2YWlsYWJpbGl0eTtcbiAgICB9XG5cbiAgICBpZiAoZGVmYXVsdEV4dGVybmFsTWVldGluZ01vZGlmaWFibGUgIT09IHVuZGVmaW5lZCkge1xuICAgICAgdmFyaWFibGVzLmRlZmF1bHRFeHRlcm5hbE1lZXRpbmdNb2RpZmlhYmxlID1cbiAgICAgICAgZGVmYXVsdEV4dGVybmFsTWVldGluZ01vZGlmaWFibGU7XG4gICAgfVxuXG4gICAgaWYgKGRlZmF1bHRJc0JyZWFrICE9PSB1bmRlZmluZWQpIHtcbiAgICAgIHZhcmlhYmxlcy5kZWZhdWx0SXNCcmVhayA9IGRlZmF1bHRJc0JyZWFrO1xuICAgIH1cblxuICAgIGlmIChkZWZhdWx0SXNFeHRlcm5hbE1lZXRpbmcgIT09IHVuZGVmaW5lZCkge1xuICAgICAgdmFyaWFibGVzLmRlZmF1bHRJc0V4dGVybmFsTWVldGluZyA9IGRlZmF1bHRJc0V4dGVybmFsTWVldGluZztcbiAgICB9XG5cbiAgICBpZiAoZGVmYXVsdElzTWVldGluZyAhPT0gdW5kZWZpbmVkKSB7XG4gICAgICB2YXJpYWJsZXMuZGVmYXVsdElzTWVldGluZyA9IGRlZmF1bHRJc01lZXRpbmc7XG4gICAgfVxuXG4gICAgaWYgKGRlZmF1bHRNZWV0aW5nTW9kaWZpYWJsZSAhPT0gdW5kZWZpbmVkKSB7XG4gICAgICB2YXJpYWJsZXMuZGVmYXVsdE1lZXRpbmdNb2RpZmlhYmxlID0gZGVmYXVsdE1lZXRpbmdNb2RpZmlhYmxlO1xuICAgIH1cblxuICAgIGlmIChkZWZhdWx0TW9kaWZpYWJsZSAhPT0gdW5kZWZpbmVkKSB7XG4gICAgICB2YXJpYWJsZXMuZGVmYXVsdE1vZGlmaWFibGUgPSBkZWZhdWx0TW9kaWZpYWJsZTtcbiAgICB9XG5cbiAgICBpZiAoZGVmYXVsdFByaW9yaXR5TGV2ZWwgIT09IHVuZGVmaW5lZCkge1xuICAgICAgdmFyaWFibGVzLmRlZmF1bHRQcmlvcml0eUxldmVsID0gZGVmYXVsdFByaW9yaXR5TGV2ZWw7XG4gICAgfVxuXG4gICAgaWYgKGRlZmF1bHRSZW1pbmRlcnMgIT09IHVuZGVmaW5lZCkge1xuICAgICAgdmFyaWFibGVzLmRlZmF1bHRSZW1pbmRlcnMgPSBkZWZhdWx0UmVtaW5kZXJzO1xuICAgIH1cblxuICAgIGlmIChkZWZhdWx0VGltZUJsb2NraW5nICE9PSB1bmRlZmluZWQpIHtcbiAgICAgIHZhcmlhYmxlcy5kZWZhdWx0VGltZUJsb2NraW5nID0gZGVmYXVsdFRpbWVCbG9ja2luZztcbiAgICB9XG5cbiAgICBpZiAoZGVmYXVsdFRpbWVQcmVmZXJlbmNlICE9PSB1bmRlZmluZWQpIHtcbiAgICAgIHZhcmlhYmxlcy5kZWZhdWx0VGltZVByZWZlcmVuY2UgPSBkZWZhdWx0VGltZVByZWZlcmVuY2U7XG4gICAgfVxuXG4gICAgY29uc3QgeyBkYXRhIH0gPSBhd2FpdCBjbGllbnQubXV0YXRlPHtcbiAgICAgIHVwZGF0ZV9DYXRlZ29yeV9ieV9wazogQ2F0ZWdvcnlUeXBlO1xuICAgIH0+KHtcbiAgICAgIG11dGF0aW9uOiB1cGRhdGVDYXRlZ29yeU11dGF0aW9uLFxuICAgICAgdmFyaWFibGVzLFxuICAgIH0pO1xuXG4gICAgcmV0dXJuIGRhdGEudXBkYXRlX0NhdGVnb3J5X2J5X3BrO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gdXBkYXRlIGNhdGVnb3J5Jyk7XG4gIH1cbn07XG5cbi8qKlxuRW5kICovXG4iXX0=