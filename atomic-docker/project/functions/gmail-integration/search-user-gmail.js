// Adjust path to where gmail-service/service.ts is located relative to this file
import { searchUserEmails } from '../gmail-service/service';
const handler = async (req, res) => {
    const userId = req.body.session_variables['x-hasura-user-id'];
    const { query, maxResults = 10 } = req.body.input; // Default maxResults to 10
    if (!userId) {
        return res
            .status(401)
            .json({ success: false, message: 'User ID is missing. Unauthorized.' });
    }
    if (!query || typeof query !== 'string' || query.trim() === '') {
        return res
            .status(400)
            .json({ success: false, message: 'Search query is missing or invalid.' });
    }
    if (maxResults !== undefined &&
        (typeof maxResults !== 'number' || maxResults <= 0 || maxResults > 100)) {
        return res
            .status(400)
            .json({
            success: false,
            message: 'maxResults must be a positive number, not exceeding 100.',
        });
    }
    try {
        // searchUserEmails is expected to return an array of gmail_v1.Schema$Message
        const rawMessages = await searchUserEmails(userId, query, maxResults);
        // Transform the raw Gmail API messages to our GmailSearchResultItem structure.
        // The current searchUserEmails (from service.ts) might only fetch basic message list (IDs, threadId).
        // To populate snippet, subject, from, date, searchUserEmails would need to be enhanced,
        // or we'd make additional calls here (which is N+1 and inefficient for a list).
        // For this step, we primarily rely on what messages.list provides (id, threadId, snippet).
        const results = rawMessages.map((msg) => ({
            id: msg.id || 'N/A', // Gmail message ID is crucial
            threadId: msg.threadId || undefined,
            snippet: msg.snippet || undefined,
            // These are placeholders as messages.list doesn't usually provide them directly.
            // Populating these would require modifying searchUserEmails to fetch more details or
            // making individual gmail.users.messages.get calls.
            subject: `Subject for ${msg.id}`, // Placeholder
            from: 'Sender placeholder', // Placeholder
            date: new Date().toISOString(), // Placeholder
        }));
        return res.status(200).json({
            success: true,
            results: results,
        });
    }
    catch (e) {
        console.error(`Error in searchUserGmail handler for user ${userId}:`, e);
        const errorMessage = e.message || 'An unexpected error occurred while searching emails.';
        // Check if the error message indicates an authentication issue from getGmailClientForUser
        if (errorMessage.includes('Failed to get authenticated Gmail client') ||
            errorMessage.includes('User needs to authorize')) {
            return res
                .status(401)
                .json({
                success: false,
                message: 'Gmail authentication failed or is required. Please connect/reconnect your Gmail account via settings.',
            });
        }
        return res.status(500).json({
            success: false,
            message: errorMessage,
        });
    }
};
export default handler;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoic2VhcmNoLXVzZXItZ21haWwuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJzZWFyY2gtdXNlci1nbWFpbC50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiQUFDQSxpRkFBaUY7QUFDakYsT0FBTyxFQUFFLGdCQUFnQixFQUFFLE1BQU0sMEJBQTBCLENBQUM7QUFpQzVELE1BQU0sT0FBTyxHQUFHLEtBQUssRUFDbkIsR0FBZ0QsRUFDaEQsR0FBc0MsRUFDdEMsRUFBRTtJQUNGLE1BQU0sTUFBTSxHQUFHLEdBQUcsQ0FBQyxJQUFJLENBQUMsaUJBQWlCLENBQUMsa0JBQWtCLENBQUMsQ0FBQztJQUM5RCxNQUFNLEVBQUUsS0FBSyxFQUFFLFVBQVUsR0FBRyxFQUFFLEVBQUUsR0FBRyxHQUFHLENBQUMsSUFBSSxDQUFDLEtBQUssQ0FBQyxDQUFDLDJCQUEyQjtJQUU5RSxJQUFJLENBQUMsTUFBTSxFQUFFLENBQUM7UUFDWixPQUFPLEdBQUc7YUFDUCxNQUFNLENBQUMsR0FBRyxDQUFDO2FBQ1gsSUFBSSxDQUFDLEVBQUUsT0FBTyxFQUFFLEtBQUssRUFBRSxPQUFPLEVBQUUsbUNBQW1DLEVBQUUsQ0FBQyxDQUFDO0lBQzVFLENBQUM7SUFDRCxJQUFJLENBQUMsS0FBSyxJQUFJLE9BQU8sS0FBSyxLQUFLLFFBQVEsSUFBSSxLQUFLLENBQUMsSUFBSSxFQUFFLEtBQUssRUFBRSxFQUFFLENBQUM7UUFDL0QsT0FBTyxHQUFHO2FBQ1AsTUFBTSxDQUFDLEdBQUcsQ0FBQzthQUNYLElBQUksQ0FBQyxFQUFFLE9BQU8sRUFBRSxLQUFLLEVBQUUsT0FBTyxFQUFFLHFDQUFxQyxFQUFFLENBQUMsQ0FBQztJQUM5RSxDQUFDO0lBQ0QsSUFDRSxVQUFVLEtBQUssU0FBUztRQUN4QixDQUFDLE9BQU8sVUFBVSxLQUFLLFFBQVEsSUFBSSxVQUFVLElBQUksQ0FBQyxJQUFJLFVBQVUsR0FBRyxHQUFHLENBQUMsRUFDdkUsQ0FBQztRQUNELE9BQU8sR0FBRzthQUNQLE1BQU0sQ0FBQyxHQUFHLENBQUM7YUFDWCxJQUFJLENBQUM7WUFDSixPQUFPLEVBQUUsS0FBSztZQUNkLE9BQU8sRUFBRSwwREFBMEQ7U0FDcEUsQ0FBQyxDQUFDO0lBQ1AsQ0FBQztJQUVELElBQUksQ0FBQztRQUNILDZFQUE2RTtRQUM3RSxNQUFNLFdBQVcsR0FBOEIsTUFBTSxnQkFBZ0IsQ0FDbkUsTUFBTSxFQUNOLEtBQUssRUFDTCxVQUFVLENBQ1gsQ0FBQztRQUVGLCtFQUErRTtRQUMvRSxzR0FBc0c7UUFDdEcsd0ZBQXdGO1FBQ3hGLGdGQUFnRjtRQUNoRiwyRkFBMkY7UUFDM0YsTUFBTSxPQUFPLEdBQTRCLFdBQVcsQ0FBQyxHQUFHLENBQ3RELENBQUMsR0FBNEIsRUFBRSxFQUFFLENBQUMsQ0FBQztZQUNqQyxFQUFFLEVBQUUsR0FBRyxDQUFDLEVBQUUsSUFBSSxLQUFLLEVBQUUsOEJBQThCO1lBQ25ELFFBQVEsRUFBRSxHQUFHLENBQUMsUUFBUSxJQUFJLFNBQVM7WUFDbkMsT0FBTyxFQUFFLEdBQUcsQ0FBQyxPQUFPLElBQUksU0FBUztZQUNqQyxpRkFBaUY7WUFDakYscUZBQXFGO1lBQ3JGLG9EQUFvRDtZQUNwRCxPQUFPLEVBQUUsZUFBZSxHQUFHLENBQUMsRUFBRSxFQUFFLEVBQUUsY0FBYztZQUNoRCxJQUFJLEVBQUUsb0JBQW9CLEVBQUUsY0FBYztZQUMxQyxJQUFJLEVBQUUsSUFBSSxJQUFJLEVBQUUsQ0FBQyxXQUFXLEVBQUUsRUFBRSxjQUFjO1NBQy9DLENBQUMsQ0FDSCxDQUFDO1FBRUYsT0FBTyxHQUFHLENBQUMsTUFBTSxDQUFDLEdBQUcsQ0FBQyxDQUFDLElBQUksQ0FBQztZQUMxQixPQUFPLEVBQUUsSUFBSTtZQUNiLE9BQU8sRUFBRSxPQUFPO1NBQ2pCLENBQUMsQ0FBQztJQUNMLENBQUM7SUFBQyxPQUFPLENBQU0sRUFBRSxDQUFDO1FBQ2hCLE9BQU8sQ0FBQyxLQUFLLENBQUMsNkNBQTZDLE1BQU0sR0FBRyxFQUFFLENBQUMsQ0FBQyxDQUFDO1FBQ3pFLE1BQU0sWUFBWSxHQUNoQixDQUFDLENBQUMsT0FBTyxJQUFJLHNEQUFzRCxDQUFDO1FBRXRFLDBGQUEwRjtRQUMxRixJQUNFLFlBQVksQ0FBQyxRQUFRLENBQUMsMENBQTBDLENBQUM7WUFDakUsWUFBWSxDQUFDLFFBQVEsQ0FBQyx5QkFBeUIsQ0FBQyxFQUNoRCxDQUFDO1lBQ0QsT0FBTyxHQUFHO2lCQUNQLE1BQU0sQ0FBQyxHQUFHLENBQUM7aUJBQ1gsSUFBSSxDQUFDO2dCQUNKLE9BQU8sRUFBRSxLQUFLO2dCQUNkLE9BQU8sRUFDTCx1R0FBdUc7YUFDMUcsQ0FBQyxDQUFDO1FBQ1AsQ0FBQztRQUVELE9BQU8sR0FBRyxDQUFDLE1BQU0sQ0FBQyxHQUFHLENBQUMsQ0FBQyxJQUFJLENBQUM7WUFDMUIsT0FBTyxFQUFFLEtBQUs7WUFDZCxPQUFPLEVBQUUsWUFBWTtTQUN0QixDQUFDLENBQUM7SUFDTCxDQUFDO0FBQ0gsQ0FBQyxDQUFDO0FBRUYsZUFBZSxPQUFPLENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgeyBSZXF1ZXN0LCBSZXNwb25zZSB9IGZyb20gJ2V4cHJlc3MnO1xuLy8gQWRqdXN0IHBhdGggdG8gd2hlcmUgZ21haWwtc2VydmljZS9zZXJ2aWNlLnRzIGlzIGxvY2F0ZWQgcmVsYXRpdmUgdG8gdGhpcyBmaWxlXG5pbXBvcnQgeyBzZWFyY2hVc2VyRW1haWxzIH0gZnJvbSAnLi4vZ21haWwtc2VydmljZS9zZXJ2aWNlJztcbmltcG9ydCB7IGdtYWlsX3YxIH0gZnJvbSAnZ29vZ2xlYXBpcyc7IC8vIEZvciB0eXBpbmcgR29vZ2xlJ3MgbWVzc2FnZSBvYmplY3RcblxuLy8gRGVmaW5lIGV4cGVjdGVkIGlucHV0IHN0cnVjdHVyZSBmcm9tIEhhc3VyYSBhY3Rpb24sIG1hdGNoaW5nIEdtYWlsU2VhcmNoUXVlcnlJbnB1dFxuaW50ZXJmYWNlIFNlYXJjaFVzZXJHbWFpbElucHV0IHtcbiAgcXVlcnk6IHN0cmluZztcbiAgbWF4UmVzdWx0cz86IG51bWJlcjtcbn1cblxuaW50ZXJmYWNlIFNlYXJjaFVzZXJHbWFpbFJlcXVlc3RCb2R5IHtcbiAgc2Vzc2lvbl92YXJpYWJsZXM6IHtcbiAgICAneC1oYXN1cmEtdXNlci1pZCc6IHN0cmluZztcbiAgfTtcbiAgaW5wdXQ6IFNlYXJjaFVzZXJHbWFpbElucHV0O1xufVxuXG4vLyBEZWZpbmUgdGhlIHN0cnVjdHVyZSBmb3IgYSBzaW5nbGUgc2VhcmNoIHJlc3VsdCBpdGVtLCBtYXRjaGluZyBHbWFpbFNlYXJjaFJlc3VsdEl0ZW1cbmludGVyZmFjZSBHbWFpbFNlYXJjaFJlc3VsdEl0ZW0ge1xuICBpZDogc3RyaW5nO1xuICB0aHJlYWRJZD86IHN0cmluZztcbiAgc25pcHBldD86IHN0cmluZztcbiAgc3ViamVjdD86IHN0cmluZzsgLy8gUGxhY2Vob2xkZXIsIG5lZWRzIGFjdHVhbCBkYXRhIGZldGNoaW5nXG4gIGZyb20/OiBzdHJpbmc7IC8vIFBsYWNlaG9sZGVyLCBuZWVkcyBhY3R1YWwgZGF0YSBmZXRjaGluZ1xuICBkYXRlPzogc3RyaW5nOyAvLyBQbGFjZWhvbGRlciwgbmVlZHMgYWN0dWFsIGRhdGEgZmV0Y2hpbmdcbn1cblxuLy8gRGVmaW5lIHRoZSBvdXRwdXQgc3RydWN0dXJlIG1hdGNoaW5nIEdtYWlsU2VhcmNoT3V0cHV0IGluIEdyYXBoUUxcbmludGVyZmFjZSBTZWFyY2hVc2VyR21haWxSZXNwb25zZSB7XG4gIHN1Y2Nlc3M6IGJvb2xlYW47XG4gIG1lc3NhZ2U/OiBzdHJpbmc7XG4gIHJlc3VsdHM/OiBHbWFpbFNlYXJjaFJlc3VsdEl0ZW1bXTtcbn1cblxuY29uc3QgaGFuZGxlciA9IGFzeW5jIChcbiAgcmVxOiBSZXF1ZXN0PHt9LCB7fSwgU2VhcmNoVXNlckdtYWlsUmVxdWVzdEJvZHk+LFxuICByZXM6IFJlc3BvbnNlPFNlYXJjaFVzZXJHbWFpbFJlc3BvbnNlPlxuKSA9PiB7XG4gIGNvbnN0IHVzZXJJZCA9IHJlcS5ib2R5LnNlc3Npb25fdmFyaWFibGVzWyd4LWhhc3VyYS11c2VyLWlkJ107XG4gIGNvbnN0IHsgcXVlcnksIG1heFJlc3VsdHMgPSAxMCB9ID0gcmVxLmJvZHkuaW5wdXQ7IC8vIERlZmF1bHQgbWF4UmVzdWx0cyB0byAxMFxuXG4gIGlmICghdXNlcklkKSB7XG4gICAgcmV0dXJuIHJlc1xuICAgICAgLnN0YXR1cyg0MDEpXG4gICAgICAuanNvbih7IHN1Y2Nlc3M6IGZhbHNlLCBtZXNzYWdlOiAnVXNlciBJRCBpcyBtaXNzaW5nLiBVbmF1dGhvcml6ZWQuJyB9KTtcbiAgfVxuICBpZiAoIXF1ZXJ5IHx8IHR5cGVvZiBxdWVyeSAhPT0gJ3N0cmluZycgfHwgcXVlcnkudHJpbSgpID09PSAnJykge1xuICAgIHJldHVybiByZXNcbiAgICAgIC5zdGF0dXMoNDAwKVxuICAgICAgLmpzb24oeyBzdWNjZXNzOiBmYWxzZSwgbWVzc2FnZTogJ1NlYXJjaCBxdWVyeSBpcyBtaXNzaW5nIG9yIGludmFsaWQuJyB9KTtcbiAgfVxuICBpZiAoXG4gICAgbWF4UmVzdWx0cyAhPT0gdW5kZWZpbmVkICYmXG4gICAgKHR5cGVvZiBtYXhSZXN1bHRzICE9PSAnbnVtYmVyJyB8fCBtYXhSZXN1bHRzIDw9IDAgfHwgbWF4UmVzdWx0cyA+IDEwMClcbiAgKSB7XG4gICAgcmV0dXJuIHJlc1xuICAgICAgLnN0YXR1cyg0MDApXG4gICAgICAuanNvbih7XG4gICAgICAgIHN1Y2Nlc3M6IGZhbHNlLFxuICAgICAgICBtZXNzYWdlOiAnbWF4UmVzdWx0cyBtdXN0IGJlIGEgcG9zaXRpdmUgbnVtYmVyLCBub3QgZXhjZWVkaW5nIDEwMC4nLFxuICAgICAgfSk7XG4gIH1cblxuICB0cnkge1xuICAgIC8vIHNlYXJjaFVzZXJFbWFpbHMgaXMgZXhwZWN0ZWQgdG8gcmV0dXJuIGFuIGFycmF5IG9mIGdtYWlsX3YxLlNjaGVtYSRNZXNzYWdlXG4gICAgY29uc3QgcmF3TWVzc2FnZXM6IGdtYWlsX3YxLlNjaGVtYSRNZXNzYWdlW10gPSBhd2FpdCBzZWFyY2hVc2VyRW1haWxzKFxuICAgICAgdXNlcklkLFxuICAgICAgcXVlcnksXG4gICAgICBtYXhSZXN1bHRzXG4gICAgKTtcblxuICAgIC8vIFRyYW5zZm9ybSB0aGUgcmF3IEdtYWlsIEFQSSBtZXNzYWdlcyB0byBvdXIgR21haWxTZWFyY2hSZXN1bHRJdGVtIHN0cnVjdHVyZS5cbiAgICAvLyBUaGUgY3VycmVudCBzZWFyY2hVc2VyRW1haWxzIChmcm9tIHNlcnZpY2UudHMpIG1pZ2h0IG9ubHkgZmV0Y2ggYmFzaWMgbWVzc2FnZSBsaXN0IChJRHMsIHRocmVhZElkKS5cbiAgICAvLyBUbyBwb3B1bGF0ZSBzbmlwcGV0LCBzdWJqZWN0LCBmcm9tLCBkYXRlLCBzZWFyY2hVc2VyRW1haWxzIHdvdWxkIG5lZWQgdG8gYmUgZW5oYW5jZWQsXG4gICAgLy8gb3Igd2UnZCBtYWtlIGFkZGl0aW9uYWwgY2FsbHMgaGVyZSAod2hpY2ggaXMgTisxIGFuZCBpbmVmZmljaWVudCBmb3IgYSBsaXN0KS5cbiAgICAvLyBGb3IgdGhpcyBzdGVwLCB3ZSBwcmltYXJpbHkgcmVseSBvbiB3aGF0IG1lc3NhZ2VzLmxpc3QgcHJvdmlkZXMgKGlkLCB0aHJlYWRJZCwgc25pcHBldCkuXG4gICAgY29uc3QgcmVzdWx0czogR21haWxTZWFyY2hSZXN1bHRJdGVtW10gPSByYXdNZXNzYWdlcy5tYXAoXG4gICAgICAobXNnOiBnbWFpbF92MS5TY2hlbWEkTWVzc2FnZSkgPT4gKHtcbiAgICAgICAgaWQ6IG1zZy5pZCB8fCAnTi9BJywgLy8gR21haWwgbWVzc2FnZSBJRCBpcyBjcnVjaWFsXG4gICAgICAgIHRocmVhZElkOiBtc2cudGhyZWFkSWQgfHwgdW5kZWZpbmVkLFxuICAgICAgICBzbmlwcGV0OiBtc2cuc25pcHBldCB8fCB1bmRlZmluZWQsXG4gICAgICAgIC8vIFRoZXNlIGFyZSBwbGFjZWhvbGRlcnMgYXMgbWVzc2FnZXMubGlzdCBkb2Vzbid0IHVzdWFsbHkgcHJvdmlkZSB0aGVtIGRpcmVjdGx5LlxuICAgICAgICAvLyBQb3B1bGF0aW5nIHRoZXNlIHdvdWxkIHJlcXVpcmUgbW9kaWZ5aW5nIHNlYXJjaFVzZXJFbWFpbHMgdG8gZmV0Y2ggbW9yZSBkZXRhaWxzIG9yXG4gICAgICAgIC8vIG1ha2luZyBpbmRpdmlkdWFsIGdtYWlsLnVzZXJzLm1lc3NhZ2VzLmdldCBjYWxscy5cbiAgICAgICAgc3ViamVjdDogYFN1YmplY3QgZm9yICR7bXNnLmlkfWAsIC8vIFBsYWNlaG9sZGVyXG4gICAgICAgIGZyb206ICdTZW5kZXIgcGxhY2Vob2xkZXInLCAvLyBQbGFjZWhvbGRlclxuICAgICAgICBkYXRlOiBuZXcgRGF0ZSgpLnRvSVNPU3RyaW5nKCksIC8vIFBsYWNlaG9sZGVyXG4gICAgICB9KVxuICAgICk7XG5cbiAgICByZXR1cm4gcmVzLnN0YXR1cygyMDApLmpzb24oe1xuICAgICAgc3VjY2VzczogdHJ1ZSxcbiAgICAgIHJlc3VsdHM6IHJlc3VsdHMsXG4gICAgfSk7XG4gIH0gY2F0Y2ggKGU6IGFueSkge1xuICAgIGNvbnNvbGUuZXJyb3IoYEVycm9yIGluIHNlYXJjaFVzZXJHbWFpbCBoYW5kbGVyIGZvciB1c2VyICR7dXNlcklkfTpgLCBlKTtcbiAgICBjb25zdCBlcnJvck1lc3NhZ2UgPVxuICAgICAgZS5tZXNzYWdlIHx8ICdBbiB1bmV4cGVjdGVkIGVycm9yIG9jY3VycmVkIHdoaWxlIHNlYXJjaGluZyBlbWFpbHMuJztcblxuICAgIC8vIENoZWNrIGlmIHRoZSBlcnJvciBtZXNzYWdlIGluZGljYXRlcyBhbiBhdXRoZW50aWNhdGlvbiBpc3N1ZSBmcm9tIGdldEdtYWlsQ2xpZW50Rm9yVXNlclxuICAgIGlmIChcbiAgICAgIGVycm9yTWVzc2FnZS5pbmNsdWRlcygnRmFpbGVkIHRvIGdldCBhdXRoZW50aWNhdGVkIEdtYWlsIGNsaWVudCcpIHx8XG4gICAgICBlcnJvck1lc3NhZ2UuaW5jbHVkZXMoJ1VzZXIgbmVlZHMgdG8gYXV0aG9yaXplJylcbiAgICApIHtcbiAgICAgIHJldHVybiByZXNcbiAgICAgICAgLnN0YXR1cyg0MDEpXG4gICAgICAgIC5qc29uKHtcbiAgICAgICAgICBzdWNjZXNzOiBmYWxzZSxcbiAgICAgICAgICBtZXNzYWdlOlxuICAgICAgICAgICAgJ0dtYWlsIGF1dGhlbnRpY2F0aW9uIGZhaWxlZCBvciBpcyByZXF1aXJlZC4gUGxlYXNlIGNvbm5lY3QvcmVjb25uZWN0IHlvdXIgR21haWwgYWNjb3VudCB2aWEgc2V0dGluZ3MuJyxcbiAgICAgICAgfSk7XG4gICAgfVxuXG4gICAgcmV0dXJuIHJlcy5zdGF0dXMoNTAwKS5qc29uKHtcbiAgICAgIHN1Y2Nlc3M6IGZhbHNlLFxuICAgICAgbWVzc2FnZTogZXJyb3JNZXNzYWdlLFxuICAgIH0pO1xuICB9XG59O1xuXG5leHBvcnQgZGVmYXVsdCBoYW5kbGVyO1xuIl19