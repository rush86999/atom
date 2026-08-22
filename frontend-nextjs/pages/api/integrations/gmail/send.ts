import { NextApiRequest, NextApiResponse } from 'next';

const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

const MAX_SUBJECT_LENGTH = 998;
const MAX_MESSAGE_LENGTH = 100_000;

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const { to, subject, message } = req.body || {};

  if (typeof to !== 'string' || !EMAIL_RE.test(to.trim())) {
    return res.status(400).json({ error: 'A valid recipient email address is required' });
  }
  if (subject !== undefined && typeof subject !== 'string') {
    return res.status(400).json({ error: 'Invalid subject' });
  }
  if (message !== undefined && typeof message !== 'string') {
    return res.status(400).json({ error: 'Invalid message' });
  }
  if ((subject || '').length > MAX_SUBJECT_LENGTH || (message || '').length > MAX_MESSAGE_LENGTH) {
    return res.status(413).json({ error: 'Email content exceeds the allowed size' });
  }

  try {
    const backendUrl = process.env.PYTHON_API_SERVICE_BASE_URL || process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';
    const response = await fetch(`${backendUrl}/api/gmail/send`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        to: to.trim(),
        subject: subject || '',
        body: message || '',
      }),
    });

    if (response.ok) {
      const data = await response.json().catch(() => ({}));
      return res.status(200).json({
        ok: true,
        message_id: data.message_id,
        thread_id: data.thread_id,
      });
    }

    if (response.status === 503) {
      return res.status(503).json({
        error: 'Gmail is not configured on the server. Connect a Gmail account first.',
      });
    }

    return res.status(502).json({ error: 'Failed to send email' });
  } catch (error) {
    console.error('Gmail send proxy error:', error);
    return res.status(500).json({ error: 'Failed to send email' });
  }
}
