import { gql } from '@apollo/client';

export default gql`
  mutation InsertCalendar_Integration(
    $calendar_integrations: [Calendar_Integration_insert_input!]!
  ) {
    insert_Calendar_Integration(
      objects: $calendar_integrations
      on_conflict: {
        constraint: Calendar_Integration_pkey
        update_columns: [
          token
          refreshToken
          resource
          name
          enabled
          syncEnabled
          expiresAt
          pageToken
          syncToken
          appId
          appEmail
          appAccountId
          contactName
          contactEmail
          deleted
          updatedAt
          clientType
        ]
      }
    ) {
      returning {
        id
      }
    }
  }
`;
