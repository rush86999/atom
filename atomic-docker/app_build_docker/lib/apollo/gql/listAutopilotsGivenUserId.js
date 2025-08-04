"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const client_1 = require("@apollo/client");
exports.default = (0, client_1.gql) `
  query ListAutopilotsGivenUserId($userId: uuid!) {
    Autopilot(where: { userId: { _eq: $userId } }) {
      createdDate
      id
      payload
      scheduleAt
      timezone
      updatedAt
      userId
    }
  }
`;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoibGlzdEF1dG9waWxvdHNHaXZlblVzZXJJZC5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImxpc3RBdXRvcGlsb3RzR2l2ZW5Vc2VySWQudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7QUFBQSwyQ0FBcUM7QUFFckMsa0JBQWUsSUFBQSxZQUFHLEVBQUE7Ozs7Ozs7Ozs7OztDQVlqQixDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IHsgZ3FsIH0gZnJvbSAnQGFwb2xsby9jbGllbnQnO1xuXG5leHBvcnQgZGVmYXVsdCBncWxgXG4gIHF1ZXJ5IExpc3RBdXRvcGlsb3RzR2l2ZW5Vc2VySWQoJHVzZXJJZDogdXVpZCEpIHtcbiAgICBBdXRvcGlsb3Qod2hlcmU6IHsgdXNlcklkOiB7IF9lcTogJHVzZXJJZCB9IH0pIHtcbiAgICAgIGNyZWF0ZWREYXRlXG4gICAgICBpZFxuICAgICAgcGF5bG9hZFxuICAgICAgc2NoZWR1bGVBdFxuICAgICAgdGltZXpvbmVcbiAgICAgIHVwZGF0ZWRBdFxuICAgICAgdXNlcklkXG4gICAgfVxuICB9XG5gO1xuIl19