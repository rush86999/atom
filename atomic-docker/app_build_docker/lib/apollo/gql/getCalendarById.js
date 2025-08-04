"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const client_1 = require("@apollo/client");
exports.default = (0, client_1.gql) `
  query GetCalendarById($id: String!) {
    calendarById(id: $id) {
      # Renamed from Calendar_by_pk
      id
      title
      colorId # Assuming field names remain similar or are camelCased by PostGraphile
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
      pageToken
      syncToken
      # Ensure all field names are camelCase if originally snake_case in DB
    }
  }
`;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiZ2V0Q2FsZW5kYXJCeUlkLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsiZ2V0Q2FsZW5kYXJCeUlkLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiI7O0FBQUEsMkNBQXFDO0FBRXJDLGtCQUFlLElBQUEsWUFBRyxFQUFBOzs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Q0F3QmpCLENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgeyBncWwgfSBmcm9tICdAYXBvbGxvL2NsaWVudCc7XG5cbmV4cG9ydCBkZWZhdWx0IGdxbGBcbiAgcXVlcnkgR2V0Q2FsZW5kYXJCeUlkKCRpZDogU3RyaW5nISkge1xuICAgIGNhbGVuZGFyQnlJZChpZDogJGlkKSB7XG4gICAgICAjIFJlbmFtZWQgZnJvbSBDYWxlbmRhcl9ieV9wa1xuICAgICAgaWRcbiAgICAgIHRpdGxlXG4gICAgICBjb2xvcklkICMgQXNzdW1pbmcgZmllbGQgbmFtZXMgcmVtYWluIHNpbWlsYXIgb3IgYXJlIGNhbWVsQ2FzZWQgYnkgUG9zdEdyYXBoaWxlXG4gICAgICBhY2NvdW50XG4gICAgICBhY2Nlc3NMZXZlbFxuICAgICAgbW9kaWZpYWJsZVxuICAgICAgcmVzb3VyY2VcbiAgICAgIGRlZmF1bHRSZW1pbmRlcnNcbiAgICAgIGdsb2JhbFByaW1hcnlcbiAgICAgIGRlbGV0ZWRcbiAgICAgIGNyZWF0ZWREYXRlXG4gICAgICB1cGRhdGVkQXRcbiAgICAgIHVzZXJJZFxuICAgICAgZm9yZWdyb3VuZENvbG9yXG4gICAgICBiYWNrZ3JvdW5kQ29sb3JcbiAgICAgIHBhZ2VUb2tlblxuICAgICAgc3luY1Rva2VuXG4gICAgICAjIEVuc3VyZSBhbGwgZmllbGQgbmFtZXMgYXJlIGNhbWVsQ2FzZSBpZiBvcmlnaW5hbGx5IHNuYWtlX2Nhc2UgaW4gREJcbiAgICB9XG4gIH1cbmA7XG4iXX0=