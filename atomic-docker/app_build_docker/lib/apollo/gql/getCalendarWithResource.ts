import { gql } from '@apollo/client';

export default gql`
  query GetCalendarWithResource($userId: uuid!, $resource: String!) {
    Calendar(
      where: {
        userId: { _eq: $userId }
        resource: { _eq: $resource }
        accessLevel: { _in: ["writer", "owner"] }
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
      primary
      pageToken
      syncToken
    }
  }
`;
