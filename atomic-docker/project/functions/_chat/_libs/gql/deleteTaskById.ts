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
