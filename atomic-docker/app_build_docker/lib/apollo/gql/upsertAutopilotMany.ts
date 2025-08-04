import { gql } from '@apollo/client';

export default gql`
  mutation UpsertAutopilotMany($autopilots: [Autopilot_insert_input!]!) {
    insert_Autopilot(
      objects: $autopilots
      on_conflict: {
        constraint: Autopilot_pkey
        update_columns: [payload, scheduleAt, timezone, updatedAt]
      }
    ) {
      affected_rows
      returning {
        createdDate
        id
        payload
        scheduleAt
        timezone
        updatedAt
        userId
      }
    }
  }
`;
