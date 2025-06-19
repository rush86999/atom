import { Request, Response } from 'express';
import got from 'got';

// Assume these are defined elsewhere and imported
const HASURA_URL = process.env.HASURA_URL || 'http://localhost:8080/v1/graphql';
const HASURA_ADMIN_SECRET = process.env.HASURA_ADMIN_SECRET || 'admin-secret';

interface PreferenceInput {
  preferred_start_datetime: string;
  preferred_end_datetime: string;
}

interface SubmitExternalPreferenceRequestBody {
  preference_token: string;
  preferences: PreferenceInput[];
}

interface MeetingAssistAttendee {
  id: string;
  meeting_assist_id: string;
  token_expires_at?: string | null;
  // preference_token is validated from the input, so not strictly needed here from DB
}

interface MeetingAssist {
  id: string;
  window_start_date: string; // Assuming column names are window_start_date
  window_end_date: string;   // and window_end_date
}

// Helper function for Hasura requests
async function callHasura<T = any>(query: string, variables: Record<string, any>): Promise<T> {
  const response = await got.post(HASURA_URL, {
    json: {
      query,
      variables,
    },
    headers: {
      'x-hasura-admin-secret': HASURA_ADMIN_SECRET,
    },
    responseType: 'json',
  });
  if (response.body.errors) {
    console.error('Hasura errors:', JSON.stringify(response.body.errors, null, 2));
    throw new Error(`Hasura request failed: ${response.body.errors[0].message}`);
  }
  return response.body.data;
}

const GET_ATTENDEE_BY_TOKEN = `
  query GetAttendeeByToken($preference_token: String!) {
    Meeting_Assist_Attendee(where: {preference_token: {_eq: $preference_token}}) {
      id
      meeting_assist_id
      token_expires_at
    }
  }
`;

const GET_MEETING_ASSIST = `
  query GetMeetingAssist($id: uuid!) {
    Meeting_Assist_by_pk(id: $id) {
      id
      window_start_date
      window_end_date
    }
  }
`;

const DELETE_EXISTING_PREFERENCES = `
  mutation DeleteExistingPreferences($meeting_assist_attendee_id: uuid!, $meeting_assist_id: uuid!) {
    delete_Meeting_Assist_External_Attendee_Preference(
      where: {
        meeting_assist_attendee_id: {_eq: $meeting_assist_attendee_id},
        meeting_assist_id: {_eq: $meeting_assist_id}
      }
    ) {
      affected_rows
    }
  }
`;

const INSERT_PREFERENCE = `
  mutation InsertPreference(
    $meeting_assist_id: uuid!,
    $meeting_assist_attendee_id: uuid!,
    $preference_token: String!,
    $preferred_start_datetime: timestamptz!,
    $preferred_end_datetime: timestamptz!,
    $token_expires_at: timestamptz!
  ) {
    insert_Meeting_Assist_External_Attendee_Preference_one(object: {
      meeting_assist_id: $meeting_assist_id,
      meeting_assist_attendee_id: $meeting_assist_attendee_id,
      preference_token: $preference_token,
      preferred_start_datetime: $preferred_start_datetime,
      preferred_end_datetime: $preferred_end_datetime,
      token_expires_at: $token_expires_at
    }) {
      id
    }
  }
`;


export default async (req: Request, res: Response): Promise<void> => {
  const { preference_token, preferences } = req.body as SubmitExternalPreferenceRequestBody;

  if (!preference_token || !preferences || !Array.isArray(preferences)) {
    res.status(400).json({ message: 'Missing preference_token or preferences in request body' });
    return;
  }

  if (preferences.length === 0) {
    res.status(400).json({ message: 'Preferences array cannot be empty' });
    return;
  }

  try {
    // 1. Token Validation
    const attendeeData = await callHasura<{ Meeting_Assist_Attendee: MeetingAssistAttendee[] }>(
      GET_ATTENDEE_BY_TOKEN,
      { preference_token }
    );

    const attendee = attendeeData?.Meeting_Assist_Attendee?.[0];

    if (!attendee) {
      res.status(403).json({ message: 'Invalid or expired preference token.' });
      return;
    }

    if (attendee.token_expires_at && new Date(attendee.token_expires_at) < new Date()) {
      res.status(403).json({ message: 'Preference token has expired.' });
      return;
    }

    const { meeting_assist_id, id: meeting_assist_attendee_id } = attendee;

    // 2. Meeting Window Validation
    const meetingAssistData = await callHasura<{ Meeting_Assist_by_pk: MeetingAssist }>(
      GET_MEETING_ASSIST,
      { id: meeting_assist_id }
    );

    const meetingAssist = meetingAssistData?.Meeting_Assist_by_pk;

    if (!meetingAssist) {
      res.status(404).json({ message: 'Associated meeting not found.' });
      return;
    }

    const meetingWindowStart = new Date(meetingAssist.window_start_date);
    const meetingWindowEnd = new Date(meetingAssist.window_end_date);

    for (const pref of preferences) {
      const prefStart = new Date(pref.preferred_start_datetime);
      const prefEnd = new Date(pref.preferred_end_datetime);

      if (prefEnd <= prefStart) {
        res.status(400).json({ message: 'Preferred end datetime must be after preferred start datetime.' });
        return;
      }
      if (prefStart < meetingWindowStart || prefEnd > meetingWindowEnd) {
        res.status(400).json({
          message: `Preferences must be within the meeting window: ${meetingAssist.window_start_date} to ${meetingAssist.window_end_date}.`
        });
        return;
      }
    }

    // 3. Data Insertion
    // Delete existing preferences
    await callHasura(DELETE_EXISTING_PREFERENCES, {
      meeting_assist_attendee_id,
      meeting_assist_id,
    });

    // Insert new preferences
    // For the new table, token_expires_at for the *preference record* itself might not be needed,
    // as the link is validated via the attendee's token.
    // However, if the table schema *requires* it (as per step 1 DDL), we must provide it.
    // Let's assume the `Meeting_Assist_External_Attendee_Preference.token_expires_at` refers to the expiry of the preference submission itself,
    // which can be set to a short duration or same as attendee's token expiry for simplicity here.
    // The DDL has token_expires_at as NOT NULL.
    const preferenceTokenExpiresAt = attendee.token_expires_at || new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString(); // Default to 24h if not set on attendee

    for (const pref of preferences) {
      await callHasura(INSERT_PREFERENCE, {
        meeting_assist_id,
        meeting_assist_attendee_id,
        preference_token, // Storing the original token used for this submission batch
        preferred_start_datetime: pref.preferred_start_datetime,
        preferred_end_datetime: pref.preferred_end_datetime,
        token_expires_at: preferenceTokenExpiresAt, // This is for the preference record itself
      });
    }

    res.status(201).json({ message: 'Preferences submitted successfully.' });

  } catch (error) {
    console.error('Error submitting external preference:', error);
    // Type guard for error
    let errorMessage = 'An unexpected error occurred.';
    if (error instanceof Error) {
      errorMessage = error.message;
    }
    res.status(500).json({ message: 'Failed to submit preferences.', error: errorMessage });
  }
};
