export default `
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
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiZ2V0Q29uZmVyZW5jZUJ5SWQuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJnZXRDb25mZXJlbmNlQnlJZC50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiQUFBQSxlQUFlOzs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7OztDQTBCZCxDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiZXhwb3J0IGRlZmF1bHQgYFxucXVlcnkgR2V0Q29uZmVyZW5jZUJ5SWQoJGlkOiBTdHJpbmchKSB7XG4gIENvbmZlcmVuY2VfYnlfcGsoaWQ6ICRpZCkge1xuICAgIGlkXG4gICAgdXNlcklkXG4gICAgcmVxdWVzdElkXG4gICAgdHlwZVxuICAgIHN0YXR1c1xuICAgIGNhbGVuZGFySWRcbiAgICBpY29uVXJpXG4gICAgbmFtZVxuICAgIG5vdGVzXG4gICAgZW50cnlQb2ludHNcbiAgICBwYXJhbWV0ZXJzXG4gICAgYXBwXG4gICAga2V5XG4gICAgaGFuZ291dExpbmtcbiAgICBqb2luVXJsXG4gICAgc3RhcnRVcmxcbiAgICB6b29tUHJpdmF0ZU1lZXRpbmdcbiAgICBkZWxldGVkXG4gICAgY3JlYXRlZERhdGVcbiAgICB1cGRhdGVkQXRcbiAgICBpc0hvc3RcbiAgfVxufVxuYDtcbiJdfQ==