export default `
mutation DeleteConferenceById($id: String!) {
  delete_Conference_by_pk(id: $id) {
    app
    calendarId
    createdDate
    deleted
    entryPoints
    hangoutLink
    iconUri
    id
    isHost
    joinUrl
    key
    name
    notes
    parameters
    requestId
    startUrl
    status
    type
    updatedAt
    userId
    zoomPrivateMeeting
  }
}
`;
