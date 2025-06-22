import { Request, Response } from 'express';
// Adjust path to where gmail-service/service.ts is located relative to this file
import { searchUserEmails } from '../gmail-service/service';
import { gmail_v1 } from 'googleapis'; // For typing Google's message object

// Define expected input structure from Hasura action, matching GmailSearchQueryInput
interface SearchUserGmailInput {
  query: string;
  maxResults?: number;
}

interface SearchUserGmailRequestBody {
  session_variables: {
    'x-hasura-user-id': string;
  };
  input: SearchUserGmailInput;
}

// Define the structure for a single search result item, matching GmailSearchResultItem
interface GmailSearchResultItem {
  id: string;
  threadId?: string;
  snippet?: string;
  subject?: string; // Placeholder, needs actual data fetching
  from?: string;    // Placeholder, needs actual data fetching
  date?: string;    // Placeholder, needs actual data fetching
}

// Define the output structure matching GmailSearchOutput in GraphQL
interface SearchUserGmailResponse {
  success: boolean;
  message?: string;
  results?: GmailSearchResultItem[];
}

const handler = async (req: Request<{}, {}, SearchUserGmailRequestBody>, res: Response<SearchUserGmailResponse>) => {
  const userId = req.body.session_variables['x-hasura-user-id'];
  const { query, maxResults = 10 } = req.body.input; // Default maxResults to 10

  if (!userId) {
    return res.status(401).json({ success: false, message: 'User ID is missing. Unauthorized.' });
  }
  if (!query || typeof query !== 'string' || query.trim() === '') {
    return res.status(400).json({ success: false, message: 'Search query is missing or invalid.' });
  }
  if (maxResults !== undefined && (typeof maxResults !== 'number' || maxResults <= 0 || maxResults > 100)) {
    return res.status(400).json({ success: false, message: 'maxResults must be a positive number, not exceeding 100.' });
  }


  try {
    // searchUserEmails is expected to return an array of gmail_v1.Schema$Message
    const rawMessages: gmail_v1.Schema$Message[] = await searchUserEmails(userId, query, maxResults);

    // Transform the raw Gmail API messages to our GmailSearchResultItem structure.
    // The current searchUserEmails (from service.ts) might only fetch basic message list (IDs, threadId).
    // To populate snippet, subject, from, date, searchUserEmails would need to be enhanced,
    // or we'd make additional calls here (which is N+1 and inefficient for a list).
    // For this step, we primarily rely on what messages.list provides (id, threadId, snippet).
    const results: GmailSearchResultItem[] = rawMessages.map((msg: gmail_v1.Schema$Message) => ({
      id: msg.id || 'N/A', // Gmail message ID is crucial
      threadId: msg.threadId || undefined,
      snippet: msg.snippet || undefined,
      // These are placeholders as messages.list doesn't usually provide them directly.
      // Populating these would require modifying searchUserEmails to fetch more details or
      // making individual gmail.users.messages.get calls.
      subject: `Subject for ${msg.id}`, // Placeholder
      from: 'Sender placeholder',        // Placeholder
      date: new Date().toISOString(),   // Placeholder
    }));

    return res.status(200).json({
      success: true,
      results: results,
    });

  } catch (e: any) {
    console.error(`Error in searchUserGmail handler for user ${userId}:`, e);
    const errorMessage = e.message || 'An unexpected error occurred while searching emails.';

    // Check if the error message indicates an authentication issue from getGmailClientForUser
    if (errorMessage.includes('Failed to get authenticated Gmail client') ||
        errorMessage.includes('User needs to authorize')) {
        return res.status(401).json({ success: false, message: 'Gmail authentication failed or is required. Please connect/reconnect your Gmail account via settings.' });
    }

    return res.status(500).json({
      success: false,
      message: errorMessage,
    });
  }
};

export default handler;
