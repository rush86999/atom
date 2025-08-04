"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const client_1 = require("@apollo/client");
exports.default = (0, client_1.gql) `
  query ListCalendarIntegrations($userId: uuid!) {
    Calendar_Integration(where: { userId: { _eq: $userId } }) {
      appAccountId
      appEmail
      appId
      colors
      contactEmail
      createdDate
      contactName
      deleted
      enabled
      expiresAt
      id
      name
      pageToken
      password
      refreshToken
      resource
      syncEnabled
      syncToken
      token
      updatedAt
      userId
      username
    }
  }
`;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoibGlzdENhbGVuZGFySW50ZWdyYXRpb25zLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsibGlzdENhbGVuZGFySW50ZWdyYXRpb25zLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiI7O0FBQUEsMkNBQXFDO0FBRXJDLGtCQUFlLElBQUEsWUFBRyxFQUFBOzs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Q0EyQmpCLENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgeyBncWwgfSBmcm9tICdAYXBvbGxvL2NsaWVudCc7XG5cbmV4cG9ydCBkZWZhdWx0IGdxbGBcbiAgcXVlcnkgTGlzdENhbGVuZGFySW50ZWdyYXRpb25zKCR1c2VySWQ6IHV1aWQhKSB7XG4gICAgQ2FsZW5kYXJfSW50ZWdyYXRpb24od2hlcmU6IHsgdXNlcklkOiB7IF9lcTogJHVzZXJJZCB9IH0pIHtcbiAgICAgIGFwcEFjY291bnRJZFxuICAgICAgYXBwRW1haWxcbiAgICAgIGFwcElkXG4gICAgICBjb2xvcnNcbiAgICAgIGNvbnRhY3RFbWFpbFxuICAgICAgY3JlYXRlZERhdGVcbiAgICAgIGNvbnRhY3ROYW1lXG4gICAgICBkZWxldGVkXG4gICAgICBlbmFibGVkXG4gICAgICBleHBpcmVzQXRcbiAgICAgIGlkXG4gICAgICBuYW1lXG4gICAgICBwYWdlVG9rZW5cbiAgICAgIHBhc3N3b3JkXG4gICAgICByZWZyZXNoVG9rZW5cbiAgICAgIHJlc291cmNlXG4gICAgICBzeW5jRW5hYmxlZFxuICAgICAgc3luY1Rva2VuXG4gICAgICB0b2tlblxuICAgICAgdXBkYXRlZEF0XG4gICAgICB1c2VySWRcbiAgICAgIHVzZXJuYW1lXG4gICAgfVxuICB9XG5gO1xuIl19