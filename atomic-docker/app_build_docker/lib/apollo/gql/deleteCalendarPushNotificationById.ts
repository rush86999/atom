import { gql } from '@apollo/client';

export default gql`
  mutation DeleteCalendarPushNotificationById($id: String!) {
    delete_Calendar_Push_Notification_by_pk(id: $id) {
      calendarId
      createdDate
      expiration
      id
      resourceId
      resourceUri
      token
      updatedAt
      userId
    }
  }
`;
