"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const client_1 = require("@apollo/client");
exports.default = (0, client_1.gql) `
  mutation UpdateFeedbackForLastSeen($id: uuid!, $lastSeen: timestamptz!) {
    update_Feedback_by_pk(
      pk_columns: { id: $id }
      _set: { lastSeen: $lastSeen }
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
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoidXBkYXRlRmVlZGJhY2tGb3JMYXN0U2Vlbi5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbInVwZGF0ZUZlZWRiYWNrRm9yTGFzdFNlZW4udHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7QUFBQSwyQ0FBcUM7QUFFckMsa0JBQWUsSUFBQSxZQUFHLEVBQUE7Ozs7Ozs7Ozs7Ozs7Ozs7O0NBaUJqQixDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IHsgZ3FsIH0gZnJvbSAnQGFwb2xsby9jbGllbnQnO1xuXG5leHBvcnQgZGVmYXVsdCBncWxgXG4gIG11dGF0aW9uIFVwZGF0ZUZlZWRiYWNrRm9yTGFzdFNlZW4oJGlkOiB1dWlkISwgJGxhc3RTZWVuOiB0aW1lc3RhbXB0eiEpIHtcbiAgICB1cGRhdGVfRmVlZGJhY2tfYnlfcGsoXG4gICAgICBwa19jb2x1bW5zOiB7IGlkOiAkaWQgfVxuICAgICAgX3NldDogeyBsYXN0U2VlbjogJGxhc3RTZWVuIH1cbiAgICApIHtcbiAgICAgIGxhc3RTZWVuXG4gICAgICBxdWVzdGlvbjFfQVxuICAgICAgcXVlc3Rpb24xX0JcbiAgICAgIHF1ZXN0aW9uMV9DXG4gICAgICBxdWVzdGlvbjJcbiAgICAgIHF1ZXN0aW9uM1xuICAgICAgcXVlc3Rpb240XG4gICAgICB1cGRhdGVkQXRcbiAgICAgIHVzZXJJZFxuICAgIH1cbiAgfVxuYDtcbiJdfQ==