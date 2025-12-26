import { NextApiRequest, NextApiResponse } from "next";

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse,
) {
  const backendUrl = process.env.PYTHON_API_SERVICE_BASE_URL || 'http://localhost:5058';

  if (req.method === 'POST') {
    try {
      const file = (req as any).files?.file;
      const { channels = [], title, initialComment } = req.body;

      if (!file) {
        return res.status(400).json({
          success: false,
          error: 'file is required'
        });
      }

      // Create FormData for file upload
      const formData = new FormData();
      formData.append('file', file);

      if (channels.length > 0) {
        formData.append('channels', channels.join(','));
      }

      if (title) {
        formData.append('title', title);
      }

      if (initialComment) {
        formData.append('initial_comment', initialComment);
      }

      const response = await fetch(`${backendUrl}/api/slack/files/upload`, {
        method: 'POST',
        body: formData,
      });

      const data = await response.json();

      if (response.ok) {
        return res.status(200).json(data);
      } else {
        return res.status(400).json(data);
      }
    } catch (error) {
      console.error('Error uploading file:', error);
      return res.status(500).json({
        success: false,
        error: 'Failed to upload file'
      });
    }
  } else {
    res.setHeader('Allow', ['POST']);
    return res.status(405).end(`Method ${req.method} Not Allowed`);
  }
}