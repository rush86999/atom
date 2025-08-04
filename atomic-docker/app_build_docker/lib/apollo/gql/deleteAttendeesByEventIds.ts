import { gql } from '@apollo/client';

export default gql`
  mutation DeleteAttendees($eventIds: [String!]!) {
    delete_Attendee(where: { eventId: { _in: $eventIds } }) {
      returning {
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
      affected_rows
    }
  }
`;
