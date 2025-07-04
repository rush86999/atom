import type { NextApiRequest, NextApiResponse } from 'next';
import formidable from 'formidable'; // Using formidable for robust file parsing
import fs from 'fs';
import path from 'path';
import axios from 'axios'; // To call the Python backend

// Disable Next.js body parser for this route as formidable will handle it
export const config = {
  api: {
    bodyParser: false,
  },
};

// Determine the Python backend URL from environment variables
// This should point to the service that will actually process the audio (e.g., python-agent)
const PYTHON_PROCESSING_SERVICE_URL = process.env.PYTHON_API_SERVICE_BASE_URL || 'http://python-agent:5000'; // Default from compose

interface FormidableParseResult {
  fields: formidable.Fields;
  files: formidable.Files;
}

interface PythonBackendResponseData {
  notion_page_url: string;
  title: string;
  summary_preview?: string;
  // other fields from the python service if needed
}

interface PythonBackendResponse {
  ok: boolean;
  data?: PythonBackendResponseData;
  error?: {
    message: string;
    code?: string;
    details?: any;
  };
  // Compatibility with simple status/message
  status?: 'success' | 'error';
  message?: string;
}


export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'POST') {
    res.setHeader('Allow', ['POST']);
    return res.status(405).end(`Method ${req.method} Not Allowed`);
  }

  const form = formidable({
    keepExtensions: true,
    // Define a temporary directory for uploads if needed, or let formidable handle it
    // uploadDir: path.join(process.cwd(), '.tmp_uploads'), // Ensure this dir exists and is writable
    // maxFileSize: 100 * 1024 * 1024, // 100MB limit example
  });

  try {
    const parsePromise = new Promise<FormidableParseResult>((resolve, reject) => {
      form.parse(req, (err, fields, files) => {
        if (err) {
          console.error('Formidable parsing error:', err);
          return reject(err);
        }
        resolve({ fields, files });
      });
    });

    const { fields, files } = await parsePromise;

    const audioFileArray = files.audio_file;
    const titleArray = fields.title;
    const userIdArray = fields.user_id;
    const linkedEventIdArray = fields.linked_event_id; // Optional

    if (!audioFileArray || !Array.isArray(audioFileArray) || audioFileArray.length === 0) {
      return res.status(400).json({ ok: false, error: { message: 'No audio file uploaded.' } });
    }
    const audioFile = audioFileArray[0];

    if (!titleArray || !Array.isArray(titleArray) || titleArray.length === 0 || !titleArray[0]) {
      return res.status(400).json({ ok: false, error: { message: 'Missing title for the audio note.' } });
    }
    const title = titleArray[0];

    if (!userIdArray || !Array.isArray(userIdArray) || userIdArray.length === 0 || !userIdArray[0]) {
      return res.status(400).json({ ok: false, error: { message: 'Missing user_id.' } });
    }
    const userId = userIdArray[0];

    const linkedEventId = (linkedEventIdArray && Array.isArray(linkedEventIdArray) && linkedEventIdArray.length > 0)
                          ? linkedEventIdArray[0]
                          : undefined;

    if (!audioFile.filepath) {
        return res.status(500).json({ ok: false, error: { message: 'Uploaded file path is missing.' } });
    }

    // At this point, audioFile.filepath points to the temporary location of the uploaded file.
    // We need to send this file to the Python backend.

    const pythonEndpoint = `${PYTHON_PROCESSING_SERVICE_URL}/api/internal/process_audio_note_data`;
    console.log(`Next API: Forwarding audio to Python backend: ${pythonEndpoint}`);

    const backendFormData = new FormData();
    const fileStream = fs.createReadStream(audioFile.filepath);

    // Use original filename or a generic one. Formidable provides originalFilename.
    const originalFilename = audioFile.originalFilename || 'audio.tmp';
    backendFormData.append('audio_file', fileStream as any, originalFilename); // Casting to any for FormData compatibility with stream
    backendFormData.append('title', title);
    backendFormData.append('user_id', userId);
    if (linkedEventId) {
      backendFormData.append('linked_event_id', linkedEventId);
    }
    // Add other necessary metadata for the Python service
    // backendFormData.append('notion_source_text', 'In-Person Audio Note via Agent');

    try {
      const pythonResponse = await axios.post<PythonBackendResponse>(pythonEndpoint, backendFormData, {
        headers: {
          ...backendFormData.getHeaders?.(), // For FormData content-type
          // Add any auth headers if Python service requires them
        },
        maxBodyLength: Infinity, // Important for large file uploads
        maxContentLength: Infinity,
      });

      // Clean up the temporary file uploaded by formidable
      fs.unlink(audioFile.filepath, (unlinkErr) => {
        if (unlinkErr) console.error("Error deleting temp audio file:", unlinkErr);
      });

      // Check Python backend response
      if (pythonResponse.data && (pythonResponse.data.ok || pythonResponse.data.status === 'success') && pythonResponse.data.data) {
        return res.status(200).json({
          ok: true,
          message: "Audio note processed successfully.",
          data: pythonResponse.data.data
        });
      } else {
        const errorMsg = pythonResponse.data?.error?.message || pythonResponse.data?.message || "Unknown error from Python processing service.";
        console.error("Error from Python backend:", pythonResponse.data);
        return res.status(500).json({ ok: false, error: { message: errorMsg, code: pythonResponse.data?.error?.code || "PYTHON_PROCESSING_FAILED" } });
      }
    } catch (axiosError: any) {
      fs.unlink(audioFile.filepath, (unlinkErr) => { // Ensure cleanup on error too
        if (unlinkErr) console.error("Error deleting temp audio file after axios error:", unlinkErr);
      });
      console.error('Axios error calling Python backend:', axiosError.isAxiosError ? axiosError.toJSON() : axiosError);
      let errorMessage = "Error communicating with audio processing service.";
      if (axiosError.response && axiosError.response.data && (axiosError.response.data.message || axiosError.response.data.error?.message)) {
        errorMessage = axiosError.response.data.message || axiosError.response.data.error.message;
      } else if (axiosError.message) {
        errorMessage = axiosError.message;
      }
      return res.status(502).json({ ok: false, error: { message: errorMessage, code: "PYTHON_SERVICE_COMMUNICATION_ERROR" } });
    }

  } catch (error: any) {
    console.error('Overall error in /api/process-recorded-audio-note:', error);
    return res.status(500).json({ ok: false, error: { message: `Server error: ${error.message || 'Failed to process request'}` } });
  }
}
