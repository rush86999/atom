import { gql } from '@apollo/client';

export default gql`
  mutation DeleteCalendarPushNotificationByCalendarId($calendarId: String!) {
    delete_Calendar_Push_Notification(
      where: { calendarId: { _eq: $calendarId } }
    ) {
      affected_rows
    }
  }
`;
