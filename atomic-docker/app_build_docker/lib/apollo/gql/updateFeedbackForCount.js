"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const client_1 = require("@apollo/client");
exports.default = (0, client_1.gql) `
  mutation UpdateFeedbackForCount(
    $id: uuid!
    $lastSeen: timestamptz!
    $count: Int!
  ) {
    update_Feedback_by_pk(
      pk_columns: { id: $id }
      _set: { lastSeen: $lastSeen, count: $count }
    ) {
      lastSeen
      question1_A
      question1_B
      question1_C
      question2
      question3
      question4
      updatedAt
      userId
    }
  }
`;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoidXBkYXRlRmVlZGJhY2tGb3JDb3VudC5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbInVwZGF0ZUZlZWRiYWNrRm9yQ291bnQudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7QUFBQSwyQ0FBcUM7QUFFckMsa0JBQWUsSUFBQSxZQUFHLEVBQUE7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7OztDQXFCakIsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7IGdxbCB9IGZyb20gJ0BhcG9sbG8vY2xpZW50JztcblxuZXhwb3J0IGRlZmF1bHQgZ3FsYFxuICBtdXRhdGlvbiBVcGRhdGVGZWVkYmFja0ZvckNvdW50KFxuICAgICRpZDogdXVpZCFcbiAgICAkbGFzdFNlZW46IHRpbWVzdGFtcHR6IVxuICAgICRjb3VudDogSW50IVxuICApIHtcbiAgICB1cGRhdGVfRmVlZGJhY2tfYnlfcGsoXG4gICAgICBwa19jb2x1bW5zOiB7IGlkOiAkaWQgfVxuICAgICAgX3NldDogeyBsYXN0U2VlbjogJGxhc3RTZWVuLCBjb3VudDogJGNvdW50IH1cbiAgICApIHtcbiAgICAgIGxhc3RTZWVuXG4gICAgICBxdWVzdGlvbjFfQVxuICAgICAgcXVlc3Rpb24xX0JcbiAgICAgIHF1ZXN0aW9uMV9DXG4gICAgICBxdWVzdGlvbjJcbiAgICAgIHF1ZXN0aW9uM1xuICAgICAgcXVlc3Rpb240XG4gICAgICB1cGRhdGVkQXRcbiAgICAgIHVzZXJJZFxuICAgIH1cbiAgfVxuYDtcbiJdfQ==