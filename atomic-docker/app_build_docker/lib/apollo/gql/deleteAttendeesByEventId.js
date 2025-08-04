"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const client_1 = require("@apollo/client");
exports.default = (0, client_1.gql) `
  mutation DeleteAttendees($eventId: String!) {
    delete_Attendee(where: { eventId: { _eq: $eventId } }) {
      affected_rows
    }
  }
`;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiZGVsZXRlQXR0ZW5kZWVzQnlFdmVudElkLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsiZGVsZXRlQXR0ZW5kZWVzQnlFdmVudElkLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiI7O0FBQUEsMkNBQXFDO0FBRXJDLGtCQUFlLElBQUEsWUFBRyxFQUFBOzs7Ozs7Q0FNakIsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7IGdxbCB9IGZyb20gJ0BhcG9sbG8vY2xpZW50JztcblxuZXhwb3J0IGRlZmF1bHQgZ3FsYFxuICBtdXRhdGlvbiBEZWxldGVBdHRlbmRlZXMoJGV2ZW50SWQ6IFN0cmluZyEpIHtcbiAgICBkZWxldGVfQXR0ZW5kZWUod2hlcmU6IHsgZXZlbnRJZDogeyBfZXE6ICRldmVudElkIH0gfSkge1xuICAgICAgYWZmZWN0ZWRfcm93c1xuICAgIH1cbiAgfVxuYDtcbiJdfQ==