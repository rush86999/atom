export default `query listConferencesByIds($ids: [String!]!) {
  Conference(where: {id: {_in: $ids}}) {
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
