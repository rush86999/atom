import { gql } from '@apollo/client';

export default gql`
  query GetConferenceById($id: String!) {
    Conference_by_pk(id: $id) {
      id
      userId
      requestId
      type
      status
      calendarId
      iconUri
      name
      notes
      entryPoints
      parameters
      app
      key
      hangoutLink
      joinUrl
      startUrl
      zoomPrivateMeeting
      deleted
      createdDate
      updatedAt
      isHost
    }
  }
`;
