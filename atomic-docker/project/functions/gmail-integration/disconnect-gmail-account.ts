import { Request, Response } from 'express';
import { createAdminGraphQLClient } from '../_utils/dbService'; // Adjust path as necessary

const DELETE_GMAIL_TOKENS_MUTATION = `
mutation DeleteUserGmailTokensForDisconnect($userId: uuid!) {
  delete_user_gmail_tokens(where: {user_id: {_eq: $userId}}) {
    affected_rows
  }
}
`;

interface DisconnectGmailAccountRequestBody {
  session_variables: {
    'x-hasura-user-id': string;
  };
  // No specific input args needed from client for this mutation beyond session
}

// Matches DisconnectGmailAccountOutput in actions.graphql
interface DisconnectGmailAccountResponse {
  success: boolean;
  message?: string;
}

const handler = async (
  req: Request<{}, {}, DisconnectGmailAccountRequestBody>,
  res: Response<DisconnectGmailAccountResponse>
) => {
  const userId = req.body.session_variables['x-hasura-user-id'];

  if (!userId) {
    // This should ideally be caught by Hasura permissions if session_variables are required
    return res.status(401).json({ success: false, message: "Unauthorized: User ID missing." });
  }

  const adminGraphQLClient = createAdminGraphQLClient();

  try {
    console.log(`[Disconnect Gmail] Attempting to delete tokens for user: ${userId}`);
    const result = await adminGraphQLClient.request(DELETE_GMAIL_TOKENS_MUTATION, { userId });

    if (result.delete_user_gmail_tokens) {
      if (result.delete_user_gmail_tokens.affected_rows > 0) {
        console.log(`[Disconnect Gmail] Successfully deleted tokens for user: ${userId}`);
        return res.status(200).json({ success: true, message: "Gmail account disconnected successfully." });
      } else {
        console.log(`[Disconnect Gmail] No tokens found to delete for user: ${userId} (already disconnected or never connected).`);
        // For a disconnect operation, not finding tokens to delete isn't necessarily a failure of the operation's intent.
        return res.status(200).json({ success: true, message: "No active Gmail connection found to disconnect." });
      }
    } else {
      // This case should ideally not happen if the GraphQL mutation is valid and Hasura is running.
      // It implies an issue with the Hasura response structure itself.
      console.error(`[Disconnect Gmail] Unexpected response structure from Hasura for user ${userId}:`, result);
      return res.status(500).json({ success: false, message: "Unexpected error during disconnection." });
    }
  } catch (e: any) {
    console.error(`[Disconnect Gmail] Error in handler for user ${userId}:`, e);
    return res.status(500).json({
      success: false,
      message: "An error occurred while disconnecting Gmail account: " + (e.message || "Unknown server error"),
    });
  }
};

export default handler;
