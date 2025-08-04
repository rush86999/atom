import got from 'got';
// Assume these are defined elsewhere and imported
const HASURA_URL = process.env.HASURA_URL || 'http://localhost:8080/v1/graphql';
const HASURA_ADMIN_SECRET = process.env.HASURA_ADMIN_SECRET || 'admin-secret';
// Helper function for Hasura requests
async function callHasura(query, variables) {
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
export default async (req, res) => {
    const { preference_token, preferences } = req.body;
    if (!preference_token || !preferences || !Array.isArray(preferences)) {
        res
            .status(400)
            .json({
            message: 'Missing preference_token or preferences in request body',
        });
        return;
    }
    if (preferences.length === 0) {
        res.status(400).json({ message: 'Preferences array cannot be empty' });
        return;
    }
    try {
        // 1. Token Validation
        const attendeeData = await callHasura(GET_ATTENDEE_BY_TOKEN, { preference_token });
        const attendee = attendeeData?.Meeting_Assist_Attendee?.[0];
        if (!attendee) {
            res.status(403).json({ message: 'Invalid or expired preference token.' });
            return;
        }
        if (attendee.token_expires_at &&
            new Date(attendee.token_expires_at) < new Date()) {
            res.status(403).json({ message: 'Preference token has expired.' });
            return;
        }
        const { meeting_assist_id, id: meeting_assist_attendee_id } = attendee;
        // 2. Meeting Window Validation
        const meetingAssistData = await callHasura(GET_MEETING_ASSIST, { id: meeting_assist_id });
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
                res
                    .status(400)
                    .json({
                    message: 'Preferred end datetime must be after preferred start datetime.',
                });
                return;
            }
            if (prefStart < meetingWindowStart || prefEnd > meetingWindowEnd) {
                res.status(400).json({
                    message: `Preferences must be within the meeting window: ${meetingAssist.window_start_date} to ${meetingAssist.window_end_date}.`,
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
        const preferenceTokenExpiresAt = attendee.token_expires_at ||
            new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString(); // Default to 24h if not set on attendee
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
    }
    catch (error) {
        console.error('Error submitting external preference:', error);
        // Type guard for error
        let errorMessage = 'An unexpected error occurred.';
        if (error instanceof Error) {
            errorMessage = error.message;
        }
        res
            .status(500)
            .json({ message: 'Failed to submit preferences.', error: errorMessage });
    }
};
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoic3VibWl0LWV4dGVybmFsLXByZWZlcmVuY2UuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJzdWJtaXQtZXh0ZXJuYWwtcHJlZmVyZW5jZS50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiQUFDQSxPQUFPLEdBQUcsTUFBTSxLQUFLLENBQUM7QUFFdEIsa0RBQWtEO0FBQ2xELE1BQU0sVUFBVSxHQUFHLE9BQU8sQ0FBQyxHQUFHLENBQUMsVUFBVSxJQUFJLGtDQUFrQyxDQUFDO0FBQ2hGLE1BQU0sbUJBQW1CLEdBQUcsT0FBTyxDQUFDLEdBQUcsQ0FBQyxtQkFBbUIsSUFBSSxjQUFjLENBQUM7QUF5QjlFLHNDQUFzQztBQUN0QyxLQUFLLFVBQVUsVUFBVSxDQUN2QixLQUFhLEVBQ2IsU0FBOEI7SUFFOUIsTUFBTSxRQUFRLEdBQUcsTUFBTSxHQUFHLENBQUMsSUFBSSxDQUFDLFVBQVUsRUFBRTtRQUMxQyxJQUFJLEVBQUU7WUFDSixLQUFLO1lBQ0wsU0FBUztTQUNWO1FBQ0QsT0FBTyxFQUFFO1lBQ1AsdUJBQXVCLEVBQUUsbUJBQW1CO1NBQzdDO1FBQ0QsWUFBWSxFQUFFLE1BQU07S0FDckIsQ0FBQyxDQUFDO0lBQ0gsSUFBSSxRQUFRLENBQUMsSUFBSSxDQUFDLE1BQU0sRUFBRSxDQUFDO1FBQ3pCLE9BQU8sQ0FBQyxLQUFLLENBQ1gsZ0JBQWdCLEVBQ2hCLElBQUksQ0FBQyxTQUFTLENBQUMsUUFBUSxDQUFDLElBQUksQ0FBQyxNQUFNLEVBQUUsSUFBSSxFQUFFLENBQUMsQ0FBQyxDQUM5QyxDQUFDO1FBQ0YsTUFBTSxJQUFJLEtBQUssQ0FDYiwwQkFBMEIsUUFBUSxDQUFDLElBQUksQ0FBQyxNQUFNLENBQUMsQ0FBQyxDQUFDLENBQUMsT0FBTyxFQUFFLENBQzVELENBQUM7SUFDSixDQUFDO0lBQ0QsT0FBTyxRQUFRLENBQUMsSUFBSSxDQUFDLElBQUksQ0FBQztBQUM1QixDQUFDO0FBRUQsTUFBTSxxQkFBcUIsR0FBRzs7Ozs7Ozs7Q0FRN0Is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RUFBRSx3QkFBd0IsRUFBRSwyQ0FBMkM7YUFDeEYsQ0FBQyxDQUFDO1FBQ0wsQ0FBQztRQUVELEdBQUcsQ0FBQyxNQUFNLENBQUMsR0FBRyxDQUFDLENBQUMsSUFBSSxDQUFDLEVBQUUsT0FBTyxFQUFFLHFDQUFxQyxFQUFFLENBQUMsQ0FBQztJQUMzRSxDQUFDO0lBQUMsT0FBTyxLQUFLLEVBQUUsQ0FBQztRQUNmLE9BQU8sQ0FBQyxLQUFLLENBQUMsdUNBQXVDLEVBQUUsS0FBSyxDQUFDLENBQUM7UUFDOUQsdUJBQXVCO1FBQ3ZCLElBQUksWUFBWSxHQUFHLCtCQUErQixDQUFDO1FBQ25ELElBQUksS0FBSyxZQUFZLEtBQUssRUFBRSxDQUFDO1lBQzNCLFlBQVksR0FBRyxLQUFLLENBQUMsT0FBTyxDQUFDO1FBQy9CLENBQUM7UUFDRCxHQUFHO2FBQ0EsTUFBTSxDQUFDLEdBQUcsQ0FBQzthQUNYLElBQUksQ0FBQyxFQUFFLE9BQU8sRUFBRSwrQkFBK0IsRUFBRSxLQUFLLEVBQUUsWUFBWSxFQUFFLENBQUMsQ0FBQztJQUM3RSxDQUFDO0FBQ0gsQ0FBQyxDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IHsgUmVxdWVzdCwgUmVzcG9uc2UgfSBmcm9tICdleHByZXNzJztcbmltcG9ydCBnb3QgZnJvbSAnZ290JztcblxuLy8gQXNzdW1lIHRoZXNlIGFyZSBkZWZpbmVkIGVsc2V3aGVyZSBhbmQgaW1wb3J0ZWRcbmNvbnN0IEhBU1VSQV9VUkwgPSBwcm9jZXNzLmVudi5IQVNVUkFfVVJMIHx8ICdodHRwOi8vbG9jYWxob3N0OjgwODAvdjEvZ3JhcGhxbCc7XG5jb25zdCBIQVNVUkFfQURNSU5fU0VDUkVUID0gcHJvY2Vzcy5lbnYuSEFTVVJBX0FETUlOX1NFQ1JFVCB8fCAnYWRtaW4tc2VjcmV0JztcblxuaW50ZXJmYWNlIFByZWZlcmVuY2VJbnB1dCB7XG4gIHByZWZlcnJlZF9zdGFydF9kYXRldGltZTogc3RyaW5nO1xuICBwcmVmZXJyZWRfZW5kX2RhdGV0aW1lOiBzdHJpbmc7XG59XG5cbmludGVyZmFjZSBTdWJtaXRFeHRlcm5hbFByZWZlcmVuY2VSZXF1ZXN0Qm9keSB7XG4gIHByZWZlcmVuY2VfdG9rZW46IHN0cmluZztcbiAgcHJlZmVyZW5jZXM6IFByZWZlcmVuY2VJbnB1dFtdO1xufVxuXG5pbnRlcmZhY2UgTWVldGluZ0Fzc2lzdEF0dGVuZGVlIHtcbiAgaWQ6IHN0cmluZztcbiAgbWVldGluZ19hc3Npc3RfaWQ6IHN0cmluZztcbiAgdG9rZW5fZXhwaXJlc19hdD86IHN0cmluZyB8IG51bGw7XG4gIC8vIHByZWZlcmVuY2VfdG9rZW4gaXMgdmFsaWRhdGVkIGZyb20gdGhlIGlucHV0LCBzbyBub3Qgc3RyaWN0bHkgbmVlZGVkIGhlcmUgZnJvbSBEQlxufVxuXG5pbnRlcmZhY2UgTWVldGluZ0Fzc2lzdCB7XG4gIGlkOiBzdHJpbmc7XG4gIHdpbmRvd19zdGFydF9kYXRlOiBzdHJpbmc7IC8vIEFzc3VtaW5nIGNvbHVtbiBuYW1lcyBhcmUgd2luZG93X3N0YXJ0X2RhdGVcbiAgd2luZG93X2VuZF9kYXRlOiBzdHJpbmc7IC8vIGFuZCB3aW5kb3dfZW5kX2RhdGVcbn1cblxuLy8gSGVscGVyIGZ1bmN0aW9uIGZvciBIYXN1cmEgcmVxdWVzdHNcbmFzeW5jIGZ1bmN0aW9uIGNhbGxIYXN1cmE8VCA9IGFueT4oXG4gIHF1ZXJ5OiBzdHJpbmcsXG4gIHZhcmlhYmxlczogUmVjb3JkPHN0cmluZywgYW55PlxuKTogUHJvbWlzZTxUPiB7XG4gIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgZ290LnBvc3QoSEFTVVJBX1VSTCwge1xuICAgIGpzb246IHtcbiAgICAgIHF1ZXJ5LFxuICAgICAgdmFyaWFibGVzLFxuICAgIH0sXG4gICAgaGVhZGVyczoge1xuICAgICAgJ3gtaGFzdXJhLWFkbWluLXNlY3JldCc6IEhBU1VSQV9BRE1JTl9TRUNSRVQsXG4gICAgfSxcbiAgICByZXNwb25zZVR5cGU6ICdqc29uJyxcbiAgfSk7XG4gIGlmIChyZXNwb25zZS5ib2R5LmVycm9ycykge1xuICAgIGNvbnNvbGUuZXJyb3IoXG4gICAgICAnSGFzdXJhIGVycm9yczonLFxuICAgICAgSlNPTi5zdHJpbmdpZnkocmVzcG9uc2UuYm9keS5lcnJvcnMsIG51bGwsIDIpXG4gICAgKTtcbiAgICB0aHJvdyBuZXcgRXJyb3IoXG4gICAgICBgSGFzdXJhIHJlcXVlc3QgZmFpbGVkOiAke3Jlc3BvbnNlLmJvZHkuZXJyb3JzWzBdLm1lc3NhZ2V9YFxuICAgICk7XG4gIH1cbiAgcmV0dXJuIHJlc3BvbnNlLmJvZHkuZGF0YTtcbn1cblxuY29uc3QgR0VUX0FUVEVOREVFX0JZX1RPS0VOID0gYFxuICBxdWVyeSBHZXRBdHRlbmRlZUJ5VG9rZW4oJHByZWZlcmVuY2VfdG9rZW46IFN0cmluZyEpIHtcbiAgICBNZWV0aW5nX0Fzc2lzdF9BdHRlbmRlZSh3aGVyZToge3ByZWZlcmVuY2VfdG9rZW46IHtfZXE6ICRwcmVmZXJlbmNlX3Rva2VufX0pIHtcbiAgICAgIGlkXG4gICAgICBtZWV0aW5nX2Fzc2lzdF9pZFxuICAgICAgdG9rZW5fZXhwaXJlc19hdFxuICAgIH1cbiAgfVxuYDtcblxuY29uc3QgR0VUX01FRVRJTkdfQVNTSVNUID0gYFxuICBxdWVyeSBHZXRNZWV0aW5nQXNzaXN0KCRpZDogdXVpZCEpIHtcbiAgICBNZWV0aW5nX0Fzc2lzdF9ieV9wayhpZDogJGlkKSB7XG4gICAgICBpZFxuICAgICAgd2luZG93X3N0YXJ0X2RhdGVcbiAgICAgIHdpbmRvd19lbmRfZGF0ZVxuICAgIH1cbiAgfVxuYDtcblxuY29uc3QgREVMRVRFX0VYSVNUSU5HX1BSRUZFUkVOQ0VTID0gYFxuICBtdXRhdGlvbiBEZWxldGVFeGlzdGluZ1ByZWZlcmVuY2VzKCRtZWV0aW5nX2Fzc2lzdF9hdHRlbmRlZV9pZDogdXVpZCEsICRtZWV0aW5nX2Fzc2lzdF9pZDogdXVpZCEpIHtcbiAgICBkZWxldGVfTWVldGluZ19Bc3Npc3RfRXh0ZXJuYWxfQXR0ZW5kZWVfUHJlZmVyZW5jZShcbiAgICAgIHdoZXJlOiB7XG4gICAgICAgIG1lZXRpbmdfYXNzaXN0X2F0dGVuZGVlX2lkOiB7X2VxOiAkbWVldGluZ19hc3Npc3RfYXR0ZW5kZWVfaWR9LFxuICAgICAgICBtZWV0aW5nX2Fzc2lzdF9pZDoge19lcTogJG1lZXRpbmdfYXNzaXN0X2lkfVxuICAgICAgfVxuICAgICkge1xuICAgICAgYWZmZWN0ZWRfcm93c1xuICAgIH1cbiAgfVxuYDtcblxuY29uc3QgSU5TRVJUX1BSRUZFUkVOQ0UgPSBgXG4gIG11dGF0aW9uIEluc2VydFByZWZlcmVuY2UoXG4gICAgJG1lZXRpbmdfYXNzaXN0X2lkOiB1dWlkISxcbiAgICAkbWVldGluZ19hc3Npc3RfYXR0ZW5kZWVfaWQ6IHV1aWQhLFxuICAgICRwcmVmZXJlbmNlX3Rva2VuOiBTdHJpbmchLFxuICAgICRwcmVmZXJyZWRfc3RhcnRfZGF0ZXRpbWU6IHRpbWVzdGFtcHR6ISxcbiAgICAkcHJlZmVycmVkX2VuZF9kYXRldGltZTogdGltZXN0YW1wdHohLFxuICAgICR0b2tlbl9leHBpcmVzX2F0OiB0aW1lc3RhbXB0eiFcbiAgKSB7XG4gICAgaW5zZXJ0X01lZXRpbmdfQXNzaXN0X0V4dGVybmFsX0F0dGVuZGVlX1ByZWZlcmVuY2Vfb25lKG9iamVjdDoge1xuICAgICAgbWVldGluZ19hc3Npc3RfaWQ6ICRtZWV0aW5nX2Fzc2lzdF9pZCxcbiAgICAgIG1lZXRpbmdfYXNzaXN0X2F0dGVuZGVlX2lkOiAkbWVldGluZ19hc3Npc3RfYXR0ZW5kZWVfaWQsXG4gICAgICBwcmVmZXJlbmNlX3Rva2VuOiAkcHJlZmVyZW5jZV90b2tlbixcbiAgICAgIHByZWZlcnJlZF9zdGFydF9kYXRldGltZTogJHByZWZlcnJlZF9zdGFydF9kYXRldGltZSxcbiAgICAgIHByZWZlcnJlZF9lbmRfZGF0ZXRpbWU6ICRwcmVmZXJyZWRfZW5kX2RhdGV0aW1lLFxuICAgICAgdG9rZW5fZXhwaXJlc19hdDogJHRva2VuX2V4cGlyZXNfYXRcbiAgICB9KSB7XG4gICAgICBpZFxuICAgIH1cbiAgfVxuYDtcblxuZXhwb3J0IGRlZmF1bHQgYXN5bmMgKHJlcTogUmVxdWVzdCwgcmVzOiBSZXNwb25zZSk6IFByb21pc2U8dm9pZD4gPT4ge1xuICBjb25zdCB7IHByZWZlcmVuY2VfdG9rZW4sIHByZWZlcmVuY2VzIH0gPVxuICAgIHJlcS5ib2R5IGFzIFN1Ym1pdEV4dGVybmFsUHJlZmVyZW5jZVJlcXVlc3RCb2R5O1xuXG4gIGlmICghcHJlZmVyZW5jZV90b2tlbiB8fCAhcHJlZmVyZW5jZXMgfHwgIUFycmF5LmlzQXJyYXkocHJlZmVyZW5jZXMpKSB7XG4gICAgcmVzXG4gICAgICAuc3RhdHVzKDQwMClcbiAgICAgIC5qc29uKHtcbiAgICAgICAgbWVzc2FnZTogJ01pc3NpbmcgcHJlZmVyZW5jZV90b2tlbiBvciBwcmVmZXJlbmNlcyBpbiByZXF1ZXN0IGJvZHknLFxuICAgICAgfSk7XG4gICAgcmV0dXJuO1xuICB9XG5cbiAgaWYgKHByZWZlcmVuY2VzLmxlbmd0aCA9PT0gMCkge1xuICAgIHJlcy5zdGF0dXMoNDAwKS5qc29uKHsgbWVzc2FnZTogJ1ByZWZlcmVuY2VzIGFycmF5IGNhbm5vdCBiZSBlbXB0eScgfSk7XG4gICAgcmV0dXJuO1xuICB9XG5cbiAgdHJ5IHtcbiAgICAvLyAxLiBUb2tlbiBWYWxpZGF0aW9uXG4gICAgY29uc3QgYXR0ZW5kZWVEYXRhID0gYXdhaXQgY2FsbEhhc3VyYTx7XG4gICAgICBNZWV0aW5nX0Fzc2lzdF9BdHRlbmRlZTogTWVldGluZ0Fzc2lzdEF0dGVuZGVlW107XG4gICAgfT4oR0VUX0FUVEVOREVFX0JZX1RPS0VOLCB7IHByZWZlcmVuY2VfdG9rZW4gfSk7XG5cbiAgICBjb25zdCBhdHRlbmRlZSA9IGF0dGVuZGVlRGF0YT8uTWVldGluZ19Bc3Npc3RfQXR0ZW5kZWU/LlswXTtcblxuICAgIGlmICghYXR0ZW5kZWUpIHtcbiAgICAgIHJlcy5zdGF0dXMoNDAzKS5qc29uKHsgbWVzc2FnZTogJ0ludmFsaWQgb3IgZXhwaXJlZCBwcmVmZXJlbmNlIHRva2VuLicgfSk7XG4gICAgICByZXR1cm47XG4gICAgfVxuXG4gICAgaWYgKFxuICAgICAgYXR0ZW5kZWUudG9rZW5fZXhwaXJlc19hdCAmJlxuICAgICAgbmV3IERhdGUoYXR0ZW5kZWUudG9rZW5fZXhwaXJlc19hdCkgPCBuZXcgRGF0ZSgpXG4gICAgKSB7XG4gICAgICByZXMuc3RhdHVzKDQwMykuanNvbih7IG1lc3NhZ2U6ICdQcmVmZXJlbmNlIHRva2VuIGhhcyBleHBpcmVkLicgfSk7XG4gICAgICByZXR1cm47XG4gICAgfVxuXG4gICAgY29uc3QgeyBtZWV0aW5nX2Fzc2lzdF9pZCwgaWQ6IG1lZXRpbmdfYXNzaXN0X2F0dGVuZGVlX2lkIH0gPSBhdHRlbmRlZTtcblxuICAgIC8vIDIuIE1lZXRpbmcgV2luZG93IFZhbGlkYXRpb25cbiAgICBjb25zdCBtZWV0aW5nQXNzaXN0RGF0YSA9IGF3YWl0IGNhbGxIYXN1cmE8e1xuICAgICAgTWVldGluZ19Bc3Npc3RfYnlfcGs6IE1lZXRpbmdBc3Npc3Q7XG4gICAgfT4oR0VUX01FRVRJTkdfQVNTSVNULCB7IGlkOiBtZWV0aW5nX2Fzc2lzdF9pZCB9KTtcblxuICAgIGNvbnN0IG1lZXRpbmdBc3Npc3QgPSBtZWV0aW5nQXNzaXN0RGF0YT8uTWVldGluZ19Bc3Npc3RfYnlfcGs7XG5cbiAgICBpZiAoIW1lZXRpbmdBc3Npc3QpIHtcbiAgICAgIHJlcy5zdGF0dXMoNDA0KS5qc29uKHsgbWVzc2FnZTogJ0Fzc29jaWF0ZWQgbWVldGluZyBub3QgZm91bmQuJyB9KTtcbiAgICAgIHJldHVybjtcbiAgICB9XG5cbiAgICBjb25zdCBtZWV0aW5nV2luZG93U3RhcnQgPSBuZXcgRGF0ZShtZWV0aW5nQXNzaXN0LndpbmRvd19zdGFydF9kYXRlKTtcbiAgICBjb25zdCBtZWV0aW5nV2luZG93RW5kID0gbmV3IERhdGUobWVldGluZ0Fzc2lzdC53aW5kb3dfZW5kX2RhdGUpO1xuXG4gICAgZm9yIChjb25zdCBwcmVmIG9mIHByZWZlcmVuY2VzKSB7XG4gICAgICBjb25zdCBwcmVmU3RhcnQgPSBuZXcgRGF0ZShwcmVmLnByZWZlcnJlZF9zdGFydF9kYXRldGltZSk7XG4gICAgICBjb25zdCBwcmVmRW5kID0gbmV3IERhdGUocHJlZi5wcmVmZXJyZWRfZW5kX2RhdGV0aW1lKTtcblxuICAgICAgaWYgKHByZWZFbmQgPD0gcHJlZlN0YXJ0KSB7XG4gICAgICAgIHJlc1xuICAgICAgICAgIC5zdGF0dXMoNDAwKVxuICAgICAgICAgIC5qc29uKHtcbiAgICAgICAgICAgIG1lc3NhZ2U6XG4gICAgICAgICAgICAgICdQcmVmZXJyZWQgZW5kIGRhdGV0aW1lIG11c3QgYmUgYWZ0ZXIgcHJlZmVycmVkIHN0YXJ0IGRhdGV0aW1lLicsXG4gICAgICAgICAgfSk7XG4gICAgICAgIHJldHVybjtcbiAgICAgIH1cbiAgICAgIGlmIChwcmVmU3RhcnQgPCBtZWV0aW5nV2luZG93U3RhcnQgfHwgcHJlZkVuZCA+IG1lZXRpbmdXaW5kb3dFbmQpIHtcbiAgICAgICAgcmVzLnN0YXR1cyg0MDApLmpzb24oe1xuICAgICAgICAgIG1lc3NhZ2U6IGBQcmVmZXJlbmNlcyBtdXN0IGJlIHdpdGhpbiB0aGUgbWVldGluZyB3aW5kb3c6ICR7bWVldGluZ0Fzc2lzdC53aW5kb3dfc3RhcnRfZGF0ZX0gdG8gJHttZWV0aW5nQXNzaXN0LndpbmRvd19lbmRfZGF0ZX0uYCxcbiAgICAgICAgfSk7XG4gICAgICAgIHJldHVybjtcbiAgICAgIH1cbiAgICB9XG5cbiAgICAvLyAzLiBEYXRhIEluc2VydGlvblxuICAgIC8vIERlbGV0ZSBleGlzdGluZyBwcmVmZXJlbmNlc1xuICAgIGF3YWl0IGNhbGxIYXN1cmEoREVMRVRFX0VYSVNUSU5HX1BSRUZFUkVOQ0VTLCB7XG4gICAgICBtZWV0aW5nX2Fzc2lzdF9hdHRlbmRlZV9pZCxcbiAgICAgIG1lZXRpbmdfYXNzaXN0X2lkLFxuICAgIH0pO1xuXG4gICAgLy8gSW5zZXJ0IG5ldyBwcmVmZXJlbmNlc1xuICAgIC8vIEZvciB0aGUgbmV3IHRhYmxlLCB0b2tlbl9leHBpcmVzX2F0IGZvciB0aGUgKnByZWZlcmVuY2UgcmVjb3JkKiBpdHNlbGYgbWlnaHQgbm90IGJlIG5lZWRlZCxcbiAgICAvLyBhcyB0aGUgbGluayBpcyB2YWxpZGF0ZWQgdmlhIHRoZSBhdHRlbmRlZSdzIHRva2VuLlxuICAgIC8vIEhvd2V2ZXIsIGlmIHRoZSB0YWJsZSBzY2hlbWEgKnJlcXVpcmVzKiBpdCAoYXMgcGVyIHN0ZXAgMSBEREwpLCB3ZSBtdXN0IHByb3ZpZGUgaXQuXG4gICAgLy8gTGV0J3MgYXNzdW1lIHRoZSBgTWVldGluZ19Bc3Npc3RfRXh0ZXJuYWxfQXR0ZW5kZWVfUHJlZmVyZW5jZS50b2tlbl9leHBpcmVzX2F0YCByZWZlcnMgdG8gdGhlIGV4cGlyeSBvZiB0aGUgcHJlZmVyZW5jZSBzdWJtaXNzaW9uIGl0c2VsZixcbiAgICAvLyB3aGljaCBjYW4gYmUgc2V0IHRvIGEgc2hvcnQgZHVyYXRpb24gb3Igc2FtZSBhcyBhdHRlbmRlZSdzIHRva2VuIGV4cGlyeSBmb3Igc2ltcGxpY2l0eSBoZXJlLlxuICAgIC8vIFRoZSBEREwgaGFzIHRva2VuX2V4cGlyZXNfYXQgYXMgTk9UIE5VTEwuXG4gICAgY29uc3QgcHJlZmVyZW5jZVRva2VuRXhwaXJlc0F0ID1cbiAgICAgIGF0dGVuZGVlLnRva2VuX2V4cGlyZXNfYXQgfHxcbiAgICAgIG5ldyBEYXRlKERhdGUubm93KCkgKyAyNCAqIDYwICogNjAgKiAxMDAwKS50b0lTT1N0cmluZygpOyAvLyBEZWZhdWx0IHRvIDI0aCBpZiBub3Qgc2V0IG9uIGF0dGVuZGVlXG5cbiAgICBmb3IgKGNvbnN0IHByZWYgb2YgcHJlZmVyZW5jZXMpIHtcbiAgICAgIGF3YWl0IGNhbGxIYXN1cmEoSU5TRVJUX1BSRUZFUkVOQ0UsIHtcbiAgICAgICAgbWVldGluZ19hc3Npc3RfaWQsXG4gICAgICAgIG1lZXRpbmdfYXNzaXN0X2F0dGVuZGVlX2lkLFxuICAgICAgICBwcmVmZXJlbmNlX3Rva2VuLCAvLyBTdG9yaW5nIHRoZSBvcmlnaW5hbCB0b2tlbiB1c2VkIGZvciB0aGlzIHN1Ym1pc3Npb24gYmF0Y2hcbiAgICAgICAgcHJlZmVycmVkX3N0YXJ0X2RhdGV0aW1lOiBwcmVmLnByZWZlcnJlZF9zdGFydF9kYXRldGltZSxcbiAgICAgICAgcHJlZmVycmVkX2VuZF9kYXRldGltZTogcHJlZi5wcmVmZXJyZWRfZW5kX2RhdGV0aW1lLFxuICAgICAgICB0b2tlbl9leHBpcmVzX2F0OiBwcmVmZXJlbmNlVG9rZW5FeHBpcmVzQXQsIC8vIFRoaXMgaXMgZm9yIHRoZSBwcmVmZXJlbmNlIHJlY29yZCBpdHNlbGZcbiAgICAgIH0pO1xuICAgIH1cblxuICAgIHJlcy5zdGF0dXMoMjAxKS5qc29uKHsgbWVzc2FnZTogJ1ByZWZlcmVuY2VzIHN1Ym1pdHRlZCBzdWNjZXNzZnVsbHkuJyB9KTtcbiAgfSBjYXRjaCAoZXJyb3IpIHtcbiAgICBjb25zb2xlLmVycm9yKCdFcnJvciBzdWJtaXR0aW5nIGV4dGVybmFsIHByZWZlcmVuY2U6JywgZXJyb3IpO1xuICAgIC8vIFR5cGUgZ3VhcmQgZm9yIGVycm9yXG4gICAgbGV0IGVycm9yTWVzc2FnZSA9ICdBbiB1bmV4cGVjdGVkIGVycm9yIG9jY3VycmVkLic7XG4gICAgaWYgKGVycm9yIGluc3RhbmNlb2YgRXJyb3IpIHtcbiAgICAgIGVycm9yTWVzc2FnZSA9IGVycm9yLm1lc3NhZ2U7XG4gICAgfVxuICAgIHJlc1xuICAgICAgLnN0YXR1cyg1MDApXG4gICAgICAuanNvbih7IG1lc3NhZ2U6ICdGYWlsZWQgdG8gc3VibWl0IHByZWZlcmVuY2VzLicsIGVycm9yOiBlcnJvck1lc3NhZ2UgfSk7XG4gIH1cbn07XG4iXX0=