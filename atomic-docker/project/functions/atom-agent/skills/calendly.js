import { listCalendlyEventTypes as listTypes, listCalendlyScheduledEvents as listScheduled, } from './calendlySkills';
import { handleError } from '../../_utils/errorHandler';
export async function handleListCalendlyEventTypes(userId, entities) {
    try {
        const calendlyUserId = entities?.user_id && typeof entities.user_id === 'string'
            ? entities.user_id
            : userId;
        const response = await listTypes(calendlyUserId);
        if (response.ok && response.collection && response.collection.length > 0) {
            let output = 'Your Calendly Event Types (via NLU):\n';
            for (const et of response.collection) {
                output += `- ${et.name} (${et.duration} mins) - Active: ${et.active} - URL: ${et.scheduling_url}\n`;
            }
            if (response.pagination?.next_page_token) {
                output += `More event types available. Use next page token: ${response.pagination.next_page_token}\n`;
            }
            return output;
        }
        else if (response.ok) {
            return 'No active Calendly event types found (via NLU).';
        }
        else {
            return `Error fetching Calendly event types (via NLU): ${response.error || 'Unknown error'}`;
        }
    }
    catch (error) {
        return handleError(error, 'Sorry, an unexpected error occurred while fetching your Calendly event types (NLU path).');
    }
}
export async function handleListCalendlyScheduledEvents(userId, entities) {
    try {
        const calendlyUserId = entities?.user_id && typeof entities.user_id === 'string'
            ? entities.user_id
            : userId;
        const count = entities?.count && typeof entities.count === 'number'
            ? entities.count
            : 10;
        const status = entities?.status && typeof entities.status === 'string'
            ? entities.status
            : 'active';
        const sort = entities?.sort && typeof entities.sort === 'string'
            ? entities.sort
            : 'start_time:asc';
        const options = { count, status, sort, user: calendlyUserId };
        const response = await listScheduled(calendlyUserId, options);
        if (response.ok && response.collection && response.collection.length > 0) {
            let output = `Your Calendly Bookings (${status}, via NLU):\n`;
            for (const se of response.collection) {
                output += `- ${se.name} (Starts: ${new Date(se.start_time).toLocaleString()}, Ends: ${new Date(se.end_time).toLocaleString()}) - Status: ${se.status}\n`;
            }
            if (response.pagination?.next_page_token) {
                output += `More bookings available. Use next page token: ${response.pagination.next_page_token}\n`;
            }
            return output;
        }
        else if (response.ok) {
            return `No ${status} scheduled Calendly bookings found (via NLU).`;
        }
        else {
            return `Error fetching Calendly bookings (via NLU): ${response.error || 'Unknown error'}`;
        }
    }
    catch (error) {
        return handleError(error, 'Sorry, an unexpected error occurred while fetching your Calendly bookings (NLU path).');
    }
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiY2FsZW5kbHkuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJjYWxlbmRseS50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiQUFJQSxPQUFPLEVBQ0wsc0JBQXNCLElBQUksU0FBUyxFQUNuQywyQkFBMkIsSUFBSSxhQUFhLEdBQzdDLE1BQU0sa0JBQWtCLENBQUM7QUFDMUIsT0FBTyxFQUFFLFdBQVcsRUFBRSxNQUFNLDJCQUEyQixDQUFDO0FBRXhELE1BQU0sQ0FBQyxLQUFLLFVBQVUsNEJBQTRCLENBQ2hELE1BQWMsRUFDZCxRQUFhO0lBRWIsSUFBSSxDQUFDO1FBQ0gsTUFBTSxjQUFjLEdBQ2xCLFFBQVEsRUFBRSxPQUFPLElBQUksT0FBTyxRQUFRLENBQUMsT0FBTyxLQUFLLFFBQVE7WUFDdkQsQ0FBQyxDQUFDLFFBQVEsQ0FBQyxPQUFPO1lBQ2xCLENBQUMsQ0FBQyxNQUFNLENBQUM7UUFDYixNQUFNLFFBQVEsR0FDWixNQUFNLFNBQVMsQ0FBQyxjQUFjLENBQUMsQ0FBQztRQUNsQyxJQUFJLFFBQVEsQ0FBQyxFQUFFLElBQUksUUFBUSxDQUFDLFVBQVUsSUFBSSxRQUFRLENBQUMsVUFBVSxDQUFDLE1BQU0sR0FBRyxDQUFDLEVBQUUsQ0FBQztZQUN6RSxJQUFJLE1BQU0sR0FBRyx3Q0FBd0MsQ0FBQztZQUN0RCxLQUFLLE1BQU0sRUFBRSxJQUFJLFFBQVEsQ0FBQyxVQUFVLEVBQUUsQ0FBQztnQkFDckMsTUFBTSxJQUFJLEtBQUssRUFBRSxDQUFDLElBQUksS0FBSyxFQUFFLENBQUMsUUFBUSxvQkFBb0IsRUFBRSxDQUFDLE1BQU0sV0FBVyxFQUFFLENBQUMsY0FBYyxJQUFJLENBQUM7WUFDdEcsQ0FBQztZQUNELElBQUksUUFBUSxDQUFDLFVBQVUsRUFBRSxlQUFlLEVBQUUsQ0FBQztnQkFDekMsTUFBTSxJQUFJLG9EQUFvRCxRQUFRLENBQUMsVUFBVSxDQUFDLGVBQWUsSUFBSSxDQUFDO1lBQ3hHLENBQUM7WUFDRCxPQUFPLE1BQU0sQ0FB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YWxlbmRseUV2ZW50VHlwZXNSZXNwb25zZSxcbiAgTGlzdENhbGVuZGx5U2NoZWR1bGVkRXZlbnRzUmVzcG9uc2UsXG59IGZyb20gJy4uLy4uL3R5cGVzJztcbmltcG9ydCB7XG4gIGxpc3RDYWxlbmRseUV2ZW50VHlwZXMgYXMgbGlzdFR5cGVzLFxuICBsaXN0Q2FsZW5kbHlTY2hlZHVsZWRFdmVudHMgYXMgbGlzdFNjaGVkdWxlZCxcbn0gZnJvbSAnLi9jYWxlbmRseVNraWxscyc7XG5pbXBvcnQgeyBoYW5kbGVFcnJvciB9IGZyb20gJy4uLy4uL191dGlscy9lcnJvckhhbmRsZXInO1xuXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gaGFuZGxlTGlzdENhbGVuZGx5RXZlbnRUeXBlcyhcbiAgdXNlcklkOiBzdHJpbmcsXG4gIGVudGl0aWVzOiBhbnlcbik6IFByb21pc2U8c3RyaW5nPiB7XG4gIHRyeSB7XG4gICAgY29uc3QgY2FsZW5kbHlVc2VySWQgPVxuICAgICAgZW50aXRpZXM/LnVzZXJfaWQgJiYgdHlwZW9mIGVudGl0aWVzLnVzZXJfaWQgPT09ICdzdHJpbmcnXG4gICAgICAgID8gZW50aXRpZXMudXNlcl9pZFxuICAgICAgICA6IHVzZXJJZDtcbiAgICBjb25zdCByZXNwb25zZTogTGlzdENhbGVuZGx5RXZlbnRUeXBlc1Jlc3BvbnNlID1cbiAgICAgIGF3YWl0IGxpc3RUeXBlcyhjYWxlbmRseVVzZXJJZCk7XG4gICAgaWYgKHJlc3BvbnNlLm9rICYmIHJlc3BvbnNlLmNvbGxlY3Rpb24gJiYgcmVzcG9uc2UuY29sbGVjdGlvbi5sZW5ndGggPiAwKSB7XG4gICAgICBsZXQgb3V0cHV0ID0gJ1lvdXIgQ2FsZW5kbHkgRXZlbnQgVHlwZXMgKHZpYSBOTFUpOlxcbic7XG4gICAgICBmb3IgKGNvbnN0IGV0IG9mIHJlc3BvbnNlLmNvbGxlY3Rpb24pIHtcbiAgICAgICAgb3V0cHV0ICs9IGAtICR7ZXQubmFtZX0gKCR7ZXQuZHVyYXRpb259IG1pbnMpIC0gQWN0aXZlOiAke2V0LmFjdGl2ZX0gLSBVUkw6ICR7ZXQuc2NoZWR1bGluZ191cmx9XFxuYDtcbiAgICAgIH1cbiAgICAgIGlmIChyZXNwb25zZS5wYWdpbmF0aW9uPy5uZXh0X3BhZ2VfdG9rZW4pIHtcbiAgICAgICAgb3V0cHV0ICs9IGBNb3JlIGV2ZW50IHR5cGVzIGF2YWlsYWJsZS4gVXNlIG5leHQgcGFnZSB0b2tlbjogJHtyZXNwb25zZS5wYWdpbmF0aW9uLm5leHRfcGFnZV90b2tlbn1cXG5gO1xuICAgICAgfVxuICAgICAgcmV0dXJuIG91dHB1dDtcbiAgICB9IGVsc2UgaWYgKHJlc3BvbnNlLm9rKSB7XG4gICAgICByZXR1cm4gJ05vIGFjdGl2ZSBDYWxlbmRseSBldmVudCB0eXBlcyBmb3VuZCAodmlhIE5MVSkuJztcbiAgICB9IGVsc2Uge1xuICAgICAgcmV0dXJuIGBFcnJvciBmZXRjaGluZyBDYWxlbmRseSBldmVudCB0eXBlcyAodmlhIE5MVSk6ICR7cmVzcG9uc2UuZXJyb3IgfHwgJ1Vua25vd24gZXJyb3InfWA7XG4gICAgfVxuICB9IGNhdGNoIChlcnJvcjogYW55KSB7XG4gICAgcmV0dXJuIGhhbmRsZUVycm9yKFxuICAgICAgZXJyb3IsXG4gICAgICAnU29ycnksIGFuIHVuZXhwZWN0ZWQgZXJyb3Igb2NjdXJyZWQgd2hpbGUgZmV0Y2hpbmcgeW91ciBDYWxlbmRseSBldmVudCB0eXBlcyAoTkxVIHBhdGgpLidcbiAgICApO1xuICB9XG59XG5cbmV4cG9ydCBhc3luYyBmdW5jdGlvbiBoYW5kbGVMaXN0Q2FsZW5kbHlTY2hlZHVsZWRFdmVudHMoXG4gIHVzZXJJZDogc3RyaW5nLFxuICBlbnRpdGllczogYW55XG4pOiBQcm9taXNlPHN0cmluZz4ge1xuICB0cnkge1xuICAgIGNvbnN0IGNhbGVuZGx5VXNlcklkID1cbiAgICAgIGVudGl0aWVzPy51c2VyX2lkICYmIHR5cGVvZiBlbnRpdGllcy51c2VyX2lkID09PSAnc3RyaW5nJ1xuICAgICAgICA/IGVudGl0aWVzLnVzZXJfaWRcbiAgICAgICAgOiB1c2VySWQ7XG4gICAgY29uc3QgY291bnQgPVxuICAgICAgZW50aXRpZXM/LmNvdW50ICYmIHR5cGVvZiBlbnRpdGllcy5jb3VudCA9PT0gJ251bWJlcidcbiAgICAgICAgPyBlbnRpdGllcy5jb3VudFxuICAgICAgICA6IDEwO1xuICAgIGNvbnN0IHN0YXR1cyA9XG4gICAgICBlbnRpdGllcz8uc3RhdHVzICYmIHR5cGVvZiBlbnRpdGllcy5zdGF0dXMgPT09ICdzdHJpbmcnXG4gICAgICAgID8gKGVudGl0aWVzLnN0YXR1cyBhcyAnYWN0aXZlJyB8ICdjYW5jZWxlZCcpXG4gICAgICAgIDogJ2FjdGl2ZSc7XG4gICAgY29uc3Qgc29ydCA9XG4gICAgICBlbnRpdGllcz8uc29ydCAmJiB0eXBlb2YgZW50aXRpZXMuc29ydCA9PT0gJ3N0cmluZydcbiAgICAgICAgPyBlbnRpdGllcy5zb3J0XG4gICAgICAgIDogJ3N0YXJ0X3RpbWU6YXNjJztcbiAgICBjb25zdCBvcHRpb25zID0geyBjb3VudCwgc3RhdHVzLCBzb3J0LCB1c2VyOiBjYWxlbmRseVVzZXJJZCB9O1xuICAgIGNvbnN0IHJlc3BvbnNlOiBMaXN0Q2FsZW5kbHlTY2hlZHVsZWRFdmVudHNSZXNwb25zZSA9IGF3YWl0IGxpc3RTY2hlZHVsZWQoXG4gICAgICBjYWxlbmRseVVzZXJJZCxcbiAgICAgIG9wdGlvbnNcbiAgICApO1xuICAgIGlmIChyZXNwb25zZS5vayAmJiByZXNwb25zZS5jb2xsZWN0aW9uICYmIHJlc3BvbnNlLmNvbGxlY3Rpb24ubGVuZ3RoID4gMCkge1xuICAgICAgbGV0IG91dHB1dCA9IGBZb3VyIENhbGVuZGx5IEJvb2tpbmdzICgke3N0YXR1c30sIHZpYSBOTFUpOlxcbmA7XG4gICAgICBmb3IgKGNvbnN0IHNlIG9mIHJlc3BvbnNlLmNvbGxlY3Rpb24pIHtcbiAgICAgICAgb3V0cHV0ICs9IGAtICR7c2UubmFtZX0gKFN0YXJ0czogJHtuZXcgRGF0ZShzZS5zdGFydF90aW1lKS50b0xvY2FsZVN0cmluZygpfSwgRW5kczogJHtuZXcgRGF0ZShzZS5lbmRfdGltZSkudG9Mb2NhbGVTdHJpbmcoKX0pIC0gU3RhdHVzOiAke3NlLnN0YXR1c31cXG5gO1xuICAgICAgfVxuICAgICAgaWYgKHJlc3BvbnNlLnBhZ2luYXRpb24/Lm5leHRfcGFnZV90b2tlbikge1xuICAgICAgICBvdXRwdXQgKz0gYE1vcmUgYm9va2luZ3MgYXZhaWxhYmxlLiBVc2UgbmV4dCBwYWdlIHRva2VuOiAke3Jlc3BvbnNlLnBhZ2luYXRpb24ubmV4dF9wYWdlX3Rva2VufVxcbmA7XG4gICAgICB9XG4gICAgICByZXR1cm4gb3V0cHV0O1xuICAgIH0gZWxzZSBpZiAocmVzcG9uc2Uub2spIHtcbiAgICAgIHJldHVybiBgTm8gJHtzdGF0dXN9IHNjaGVkdWxlZCBDYWxlbmRseSBib29raW5ncyBmb3VuZCAodmlhIE5MVSkuYDtcbiAgICB9IGVsc2Uge1xuICAgICAgcmV0dXJuIGBFcnJvciBmZXRjaGluZyBDYWxlbmRseSBib29raW5ncyAodmlhIE5MVSk6ICR7cmVzcG9uc2UuZXJyb3IgfHwgJ1Vua25vd24gZXJyb3InfWA7XG4gICAgfVxuICB9IGNhdGNoIChlcnJvcjogYW55KSB7XG4gICAgcmV0dXJuIGhhbmRsZUVycm9yKFxuICAgICAgZXJyb3IsXG4gICAgICAnU29ycnksIGFuIHVuZXhwZWN0ZWQgZXJyb3Igb2NjdXJyZWQgd2hpbGUgZmV0Y2hpbmcgeW91ciBDYWxlbmRseSBib29raW5ncyAoTkxVIHBhdGgpLidcbiAgICApO1xuICB9XG59XG4iXX0=