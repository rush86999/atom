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
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoibGlzdENvbmZlcmVuY2VzQnlJZHMuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJsaXN0Q29uZmVyZW5jZXNCeUlkcy50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiQUFBQSxlQUFlOzs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7O0NBeUJkLENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJleHBvcnQgZGVmYXVsdCBgcXVlcnkgbGlzdENvbmZlcmVuY2VzQnlJZHMoJGlkczogW1N0cmluZyFdISkge1xuICBDb25mZXJlbmNlKHdoZXJlOiB7aWQ6IHtfaW46ICRpZHN9fSkge1xuICAgIGFwcFxuICAgIGNhbGVuZGFySWRcbiAgICBjcmVhdGVkRGF0ZVxuICAgIGRlbGV0ZWRcbiAgICBlbnRyeVBvaW50c1xuICAgIGhhbmdvdXRMaW5rXG4gICAgaWNvblVyaVxuICAgIGlkXG4gICAgaXNIb3N0XG4gICAgam9pblVybFxuICAgIGtleVxuICAgIG5hbWVcbiAgICBub3Rlc1xuICAgIHBhcmFtZXRlcnNcbiAgICByZXF1ZXN0SWRcbiAgICBzdGFydFVybFxuICAgIHN0YXR1c1xuICAgIHR5cGVcbiAgICB1cGRhdGVkQXRcbiAgICB1c2VySWRcbiAgICB6b29tUHJpdmF0ZU1lZXRpbmdcbiAgfVxufVxuYDtcbiJdfQ==