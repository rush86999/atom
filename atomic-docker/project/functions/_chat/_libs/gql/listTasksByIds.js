export default `
query listTasksByIds($ids: [uuid!]!) {
  Task(where: {id: {_in: $ids}}) {
    completedDate
    createdDate
    duration
    eventId
    hardDeadline
    id
    important
    notes
    order
    parentId
    priority
    softDeadline
    status
    syncData
    type
    updatedAt
    userId
  }
}
`;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoibGlzdFRhc2tzQnlJZHMuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJsaXN0VGFza3NCeUlkcy50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiQUFBQSxlQUFlOzs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7O0NBc0JkLENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJleHBvcnQgZGVmYXVsdCBgXG5xdWVyeSBsaXN0VGFza3NCeUlkcygkaWRzOiBbdXVpZCFdISkge1xuICBUYXNrKHdoZXJlOiB7aWQ6IHtfaW46ICRpZHN9fSkge1xuICAgIGNvbXBsZXRlZERhdGVcbiAgICBjcmVhdGVkRGF0ZVxuICAgIGR1cmF0aW9uXG4gICAgZXZlbnRJZFxuICAgIGhhcmREZWFkbGluZVxuICAgIGlkXG4gICAgaW1wb3J0YW50XG4gICAgbm90ZXNcbiAgICBvcmRlclxuICAgIHBhcmVudElkXG4gICAgcHJpb3JpdHlcbiAgICBzb2Z0RGVhZGxpbmVcbiAgICBzdGF0dXNcbiAgICBzeW5jRGF0YVxuICAgIHR5cGVcbiAgICB1cGRhdGVkQXRcbiAgICB1c2VySWRcbiAgfVxufVxuYDtcbiJdfQ==