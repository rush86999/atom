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
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiaW5zZXJ0VGFza09uZS5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImluc2VydFRhc2tPbmUudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6IkFBQUEsZUFBZTs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7OztDQXNCZCxDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiZXhwb3J0IGRlZmF1bHQgYFxuICAgIG11dGF0aW9uIEluc2VydFRhc2tPbmUoJHRhc2s6IFRhc2tfaW5zZXJ0X2lucHV0ISkge1xuICAgICAgICBpbnNlcnRfVGFza19vbmUob2JqZWN0OiAkdGFzaykge1xuICAgICAgICAgICAgY29tcGxldGVkRGF0ZVxuICAgICAgICAgICAgY3JlYXRlZERhdGVcbiAgICAgICAgICAgIGR1cmF0aW9uXG4gICAgICAgICAgICBldmVudElkXG4gICAgICAgICAgICBoYXJkRGVhZGxpbmVcbiAgICAgICAgICAgIGlkXG4gICAgICAgICAgICBpbXBvcnRhbnRcbiAgICAgICAgICAgIG5vdGVzXG4gICAgICAgICAgICBvcmRlclxuICAgICAgICAgICAgcGFyZW50SWRcbiAgICAgICAgICAgIHByaW9yaXR5XG4gICAgICAgICAgICBzb2Z0RGVhZGxpbmVcbiAgICAgICAgICAgIHN0YXR1c1xuICAgICAgICAgICAgc3luY0RhdGFcbiAgICAgICAgICAgIHR5cGVcbiAgICAgICAgICAgIHVwZGF0ZWRBdFxuICAgICAgICAgICAgdXNlcklkXG4gICAgICAgIH1cbiAgICB9XG5gO1xuIl19