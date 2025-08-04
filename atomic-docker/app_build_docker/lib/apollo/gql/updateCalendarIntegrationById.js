"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const client_1 = require("@apollo/client");
exports.default = (0, client_1.gql) `
  mutation UpdateCalendarIntegrationById(
    $id: uuid!
    $appEmail: String
    $appAccountId: String
    $appId: String
    $contactEmail: String
    $colors: jsonb
    $contactName: String
    $deleted: Boolean
    $enabled: Boolean
    $expiresAt: timestamptz
    $name: String
    $pageToken: String
    $password: String
    $refreshToken: String
    $resource: String
    $syncEnabled: Boolean
    $syncToken: String
    $token: String
    $updatedAt: timestamptz
    $userId: uuid
    $username: String
  ) {
    update_Calendar_Integration_by_pk(
      _set: {
        appEmail: $appEmail
        appAccountId: $appAccountId
        appId: $appId
        contactEmail: $contactEmail
        colors: $colors
        contactName: $contactName
        deleted: $deleted
        enabled: $enabled
        expiresAt: $expiresAt
        name: $name
        pageToken: $pageToken
        password: $password
        refreshToken: $refreshToken
        resource: $resource
        syncEnabled: $syncEnabled
        syncToken: $syncToken
        token: $token
        updatedAt: $updatedAt
        userId: $userId
        username: $username
      }
      pk_columns: { id: $id }
    ) {
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
      syncEnabled
      resource
      token
      syncToken
      updatedAt
      userId
      username
      clientType
    }
  }
`;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoidXBkYXRlQ2FsZW5kYXJJbnRlZ3JhdGlvbkJ5SWQuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJ1cGRhdGVDYWxlbmRhckludGVncmF0aW9uQnlJZC50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOztBQUFBLDJDQUFxQztBQUVyQyxrQkFBZSxJQUFBLFlBQUcsRUFBQTs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Q0EwRWpCLENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgeyBncWwgfSBmcm9tICdAYXBvbGxvL2NsaWVudCc7XG5cbmV4cG9ydCBkZWZhdWx0IGdxbGBcbiAgbXV0YXRpb24gVXBkYXRlQ2FsZW5kYXJJbnRlZ3JhdGlvbkJ5SWQoXG4gICAgJGlkOiB1dWlkIVxuICAgICRhcHBFbWFpbDogU3RyaW5nXG4gICAgJGFwcEFjY291bnRJZDogU3RyaW5nXG4gICAgJGFwcElkOiBTdHJpbmdcbiAgICAkY29udGFjdEVtYWlsOiBTdHJpbmdcbiAgICAkY29sb3JzOiBqc29uYlxuICAgICRjb250YWN0TmFtZTogU3RyaW5nXG4gICAgJGRlbGV0ZWQ6IEJvb2xlYW5cbiAgICAkZW5hYmxlZDogQm9vbGVhblxuICAgICRleHBpcmVzQXQ6IHRpbWVzdGFtcHR6XG4gICAgJG5hbWU6IFN0cmluZ1xuICAgICRwYWdlVG9rZW46IFN0cmluZ1xuICAgICRwYXNzd29yZDogU3RyaW5nXG4gICAgJHJlZnJlc2hUb2tlbjogU3RyaW5nXG4gICAgJHJlc291cmNlOiBTdHJpbmdcbiAgICAkc3luY0VuYWJsZWQ6IEJvb2xlYW5cbiAgICAkc3luY1Rva2VuOiBTdHJpbmdcbiAgICAkdG9rZW46IFN0cmluZ1xuICAgICR1cGRhdGVkQXQ6IHRpbWVzdGFtcHR6XG4gICAgJHVzZXJJZDogdXVpZFxuICAgICR1c2VybmFtZTogU3RyaW5nXG4gICkge1xuICAgIHVwZGF0ZV9DYWxlbmRhcl9JbnRlZ3JhdGlvbl9ieV9wayhcbiAgICAgIF9zZXQ6IHtcbiAgICAgICAgYXBwRW1haWw6ICRhcHBFbWFpbFxuICAgICAgICBhcHBBY2NvdW50SWQ6ICRhcHBBY2NvdW50SWRcbiAgICAgICAgYXBwSWQ6ICRhcHBJZFxuICAgICAgICBjb250YWN0RW1haWw6ICRjb250YWN0RW1haWxcbiAgICAgICAgY29sb3JzOiAkY29sb3JzXG4gICAgICAgIGNvbnRhY3ROYW1lOiAkY29udGFjdE5hbWVcbiAgICAgICAgZGVsZXRlZDogJGRlbGV0ZWRcbiAgICAgICAgZW5hYmxlZDogJGVuYWJsZWRcbiAgICAgICAgZXhwaXJlc0F0OiAkZXhwaXJlc0F0XG4gICAgICAgIG5hbWU6ICRuYW1lXG4gICAgICAgIHBhZ2VUb2tlbjogJHBhZ2VUb2tlblxuICAgICAgICBwYXNzd29yZDogJHBhc3N3b3JkXG4gICAgICAgIHJlZnJlc2hUb2tlbjogJHJlZnJlc2hUb2tlblxuICAgICAgICByZXNvdXJjZTogJHJlc291cmNlXG4gICAgICAgIHN5bmNFbmFibGVkOiAkc3luY0VuYWJsZWRcbiAgICAgICAgc3luY1Rva2VuOiAkc3luY1Rva2VuXG4gICAgICAgIHRva2VuOiAkdG9rZW5cbiAgICAgICAgdXBkYXRlZEF0OiAkdXBkYXRlZEF0XG4gICAgICAgIHVzZXJJZDogJHVzZXJJZFxuICAgICAgICB1c2VybmFtZTogJHVzZXJuYW1lXG4gICAgICB9XG4gICAgICBwa19jb2x1bW5zOiB7IGlkOiAkaWQgfVxuICAgICkge1xuICAgICAgYXBwQWNjb3VudElkXG4gICAgICBhcHBFbWFpbFxuICAgICAgYXBwSWRcbiAgICAgIGNvbG9yc1xuICAgICAgY29udGFjdEVtYWlsXG4gICAgICBjb250YWN0TmFtZVxuICAgICAgY3JlYXRlZERhdGVcbiAgICAgIGRlbGV0ZWRcbiAgICAgIGVuYWJsZWRcbiAgICAgIGV4cGlyZXNBdFxuICAgICAgaWRcbiAgICAgIG5hbWVcbiAgICAgIHBhZ2VUb2tlblxuICAgICAgcGFzc3dvcmRcbiAgICAgIHJlZnJlc2hUb2tlblxuICAgICAgc3luY0VuYWJsZWRcbiAgICAgIHJlc291cmNlXG4gICAgICB0b2tlblxuICAgICAgc3luY1Rva2VuXG4gICAgICB1cGRhdGVkQXRcbiAgICAgIHVzZXJJZFxuICAgICAgdXNlcm5hbWVcbiAgICAgIGNsaWVudFR5cGVcbiAgICB9XG4gIH1cbmA7XG4iXX0=