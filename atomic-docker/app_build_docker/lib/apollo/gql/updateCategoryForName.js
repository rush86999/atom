"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const client_1 = require("@apollo/client");
exports.default = (0, client_1.gql) `
  mutation UpdateCategoryForName(
    $id: uuid!
    $name: String!
    $updatedAt: timestamptz
  ) {
    update_Category_by_pk(
      pk_columns: { id: $id }
      _set: { name: $name, updatedAt: $updatedAt }
    ) {
      id
      name
      deleted
      createdDate
      updatedAt
      userId
      copyAvailability
      copyTimeBlocking
      copyTimePreference
      copyReminders
      copyPriorityLevel
      copyModifiable
      defaultAvailability
      defaultTimeBlocking
      defaultTimePreference
      defaultReminders
      defaultPriorityLevel
      defaultModifiable
      copyIsBreak
      defaultIsBreak
      color
      copyIsMeeting
      copyIsExternalMeeting
      defaultIsMeeting
      defaultIsExternalMeeting
      defaultMeetingModifiable
      defaultExternalMeetingModifiable
    }
  }
`;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoidXBkYXRlQ2F0ZWdvcnlGb3JOYW1lLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsidXBkYXRlQ2F0ZWdvcnlGb3JOYW1lLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiI7O0FBQUEsMkNBQXFDO0FBRXJDLGtCQUFlLElBQUEsWUFBRyxFQUFBOzs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Q0F1Q2pCLENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgeyBncWwgfSBmcm9tICdAYXBvbGxvL2NsaWVudCc7XG5cbmV4cG9ydCBkZWZhdWx0IGdxbGBcbiAgbXV0YXRpb24gVXBkYXRlQ2F0ZWdvcnlGb3JOYW1lKFxuICAgICRpZDogdXVpZCFcbiAgICAkbmFtZTogU3RyaW5nIVxuICAgICR1cGRhdGVkQXQ6IHRpbWVzdGFtcHR6XG4gICkge1xuICAgIHVwZGF0ZV9DYXRlZ29yeV9ieV9wayhcbiAgICAgIHBrX2NvbHVtbnM6IHsgaWQ6ICRpZCB9XG4gICAgICBfc2V0OiB7IG5hbWU6ICRuYW1lLCB1cGRhdGVkQXQ6ICR1cGRhdGVkQXQgfVxuICAgICkge1xuICAgICAgaWRcbiAgICAgIG5hbWVcbiAgICAgIGRlbGV0ZWRcbiAgICAgIGNyZWF0ZWREYXRlXG4gICAgICB1cGRhdGVkQXRcbiAgICAgIHVzZXJJZFxuICAgICAgY29weUF2YWlsYWJpbGl0eVxuICAgICAgY29weVRpbWVCbG9ja2luZ1xuICAgICAgY29weVRpbWVQcmVmZXJlbmNlXG4gICAgICBjb3B5UmVtaW5kZXJzXG4gICAgICBjb3B5UHJpb3JpdHlMZXZlbFxuICAgICAgY29weU1vZGlmaWFibGVcbiAgICAgIGRlZmF1bHRBdmFpbGFiaWxpdHlcbiAgICAgIGRlZmF1bHRUaW1lQmxvY2tpbmdcbiAgICAgIGRlZmF1bHRUaW1lUHJlZmVyZW5jZVxuICAgICAgZGVmYXVsdFJlbWluZGVyc1xuICAgICAgZGVmYXVsdFByaW9yaXR5TGV2ZWxcbiAgICAgIGRlZmF1bHRNb2RpZmlhYmxlXG4gICAgICBjb3B5SXNCcmVha1xuICAgICAgZGVmYXVsdElzQnJlYWtcbiAgICAgIGNvbG9yXG4gICAgICBjb3B5SXNNZWV0aW5nXG4gICAgICBjb3B5SXNFeHRlcm5hbE1lZXRpbmdcbiAgICAgIGRlZmF1bHRJc01lZXRpbmdcbiAgICAgIGRlZmF1bHRJc0V4dGVybmFsTWVldGluZ1xuICAgICAgZGVmYXVsdE1lZXRpbmdNb2RpZmlhYmxlXG4gICAgICBkZWZhdWx0RXh0ZXJuYWxNZWV0aW5nTW9kaWZpYWJsZVxuICAgIH1cbiAgfVxuYDtcbiJdfQ==