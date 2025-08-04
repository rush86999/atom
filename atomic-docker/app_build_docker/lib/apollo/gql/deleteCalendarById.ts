import { gql } from '@apollo/client';

export default gql`
  mutation DeleteCalendarById($id: String!) {
    deleteCalendarById(input: { id: $id }) {
      # Renamed and using input object
      calendar {
        # Standard PostGraphile payload often returns the deleted object or its ID
        id # Commonly, only the ID of the deleted object is returned
        # title # Other fields might be available if the PG function returns the full record
      }
      # clientMutationId # Optional, for Relay compatibility
      # deletedCalendarId # Alternative way PostGraphile might return the ID
    }
  }
`;
// Note: The exact return fields (e.g., 'calendar { id }' vs 'deletedCalendarId')
// depend on PostGraphile's default CRUD mutations or how a custom delete function is defined.
// Returning just the ID is common. The original query returned many fields, which is less typical for PostGraphile deletes.
