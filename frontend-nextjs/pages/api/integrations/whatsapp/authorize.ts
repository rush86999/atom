import { NextApiRequest, NextApiResponse } from 'next';

/**
 * Legacy Redirect Bridge for WhatsApp OAuth
 * Redirects from /api/integrations/whatsapp/authorize to the unified /api/v1/auth/oauth/whatsapp/initiate
 */
export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  // Use a 307 Temporary Redirect to ensure the browser preserves the intent
  // and redirect to the current unified OAuth initiation endpoint
  res.redirect(307, '/api/v1/auth/oauth/whatsapp/initiate');
}
