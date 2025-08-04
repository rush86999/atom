import { gql } from '@apollo/client';

export default gql`
  query GetAnyCalendar($userId: uuid!) {
    Calendar(
      where: {
        userId: { _eq: $userId }
        accessLevel: { _nin: ["reader", "freeBusyReader"] }
      }
    ) {
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
