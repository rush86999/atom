import { gql } from '@apollo/client';

export default gql`
  query GetCalendarIntegrationById($id: uuid!) {
    Calendar_Integration_by_pk(id: $id) {
      appAccountId
      appEmail
      appId
      colors
      contactEmail
      contactName
      createdDate
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
      clientType
    }
  }
`;
