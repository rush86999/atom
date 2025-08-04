import { gql } from '@apollo/client';

export default gql`
  query ListMeetingAssistInvites($meetingId: uuid!) {
    Meeting_Assist_Invite(where: { meetingId: { _eq: $meetingId } }) {
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
`;
