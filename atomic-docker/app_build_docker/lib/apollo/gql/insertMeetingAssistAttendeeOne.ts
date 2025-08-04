import { gql } from '@apollo/client';

export default gql`
  mutation InsertMeetingAssistAttendee(
    $attendee: Meeting_Assist_Attendee_insert_input!
  ) {
    insert_Meeting_Assist_Attendee_one(object: $attendee) {
      createdDate
      contactId
      emails
      externalAttendee
      hostId
      id
      imAddresses
      meetingId
      name
      phoneNumbers
      primaryEmail
      timezone
      updatedAt
      userId
    }
  }
`;
