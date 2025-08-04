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
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiaW5zZXJ0QXR0ZW5kZWVzRm9yRXZlbnQuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJpbnNlcnRBdHRlbmRlZXNGb3JFdmVudC50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiQUFBQSxlQUFlOzs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7OztDQW1DZCxDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiZXhwb3J0IGRlZmF1bHQgYFxuICAgIG11dGF0aW9uIEluc2VydEF0dGVuZGVlc0ZvckV2ZW50KCRhdHRlbmRlZXM6IFtBdHRlbmRlZV9pbnNlcnRfaW5wdXQhXSEpIHtcbiAgICAgICAgaW5zZXJ0X0F0dGVuZGVlKG9iamVjdHM6ICRhdHRlbmRlZXMsIG9uX2NvbmZsaWN0OiB7Y29uc3RyYWludDogQXR0ZW5kZWVfcGtleSwgdXBkYXRlX2NvbHVtbnM6IFtcbiAgICAgICAgICAgIGFkZGl0aW9uYWxHdWVzdHMsXG4gICAgICAgICAgICBjb21tZW50LFxuICAgICAgICAgICAgY29udGFjdElkLFxuICAgICAgICAgICAgZW1haWxzLFxuICAgICAgICAgICAgaW1BZGRyZXNzZXMsXG4gICAgICAgICAgICBwaG9uZU51bWJlcnMsXG4gICAgICAgICAgICByZXNvdXJjZSxcbiAgICAgICAgICAgIHJlc3BvbnNlU3RhdHVzLFxuICAgICAgICAgICAgdXBkYXRlZEF0LFxuICAgICAgICBdfSkge1xuICAgICAgICAgICAgICAgIGFmZmVjdGVkX3Jvd3NcbiAgICAgICAgICAgICAgICByZXR1cm5pbmcge1xuICAgICAgICAgICAgICAgIGFkZGl0aW9uYWxHdWVzdHNcbiAgICAgICAgICAgICAgICBjb21tZW50XG4gICAgICAgICAgICAgICAgY29udGFjdElkXG4gICAgICAgICAgICAgICAgY3JlYXRlZERhdGVcbiAgICAgICAgICAgICAgICBkZWxldGVkXG4gICAgICAgICAgICAgICAgZW1haWxzXG4gICAgICAgICAgICAgICAgZXZlbnRJZFxuICAgICAgICAgICAgICAgIGlkXG4gICAgICAgICAgICAgICAgaW1BZGRyZXNzZXNcbiAgICAgICAgICAgICAgICBuYW1lXG4gICAgICAgICAgICAgICAgb3B0aW9uYWxcbiAgICAgICAgICAgICAgICBwaG9uZU51bWJlcnNcbiAgICAgICAgICAgICAgICByZXNvdXJjZVxuICAgICAgICAgICAgICAgIHJlc3BvbnNlU3RhdHVzXG4gICAgICAgICAgICAgICAgdXBkYXRlZEF0XG4gICAgICAgICAgICAgICAgdXNlcklkXG4gICAgICAgICAgICB9XG4gICAgICAgIH1cbiAgICB9XG5cbmA7XG4iXX0=