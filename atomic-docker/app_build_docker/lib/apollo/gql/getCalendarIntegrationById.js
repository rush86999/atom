"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const client_1 = require("@apollo/client");
exports.default = (0, client_1.gql) `
  query GetCalendarIntegrationById($id: uuid!) {
    Calendar_Integration_by_pk(id: $id) {
      appAccountId
      appEmail
      appId
      colors
      contactEmail
      contactName
      createdDate
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
      clientType
    }
  }
`;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiZ2V0Q2FsZW5kYXJJbnRlZ3JhdGlvbkJ5SWQuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJnZXRDYWxlbmRhckludGVncmF0aW9uQnlJZC50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOztBQUFBLDJDQUFxQztBQUVyQyxrQkFBZSxJQUFBLFlBQUcsRUFBQTs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7OztDQTRCakIsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7IGdxbCB9IGZyb20gJ0BhcG9sbG8vY2xpZW50JztcblxuZXhwb3J0IGRlZmF1bHQgZ3FsYFxuICBxdWVyeSBHZXRDYWxlbmRhckludGVncmF0aW9uQnlJZCgkaWQ6IHV1aWQhKSB7XG4gICAgQ2FsZW5kYXJfSW50ZWdyYXRpb25fYnlfcGsoaWQ6ICRpZCkge1xuICAgICAgYXBwQWNjb3VudElkXG4gICAgICBhcHBFbWFpbFxuICAgICAgYXBwSWRcbiAgICAgIGNvbG9yc1xuICAgICAgY29udGFjdEVtYWlsXG4gICAgICBjb250YWN0TmFtZVxuICAgICAgY3JlYXRlZERhdGVcbiAgICAgIGRlbGV0ZWRcbiAgICAgIGVuYWJsZWRcbiAgICAgIGV4cGlyZXNBdFxuICAgICAgaWRcbiAgICAgIG5hbWVcbiAgICAgIHBhZ2VUb2tlblxuICAgICAgcGFzc3dvcmRcbiAgICAgIHJlZnJlc2hUb2tlblxuICAgICAgcmVzb3VyY2VcbiAgICAgIHN5bmNFbmFibGVkXG4gICAgICBzeW5jVG9rZW5cbiAgICAgIHRva2VuXG4gICAgICB1cGRhdGVkQXRcbiAgICAgIHVzZXJJZFxuICAgICAgdXNlcm5hbWVcbiAgICAgIGNsaWVudFR5cGVcbiAgICB9XG4gIH1cbmA7XG4iXX0=