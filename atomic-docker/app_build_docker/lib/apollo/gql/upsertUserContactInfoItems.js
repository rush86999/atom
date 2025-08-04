"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const client_1 = require("@apollo/client");
exports.default = (0, client_1.gql) `
  mutation UpsertUserContactInfo(
    $contactInfoItems: [User_Contact_Info_insert_input!]!
  ) {
    insert_User_Contact_Info(
      objects: $contactInfoItems
      on_conflict: {
        constraint: User_Contact_Info_pkey
        update_columns: [name, primary, type, updatedAt]
      }
    ) {
      affected_rows
      returning {
        createdDate
        id
        name
        primary
        type
        updatedAt
        userId
      }
    }
  }
`;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoidXBzZXJ0VXNlckNvbnRhY3RJbmZvSXRlbXMuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJ1cHNlcnRVc2VyQ29udGFjdEluZm9JdGVtcy50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOztBQUFBLDJDQUFxQztBQUVyQyxrQkFBZSxJQUFBLFlBQUcsRUFBQTs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Q0F1QmpCLENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgeyBncWwgfSBmcm9tICdAYXBvbGxvL2NsaWVudCc7XG5cbmV4cG9ydCBkZWZhdWx0IGdxbGBcbiAgbXV0YXRpb24gVXBzZXJ0VXNlckNvbnRhY3RJbmZvKFxuICAgICRjb250YWN0SW5mb0l0ZW1zOiBbVXNlcl9Db250YWN0X0luZm9faW5zZXJ0X2lucHV0IV0hXG4gICkge1xuICAgIGluc2VydF9Vc2VyX0NvbnRhY3RfSW5mbyhcbiAgICAgIG9iamVjdHM6ICRjb250YWN0SW5mb0l0ZW1zXG4gICAgICBvbl9jb25mbGljdDoge1xuICAgICAgICBjb25zdHJhaW50OiBVc2VyX0NvbnRhY3RfSW5mb19wa2V5XG4gICAgICAgIHVwZGF0ZV9jb2x1bW5zOiBbbmFtZSwgcHJpbWFyeSwgdHlwZSwgdXBkYXRlZEF0XVxuICAgICAgfVxuICAgICkge1xuICAgICAgYWZmZWN0ZWRfcm93c1xuICAgICAgcmV0dXJuaW5nIHtcbiAgICAgICAgY3JlYXRlZERhdGVcbiAgICAgICAgaWRcbiAgICAgICAgbmFtZVxuICAgICAgICBwcmltYXJ5XG4gICAgICAgIHR5cGVcbiAgICAgICAgdXBkYXRlZEF0XG4gICAgICAgIHVzZXJJZFxuICAgICAgfVxuICAgIH1cbiAgfVxuYDtcbiJdfQ==