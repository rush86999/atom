"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const client_1 = require("@apollo/client");
exports.default = (0, client_1.gql) `
  query GetConferenceById($id: String!) {
    Conference_by_pk(id: $id) {
      id
      userId
      requestId
      type
      status
      calendarId
      iconUri
      name
      notes
      entryPoints
      parameters
      app
      key
      hangoutLink
      joinUrl
      startUrl
      zoomPrivateMeeting
      deleted
      createdDate
      updatedAt
      isHost
    }
  }
`;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiZ2V0Q29uZmVyZW5jZUJ5SWQuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJnZXRDb25mZXJlbmNlQnlJZC50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOztBQUFBLDJDQUFxQztBQUVyQyxrQkFBZSxJQUFBLFlBQUcsRUFBQTs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Q0EwQmpCLENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgeyBncWwgfSBmcm9tICdAYXBvbGxvL2NsaWVudCc7XG5cbmV4cG9ydCBkZWZhdWx0IGdxbGBcbiAgcXVlcnkgR2V0Q29uZmVyZW5jZUJ5SWQoJGlkOiBTdHJpbmchKSB7XG4gICAgQ29uZmVyZW5jZV9ieV9wayhpZDogJGlkKSB7XG4gICAgICBpZFxuICAgICAgdXNlcklkXG4gICAgICByZXF1ZXN0SWRcbiAgICAgIHR5cGVcbiAgICAgIHN0YXR1c1xuICAgICAgY2FsZW5kYXJJZFxuICAgICAgaWNvblVyaVxuICAgICAgbmFtZVxuICAgICAgbm90ZXNcbiAgICAgIGVudHJ5UG9pbnRzXG4gICAgICBwYXJhbWV0ZXJzXG4gICAgICBhcHBcbiAgICAgIGtleVxuICAgICAgaGFuZ291dExpbmtcbiAgICAgIGpvaW5VcmxcbiAgICAgIHN0YXJ0VXJsXG4gICAgICB6b29tUHJpdmF0ZU1lZXRpbmdcbiAgICAgIGRlbGV0ZWRcbiAgICAgIGNyZWF0ZWREYXRlXG4gICAgICB1cGRhdGVkQXRcbiAgICAgIGlzSG9zdFxuICAgIH1cbiAgfVxuYDtcbiJdfQ==