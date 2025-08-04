"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const client_1 = require("@apollo/client");
exports.default = (0, client_1.gql) `
  mutation UpsertAutopilotMany($autopilots: [Autopilot_insert_input!]!) {
    insert_Autopilot(
      objects: $autopilots
      on_conflict: {
        constraint: Autopilot_pkey
        update_columns: [payload, scheduleAt, timezone, updatedAt]
      }
    ) {
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
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoidXBzZXJ0QXV0b3BpbG90TWFueS5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbInVwc2VydEF1dG9waWxvdE1hbnkudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7QUFBQSwyQ0FBcUM7QUFFckMsa0JBQWUsSUFBQSxZQUFHLEVBQUE7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7OztDQXFCakIsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7IGdxbCB9IGZyb20gJ0BhcG9sbG8vY2xpZW50JztcblxuZXhwb3J0IGRlZmF1bHQgZ3FsYFxuICBtdXRhdGlvbiBVcHNlcnRBdXRvcGlsb3RNYW55KCRhdXRvcGlsb3RzOiBbQXV0b3BpbG90X2luc2VydF9pbnB1dCFdISkge1xuICAgIGluc2VydF9BdXRvcGlsb3QoXG4gICAgICBvYmplY3RzOiAkYXV0b3BpbG90c1xuICAgICAgb25fY29uZmxpY3Q6IHtcbiAgICAgICAgY29uc3RyYWludDogQXV0b3BpbG90X3BrZXlcbiAgICAgICAgdXBkYXRlX2NvbHVtbnM6IFtwYXlsb2FkLCBzY2hlZHVsZUF0LCB0aW1lem9uZSwgdXBkYXRlZEF0XVxuICAgICAgfVxuICAgICkge1xuICAgICAgYWZmZWN0ZWRfcm93c1xuICAgICAgcmV0dXJuaW5nIHtcbiAgICAgICAgY3JlYXRlZERhdGVcbiAgICAgICAgaWRcbiAgICAgICAgcGF5bG9hZFxuICAgICAgICBzY2hlZHVsZUF0XG4gICAgICAgIHRpbWV6b25lXG4gICAgICAgIHVwZGF0ZWRBdFxuICAgICAgICB1c2VySWRcbiAgICAgIH1cbiAgICB9XG4gIH1cbmA7XG4iXX0=