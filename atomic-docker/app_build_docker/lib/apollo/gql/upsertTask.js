"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const client_1 = require("@apollo/client");
exports.default = (0, client_1.gql) `
  mutation UpsertTask($tasks: [Task_insert_input!]!) {
    insert_Task(
      objects: $tasks
      on_conflict: {
        constraint: Task_pkey
        update_columns: [
          completedDate
          duration
          eventId
          hardDeadline
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
        ]
      }
    ) {
      affected_rows
      returning {
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
  }
`;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoidXBzZXJ0VGFzay5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbInVwc2VydFRhc2sudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7QUFBQSwyQ0FBcUM7QUFFckMsa0JBQWUsSUFBQSxZQUFHLEVBQUE7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Q0E4Q2pCLENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgeyBncWwgfSBmcm9tICdAYXBvbGxvL2NsaWVudCc7XG5cbmV4cG9ydCBkZWZhdWx0IGdxbGBcbiAgbXV0YXRpb24gVXBzZXJ0VGFzaygkdGFza3M6IFtUYXNrX2luc2VydF9pbnB1dCFdISkge1xuICAgIGluc2VydF9UYXNrKFxuICAgICAgb2JqZWN0czogJHRhc2tzXG4gICAgICBvbl9jb25mbGljdDoge1xuICAgICAgICBjb25zdHJhaW50OiBUYXNrX3BrZXlcbiAgICAgICAgdXBkYXRlX2NvbHVtbnM6IFtcbiAgICAgICAgICBjb21wbGV0ZWREYXRlXG4gICAgICAgICAgZHVyYXRpb25cbiAgICAgICAgICBldmVudElkXG4gICAgICAgICAgaGFyZERlYWRsaW5lXG4gICAgICAgICAgaW1wb3J0YW50XG4gICAgICAgICAgbm90ZXNcbiAgICAgICAgICBvcmRlclxuICAgICAgICAgIHBhcmVudElkXG4gICAgICAgICAgcHJpb3JpdHlcbiAgICAgICAgICBzb2Z0RGVhZGxpbmVcbiAgICAgICAgICBzdGF0dXNcbiAgICAgICAgICBzeW5jRGF0YVxuICAgICAgICAgIHR5cGVcbiAgICAgICAgICB1cGRhdGVkQXRcbiAgICAgICAgXVxuICAgICAgfVxuICAgICkge1xuICAgICAgYWZmZWN0ZWRfcm93c1xuICAgICAgcmV0dXJuaW5nIHtcbiAgICAgICAgY29tcGxldGVkRGF0ZVxuICAgICAgICBjcmVhdGVkRGF0ZVxuICAgICAgICBkdXJhdGlvblxuICAgICAgICBldmVudElkXG4gICAgICAgIGhhcmREZWFkbGluZVxuICAgICAgICBpZFxuICAgICAgICBpbXBvcnRhbnRcbiAgICAgICAgbm90ZXNcbiAgICAgICAgb3JkZXJcbiAgICAgICAgcGFyZW50SWRcbiAgICAgICAgcHJpb3JpdHlcbiAgICAgICAgc29mdERlYWRsaW5lXG4gICAgICAgIHN0YXR1c1xuICAgICAgICBzeW5jRGF0YVxuICAgICAgICB0eXBlXG4gICAgICAgIHVwZGF0ZWRBdFxuICAgICAgICB1c2VySWRcbiAgICAgIH1cbiAgICB9XG4gIH1cbmA7XG4iXX0=