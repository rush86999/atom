import { gql } from '@apollo/client';

export default gql`
  query ListCalendarPushNotificationsByUserId($userId: uuid!) {
    Calendar_Push_Notification(where: { userId: { _eq: $userId } }) {
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
