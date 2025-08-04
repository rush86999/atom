"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.updateZoomMeeting = exports.deleteZoomMeeting = exports.createZoomMeeting = exports.zoomAvailable = void 0;
const axios_1 = __importDefault(require("axios"));
const constants_1 = require("@lib/zoom/constants");
const getCalendarIntegrationByResourceAndName_1 = __importDefault(require("@lib/apollo/gql/getCalendarIntegrationByResourceAndName"));
const session_1 = __importDefault(require("supertokens-web-js/recipe/session"));
const zoomAvailable = async (client, userId) => {
    try {
        const calIntObject = (await client.query({
            query: getCalendarIntegrationByResourceAndName_1.default,
            variables: {
                userId,
                name: constants_1.zoomName,
                resource: constants_1.zoomResourceName,
            },
        })).data?.Calendar_Integration?.[0];
        if (calIntObject?.enabled) {
            return true;
        }
        return false;
    }
    catch (e) {
        console.log(e, ' unable to get zoom availability');
    }
};
exports.zoomAvailable = zoomAvailable;
const createZoomMeeting = async (userId, startDate, timezone, agenda, duration, contactName, contactEmail, meetingInvitees, privateMeeting) => {
    try {
        if (startDate) {
            throw new Error('no startDate present inside createZoomMeeting');
        }
        if (!timezone) {
            throw new Error('no timezone inside createZoomMeeting');
        }
        if (!agenda) {
            throw new Error('no agenda inside createZoomMeeting');
        }
        if (!duration) {
            throw new Error('no duration inside createZoomMeeting');
        }
        if (!userId) {
            throw new Error('no userId inside createZoomMeeting');
        }
        const accessToken = await session_1.default.getAccessToken();
        const config = {
            headers: {
                Authorization: `Bearer ${accessToken}`,
                'Content-Type': 'application/json',
            },
        };
        const data = {
            startDate,
            timezone,
            agenda,
            duration,
            userId,
            contactName,
            contactEmail,
            meetingInvitees,
            privateMeeting,
        };
        const url = constants_1.zoomCreateMeetingUrl;
        const results = await axios_1.default.post(url, data, config);
        const { data: { join_url, id, start_url, status }, } = results;
        return { id, join_url, start_url, status };
    }
    catch (e) {
        console.log(e, ' unabel to create zoom meeting');
    }
};
exports.createZoomMeeting = createZoomMeeting;
const deleteZoomMeeting = async (userId, meetingId, scheduleForReminder, cancelMeetingReminder) => {
    try {
        if (typeof meetingId !== 'number') {
            console.log('id was not properly parsed to int ');
            return;
        }
        if (!userId) {
            throw new Error('no userId inside deleteZoomMeeting');
        }
        const url = constants_1.zoomDeleteMeetingUrl;
        const accessToken = await session_1.default.getAccessToken();
        const config = {
            headers: {
                Authorization: `Bearer ${accessToken}`,
                'Content-Type': 'application/json',
            },
        };
        const data = {
            meetingId,
            userId,
            scheduleForReminder,
            cancelMeetingReminder,
        };
        const results = await axios_1.default.post(url, data, config);
        console.log(results, ' successfully deleted meeting');
    }
    catch (e) {
        console.log(e, '  unable to delete zoom meeting');
    }
};
exports.deleteZoomMeeting = deleteZoomMeeting;
const updateZoomMeeting = async (userId, meetingId, startDate, timezone, agenda, duration, contactName, contactEmail, meetingInvitees, privateMeeting) => {
    try {
        if (!userId) {
            throw new Error('no userId inside updateZoomMeeting');
        }
        if (typeof meetingId !== 'number') {
            throw new Error('id was not properly parsed to int  inside updateZoomMeeting');
        }
        const url = constants_1.zoomUpdateMeetingUrl;
        const data = {
            userId,
            meetingId,
            startDate,
            timezone,
            agenda,
            duration,
            contactName,
            contactEmail,
            meetingInvitees,
            privateMeeting,
        };
        const accessToken = await session_1.default.getAccessToken();
        const config = {
            headers: {
                Authorization: `Bearer ${accessToken}`,
                'Content-Type': 'application/json',
            },
        };
        const results = await axios_1.default.post(url, data, config);
        const { data: { join_url, id, start_url, status }, } = results;
        return { id, join_url, start_url, status };
    }
    catch (e) {
        console.log(e, ' unable to update zoom meeting');
    }
};
exports.updateZoomMeeting = updateZoomMeeting;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiem9vbU1lZXRpbmdIZWxwZXIuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJ6b29tTWVldGluZ0hlbHBlci50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOzs7Ozs7QUFDQSxrREFBMEI7QUFHMUIsbURBTzZCO0FBUzdCLHNJQUF1RztBQUV2RyxnRkFBd0Q7QUFFakQsTUFBTSxhQUFhLEdBQUcsS0FBSyxFQUNoQyxNQUEyQyxFQUMzQyxNQUFjLEVBQ2QsRUFBRTtJQUNGLElBQUksQ0FBQztRQUNILE1BQU0sWUFBWSxHQUFHLENBQ25CLE1BQU0sTUFBTSxDQUFDLEtBQUssQ0FBc0Q7WUFDdEUsS0FBSyxFQUFFLGlEQUFnQztZQUN2QyxTQUFTLEVBQUU7Z0JBQ1QsTUFBTTtnQkFDTixJQUFJLEVBQUUsb0JBQVE7Z0JBQ2QsUUFBUSxFQUFFLDRCQUFnQjthQUMzQjtTQUNGLENBQUMsQ0FDSCxDQUFDLElBQUksRUFBRSxvQkFBb0IsRUFBRSxDQUFDLENBQUMsQ0FBQyxDQUFDO1FBQ2xDLElBQUksWUFBWSxFQUFFLE9BQU8sRUFBRSxDQUFDO1lBQzFCLE9BQU8sSUFBSSxDQUFDO1FBQ2QsQ0FBQztRQUNELE9BQU8sS0FBSyxDQUFDO0lBQ2YsQ0FBQztJQUFDLE9BQU8sQ0FBQyxFQUFFLENBQUM7UUFDWCxPQUFPLENBQUMsR0FBRyxDQUFDLENBQUMsRUFBRSxrQ0FBa0MsQ0FBQyxDQUFDO0lBQ3JELENBQUM7QUFDSCxDQUFDLENBQUM7QUF0QlcsUUFBQSxhQUFhLGlCQXNCeEI7QUFFSyxNQUFNLGlCQUFpQixHQUFHLEtBQUssRUFDcEMsTUFBYyxFQUNkLFNBQWlCLEVBQ2pCLFFBQWdCLEVBQ2hCLE1BQWMsRUFDZCxRQUFnQixFQUNoQixXQUFvQixFQUNwQixZQUFxQixFQUNyQixlQUEwQixFQUMxQixjQUF3QixFQUN4QixFQUFFO0lBQ0YsSUFBSSxDQUFDO1FBQ0gsSUFBSSxTQUFTLEVBQUUsQ0FBQztZQUNkLE1BQU0sSUFBSSxLQUFLLENBQUMsK0NBQStD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T0FBTyxDQUFDO1FBRVosT0FBTyxFQUFFLEVBQUUsRUFBRSxRQUFRLEVBQUUsU0FBUyxFQUFFLE1BQU0sRUFBRSxDQUFDO0lBQzdDLENBQUM7SUFBQyxPQUFPLENBQUMsRUFBRSxDQUFDO1FBQ1gsT0FBTyxDQUFDLEdBQUcsQ0FBQyxDQUFDLEVBQUUsZ0NBQWdDLENBQUMsQ0FBQztJQUNuRCxDQUFDO0FBQ0gsQ0FBQyxDQUFDO0FBN0RXLFFBQUEsaUJBQWlCLHFCQTZENUIiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgeyBMaW5raW5nIH0gZnJvbSAncmVhY3QtbmF0aXZlJztcbmltcG9ydCBheGlvcyBmcm9tICdheGlvcyc7XG5pbXBvcnQgcXMgZnJvbSAncXMnO1xuXG5pbXBvcnQge1xuICB6b29tTmFtZSxcbiAgem9vbVJlc291cmNlTmFtZSxcbiAgem9vbUNyZWF0ZU1lZXRpbmdVcmwsXG4gIHpvb21VcGRhdGVNZWV0aW5nVXJsLFxuICB6b29tRGVsZXRlTWVldGluZ1VybCxcbiAgem9vbU9BdXRoU3RhcnRVcmwsXG59IGZyb20gJ0BsaWIvem9vbS9jb25zdGFudHMnO1xuaW1wb3J0IHtcbiAgQ3JlYXRlTWVldGluZ1Jlc3BvbnNlVHlwZSxcbiAgQ3JlYXRlWm9vbU1lZXRPYmplY3RUeXBlLFxuICBVcGRhdGVab29tTWVldE9iamVjdFR5cGUsXG4gIERlbGV0ZVpvb21NZWV0T2JqZWN0VHlwZSxcbn0gZnJvbSAnQGxpYi96b29tL3R5cGVzJztcblxuaW1wb3J0IHsgQXBvbGxvQ2xpZW50LCBOb3JtYWxpemVkQ2FjaGVPYmplY3QgfSBmcm9tICdAYXBvbGxvL2NsaWVudCc7XG5pbXBvcnQgZ2V0Q2FsZW5kYXJJbnRlZ3JhdGlvbkJ5UmVzb3VyY2UgZnJvbSAnQGxpYi9hcG9sbG8vZ3FsL2dldENhbGVuZGFySW50ZWdyYXRpb25CeVJlc291cmNlQW5kTmFtZSc7XG5pbXBvcnQgeyBDYWxlbmRhckludGVncmF0aW9uVHlwZSB9IGZyb20gJ0BsaWIvZGF0YVR5cGVzL0NhbGVuZGFyX0ludGVncmF0aW9uVHlwZSc7XG5pbXBvcnQgU2Vzc2lvbiBmcm9tICdzdXBlcnRva2Vucy13ZWItanMvcmVjaXBlL3Nlc3Npb24nO1xuXG5leHBvcnQgY29uc3Qgem9vbUF2YWlsYWJsZSA9IGFzeW5jIChcbiAgY2xpZW50OiBBcG9sbG9DbGllbnQ8Tm9ybWFsaXplZENhY2hlT2JqZWN0PixcbiAgdXNlcklkOiBzdHJpbmdcbikgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IGNhbEludE9iamVjdCA9IChcbiAgICAgIGF3YWl0IGNsaWVudC5xdWVyeTx7IENhbGVuZGFyX0ludGVncmF0aW9uOiBDYWxlbmRhckludGVncmF0aW9uVHlwZVtdIH0+KHtcbiAgICAgICAgcXVlcnk6IGdldENhbGVuZGFySW50ZWdyYXRpb25CeVJlc291cmNlLFxuICAgICAgICB2YXJpYWJsZXM6IHtcbiAgICAgICAgICB1c2VySWQsXG4gICAgICAgICAgbmFtZTogem9vbU5hbWUsXG4gICAgICAgICAgcmVzb3VyY2U6IHpvb21SZXNvdXJjZU5hbWUsXG4gICAgICAgIH0sXG4gICAgICB9KVxuICAgICkuZGF0YT8uQ2FsZW5kYXJfSW50ZWdyYXRpb24/LlswXTtcbiAgICBpZiAoY2FsSW50T2JqZWN0Py5lbmFibGVkKSB7XG4gICAgICByZXR1cm4gdHJ1ZTtcbiAgICB9XG4gICAgcmV0dXJuIGZhbHNlO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gZ2V0IHpvb20gYXZhaWxhYmlsaXR5Jyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBjcmVhdGVab29tTWVldGluZyA9IGFzeW5jIChcbiAgdXNlcklkOiBzdHJpbmcsXG4gIHN0YXJ0RGF0ZTogc3RyaW5nLFxuICB0aW1lem9uZTogc3RyaW5nLFxuICBhZ2VuZGE6IHN0cmluZyxcbiAgZHVyYXRpb246IG51bWJlcixcbiAgY29udGFjdE5hbWU/OiBzdHJpbmcsXG4gIGNvbnRhY3RFbWFpbD86IHN0cmluZyxcbiAgbWVldGluZ0ludml0ZWVzPzogc3RyaW5nW10sXG4gIHByaXZhdGVNZWV0aW5nPzogYm9vbGVhblxuKSA9PiB7XG4gIHRyeSB7XG4gICAgaWYgKHN0YXJ0RGF0ZSkge1xuICAgICAgdGhyb3cgbmV3IEVycm9yKCdubyBzdGFydERhdGUgcHJlc2VudCBpbnNpZGUgY3JlYXRlWm9vbU1lZXRpbmcnKTtcbiAgICB9XG5cbiAgICBpZiAoIXRpbWV6b25lKSB7XG4gICAgICB0aHJvdyBuZXcgRXJyb3IoJ25vIHRpbWV6b25lIGluc2lkZSBjcmVhdGVab29tTWVldGluZycpO1xuICAgIH1cblxuICAgIGlmICghYWdlbmRhKSB7XG4gICAgICB0aHJvdyBuZXcgRXJyb3IoJ25vIGFnZW5kYSBpbnNpZGUgY3JlYXRlWm9vbU1lZXRpbmcnKTtcbiAgICB9XG5cbiAgICBpZiAoIWR1cmF0aW9uKSB7XG4gICAgICB0aHJvdyBuZXcgRXJyb3IoJ25vIGR1cmF0aW9uIGluc2lkZSBjcmVhdGVab29tTWVldGluZycpO1xuICAgIH1cblxuICAgIGlmICghdXNlcklkKSB7XG4gICAgICB0aHJvdyBuZXcgRXJyb3IoJ25vIHVzZXJJZCBpbnNpZGUgY3JlYXRlWm9vbU1lZXRpbmcnKTtcbiAgICB9XG5cbiAgICBjb25zdCBhY2Nlc3NUb2tlbiA9IGF3YWl0IFNlc3Npb24uZ2V0QWNjZXNzVG9rZW4oKTtcblxuICAgIGNvbnN0IGNvbmZpZyA9IHtcbiAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgQXV0aG9yaXphdGlvbjogYEJlYXJlciAke2FjY2Vzc1Rva2VufWAsXG4gICAgICAgICdDb250ZW50LVR5cGUnOiAnYXBwbGljYXRpb24vanNvbicsXG4gICAgICB9LFxuICAgIH07XG5cbiAgICBjb25zdCBkYXRhOiBDcmVhdGVab29tTWVldE9iamVjdFR5cGUgPSB7XG4gICAgICBzdGFydERhdGUsXG4gICAgICB0aW1lem9uZSxcbiAgICAgIGFnZW5kYSxcbiAgICAgIGR1cmF0aW9uLFxuICAgICAgdXNlcklkLFxuICAgICAgY29udGFjdE5hbWUsXG4gICAgICBjb250YWN0RW1haWwsXG4gICAgICBtZWV0aW5nSW52aXRlZXMsXG4gICAgICBwcml2YXRlTWVldGluZyxcbiAgICB9O1xuXG4gICAgY29uc3QgdXJsID0gem9vbUNyZWF0ZU1lZXRpbmdVcmw7XG5cbiAgICBjb25zdCByZXN1bHRzID0gYXdhaXQgYXhpb3MucG9zdDxDcmVhdGVNZWV0aW5nUmVzcG9uc2VUeXBlPihcbiAgICAgIHVybCxcbiAgICAgIGRhdGEsXG4gICAgICBjb25maWdcbiAgICApO1xuXG4gICAgY29uc3Qge1xuICAgICAgZGF0YTogeyBqb2luX3VybCwgaWQsIHN0YXJ0X3VybCwgc3RhdHVzIH0sXG4gICAgfSA9IHJlc3VsdHM7XG5cbiAgICByZXR1cm4geyBpZCwgam9pbl91cmwsIHN0YXJ0X3VybCwgc3RhdHVzIH07XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJlbCB0byBjcmVhdGUgem9vbSBtZWV0aW5nJyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBkZWxldGVab29tTWVldGluZyA9IGFzeW5jIChcbiAgdXNlcklkOiBzdHJpbmcsXG4gIG1lZXRpbmdJZDogbnVtYmVyLFxuICBzY2hlZHVsZUZvclJlbWluZGVyPzogYm9vbGVhbixcbiAgY2FuY2VsTWVldGluZ1JlbWluZGVyPzogc3RyaW5nXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBpZiAodHlwZW9mIG1lZXRpbmdJZCAhPT0gJ251bWJlcicpIHtcbiAgICAgIGNvbnNvbGUubG9nKCdpZCB3YXMgbm90IHByb3Blcmx5IHBhcnNlZCB0byBpbnQgJyk7XG4gICAgICByZXR1cm47XG4gICAgfVxuXG4gICAgaWYgKCF1c2VySWQpIHtcbiAgICAgIHRocm93IG5ldyBFcnJvcignbm8gdXNlcklkIGluc2lkZSBkZWxldGVab29tTWVldGluZycpO1xuICAgIH1cblxuICAgIGNvbnN0IHVybCA9IHpvb21EZWxldGVNZWV0aW5nVXJsO1xuXG4gICAgY29uc3QgYWNjZXNzVG9rZW4gPSBhd2FpdCBTZXNzaW9uLmdldEFjY2Vzc1Rva2VuKCk7XG5cbiAgICBjb25zdCBjb25maWcgPSB7XG4gICAgICBoZWFkZXJzOiB7XG4gICAgICAgIEF1dGhvcml6YXRpb246IGBCZWFyZXIgJHthY2Nlc3NUb2tlbn1gLFxuICAgICAgICAnQ29udGVudC1UeXBlJzogJ2FwcGxpY2F0aW9uL2pzb24nLFxuICAgICAgfSxcbiAgICB9O1xuXG4gICAgY29uc3QgZGF0YTogRGVsZXRlWm9vbU1lZXRPYmplY3RUeXBlID0ge1xuICAgICAgbWVldGluZ0lkLFxuICAgICAgdXNlcklkLFxuICAgICAgc2NoZWR1bGVGb3JSZW1pbmRlcixcbiAgICAgIGNhbmNlbE1lZXRpbmdSZW1pbmRlcixcbiAgICB9O1xuXG4gICAgY29uc3QgcmVzdWx0cyA9IGF3YWl0IGF4aW9zLnBvc3QodXJsLCBkYXRhLCBjb25maWcpO1xuICAgIGNvbnNvbGUubG9nKHJlc3VsdHMsICcgc3VjY2Vzc2Z1bGx5IGRlbGV0ZWQgbWVldGluZycpO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyAgdW5hYmxlIHRvIGRlbGV0ZSB6b29tIG1lZXRpbmcnKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IHVwZGF0ZVpvb21NZWV0aW5nID0gYXN5bmMgKFxuICB1c2VySWQ6IHN0cmluZyxcbiAgbWVldGluZ0lkOiBudW1iZXIsXG4gIHN0YXJ0RGF0ZT86IHN0cmluZyxcbiAgdGltZXpvbmU/OiBzdHJpbmcsXG4gIGFnZW5kYT86IHN0cmluZyxcbiAgZHVyYXRpb24/OiBudW1iZXIsXG4gIGNvbnRhY3ROYW1lPzogc3RyaW5nLFxuICBjb250YWN0RW1haWw/OiBzdHJpbmcsXG4gIG1lZXRpbmdJbnZpdGVlcz86IHN0cmluZ1tdLFxuICBwcml2YXRlTWVldGluZz86IGJvb2xlYW5cbikgPT4ge1xuICB0cnkge1xuICAgIGlmICghdXNlcklkKSB7XG4gICAgICB0aHJvdyBuZXcgRXJyb3IoJ25vIHVzZXJJZCBpbnNpZGUgdXBkYXRlWm9vbU1lZXRpbmcnKTtcbiAgICB9XG5cbiAgICBpZiAodHlwZW9mIG1lZXRpbmdJZCAhPT0gJ251bWJlcicpIHtcbiAgICAgIHRocm93IG5ldyBFcnJvcihcbiAgICAgICAgJ2lkIHdhcyBub3QgcHJvcGVybHkgcGFyc2VkIHRvIGludCAgaW5zaWRlIHVwZGF0ZVpvb21NZWV0aW5nJ1xuICAgICAgKTtcbiAgICB9XG5cbiAgICBjb25zdCB1cmwgPSB6b29tVXBkYXRlTWVldGluZ1VybDtcblxuICAgIGNvbnN0IGRhdGE6IFVwZGF0ZVpvb21NZWV0T2JqZWN0VHlwZSA9IHtcbiAgICAgIHVzZXJJZCxcbiAgICAgIG1lZXRpbmdJZCxcbiAgICAgIHN0YXJ0RGF0ZSxcbiAgICAgIHRpbWV6b25lLFxuICAgICAgYWdlbmRhLFxuICAgICAgZHVyYXRpb24sXG4gICAgICBjb250YWN0TmFtZSxcbiAgICAgIGNvbnRhY3RFbWFpbCxcbiAgICAgIG1lZXRpbmdJbnZpdGVlcyxcbiAgICAgIHByaXZhdGVNZWV0aW5nLFxuICAgIH07XG5cbiAgICBjb25zdCBhY2Nlc3NUb2tlbiA9IGF3YWl0IFNlc3Npb24uZ2V0QWNjZXNzVG9rZW4oKTtcblxuICAgIGNvbnN0IGNvbmZpZyA9IHtcbiAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgQXV0aG9yaXphdGlvbjogYEJlYXJlciAke2FjY2Vzc1Rva2VufWAsXG4gICAgICAgICdDb250ZW50LVR5cGUnOiAnYXBwbGljYXRpb24vanNvbicsXG4gICAgICB9LFxuICAgIH07XG5cbiAgICBjb25zdCByZXN1bHRzID0gYXdhaXQgYXhpb3MucG9zdDxDcmVhdGVNZWV0aW5nUmVzcG9uc2VUeXBlPihcbiAgICAgIHVybCxcbiAgICAgIGRhdGEsXG4gICAgICBjb25maWdcbiAgICApO1xuXG4gICAgY29uc3Qge1xuICAgICAgZGF0YTogeyBqb2luX3VybCwgaWQsIHN0YXJ0X3VybCwgc3RhdHVzIH0sXG4gICAgfSA9IHJlc3VsdHM7XG5cbiAgICByZXR1cm4geyBpZCwgam9pbl91cmwsIHN0YXJ0X3VybCwgc3RhdHVzIH07XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byB1cGRhdGUgem9vbSBtZWV0aW5nJyk7XG4gIH1cbn07XG4iXX0=