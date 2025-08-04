"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const client_1 = require("@apollo/client");
exports.default = (0, client_1.gql) `
  mutation DeleteAutopilotsByUserId($userId: uuid!) {
    delete_Autopilot(where: { userId: { _eq: $userId } }) {
      affected_rows
      returning {
        createdDate
        id
        payload
        scheduleAt
        timezone
        updatedAt
        userId
      }
    }
  }
`;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiZGVsZXRlQXV0b3BpbG90c0J5VXNlcklkLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsiZGVsZXRlQXV0b3BpbG90c0J5VXNlcklkLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiI7O0FBQUEsMkNBQXFDO0FBRXJDLGtCQUFlLElBQUEsWUFBRyxFQUFBOzs7Ozs7Ozs7Ozs7Ozs7Q0FlakIsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7IGdxbCB9IGZyb20gJ0BhcG9sbG8vY2xpZW50JztcblxuZXhwb3J0IGRlZmF1bHQgZ3FsYFxuICBtdXRhdGlvbiBEZWxldGVBdXRvcGlsb3RzQnlVc2VySWQoJHVzZXJJZDogdXVpZCEpIHtcbiAgICBkZWxldGVfQXV0b3BpbG90KHdoZXJlOiB7IHVzZXJJZDogeyBfZXE6ICR1c2VySWQgfSB9KSB7XG4gICAgICBhZmZlY3RlZF9yb3dzXG4gICAgICByZXR1cm5pbmcge1xuICAgICAgICBjcmVhdGVkRGF0ZVxuICAgICAgICBpZFxuICAgICAgICBwYXlsb2FkXG4gICAgICAgIHNjaGVkdWxlQXRcbiAgICAgICAgdGltZXpvbmVcbiAgICAgICAgdXBkYXRlZEF0XG4gICAgICAgIHVzZXJJZFxuICAgICAgfVxuICAgIH1cbiAgfVxuYDtcbiJdfQ==