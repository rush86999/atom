import { listRecentEmails as listEmails, readEmail as read, sendEmail as send, } from './emailSkills';
import { handleError } from '../../_utils/errorHandler';
export async function handleListEmails(entities) {
    try {
        let limit = 10; // Default limit
        if (entities?.limit) {
            if (typeof entities.limit === 'number')
                limit = entities.limit;
            else if (typeof entities.limit === 'string') {
                const parsedLimit = parseInt(entities.limit, 10);
                if (!isNaN(parsedLimit))
                    limit = parsedLimit;
            }
        }
        const emails = await listEmails(limit);
        if (emails.length === 0) {
            return 'No recent emails found (via NLU).';
        }
        else {
            const emailList = emails
                .map((email) => `- (${email.read ? 'read' : 'unread'}) From: ${email.sender}, Subject: ${email.subject} (ID: ${email.id})`)
                .join('\n');
            return `Recent emails (via NLU):\n${emailList}`;
        }
    }
    catch (error) {
        return handleError(error, "Sorry, I couldn't fetch recent emails due to an error (NLU path).");
    }
}
export async function handleReadEmail(entities) {
    try {
        const { email_id } = entities;
        if (!email_id || typeof email_id !== 'string') {
            return 'Email ID is required to read an email via NLU.';
        }
        else {
            const response = await read(email_id);
            if (response.success && response.email) {
                const email = response.email;
                return `Email (ID: ${email.id}):\nFrom: ${email.sender}\nTo: ${email.recipient}\nSubject: ${email.subject}\nDate: ${email.timestamp}\n\n${email.body}`;
            }
            else {
                return response.message || 'Could not read email via NLU.';
            }
        }
    }
    catch (error) {
        return handleError(error, "Sorry, I couldn't read the specified email due to an error (NLU path).");
    }
}
export async function handleSendEmail(entities) {
    try {
        const { to, subject, body } = entities;
        if (!to || typeof to !== 'string') {
            return "Recipient 'to' address is required to send an email via NLU.";
        }
        else if (!subject || typeof subject !== 'string') {
            return 'Subject is required to send an email via NLU.';
        }
        else if (!body || typeof body !== 'string') {
            return 'Body is required to send an email via NLU.';
        }
        else {
            const emailDetails = { to, subject, body };
            const response = await send(emailDetails);
            if (response.success) {
                return `Email sent via NLU: ${response.message} (ID: ${response.emailId})`;
            }
            else {
                return `Failed to send email via NLU: ${response.message}`;
            }
        }
    }
    catch (error) {
        return handleError(error, "Sorry, I couldn't send the email due to an error (NLU path).");
    }
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiZW1haWwuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJlbWFpbC50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiQUFNQSxPQUFPLEVBQ0wsZ0JBQWdCLElBQUksVUFBVSxFQUM5QixTQUFTLElBQUksSUFBSSxFQUNqQixTQUFTLElBQUksSUFBSSxHQUNsQixNQUFNLGVBQWUsQ0FBQztBQUN2QixPQUFPLEVBQUUsV0FBVyxFQUFFLE1BQU0sMkJBQTJCLENBQUM7QUFFeEQsTUFBTSxDQUFDLEtBQUssVUFBVSxnQkFBZ0IsQ0FBQyxRQUFhO0lBQ2xELElBQUksQ0FBQztRQUNILElBQUksS0FBSyxHQUFHLEVBQUUsQ0FBQyxDQUFDLGdCQUFnQjtRQUNoQyxJQUFJLFFBQVEsRUFBRSxLQUFLLEVBQUUsQ0FBQztZQUNwQixJQUFJLE9BQU8sUUFBUSxDQUFDLEtBQUssS0FBSyxRQUFRO2dCQUFFLEtBQUssR0FBRyxRQUFRLENBQUMsS0FBSyxDQUFDO2lCQUMxRCxJQUFJLE9BQU8sUUFBUSxDQUFDLEtBQUssS0FBSyxRQUFRLEVBQUUsQ0FBQztnQkFDNUMsTUFBTSxXQUFXLEdBQUcsUUFBUSxDQUFDLFFBQVEsQ0FBQyxLQUFLLEVBQUUsRUFBRSxDQUFDLENBQUM7Z0JBQ2pELElBQUksQ0FBQyxLQUFLLENBQUMsV0FBVyxDQUFDO29CQUFFLEtBQUssR0FBRyxXQUFXLENBQUM7WUFDL0MsQ0FBQztRQUNILENBQUM7UUFDRCxNQUFNLE1BQU0sR0FBWSxNQUFNLFVBQVUsQ0FBQyxLQUFLLENBQUMsQ0FBQztRQUNoRCxJQUFJLE1BQU0sQ0FBQyxNQUFNLEtBQUssQ0FBQyxFQUFFLENBQUM7WUFDeEIsT0FBTyxtQ0FBbUMsQ0FBQztRQUM3QyxDQUFDO2FBQU0sQ0FBQztZQUNOLE1BQU0sU0FBUyxHQUFHLE1BQU07aUJBQ3JCLEdBQUcsQ0FDRixDQUFDLEtBQUssRUFBRSxFQUFFLENBQ1IsTUFBTSxLQUFLLENBQUMsSUFBSSxDQUFDLENBQUMsQ0FBQyxNQUFNLENBQUMs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LFxuICBTZW5kRW1haWxSZXNwb25zZSxcbiAgRW1haWxEZXRhaWxzLFxufSBmcm9tICcuLi8uLi90eXBlcyc7XG5pbXBvcnQge1xuICBsaXN0UmVjZW50RW1haWxzIGFzIGxpc3RFbWFpbHMsXG4gIHJlYWRFbWFpbCBhcyByZWFkLFxuICBzZW5kRW1haWwgYXMgc2VuZCxcbn0gZnJvbSAnLi9lbWFpbFNraWxscyc7XG5pbXBvcnQgeyBoYW5kbGVFcnJvciB9IGZyb20gJy4uLy4uL191dGlscy9lcnJvckhhbmRsZXInO1xuXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gaGFuZGxlTGlzdEVtYWlscyhlbnRpdGllczogYW55KTogUHJvbWlzZTxzdHJpbmc+IHtcbiAgdHJ5IHtcbiAgICBsZXQgbGltaXQgPSAxMDsgLy8gRGVmYXVsdCBsaW1pdFxuICAgIGlmIChlbnRpdGllcz8ubGltaXQpIHtcbiAgICAgIGlmICh0eXBlb2YgZW50aXRpZXMubGltaXQgPT09ICdudW1iZXInKSBsaW1pdCA9IGVudGl0aWVzLmxpbWl0O1xuICAgICAgZWxzZSBpZiAodHlwZW9mIGVudGl0aWVzLmxpbWl0ID09PSAnc3RyaW5nJykge1xuICAgICAgICBjb25zdCBwYXJzZWRMaW1pdCA9IHBhcnNlSW50KGVudGl0aWVzLmxpbWl0LCAxMCk7XG4gICAgICAgIGlmICghaXNOYU4ocGFyc2VkTGltaXQpKSBsaW1pdCA9IHBhcnNlZExpbWl0O1xuICAgICAgfVxuICAgIH1cbiAgICBjb25zdCBlbWFpbHM6IEVtYWlsW10gPSBhd2FpdCBsaXN0RW1haWxzKGxpbWl0KTtcbiAgICBpZiAoZW1haWxzLmxlbmd0aCA9PT0gMCkge1xuICAgICAgcmV0dXJuICdObyByZWNlbnQgZW1haWxzIGZvdW5kICh2aWEgTkxVKS4nO1xuICAgIH0gZWxzZSB7XG4gICAgICBjb25zdCBlbWFpbExpc3QgPSBlbWFpbHNcbiAgICAgICAgLm1hcChcbiAgICAgICAgICAoZW1haWwpID0+XG4gICAgICAgICAgICBgLSAoJHtlbWFpbC5yZWFkID8gJ3JlYWQnIDogJ3VucmVhZCd9KSBGcm9tOiAke2VtYWlsLnNlbmRlcn0sIFN1YmplY3Q6ICR7ZW1haWwuc3ViamVjdH0gKElEOiAke2VtYWlsLmlkfSlgXG4gICAgICAgIClcbiAgICAgICAgLmpvaW4oJ1xcbicpO1xuICAgICAgcmV0dXJuIGBSZWNlbnQgZW1haWxzICh2aWEgTkxVKTpcXG4ke2VtYWlsTGlzdH1gO1xuICAgIH1cbiAgfSBjYXRjaCAoZXJyb3I6IGFueSkge1xuICAgIHJldHVybiBoYW5kbGVFcnJvcihcbiAgICAgIGVycm9yLFxuICAgICAgXCJTb3JyeSwgSSBjb3VsZG4ndCBmZXRjaCByZWNlbnQgZW1haWxzIGR1ZSB0byBhbiBlcnJvciAoTkxVIHBhdGgpLlwiXG4gICAgKTtcbiAgfVxufVxuXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gaGFuZGxlUmVhZEVtYWlsKGVudGl0aWVzOiBhbnkpOiBQcm9taXNlPHN0cmluZz4ge1xuICB0cnkge1xuICAgIGNvbnN0IHsgZW1haWxfaWQgfSA9IGVudGl0aWVzO1xuICAgIGlmICghZW1haWxfaWQgfHwgdHlwZW9mIGVtYWlsX2lkICE9PSAnc3RyaW5nJykge1xuICAgICAgcmV0dXJuICdFbWFpbCBJRCBpcyByZXF1aXJlZCB0byByZWFkIGFuIGVtYWlsIHZpYSBOTFUuJztcbiAgICB9IGVsc2Uge1xuICAgICAgY29uc3QgcmVzcG9uc2U6IFJlYWRFbWFpbFJlc3BvbnNlID0gYXdhaXQgcmVhZChlbWFpbF9pZCk7XG4gICAgICBpZiAocmVzcG9uc2Uuc3VjY2VzcyAmJiByZXNwb25zZS5lbWFpbCkge1xuICAgICAgICBjb25zdCBlbWFpbCA9IHJlc3BvbnNlLmVtYWlsO1xuICAgICAgICByZXR1cm4gYEVtYWlsIChJRDogJHtlbWFpbC5pZH0pOlxcbkZyb206ICR7ZW1haWwuc2VuZGVyfVxcblRvOiAke2VtYWlsLnJlY2lwaWVudH1cXG5TdWJqZWN0OiAke2VtYWlsLnN1YmplY3R9XFxuRGF0ZTogJHtlbWFpbC50aW1lc3RhbXB9XFxuXFxuJHtlbWFpbC5ib2R5fWA7XG4gICAgICB9IGVsc2Uge1xuICAgICAgICByZXR1cm4gcmVzcG9uc2UubWVzc2FnZSB8fCAnQ291bGQgbm90IHJlYWQgZW1haWwgdmlhIE5MVS4nO1xuICAgICAgfVxuICAgIH1cbiAgfSBjYXRjaCAoZXJyb3I6IGFueSkge1xuICAgIHJldHVybiBoYW5kbGVFcnJvcihcbiAgICAgIGVycm9yLFxuICAgICAgXCJTb3JyeSwgSSBjb3VsZG4ndCByZWFkIHRoZSBzcGVjaWZpZWQgZW1haWwgZHVlIHRvIGFuIGVycm9yIChOTFUgcGF0aCkuXCJcbiAgICApO1xuICB9XG59XG5cbmV4cG9ydCBhc3luYyBmdW5jdGlvbiBoYW5kbGVTZW5kRW1haWwoZW50aXRpZXM6IGFueSk6IFByb21pc2U8c3RyaW5nPiB7XG4gIHRyeSB7XG4gICAgY29uc3QgeyB0bywgc3ViamVjdCwgYm9keSB9ID0gZW50aXRpZXM7XG4gICAgaWYgKCF0byB8fCB0eXBlb2YgdG8gIT09ICdzdHJpbmcnKSB7XG4gICAgICByZXR1cm4gXCJSZWNpcGllbnQgJ3RvJyBhZGRyZXNzIGlzIHJlcXVpcmVkIHRvIHNlbmQgYW4gZW1haWwgdmlhIE5MVS5cIjtcbiAgICB9IGVsc2UgaWYgKCFzdWJqZWN0IHx8IHR5cGVvZiBzdWJqZWN0ICE9PSAnc3RyaW5nJykge1xuICAgICAgcmV0dXJuICdTdWJqZWN0IGlzIHJlcXVpcmVkIHRvIHNlbmQgYW4gZW1haWwgdmlhIE5MVS4nO1xuICAgIH0gZWxzZSBpZiAoIWJvZHkgfHwgdHlwZW9mIGJvZHkgIT09ICdzdHJpbmcnKSB7XG4gICAgICByZXR1cm4gJ0JvZHkgaXMgcmVxdWlyZWQgdG8gc2VuZCBhbiBlbWFpbCB2aWEgTkxVLic7XG4gICAgfSBlbHNlIHtcbiAgICAgIGNvbnN0IGVtYWlsRGV0YWlsczogRW1haWxEZXRhaWxzID0geyB0bywgc3ViamVjdCwgYm9keSB9O1xuICAgICAgY29uc3QgcmVzcG9uc2U6IFNlbmRFbWFpbFJlc3BvbnNlID0gYXdhaXQgc2VuZChlbWFpbERldGFpbHMpO1xuICAgICAgaWYgKHJlc3BvbnNlLnN1Y2Nlc3MpIHtcbiAgICAgICAgcmV0dXJuIGBFbWFpbCBzZW50IHZpYSBOTFU6ICR7cmVzcG9uc2UubWVzc2FnZX0gKElEOiAke3Jlc3BvbnNlLmVtYWlsSWR9KWA7XG4gICAgICB9IGVsc2Uge1xuICAgICAgICByZXR1cm4gYEZhaWxlZCB0byBzZW5kIGVtYWlsIHZpYSBOTFU6ICR7cmVzcG9uc2UubWVzc2FnZX1gO1xuICAgICAgfVxuICAgIH1cbiAgfSBjYXRjaCAoZXJyb3I6IGFueSkge1xuICAgIHJldHVybiBoYW5kbGVFcnJvcihcbiAgICAgIGVycm9yLFxuICAgICAgXCJTb3JyeSwgSSBjb3VsZG4ndCBzZW5kIHRoZSBlbWFpbCBkdWUgdG8gYW4gZXJyb3IgKE5MVSBwYXRoKS5cIlxuICAgICk7XG4gIH1cbn1cbiJdfQ==