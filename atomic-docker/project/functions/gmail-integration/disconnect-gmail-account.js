import { createAdminGraphQLClient } from '../_utils/dbService'; // Adjust path as necessary
const DELETE_GMAIL_TOKENS_MUTATION = `
mutation DeleteUserGmailTokensForDisconnect($userId: uuid!) {
  delete_user_gmail_tokens(where: {user_id: {_eq: $userId}}) {
    affected_rows
  }
}
`;
const handler = async (req, res) => {
    const userId = req.body.session_variables['x-hasura-user-id'];
    if (!userId) {
        // This should ideally be caught by Hasura permissions if session_variables are required
        return res
            .status(401)
            .json({ success: false, message: 'Unauthorized: User ID missing.' });
    }
    const adminGraphQLClient = createAdminGraphQLClient();
    try {
        console.log(`[Disconnect Gmail] Attempting to delete tokens for user: ${userId}`);
        const result = await adminGraphQLClient.request(DELETE_GMAIL_TOKENS_MUTATION, { userId });
        if (result.delete_user_gmail_tokens) {
            if (result.delete_user_gmail_tokens.affected_rows > 0) {
                console.log(`[Disconnect Gmail] Successfully deleted tokens for user: ${userId}`);
                return res
                    .status(200)
                    .json({
                    success: true,
                    message: 'Gmail account disconnected successfully.',
                });
            }
            else {
                console.log(`[Disconnect Gmail] No tokens found to delete for user: ${userId} (already disconnected or never connected).`);
                // For a disconnect operation, not finding tokens to delete isn't necessarily a failure of the operation's intent.
                return res
                    .status(200)
                    .json({
                    success: true,
                    message: 'No active Gmail connection found to disconnect.',
                });
            }
        }
        else {
            // This case should ideally not happen if the GraphQL mutation is valid and Hasura is running.
            // It implies an issue with the Hasura response structure itself.
            console.error(`[Disconnect Gmail] Unexpected response structure from Hasura for user ${userId}:`, result);
            return res
                .status(500)
                .json({
                success: false,
                message: 'Unexpected error during disconnection.',
            });
        }
    }
    catch (e) {
        console.error(`[Disconnect Gmail] Error in handler for user ${userId}:`, e);
        return res.status(500).json({
            success: false,
            message: 'An error occurred while disconnecting Gmail account: ' +
                (e.message || 'Unknown server error'),
        });
    }
};
export default handler;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiZGlzY29ubmVjdC1nbWFpbC1hY2NvdW50LmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsiZGlzY29ubmVjdC1nbWFpbC1hY2NvdW50LnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiJBQUNBLE9BQU8sRUFBRSx3QkFBd0IsRUFBRSxNQUFNLHFCQUFxQixDQUFDLENBQUMsMkJBQTJCO0FBRTNGLE1BQU0sNEJBQTRCLEdBQUc7Ozs7OztDQU1wQyxDQUFDO0FBZUYsTUFBTSxPQUFPLEdBQUcsS0FBSyxFQUNuQixHQUF1RCxFQUN2RCxHQUE2QyxFQUM3QyxFQUFFO0lBQ0YsTUFBTSxNQUFNLEdBQUcsR0FBRyxDQUFDLElBQUksQ0FBQyxpQkFBaUIsQ0FBQyxrQkFBa0IsQ0FBQyxDQUFDO0lBRTlELElBQUksQ0FBQyxNQUFNLEVBQUUsQ0FBQztRQUNaLHdGQUF3RjtRQUN4RixPQUFPLEdBQUc7YUFDUCxNQUFNLENBQUMsR0FBRyxDQUFDO2FBQ1gsSUFBSSxDQUFDLEVBQUUsT0FBTyxFQUFFLEtBQUssRUFBRSxPQUFPLEVBQUUsZ0NBQWdDLEVBQUUsQ0FBQyxDQUFDO0lBQ3pFLENBQUM7SUFFRCxNQUFNLGtCQUFrQixHQUFHLHdCQUF3QixFQUFFLENBQUM7SUFFdEQsSUFBSSxDQUFDO1FBQ0gsT0FBTyxDQUFDLEdBQUcsQ0FDVCw0REFBNEQsTUFBTSxFQUFFLENBQ3JFLENBQUM7UUFDRixNQUFNLE1BQU0sR0FBRyxNQUFNLGtCQUFrQixDQUFDLE9BQU8sQ0FDN0MsNEJBQTRCLEVBQzVCLEVBQUUsTUFBTSxFQUFFLENBQ1gsQ0FBQztRQUVGLElBQUksTUFBTSxDQUFDLHdCQUF3QixFQUFFLENBQUM7WUFDcEMsSUFBSSxNQUFNLENBQUMsd0JBQXdCLENBQUMsYUFBYSxHQUFHLENBQUMsRUFBRSxDQUFDO2dCQUN0RCxPQUFPLENBQUMsR0FBRyxDQUNULDREQUE0RCxNQUFNLEVBQUUsQ0FDckUsQ0FBQztnQkFDRixPQUFPLEdBQUc7cUJBQ1AsTUFBTSxDQUFDLEdBQUcsQ0FBQztxQkFDWCxJQUFJLENBQUM7b0JBQ0osT0FBTyxFQUFFLElBQUk7b0JBQ2IsT0FBTyxFQUFFLDBDQUEwQztpQkFDcEQsQ0FBQyxDQUFDO1lBQ1AsQ0FBQztpQkFBTSxDQUFDO2dCQUNOLE9BQU8sQ0FBQyxHQUFHLENBQ1QsMERBQTBELE1BQU0sNkNBQTZDLENBQzlHLENBQUM7Z0JBQ0Ysa0hBQWtIO2dCQUNsSCxPQUFPLEdBQUc7cUJBQ1AsTUFBTSxDQUFDLEdBQUcsQ0FBQztxQkFDWCxJQUFJLENBQUM7b0JBQ0osT0FBTyxFQUFFLElBQUk7b0JBQ2IsT0FBTyxFQUFFLGlEQUFpRDtpQkFDM0QsQ0FBQyxDQUFDO1lBQ1AsQ0FBQztRQUNILENBQUM7YUFBTSxDQUFDO1lBQ04sOEZBQThGO1lBQzlGLGlFQUFpRTtZQUNqRSxPQUFPLENBQUMsS0FBSyxDQUNYLHlFQUF5RSxNQUFNLEdBQUcsRUFDbEYsTUFBTSxDQUNQLENBQUM7WUFDRixPQUFPLEdBQUc7aUJBQ1AsTUFBTSxDQUFDLEdBQUcsQ0FBQztpQkFDWCxJQUFJLENBQUM7Z0JBQ0osT0FBTyxFQUFFLEtBQUs7Z0JBQ2QsT0FBTyxFQUFFLHdDQUF3QzthQUNsRCxDQUFDLENBQUM7UUFDUCxDQUFDO0lBQ0gsQ0FBQztJQUFDLE9BQU8sQ0FBTSxFQUFFLENBQUM7UUFDaEIsT0FBTyxDQUFDLEtBQUssQ0FBQyxnREFBZ0QsTUFBTSxHQUFHLEVBQUUsQ0FBQyxDQUFDLENBQUM7UUFDNUUsT0FBTyxHQUFHLENBQUMsTUFBTSxDQUFDLEdBQUcsQ0FBQyxDQUFDLElBQUksQ0FBQztZQUMxQixPQUFPLEVBQUUsS0FBSztZQUNkLE9BQU8sRUFDTCx1REFBdUQ7Z0JBQ3ZELENBQUMsQ0FBQyxDQUFDLE9BQU8sSUFBSSxzQkFBc0IsQ0FBQztTQUN4QyxDQUFDLENBQUM7SUFDTCxDQUFDO0FBQ0gsQ0FBQyxDQUFDO0FBRUYsZUFBZSxPQUFPLENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgeyBSZXF1ZXN0LCBSZXNwb25zZSB9IGZyb20gJ2V4cHJlc3MnO1xuaW1wb3J0IHsgY3JlYXRlQWRtaW5HcmFwaFFMQ2xpZW50IH0gZnJvbSAnLi4vX3V0aWxzL2RiU2VydmljZSc7IC8vIEFkanVzdCBwYXRoIGFzIG5lY2Vzc2FyeVxuXG5jb25zdCBERUxFVEVfR01BSUxfVE9LRU5TX01VVEFUSU9OID0gYFxubXV0YXRpb24gRGVsZXRlVXNlckdtYWlsVG9rZW5zRm9yRGlzY29ubmVjdCgkdXNlcklkOiB1dWlkISkge1xuICBkZWxldGVfdXNlcl9nbWFpbF90b2tlbnMod2hlcmU6IHt1c2VyX2lkOiB7X2VxOiAkdXNlcklkfX0pIHtcbiAgICBhZmZlY3RlZF9yb3dzXG4gIH1cbn1cbmA7XG5cbmludGVyZmFjZSBEaXNjb25uZWN0R21haWxBY2NvdW50UmVxdWVzdEJvZHkge1xuICBzZXNzaW9uX3ZhcmlhYmxlczoge1xuICAgICd4LWhhc3VyYS11c2VyLWlkJzogc3RyaW5nO1xuICB9O1xuICAvLyBObyBzcGVjaWZpYyBpbnB1dCBhcmdzIG5lZWRlZCBmcm9tIGNsaWVudCBmb3IgdGhpcyBtdXRhdGlvbiBiZXlvbmQgc2Vzc2lvblxufVxuXG4vLyBNYXRjaGVzIERpc2Nvbm5lY3RHbWFpbEFjY291bnRPdXRwdXQgaW4gYWN0aW9ucy5ncmFwaHFsXG5pbnRlcmZhY2UgRGlzY29ubmVjdEdtYWlsQWNjb3VudFJlc3BvbnNlIHtcbiAgc3VjY2VzczogYm9vbGVhbjtcbiAgbWVzc2FnZT86IHN0cmluZztcbn1cblxuY29uc3QgaGFuZGxlciA9IGFzeW5jIChcbiAgcmVxOiBSZXF1ZXN0PHt9LCB7fSwgRGlzY29ubmVjdEdtYWlsQWNjb3VudFJlcXVlc3RCb2R5PixcbiAgcmVzOiBSZXNwb25zZTxEaXNjb25uZWN0R21haWxBY2NvdW50UmVzcG9uc2U+XG4pID0+IHtcbiAgY29uc3QgdXNlcklkID0gcmVxLmJvZHkuc2Vzc2lvbl92YXJpYWJsZXNbJ3gtaGFzdXJhLXVzZXItaWQnXTtcblxuICBpZiAoIXVzZXJJZCkge1xuICAgIC8vIFRoaXMgc2hvdWxkIGlkZWFsbHkgYmUgY2F1Z2h0IGJ5IEhhc3VyYSBwZXJtaXNzaW9ucyBpZiBzZXNzaW9uX3ZhcmlhYmxlcyBhcmUgcmVxdWlyZWRcbiAgICByZXR1cm4gcmVzXG4gICAgICAuc3RhdHVzKDQwMSlcbiAgICAgIC5qc29uKHsgc3VjY2VzczogZmFsc2UsIG1lc3NhZ2U6ICdVbmF1dGhvcml6ZWQ6IFVzZXIgSUQgbWlzc2luZy4nIH0pO1xuICB9XG5cbiAgY29uc3QgYWRtaW5HcmFwaFFMQ2xpZW50ID0gY3JlYXRlQWRtaW5HcmFwaFFMQ2xpZW50KCk7XG5cbiAgdHJ5IHtcbiAgICBjb25zb2xlLmxvZyhcbiAgICAgIGBbRGlzY29ubmVjdCBHbWFpbF0gQXR0ZW1wdGluZyB0byBkZWxldGUgdG9rZW5zIGZvciB1c2VyOiAke3VzZXJJZH1gXG4gICAgKTtcbiAgICBjb25zdCByZXN1bHQgPSBhd2FpdCBhZG1pbkdyYXBoUUxDbGllbnQucmVxdWVzdChcbiAgICAgIERFTEVURV9HTUFJTF9UT0tFTlNfTVVUQVRJT04sXG4gICAgICB7IHVzZXJJZCB9XG4gICAgKTtcblxuICAgIGlmIChyZXN1bHQuZGVsZXRlX3VzZXJfZ21haWxfdG9rZW5zKSB7XG4gICAgICBpZiAocmVzdWx0LmRlbGV0ZV91c2VyX2dtYWlsX3Rva2Vucy5hZmZlY3RlZF9yb3dzID4gMCkge1xuICAgICAgICBjb25zb2xlLmxvZyhcbiAgICAgICAgICBgW0Rpc2Nvbm5lY3QgR21haWxdIFN1Y2Nlc3NmdWxseSBkZWxldGVkIHRva2VucyBmb3IgdXNlcjogJHt1c2VySWR9YFxuICAgICAgICApO1xuICAgICAgICByZXR1cm4gcmVzXG4gICAgICAgICAgLnN0YXR1cygyMDApXG4gICAgICAgICAgLmpzb24oe1xuICAgICAgICAgICAgc3VjY2VzczogdHJ1ZSxcbiAgICAgICAgICAgIG1lc3NhZ2U6ICdHbWFpbCBhY2NvdW50IGRpc2Nvbm5lY3RlZCBzdWNjZXNzZnVsbHkuJyxcbiAgICAgICAgICB9KTtcbiAgICAgIH0gZWxzZSB7XG4gICAgICAgIGNvbnNvbGUubG9nKFxuICAgICAgICAgIGBbRGlzY29ubmVjdCBHbWFpbF0gTm8gdG9rZW5zIGZvdW5kIHRvIGRlbGV0ZSBmb3IgdXNlcjogJHt1c2VySWR9IChhbHJlYWR5IGRpc2Nvbm5lY3RlZCBvciBuZXZlciBjb25uZWN0ZWQpLmBcbiAgICAgICAgKTtcbiAgICAgICAgLy8gRm9yIGEgZGlzY29ubmVjdCBvcGVyYXRpb24sIG5vdCBmaW5kaW5nIHRva2VucyB0byBkZWxldGUgaXNuJ3QgbmVjZXNzYXJpbHkgYSBmYWlsdXJlIG9mIHRoZSBvcGVyYXRpb24ncyBpbnRlbnQuXG4gICAgICAgIHJldHVybiByZXNcbiAgICAgICAgICAuc3RhdHVzKDIwMClcbiAgICAgICAgICAuanNvbih7XG4gICAgICAgICAgICBzdWNjZXNzOiB0cnVlLFxuICAgICAgICAgICAgbWVzc2FnZTogJ05vIGFjdGl2ZSBHbWFpbCBjb25uZWN0aW9uIGZvdW5kIHRvIGRpc2Nvbm5lY3QuJyxcbiAgICAgICAgICB9KTtcbiAgICAgIH1cbiAgICB9IGVsc2Uge1xuICAgICAgLy8gVGhpcyBjYXNlIHNob3VsZCBpZGVhbGx5IG5vdCBoYXBwZW4gaWYgdGhlIEdyYXBoUUwgbXV0YXRpb24gaXMgdmFsaWQgYW5kIEhhc3VyYSBpcyBydW5uaW5nLlxuICAgICAgLy8gSXQgaW1wbGllcyBhbiBpc3N1ZSB3aXRoIHRoZSBIYXN1cmEgcmVzcG9uc2Ugc3RydWN0dXJlIGl0c2VsZi5cbiAgICAgIGNvbnNvbGUuZXJyb3IoXG4gICAgICAgIGBbRGlzY29ubmVjdCBHbWFpbF0gVW5leHBlY3RlZCByZXNwb25zZSBzdHJ1Y3R1cmUgZnJvbSBIYXN1cmEgZm9yIHVzZXIgJHt1c2VySWR9OmAsXG4gICAgICAgIHJlc3VsdFxuICAgICAgKTtcbiAgICAgIHJldHVybiByZXNcbiAgICAgICAgLnN0YXR1cyg1MDApXG4gICAgICAgIC5qc29uKHtcbiAgICAgICAgICBzdWNjZXNzOiBmYWxzZSxcbiAgICAgICAgICBtZXNzYWdlOiAnVW5leHBlY3RlZCBlcnJvciBkdXJpbmcgZGlzY29ubmVjdGlvbi4nLFxuICAgICAgICB9KTtcbiAgICB9XG4gIH0gY2F0Y2ggKGU6IGFueSkge1xuICAgIGNvbnNvbGUuZXJyb3IoYFtEaXNjb25uZWN0IEdtYWlsXSBFcnJvciBpbiBoYW5kbGVyIGZvciB1c2VyICR7dXNlcklkfTpgLCBlKTtcbiAgICByZXR1cm4gcmVzLnN0YXR1cyg1MDApLmpzb24oe1xuICAgICAgc3VjY2VzczogZmFsc2UsXG4gICAgICBtZXNzYWdlOlxuICAgICAgICAnQW4gZXJyb3Igb2NjdXJyZWQgd2hpbGUgZGlzY29ubmVjdGluZyBHbWFpbCBhY2NvdW50OiAnICtcbiAgICAgICAgKGUubWVzc2FnZSB8fCAnVW5rbm93biBzZXJ2ZXIgZXJyb3InKSxcbiAgICB9KTtcbiAgfVxufTtcblxuZXhwb3J0IGRlZmF1bHQgaGFuZGxlcjtcbiJdfQ==