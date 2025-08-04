"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const client_1 = require("@apollo/client");
exports.default = (0, client_1.gql) `
  mutation RemoveCategoriesForEvent($eventId: String!) {
    delete_Category_Event(where: { eventId: { _eq: $eventId } }) {
      affected_rows
      returning {
        id
        categoryId
        createdDate
        deleted
        eventId
        updatedAt
        userId
      }
    }
  }
`;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoicmVtb3ZlQ2F0ZWdvcmllc0ZvckV2ZW50LmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsicmVtb3ZlQ2F0ZWdvcmllc0ZvckV2ZW50LnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiI7O0FBQUEsMkNBQXFDO0FBRXJDLGtCQUFlLElBQUEsWUFBRyxFQUFBOzs7Ozs7Ozs7Ozs7Ozs7Q0FlakIsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7IGdxbCB9IGZyb20gJ0BhcG9sbG8vY2xpZW50JztcblxuZXhwb3J0IGRlZmF1bHQgZ3FsYFxuICBtdXRhdGlvbiBSZW1vdmVDYXRlZ29yaWVzRm9yRXZlbnQoJGV2ZW50SWQ6IFN0cmluZyEpIHtcbiAgICBkZWxldGVfQ2F0ZWdvcnlfRXZlbnQod2hlcmU6IHsgZXZlbnRJZDogeyBfZXE6ICRldmVudElkIH0gfSkge1xuICAgICAgYWZmZWN0ZWRfcm93c1xuICAgICAgcmV0dXJuaW5nIHtcbiAgICAgICAgaWRcbiAgICAgICAgY2F0ZWdvcnlJZFxuICAgICAgICBjcmVhdGVkRGF0ZVxuICAgICAgICBkZWxldGVkXG4gICAgICAgIGV2ZW50SWRcbiAgICAgICAgdXBkYXRlZEF0XG4gICAgICAgIHVzZXJJZFxuICAgICAgfVxuICAgIH1cbiAgfVxuYDtcbiJdfQ==