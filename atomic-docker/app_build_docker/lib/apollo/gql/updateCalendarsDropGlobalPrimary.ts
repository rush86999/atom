import { gql } from '@apollo/client';

export default gql`
  mutation UpdateCalendarsDropGlobalPrimary($ids: [String!]!) {
    update_Calendar(
      where: { id: { _in: $ids } }
      _set: { globalPrimary: false }
    ) {
      affected_rows
      returning {
        accessLevel
        account
        backgroundColor
        colorId
        createdDate
        defaultReminders
        deleted
        foregroundColor
        globalPrimary
        id
        modifiable
        pageToken
        primary
        resource
        syncToken
        title
        updatedAt
        userId
      }
    }
  }
`;
