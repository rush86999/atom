import { gql } from '@apollo/client';

export default gql`
  mutation UpdateCalendarToGlobalPrimary($id: String!) {
    update_Calendar_by_pk(
      pk_columns: { id: $id }
      _set: { globalPrimary: true }
    ) {
      accessLevel
      account
      backgroundColor
      colorId
      createdDate
      defaultReminders
      deleted
      foregroundColor
      globalPrimary
      id
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
