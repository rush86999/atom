"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const client_1 = require("@apollo/client");
exports.default = (0, client_1.gql) `
  query GetCalendarIntegrationByResource(
    $userId: uuid!
    $resource: String!
    $name: String!
  ) {
    Calendar_Integration(
      where: {
        userId: { _eq: $userId }
        resource: { _eq: $resource }
        name: { _eq: $name }
      }
    ) {
      id
      token
      refreshToken
      resource
      name
      enabled
      syncEnabled
      deleted
      expiresAt
      pageToken
      syncToken
      appId
      appEmail
      appAccountId
      contactName
      contactEmail
      createdDate
      updatedAt
      userId
      clientType
    }
  }
`;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiZ2V0Q2FsZW5kYXJJbnRlZ3JhdGlvbkJ5UmVzb3VyY2VBbmROYW1lLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsiZ2V0Q2FsZW5kYXJJbnRlZ3JhdGlvbkJ5UmVzb3VyY2VBbmROYW1lLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiI7O0FBQUEsMkNBQXFDO0FBRXJDLGtCQUFlLElBQUEsWUFBRyxFQUFBOzs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7OztDQW1DakIsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7IGdxbCB9IGZyb20gJ0BhcG9sbG8vY2xpZW50JztcblxuZXhwb3J0IGRlZmF1bHQgZ3FsYFxuICBxdWVyeSBHZXRDYWxlbmRhckludGVncmF0aW9uQnlSZXNvdXJjZShcbiAgICAkdXNlcklkOiB1dWlkIVxuICAgICRyZXNvdXJjZTogU3RyaW5nIVxuICAgICRuYW1lOiBTdHJpbmchXG4gICkge1xuICAgIENhbGVuZGFyX0ludGVncmF0aW9uKFxuICAgICAgd2hlcmU6IHtcbiAgICAgICAgdXNlcklkOiB7IF9lcTogJHVzZXJJZCB9XG4gICAgICAgIHJlc291cmNlOiB7IF9lcTogJHJlc291cmNlIH1cbiAgICAgICAgbmFtZTogeyBfZXE6ICRuYW1lIH1cbiAgICAgIH1cbiAgICApIHtcbiAgICAgIGlkXG4gICAgICB0b2tlblxuICAgICAgcmVmcmVzaFRva2VuXG4gICAgICByZXNvdXJjZVxuICAgICAgbmFtZVxuICAgICAgZW5hYmxlZFxuICAgICAgc3luY0VuYWJsZWRcbiAgICAgIGRlbGV0ZWRcbiAgICAgIGV4cGlyZXNBdFxuICAgICAgcGFnZVRva2VuXG4gICAgICBzeW5jVG9rZW5cbiAgICAgIGFwcElkXG4gICAgICBhcHBFbWFpbFxuICAgICAgYXBwQWNjb3VudElkXG4gICAgICBjb250YWN0TmFtZVxuICAgICAgY29udGFjdEVtYWlsXG4gICAgICBjcmVhdGVkRGF0ZVxuICAgICAgdXBkYXRlZEF0XG4gICAgICB1c2VySWRcbiAgICAgIGNsaWVudFR5cGVcbiAgICB9XG4gIH1cbmA7XG4iXX0=