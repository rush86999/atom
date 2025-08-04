import { gql } from '@apollo/client';

export default gql`
  query GetCalendarPushNotificationByCalendarId($calendarId: String!) {
    Calendar_Push_Notification(
      where: { calendarId: { _eq: $calendarId } }
      limit: 1
    ) {
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
