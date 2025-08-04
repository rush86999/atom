import { gql } from '@apollo/client';

export default gql`
  mutation UpdateUserForUserPreference($id: uuid!, $userPreferenceId: uuid) {
    update_User_by_pk(
      pk_columns: { id: $id }
      _set: { userPreferenceId: $userPreferenceId }
    ) {
      createdDate
      deleted
      email
      id
      name
      updatedAt
      userPreferenceId
    }
  }
`;
