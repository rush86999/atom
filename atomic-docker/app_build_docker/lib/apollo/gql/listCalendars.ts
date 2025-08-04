import { gql } from '@apollo/client';

export default gql`
  query ListCalendars($userId: uuid!) {
    Calendar(where: { userId: { _eq: $userId } }) {
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
  }
`;
