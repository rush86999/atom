import type { NextApiRequest, NextApiResponse } from 'next';
import { forwardBackendApi } from '../../../../lib/backend-api-proxy';

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  const id = req.query.id;
  if (typeof id !== 'string' || !id || id === '.' || id === '..') { res.status(400).json({ error: 'Invalid record id' }); return; }
  return forwardBackendApi(req, res, `/api/v1/tasks/${encodeURIComponent(id)}`, ['PUT', 'DELETE'], { pathParameters: ['id'] });
}
