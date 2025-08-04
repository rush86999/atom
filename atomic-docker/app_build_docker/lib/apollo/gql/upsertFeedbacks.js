"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const client_1 = require("@apollo/client");
exports.default = (0, client_1.gql) `
  mutation InsertFeedback($feedbacks: [Feedback_insert_input!]!) {
    insert_Feedback(
      objects: $feedbacks
      on_conflict: {
        constraint: Feedback_pkey
        update_columns: [
          question1_A
          question1_B
          question1_C
          question2
          question3
          question4
          lastSeen
          count
          deleted
          updatedAt
        ]
      }
    ) {
      returning {
        id
      }
    }
  }
`;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoidXBzZXJ0RmVlZGJhY2tzLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsidXBzZXJ0RmVlZGJhY2tzLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiI7O0FBQUEsMkNBQXFDO0FBRXJDLGtCQUFlLElBQUEsWUFBRyxFQUFBOzs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7O0NBeUJqQixDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IHsgZ3FsIH0gZnJvbSAnQGFwb2xsby9jbGllbnQnO1xuXG5leHBvcnQgZGVmYXVsdCBncWxgXG4gIG11dGF0aW9uIEluc2VydEZlZWRiYWNrKCRmZWVkYmFja3M6IFtGZWVkYmFja19pbnNlcnRfaW5wdXQhXSEpIHtcbiAgICBpbnNlcnRfRmVlZGJhY2soXG4gICAgICBvYmplY3RzOiAkZmVlZGJhY2tzXG4gICAgICBvbl9jb25mbGljdDoge1xuICAgICAgICBjb25zdHJhaW50OiBGZWVkYmFja19wa2V5XG4gICAgICAgIHVwZGF0ZV9jb2x1bW5zOiBbXG4gICAgICAgICAgcXVlc3Rpb24xX0FcbiAgICAgICAgICBxdWVzdGlvbjFfQlxuICAgICAgICAgIHF1ZXN0aW9uMV9DXG4gICAgICAgICAgcXVlc3Rpb24yXG4gICAgICAgICAgcXVlc3Rpb24zXG4gICAgICAgICAgcXVlc3Rpb240XG4gICAgICAgICAgbGFzdFNlZW5cbiAgICAgICAgICBjb3VudFxuICAgICAgICAgIGRlbGV0ZWRcbiAgICAgICAgICB1cGRhdGVkQXRcbiAgICAgICAgXVxuICAgICAgfVxuICAgICkge1xuICAgICAgcmV0dXJuaW5nIHtcbiAgICAgICAgaWRcbiAgICAgIH1cbiAgICB9XG4gIH1cbmA7XG4iXX0=