import type { NextApiRequest, NextApiResponse } from 'next';
import formidable from 'formidable';
import fs from 'fs';
import path from 'path';
import { process_silent_audio_recording_for_notion } from '../../../project/functions/note_utils';

export const config = {
  api: {
    bodyParser: false,
  },
};

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  if (req.method === 'POST') {
    const form = new formidable.IncomingForm();
    form.parse(req, async (err, fields, files) => {
      if (err) {
        res.status(500).json({ message: 'Error parsing form data' });
        return;
      }

      const audioFile = files.audio;
      const title = fields.title as string;

      if (!audioFile) {
        res.status(400).json({ message: 'No audio file uploaded' });
        return;
      }

      const audioFilePath = audioFile.filepath;
      const result = await process_silent_audio_recording_for_notion(
        audioFilePath,
        title
      );

      if (result.status === 'success') {
        res.status(200).json(result.data);
      } else {
        res.status(500).json({ message: result.message });
      }
    });
  } else {
    res.status(405).json({ message: 'Method not allowed' });
  }
}
