// Next.js API route support: https://nextjs.org/docs/api-routes/introduction
import {
  cancelMeetingAssist,
  deleteMeetingAssistAttendee,
  getMeetingAssist,
  getMeetingAssistAttendee,
  // googleCalendarSync, // googleCalendarSync is not used in this handler
  updateMeetingAssistAttendanceCount,
  updateMeetingAssistInviteResponse,
  upsertOneMeetingAssistAttendee,
} from '@lib/api-helper';
import {
  MeetingAssistAttendeeType,
  MeetingAssistType,
  HandshakeApiResponse,
  SkillError,
} from '@lib/types'; // Added HandshakeApiResponse and SkillError
import type { NextApiRequest, NextApiResponse } from 'next';

type RequestDataForCancelMeetingAssistType = {
  method: 'cancelMeetingAssist';
  variables: { id: string };
};

type RequestDataForDeleteMeetingAssistAttendeeType = {
  method: 'deleteMeetingAssistAttendee';
  variables: { id: string };
};

type RequestDataForGetMeetingAssistType = {
  method: 'getMeetingAssist';
  variables: { id: string };
};

type RequestDataForGetMeetingAssistAttendeeType = {
  method: 'getMeetingAssistAttendee';
  variables: { id: string };
};

type RequestDataForUpsertMeetingAssistAttendeeType = {
  method: 'upsertOneMeetingAssistAttendee';
  variables: { attendee: MeetingAssistAttendeeType };
};

type RequestDataForUpdateMeetingAssistAttendanceCountType = {
  method: 'updateMeetingAssistAttendanceCount';
  variables: {
    id: string;
    attendeeCount: number;
    attendeeRespondedCount: number;
  };
};

