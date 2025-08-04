"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const client_1 = require("@apollo/client");
exports.default = (0, client_1.gql) `
  query GetCalendarWithResource($userId: uuid!, $resource: String!) {
    Calendar(
      where: {
        userId: { _eq: $userId }
        resource: { _eq: $resource }
        accessLevel: { _in: ["writer", "owner"] }
      }
    ) {
      id
      title
      colorId
      account
      accessLevel
      modifiable
      resource
      defaultReminders
      globalPrimary
      deleted
      createdDate
      updatedAt
      userId
      foregroundColor
      backgroundColor
      primary
      pageToken
      syncToken
    }
  }
`;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiZ2V0Q2FsZW5kYXJXaXRoUmVzb3VyY2UuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJnZXRDYWxlbmRhcldpdGhSZXNvdXJjZS50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOztBQUFBLDJDQUFxQztBQUVyQyxrQkFBZSxJQUFBLFlBQUcsRUFBQTs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Q0E2QmpCLENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgeyBncWwgfSBmcm9tICdAYXBvbGxvL2NsaWVudCc7XG5cbmV4cG9ydCBkZWZhdWx0IGdxbGBcbiAgcXVlcnkgR2V0Q2FsZW5kYXJXaXRoUmVzb3VyY2UoJHVzZXJJZDogdXVpZCEsICRyZXNvdXJjZTogU3RyaW5nISkge1xuICAgIENhbGVuZGFyKFxuICAgICAgd2hlcmU6IHtcbiAgICAgICAgdXNlcklkOiB7IF9lcTogJHVzZXJJZCB9XG4gICAgICAgIHJlc291cmNlOiB7IF9lcTogJHJlc291cmNlIH1cbiAgICAgICAgYWNjZXNzTGV2ZWw6IHsgX2luOiBbXCJ3cml0ZXJcIiwgXCJvd25lclwiXSB9XG4gICAgICB9XG4gICAgKSB7XG4gICAgICBpZFxuICAgICAgdGl0bGVcbiAgICAgIGNvbG9ySWRcbiAgICAgIGFjY291bnRcbiAgICAgIGFjY2Vzc0xldmVsXG4gICAgICBtb2RpZmlhYmxlXG4gICAgICByZXNvdXJjZVxuICAgICAgZGVmYXVsdFJlbWluZGVyc1xuICAgICAgZ2xvYmFsUHJpbWFyeVxuICAgICAgZGVsZXRlZFxuICAgICAgY3JlYXRlZERhdGVcbiAgICAgIHVwZGF0ZWRBdFxuICAgICAgdXNlcklkXG4gICAgICBmb3JlZ3JvdW5kQ29sb3JcbiAgICAgIGJhY2tncm91bmRDb2xvclxuICAgICAgcHJpbWFyeVxuICAgICAgcGFnZVRva2VuXG4gICAgICBzeW5jVG9rZW5cbiAgICB9XG4gIH1cbmA7XG4iXX0=