import type { NextApiRequest, NextApiResponse } from 'next';
import fs from 'fs';
import path from 'path';

export default function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method === 'GET') {
    const recordingsDir = path.join(process.cwd(), 'silent-audio-recordings');
    const files = fs.readdirSync(recordingsDir);
    res.status(200).json({ files });
  } else {
    res.status(405).json({ message: 'Method not allowed' });
  }
}
