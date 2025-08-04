export default `
    mutation InsertAttendeesForEvent($attendees: [Attendee_insert_input!]!) {
        insert_Attendee(objects: $attendees, on_conflict: {constraint: Attendee_pkey, update_columns: [
            additionalGuests,
            comment,
            contactId,
            emails,
            imAddresses,
            phoneNumbers,
            resource,
            responseStatus,
            updatedAt,
        ]}) {
                affected_rows
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
        }
    }

`;
