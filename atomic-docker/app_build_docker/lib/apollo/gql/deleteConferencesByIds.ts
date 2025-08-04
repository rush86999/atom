import { gql } from '@apollo/client';

export default gql`
  mutation deleteConferences($ids: [String!]!) {
    delete_Conference(where: { id: { _in: $ids } }) {
      affected_rows
    }
  }
`;
