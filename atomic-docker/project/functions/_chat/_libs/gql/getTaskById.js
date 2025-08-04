export default `
query GetTaskById($id: uuid!) {
  Task_by_pk(id: $id) {
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
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiZ2V0VGFza0J5SWQuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJnZXRUYXNrQnlJZC50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiQUFBQSxlQUFlOzs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7O0NBc0JkLENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJleHBvcnQgZGVmYXVsdCBgXG5xdWVyeSBHZXRUYXNrQnlJZCgkaWQ6IHV1aWQhKSB7XG4gIFRhc2tfYnlfcGsoaWQ6ICRpZCkge1xuICAgIGNvbXBsZXRlZERhdGVcbiAgICBjcmVhdGVkRGF0ZVxuICAgIGR1cmF0aW9uXG4gICAgZXZlbnRJZFxuICAgIGhhcmREZWFkbGluZVxuICAgIGlkXG4gICAgaW1wb3J0YW50XG4gICAgbm90ZXNcbiAgICBvcmRlclxuICAgIHBhcmVudElkXG4gICAgcHJpb3JpdHlcbiAgICBzb2Z0RGVhZGxpbmVcbiAgICBzdGF0dXNcbiAgICBzeW5jRGF0YVxuICAgIHR5cGVcbiAgICB1cGRhdGVkQXRcbiAgICB1c2VySWRcbiAgfVxufVxuYDtcbiJdfQ==