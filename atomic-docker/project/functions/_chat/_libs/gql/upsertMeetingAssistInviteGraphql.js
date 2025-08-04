export default `
    mutation InsertMeetingAssistInvite($meetingAssistInvites: [Meeting_Assist_Invite_insert_input!]!) {
        insert_Meeting_Assist_Invite(
            objects: $meetingAssistInvites,
            on_conflict: {
            constraint: Meeting_Assist_Invite_pkey,
            update_columns: [
                email,
                hostId,
                hostName,
                meetingId,
                name,
                response,
                updatedAt,
                userId,
                contactId,
            ]}) {
            affected_rows
            returning {
                createdDate
                email
                hostId
                hostName
                id
                meetingId
                name
                response
                updatedAt
                userId
                contactId
            }
        }
    }
`;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoidXBzZXJ0TWVldGluZ0Fzc2lzdEludml0ZUdyYXBocWwuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJ1cHNlcnRNZWV0aW5nQXNzaXN0SW52aXRlR3JhcGhxbC50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiQUFBQSxlQUFlOzs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Q0FpQ2QsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImV4cG9ydCBkZWZhdWx0IGBcbiAgICBtdXRhdGlvbiBJbnNlcnRNZWV0aW5nQXNzaXN0SW52aXRlKCRtZWV0aW5nQXNzaXN0SW52aXRlczogW01lZXRpbmdfQXNzaXN0X0ludml0ZV9pbnNlcnRfaW5wdXQhXSEpIHtcbiAgICAgICAgaW5zZXJ0X01lZXRpbmdfQXNzaXN0X0ludml0ZShcbiAgICAgICAgICAgIG9iamVjdHM6ICRtZWV0aW5nQXNzaXN0SW52aXRlcyxcbiAgICAgICAgICAgIG9uX2NvbmZsaWN0OiB7XG4gICAgICAgICAgICBjb25zdHJhaW50OiBNZWV0aW5nX0Fzc2lzdF9JbnZpdGVfcGtleSxcbiAgICAgICAgICAgIHVwZGF0ZV9jb2x1bW5zOiBbXG4gICAgICAgICAgICAgICAgZW1haWwsXG4gICAgICAgICAgICAgICAgaG9zdElkLFxuICAgICAgICAgICAgICAgIGhvc3ROYW1lLFxuICAgICAgICAgICAgICAgIG1lZXRpbmdJZCxcbiAgICAgICAgICAgICAgICBuYW1lLFxuICAgICAgICAgICAgICAgIHJlc3BvbnNlLFxuICAgICAgICAgICAgICAgIHVwZGF0ZWRBdCxcbiAgICAgICAgICAgICAgICB1c2VySWQsXG4gICAgICAgICAgICAgICAgY29udGFjdElkLFxuICAgICAgICAgICAgXX0pIHtcbiAgICAgICAgICAgIGFmZmVjdGVkX3Jvd3NcbiAgICAgICAgICAgIHJldHVybmluZyB7XG4gICAgICAgICAgICAgICAgY3JlYXRlZERhdGVcbiAgICAgICAgICAgICAgICBlbWFpbFxuICAgICAgICAgICAgICAgIGhvc3RJZFxuICAgICAgICAgICAgICAgIGhvc3ROYW1lXG4gICAgICAgICAgICAgICAgaWRcbiAgICAgICAgICAgICAgICBtZWV0aW5nSWRcbiAgICAgICAgICAgICAgICBuYW1lXG4gICAgICAgICAgICAgICAgcmVzcG9uc2VcbiAgICAgICAgICAgICAgICB1cGRhdGVkQXRcbiAgICAgICAgICAgICAgICB1c2VySWRcbiAgICAgICAgICAgICAgICBjb250YWN0SWRcbiAgICAgICAgICAgIH1cbiAgICAgICAgfVxuICAgIH1cbmA7XG4iXX0=