import { Request, Response } from 'express';
import { searchUserOutlookEmails } from '../outlook-service/service';

interface SearchUserOutlookInput {
  query: string;
  maxResults?: number;
}

interface SearchUserOutlookRequestBody {
  session_variables: {
    'x-hasura-user-id': string;
  };
  input: SearchUserOutlookInput;
}

const handler = async (req: Request<{}, {}, SearchUserOutlookRequestBody>, res: Response) => {
  const userId = req.body.session_variables['x-hasura-user-id'];
  const { query, maxResults = 10 } = req.body.input;

  if (!userId) {
    return res.status(401).json({ success: false, message: 'User ID is missing. Unauthorized.' });
  }

  try {
    const results = await searchUserOutlookEmails(userId, query, maxResults);
    return res.status(200).json({ success: true, results });
  } catch (error) {
    console.error('Error searching Outlook emails:', error);
    return res.status(500).json({ success: false, message: 'Error searching Outlook emails.' });
  }
};

export default handler;
