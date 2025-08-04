"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const client_1 = require("@apollo/client");
exports.default = (0, client_1.gql) `
  mutation InsertUserContactInfoOne(
    $contactInfo: User_Contact_Info_insert_input!
  ) {
    insert_User_Contact_Info_one(object: $contactInfo) {
      createdDate
      id
      name
      primary
      type
      updatedAt
      userId
    }
  }
`;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiaW5zZXJ0VXNlckNvbnRhY3RJbmZvT25lLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsiaW5zZXJ0VXNlckNvbnRhY3RJbmZvT25lLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiI7O0FBQUEsMkNBQXFDO0FBRXJDLGtCQUFlLElBQUEsWUFBRyxFQUFBOzs7Ozs7Ozs7Ozs7OztDQWNqQixDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IHsgZ3FsIH0gZnJvbSAnQGFwb2xsby9jbGllbnQnO1xuXG5leHBvcnQgZGVmYXVsdCBncWxgXG4gIG11dGF0aW9uIEluc2VydFVzZXJDb250YWN0SW5mb09uZShcbiAgICAkY29udGFjdEluZm86IFVzZXJfQ29udGFjdF9JbmZvX2luc2VydF9pbnB1dCFcbiAgKSB7XG4gICAgaW5zZXJ0X1VzZXJfQ29udGFjdF9JbmZvX29uZShvYmplY3Q6ICRjb250YWN0SW5mbykge1xuICAgICAgY3JlYXRlZERhdGVcbiAgICAgIGlkXG4gICAgICBuYW1lXG4gICAgICBwcmltYXJ5XG4gICAgICB0eXBlXG4gICAgICB1cGRhdGVkQXRcbiAgICAgIHVzZXJJZFxuICAgIH1cbiAgfVxuYDtcbiJdfQ==