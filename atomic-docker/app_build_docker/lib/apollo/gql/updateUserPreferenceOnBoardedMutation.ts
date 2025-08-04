import { gql } from '@apollo/client';

export default gql`
  mutation UpdateUserPreferenceOnBoarding(
    $userId: uuid!
    $onBoarded: Boolean!
  ) {
    update_User_Preference(
      where: { userId: { _eq: $userId } }
      _set: { onBoarded: $onBoarded }
    ) {
      affected_rows
      returning {
        id
        onBoarded
      }
    }
  }
`;
