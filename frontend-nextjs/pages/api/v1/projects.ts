import type { NextApiRequest, NextApiResponse } from 'next';
import { forwardBackendApi } from '../../../lib/backend-api-proxy';

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  return forwardBackendApi(req, res, '/api/v1/projects', ['GET', 'POST']);
}
