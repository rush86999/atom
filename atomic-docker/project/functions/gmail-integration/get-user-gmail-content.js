// Adjust path to where gmail-service/service.ts is located relative to this file
import { getUserEmailContent as fetchEmailContentFromService } from '../gmail-service/service';
// Helper function to recursively transform Google's MessagePart to our defined GmailMessagePart
function transformGmailPart(part) {
    if (!part) {
        return null;
    }
    return {
        partId: part.partId || undefined, // Ensure nulls become undefined if schema expects optional
        mimeType: part.mimeType || undefined,
        filename: part.filename || undefined,
        headers: part.headers?.map((h) => ({
            name: h.name || undefined,
            value: h.value || undefined,
        })) || [],
        body: part.body
            ? {
                size: part.body.size || undefined,
                data: part.body.data || undefined,
                attachmentId: part.body.attachmentId || undefined,
            }
            : undefined, // Use undefined if body is null/undefined
        // Ensure recursive call correctly handles null/undefined parts and maps to GmailMessagePart or null
        parts: part.parts
            ?.map((p) => transformGmailPart(p))
            .filter((p) => p !== null) || [],
    };
}
const handler = async (req, res) => {
    const userId = req.body.session_variables['x-hasura-user-id'];
    const { emailId } = req.body.input;
    if (!userId) {
        return res
            .status(401)
            .json({
            success: false,
            message: 'User ID is missing from session. Unauthorized.',
        });
    }
    if (!emailId || typeof emailId !== 'string' || emailId.trim() === '') {
        return res
            .status(400)
            .json({ success: false, message: 'Email ID is missing or invalid.' });
    }
    try {
        const rawEmailFromService = await fetchEmailContentFromService(userId, emailId);
        if (!rawEmailFromService || !rawEmailFromService.id) {
            return res
                .status(404)
                .json({
                success: false,
                message: `Email with ID '${emailId}' not found or inaccessible.`,
            });
        }
        // Transform the raw Gmail API message to our GmailMessageContent structure
        const transformedEmail = {
            id: rawEmailFromService.id, // id is non-nullable
            threadId: rawEmailFromService.threadId || undefined,
            labelIds: rawEmailFromService.labelIds || [],
            snippet: rawEmailFromService.snippet || undefined,
            historyId: rawEmailFromService.historyId || undefined,
            internalDate: rawEmailFromService.internalDate || undefined,
            payload: transformGmailPart(rawEmailFromService.payload),
            sizeEstimate: rawEmailFromService.sizeEstimate || undefined,
            raw: rawEmailFromService.raw || undefined,
        };
        return res.status(200).json({
            success: true,
            email: transformedEmail,
        });
    }
    catch (e) {
        console.error(`Error in getUserGmailContent handler for user ${userId}, emailId ${emailId}:`, e);
        const errorMessage = e.message || 'An unexpected error occurred while fetching email content.';
        if (errorMessage.includes('Failed to get authenticated Gmail client') ||
            errorMessage.includes('User needs to authorize') ||
            errorMessage.includes('token might be revoked') ||
            errorMessage.includes('Gmail authentication failed')) {
            // Catch more specific auth errors
            return res
                .status(401)
                .json({
                success: false,
                message: 'Gmail authentication error. Please connect or reconnect your Gmail account via settings.',
            });
        }
        if (errorMessage.toLowerCase().includes('not found')) {
            // Catch "not found" from service layer
            return res.status(404).json({ success: false, message: errorMessage });
        }
        return res.status(500).json({
            success: false,
            message: errorMessage,
        });
    }
};
export default handler;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiZ2V0LXVzZXItZ21haWwtY29udGVudC5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImdldC11c2VyLWdtYWlsLWNvbnRlbnQudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6IkFBQ0EsaUZBQWlGO0FBQ2pGLE9BQU8sRUFBRSxtQkFBbUIsSUFBSSw0QkFBNEIsRUFBRSxNQUFNLDBCQUEwQixDQUFDO0FBMEQvRixnR0FBZ0c7QUFDaEcsU0FBUyxrQkFBa0IsQ0FDekIsSUFBb0Q7SUFFcEQsSUFBSSxDQUFDLElBQUksRUFBRSxDQUFDO1FBQ1YsT0FBTyxJQUFJLENBQUM7SUFDZCxDQUFDO0lBQ0QsT0FBTztRQUNMLE1BQU0sRUFBRSxJQUFJLENBQUMsTUFBTSxJQUFJLFNBQVMsRUFBRSwyREFBMkQ7UUFDN0YsUUFBUSxFQUFFLElBQUksQ0FBQyxRQUFRLElBQUksU0FBUztRQUNwQyxRQUFRLEVBQUUsSUFBSSxDQUFDLFFBQVEsSUFBSSxTQUFTO1FBQ3BDLE9BQU8sRUFDTCxJQUFJLENBQUMsT0FBTyxFQUFFLEdBQUcsQ0FBQyxDQUFDLENBQUMsRUFBRSxFQUFFLENBQUMsQ0FBQztZQUN4QixJQUFJLEVBQUUsQ0FBQyxDQUFDLElBQUksSUFBSSxTQUFTO1lBQ3pCLEtBQUssRUFBRSxDQUFDLENBQUMsS0FBSyxJQUFJLFNBQVM7U0FDNUIsQ0FBQyxDQUFDLElBQUksRUFBRTtRQUNYLElBQUksRUFBRSxJQUFJLENBQUMsSUFBSTtZQUNiLENBQUMsQ0FBQztnQkFDRSxJQUFJLEVBQUUsSUFBSSxDQUFDLElBQUksQ0FBQyxJQUFJLElBQUksU0FBUztnQkFDakMsSUFBSSxFQUFFLElBQUksQ0FBQyxJQUFJLENBQUMsSUFBSSxJQUFJLFNBQVM7Z0JBQ2pDLFlBQVksRUFBRSxJQUFJLENBQUMsSUFBSSxDQUFDLFlBQVksSUFBSSxTQUFTO2FBQ2xEO1lBQ0gsQ0FBQyxDQUFDLFNBQVMsRUFBRSwwQ0FBMEM7UUFDekQsb0dBQW9HO1FBQ3BHLEtBQUssRUFDRixJQUFJ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Qyx5QkFBeUIsQ0FBQztZQUNoRCxZQUFZLENBQUMsUUFBUSxDQUFDLHdCQUF3QixDQUFDO1lBQy9DLFlBQVksQ0FBQyxRQUFRLENBQUMsNkJBQTZCLENBQUMsRUFDcEQsQ0FBQztZQUNELGtDQUFrQztZQUNsQyxPQUFPLEdBQUc7aUJBQ1AsTUFBTSxDQUFDLEdBQUcsQ0FBQztpQkFDWCxJQUFJLENBQUM7Z0JBQ0osT0FBTyxFQUFFLEtBQUs7Z0JBQ2QsT0FBTyxFQUNMLDBGQUEwRjthQUM3RixDQUFDLENBQUM7UUFDUCxDQUFDO1FBQ0QsSUFBSSxZQUFZLENBQUMsV0FBVyxFQUFFLENBQUMsUUFBUSxDQUFDLFdBQVcsQ0FBQyxFQUFFLENBQUM7WUFDckQsdUNBQXVDO1lBQ3ZDLE9BQU8sR0FBRyxDQUFDLE1BQU0sQ0FBQyxHQUFHLENBQUMsQ0FBQyxJQUFJLENBQUMsRUFBRSxPQUFPLEVBQUUsS0FBSyxFQUFFLE9BQU8sRUFBRSxZQUFZLEVBQUUsQ0FBQyxDQUFDO1FBQ3pFLENBQUM7UUFFRCxPQUFPLEdBQUcsQ0FBQyxNQUFNLENBQUMsR0FBRyxDQUFDLENBQUMsSUFBSSxDQUFDO1lBQzFCLE9BQU8sRUFBRSxLQUFLO1lBQ2QsT0FBTyxFQUFFLFlBQVk7U0FDdEIsQ0FBQyxDQUFDO0lBQ0wsQ0FBQztBQUNILENBQUMsQ0FBQztBQUVGLGVBQWUsT0FBTyxDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IHsgUmVxdWVzdCwgUmVzcG9uc2UgfSBmcm9tICdleHByZXNzJztcbi8vIEFkanVzdCBwYXRoIHRvIHdoZXJlIGdtYWlsLXNlcnZpY2Uvc2VydmljZS50cyBpcyBsb2NhdGVkIHJlbGF0aXZlIHRvIHRoaXMgZmlsZVxuaW1wb3J0IHsgZ2V0VXNlckVtYWlsQ29udGVudCBhcyBmZXRjaEVtYWlsQ29udGVudEZyb21TZXJ2aWNlIH0gZnJvbSAnLi4vZ21haWwtc2VydmljZS9zZXJ2aWNlJztcbmltcG9ydCB7IGdtYWlsX3YxIH0gZnJvbSAnZ29vZ2xlYXBpcyc7XG5cbi8vIFR5cGVTY3JpcHQgaW50ZXJmYWNlcyBtYXRjaGluZyB0aGUgR3JhcGhRTCBzY2hlbWEgZm9yIEdtYWlsTWVzc2FnZUNvbnRlbnQgYW5kIHJlbGF0ZWQgdHlwZXNcbi8vIFRoZXNlIHNob3VsZCBpZGVhbGx5IGJlIGdlbmVyYXRlZCBieSBhIHRvb2wgbGlrZSBHcmFwaFFMIENvZGUgR2VuZXJhdG9yIGJhc2VkIG9uIHlvdXIgYWN0aW9ucy5ncmFwaHFsIGRlZmluaXRpb25zLlxuLy8gRGVmaW5pbmcgbWFudWFsbHkgZm9yIG5vdyB0byBlbnN1cmUgaGFuZGxlciBhbGlnbnMgd2l0aCB0aGUgc2NoZW1hLlxuXG5pbnRlcmZhY2UgR21haWxNZXNzYWdlUGF5bG9hZEhlYWRlciB7XG4gIG5hbWU/OiBzdHJpbmcgfCBudWxsO1xuICB2YWx1ZT86IHN0cmluZyB8IG51bGw7XG59XG5cbmludGVyZmFjZSBHbWFpbE1lc3NhZ2VQYXJ0Qm9keSB7XG4gIHNpemU/OiBudW1iZXIgfCBudWxsO1xuICBkYXRhPzogc3RyaW5nIHwgbnVsbDtcbiAgYXR0YWNobWVudElkPzogc3RyaW5nIHwgbnVsbDtcbn1cblxuaW50ZXJmYWNlIEdtYWlsTWVzc2FnZVBhcnQge1xuICBwYXJ0SWQ/OiBzdHJpbmcgfCBudWxsO1xuICBtaW1lVHlwZT86IHN0cmluZyB8IG51bGw7XG4gIGZpbGVuYW1lPzogc3RyaW5nIHwgbnVsbDtcbiAgaGVhZGVycz86IEdtYWlsTWVzc2FnZVBheWxvYWRIZWFkZXJbXSB8IG51bGw7IC8vIENoYW5nZWQgZnJvbSBbR21haWxNZXNzYWdlUGF5bG9hZEhlYWRlciFdIHRvIGFsbG93IGVtcHR5IG9yIG51bGxcbiAgYm9keT86IEdtYWlsTWVzc2FnZVBhcnRCb2R5IHwgbnVsbDtcbiAgcGFydHM/OiBHbWFpbE1lc3NhZ2VQYXJ0W10gfCBudWxsOyAvLyBDaGFuZ2VkIGZyb20gW0dtYWlsTWVzc2FnZVBhcnQhXVxufVxuXG5pbnRlcmZhY2UgR21haWxNZXNzYWdlQ29udGVudCB7XG4gIGlkOiBzdHJpbmc7XG4gIHRocmVhZElkPzogc3RyaW5nIHwgbnVsbDtcbiAgbGFiZWxJZHM/OiBzdHJpbmdbXSB8IG51bGw7IC8vIENoYW5nZWQgZnJvbSBbU3RyaW5nIV1cbiAgc25pcHBldD86IHN0cmluZyB8IG51bGw7XG4gIGhpc3RvcnlJZD86IHN0cmluZyB8IG51bGw7XG4gIGludGVybmFsRGF0ZT86IHN0cmluZyB8IG51bGw7XG4gIHBheWxvYWQ/OiBHbWFpbE1lc3NhZ2VQYXJ0IHwgbnVsbDtcbiAgc2l6ZUVzdGltYXRlPzogbnVtYmVyIHwgbnVsbDtcbiAgcmF3Pzogc3RyaW5nIHwgbnVsbDtcbn1cblxuLy8gSW5wdXQgZm9yIHRoaXMgYWN0aW9uIGhhbmRsZXJcbmludGVyZmFjZSBHZXRVc2VyR21haWxDb250ZW50SW5wdXQge1xuICBlbWFpbElkOiBzdHJpbmc7XG59XG5cbmludGVyZmFjZSBHZXRVc2VyR21haWxDb250ZW50UmVxdWVzdEJvZHkge1xuICBzZXNzaW9uX3ZhcmlhYmxlczoge1xuICAgICd4LWhhc3VyYS11c2VyLWlkJzogc3RyaW5nO1xuICB9O1xuICBpbnB1dDogR2V0VXNlckdtYWlsQ29udGVudElucHV0O1xufVxuXG4vLyBPdXRwdXQgcmVzcG9uc2UgZm9yIHRoaXMgYWN0aW9uIGhhbmRsZXJcbmludGVyZmFjZSBHZXRVc2VyR21haWxDb250ZW50UmVzcG9uc2Uge1xuICBzdWNjZXNzOiBib29sZWFuO1xuICBtZXNzYWdlPzogc3RyaW5nO1xuICBlbWFpbD86IEdtYWlsTWVzc2FnZUNvbnRlbnQgfCBudWxsO1xufVxuXG4vLyBIZWxwZXIgZnVuY3Rpb24gdG8gcmVjdXJzaXZlbHkgdHJhbnNmb3JtIEdvb2dsZSdzIE1lc3NhZ2VQYXJ0IHRvIG91ciBkZWZpbmVkIEdtYWlsTWVzc2FnZVBhcnRcbmZ1bmN0aW9uIHRyYW5zZm9ybUdtYWlsUGFydChcbiAgcGFydDogZ21haWxfdjEuU2NoZW1hJE1lc3NhZ2VQYXJ0IHwgdW5kZWZpbmVkIHwgbnVsbFxuKTogR21haWxNZXNzYWdlUGFydCB8IG51bGwge1xuICBpZiAoIXBhcnQpIHtcbiAgICByZXR1cm4gbnVsbDtcbiAgfVxuICByZXR1cm4ge1xuICAgIHBhcnRJZDogcGFydC5wYXJ0SWQgfHwgdW5kZWZpbmVkLCAvLyBFbnN1cmUgbnVsbHMgYmVjb21lIHVuZGVmaW5lZCBpZiBzY2hlbWEgZXhwZWN0cyBvcHRpb25hbFxuICAgIG1pbWVUeXBlOiBwYXJ0Lm1pbWVUeXBlIHx8IHVuZGVmaW5lZCxcbiAgICBmaWxlbmFtZTogcGFydC5maWxlbmFtZSB8fCB1bmRlZmluZWQsXG4gICAgaGVhZGVyczpcbiAgICAgIHBhcnQuaGVhZGVycz8ubWFwKChoKSA9PiAoe1xuICAgICAgICBuYW1lOiBoLm5hbWUgfHwgdW5kZWZpbmVkLFxuICAgICAgICB2YWx1ZTogaC52YWx1ZSB8fCB1bmRlZmluZWQsXG4gICAgICB9KSkgfHwgW10sXG4gICAgYm9keTogcGFydC5ib2R5XG4gICAgICA/IHtcbiAgICAgICAgICBzaXplOiBwYXJ0LmJvZHkuc2l6ZSB8fCB1bmRlZmluZWQsXG4gICAgICAgICAgZGF0YTogcGFydC5ib2R5LmRhdGEgfHwgdW5kZWZpbmVkLFxuICAgICAgICAgIGF0dGFjaG1lbnRJZDogcGFydC5ib2R5LmF0dGFjaG1lbnRJZCB8fCB1bmRlZmluZWQsXG4gICAgICAgIH1cbiAgICAgIDogdW5kZWZpbmVkLCAvLyBVc2UgdW5kZWZpbmVkIGlmIGJvZHkgaXMgbnVsbC91bmRlZmluZWRcbiAgICAvLyBFbnN1cmUgcmVjdXJzaXZlIGNhbGwgY29ycmVjdGx5IGhhbmRsZXMgbnVsbC91bmRlZmluZWQgcGFydHMgYW5kIG1hcHMgdG8gR21haWxNZXNzYWdlUGFydCBvciBudWxsXG4gICAgcGFydHM6XG4gICAgICAocGFydC5wYXJ0c1xuICAgICAgICA/Lm1hcCgocCkgPT4gdHJhbnNmb3JtR21haWxQYXJ0KHApKVxuICAgICAgICAuZmlsdGVyKChwKSA9PiBwICE9PSBudWxsKSBhcyBHbWFpbE1lc3NhZ2VQYXJ0W10pIHx8IFtdLFxuICB9O1xufVxuXG5jb25zdCBoYW5kbGVyID0gYXN5bmMgKFxuICByZXE6IFJlcXVlc3Q8e30sIHt9LCBHZXRVc2VyR21haWxDb250ZW50UmVxdWVzdEJvZHk+LFxuICByZXM6IFJlc3BvbnNlPEdldFVzZXJHbWFpbENvbnRlbnRSZXNwb25zZT5cbikgPT4ge1xuICBjb25zdCB1c2VySWQgPSByZXEuYm9keS5zZXNzaW9uX3ZhcmlhYmxlc1sneC1oYXN1cmEtdXNlci1pZCddO1xuICBjb25zdCB7IGVtYWlsSWQgfSA9IHJlcS5ib2R5LmlucHV0O1xuXG4gIGlmICghdXNlcklkKSB7XG4gICAgcmV0dXJuIHJlc1xuICAgICAgLnN0YXR1cyg0MDEpXG4gICAgICAuanNvbih7XG4gICAgICAgIHN1Y2Nlc3M6IGZhbHNlLFxuICAgICAgICBtZXNzYWdlOiAnVXNlciBJRCBpcyBtaXNzaW5nIGZyb20gc2Vzc2lvbi4gVW5hdXRob3JpemVkLicsXG4gICAgICB9KTtcbiAgfVxuICBpZiAoIWVtYWlsSWQgfHwgdHlwZW9mIGVtYWlsSWQgIT09ICdzdHJpbmcnIHx8IGVtYWlsSWQudHJpbSgpID09PSAnJykge1xuICAgIHJldHVybiByZXNcbiAgICAgIC5zdGF0dXMoNDAwKVxuICAgICAgLmpzb24oeyBzdWNjZXNzOiBmYWxzZSwgbWVzc2FnZTogJ0VtYWlsIElEIGlzIG1pc3Npbmcgb3IgaW52YWxpZC4nIH0pO1xuICB9XG5cbiAgdHJ5IHtcbiAgICBjb25zdCByYXdFbWFpbEZyb21TZXJ2aWNlOiBnbWFpbF92MS5TY2hlbWEkTWVzc2FnZSB8IG51bGwgPVxuICAgICAgYXdhaXQgZmV0Y2hFbWFpbENvbnRlbnRGcm9tU2VydmljZSh1c2VySWQsIGVtYWlsSWQpO1xuXG4gICAgaWYgKCFyYXdFbWFpbEZyb21TZXJ2aWNlIHx8ICFyYXdFbWFpbEZyb21TZXJ2aWNlLmlkKSB7XG4gICAgICByZXR1cm4gcmVzXG4gICAgICAgIC5zdGF0dXMoNDA0KVxuICAgICAgICAuanNvbih7XG4gICAgICAgICAgc3VjY2VzczogZmFsc2UsXG4gICAgICAgICAgbWVzc2FnZTogYEVtYWlsIHdpdGggSUQgJyR7ZW1haWxJZH0nIG5vdCBmb3VuZCBvciBpbmFjY2Vzc2libGUuYCxcbiAgICAgICAgfSk7XG4gICAgfVxuXG4gICAgLy8gVHJhbnNmb3JtIHRoZSByYXcgR21haWwgQVBJIG1lc3NhZ2UgdG8gb3VyIEdtYWlsTWVzc2FnZUNvbnRlbnQgc3RydWN0dXJlXG4gICAgY29uc3QgdHJhbnNmb3JtZWRFbWFpbDogR21haWxNZXNzYWdlQ29udGVudCA9IHtcbiAgICAgIGlkOiByYXdFbWFpbEZyb21TZXJ2aWNlLmlkLCAvLyBpZCBpcyBub24tbnVsbGFibGVcbiAgICAgIHRocmVhZElkOiByYXdFbWFpbEZyb21TZXJ2aWNlLnRocmVhZElkIHx8IHVuZGVmaW5lZCxcbiAgICAgIGxhYmVsSWRzOiByYXdFbWFpbEZyb21TZXJ2aWNlLmxhYmVsSWRzIHx8IFtdLFxuICAgICAgc25pcHBldDogcmF3RW1haWxGcm9tU2VydmljZS5zbmlwcGV0IHx8IHVuZGVmaW5lZCxcbiAgICAgIGhpc3RvcnlJZDogcmF3RW1haWxGcm9tU2VydmljZS5oaXN0b3J5SWQgfHwgdW5kZWZpbmVkLFxuICAgICAgaW50ZXJuYWxEYXRlOiByYXdFbWFpbEZyb21TZXJ2aWNlLmludGVybmFsRGF0ZSB8fCB1bmRlZmluZWQsXG4gICAgICBwYXlsb2FkOiB0cmFuc2Zvcm1HbWFpbFBhcnQocmF3RW1haWxGcm9tU2VydmljZS5wYXlsb2FkKSxcbiAgICAgIHNpemVFc3RpbWF0ZTogcmF3RW1haWxGcm9tU2VydmljZS5zaXplRXN0aW1hdGUgfHwgdW5kZWZpbmVkLFxuICAgICAgcmF3OiByYXdFbWFpbEZyb21TZXJ2aWNlLnJhdyB8fCB1bmRlZmluZWQsXG4gICAgfTtcblxuICAgIHJldHVybiByZXMuc3RhdHVzKDIwMCkuanNvbih7XG4gICAgICBzdWNjZXNzOiB0cnVlLFxuICAgICAgZW1haWw6IHRyYW5zZm9ybWVkRW1haWwsXG4gICAgfSk7XG4gIH0gY2F0Y2ggKGU6IGFueSkge1xuICAgIGNvbnNvbGUuZXJyb3IoXG4gICAgICBgRXJyb3IgaW4gZ2V0VXNlckdtYWlsQ29udGVudCBoYW5kbGVyIGZvciB1c2VyICR7dXNlcklkfSwgZW1haWxJZCAke2VtYWlsSWR9OmAsXG4gICAgICBlXG4gICAgKTtcbiAgICBjb25zdCBlcnJvck1lc3NhZ2UgPVxuICAgICAgZS5tZXNzYWdlIHx8ICdBbiB1bmV4cGVjdGVkIGVycm9yIG9jY3VycmVkIHdoaWxlIGZldGNoaW5nIGVtYWlsIGNvbnRlbnQuJztcblxuICAgIGlmIChcbiAgICAgIGVycm9yTWVzc2FnZS5pbmNsdWRlcygnRmFpbGVkIHRvIGdldCBhdXRoZW50aWNhdGVkIEdtYWlsIGNsaWVudCcpIHx8XG4gICAgICBlcnJvck1lc3NhZ2UuaW5jbHVkZXMoJ1VzZXIgbmVlZHMgdG8gYXV0aG9yaXplJykgfHxcbiAgICAgIGVycm9yTWVzc2FnZS5pbmNsdWRlcygndG9rZW4gbWlnaHQgYmUgcmV2b2tlZCcpIHx8XG4gICAgICBlcnJvck1lc3NhZ2UuaW5jbHVkZXMoJ0dtYWlsIGF1dGhlbnRpY2F0aW9uIGZhaWxlZCcpXG4gICAgKSB7XG4gICAgICAvLyBDYXRjaCBtb3JlIHNwZWNpZmljIGF1dGggZXJyb3JzXG4gICAgICByZXR1cm4gcmVzXG4gICAgICAgIC5zdGF0dXMoNDAxKVxuICAgICAgICAuanNvbih7XG4gICAgICAgICAgc3VjY2VzczogZmFsc2UsXG4gICAgICAgICAgbWVzc2FnZTpcbiAgICAgICAgICAgICdHbWFpbCBhdXRoZW50aWNhdGlvbiBlcnJvci4gUGxlYXNlIGNvbm5lY3Qgb3IgcmVjb25uZWN0IHlvdXIgR21haWwgYWNjb3VudCB2aWEgc2V0dGluZ3MuJyxcbiAgICAgICAgfSk7XG4gICAgfVxuICAgIGlmIChlcnJvck1lc3NhZ2UudG9Mb3dlckNhc2UoKS5pbmNsdWRlcygnbm90IGZvdW5kJykpIHtcbiAgICAgIC8vIENhdGNoIFwibm90IGZvdW5kXCIgZnJvbSBzZXJ2aWNlIGxheWVyXG4gICAgICByZXR1cm4gcmVzLnN0YXR1cyg0MDQpLmpzb24oeyBzdWNjZXNzOiBmYWxzZSwgbWVzc2FnZTogZXJyb3JNZXNzYWdlIH0pO1xuICAgIH1cblxuICAgIHJldHVybiByZXMuc3RhdHVzKDUwMCkuanNvbih7XG4gICAgICBzdWNjZXNzOiBmYWxzZSxcbiAgICAgIG1lc3NhZ2U6IGVycm9yTWVzc2FnZSxcbiAgICB9KTtcbiAgfVxufTtcblxuZXhwb3J0IGRlZmF1bHQgaGFuZGxlcjtcbiJdfQ==