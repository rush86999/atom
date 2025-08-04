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
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiZGVsZXRlQ29uZmVyZW5jZUJ5SWQuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJkZWxldGVDb25mZXJlbmNlQnlJZC50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiQUFBQSxlQUFlOzs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7OztDQTBCZCxDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiZXhwb3J0IGRlZmF1bHQgYFxubXV0YXRpb24gRGVsZXRlQ29uZmVyZW5jZUJ5SWQoJGlkOiBTdHJpbmchKSB7XG4gIGRlbGV0ZV9Db25mZXJlbmNlX2J5X3BrKGlkOiAkaWQpIHtcbiAgICBhcHBcbiAgICBjYWxlbmRhcklkXG4gICAgY3JlYXRlZERhdGVcbiAgICBkZWxldGVkXG4gICAgZW50cnlQb2ludHNcbiAgICBoYW5nb3V0TGlua1xuICAgIGljb25VcmlcbiAgICBpZFxuICAgIGlzSG9zdFxuICAgIGpvaW5VcmxcbiAgICBrZXlcbiAgICBuYW1lXG4gICAgbm90ZXNcbiAgICBwYXJhbWV0ZXJzXG4gICAgcmVxdWVzdElkXG4gICAgc3RhcnRVcmxcbiAgICBzdGF0dXNcbiAgICB0eXBlXG4gICAgdXBkYXRlZEF0XG4gICAgdXNlcklkXG4gICAgem9vbVByaXZhdGVNZWV0aW5nXG4gIH1cbn1cbmA7XG4iXX0=