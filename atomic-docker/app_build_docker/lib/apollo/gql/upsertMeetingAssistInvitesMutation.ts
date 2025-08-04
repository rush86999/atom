import { gql } from '@apollo/client';

export default gql`
  mutation InsertMeetingAssistInvite(
    $meetingAssistInvites: [Meeting_Assist_Invite_insert_input!]!
  ) {
    insert_Meeting_Assist_Invite(
      objects: $meetingAssistInvites
      on_conflict: {
        constraint: Meeting_Assist_Invite_pkey
        update_columns: [
          email
          hostId
          hostName
          meetingId
          name
          response
          updatedAt
          userId
          contactId
        ]
      }
    ) {
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
