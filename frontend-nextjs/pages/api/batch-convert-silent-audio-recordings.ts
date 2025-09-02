import type { NextApiRequest, NextApiResponse } from 'next';
import fs from 'fs';
import path from 'path';
import { exec } from 'child_process';

export default function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method === 'POST') {
    const recordingsDir = path.join(process.cwd(), 'silent-audio-recordings');
    const files = fs.readdirSync(recordingsDir);
    files.forEach((file) => {
      if (file.endsWith('.wav')) {
        const wavFilePath = path.join(recordingsDir, file);
        const mp3FilePath = path.join(
          recordingsDir,
          file.replace('.wav', '.mp3')
        );
        exec(
          `ffmpeg -i ${wavFilePath} ${mp3FilePath}`,
          (error, stdout, stderr) => {
            if (error) {
              console.error(`exec error: ${error}`);
              return;
            }
            fs.unlinkSync(wavFilePath);
          }
        );
      }
    });
    res.status(200).json({ message: 'Batch conversion started' });
  } else {
    res.status(405).json({ message: 'Method not allowed' });
  }
}
