import { Request, Response } from 'express';
import { getUserOutlookEmailContent } from '../outlook-service/service';

interface GetUserOutlookContentInput {
  emailId: string;
}

interface GetUserOutlookContentRequestBody {
  session_variables: {
    'x-hasura-user-id': string;
  };
  input: GetUserOutlookContentInput;
}

const handler = async (req: Request<{}, {}, GetUserOutlookContentRequestBody>, res: Response) => {
  const userId = req.body.session_variables['x-hasura-user-id'];
  const { emailId } = req.body.input;

  if (!userId) {
    return res.status(401).json({ success: false, message: 'User ID is missing. Unauthorized.' });
  }

  try {
    const email = await getUserOutlookEmailContent(userId, emailId);
    return res.status(200).json({ success: true, email });
  } catch (error) {
    console.error('Error getting Outlook email content:', error);
    return res.status(500).json({ success: false, message: 'Error getting Outlook email content.' });
  }
};

export default handler;
