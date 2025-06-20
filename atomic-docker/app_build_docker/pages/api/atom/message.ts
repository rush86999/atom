import type { NextApiRequest, NextApiResponse } from 'next';
// Assuming HandleMessageResponse is exported from handler.ts or a types file
// If not, we define it here based on its expected structure.
import { handleMessage, HandleMessageResponse } from '../../../../project/functions/atom-agent/handler'; // Adjust path as necessary

// The Data type should now match HandleMessageResponse or be a superset if additional API-specific fields are needed.
// For now, let's assume it directly mirrors HandleMessageResponse for simplicity.
type Data = HandleMessageResponse;

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse<Data>
) {
  if (req.method === 'POST') {
    const { message } = req.body;

    if (!message) {
      // Ensure error response matches the 'Data' type if it expects 'text' for main content
      // For now, keeping it simple as the client likely handles this distinct error structure.
      return res.status(400).json({ text: '', error: 'Missing message in request body' });
    }

    try {
      // atomResponse is now an object like { text: string; audioUrl?: string; error?: string }
      const atomResponse: HandleMessageResponse = await handleMessage(message as string);
      return res.status(200).json(atomResponse);
    } catch (error: any) {
      console.error('Error calling Atom agent handleMessage:', error);
      // Ensure error response structure aligns with 'Data' type as much as possible
      return res.status(500).json({ text: '', error: error.message || 'Internal Server Error from Atom agent' });
    }
  } else {
    res.setHeader('Allow', ['POST']);
    return res.status(405).end(`Method ${req.method} Not Allowed`);
  }
}
