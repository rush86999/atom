import { gql } from '@apollo/client';

export default gql`
  query GetCalendarIntegrationByResource(
    $userId: uuid!
    $resource: String!
    $name: String!
  ) {
    Calendar_Integration(
      where: {
        userId: { _eq: $userId }
        resource: { _eq: $resource }
        name: { _eq: $name }
      }
    ) {
      id
      token
      refreshToken
      resource
      name
      enabled
      syncEnabled
      deleted
      expiresAt
      pageToken
      syncToken
      appId
      appEmail
      appAccountId
      contactName
      contactEmail
      createdDate
      updatedAt
      userId
      clientType
    }
  }
`;
