"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const client_1 = require("@apollo/client");
exports.default = (0, client_1.gql) `
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
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiaW5zZXJ0VGFza09uZS5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImluc2VydFRhc2tPbmUudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7QUFBQSwyQ0FBcUM7QUFFckMsa0JBQWUsSUFBQSxZQUFHLEVBQUE7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Q0FzQmpCLENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgeyBncWwgfSBmcm9tICdAYXBvbGxvL2NsaWVudCc7XG5cbmV4cG9ydCBkZWZhdWx0IGdxbGBcbiAgbXV0YXRpb24gSW5zZXJ0VGFza09uZSgkdGFzazogVGFza19pbnNlcnRfaW5wdXQhKSB7XG4gICAgaW5zZXJ0X1Rhc2tfb25lKG9iamVjdDogJHRhc2spIHtcbiAgICAgIGNvbXBsZXRlZERhdGVcbiAgICAgIGNyZWF0ZWREYXRlXG4gICAgICBkdXJhdGlvblxuICAgICAgZXZlbnRJZFxuICAgICAgaGFyZERlYWRsaW5lXG4gICAgICBpZFxuICAgICAgaW1wb3J0YW50XG4gICAgICBub3Rlc1xuICAgICAgb3JkZXJcbiAgICAgIHBhcmVudElkXG4gICAgICBwcmlvcml0eVxuICAgICAgc29mdERlYWRsaW5lXG4gICAgICBzdGF0dXNcbiAgICAgIHN5bmNEYXRhXG4gICAgICB0eXBlXG4gICAgICB1cGRhdGVkQXRcbiAgICAgIHVzZXJJZFxuICAgIH1cbiAgfVxuYDtcbiJdfQ==