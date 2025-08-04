import { gql } from '@apollo/client';

export default gql`
  mutation InsertAttendee($attendee: Attendee_insert_input!) {
    insert_Attendee_one(object: $attendee) {
      additionalGuests
      comment
      contactId
      createdDate
      deleted
      emails
      eventId
      id
      imAddresses
      name
      optional
      phoneNumbers
      resource
      responseStatus
      updatedAt
      userId
    }
  }
`;
