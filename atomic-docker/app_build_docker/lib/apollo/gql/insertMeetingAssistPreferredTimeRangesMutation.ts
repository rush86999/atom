import { gql } from '@apollo/client';

export default gql`
  mutation InsertMeetingAssistPreferredTimeRanges(
    $meetingAssistPreferredTimeRanges: [Meeting_Assist_Preferred_Time_Range_insert_input!]!
  ) {
    insert_Meeting_Assist_Preferred_Time_Range(
      objects: $meetingAssistPreferredTimeRanges
    ) {
      affected_rows
      returning {
        attendeeId
        createdDate
        dayOfWeek
        endTime
        hostId
        id
        meetingId
        startTime
        updatedAt
      }
    }
  }
`;
