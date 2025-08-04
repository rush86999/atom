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
