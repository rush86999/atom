export default `
mutation DeleteTaskById($id: uuid!) {
  delete_Task_by_pk(id: $id) {
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
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiZGVsZXRlVGFza0J5SWQuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJkZWxldGVUYXNrQnlJZC50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiQUFBQSxlQUFlOzs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7O0NBc0JkLENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJleHBvcnQgZGVmYXVsdCBgXG5tdXRhdGlvbiBEZWxldGVUYXNrQnlJZCgkaWQ6IHV1aWQhKSB7XG4gIGRlbGV0ZV9UYXNrX2J5X3BrKGlkOiAkaWQpIHtcbiAgICBjb21wbGV0ZWREYXRlXG4gICAgY3JlYXRlZERhdGVcbiAgICBkdXJhdGlvblxuICAgIGV2ZW50SWRcbiAgICBoYXJkRGVhZGxpbmVcbiAgICBpZFxuICAgIGltcG9ydGFudFxuICAgIG5vdGVzXG4gICAgb3JkZXJcbiAgICBwYXJlbnRJZFxuICAgIHByaW9yaXR5XG4gICAgc29mdERlYWRsaW5lXG4gICAgc3RhdHVzXG4gICAgc3luY0RhdGFcbiAgICB0eXBlXG4gICAgdXBkYXRlZEF0XG4gICAgdXNlcklkXG4gIH1cbn1cbmA7XG4iXX0=