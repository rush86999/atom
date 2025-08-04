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
