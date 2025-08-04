import { gql } from '@apollo/client';

export default gql`
  query GetGlobalPrimaryCalendar($userId: uuid!) {
    Calendar(
      where: { userId: { _eq: $userId }, globalPrimary: { _eq: true } }
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
    }
  }
`;
