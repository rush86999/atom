import { gql } from '@apollo/client';

export default gql`
  mutation DeleteCalendarsByIds($ids: [String!]!) {
    delete_Calendar(where: { id: { _in: $ids } }) {
      affected_rows
    }
  }
`;
