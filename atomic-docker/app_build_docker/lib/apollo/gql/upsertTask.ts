import { gql } from '@apollo/client';

export default gql`
  mutation UpsertTask($tasks: [Task_insert_input!]!) {
    insert_Task(
      objects: $tasks
      on_conflict: {
        constraint: Task_pkey
        update_columns: [
          completedDate
          duration
          eventId
          hardDeadline
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
        ]
      }
    ) {
      affected_rows
      returning {
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
  }
`;
