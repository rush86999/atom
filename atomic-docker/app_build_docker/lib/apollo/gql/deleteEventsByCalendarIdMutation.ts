import { gql } from '@apollo/client';

export default gql`
  mutation DeleteEventsByCalendarId($calendarId: String!) {
    delete_Event(where: { calendarId: { _eq: $calendarId } }) {
      affected_rows
    }
  }
`;
