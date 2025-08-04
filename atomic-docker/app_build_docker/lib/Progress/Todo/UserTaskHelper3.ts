import { ApolloClient, gql, NormalizedCacheObject } from '@apollo/client';
import deleteTaskById from '@lib/apollo/gql/deleteTaskById';
import deleteTasksByIds from '@lib/apollo/gql/deleteTasksByIds';
import getTaskById from '@lib/apollo/gql/getTaskById';
import insertTaskOne from '@lib/apollo/gql/insertTaskOne';
import listEventsByIds from '@lib/apollo/gql/listEventsByIds';
import upsertTask from '@lib/apollo/gql/upsertTask';
import { EventType } from '@lib/dataTypes/EventType';
import { TaskType } from '@lib/dataTypes/TaskType';

export const getTaskGivenId = async (
  client: ApolloClient<NormalizedCacheObject>,
  taskId: string
) => {
  try {
    const { data } = await client.query<{ Task_by_pk: TaskType }>({
      query: getTaskById,
      variables: {
        id: taskId,
      },
    });

    console.log(data?.Task_by_pk, ' successfully got task by id');
    return data?.Task_by_pk;
  } catch (e) {
    console.log(e, ' unable to get task given Id');
  }
};

export const listTasksGivenUserId = async (
  client: ApolloClient<NormalizedCacheObject>,
  userId: string,
  type?: string
) => {
  try {
    const listTasksByUserId = gql`
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
    const variables: { userId: string; type?: string } = {
      userId,
    };

    if (type) {
      variables.type = type;
    }

    const { data } = await client.query<{ Task: TaskType[] }>({
      query: listTasksByUserId,
      variables,
      fetchPolicy: 'no-cache',
    });

    console.log(data, ' successfully retrieved tasks');

    return data?.Task;
  } catch (e) {
    console.log(e, ' unable to list tasks for userId');
  }
};

export const listEventsGivenIds = async (
  client: ApolloClient<NormalizedCacheObject>,
  eventIds: string[]
) => {
  try {
    // listEventsByIds

    const { data } = await client.query<{ Event: EventType[] }>({
      query: listEventsByIds,
      variables: {
        ids: eventIds,
      },
    });

    return data?.Event;
  } catch (e) {
    console.log(e, ' unable to list events givenIds');
  }
};

export const updateTaskByIdInDb = async (
  client: ApolloClient<NormalizedCacheObject>,
  task: TaskType
) => {
  try {
    /**
         * const result = await client.mutate<{ insert_Calendar: { returning: CalendarType[] } }>({
            mutation: upsertCalendar,
            variables: {
                calendars: [calendarValueToUpsert],
            },
            })
         */

    let variables: any = { id: task?.id };

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

    const updateTaskById = gql`
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

    const results = await client.mutate<{ update_Task_by_pk: TaskType }>({
      mutation: updateTaskById,
      variables,
    });

    console.log(results?.data?.update_Task_by_pk, ' successfully updated task');
  } catch (e) {
    console.log(e, ' unable to update task in db');
  }
};

export const insertTaskInDb = async (
  client: ApolloClient<NormalizedCacheObject>,
  task: TaskType
) => {
  try {
    const results = await client.mutate<{ insert_Task_one: TaskType }>({
      mutation: insertTaskOne,
      variables: {
        task,
      },
    });

    console.log(
      results?.data?.insert_Task_one,
      ' successfully inserted one task'
    );

    return results?.data?.insert_Task_one;
  } catch (e) {
    console.log(e, ' unable to insert task in db');
  }
};

export const upsertManyTasksInDb = async (
  client: ApolloClient<NormalizedCacheObject>,
  tasks: TaskType[]
) => {
  try {
    /**
         * const result = await client.mutate<{ insert_Calendar: { returning: CalendarType[] } }>({
            mutation: upsertCalendar,
            variables: {
                calendars: [calendarValueToUpsert],
            },
            })
         */

    const results = await client.mutate<{
      insert_Task: { affected_rows: number; returning: TaskType[] };
    }>({
      mutation: upsertTask,
      variables: {
        tasks,
      },
    });

    console.log(results?.data, ' succesfully upserted many tasks ');
  } catch (e) {
    console.log(e, ' unable to upsert many tasks in Db');
  }
};

export const deleteTaskGivenId = async (
  client: ApolloClient<NormalizedCacheObject>,
  taskId: string
) => {
  try {
    const results = await client.mutate<{
      delete_Task: { affected_rows: number };
    }>({
      mutation: deleteTaskById,
      variables: {
        id: taskId,
      },
    });

    console.log(results?.data?.delete_Task, ' successfully deleted task ');

    return results?.data?.delete_Task;
  } catch (e) {
    console.log(e, ' unable to delete task given id');
  }
};

export const deleteTasksGivenIds = async (
  client: ApolloClient<NormalizedCacheObject>,
  taskIds: string[]
) => {
  try {
    const results = await client.mutate<{
      delete_Task: { affected_rows: number };
    }>({
      mutation: deleteTasksByIds,
      variables: {
        taskIds,
      },
    });

    console.log(
      results,
      ' successfully deleted tasks by ids given affected rows'
    );
  } catch (e) {
    console.log(e, ' unable to delete tasks givne ids');
  }
};
