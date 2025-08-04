import got from 'got';
import dayjs from 'dayjs';
import isoWeek from 'dayjs/plugin/isoWeek';
import duration from 'dayjs/plugin/duration';
import isBetween from 'dayjs/plugin/isBetween';
import timezone from 'dayjs/plugin/timezone';
import utc from 'dayjs/plugin/utc';
import { hasuraAdminSecret, hasuraGraphUrl, zoomBaseTokenUrl, zoomBaseUrl, zoomClientId, zoomClientSecret, zoomIVForPass, zoomPassKey, zoomResourceName, zoomSaltForPass, } from './constants';
import qs from 'qs';
import axios from 'axios';
import crypto from 'crypto';
dayjs.extend(isoWeek);
dayjs.extend(duration);
dayjs.extend(isBetween);
dayjs.extend(timezone);
dayjs.extend(utc);
// update zoom meeting
export const updateZoomMeetingStartDate = async (zoomToken, meetingId, startDate, timezone) => {
    try {
        const reqBody = {
            start_time: dayjs(startDate?.slice(0, 19)).format('YYYY-MM-DDTHH:mm:ss'),
            timezone,
        };
        await got
            .patch(`${zoomBaseUrl}/meetings/${meetingId}`, {
            json: reqBody,
            headers: {
                Authorization: `Bearer ${zoomToken}`,
                ContentType: 'application/json',
            },
        })
            .json();
        console.log(meetingId, 'successfully patched zoom meeting starting date');
    }
    catch (e) {
        console.log(e, ' unable to update zoom meeting');
    }
};
export const updateZoomMeeting = async (zoomToken, meetingId, startDate, timezone, agenda, duration, contactName, contactEmail, meetingInvitees, privateMeeting) => {
    try {
        //valdiate
        if (startDate && dayjs().isAfter(dayjs(startDate))) {
            console.log(' starttime is in the past');
            throw new Error('starttime is in the past');
        }
        let settings = {};
        if (privateMeeting) {
            settings = { ...settings, private_meeting: privateMeeting };
        }
        if (contactName?.length > 0 && contactEmail?.length > 0) {
            settings = {
                contact_name: contactName,
                contact_email: contactEmail,
            };
        }
        if (meetingInvitees?.length > 0) {
            settings = { ...settings, meeting_invitees: meetingInvitees };
        }
        let reqBody = {};
        if (Object.keys(settings)?.length > 0) {
            reqBody.settings = settings;
        }
        if (startDate && timezone) {
            reqBody.start_time = dayjs(startDate?.slice(0, 19)).format('YYYY-MM-DDTHH:mm:ss');
            reqBody.timezone = timezone;
        }
        if (agenda) {
            reqBody.agenda = agenda;
        }
        if (duration) {
            reqBody.duration = duration;
        }
        await got
            .patch(`${zoomBaseUrl}/meetings/${meetingId}`, {
            json: reqBody,
            headers: {
                Authorization: `Bearer ${zoomToken}`,
                ContentType: 'application/json',
            },
        })
            .json();
        console.log(meetingId, 'successfully patched zoom meeting starting date');
    }
    catch (e) {
        console.log(e, ' unable to update zoom meeting');
    }
};
export const createZoomMeeting = async (zoomToken, startDate, timezone, agenda, duration, contactName, contactEmail, meetingInvitees, privateMeeting) => {
    try {
        //valdiate
        if (dayjs().isAfter(dayjs(startDate))) {
            console.log(' starttime is in the past');
            throw new Error('starttime is in the past');
        }
        console.log(dayjs(startDate?.slice(0, 19))
            .tz(timezone, true)
            .format('YYYY-MM-DDTHH:mm:ss'), timezone, agenda, duration, ` dayjs(startDate?.slice(0, 19)).tz(timezone, true).format('YYYY-MM-DDTHH:mm:ss'),
            timezone,
            agenda,
            duration, createZoomMeeting called`);
        let settings = {};
        if (contactName?.length > 0 && contactEmail?.length > 0) {
            settings = {
                contact_name: contactName,
                contact_email: contactEmail,
            };
        }
        if (meetingInvitees?.length > 0) {
            settings = {
                ...settings,
                meeting_invitees: meetingInvitees?.map((m) => ({ email: m })),
            };
        }
        if (privateMeeting) {
            settings.private_meeting = true;
        }
        let reqBody = {};
        if (Object.keys(settings)?.length > 0) {
            reqBody.settings = settings;
        }
        reqBody = {
            ...reqBody,
            start_time: dayjs(startDate?.slice(0, 19))
                .tz(timezone, true)
                .utc()
                .format(),
            // timezone,
            agenda,
            duration,
        };
        console.log(reqBody, ' reqBody inside createZoomMeeting');
        const res = await got
            .post(`${zoomBaseUrl}/users/me/meetings`, {
            json: reqBody,
            headers: {
                Authorization: `Bearer ${zoomToken}`,
                ContentType: 'application/json',
            },
        })
            .json();
        console.log(res, ' res inside createZoomMeeting');
        return res;
    }
    catch (e) {
        console.log(e, ' unable to create zoom meeting');
    }
};
export const getZoomMeeting = async (zoomToken, meetingId) => {
    try {
        const res = await got(`${zoomBaseUrl}/meetings/${meetingId}`, {
            headers: {
                Authorization: `Bearer ${zoomToken}`,
                ContentType: 'application/json',
            },
        }).json();
        return res;
    }
    catch (e) {
        console.log(e, ' unable to get zoom meeting');
    }
};
export const deleteZoomMeeting = async (zoomToken, meetingId, scheduleForReminder, cancelMeetingReminder) => {
    try {
        let params = {};
        if (cancelMeetingReminder || scheduleForReminder) {
            if (cancelMeetingReminder) {
                params = { cancel_meeting_reminder: cancelMeetingReminder };
            }
            if (scheduleForReminder) {
                params = { ...params, schedule_for_reminder: scheduleForReminder };
            }
        }
        const stringifiedObject = Object.keys(params)?.length > 0 ? qs.stringify(params) : '';
        if (stringifiedObject) {
            await got.delete(`${zoomBaseUrl}/meetings/` + meetingId + '?' + stringifiedObject, {
                headers: {
                    Authorization: `Bearer ${zoomToken}`,
                    ContentType: 'application/json',
                },
            });
        }
        else {
            await got.delete(`${zoomBaseUrl}/meetings/` + meetingId, {
                headers: {
                    Authorization: `Bearer ${zoomToken}`,
                    ContentType: 'application/json',
                },
            });
        }
        console.log(meetingId, 'successfully deleted meeting');
    }
    catch (e) {
        console.log(e, ' unable to delete zoom meeting');
    }
};
export const refreshZoomToken = async (refreshToken) => {
    try {
        const username = zoomClientId;
        const password = zoomClientSecret;
        return axios({
            data: new URLSearchParams({
                refresh_token: refreshToken,
                grant_type: 'refresh_token',
            }).toString(),
            baseURL: zoomBaseTokenUrl,
            url: '/oauth/token',
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            auth: {
                username,
                password,
            },
        }).then(({ data }) => Promise.resolve(data));
    }
    catch (e) {
        console.log(e, ' unable to refresh zoom token');
    }
};
export const getCalendarIntegration = async (userId, resource) => {
    try {
        const operationName = 'getCalendarIntegration';
        const query = `
      query getCalendarIntegration($userId: uuid!, $resource: String!) {
        Calendar_Integration(where: {userId: {_eq: $userId}, resource: {_eq: $resource}}) {
          token
          expiresAt
          id
          refreshToken
          resource
          name
          clientType
        }
      }
    `;
        const variables = {
            userId,
            resource,
        };
        const res = await got
            .post(hasuraGraphUrl, {
            json: {
                operationName,
                query,
                variables,
            },
            headers: {
                'X-Hasura-Admin-Secret': hasuraAdminSecret,
                'Content-Type': 'application/json',
                'X-Hasura-Role': 'admin',
            },
        })
            .json();
        console.log(res, ' res inside getCalendarIntegration');
        if (res?.data?.Calendar_Integration?.length > 0) {
            return res?.data?.Calendar_Integration?.[0];
        }
    }
    catch (e) {
        console.log(e, ' unable to get calendar integration');
    }
};
export const updateCalendarIntegration = async (id, token, expiresIn, enabled) => {
    try {
        const operationName = 'updateCalendarIntegration';
        const query = `
      mutation updateCalendarIntegration($id: uuid!,${token !== undefined ? ' $token: String,' : ''}${expiresIn !== undefined ? ' $expiresAt: timestamptz,' : ''}${enabled !== undefined ? ' $enabled: Boolean,' : ''}) {
        update_Calendar_Integration_by_pk(pk_columns: {id: $id}, _set: {${token !== undefined ? 'token: $token,' : ''}${expiresIn !== undefined ? ' expiresAt: $expiresAt,' : ''}${enabled !== undefined ? ' enabled: $enabled,' : ''}}) {
          id
          name
          refreshToken
          token
          clientType
          userId
          updatedAt
        }
      }
    `;
        const variables = {
            id,
            token,
            expiresAt: dayjs().add(expiresIn, 'seconds').toISOString(),
            enabled,
        };
        const res = await got
            .post(hasuraGraphUrl, {
            json: {
                operationName,
                query,
                variables,
            },
            headers: {
                'X-Hasura-Admin-Secret': hasuraAdminSecret,
                'Content-Type': 'application/json',
                'X-Hasura-Role': 'admin',
            },
        })
            .json();
        console.log(res, ' res inside updateCalendarIntegration');
    }
    catch (e) {
        console.log(e, ' unable to update calendar integration');
    }
};
export const decryptZoomTokens = (encryptedToken, encryptedRefreshToken) => {
    const ivBuffer = Buffer.from(zoomIVForPass, 'base64');
    const saltBuffer = Buffer.from(zoomSaltForPass, 'base64');
    const key = crypto.pbkdf2Sync(zoomPassKey, saltBuffer, 10000, 32, 'sha256');
    const decipherToken = crypto.createDecipheriv('aes-256-cbc', key, ivBuffer);
    let decryptedToken = decipherToken.update(encryptedToken, 'base64', 'utf8');
    decryptedToken += decipherToken.final('utf8');
    if (encryptedRefreshToken) {
        const decipherRefreshToken = crypto.createDecipheriv('aes-256-cbc', key, ivBuffer);
        let decryptedRefreshToken = decipherRefreshToken.update(encryptedRefreshToken, 'base64', 'utf8');
        decryptedRefreshToken += decipherRefreshToken.final('utf8');
        return {
            token: decryptedToken,
            refreshToken: decryptedRefreshToken,
        };
    }
    return {
        token: decryptedToken,
    };
};
export const encryptZoomTokens = (token, refreshToken) => {
    const ivBuffer = Buffer.from(zoomIVForPass, 'base64');
    const saltBuffer = Buffer.from(zoomSaltForPass, 'base64');
    const key = crypto.pbkdf2Sync(zoomPassKey, saltBuffer, 10000, 32, 'sha256');
    const cipherToken = crypto.createCipheriv('aes-256-cbc', key, ivBuffer);
    let encryptedToken = cipherToken.update(token, 'utf8', 'base64');
    encryptedToken += cipherToken.final('base64');
    let encryptedRefreshToken = '';
    if (refreshToken) {
        const cipherRefreshToken = crypto.createCipheriv('aes-256-cbc', key, ivBuffer);
        encryptedRefreshToken = cipherRefreshToken.update(refreshToken, 'utf8', 'base64');
        encryptedRefreshToken += cipherRefreshToken.final('base64');
    }
    if (encryptedRefreshToken) {
        return {
            encryptedToken,
            encryptedRefreshToken,
        };
    }
    else {
        return { encryptedToken };
    }
};
export const getZoomIntegration = async (userId) => {
    try {
        const { id, token, expiresAt, refreshToken } = await getCalendarIntegration(userId, zoomResourceName);
        const decryptedTokens = decryptZoomTokens(token, refreshToken);
        return {
            id,
            expiresAt,
            ...decryptedTokens,
        };
    }
    catch (e) {
        console.log(e, ' unable to get zoom integration');
    }
};
export const updateZoomIntegration = async (id, accessToken, expiresIn) => {
    try {
        const { encryptedToken } = encryptZoomTokens(accessToken);
        await updateCalendarIntegration(id, encryptedToken, expiresIn);
    }
    catch (e) {
        console.log(e, ' unable to update zoom integration');
    }
};
export const getZoomAPIToken = async (userId) => {
    let integrationId = '';
    try {
        console.log('getZoomAPIToken called');
        const { id, token, expiresAt, refreshToken } = await getZoomIntegration(userId);
        integrationId = id;
        console.log(id, token, expiresAt, refreshToken, ' id, token, expiresAt, refreshToken');
        if (dayjs().isAfter(dayjs(expiresAt)) || !token) {
            const res = await refreshZoomToken(refreshToken);
            console.log(res, ' res from refreshZoomToken');
            await updateZoomIntegration(id, res.access_token, res.expires_in);
            return res.access_token;
        }
        return token;
    }
    catch (e) {
        console.log(e, ' unable to get zoom api token');
        await updateCalendarIntegration(integrationId, null, null, false);
    }
};
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiYXBpLWhlbHBlci5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImFwaS1oZWxwZXIudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6IkFBQUEsT0FBTyxHQUFHLE1BQU0sS0FBSyxDQUFDO0FBQ3RCLE9BQU8sS0FBSyxNQUFNLE9BQU8sQ0FBQztBQUMxQixPQUFPLE9BQU8sTUFBTSxzQkFBc0IsQ0FBQztBQUMzQyxPQUFPLFFBQVEsTUFBTSx1QkFBdUIsQ0FBQztBQUM3QyxPQUFPLFNBQVMsTUFBTSx3QkFBd0IsQ0FBQztBQUMvQyxPQUFPLFFBQVEsTUFBTSx1QkFBdUIsQ0FBQztBQUM3QyxPQUFPLEdBQUcsTUFBTSxrQkFBa0IsQ0FBQztBQUNuQyxPQUFPLEVBQ0wsaUJBQWlCLEVBQ2pCLGNBQWMsRUFDZCxnQkFBZ0IsRUFDaEIsV0FBVyxFQUNYLFlBQVksRUFDWixnQkFBZ0IsRUFDaEIsYUFBYSxFQUNiLFdBQVcsRUFDWCxnQkFBZ0IsRUFDaEIsZUFBZSxHQUNoQixNQUFNLGFBQWEsQ0FBQztBQU9yQixPQUFPLEVBQUUsTUFBTSxJQUFJLENBQUM7QUFDcEIsT0FBTyxLQUFLLE1BQU0sT0FBTyxDQUFDO0FBQzFCLE9BQU8sTUFBTSxNQUFNLFFBQVEsQ0FBQztBQUU1QixLQUFLLENBQUMsTUFBTSxDQUFDLE9BQU8sQ0FBQyxDQUFDO0FBQ3RCLEtBQUssQ0FBQyxNQUFNLENBQUMsUUFBUSxDQUFDLENBQUM7QUFDdkIsS0FBSyxDQUFDLE1BQU0sQ0FBQyxTQUFTLENBQUMsQ0FBQztBQUN4QixLQUFLLENBQUMsTUFBTSxDQUFDLFFBQVEsQ0FBQyxDQUFDO0FBQ3ZCLEtBQUssQ0FBQyxNQUFNLENBQUMsR0FBRyxDQUFDLENBQUM7QUFFbEIsc0JBQXNCO0FBQ3RCLE1BQU0sQ0FBQyxNQUFNLDBCQUEwQixHQUFHLEtBQUssRUFDN0MsU0FBaUIsRUFDakIsU0FBaUIsRUFDakIsU0FBaUIsRUFDakIsUUFBZ0IsRUFDaEIsRUFBRTtJQUNGLElBQUksQ0FBQztRQUNI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aEQsTUFBTSxHQUFHLEdBQUcsTUFBTSxnQkFBZ0IsQ0FBQyxZQUFZLENBQUMsQ0FBQztZQUNqRCxPQUFPLENBQUMsR0FBRyxDQUFDLEdBQUcsRUFBRSw0QkFBNEIsQ0FBQyxDQUFDO1lBQy9DLE1BQU0scUJBQXFCLENBQUMsRUFBRSxFQUFFLEdBQUcsQ0FBQyxZQUFZLEVBQUUsR0FBRyxDQUFDLFVBQVUsQ0FBQyxDQUFDO1lBQ2xFLE9BQU8sR0FBRyxDQUFDLFlBQVksQ0FBQztRQUMxQixDQUFDO1FBRUQsT0FBTyxLQUFLLENBQUM7SUFDZixDQUFDO0lBQUMsT0FBTyxDQUFDLEVBQUUsQ0FBQztRQUNYLE9BQU8sQ0FBQyxHQUFHLENBQUMsQ0FBQyxFQUFFLCtCQUErQixDQUFDLENBQUM7UUFDaEQsTUFBTSx5QkFBeUIsQ0FBQyxhQUFhLEVBQUUsSUFBSSxFQUFFLElBQUksRUFBRSxLQUFLLENBQUMsQ0FBQztJQUNwRSxDQUFDO0FBQ0gsQ0FBQyxDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IGdvdCBmcm9tICdnb3QnO1xuaW1wb3J0IGRheWpzIGZyb20gJ2RheWpzJztcbmltcG9ydCBpc29XZWVrIGZyb20gJ2RheWpzL3BsdWdpbi9pc29XZWVrJztcbmltcG9ydCBkdXJhdGlvbiBmcm9tICdkYXlqcy9wbHVnaW4vZHVyYXRpb24nO1xuaW1wb3J0IGlzQmV0d2VlbiBmcm9tICdkYXlqcy9wbHVnaW4vaXNCZXR3ZWVuJztcbmltcG9ydCB0aW1lem9uZSBmcm9tICdkYXlqcy9wbHVnaW4vdGltZXpvbmUnO1xuaW1wb3J0IHV0YyBmcm9tICdkYXlqcy9wbHVnaW4vdXRjJztcbmltcG9ydCB7XG4gIGhhc3VyYUFkbWluU2VjcmV0LFxuICBoYXN1cmFHcmFwaFVybCxcbiAgem9vbUJhc2VUb2tlblVybCxcbiAgem9vbUJhc2VVcmwsXG4gIHpvb21DbGllbnRJZCxcbiAgem9vbUNsaWVudFNlY3JldCxcbiAgem9vbUlWRm9yUGFzcyxcbiAgem9vbVBhc3NLZXksXG4gIHpvb21SZXNvdXJjZU5hbWUsXG4gIHpvb21TYWx0Rm9yUGFzcyxcbn0gZnJvbSAnLi9jb25zdGFudHMnO1xuaW1wb3J0IHtcbiAgQ2FsZW5kYXJJbnRlZ3JhdGlvblR5cGUsXG4gIENyZWF0ZU1lZXRpbmdSZXNwb25zZVR5cGUsXG4gIENyZWF0ZVpvb21NZWV0aW5nUmVxdWVzdEJvZHlUeXBlLFxuICBab29tTWVldGluZ09iamVjdFR5cGUsXG59IGZyb20gJy4vdHlwZXMnO1xuaW1wb3J0IHFzIGZyb20gJ3FzJztcbmltcG9ydCBheGlvcyBmcm9tICdheGlvcyc7XG5pbXBvcnQgY3J5cHRvIGZyb20gJ2NyeXB0byc7XG5cbmRheWpzLmV4dGVuZChpc29XZWVrKTtcbmRheWpzLmV4dGVuZChkdXJhdGlvbik7XG5kYXlqcy5leHRlbmQoaXNCZXR3ZWVuKTtcbmRheWpzLmV4dGVuZCh0aW1lem9uZSk7XG5kYXlqcy5leHRlbmQodXRjKTtcblxuLy8gdXBkYXRlIHpvb20gbWVldGluZ1xuZXhwb3J0IGNvbnN0IHVwZGF0ZVpvb21NZWV0aW5nU3RhcnREYXRlID0gYXN5bmMgKFxuICB6b29tVG9rZW46IHN0cmluZyxcbiAgbWVldGluZ0lkOiBudW1iZXIsXG4gIHN0YXJ0RGF0ZTogc3RyaW5nLFxuICB0aW1lem9uZTogc3RyaW5nXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCByZXFCb2R5ID0ge1xuICAgICAgc3RhcnRfdGltZTogZGF5anMoc3RhcnREYXRlPy5zbGljZSgwLCAxOSkpLmZvcm1hdCgnWVlZWS1NTS1ERFRISDptbTpzcycpLFxuICAgICAgdGltZXpvbmUsXG4gICAgfTtcblxuICAgIGF3YWl0IGdvdFxuICAgICAgLnBhdGNoKGAke3pvb21CYXNlVXJsfS9tZWV0aW5ncy8ke21lZXRpbmdJZH1gLCB7XG4gICAgICAgIGpzb246IHJlcUJvZHksXG4gICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICBBdXRob3JpemF0aW9uOiBgQmVhcmVyICR7em9vbVRva2VufWAsXG4gICAgICAgICAgQ29udGVudFR5cGU6ICdhcHBsaWNhdGlvbi9qc29uJyxcbiAgICAgICAgfSxcbiAgICAgIH0pXG4gICAgICAuanNvbigpO1xuXG4gICAgY29uc29sZS5sb2cobWVldGluZ0lkLCAnc3VjY2Vzc2Z1bGx5IHBhdGNoZWQgem9vbSBtZWV0aW5nIHN0YXJ0aW5nIGRhdGUnKTtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIHVwZGF0ZSB6b29tIG1lZXRpbmcnKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IHVwZGF0ZVpvb21NZWV0aW5nID0gYXN5bmMgKFxuICB6b29tVG9rZW46IHN0cmluZyxcbiAgbWVldGluZ0lkOiBudW1iZXIsXG4gIHN0YXJ0RGF0ZT86IHN0cmluZyxcbiAgdGltZXpvbmU/OiBzdHJpbmcsXG4gIGFnZW5kYT86IHN0cmluZyxcbiAgZHVyYXRpb24/OiBudW1iZXIsXG4gIGNvbnRhY3ROYW1lPzogc3RyaW5nLFxuICBjb250YWN0RW1haWw/OiBzdHJpbmcsXG4gIG1lZXRpbmdJbnZpdGVlcz86IHN0cmluZ1tdLFxuICBwcml2YXRlTWVldGluZz86IGJvb2xlYW5cbikgPT4ge1xuICB0cnkge1xuICAgIC8vdmFsZGlhdGVcbiAgICBpZiAoc3RhcnREYXRlICYmIGRheWpzKCkuaXNBZnRlcihkYXlqcyhzdGFydERhdGUpKSkge1xuICAgICAgY29uc29sZS5sb2coJyBzdGFydHRpbWUgaXMgaW4gdGhlIHBhc3QnKTtcbiAgICAgIHRocm93IG5ldyBFcnJvcignc3RhcnR0aW1lIGlzIGluIHRoZSBwYXN0Jyk7XG4gICAgfVxuXG4gICAgbGV0IHNldHRpbmdzOiBhbnkgPSB7fTtcblxuICAgIGlmIChwcml2YXRlTWVldGluZykge1xuICAgICAgc2V0dGluZ3MgPSB7IC4uLnNldHRpbmdzLCBwcml2YXRlX21lZXRpbmc6IHByaXZhdGVNZWV0aW5nIH07XG4gICAgfVxuXG4gICAgaWYgKGNvbnRhY3ROYW1lPy5sZW5ndGggPiAwICYmIGNvbnRhY3RFbWFpbD8ubGVuZ3RoID4gMCkge1xuICAgICAgc2V0dGluZ3MgPSB7XG4gICAgICAgIGNvbnRhY3RfbmFtZTogY29udGFjdE5hbWUsXG4gICAgICAgIGNvbnRhY3RfZW1haWw6IGNvbnRhY3RFbWFpbCxcbiAgICAgIH07XG4gICAgfVxuXG4gICAgaWYgKG1lZXRpbmdJbnZpdGVlcz8ubGVuZ3RoID4gMCkge1xuICAgICAgc2V0dGluZ3MgPSB7IC4uLnNldHRpbmdzLCBtZWV0aW5nX2ludml0ZWVzOiBtZWV0aW5nSW52aXRlZXMgfTtcbiAgICB9XG5cbiAgICBsZXQgcmVxQm9keTogYW55ID0ge307XG5cbiAgICBpZiAoT2JqZWN0LmtleXMoc2V0dGluZ3MpPy5sZW5ndGggPiAwKSB7XG4gICAgICByZXFCb2R5LnNldHRpbmdzID0gc2V0dGluZ3M7XG4gICAgfVxuXG4gICAgaWYgKHN0YXJ0RGF0ZSAmJiB0aW1lem9uZSkge1xuICAgICAgcmVxQm9keS5zdGFydF90aW1lID0gZGF5anMoc3RhcnREYXRlPy5zbGljZSgwLCAxOSkpLmZvcm1hdChcbiAgICAgICAgJ1lZWVktTU0tRERUSEg6bW06c3MnXG4gICAgICApO1xuICAgICAgcmVxQm9keS50aW1lem9uZSA9IHRpbWV6b25lO1xuICAgIH1cblxuICAgIGlmIChhZ2VuZGEpIHtcbiAgICAgIHJlcUJvZHkuYWdlbmRhID0gYWdlbmRhO1xuICAgIH1cblxuICAgIGlmIChkdXJhdGlvbikge1xuICAgICAgcmVxQm9keS5kdXJhdGlvbiA9IGR1cmF0aW9uO1xuICAgIH1cblxuICAgIGF3YWl0IGdvdFxuICAgICAgLnBhdGNoKGAke3pvb21CYXNlVXJsfS9tZWV0aW5ncy8ke21lZXRpbmdJZH1gLCB7XG4gICAgICAgIGpzb246IHJlcUJvZHksXG4gICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICBBdXRob3JpemF0aW9uOiBgQmVhcmVyICR7em9vbVRva2VufWAsXG4gICAgICAgICAgQ29udGVudFR5cGU6ICdhcHBsaWNhdGlvbi9qc29uJyxcbiAgICAgICAgfSxcbiAgICAgIH0pXG4gICAgICAuanNvbigpO1xuXG4gICAgY29uc29sZS5sb2cobWVldGluZ0lkLCAnc3VjY2Vzc2Z1bGx5IHBhdGNoZWQgem9vbSBtZWV0aW5nIHN0YXJ0aW5nIGRhdGUnKTtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIHVwZGF0ZSB6b29tIG1lZXRpbmcnKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IGNyZWF0ZVpvb21NZWV0aW5nID0gYXN5bmMgKFxuICB6b29tVG9rZW46IHN0cmluZyxcbiAgc3RhcnREYXRlOiBzdHJpbmcsXG4gIHRpbWV6b25lOiBzdHJpbmcsXG4gIGFnZW5kYTogc3RyaW5nLFxuICBkdXJhdGlvbjogbnVtYmVyLFxuICBjb250YWN0TmFtZT86IHN0cmluZyxcbiAgY29udGFjdEVtYWlsPzogc3RyaW5nLFxuICBtZWV0aW5nSW52aXRlZXM/OiBzdHJpbmdbXSxcbiAgcHJpdmF0ZU1lZXRpbmc/OiBib29sZWFuXG4pID0+IHtcbiAgdHJ5IHtcbiAgICAvL3ZhbGRpYXRlXG4gICAgaWYgKGRheWpzKCkuaXNBZnRlcihkYXlqcyhzdGFydERhdGUpKSkge1xuICAgICAgY29uc29sZS5sb2coJyBzdGFydHRpbWUgaXMgaW4gdGhlIHBhc3QnKTtcbiAgICAgIHRocm93IG5ldyBFcnJvcignc3RhcnR0aW1lIGlzIGluIHRoZSBwYXN0Jyk7XG4gICAgfVxuXG4gICAgY29uc29sZS5sb2coXG4gICAgICBkYXlqcyhzdGFydERhdGU/LnNsaWNlKDAsIDE5KSlcbiAgICAgICAgLnR6KHRpbWV6b25lLCB0cnVlKVxuICAgICAgICAuZm9ybWF0KCdZWVlZLU1NLUREVEhIOm1tOnNzJyksXG4gICAgICB0aW1lem9uZSxcbiAgICAgIGFnZW5kYSxcbiAgICAgIGR1cmF0aW9uLFxuICAgICAgYCBkYXlqcyhzdGFydERhdGU/LnNsaWNlKDAsIDE5KSkudHoodGltZXpvbmUsIHRydWUpLmZvcm1hdCgnWVlZWS1NTS1ERFRISDptbTpzcycpLFxuICAgICAgICAgICAgdGltZXpvbmUsXG4gICAgICAgICAgICBhZ2VuZGEsXG4gICAgICAgICAgICBkdXJhdGlvbiwgY3JlYXRlWm9vbU1lZXRpbmcgY2FsbGVkYFxuICAgICk7XG5cbiAgICBsZXQgc2V0dGluZ3M6IGFueSA9IHt9O1xuXG4gICAgaWYgKGNvbnRhY3ROYW1lPy5sZW5ndGggPiAwICYmIGNvbnRhY3RFbWFpbD8ubGVuZ3RoID4gMCkge1xuICAgICAgc2V0dGluZ3MgPSB7XG4gICAgICAgIGNvbnRhY3RfbmFtZTogY29udGFjdE5hbWUsXG4gICAgICAgIGNvbnRhY3RfZW1haWw6IGNvbnRhY3RFbWFpbCxcbiAgICAgIH07XG4gICAgfVxuXG4gICAgaWYgKG1lZXRpbmdJbnZpdGVlcz8ubGVuZ3RoID4gMCkge1xuICAgICAgc2V0dGluZ3MgPSB7XG4gICAgICAgIC4uLnNldHRpbmdzLFxuICAgICAgICBtZWV0aW5nX2ludml0ZWVzOiBtZWV0aW5nSW52aXRlZXM/Lm1hcCgobSkgPT4gKHsgZW1haWw6IG0gfSkpLFxuICAgICAgfTtcbiAgICB9XG5cbiAgICBpZiAocHJpdmF0ZU1lZXRpbmcpIHtcbiAgICAgIHNldHRpbmdzLnByaXZhdGVfbWVldGluZyA9IHRydWU7XG4gICAgfVxuXG4gICAgbGV0IHJlcUJvZHk6IENyZWF0ZVpvb21NZWV0aW5nUmVxdWVzdEJvZHlUeXBlID0ge307XG5cbiAgICBpZiAoT2JqZWN0LmtleXMoc2V0dGluZ3MpPy5sZW5ndGggPiAwKSB7XG4gICAgICByZXFCb2R5LnNldHRpbmdzID0gc2V0dGluZ3M7XG4gICAgfVxuXG4gICAgcmVxQm9keSA9IHtcbiAgICAgIC4uLnJlcUJvZHksXG4gICAgICBzdGFydF90aW1lOiBkYXlqcyhzdGFydERhdGU/LnNsaWNlKDAsIDE5KSlcbiAgICAgICAgLnR6KHRpbWV6b25lLCB0cnVlKVxuICAgICAgICAudXRjKClcbiAgICAgICAgLmZvcm1hdCgpLFxuICAgICAgLy8gdGltZXpvbmUsXG4gICAgICBhZ2VuZGEsXG4gICAgICBkdXJhdGlvbixcbiAgICB9O1xuXG4gICAgY29uc29sZS5sb2cocmVxQm9keSwgJyByZXFCb2R5IGluc2lkZSBjcmVhdGVab29tTWVldGluZycpO1xuXG4gICAgY29uc3QgcmVzOiBab29tTWVldGluZ09iamVjdFR5cGUgPSBhd2FpdCBnb3RcbiAgICAgIC5wb3N0KGAke3pvb21CYXNlVXJsfS91c2Vycy9tZS9tZWV0aW5nc2AsIHtcbiAgICAgICAganNvbjogcmVxQm9keSxcbiAgICAgICAgaGVhZGVyczoge1xuICAgICAgICAgIEF1dGhvcml6YXRpb246IGBCZWFyZXIgJHt6b29tVG9rZW59YCxcbiAgICAgICAgICBDb250ZW50VHlwZTogJ2FwcGxpY2F0aW9uL2pzb24nLFxuICAgICAgICB9LFxuICAgICAgfSlcbiAgICAgIC5qc29uKCk7XG5cbiAgICBjb25zb2xlLmxvZyhyZXMsICcgcmVzIGluc2lkZSBjcmVhdGVab29tTWVldGluZycpO1xuXG4gICAgcmV0dXJuIHJlcztcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIGNyZWF0ZSB6b29tIG1lZXRpbmcnKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IGdldFpvb21NZWV0aW5nID0gYXN5bmMgKHpvb21Ub2tlbjogc3RyaW5nLCBtZWV0aW5nSWQ6IG51bWJlcikgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IHJlczogQ3JlYXRlTWVldGluZ1Jlc3BvbnNlVHlwZSA9IGF3YWl0IGdvdChcbiAgICAgIGAke3pvb21CYXNlVXJsfS9tZWV0aW5ncy8ke21lZXRpbmdJZH1gLFxuICAgICAge1xuICAgICAgICBoZWFkZXJzOiB7XG4gICAgICAgICAgQXV0aG9yaXphdGlvbjogYEJlYXJlciAke3pvb21Ub2tlbn1gLFxuICAgICAgICAgIENvbnRlbnRUeXBlOiAnYXBwbGljYXRpb24vanNvbicsXG4gICAgICAgIH0sXG4gICAgICB9XG4gICAgKS5qc29uKCk7XG5cbiAgICByZXR1cm4gcmVzO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gZ2V0IHpvb20gbWVldGluZycpO1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgZGVsZXRlWm9vbU1lZXRpbmcgPSBhc3luYyAoXG4gIHpvb21Ub2tlbjogc3RyaW5nLFxuICBtZWV0aW5nSWQ6IG51bWJlcixcbiAgc2NoZWR1bGVGb3JSZW1pbmRlcj86IGJvb2xlYW4sXG4gIGNhbmNlbE1lZXRpbmdSZW1pbmRlcj86IGJvb2xlYW5cbikgPT4ge1xuICB0cnkge1xuICAgIGxldCBwYXJhbXM6IGFueSA9IHt9O1xuICAgIGlmIChjYW5jZWxNZWV0aW5nUmVtaW5kZXIgfHwgc2NoZWR1bGVGb3JSZW1pbmRlcikge1xuICAgICAgaWYgKGNhbmNlbE1lZXRpbmdSZW1pbmRlcikge1xuICAgICAgICBwYXJhbXMgPSB7IGNhbmNlbF9tZWV0aW5nX3JlbWluZGVyOiBjYW5jZWxNZWV0aW5nUmVtaW5kZXIgfTtcbiAgICAgIH1cblxuICAgICAgaWYgKHNjaGVkdWxlRm9yUmVtaW5kZXIpIHtcbiAgICAgICAgcGFyYW1zID0geyAuLi5wYXJhbXMsIHNjaGVkdWxlX2Zvcl9yZW1pbmRlcjogc2NoZWR1bGVGb3JSZW1pbmRlciB9O1xuICAgICAgfVxuICAgIH1cblxuICAgIGNvbnN0IHN0cmluZ2lmaWVkT2JqZWN0ID1cbiAgICAgIE9iamVjdC5rZXlzKHBhcmFtcyk/Lmxlbmd0aCA+IDAgPyBxcy5zdHJpbmdpZnkocGFyYW1zKSA6ICcnO1xuXG4gICAgaWYgKHN0cmluZ2lmaWVkT2JqZWN0KSB7XG4gICAgICBhd2FpdCBnb3QuZGVsZXRlKFxuICAgICAgICBgJHt6b29tQmFzZVVybH0vbWVldGluZ3MvYCArIG1lZXRpbmdJZCArICc/JyArIHN0cmluZ2lmaWVkT2JqZWN0LFxuICAgICAgICB7XG4gICAgICAgICAgaGVhZGVyczoge1xuICAgICAgICAgICAgQXV0aG9yaXphdGlvbjogYEJlYXJlciAke3pvb21Ub2tlbn1gLFxuICAgICAgICAgICAgQ29udGVudFR5cGU6ICdhcHBsaWNhdGlvbi9qc29uJyxcbiAgICAgICAgICB9LFxuICAgICAgICB9XG4gICAgICApO1xuICAgIH0gZWxzZSB7XG4gICAgICBhd2FpdCBnb3QuZGVsZXRlKGAke3pvb21CYXNlVXJsfS9tZWV0aW5ncy9gICsgbWVldGluZ0lkLCB7XG4gICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICBBdXRob3JpemF0aW9uOiBgQmVhcmVyICR7em9vbVRva2VufWAsXG4gICAgICAgICAgQ29udGVudFR5cGU6ICdhcHBsaWNhdGlvbi9qc29uJyxcbiAgICAgICAgfSxcbiAgICAgIH0pO1xuICAgIH1cblxuICAgIGNvbnNvbGUubG9nKG1lZXRpbmdJZCwgJ3N1Y2Nlc3NmdWxseSBkZWxldGVkIG1lZXRpbmcnKTtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIGRlbGV0ZSB6b29tIG1lZXRpbmcnKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IHJlZnJlc2hab29tVG9rZW4gPSBhc3luYyAoXG4gIHJlZnJlc2hUb2tlbjogc3RyaW5nXG4pOiBQcm9taXNlPHtcbiAgYWNjZXNzX3Rva2VuOiBzdHJpbmc7XG4gIHRva2VuX3R5cGU6ICdiZWFyZXInO1xuICByZWZyZXNoX3Rva2VuOiBzdHJpbmc7XG4gIGV4cGlyZXNfaW46IG51bWJlcjtcbiAgc2NvcGU6IHN0cmluZztcbn0+ID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCB1c2VybmFtZSA9IHpvb21DbGllbnRJZDtcbiAgICBjb25zdCBwYXNzd29yZCA9IHpvb21DbGllbnRTZWNyZXQ7XG5cbiAgICByZXR1cm4gYXhpb3Moe1xuICAgICAgZGF0YTogbmV3IFVSTFNlYXJjaFBhcmFtcyh7XG4gICAgICAgIHJlZnJlc2hfdG9rZW46IHJlZnJlc2hUb2tlbixcbiAgICAgICAgZ3JhbnRfdHlwZTogJ3JlZnJlc2hfdG9rZW4nLFxuICAgICAgfSkudG9TdHJpbmcoKSxcbiAgICAgIGJhc2VVUkw6IHpvb21CYXNlVG9rZW5VcmwsXG4gICAgICB1cmw6ICcvb2F1dGgvdG9rZW4nLFxuICAgICAgbWV0aG9kOiAnUE9TVCcsXG4gICAgICBoZWFkZXJzOiB7XG4gICAgICAgICdDb250ZW50LVR5cGUnOiAnYXBwbGljYXRpb24veC13d3ctZm9ybS11cmxlbmNvZGVkJyxcbiAgICAgIH0sXG4gICAgICBhdXRoOiB7XG4gICAgICAgIHVzZXJuYW1lLFxuICAgICAgICBwYXNzd29yZCxcbiAgICAgIH0sXG4gICAgfSkudGhlbigoeyBkYXRhIH0pID0+IFByb21pc2UucmVzb2x2ZShkYXRhKSk7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byByZWZyZXNoIHpvb20gdG9rZW4nKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IGdldENhbGVuZGFySW50ZWdyYXRpb24gPSBhc3luYyAoXG4gIHVzZXJJZDogc3RyaW5nLFxuICByZXNvdXJjZTogc3RyaW5nXG4pID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCBvcGVyYXRpb25OYW1lID0gJ2dldENhbGVuZGFySW50ZWdyYXRpb24nO1xuICAgIGNvbnN0IHF1ZXJ5ID0gYFxuICAgICAgcXVlcnkgZ2V0Q2FsZW5kYXJJbnRlZ3JhdGlvbigkdXNlcklkOiB1dWlkISwgJHJlc291cmNlOiBTdHJpbmchKSB7XG4gICAgICAgIENhbGVuZGFyX0ludGVncmF0aW9uKHdoZXJlOiB7dXNlcklkOiB7X2VxOiAkdXNlcklkfSwgcmVzb3VyY2U6IHtfZXE6ICRyZXNvdXJjZX19KSB7XG4gICAgICAgICAgdG9rZW5cbiAgICAgICAgICBleHBpcmVzQXRcbiAgICAgICAgICBpZFxuICAgICAgICAgIHJlZnJlc2hUb2tlblxuICAgICAgICAgIHJlc291cmNlXG4gICAgICAgICAgbmFtZVxuICAgICAgICAgIGNsaWVudFR5cGVcbiAgICAgICAgfVxuICAgICAgfVxuICAgIGA7XG4gICAgY29uc3QgdmFyaWFibGVzID0ge1xuICAgICAgdXNlcklkLFxuICAgICAgcmVzb3VyY2UsXG4gICAgfTtcblxuICAgIGNvbnN0IHJlczogeyBkYXRhOiB7IENhbGVuZGFyX0ludGVncmF0aW9uOiBDYWxlbmRhckludGVncmF0aW9uVHlwZVtdIH0gfSA9XG4gICAgICBhd2FpdCBnb3RcbiAgICAgICAgLnBvc3QoaGFzdXJhR3JhcGhVcmwsIHtcbiAgICAgICAgICBqc29uOiB7XG4gICAgICAgICAgICBvcGVyYXRpb25OYW1lLFxuICAgICAgICAgICAgcXVlcnksXG4gICAgICAgICAgICB2YXJpYWJsZXMsXG4gICAgICAgICAgfSxcbiAgICAgICAgICBoZWFkZXJzOiB7XG4gICAgICAgICAgICAnWC1IYXN1cmEtQWRtaW4tU2VjcmV0JzogaGFzdXJhQWRtaW5TZWNyZXQsXG4gICAgICAgICAgICAnQ29udGVudC1UeXBlJzogJ2FwcGxpY2F0aW9uL2pzb24nLFxuICAgICAgICAgICAgJ1gtSGFzdXJhLVJvbGUnOiAnYWRtaW4nLFxuICAgICAgICAgIH0sXG4gICAgICAgIH0pXG4gICAgICAgIC5qc29uKCk7XG5cbiAgICBjb25zb2xlLmxvZyhyZXMsICcgcmVzIGluc2lkZSBnZXRDYWxlbmRhckludGVncmF0aW9uJyk7XG4gICAgaWYgKHJlcz8uZGF0YT8uQ2FsZW5kYXJfSW50ZWdyYXRpb24/Lmxlbmd0aCA+IDApIHtcbiAgICAgIHJldHVybiByZXM/LmRhdGE/LkNhbGVuZGFyX0ludGVncmF0aW9uPy5bMF07XG4gICAgfVxuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gZ2V0IGNhbGVuZGFyIGludGVncmF0aW9uJyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCB1cGRhdGVDYWxlbmRhckludGVncmF0aW9uID0gYXN5bmMgKFxuICBpZDogc3RyaW5nLFxuICB0b2tlbj86IHN0cmluZyxcbiAgZXhwaXJlc0luPzogbnVtYmVyLFxuICBlbmFibGVkPzogYm9vbGVhblxuKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3Qgb3BlcmF0aW9uTmFtZSA9ICd1cGRhdGVDYWxlbmRhckludGVncmF0aW9uJztcbiAgICBjb25zdCBxdWVyeSA9IGBcbiAgICAgIG11dGF0aW9uIHVwZGF0ZUNhbGVuZGFySW50ZWdyYXRpb24oJGlkOiB1dWlkISwke3Rva2VuICE9PSB1bmRlZmluZWQgPyAnICR0b2tlbjogU3RyaW5nLCcgOiAnJ30ke2V4cGlyZXNJbiAhPT0gdW5kZWZpbmVkID8gJyAkZXhwaXJlc0F0OiB0aW1lc3RhbXB0eiwnIDogJyd9JHtlbmFibGVkICE9PSB1bmRlZmluZWQgPyAnICRlbmFibGVkOiBCb29sZWFuLCcgOiAnJ30pIHtcbiAgICAgICAgdXBkYXRlX0NhbGVuZGFyX0ludGVncmF0aW9uX2J5X3BrKHBrX2NvbHVtbnM6IHtpZDogJGlkfSwgX3NldDogeyR7dG9rZW4gIT09IHVuZGVmaW5lZCA/ICd0b2tlbjogJHRva2VuLCcgOiAnJ30ke2V4cGlyZXNJbiAhPT0gdW5kZWZpbmVkID8gJyBleHBpcmVzQXQ6ICRleHBpcmVzQXQsJyA6ICcnfSR7ZW5hYmxlZCAhPT0gdW5kZWZpbmVkID8gJyBlbmFibGVkOiAkZW5hYmxlZCwnIDogJyd9fSkge1xuICAgICAgICAgIGlkXG4gICAgICAgICAgbmFtZVxuICAgICAgICAgIHJlZnJlc2hUb2tlblxuICAgICAgICAgIHRva2VuXG4gICAgICAgICAgY2xpZW50VHlwZVxuICAgICAgICAgIHVzZXJJZFxuICAgICAgICAgIHVwZGF0ZWRBdFxuICAgICAgICB9XG4gICAgICB9XG4gICAgYDtcbiAgICBjb25zdCB2YXJpYWJsZXMgPSB7XG4gICAgICBpZCxcbiAgICAgIHRva2VuLFxuICAgICAgZXhwaXJlc0F0OiBkYXlqcygpLmFkZChleHBpcmVzSW4sICdzZWNvbmRzJykudG9JU09TdHJpbmcoKSxcbiAgICAgIGVuYWJsZWQsXG4gICAgfTtcblxuICAgIGNvbnN0IHJlcyA9IGF3YWl0IGdvdFxuICAgICAgLnBvc3QoaGFzdXJhR3JhcGhVcmwsIHtcbiAgICAgICAganNvbjoge1xuICAgICAgICAgIG9wZXJhdGlvbk5hbWUsXG4gICAgICAgICAgcXVlcnksXG4gICAgICAgICAgdmFyaWFibGVzLFxuICAgICAgICB9LFxuICAgICAgICBoZWFkZXJzOiB7XG4gICAgICAgICAgJ1gtSGFzdXJhLUFkbWluLVNlY3JldCc6IGhhc3VyYUFkbWluU2VjcmV0LFxuICAgICAgICAgICdDb250ZW50LVR5cGUnOiAnYXBwbGljYXRpb24vanNvbicsXG4gICAgICAgICAgJ1gtSGFzdXJhLVJvbGUnOiAnYWRtaW4nLFxuICAgICAgICB9LFxuICAgICAgfSlcbiAgICAgIC5qc29uKCk7XG5cbiAgICBjb25zb2xlLmxvZyhyZXMsICcgcmVzIGluc2lkZSB1cGRhdGVDYWxlbmRhckludGVncmF0aW9uJyk7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byB1cGRhdGUgY2FsZW5kYXIgaW50ZWdyYXRpb24nKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IGRlY3J5cHRab29tVG9rZW5zID0gKFxuICBlbmNyeXB0ZWRUb2tlbjogc3RyaW5nLFxuICBlbmNyeXB0ZWRSZWZyZXNoVG9rZW4/OiBzdHJpbmdcbikgPT4ge1xuICBjb25zdCBpdkJ1ZmZlciA9IEJ1ZmZlci5mcm9tKHpvb21JVkZvclBhc3MsICdiYXNlNjQnKTtcbiAgY29uc3Qgc2FsdEJ1ZmZlciA9IEJ1ZmZlci5mcm9tKHpvb21TYWx0Rm9yUGFzcywgJ2Jhc2U2NCcpO1xuXG4gIGNvbnN0IGtleSA9IGNyeXB0by5wYmtkZjJTeW5jKFxuICAgIHpvb21QYXNzS2V5IGFzIHN0cmluZyxcbiAgICBzYWx0QnVmZmVyLFxuICAgIDEwMDAwLFxuICAgIDMyLFxuICAgICdzaGEyNTYnXG4gICk7XG5cbiAgY29uc3QgZGVjaXBoZXJUb2tlbiA9IGNyeXB0by5jcmVhdGVEZWNpcGhlcml2KCdhZXMtMjU2LWNiYycsIGtleSwgaXZCdWZmZXIpO1xuICBsZXQgZGVjcnlwdGVkVG9rZW4gPSBkZWNpcGhlclRva2VuLnVwZGF0ZShlbmNyeXB0ZWRUb2tlbiwgJ2Jhc2U2NCcsICd1dGY4Jyk7XG4gIGRlY3J5cHRlZFRva2VuICs9IGRlY2lwaGVyVG9rZW4uZmluYWwoJ3V0ZjgnKTtcblxuICBpZiAoZW5jcnlwdGVkUmVmcmVzaFRva2VuKSB7XG4gICAgY29uc3QgZGVjaXBoZXJSZWZyZXNoVG9rZW4gPSBjcnlwdG8uY3JlYXRlRGVjaXBoZXJpdihcbiAgICAgICdhZXMtMjU2LWNiYycsXG4gICAgICBrZXksXG4gICAgICBpdkJ1ZmZlclxuICAgICk7XG4gICAgbGV0IGRlY3J5cHRlZFJlZnJlc2hUb2tlbiA9IGRlY2lwaGVyUmVmcmVzaFRva2VuLnVwZGF0ZShcbiAgICAgIGVuY3J5cHRlZFJlZnJlc2hUb2tlbixcbiAgICAgICdiYXNlNjQnLFxuICAgICAgJ3V0ZjgnXG4gICAgKTtcbiAgICBkZWNyeXB0ZWRSZWZyZXNoVG9rZW4gKz0gZGVjaXBoZXJSZWZyZXNoVG9rZW4uZmluYWwoJ3V0ZjgnKTtcblxuICAgIHJldHVybiB7XG4gICAgICB0b2tlbjogZGVjcnlwdGVkVG9rZW4sXG4gICAgICByZWZyZXNoVG9rZW46IGRlY3J5cHRlZFJlZnJlc2hUb2tlbixcbiAgICB9O1xuICB9XG5cbiAgcmV0dXJuIHtcbiAgICB0b2tlbjogZGVjcnlwdGVkVG9rZW4sXG4gIH07XG59O1xuXG5leHBvcnQgY29uc3QgZW5jcnlwdFpvb21Ub2tlbnMgPSAodG9rZW46IHN0cmluZywgcmVmcmVzaFRva2VuPzogc3RyaW5nKSA9PiB7XG4gIGNvbnN0IGl2QnVmZmVyID0gQnVmZmVyLmZyb20oem9vbUlWRm9yUGFzcywgJ2Jhc2U2NCcpO1xuICBjb25zdCBzYWx0QnVmZmVyID0gQnVmZmVyLmZyb20oem9vbVNhbHRGb3JQYXNzLCAnYmFzZTY0Jyk7XG5cbiAgY29uc3Qga2V5ID0gY3J5cHRvLnBia2RmMlN5bmMoXG4gICAgem9vbVBhc3NLZXkgYXMgc3RyaW5nLFxuICAgIHNhbHRCdWZmZXIsXG4gICAgMTAwMDAsXG4gICAgMzIsXG4gICAgJ3NoYTI1NidcbiAgKTtcbiAgY29uc3QgY2lwaGVyVG9rZW4gPSBjcnlwdG8uY3JlYXRlQ2lwaGVyaXYoJ2Flcy0yNTYtY2JjJywga2V5LCBpdkJ1ZmZlcik7XG4gIGxldCBlbmNyeXB0ZWRUb2tlbiA9IGNpcGhlclRva2VuLnVwZGF0ZSh0b2tlbiwgJ3V0ZjgnLCAnYmFzZTY0Jyk7XG4gIGVuY3J5cHRlZFRva2VuICs9IGNpcGhlclRva2VuLmZpbmFsKCdiYXNlNjQnKTtcblxuICBsZXQgZW5jcnlwdGVkUmVmcmVzaFRva2VuID0gJyc7XG5cbiAgaWYgKHJlZnJlc2hUb2tlbikge1xuICAgIGNvbnN0IGNpcGhlclJlZnJlc2hUb2tlbiA9IGNyeXB0by5jcmVhdGVDaXBoZXJpdihcbiAgICAgICdhZXMtMjU2LWNiYycsXG4gICAgICBrZXksXG4gICAgICBpdkJ1ZmZlclxuICAgICk7XG4gICAgZW5jcnlwdGVkUmVmcmVzaFRva2VuID0gY2lwaGVyUmVmcmVzaFRva2VuLnVwZGF0ZShcbiAgICAgIHJlZnJlc2hUb2tlbixcbiAgICAgICd1dGY4JyxcbiAgICAgICdiYXNlNjQnXG4gICAgKTtcbiAgICBlbmNyeXB0ZWRSZWZyZXNoVG9rZW4gKz0gY2lwaGVyUmVmcmVzaFRva2VuLmZpbmFsKCdiYXNlNjQnKTtcbiAgfVxuXG4gIGlmIChlbmNyeXB0ZWRSZWZyZXNoVG9rZW4pIHtcbiAgICByZXR1cm4ge1xuICAgICAgZW5jcnlwdGVkVG9rZW4sXG4gICAgICBlbmNyeXB0ZWRSZWZyZXNoVG9rZW4sXG4gICAgfTtcbiAgfSBlbHNlIHtcbiAgICByZXR1cm4geyBlbmNyeXB0ZWRUb2tlbiB9O1xuICB9XG59O1xuXG5leHBvcnQgY29uc3QgZ2V0Wm9vbUludGVncmF0aW9uID0gYXN5bmMgKHVzZXJJZDogc3RyaW5nKSA9PiB7XG4gIHRyeSB7XG4gICAgY29uc3QgeyBpZCwgdG9rZW4sIGV4cGlyZXNBdCwgcmVmcmVzaFRva2VuIH0gPSBhd2FpdCBnZXRDYWxlbmRhckludGVncmF0aW9uKFxuICAgICAgdXNlcklkLFxuICAgICAgem9vbVJlc291cmNlTmFtZVxuICAgICk7XG5cbiAgICBjb25zdCBkZWNyeXB0ZWRUb2tlbnMgPSBkZWNyeXB0Wm9vbVRva2Vucyh0b2tlbiwgcmVmcmVzaFRva2VuKTtcblxuICAgIHJldHVybiB7XG4gICAgICBpZCxcbiAgICAgIGV4cGlyZXNBdCxcbiAgICAgIC4uLmRlY3J5cHRlZFRva2VucyxcbiAgICB9O1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gZ2V0IHpvb20gaW50ZWdyYXRpb24nKTtcbiAgfVxufTtcblxuZXhwb3J0IGNvbnN0IHVwZGF0ZVpvb21JbnRlZ3JhdGlvbiA9IGFzeW5jIChcbiAgaWQ6IHN0cmluZyxcbiAgYWNjZXNzVG9rZW46IHN0cmluZyxcbiAgZXhwaXJlc0luOiBudW1iZXJcbikgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IHsgZW5jcnlwdGVkVG9rZW4gfSA9IGVuY3J5cHRab29tVG9rZW5zKGFjY2Vzc1Rva2VuKTtcbiAgICBhd2FpdCB1cGRhdGVDYWxlbmRhckludGVncmF0aW9uKGlkLCBlbmNyeXB0ZWRUb2tlbiwgZXhwaXJlc0luKTtcbiAgfSBjYXRjaCAoZSkge1xuICAgIGNvbnNvbGUubG9nKGUsICcgdW5hYmxlIHRvIHVwZGF0ZSB6b29tIGludGVncmF0aW9uJyk7XG4gIH1cbn07XG5cbmV4cG9ydCBjb25zdCBnZXRab29tQVBJVG9rZW4gPSBhc3luYyAodXNlcklkOiBzdHJpbmcpID0+IHtcbiAgbGV0IGludGVncmF0aW9uSWQgPSAnJztcbiAgdHJ5IHtcbiAgICBjb25zb2xlLmxvZygnZ2V0Wm9vbUFQSVRva2VuIGNhbGxlZCcpO1xuICAgIGNvbnN0IHsgaWQsIHRva2VuLCBleHBpcmVzQXQsIHJlZnJlc2hUb2tlbiB9ID1cbiAgICAgIGF3YWl0IGdldFpvb21JbnRlZ3JhdGlvbih1c2VySWQpO1xuICAgIGludGVncmF0aW9uSWQgPSBpZDtcbiAgICBjb25zb2xlLmxvZyhcbiAgICAgIGlkLFxuICAgICAgdG9rZW4sXG4gICAgICBleHBpcmVzQXQsXG4gICAgICByZWZyZXNoVG9rZW4sXG4gICAgICAnIGlkLCB0b2tlbiwgZXhwaXJlc0F0LCByZWZyZXNoVG9rZW4nXG4gICAgKTtcbiAgICBpZiAoZGF5anMoKS5pc0FmdGVyKGRheWpzKGV4cGlyZXNBdCkpIHx8ICF0b2tlbikge1xuICAgICAgY29uc3QgcmVzID0gYXdhaXQgcmVmcmVzaFpvb21Ub2tlbihyZWZyZXNoVG9rZW4pO1xuICAgICAgY29uc29sZS5sb2cocmVzLCAnIHJlcyBmcm9tIHJlZnJlc2hab29tVG9rZW4nKTtcbiAgICAgIGF3YWl0IHVwZGF0ZVpvb21JbnRlZ3JhdGlvbihpZCwgcmVzLmFjY2Vzc190b2tlbiwgcmVzLmV4cGlyZXNfaW4pO1xuICAgICAgcmV0dXJuIHJlcy5hY2Nlc3NfdG9rZW47XG4gICAgfVxuXG4gICAgcmV0dXJuIHRva2VuO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gZ2V0IHpvb20gYXBpIHRva2VuJyk7XG4gICAgYXdhaXQgdXBkYXRlQ2FsZW5kYXJJbnRlZ3JhdGlvbihpbnRlZ3JhdGlvbklkLCBudWxsLCBudWxsLCBmYWxzZSk7XG4gIH1cbn07XG4iXX0=