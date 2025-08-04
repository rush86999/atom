declare const _default: "\nquery GetTaskById($id: uuid!) {\n  Task_by_pk(id: $id) {\n    completedDate\n    createdDate\n    duration\n    eventId\n    hardDeadline\n    id\n    important\n    notes\n    order\n    parentId\n    priority\n    softDeadline\n    status\n    syncData\n    type\n    updatedAt\n    userId\n  }\n}\n";
export default _default;
