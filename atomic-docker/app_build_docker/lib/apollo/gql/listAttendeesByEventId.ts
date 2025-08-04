import { gql } from '@apollo/client';

export default gql`
  query listAttendeesByEventId($eventId: String!) {
    Attendee(where: { eventId: { _eq: $eventId } }) {
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
