export default `
    mutation InsertTaskOne($task: Task_insert_input!) {
        insert_Task_one(object: $task) {
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
