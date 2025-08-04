"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.deleteTasksGivenIds = exports.deleteTaskGivenId = exports.upsertManyTasksInDb = exports.insertTaskInDb = exports.updateTaskByIdInDb = exports.listEventsGivenIds = exports.listTasksGivenUserId = exports.getTaskGivenId = void 0;
const client_1 = require("@apollo/client");
const deleteTaskById_1 = __importDefault(require("@lib/apollo/gql/deleteTaskById"));
const deleteTasksByIds_1 = __importDefault(require("@lib/apollo/gql/deleteTasksByIds"));
const getTaskById_1 = __importDefault(require("@lib/apollo/gql/getTaskById"));
const insertTaskOne_1 = __importDefault(require("@lib/apollo/gql/insertTaskOne"));
const listEventsByIds_1 = __importDefault(require("@lib/apollo/gql/listEventsByIds"));
const upsertTask_1 = __importDefault(require("@lib/apollo/gql/upsertTask"));
const getTaskGivenId = async (client, taskId) => {
    try {
        const { data } = await client.query({
            query: getTaskById_1.default,
            variables: {
                id: taskId,
            },
        });
        console.log(data?.Task_by_pk, ' successfully got task by id');
        return data?.Task_by_pk;
    }
    catch (e) {
        console.log(e, ' unable to get task given Id');
    }
};
exports.getTaskGivenId = getTaskGivenId;
const listTasksGivenUserId = async (client, userId, type) => {
    try {
        const listTasksByUserId = (0, client_1.gql) `
            query ListTasksByUserId($userId: uuid!, ${type ? '$type: String' : ''}) {
                Task(where: {userId: {_eq: $userId}, ${type ? 'type: {_eq: $type}' : ''}}) {
                    completedDate
                    createdDate
                    duration
                    eventId
                    hardDeadline
                    id
                    important
                    notes
                    order
                    parentId
                    priority
                    softDeadline
                    status
                    syncData
                    type
                    updatedAt
                    userId
                }
            }

        `;
        const variables = {
            userId,
        };
        if (type) {
            variables.type = type;
        }
        const { data } = await client.query({
            query: listTasksByUserId,
            variables,
            fetchPolicy: 'no-cache',
        });
        console.log(data, ' successfully retrieved tasks');
        return data?.Task;
    }
    catch (e) {
        console.log(e, ' unable to list tasks for userId');
    }
};
exports.listTasksGivenUserId = listTasksGivenUserId;
const listEventsGivenIds = async (client, eventIds) => {
    try {
        // listEventsByIds
        const { data } = await client.query({
            query: listEventsByIds_1.default,
            variables: {
                ids: eventIds,
            },
        });
        return data?.Event;
    }
    catch (e) {
        console.log(e, ' unable to list events givenIds');
    }
};
exports.listEventsGivenIds = listEventsGivenIds;
const updateTaskByIdInDb = async (client, task) => {
    try {
        /**
             * const result = await client.mutate<{ insert_Calendar: { returning: CalendarType[] } }>({
                mutation: upsertCalendar,
                variables: {
                    calendars: [calendarValueToUpsert],
                },
                })
             */
        let variables = { id: task?.id };
        if (task?.completedDate !== undefined) {
            variables.completedDate = task?.completedDate;
        }
        if (task?.duration !== undefined) {
            variables.duration = task?.duration;
        }
        if (task?.eventId !== undefined) {
            variables.eventId = task?.eventId;
        }
        if (task?.hardDeadline !== undefined) {
            variables.hardDeadline = task?.hardDeadline;
        }
        if (task?.important !== undefined) {
            variables.important = task?.important;
        }
        if (task?.notes !== undefined) {
            variables.notes = task?.notes;
        }
        if (task?.order !== undefined) {
            variables.order = task?.order;
        }
        if (task?.parentId !== undefined) {
            variables.parentId = task?.parentId;
        }
        if (task?.priority !== undefined) {
            variables.priority = task?.priority;
        }
        if (task?.softDeadline !== undefined) {
            variables.softDeadline = task?.softDeadline;
        }
        if (task?.status !== undefined) {
            variables.status = task?.status;
        }
        if (task?.syncData !== undefined) {
            variables.syncData = task?.syncData;
        }
        if (task?.type !== undefined) {
            variables.type = task?.type;
        }
        const updateTaskById = (0, client_1.gql) `
            mutation UpdateTaskById($id: uuid!, ${task?.completedDate !== undefined ? '$completedDate: timestamptz,' : ''} ${task?.duration !== undefined ? '$duration: Int,' : ''} ${task?.eventId !== undefined ? '$eventId: String,' : ''} ${task?.hardDeadline !== undefined ? '$hardDeadline: timestamp,' : ''} ${task?.important !== undefined ? '$important: Boolean,' : ''} ${task?.notes !== undefined ? '$notes: String,' : ''} ${task?.order !== undefined ? '$order: Int,' : ''} ${task?.parentId !== undefined ? '$parentId: uuid,' : ''} ${task?.priority !== undefined ? '$priority: Int,' : ''} ${task?.softDeadline !== undefined ? '$softDeadline: timestamp,' : ''} ${task?.status !== undefined ? '$status: String,' : ''} ${task?.syncData !== undefined ? '$syncData: jsonb,' : ''} ${task?.type !== undefined ? '$type: String' : ''}){
                update_Task_by_pk(pk_columns: {id: $id}, _set: {${task?.completedDate !== undefined ? 'completedDate: $completedDate,' : ''} ${task?.duration !== undefined ? 'duration: $duration,' : ''} ${task?.eventId !== undefined ? 'eventId: $eventId,' : ''} ${task?.hardDeadline !== undefined ? 'hardDeadline: $hardDeadline,' : ''} ${task?.important !== undefined ? 'important: $important,' : ''} ${task?.notes !== undefined ? 'notes: $notes,' : ''} ${task?.order !== undefined ? 'order: $order,' : ''} ${task?.parentId !== undefined ? 'parentId: $parentId,' : ''} ${task?.priority !== undefined ? 'priority: $priority,' : ''} ${task?.softDeadline !== undefined ? 'softDeadline: $softDeadline,' : ''} ${task?.status !== undefined ? 'status: $status,' : ''} ${task?.syncData !== undefined ? 'syncData: $syncData,' : ''} ${task?.type !== undefined ? 'type: $type' : ''}}) {
                    completedDate
                    createdDate
                    duration
                    eventId
                    hardDeadline
                    id
                    important
                    notes
                    order
                    parentId
                    priority
                    softDeadline
                    status
                    syncData
                    type
                    updatedAt
                    userId
                }
            }
        `;
        const results = await client.mutate({
            mutation: updateTaskById,
            variables,
        });
        console.log(results?.data?.update_Task_by_pk, ' successfully updated task');
    }
    catch (e) {
        console.log(e, ' unable to update task in db');
    }
};
exports.updateTaskByIdInDb = updateTaskByIdInDb;
const insertTaskInDb = async (client, task) => {
    try {
        const results = await client.mutate({
            mutation: insertTaskOne_1.default,
            variables: {
                task,
            },
        });
        console.log(results?.data?.insert_Task_one, ' successfully inserted one task');
        return results?.data?.insert_Task_one;
    }
    catch (e) {
        console.log(e, ' unable to insert task in db');
    }
};
exports.insertTaskInDb = insertTaskInDb;
const upsertManyTasksInDb = async (client, tasks) => {
    try {
        /**
             * const result = await client.mutate<{ insert_Calendar: { returning: CalendarType[] } }>({
                mutation: upsertCalendar,
                variables: {
                    calendars: [calendarValueToUpsert],
                },
                })
             */
        const results = await client.mutate({
            mutation: upsertTask_1.default,
            variables: {
                tasks,
            },
        });
        console.log(results?.data, ' succesfully upserted many tasks ');
    }
    catch (e) {
        console.log(e, ' unable to upsert many tasks in Db');
    }
};
exports.upsertManyTasksInDb = upsertManyTasksInDb;
const deleteTaskGivenId = async (client, taskId) => {
    try {
        const results = await client.mutate({
            mutation: deleteTaskById_1.default,
            variables: {
                id: taskId,
            },
        });
        console.log(results?.data?.delete_Task, ' successfully deleted task ');
        return results?.data?.delete_Task;
    }
    catch (e) {
        console.log(e, ' unable to delete task given id');
    }
};
exports.deleteTaskGivenId = deleteTaskGivenId;
const deleteTasksGivenIds = async (client, taskIds) => {
    try {
        const results = await client.mutate({
            mutation: deleteTasksByIds_1.default,
            variables: {
                taskIds,
            },
        });
        console.log(results, ' successfully deleted tasks by ids given affected rows');
    }
    catch (e) {
        console.log(e, ' unable to delete tasks givne ids');
    }
};
exports.deleteTasksGivenIds = deleteTasksGivenIds;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiVXNlclRhc2tIZWxwZXIzLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsiVXNlclRhc2tIZWxwZXIzLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiI7Ozs7OztBQUFBLDJDQUEwRTtBQUMxRSxvRkFBNEQ7QUFDNUQsd0ZBQWdFO0FBQ2hFLDhFQUFzRDtBQUN0RCxrRkFBMEQ7QUFDMUQsc0ZBQThEO0FBQzlELDRFQUFvRDtBQUk3QyxNQUFNLGNBQWMsR0FBRyxLQUFLLEVBQ2pDLE1BQTJDLEVBQzNDLE1BQWMsRUFDZCxFQUFFO0lBQ0YsSUFBSSxDQUFDO1FBQ0gsTUFBTSxFQUFFLElBQUksRUFBRSxHQUFHLE1BQU0sTUFBTSxDQUFDLEtBQUssQ0FBMkI7WUFDNUQsS0FBSyxFQUFFLHFCQUFXO1lBQ2xCLFNBQVMsRUFBRTtnQkFDVCxFQUFFLEVBQUUsTUFBTTthQUNYO1NBQ0YsQ0FBQyxDQUFDO1FBRUgsT0FBTyxDQUFDLEdBQUcsQ0FBQyxJQUFJLEVBQUUsVUFBVSxFQUFFLDhCQUE4QixDQUFDLENBQUM7UUFDOUQsT0FBTyxJQUFJLEVBQUUsVUFBVSxDQUFDO0lBQzFCLENBQUM7SUFBQyxPQUFPLENBQUMsRUFBRSxDQUFDO1FBQ1gsT0FBTyxDQUFDLEdBQUcsQ0FBQyxDQUFDLEVBQUUsOEJBQThCLENBQUMsQ0FBQztJQUNqRCxDQUFDO0FBQ0gsQ0FBQyxDQUFDO0FBakJXLFFBQUEsY0FBYyxrQkFpQnpCO0FBRUssTUFBTSxvQkFBb0IsR0FBRyxLQUFLLEVBQ3ZDLE1BQTJDLEVBQzNDLE1BQWMsRUFDZCxJQUFhLEVBQ2IsRUFBRTtJQUNGLElBQUksQ0FBQztRQUNILE1BQU0saUJBQWlCLEdBQUcsSUFBQSxZQUFHLEVBQUE7c0RBQ3FCLElBQUksQ0FBQyxDQUFDLENBQUMsZUFBZSxDQUFDLENBQUMsQ0FBQyxFQUFFO3VEQUMxQixJQUFJLENBQUMsQ0FBQyxDQUFDLG9CQUFvQixDQUFDLENBQUMsQ0FBQyxFQUFFOzs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7U0Fx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IHsgQXBvbGxvQ2xpZW50LCBncWwsIE5vcm1hbGl6ZWRDYWNoZU9iamVjdCB9IGZyb20gJ0BhcG9sbG8vY2xpZW50JztcbmltcG9ydCBkZWxldGVUYXNrQnlJZCBmcm9tICdAbGliL2Fwb2xsby9ncWwvZGVsZXRlVGFza0J5SWQnO1xuaW1wb3J0IGRlbGV0ZVRhc2tzQnlJZHMgZnJvbSAnQGxpYi9hcG9sbG8vZ3FsL2RlbGV0ZVRhc2tzQnlJZHMnO1xuaW1wb3J0IGdldFRhc2tCeUlkIGZyb20gJ0BsaWIvYXBvbGxvL2dxbC9nZXRUYXNrQnlJZCc7XG5pbXBvcnQgaW5zZXJ0VGFza09uZSBmcm9tICdAbGliL2Fwb2xsby9ncWwvaW5zZXJ0VGFza09uZSc7XG5pbXBvcnQgbGlzdEV2ZW50c0J5SWRzIGZyb20gJ0BsaWIvYXBvbGxvL2dxbC9saXN0RXZlbnRzQnlJZHMnO1xuaW1wb3J0IHVwc2VydFRhc2sgZnJvbSAnQGxpYi9hcG9sbG8vZ3FsL3Vwc2VydFRhc2snO1xuaW1wb3J0IHsgRXZlbnRUeXBlIH0gZnJvbSAnQGxpYi9kYXRhVHlwZXMvRXZlbnRUeXBlJztcbmltcG9ydCB7IFRhc2tUeXBlIH0gZnJvbSAnQGxpYi9kYXRhVHlwZXMvVGFza1R5cGUnO1xuXG5leHBvcnQgY29uc3QgZ2V0VGFza0dpdmVuSWQgPSBhc3luYyAoXG4gIGNsaWVudDogQXBvbGxvQ2xpZW50PE5vcm1hbGl6ZWRDYWNoZU9iamVjdD4sXG4gIHRhc2tJZDogc3RyaW5nXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCB7IGRhdGEgfSA9IGF3YWl0IGNsaWVudC5xdWVyeTx7IFRhc2tfYnlfcGs6IFRhc2tUeXBlIH0+KHtcbiAgICAgIHF1ZXJ5OiBnZXRUYXNrQnlJZCxcbiAgICAgIHZhcmlhYmxlczoge1xuICAgICAgICBpZDogdGFza0lkLFxuICAgICAgfSxcbiAgICB9KTtcblxuICAgIGNvbnNvbGUubG9nKGRhdGE/LlRhc2tfYnlfcGssICcgc3VjY2Vzc2Z1bGx5IGdvdCB0YXNrIGJ5IGlkJyk7XG4gICAgcmV0dXJuIGRhdGE/LlRhc2tfYnlfcGs7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBnZXQgdGFzayBnaXZlbiBJZCcpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgbGlzdFRhc2tzR2l2ZW5Vc2VySWQgPSBhc3luYyAoXG4gIGNsaWVudDogQXBvbGxvQ2xpZW50PE5vcm1hbGl6ZWRDYWNoZU9iamVjdD4sXG4gIHVzZXJJZDogc3RyaW5nLFxuICB0eXBlPzogc3RyaW5nXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBsaXN0VGFza3NCeVVzZXJJZCA9IGdxbGBcbiAgICAgICAgICAgIHF1ZXJ5IExpc3RUYXNrc0J5VXNlcklkKCR1c2VySWQ6IHV1aWQhLCAke3R5cGUgPyAnJHR5cGU6IFN0cmluZycgOiAnJ30pIHtcbiAgICAgICAgICAgICAgICBUYXNrKHdoZXJlOiB7dXNlcklkOiB7X2VxOiAkdXNlcklkfSwgJHt0eXBlID8gJ3R5cGU6IHtfZXE6ICR0eXBlfScgOiAnJ319KSB7XG4gICAgICAgICAgICAgICAgICAgIGNvbXBsZXRlZERhdGVcbiAgICAgICAgICAgICAgICAgICAgY3JlYXRlZERhdGVcbiAgICAgICAgICAgICAgICAgICAgZHVyYXRpb25cbiAgICAgICAgICAgICAgICAgICAgZXZlbnRJZFxuICAgICAgICAgICAgICAgICAgICBoYXJkRGVhZGxpbmVcbiAgICAgICAgICAgICAgICAgICAgaWRcbiAgICAgICAgICAgICAgICAgICAgaW1wb3J0YW50XG4gICAgICAgICAgICAgICAgICAgIG5vdGVzXG4gICAgICAgICAgICAgICAgICAgIG9yZGVyXG4gICAgICAgICAgICAgICAgICAgIHBhcmVudElkXG4gICAgICAgICAgICAgICAgICAgIHByaW9yaXR5XG4gICAgICAgICAgICAgICAgICAgIHNvZnREZWFkbGluZVxuICAgICAgICAgICAgICAgICAgICBzdGF0dXNcbiAgICAgICAgICAgICAgICAgICAgc3luY0RhdGFcbiAgICAgICAgICAgICAgICAgICAgdHlwZVxuICAgICAgICAgICAgICAgICAgICB1cGRhdGVkQXRcbiAgICAgICAgICAgICAgICAgICAgdXNlcklkXG4gICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgfVxuXG4gICAgICAgIGA7XG4gICAgY29uc3QgdmFyaWFibGVzOiB7IHVzZXJJZDogc3RyaW5nOyB0eXBlPzogc3RyaW5nIH0gPSB7XG4gICAgICB1c2VySWQsXG4gICAgfTtcblxuICAgIGlmICh0eXBlKSB7XG4gICAgICB2YXJpYWJsZXMudHlwZSA9IHR5cGU7XG4gICAgfVxuXG4gICAgY29uc3QgeyBkYXRhIH0gPSBhd2FpdCBjbGllbnQucXVlcnk8eyBUYXNrOiBUYXNrVHlwZVtdIH0+KHtcbiAgICAgIHF1ZXJ5OiBsaXN0VGFza3NCeVVzZXJJZCxcbiAgICAgIHZhcmlhYmxlcyxcbiAgICAgIGZldGNoUG9saWN5OiAnbm8tY2FjaGUnLFxuICAgIH0pO1xuXG4gICAgY29uc29sZS5sb2coZGF0YSwgJyBzdWNjZXNzZnVsbHkgcmV0cmlldmVkIHRhc2tzJyk7XG5cbiAgICByZXR1cm4gZGF0YT8uVGFzaztcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIGxpc3QgdGFza3MgZm9yIHVzZXJJZCcpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgbGlzdEV2ZW50c0dpdmVuSWRzID0gYXN5bmMgKFxuICBjbGllbnQ6IEFwb2xsb0NsaWVudDxOb3JtYWxpemVkQ2FjaGVPYmplY3Q+LFxuICBldmVudElkczogc3RyaW5nW11cbikgPT4ge1xuICB0cnkge1xuICAgIC8vIGxpc3RFdmVudHNCeUlkc1xuXG4gICAgY29uc3QgeyBkYXRhIH0gPSBhd2FpdCBjbGllbnQucXVlcnk8eyBFdmVudDogRXZlbnRUeXBlW10gfT4oe1xuICAgICAgcXVlcnk6IGxpc3RFdmVudHNCeUlkcyxcbiAgICAgIHZhcmlhYmxlczoge1xuICAgICAgICBpZHM6IGV2ZW50SWRzLFxuICAgICAgfSxcbiAgICB9KTtcblxuICAgIHJldHVybiBkYXRhPy5FdmVudDtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIGxpc3QgZXZlbnRzIGdpdmVuSWRzJyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCB1cGRhdGVUYXNrQnlJZEluRGIgPSBhc3luYyAoXG4gIGNsaWVudDogQXBvbGxvQ2xpZW50PE5vcm1hbGl6ZWRDYWNoZU9iamVjdD4sXG4gIHRhc2s6IFRhc2tUeXBlXG4pID0+IHtcbiAgdHJ5IHtcbiAgICAvKipcbiAgICAgICAgICogY29uc3QgcmVzdWx0ID0gYXdhaXQgY2xpZW50Lm11dGF0ZTx7IGluc2VydF9DYWxlbmRhcjogeyByZXR1cm5pbmc6IENhbGVuZGFyVHlwZVtdIH0gfT4oe1xuICAgICAgICAgICAgbXV0YXRpb246IHVwc2VydENhbGVuZGFyLFxuICAgICAgICAgICAgdmFyaWFibGVzOiB7XG4gICAgICAgICAgICAgICAgY2FsZW5kYXJzOiBbY2FsZW5kYXJWYWx1ZVRvVXBzZXJ0XSxcbiAgICAgICAgICAgIH0sXG4gICAgICAgICAgICB9KVxuICAgICAgICAgKi9cblxuICAgIGxldCB2YXJpYWJsZXM6IGFueSA9IHsgaWQ6IHRhc2s/LmlkIH07XG5cbiAgICBpZiAodGFzaz8uY29tcGxldGVkRGF0ZSAhPT0gdW5kZWZpbmVkKSB7XG4gICAgICB2YXJpYWJsZXMuY29tcGxldGVkRGF0ZSA9IHRhc2s/LmNvbXBsZXRlZERhdGU7XG4gICAgfVxuXG4gICAgaWYgKHRhc2s/LmR1cmF0aW9uICE9PSB1bmRlZmluZWQpIHtcbiAgICAgIHZhcmlhYmxlcy5kdXJhdGlvbiA9IHRhc2s/LmR1cmF0aW9uO1xuICAgIH1cblxuICAgIGlmICh0YXNrPy5ldmVudElkICE9PSB1bmRlZmluZWQpIHtcbiAgICAgIHZhcmlhYmxlcy5ldmVudElkID0gdGFzaz8uZXZlbnRJZDtcbiAgICB9XG5cbiAgICBpZiAodGFzaz8uaGFyZERlYWRsaW5lICE9PSB1bmRlZmluZWQpIHtcbiAgICAgIHZhcmlhYmxlcy5oYXJkRGVhZGxpbmUgPSB0YXNrPy5oYXJkRGVhZGxpbmU7XG4gICAgfVxuXG4gICAgaWYgKHRhc2s/LmltcG9ydGFudCAhPT0gdW5kZWZpbmVkKSB7XG4gICAgICB2YXJpYWJsZXMuaW1wb3J0YW50ID0gdGFzaz8uaW1wb3J0YW50O1xuICAgIH1cblxuICAgIGlmICh0YXNrPy5ub3RlcyAhPT0gdW5kZWZpbmVkKSB7XG4gICAgICB2YXJpYWJsZXMubm90ZXMgPSB0YXNrPy5ub3RlcztcbiAgICB9XG5cbiAgICBpZiAodGFzaz8ub3JkZXIgIT09IHVuZGVmaW5lZCkge1xuICAgICAgdmFyaWFibGVzLm9yZGVyID0gdGFzaz8ub3JkZXI7XG4gICAgfVxuXG4gICAgaWYgKHRhc2s/LnBhcmVudElkICE9PSB1bmRlZmluZWQpIHtcbiAgICAgIHZhcmlhYmxlcy5wYXJlbnRJZCA9IHRhc2s/LnBhcmVudElkO1xuICAgIH1cblxuICAgIGlmICh0YXNrPy5wcmlvcml0eSAhPT0gdW5kZWZpbmVkKSB7XG4gICAgICB2YXJpYWJsZXMucHJpb3JpdHkgPSB0YXNrPy5wcmlvcml0eTtcbiAgICB9XG5cbiAgICBpZiAodGFzaz8uc29mdERlYWRsaW5lICE9PSB1bmRlZmluZWQpIHtcbiAgICAgIHZhcmlhYmxlcy5zb2Z0RGVhZGxpbmUgPSB0YXNrPy5zb2Z0RGVhZGxpbmU7XG4gICAgfVxuXG4gICAgaWYgKHRhc2s/LnN0YXR1cyAhPT0gdW5kZWZpbmVkKSB7XG4gICAgICB2YXJpYWJsZXMuc3RhdHVzID0gdGFzaz8uc3RhdHVzO1xuICAgIH1cblxuICAgIGlmICh0YXNrPy5zeW5jRGF0YSAhPT0gdW5kZWZpbmVkKSB7XG4gICAgICB2YXJpYWJsZXMuc3luY0RhdGEgPSB0YXNrPy5zeW5jRGF0YTtcbiAgICB9XG5cbiAgICBpZiAodGFzaz8udHlwZSAhPT0gdW5kZWZpbmVkKSB7XG4gICAgICB2YXJpYWJsZXMudHlwZSA9IHRhc2s/LnR5cGU7XG4gICAgfVxuXG4gICAgY29uc3QgdXBkYXRlVGFza0J5SWQgPSBncWxgXG4gICAgICAgICAgICBtdXRhdGlvbiBVcGRhdGVUYXNrQnlJZCgkaWQ6IHV1aWQhLCAke3Rhc2s/LmNvbXBsZXRlZERhdGUgIT09IHVuZGVmaW5lZCA/ICckY29tcGxldGVkRGF0ZTogdGltZXN0YW1wdHosJyA6ICcnfSAke3Rhc2s/LmR1cmF0aW9uICE9PSB1bmRlZmluZWQgPyAnJGR1cmF0aW9uOiBJbnQsJyA6ICcnfSAke3Rhc2s/LmV2ZW50SWQgIT09IHVuZGVmaW5lZCA/ICckZXZlbnRJZDogU3RyaW5nLCcgOiAnJ30gJHt0YXNrPy5oYXJkRGVhZGxpbmUgIT09IHVuZGVmaW5lZCA/ICckaGFyZERlYWRsaW5lOiB0aW1lc3RhbXAsJyA6ICcnfSAke3Rhc2s/LmltcG9ydGFudCAhPT0gdW5kZWZpbmVkID8gJyRpbXBvcnRhbnQ6IEJvb2xlYW4sJyA6ICcnfSAke3Rhc2s/Lm5vdGVzICE9PSB1bmRlZmluZWQgPyAnJG5vdGVzOiBTdHJpbmcsJyA6ICcnfSAke3Rhc2s/Lm9yZGVyICE9PSB1bmRlZmluZWQgPyAnJG9yZGVyOiBJbnQsJyA6ICcnfSAke3Rhc2s/LnBhcmVudElkICE9PSB1bmRlZmluZWQgPyAnJHBhcmVudElkOiB1dWlkLCcgOiAnJ30gJHt0YXNrPy5wcmlvcml0eSAhPT0gdW5kZWZpbmVkID8gJyRwcmlvcml0eTogSW50LCcgOiAnJ30gJHt0YXNrPy5zb2Z0RGVhZGxpbmUgIT09IHVuZGVmaW5lZCA/ICckc29mdERlYWRsaW5lOiB0aW1lc3RhbXAsJyA6ICcnfSAke3Rhc2s/LnN0YXR1cyAhPT0gdW5kZWZpbmVkID8gJyRzdGF0dXM6IFN0cmluZywnIDogJyd9ICR7dGFzaz8uc3luY0RhdGEgIT09IHVuZGVmaW5lZCA/ICckc3luY0RhdGE6IGpzb25iLCcgOiAnJ30gJHt0YXNrPy50eXBlICE9PSB1bmRlZmluZWQgPyAnJHR5cGU6IFN0cmluZycgOiAnJ30pe1xuICAgICAgICAgICAgICAgIHVwZGF0ZV9UYXNrX2J5X3BrKHBrX2NvbHVtbnM6IHtpZDogJGlkfSwgX3NldDogeyR7dGFzaz8uY29tcGxldGVkRGF0ZSAhPT0gdW5kZWZpbmVkID8gJ2NvbXBsZXRlZERhdGU6ICRjb21wbGV0ZWREYXRlLCcgOiAnJ30gJHt0YXNrPy5kdXJhdGlvbiAhPT0gdW5kZWZpbmVkID8gJ2R1cmF0aW9uOiAkZHVyYXRpb24sJyA6ICcnfSAke3Rhc2s/LmV2ZW50SWQgIT09IHVuZGVmaW5lZCA/ICdldmVudElkOiAkZXZlbnRJZCwnIDogJyd9ICR7dGFzaz8uaGFyZERlYWRsaW5lICE9PSB1bmRlZmluZWQgPyAnaGFyZERlYWRsaW5lOiAkaGFyZERlYWRsaW5lLCcgOiAnJ30gJHt0YXNrPy5pbXBvcnRhbnQgIT09IHVuZGVmaW5lZCA/ICdpbXBvcnRhbnQ6ICRpbXBvcnRhbnQsJyA6ICcnfSAke3Rhc2s/Lm5vdGVzICE9PSB1bmRlZmluZWQgPyAnbm90ZXM6ICRub3RlcywnIDogJyd9ICR7dGFzaz8ub3JkZXIgIT09IHVuZGVmaW5lZCA/ICdvcmRlcjogJG9yZGVyLCcgOiAnJ30gJHt0YXNrPy5wYXJlbnRJZCAhPT0gdW5kZWZpbmVkID8gJ3BhcmVudElkOiAkcGFyZW50SWQsJyA6ICcnfSAke3Rhc2s/LnByaW9yaXR5ICE9PSB1bmRlZmluZWQgPyAncHJpb3JpdHk6ICRwcmlvcml0eSwnIDogJyd9ICR7dGFzaz8uc29mdERlYWRsaW5lICE9PSB1bmRlZmluZWQgPyAnc29mdERlYWRsaW5lOiAkc29mdERlYWRsaW5lLCcgOiAnJ30gJHt0YXNrPy5zdGF0dXMgIT09IHVuZGVmaW5lZCA/ICdzdGF0dXM6ICRzdGF0dXMsJyA6ICcnfSAke3Rhc2s/LnN5bmNEYXRhICE9PSB1bmRlZmluZWQgPyAnc3luY0RhdGE6ICRzeW5jRGF0YSwnIDogJyd9ICR7dGFzaz8udHlwZSAhPT0gdW5kZWZpbmVkID8gJ3R5cGU6ICR0eXBlJyA6ICcnfX0pIHtcbiAgICAgICAgICAgICAgICAgICAgY29tcGxldGVkRGF0ZVxuICAgICAgICAgICAgICAgICAgICBjcmVhdGVkRGF0ZVxuICAgICAgICAgICAgICAgICAgICBkdXJhdGlvblxuICAgICAgICAgICAgICAgICAgICBldmVudElkXG4gICAgICAgICAgICAgICAgICAgIGhhcmREZWFkbGluZVxuICAgICAgICAgICAgICAgICAgICBpZFxuICAgICAgICAgICAgICAgICAgICBpbXBvcnRhbnRcbiAgICAgICAgICAgICAgICAgICAgbm90ZXNcbiAgICAgICAgICAgICAgICAgICAgb3JkZXJcbiAgICAgICAgICAgICAgICAgICAgcGFyZW50SWRcbiAgICAgICAgICAgICAgICAgICAgcHJpb3JpdHlcbiAgICAgICAgICAgICAgICAgICAgc29mdERlYWRsaW5lXG4gICAgICAgICAgICAgICAgICAgIHN0YXR1c1xuICAgICAgICAgICAgICAgICAgICBzeW5jRGF0YVxuICAgICAgICAgICAgICAgICAgICB0eXBlXG4gICAgICAgICAgICAgICAgICAgIHVwZGF0ZWRBdFxuICAgICAgICAgICAgICAgICAgICB1c2VySWRcbiAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICB9XG4gICAgICAgIGA7XG5cbiAgICBjb25zdCByZXN1bHRzID0gYXdhaXQgY2xpZW50Lm11dGF0ZTx7IHVwZGF0ZV9UYXNrX2J5X3BrOiBUYXNrVHlwZSB9Pih7XG4gICAgICBtdXRhdGlvbjogdXBkYXRlVGFza0J5SWQsXG4gICAgICB2YXJpYWJsZXMsXG4gICAgfSk7XG5cbiAgICBjb25zb2xlLmxvZyhyZXN1bHRzPy5kYXRhPy51cGRhdGVfVGFza19ieV9waywgJyBzdWNjZXNzZnVsbHkgdXBkYXRlZCB0YXNrJyk7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byB1cGRhdGUgdGFzayBpbiBkYicpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgaW5zZXJ0VGFza0luRGIgPSBhc3luYyAoXG4gIGNsaWVudDogQXBvbGxvQ2xpZW50PE5vcm1hbGl6ZWRDYWNoZU9iamVjdD4sXG4gIHRhc2s6IFRhc2tUeXBlXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCByZXN1bHRzID0gYXdhaXQgY2xpZW50Lm11dGF0ZTx7IGluc2VydF9UYXNrX29uZTogVGFza1R5cGUgfT4oe1xuICAgICAgbXV0YXRpb246IGluc2VydFRhc2tPbmUsXG4gICAgICB2YXJpYWJsZXM6IHtcbiAgICAgICAgdGFzayxcbiAgICAgIH0sXG4gICAgfSk7XG5cbiAgICBjb25zb2xlLmxvZyhcbiAgICAgIHJlc3VsdHM/LmRhdGE/Lmluc2VydF9UYXNrX29uZSxcbiAgICAgICcgc3VjY2Vzc2Z1bGx5IGluc2VydGVkIG9uZSB0YXNrJ1xuICAgICk7XG5cbiAgICByZXR1cm4gcmVzdWx0cz8uZGF0YT8uaW5zZXJ0X1Rhc2tfb25lO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gaW5zZXJ0IHRhc2sgaW4gZGInKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IHVwc2VydE1hbnlUYXNrc0luRGIgPSBhc3luYyAoXG4gIGNsaWVudDogQXBvbGxvQ2xpZW50PE5vcm1hbGl6ZWRDYWNoZU9iamVjdD4sXG4gIHRhc2tzOiBUYXNrVHlwZVtdXG4pID0+IHtcbiAgdHJ5IHtcbiAgICAvKipcbiAgICAgICAgICogY29uc3QgcmVzdWx0ID0gYXdhaXQgY2xpZW50Lm11dGF0ZTx7IGluc2VydF9DYWxlbmRhcjogeyByZXR1cm5pbmc6IENhbGVuZGFyVHlwZVtdIH0gfT4oe1xuICAgICAgICAgICAgbXV0YXRpb246IHVwc2VydENhbGVuZGFyLFxuICAgICAgICAgICAgdmFyaWFibGVzOiB7XG4gICAgICAgICAgICAgICAgY2FsZW5kYXJzOiBbY2FsZW5kYXJWYWx1ZVRvVXBzZXJ0XSxcbiAgICAgICAgICAgIH0sXG4gICAgICAgICAgICB9KVxuICAgICAgICAgKi9cblxuICAgIGNvbnN0IHJlc3VsdHMgPSBhd2FpdCBjbGllbnQubXV0YXRlPHtcbiAgICAgIGluc2VydF9UYXNrOiB7IGFmZmVjdGVkX3Jvd3M6IG51bWJlcjsgcmV0dXJuaW5nOiBUYXNrVHlwZVtdIH07XG4gICAgfT4oe1xuICAgICAgbXV0YXRpb246IHVwc2VydFRhc2ssXG4gICAgICB2YXJpYWJsZXM6IHtcbiAgICAgICAgdGFza3MsXG4gICAgICB9LFxuICAgIH0pO1xuXG4gICAgY29uc29sZS5sb2cocmVzdWx0cz8uZGF0YSwgJyBzdWNjZXNmdWxseSB1cHNlcnRlZCBtYW55IHRhc2tzICcpO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gdXBzZXJ0IG1hbnkgdGFza3MgaW4gRGInKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IGRlbGV0ZVRhc2tHaXZlbklkID0gYXN5bmMgKFxuICBjbGllbnQ6IEFwb2xsb0NsaWVudDxOb3JtYWxpemVkQ2FjaGVPYmplY3Q+LFxuICB0YXNrSWQ6IHN0cmluZ1xuKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3QgcmVzdWx0cyA9IGF3YWl0IGNsaWVudC5tdXRhdGU8e1xuICAgICAgZGVsZXRlX1Rhc2s6IHsgYWZmZWN0ZWRfcm93czogbnVtYmVyIH07XG4gICAgfT4oe1xuICAgICAgbXV0YXRpb246IGRlbGV0ZVRhc2tCeUlkLFxuICAgICAgdmFyaWFibGVzOiB7XG4gICAgICAgIGlkOiB0YXNrSWQsXG4gICAgICB9LFxuICAgIH0pO1xuXG4gICAgY29uc29sZS5sb2cocmVzdWx0cz8uZGF0YT8uZGVsZXRlX1Rhc2ssICcgc3VjY2Vzc2Z1bGx5IGRlbGV0ZWQgdGFzayAnKTtcblxuICAgIHJldHVybiByZXN1bHRzPy5kYXRhPy5kZWxldGVfVGFzaztcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIGRlbGV0ZSB0YXNrIGdpdmVuIGlkJyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBkZWxldGVUYXNrc0dpdmVuSWRzID0gYXN5bmMgKFxuICBjbGllbnQ6IEFwb2xsb0NsaWVudDxOb3JtYWxpemVkQ2FjaGVPYmplY3Q+LFxuICB0YXNrSWRzOiBzdHJpbmdbXVxuKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3QgcmVzdWx0cyA9IGF3YWl0IGNsaWVudC5tdXRhdGU8e1xuICAgICAgZGVsZXRlX1Rhc2s6IHsgYWZmZWN0ZWRfcm93czogbnVtYmVyIH07XG4gICAgfT4oe1xuICAgICAgbXV0YXRpb246IGRlbGV0ZVRhc2tzQnlJZHMsXG4gICAgICB2YXJpYWJsZXM6IHtcbiAgICAgICAgdGFza0lkcyxcbiAgICAgIH0sXG4gICAgfSk7XG5cbiAgICBjb25zb2xlLmxvZyhcbiAgICAgIHJlc3VsdHMsXG4gICAgICAnIHN1Y2Nlc3NmdWxseSBkZWxldGVkIHRhc2tzIGJ5IGlkcyBnaXZlbiBhZmZlY3RlZCByb3dzJ1xuICAgICk7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byBkZWxldGUgdGFza3MgZ2l2bmUgaWRzJyk7XG4gIH1cbn07XG4iXX0=