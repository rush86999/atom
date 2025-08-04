import { gql } from '@apollo/client';

export default gql`
  mutation InsertCalendar($calendar: Calendar_insert_input!) {
    insert_Calendar_one(
      object: $calendar
      on_conflict: {
        constraint: Calendar_pkey
        update_columns: [
          title
          colorId
          account
          accessLevel
          resource
          modifiable
          defaultReminders
          globalPrimary
          backgroundColor
          foregroundColor
          deleted
          updatedAt
          pageToken
          syncToken
        ]
      }
    ) {
      id
      accessLevel
      account
      backgroundColor
      colorId
      createdDate
      defaultReminders
      deleted
      globalPrimary
      foregroundColor
      modifiable
      resource
      title
      updatedAt
      userId
      pageToken
      syncToken
    }
  }
`;