type RequestDataForUpdateMeetingAssistInviteResponseType = {
  method: 'updateMeetingAssistInviteResponse';
  variables: { id: string; response: 'PENDING' | 'ATTENDING' | 'CANCELLED' };
};

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse<
    HandshakeApiResponse<
      MeetingAssistType | MeetingAssistAttendeeType | { message: string }
    >
  >
) {
  try {
    const body = req.body; // Type will be inferred or validated per method

    if (req.method !== 'POST') {
      res.setHeader('Allow', ['POST']);
      return res
        .status(405)
        .json({
          ok: false,
          error: {
            code: 'METHOD_NOT_ALLOWED',
            message: `Method ${req.method} Not Allowed`,
          },
        });
    }

    if (!body || !body.method) {
      return res
        .status(400)
        .json({
          ok: false,
          error: {
            code: 'INVALID_INPUT',
            message: 'Missing method in request body.',
          },
        });
    }

    const { method, variables } = body;

    if (method === 'cancelMeetingAssist') {
      const { id } = variables || {};
      if (!id)
        return res
          .status(400)
          .json({
            ok: false,
            error: {
              code: 'INVALID_INPUT',
              message: 'Missing id for cancelMeetingAssist.',
            },
          });

      const meetingAssistCancelled = await cancelMeetingAssist(id);
      if (meetingAssistCancelled?.id) {
        return res.status(200).json({ ok: true, data: meetingAssistCancelled });
      }
      return res
        .status(404)
        .json({
          ok: false,
          error: {
            code: 'NOT_FOUND',
            message: `MeetingAssist with id ${id} not found or not cancelled.`,
          },
        });
    }

    if (method === 'deleteMeetingAssistAttendee') {
      const { id } = variables || {};
      if (!id)
        return res
          .status(400)
          .json({
            ok: false,
            error: {
              code: 'INVALID_INPUT',
              message: 'Missing id for deleteMeetingAssistAttendee.',
            },
          });

      const deletedMeetingAssistAttendee =
        await deleteMeetingAssistAttendee(id);
      if (deletedMeetingAssistAttendee?.id) {
        return res
          .status(200)
          .json({ ok: true, data: deletedMeetingAssistAttendee });
      }
      return res
        .status(404)
        .json({
          ok: false,
          error: {
            code: 'NOT_FOUND',
            message: `MeetingAssistAttendee with id ${id} not found or not deleted.`,
          },
        });
    }

    if (method === 'getMeetingAssist') {
      const { id } = variables || {};
      if (!id)
        return res
          .status(400)
          .json({
            ok: false,
            error: {
              code: 'INVALID_INPUT',
              message: 'Missing id for getMeetingAssist.',
            },
          });

      const meetingAssist = await getMeetingAssist(id);
      if (meetingAssist?.id) {
        return res.status(200).json({ ok: true, data: meetingAssist });
      }
      return res
        .status(404)
        .json({
          ok: false,
          error: {
            code: 'NOT_FOUND',
            message: `MeetingAssist with id ${id} not found.`,
          },
        });
    }

    if (method === 'getMeetingAssistAttendee') {
      const { id } = variables || {};
      if (!id)
        return res
          .status(400)
          .json({
            ok: false,
            error: {
              code: 'INVALID_INPUT',
              message: 'Missing id for getMeetingAssistAttendee.',
            },
          });

      const meetingAssistAttendee = await getMeetingAssistAttendee(id);
      if (meetingAssistAttendee?.id) {
        // Check if attendee was found
        return res.status(200).json({ ok: true, data: meetingAssistAttendee });
      }
      return res
        .status(404)
        .json({
          ok: false,
          error: {
            code: 'NOT_FOUND',
            message: `MeetingAssistAttendee with id ${id} not found.`,
          },
        });
    }

    if (method === 'upsertOneMeetingAssistAttendee') {
      const { attendee } = variables || {};
      if (!attendee)
        return res
          .status(400)
          .json({
            ok: false,
            error: {
              code: 'INVALID_INPUT',
              message:
                'Missing attendee data for upsertOneMeetingAssistAttendee.',
            },
          });

      const meetingAssistAttendee =
        await upsertOneMeetingAssistAttendee(attendee);
      if (meetingAssistAttendee?.id) {
        return res.status(200).json({ ok: true, data: meetingAssistAttendee });
      }
      // Upsert might not easily indicate "not found" if it creates. If it fails, it's an API_HELPER_ERROR.
      return res
        .status(500)
        .json({
          ok: false,
          error: {
            code: 'API_HELPER_ERROR',
            message: 'Failed to upsert MeetingAssistAttendee.',
          },
        });
    }

    if (method === 'updateMeetingAssistAttendanceCount') {
      const { id, attendeeCount, attendeeRespondedCount } = variables || {};
      if (
        !id ||
        typeof attendeeCount !== 'number' ||
        typeof attendeeRespondedCount !== 'number'
      ) {
        return res
          .status(400)
          .json({
            ok: false,
            error: {
              code: 'INVALID_INPUT',
              message:
                'Missing or invalid parameters for updateMeetingAssistAttendanceCount.',
            },
          });
      }

      const meetingAssistUpdatedCount =
        await updateMeetingAssistAttendanceCount(
          id,
          attendeeCount,
          attendeeRespondedCount
        );
      if (meetingAssistUpdatedCount?.id) {
        return res
          .status(200)
          .json({ ok: true, data: meetingAssistUpdatedCount });
      }
      return res
        .status(404)
        .json({
          ok: false,
          error: {
            code: 'NOT_FOUND',
            message: `MeetingAssist with id ${id} not found for update count.`,
          },
        });
    }

    if (method === 'updateMeetingAssistInviteResponse') {
      const { id, response } = variables || {};
      if (!id || !response) {
        return res
          .status(400)
          .json({
            ok: false,
            error: {
              code: 'INVALID_INPUT',
              message:
                'Missing id or response for updateMeetingAssistInviteResponse.',
            },
          });
      }
      // Add validation for response value if necessary
      if (!['PENDING', 'ATTENDING', 'CANCELLED'].includes(response)) {
        return res
          .status(400)
          .json({
            ok: false,
            error: {
              code: 'INVALID_INPUT',
              message:
                'Invalid response value for updateMeetingAssistInviteResponse.',
            },
          });
      }

      await updateMeetingAssistInviteResponse(id, response); // This function in api-helper might need to return success/failure
      return res
        .status(200)
        .json({
          ok: true,
          data: {
            message: `Invite response for ${id} updated to ${response}.`,
          },
        });
    }

    // If no method matched
    return res
      .status(400)
      .json({
        ok: false,
        error: {
          code: 'METHOD_NOT_SUPPORTED',
          message: `Method '${method}' is not supported or body is malformed.`,
        },
      });
  } catch (e: any) {
    console.error('Critical error in external-attendee handler:', e);
    // Ensure a response is sent even for unexpected errors
    return res
      .status(500)
      .json({
        ok: false,
        error: {
          code: 'INTERNAL_SERVER_ERROR',
          message: e.message || 'An unexpected critical error occurred.',
          details: e.toString(),
        },
      });
  }
}
