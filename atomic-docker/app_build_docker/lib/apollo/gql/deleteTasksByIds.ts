import { gql } from '@apollo/client';

export default gql`
  mutation DeleteTasksByIds($taskIds: [uuid!]!) {
    delete_Task(where: { id: { _in: $taskIds } }) {
      affected_rows
    }
  }
`;
