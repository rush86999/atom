"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.default = handler;
// Next.js API route support: https://nextjs.org/docs/api-routes/introduction
const api_helper_1 = require("@lib/api-helper");
async function handler(req, res) {
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
            const meetingAssistCancelled = await (0, api_helper_1.cancelMeetingAssist)(id);
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
            const deletedMeetingAssistAttendee = await (0, api_helper_1.deleteMeetingAssistAttendee)(id);
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
            const meetingAssist = await (0, api_helper_1.getMeetingAssist)(id);
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
            const meetingAssistAttendee = await (0, api_helper_1.getMeetingAssistAttendee)(id);
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
                        message: 'Missing attendee data for upsertOneMeetingAssistAttendee.',
                    },
                });
            const meetingAssistAttendee = await (0, api_helper_1.upsertOneMeetingAssistAttendee)(attendee);
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
            if (!id ||
                typeof attendeeCount !== 'number' ||
                typeof attendeeRespondedCount !== 'number') {
                return res
                    .status(400)
                    .json({
                    ok: false,
                    error: {
                        code: 'INVALID_INPUT',
                        message: 'Missing or invalid parameters for updateMeetingAssistAttendanceCount.',
                    },
                });
            }
            const meetingAssistUpdatedCount = await (0, api_helper_1.updateMeetingAssistAttendanceCount)(id, attendeeCount, attendeeRespondedCount);
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
                        message: 'Missing id or response for updateMeetingAssistInviteResponse.',
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
                        message: 'Invalid response value for updateMeetingAssistInviteResponse.',
                    },
                });
            }
            await (0, api_helper_1.updateMeetingAssistInviteResponse)(id, response); // This function in api-helper might need to return success/failure
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
    }
    catch (e) {
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
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiZXh0ZXJuYWwtYXR0ZW5kZWUuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJleHRlcm5hbC1hdHRlbmRlZS50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOztBQTBEQSwwQkFpU0M7QUEzVkQsNkVBQTZFO0FBQzdFLGdEQVN5QjtBQWdEVixLQUFLLFVBQVUsT0FBTyxDQUNuQyxHQUFtQixFQUNuQixHQUlDO0lBRUQsSUFBSSxDQUFDO1FBQ0gsTUFBTSxJQUFJLEdBQUcsR0FBRyxDQUFDLElBQUksQ0FBQyxDQUFDLGdEQUFnRDtRQUV2RSxJQUFJLEdBQUcsQ0FBQyxNQUFNLEtBQUssTUFBTSxFQUFFLENBQUM7WUFDMUIsR0FBRyxDQUFDLFNBQVMsQ0FBQyxPQUFPLEVBQUUsQ0FBQyxNQUFNLENBQUMsQ0FBQyxDQUFDO1lBQ2pDLE9BQU8sR0FBRztpQkFDUCxNQUFNLENBQUMsR0FBRyxDQUFDO2lCQUNYLElBQUksQ0FBQztnQkFDSixFQUFFLEVBQUUsS0FBSztnQkFDVCxLQUFLLEVBQUU7b0JBQ0wsSUFBSSxFQUFFLG9CQUFvQjtvQkFDMUIsT0FBTyxFQUFFLFVBQVUsR0FBRyxDQUFDLE1BQU0sY0FBYztpQkFDNUM7YUFDRixDQUFDLENBQUM7UUFDUCxDQUFDO1FBRUQsSUFBSSxDQUFDLElBQUksSUFBSSxDQUFDLElBQUksQ0FBQyxNQUFNLEVBQUUsQ0FBQztZQUMxQixPQUFPLEdBQUc7aUJBQ1AsTUFBTSxDQUFDLEdBQUcsQ0FBQztpQkFDWCxJQUFJLENBQUM7Z0JBQ0osRUFBRSxFQUFFLEtBQUs7Z0JBQ1QsS0FBSyxFQUFFO29CQUNMLElBQUksRUFBRSxlQUFlO29CQUNyQixPQUFPLEVBQUUsaUNBQWlDO2lCQUMzQzthQUNGLENBQUMsQ0FBQztRQUNQLENBQUM7UUFFRCxNQUFNLEVBQUUsTUFBTSxFQUFFLFNBQVMsRUFBRSxHQUFHLElBQUksQ0FBQztRQUVuQyxJQUFJLE1BQU0sS0FBSyxxQkFBcUIsRUFBRSxDQUFDO1lBQ3JDLE1BQU0sRUFBRSxF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d0NBQXdDO2dCQUM5RCxPQUFPLEVBQUUsQ0FBQyxDQUFDLFFBQVEsRUFBRTthQUN0QjtTQUNGLENBQUMsQ0FBQztJQUNQLENBQUM7QUFDSCxDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiLy8gTmV4dC5qcyBBUEkgcm91dGUgc3VwcG9ydDogaHR0cHM6Ly9uZXh0anMub3JnL2RvY3MvYXBpLXJvdXRlcy9pbnRyb2R1Y3Rpb25cbmltcG9ydCB7XG4gIGNhbmNlbE1lZXRpbmdBc3Npc3QsXG4gIGRlbGV0ZU1lZXRpbmdBc3Npc3RBdHRlbmRlZSxcbiAgZ2V0TWVldGluZ0Fzc2lzdCxcbiAgZ2V0TWVldGluZ0Fzc2lzdEF0dGVuZGVlLFxuICAvLyBnb29nbGVDYWxlbmRhclN5bmMsIC8vIGdvb2dsZUNhbGVuZGFyU3luYyBpcyBub3QgdXNlZCBpbiB0aGlzIGhhbmRsZXJcbiAgdXBkYXRlTWVldGluZ0Fzc2lzdEF0dGVuZGFuY2VDb3VudCxcbiAgdXBkYXRlTWVldGluZ0Fzc2lzdEludml0ZVJlc3BvbnNlLFxuICB1cHNlcnRPbmVNZWV0aW5nQXNzaXN0QXR0ZW5kZWUsXG59IGZyb20gJ0BsaWIvYXBpLWhlbHBlcic7XG5pbXBvcnQge1xuICBNZWV0aW5nQXNzaXN0QXR0ZW5kZWVUeXBlLFxuICBNZWV0aW5nQXNzaXN0VHlwZSxcbiAgSGFuZHNoYWtlQXBpUmVzcG9uc2UsXG4gIFNraWxsRXJyb3IsXG59IGZyb20gJ0BsaWIvdHlwZXMnOyAvLyBBZGRlZCBIYW5kc2hha2VBcGlSZXNwb25zZSBhbmQgU2tpbGxFcnJvclxuaW1wb3J0IHR5cGUgeyBOZXh0QXBpUmVxdWVzdCwgTmV4dEFwaVJlc3BvbnNlIH0gZnJvbSAnbmV4dCc7XG5cbnR5cGUgUmVxdWVzdERhdGFGb3JDYW5jZWxNZWV0aW5nQXNzaXN0VHlwZSA9IHtcbiAgbWV0aG9kOiAnY2FuY2VsTWVldGluZ0Fzc2lzdCc7XG4gIHZhcmlhYmxlczogeyBpZDogc3RyaW5nIH07XG59O1xuXG50eXBlIFJlcXVlc3REYXRhRm9yRGVsZXRlTWVldGluZ0Fzc2lzdEF0dGVuZGVlVHlwZSA9IHtcbiAgbWV0aG9kOiAnZGVsZXRlTWVldGluZ0Fzc2lzdEF0dGVuZGVlJztcbiAgdmFyaWFibGVzOiB7IGlkOiBzdHJpbmcgfTtcbn07XG5cbnR5cGUgUmVxdWVzdERhdGFGb3JHZXRNZWV0aW5nQXNzaXN0VHlwZSA9IHtcbiAgbWV0aG9kOiAnZ2V0TWVldGluZ0Fzc2lzdCc7XG4gIHZhcmlhYmxlczogeyBpZDogc3RyaW5nIH07XG59O1xuXG50eXBlIFJlcXVlc3REYXRhRm9yR2V0TWVldGluZ0Fzc2lzdEF0dGVuZGVlVHlwZSA9IHtcbiAgbWV0aG9kOiAnZ2V0TWVldGluZ0Fzc2lzdEF0dGVuZGVlJztcbiAgdmFyaWFibGVzOiB7IGlkOiBzdHJpbmcgfTtcbn07XG5cbnR5cGUgUmVxdWVzdERhdGFGb3JVcHNlcnRNZWV0aW5nQXNzaXN0QXR0ZW5kZWVUeXBlID0ge1xuICBtZXRob2Q6ICd1cHNlcnRPbmVNZWV0aW5nQXNzaXN0QXR0ZW5kZWUnO1xuICB2YXJpYWJsZXM6IHsgYXR0ZW5kZWU6IE1lZXRpbmdBc3Npc3RBdHRlbmRlZVR5cGUgfTtcbn07XG5cbnR5cGUgUmVxdWVzdERhdGFGb3JVcGRhdGVNZWV0aW5nQXNzaXN0QXR0ZW5kYW5jZUNvdW50VHlwZSA9IHtcbiAgbWV0aG9kOiAndXBkYXRlTWVldGluZ0Fzc2lzdEF0dGVuZGFuY2VDb3VudCc7XG4gIHZhcmlhYmxlczoge1xuICAgIGlkOiBzdHJpbmc7XG4gICAgYXR0ZW5kZWVDb3VudDogbnVtYmVyO1xuICAgIGF0dGVuZGVlUmVzcG9uZGVkQ291bnQ6IG51bWJlcjtcbiAgfTtcbn07XG5cbnR5cGUgUmVxdWVzdERhdGFGb3JVcGRhdGVNZWV0aW5nQXNzaXN0SW52aXRlUmVzcG9uc2VUeXBlID0ge1xuICBtZXRob2Q6ICd1cGRhdGVNZWV0aW5nQXNzaXN0SW52aXRlUmVzcG9uc2UnO1xuICB2YXJpYWJsZXM6IHsgaWQ6IHN0cmluZzsgcmVzcG9uc2U6ICdQRU5ESU5HJyB8ICdBVFRFTkRJTkcnIHwgJ0NBTkNFTExFRCcgfTtcbn07XG5cbmV4cG9ydCBkZWZhdWx0IGFzeW5jIGZ1bmN0aW9uIGhhbmRsZXIoXG4gIHJlcTogTmV4dEFwaVJlcXVlc3QsXG4gIHJlczogTmV4dEFwaVJlc3BvbnNlPFxuICAgIEhhbmRzaGFrZUFwaVJlc3BvbnNlPFxuICAgICAgTWVldGluZ0Fzc2lzdFR5cGUgfCBNZWV0aW5nQXNzaXN0QXR0ZW5kZWVUeXBlIHwgeyBtZXNzYWdlOiBzdHJpbmcgfVxuICAgID5cbiAgPlxuKSB7XG4gIHRyeSB7XG4gICAgY29uc3QgYm9keSA9IHJlcS5ib2R5OyAvLyBUeXBlIHdpbGwgYmUgaW5mZXJyZWQgb3IgdmFsaWRhdGVkIHBlciBtZXRob2RcblxuICAgIGlmIChyZXEubWV0aG9kICE9PSAnUE9TVCcpIHtcbiAgICAgIHJlcy5zZXRIZWFkZXIoJ0FsbG93JywgWydQT1NUJ10pO1xuICAgICAgcmV0dXJuIHJlc1xuICAgICAgICAuc3RhdHVzKDQwNSlcbiAgICAgICAgLmpzb24oe1xuICAgICAgICAgIG9rOiBmYWxzZSxcbiAgICAgICAgICBlcnJvcjoge1xuICAgICAgICAgICAgY29kZTogJ01FVEhPRF9OT1RfQUxMT1dFRCcsXG4gICAgICAgICAgICBtZXNzYWdlOiBgTWV0aG9kICR7cmVxLm1ldGhvZH0gTm90IEFsbG93ZWRgLFxuICAgICAgICAgIH0sXG4gICAgICAgIH0pO1xuICAgIH1cblxuICAgIGlmICghYm9keSB8fCAhYm9keS5tZXRob2QpIHtcbiAgICAgIHJldHVybiByZXNcbiAgICAgICAgLnN0YXR1cyg0MDApXG4gICAgICAgIC5qc29uKHtcbiAgICAgICAgICBvazogZmFsc2UsXG4gICAgICAgICAgZXJyb3I6IHtcbiAgICAgICAgICAgIGNvZGU6ICdJTlZBTElEX0lOUFVUJyxcbiAgICAgICAgICAgIG1lc3NhZ2U6ICdNaXNzaW5nIG1ldGhvZCBpbiByZXF1ZXN0IGJvZHkuJyxcbiAgICAgICAgICB9LFxuICAgICAgICB9KTtcbiAgICB9XG5cbiAgICBjb25zdCB7IG1ldGhvZCwgdmFyaWFibGVzIH0gPSBib2R5O1xuXG4gICAgaWYgKG1ldGhvZCA9PT0gJ2NhbmNlbE1lZXRpbmdBc3Npc3QnKSB7XG4gICAgICBjb25zdCB7IGlkIH0gPSB2YXJpYWJsZXMgfHwge307XG4gICAgICBpZiAoIWlkKVxuICAgICAgICByZXR1cm4gcmVzXG4gICAgICAgICAgLnN0YXR1cyg0MDApXG4gICAgICAgICAgLmpzb24oe1xuICAgICAgICAgICAgb2s6IGZhbHNlLFxuICAgICAgICAgICAgZXJyb3I6IHtcbiAgICAgICAgICAgICAgY29kZTogJ0lOVkFMSURfSU5QVVQnLFxuICAgICAgICAgICAgICBtZXNzYWdlOiAnTWlzc2luZyBpZCBmb3IgY2FuY2VsTWVldGluZ0Fzc2lzdC4nLFxuICAgICAgICAgICAgfSxcbiAgICAgICAgICB9KTtcblxuICAgICAgY29uc3QgbWVldGluZ0Fzc2lzdENhbmNlbGxlZCA9IGF3YWl0IGNhbmNlbE1lZXRpbmdBc3Npc3QoaWQpO1xuICAgICAgaWYgKG1lZXRpbmdBc3Npc3RDYW5jZWxsZWQ/LmlkKSB7XG4gICAgICAgIHJldHVybiByZXMuc3RhdHVzKDIwMCkuanNvbih7IG9rOiB0cnVlLCBkYXRhOiBtZWV0aW5nQXNzaXN0Q2FuY2VsbGVkIH0pO1xuICAgICAgfVxuICAgICAgcmV0dXJuIHJlc1xuICAgICAgICAuc3RhdHVzKDQwNClcbiAgICAgICAgLmpzb24oe1xuICAgICAgICAgIG9rOiBmYWxzZSxcbiAgICAgICAgICBlcnJvcjoge1xuICAgICAgICAgICAgY29kZTogJ05PVF9GT1VORCcsXG4gICAgICAgICAgICBtZXNzYWdlOiBgTWVldGluZ0Fzc2lzdCB3aXRoIGlkICR7aWR9IG5vdCBmb3VuZCBvciBub3QgY2FuY2VsbGVkLmAsXG4gICAgICAgICAgfSxcbiAgICAgICAgfSk7XG4gICAgfVxuXG4gICAgaWYgKG1ldGhvZCA9PT0gJ2RlbGV0ZU1lZXRpbmdBc3Npc3RBdHRlbmRlZScpIHtcbiAgICAgIGNvbnN0IHsgaWQgfSA9IHZhcmlhYmxlcyB8fCB7fTtcbiAgICAgIGlmICghaWQpXG4gICAgICAgIHJldHVybiByZXNcbiAgICAgICAgICAuc3RhdHVzKDQwMClcbiAgICAgICAgICAuanNvbih7XG4gICAgICAgICAgICBvazogZmFsc2UsXG4gICAgICAgICAgICBlcnJvcjoge1xuICAgICAgICAgICAgICBjb2RlOiAnSU5WQUxJRF9JTlBVVCcsXG4gICAgICAgICAgICAgIG1lc3NhZ2U6ICdNaXNzaW5nIGlkIGZvciBkZWxldGVNZWV0aW5nQXNzaXN0QXR0ZW5kZWUuJyxcbiAgICAgICAgICAgIH0sXG4gICAgICAgICAgfSk7XG5cbiAgICAgIGNvbnN0IGRlbGV0ZWRNZWV0aW5nQXNzaXN0QXR0ZW5kZWUgPVxuICAgICAgICBhd2FpdCBkZWxldGVNZWV0aW5nQXNzaXN0QXR0ZW5kZWUoaWQpO1xuICAgICAgaWYgKGRlbGV0ZWRNZWV0aW5nQXNzaXN0QXR0ZW5kZWU/LmlkKSB7XG4gICAgICAgIHJldHVybiByZXNcbiAgICAgICAgICAuc3RhdHVzKDIwMClcbiAgICAgICAgICAuanNvbih7IG9rOiB0cnVlLCBkYXRhOiBkZWxldGVkTWVldGluZ0Fzc2lzdEF0dGVuZGVlIH0pO1xuICAgICAgfVxuICAgICAgcmV0dXJuIHJlc1xuICAgICAgICAuc3RhdHVzKDQwNClcbiAgICAgICAgLmpzb24oe1xuICAgICAgICAgIG9rOiBmYWxzZSxcbiAgICAgICAgICBlcnJvcjoge1xuICAgICAgICAgICAgY29kZTogJ05PVF9GT1VORCcsXG4gICAgICAgICAgICBtZXNzYWdlOiBgTWVldGluZ0Fzc2lzdEF0dGVuZGVlIHdpdGggaWQgJHtpZH0gbm90IGZvdW5kIG9yIG5vdCBkZWxldGVkLmAsXG4gICAgICAgICAgfSxcbiAgICAgICAgfSk7XG4gICAgfVxuXG4gICAgaWYgKG1ldGhvZCA9PT0gJ2dldE1lZXRpbmdBc3Npc3QnKSB7XG4gICAgICBjb25zdCB7IGlkIH0gPSB2YXJpYWJsZXMgfHwge307XG4gICAgICBpZiAoIWlkKVxuICAgICAgICByZXR1cm4gcmVzXG4gICAgICAgICAgLnN0YXR1cyg0MDApXG4gICAgICAgICAgLmpzb24oe1xuICAgICAgICAgICAgb2s6IGZhbHNlLFxuICAgICAgICAgICAgZXJyb3I6IHtcbiAgICAgICAgICAgICAgY29kZTogJ0lOVkFMSURfSU5QVVQnLFxuICAgICAgICAgICAgICBtZXNzYWdlOiAnTWlzc2luZyBpZCBmb3IgZ2V0TWVldGluZ0Fzc2lzdC4nLFxuICAgICAgICAgICAgfSxcbiAgICAgICAgICB9KTtcblxuICAgICAgY29uc3QgbWVldGluZ0Fzc2lzdCA9IGF3YWl0IGdldE1lZXRpbmdBc3Npc3QoaWQpO1xuICAgICAgaWYgKG1lZXRpbmdBc3Npc3Q/LmlkKSB7XG4gICAgICAgIHJldHVybiByZXMuc3RhdHVzKDIwMCkuanNvbih7IG9rOiB0cnVlLCBkYXRhOiBtZWV0aW5nQXNzaXN0IH0pO1xuICAgICAgfVxuICAgICAgcmV0dXJuIHJlc1xuICAgICAgICAuc3RhdHVzKDQwNClcbiAgICAgICAgLmpzb24oe1xuICAgICAgICAgIG9rOiBmYWxzZSxcbiAgICAgICAgICBlcnJvcjoge1xuICAgICAgICAgICAgY29kZTogJ05PVF9GT1VORCcsXG4gICAgICAgICAgICBtZXNzYWdlOiBgTWVldGluZ0Fzc2lzdCB3aXRoIGlkICR7aWR9IG5vdCBmb3VuZC5gLFxuICAgICAgICAgIH0sXG4gICAgICAgIH0pO1xuICAgIH1cblxuICAgIGlmIChtZXRob2QgPT09ICdnZXRNZWV0aW5nQXNzaXN0QXR0ZW5kZWUnKSB7XG4gICAgICBjb25zdCB7IGlkIH0gPSB2YXJpYWJsZXMgfHwge307XG4gICAgICBpZiAoIWlkKVxuICAgICAgICByZXR1cm4gcmVzXG4gICAgICAgICAgLnN0YXR1cyg0MDApXG4gICAgICAgICAgLmpzb24oe1xuICAgICAgICAgICAgb2s6IGZhbHNlLFxuICAgICAgICAgICAgZXJyb3I6IHtcbiAgICAgICAgICAgICAgY29kZTogJ0lOVkFMSURfSU5QVVQnLFxuICAgICAgICAgICAgICBtZXNzYWdlOiAnTWlzc2luZyBpZCBmb3IgZ2V0TWVldGluZ0Fzc2lzdEF0dGVuZGVlLicsXG4gICAgICAgICAgICB9LFxuICAgICAgICAgIH0pO1xuXG4gICAgICBjb25zdCBtZWV0aW5nQXNzaXN0QXR0ZW5kZWUgPSBhd2FpdCBnZXRNZWV0aW5nQXNzaXN0QXR0ZW5kZWUoaWQpO1xuICAgICAgaWYgKG1lZXRpbmdBc3Npc3RBdHRlbmRlZT8uaWQpIHtcbiAgICAgICAgLy8gQ2hlY2sgaWYgYXR0ZW5kZWUgd2FzIGZvdW5kXG4gICAgICAgIHJldHVybiByZXMuc3RhdHVzKDIwMCkuanNvbih7IG9rOiB0cnVlLCBkYXRhOiBtZWV0aW5nQXNzaXN0QXR0ZW5kZWUgfSk7XG4gICAgICB9XG4gICAgICByZXR1cm4gcmVzXG4gICAgICAgIC5zdGF0dXMoNDA0KVxuICAgICAgICAuanNvbih7XG4gICAgICAgICAgb2s6IGZhbHNlLFxuICAgICAgICAgIGVycm9yOiB7XG4gICAgICAgICAgICBjb2RlOiAnTk9UX0ZPVU5EJyxcbiAgICAgICAgICAgIG1lc3NhZ2U6IGBNZWV0aW5nQXNzaXN0QXR0ZW5kZWUgd2l0aCBpZCAke2lkfSBub3QgZm91bmQuYCxcbiAgICAgICAgICB9LFxuICAgICAgICB9KTtcbiAgICB9XG5cbiAgICBpZiAobWV0aG9kID09PSAndXBzZXJ0T25lTWVldGluZ0Fzc2lzdEF0dGVuZGVlJykge1xuICAgICAgY29uc3QgeyBhdHRlbmRlZSB9ID0gdmFyaWFibGVzIHx8IHt9O1xuICAgICAgaWYgKCFhdHRlbmRlZSlcbiAgICAgICAgcmV0dXJuIHJlc1xuICAgICAgICAgIC5zdGF0dXMoNDAwKVxuICAgICAgICAgIC5qc29uKHtcbiAgICAgICAgICAgIG9rOiBmYWxzZSxcbiAgICAgICAgICAgIGVycm9yOiB7XG4gICAgICAgICAgICAgIGNvZGU6ICdJTlZBTElEX0lOUFVUJyxcbiAgICAgICAgICAgICAgbWVzc2FnZTpcbiAgICAgICAgICAgICAgICAnTWlzc2luZyBhdHRlbmRlZSBkYXRhIGZvciB1cHNlcnRPbmVNZWV0aW5nQXNzaXN0QXR0ZW5kZWUuJyxcbiAgICAgICAgICAgIH0sXG4gICAgICAgICAgfSk7XG5cbiAgICAgIGNvbnN0IG1lZXRpbmdBc3Npc3RBdHRlbmRlZSA9XG4gICAgICAgIGF3YWl0IHVwc2VydE9uZU1lZXRpbmdBc3Npc3RBdHRlbmRlZShhdHRlbmRlZSk7XG4gICAgICBpZiAobWVldGluZ0Fzc2lzdEF0dGVuZGVlPy5pZCkge1xuICAgICAgICByZXR1cm4gcmVzLnN0YXR1cygyMDApLmpzb24oeyBvazogdHJ1ZSwgZGF0YTogbWVldGluZ0Fzc2lzdEF0dGVuZGVlIH0pO1xuICAgICAgfVxuICAgICAgLy8gVXBzZXJ0IG1pZ2h0IG5vdCBlYXNpbHkgaW5kaWNhdGUgXCJub3QgZm91bmRcIiBpZiBpdCBjcmVhdGVzLiBJZiBpdCBmYWlscywgaXQncyBhbiBBUElfSEVMUEVSX0VSUk9SLlxuICAgICAgcmV0dXJuIHJlc1xuICAgICAgICAuc3RhdHVzKDUwMClcbiAgICAgICAgLmpzb24oe1xuICAgICAgICAgIG9rOiBmYWxzZSxcbiAgICAgICAgICBlcnJvcjoge1xuICAgICAgICAgICAgY29kZTogJ0FQSV9IRUxQRVJfRVJST1InLFxuICAgICAgICAgICAgbWVzc2FnZTogJ0ZhaWxlZCB0byB1cHNlcnQgTWVldGluZ0Fzc2lzdEF0dGVuZGVlLicsXG4gICAgICAgICAgfSxcbiAgICAgICAgfSk7XG4gICAgfVxuXG4gICAgaWYgKG1ldGhvZCA9PT0gJ3VwZGF0ZU1lZXRpbmdBc3Npc3RBdHRlbmRhbmNlQ291bnQnKSB7XG4gICAgICBjb25zdCB7IGlkLCBhdHRlbmRlZUNvdW50LCBhdHRlbmRlZVJlc3BvbmRlZENvdW50IH0gPSB2YXJpYWJsZXMgfHwge307XG4gICAgICBpZiAoXG4gICAgICAgICFpZCB8fFxuICAgICAgICB0eXBlb2YgYXR0ZW5kZWVDb3VudCAhPT0gJ251bWJlcicgfHxcbiAgICAgICAgdHlwZW9mIGF0dGVuZGVlUmVzcG9uZGVkQ291bnQgIT09ICdudW1iZXInXG4gICAgICApIHtcbiAgICAgICAgcmV0dXJuIHJlc1xuICAgICAgICAgIC5zdGF0dXMoNDAwKVxuICAgICAgICAgIC5qc29uKHtcbiAgICAgICAgICAgIG9rOiBmYWxzZSxcbiAgICAgICAgICAgIGVycm9yOiB7XG4gICAgICAgICAgICAgIGNvZGU6ICdJTlZBTElEX0lOUFVUJyxcbiAgICAgICAgICAgICAgbWVzc2FnZTpcbiAgICAgICAgICAgICAgICAnTWlzc2luZyBvciBpbnZhbGlkIHBhcmFtZXRlcnMgZm9yIHVwZGF0ZU1lZXRpbmdBc3Npc3RBdHRlbmRhbmNlQ291bnQuJyxcbiAgICAgICAgICAgIH0sXG4gICAgICAgICAgfSk7XG4gICAgICB9XG5cbiAgICAgIGNvbnN0IG1lZXRpbmdBc3Npc3RVcGRhdGVkQ291bnQgPVxuICAgICAgICBhd2FpdCB1cGRhdGVNZWV0aW5nQXNzaXN0QXR0ZW5kYW5jZUNvdW50KFxuICAgICAgICAgIGlkLFxuICAgICAgICAgIGF0dGVuZGVlQ291bnQsXG4gICAgICAgICAgYXR0ZW5kZWVSZXNwb25kZWRDb3VudFxuICAgICAgICApO1xuICAgICAgaWYgKG1lZXRpbmdBc3Npc3RVcGRhdGVkQ291bnQ/LmlkKSB7XG4gICAgICAgIHJldHVybiByZXNcbiAgICAgICAgICAuc3RhdHVzKDIwMClcbiAgICAgICAgICAuanNvbih7IG9rOiB0cnVlLCBkYXRhOiBtZWV0aW5nQXNzaXN0VXBkYXRlZENvdW50IH0pO1xuICAgICAgfVxuICAgICAgcmV0dXJuIHJlc1xuICAgICAgICAuc3RhdHVzKDQwNClcbiAgICAgICAgLmpzb24oe1xuICAgICAgICAgIG9rOiBmYWxzZSxcbiAgICAgICAgICBlcnJvcjoge1xuICAgICAgICAgICAgY29kZTogJ05PVF9GT1VORCcsXG4gICAgICAgICAgICBtZXNzYWdlOiBgTWVldGluZ0Fzc2lzdCB3aXRoIGlkICR7aWR9IG5vdCBmb3VuZCBmb3IgdXBkYXRlIGNvdW50LmAsXG4gICAgICAgICAgfSxcbiAgICAgICAgfSk7XG4gICAgfVxuXG4gICAgaWYgKG1ldGhvZCA9PT0gJ3VwZGF0ZU1lZXRpbmdBc3Npc3RJbnZpdGVSZXNwb25zZScpIHtcbiAgICAgIGNvbnN0IHsgaWQsIHJlc3BvbnNlIH0gPSB2YXJpYWJsZXMgfHwge307XG4gICAgICBpZiAoIWlkIHx8ICFyZXNwb25zZSkge1xuICAgICAgICByZXR1cm4gcmVzXG4gICAgICAgICAgLnN0YXR1cyg0MDApXG4gICAgICAgICAgLmpzb24oe1xuICAgICAgICAgICAgb2s6IGZhbHNlLFxuICAgICAgICAgICAgZXJyb3I6IHtcbiAgICAgICAgICAgICAgY29kZTogJ0lOVkFMSURfSU5QVVQnLFxuICAgICAgICAgICAgICBtZXNzYWdlOlxuICAgICAgICAgICAgICAgICdNaXNzaW5nIGlkIG9yIHJlc3BvbnNlIGZvciB1cGRhdGVNZWV0aW5nQXNzaXN0SW52aXRlUmVzcG9uc2UuJyxcbiAgICAgICAgICAgIH0sXG4gICAgICAgICAgfSk7XG4gICAgICB9XG4gICAgICAvLyBBZGQgdmFsaWRhdGlvbiBmb3IgcmVzcG9uc2UgdmFsdWUgaWYgbmVjZXNzYXJ5XG4gICAgICBpZiAoIVsnUEVORElORycsICdBVFRFTkRJTkcnLCAnQ0FOQ0VMTEVEJ10uaW5jbHVkZXMocmVzcG9uc2UpKSB7XG4gICAgICAgIHJldHVybiByZXNcbiAgICAgICAgICAuc3RhdHVzKDQwMClcbiAgICAgICAgICAuanNvbih7XG4gICAgICAgICAgICBvazogZmFsc2UsXG4gICAgICAgICAgICBlcnJvcjoge1xuICAgICAgICAgICAgICBjb2RlOiAnSU5WQUxJRF9JTlBVVCcsXG4gICAgICAgICAgICAgIG1lc3NhZ2U6XG4gICAgICAgICAgICAgICAgJ0ludmFsaWQgcmVzcG9uc2UgdmFsdWUgZm9yIHVwZGF0ZU1lZXRpbmdBc3Npc3RJbnZpdGVSZXNwb25zZS4nLFxuICAgICAgICAgICAgfSxcbiAgICAgICAgICB9KTtcbiAgICAgIH1cblxuICAgICAgYXdhaXQgdXBkYXRlTWVldGluZ0Fzc2lzdEludml0ZVJlc3BvbnNlKGlkLCByZXNwb25zZSk7IC8vIFRoaXMgZnVuY3Rpb24gaW4gYXBpLWhlbHBlciBtaWdodCBuZWVkIHRvIHJldHVybiBzdWNjZXNzL2ZhaWx1cmVcbiAgICAgIHJldHVybiByZXNcbiAgICAgICAgLnN0YXR1cygyMDApXG4gICAgICAgIC5qc29uKHtcbiAgICAgICAgICBvazogdHJ1ZSxcbiAgICAgICAgICBkYXRhOiB7XG4gICAgICAgICAgICBtZXNzYWdlOiBgSW52aXRlIHJlc3BvbnNlIGZvciAke2lkfSB1cGRhdGVkIHRvICR7cmVzcG9uc2V9LmAsXG4gICAgICAgICAgfSxcbiAgICAgICAgfSk7XG4gICAgfVxuXG4gICAgLy8gSWYgbm8gbWV0aG9kIG1hdGNoZWRcbiAgICByZXR1cm4gcmVzXG4gICAgICAuc3RhdHVzKDQwMClcbiAgICAgIC5qc29uKHtcbiAgICAgICAgb2s6IGZhbHNlLFxuICAgICAgICBlcnJvcjoge1xuICAgICAgICAgIGNvZGU6ICdNRVRIT0RfTk9UX1NVUFBPUlRFRCcsXG4gICAgICAgICAgbWVzc2FnZTogYE1ldGhvZCAnJHttZXRob2R9JyBpcyBub3Qgc3VwcG9ydGVkIG9yIGJvZHkgaXMgbWFsZm9ybWVkLmAsXG4gICAgICAgIH0sXG4gICAgICB9KTtcbiAgfSBjYXRjaCAoZTogYW55KSB7XG4gICAgY29uc29sZS5lcnJvcignQ3JpdGljYWwgZXJyb3IgaW4gZXh0ZXJuYWwtYXR0ZW5kZWUgaGFuZGxlcjonLCBlKTtcbiAgICAvLyBFbnN1cmUgYSByZXNwb25zZSBpcyBzZW50IGV2ZW4gZm9yIHVuZXhwZWN0ZWQgZXJyb3JzXG4gICAgcmV0dXJuIHJlc1xuICAgICAgLnN0YXR1cyg1MDApXG4gICAgICAuanNvbih7XG4gICAgICAgIG9rOiBmYWxzZSxcbiAgICAgICAgZXJyb3I6IHtcbiAgICAgICAgICBjb2RlOiAnSU5URVJOQUxfU0VSVkVSX0VSUk9SJyxcbiAgICAgICAgICBtZXNzYWdlOiBlLm1lc3NhZ2UgfHwgJ0FuIHVuZXhwZWN0ZWQgY3JpdGljYWwgZXJyb3Igb2NjdXJyZWQuJyxcbiAgICAgICAgICBkZXRhaWxzOiBlLnRvU3RyaW5nKCksXG4gICAgICAgIH0sXG4gICAgICB9KTtcbiAgfVxufVxuIl19