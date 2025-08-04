import { gql } from '@apollo/client';

export default gql`
  mutation UpdateCalendarIntegrationById(
    $id: uuid!
    $appEmail: String
    $appAccountId: String
    $appId: String
    $contactEmail: String
    $colors: jsonb
    $contactName: String
    $deleted: Boolean
    $enabled: Boolean
    $expiresAt: timestamptz
    $name: String
    $pageToken: String
    $password: String
    $refreshToken: String
    $resource: String
    $syncEnabled: Boolean
    $syncToken: String
    $token: String
    $updatedAt: timestamptz
    $userId: uuid
    $username: String
  ) {
    update_Calendar_Integration_by_pk(
      _set: {
        appEmail: $appEmail
        appAccountId: $appAccountId
        appId: $appId
        contactEmail: $contactEmail
        colors: $colors
        contactName: $contactName
        deleted: $deleted
        enabled: $enabled
        expiresAt: $expiresAt
        name: $name
        pageToken: $pageToken
        password: $password
        refreshToken: $refreshToken
        resource: $resource
        syncEnabled: $syncEnabled
        syncToken: $syncToken
        token: $token
        updatedAt: $updatedAt
        userId: $userId
        username: $username
      }
      pk_columns: { id: $id }
    ) {
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
      syncEnabled
      resource
      token
      syncToken
      updatedAt
      userId
      username
      clientType
    }
  }
`;
