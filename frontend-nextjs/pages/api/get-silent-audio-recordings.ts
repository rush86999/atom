// DISABLED: Temporarily disabled for build optimization - 2025-09-03T14:38:43.018Z
// import type { NextApiRequest, NextApiResponse } from 'next';
// import fs from 'fs';
// import path from 'path';
// 
// export default function handler(req: NextApiRequest, res: NextApiResponse) {
//   if (req.method === 'GET') {
//     const recordingsDir = path.join(process.cwd(), 'silent-audio-recordings');
//     const files = fs.readdirSync(recordingsDir);
//     res.status(200).json({ files });
//   } else {
//     res.status(405).json({ message: 'Method not allowed' });
//   }
// }
// 