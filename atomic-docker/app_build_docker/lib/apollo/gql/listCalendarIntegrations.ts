import { gql } from '@apollo/client';

export default gql`
  query ListCalendarIntegrations($userId: uuid!) {
    Calendar_Integration(where: { userId: { _eq: $userId } }) {
      appAccountId
      appEmail
      appId
      colors
      contactEmail
      createdDate
      contactName
      deleted
      enabled
      expiresAt
      id
      name
      pageToken
      password
      refreshToken
      resource
      syncEnabled
      syncToken
      token
      updatedAt
      userId
      username
    }
  }
`;
