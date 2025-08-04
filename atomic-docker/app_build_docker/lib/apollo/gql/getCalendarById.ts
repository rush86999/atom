import { gql } from '@apollo/client';

export default gql`
  query GetCalendarById($id: String!) {
    calendarById(id: $id) {
      # Renamed from Calendar_by_pk
      id
      title
      colorId # Assuming field names remain similar or are camelCased by PostGraphile
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
      # Ensure all field names are camelCase if originally snake_case in DB
    }
  }
`;
