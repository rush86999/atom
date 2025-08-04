import type { NextApiRequest, NextApiResponse } from 'next';
import formidable from 'formidable'; // Using formidable for robust file parsing
import fs from 'fs';
// import path from 'path'; // Path seems unused after formidable's internal handling
// import axios from 'axios'; // To call the Python backend - Will be replaced by resilientGot
import FormData from 'form-data'; // Explicitly import FormData if not globally available or for clarity
import fs from 'fs'; // Already imported
import appServiceLogger from '../../../lib/logger'; // Import the shared logger
import { resilientGot } from '../../../lib/api-backend-helper'; // Import resilientGot

// Disable Next.js body parser for this route as formidable will handle it
export const config = {
  api: {
    bodyParser: false,
  },
};

// Determine the Python backend URL from environment variables
// This should point to the service that will actually process the audio (e.g., python-agent)
const PYTHON_PROCESSING_SERVICE_URL =
  process.env.PYTHON_API_SERVICE_BASE_URL || 'http://python-agent:5000'; // Default from compose

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

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
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
    const operationName = 'processRecordedAudioNoteAPI'; // For logging context

    const parsePromise = new Promise<FormidableParseResult>(
      (resolve, reject) => {
        form.parse(req, (err, fields, files) => {
          if (err) {
            appServiceLogger.error(
              `[${operationName}] Formidable parsing error.`,
              { error: err.message, stack: err.stack, details: err }
            );
            return reject(err);
          }
          resolve({ fields, files });
        });
      }
    );

    const { fields, files } = await parsePromise;
    appServiceLogger.info(`[${operationName}] Form parsed successfully.`, {
      fileKeys: Object.keys(files),
      fieldKeys: Object.keys(fields).join(', '),
    });

    const audioFileArray = files.audio_file;
    const titleArray = fields.title;
    const userIdArray = fields.user_id;
    const linkedEventIdArray = fields.linked_event_id; // Optional

    if (
      !audioFileArray ||
      !Array.isArray(audioFileArray) ||
      audioFileArray.length === 0
    ) {
      return res
        .status(400)
        .json({ ok: false, error: { message: 'No audio file uploaded.' } });
    }
    const audioFile = audioFileArray[0];

    if (
      !titleArray ||
      !Array.isArray(titleArray) ||
      titleArray.length === 0 ||
      !titleArray[0]
    ) {
      return res
        .status(400)
        .json({
          ok: false,
          error: { message: 'Missing title for the audio note.' },
        });
    }
    const title = titleArray[0];

    if (
      !userIdArray ||
      !Array.isArray(userIdArray) ||
      userIdArray.length === 0 ||
      !userIdArray[0]
    ) {
      return res
        .status(400)
        .json({ ok: false, error: { message: 'Missing user_id.' } });
    }
    const userId = userIdArray[0];

    const linkedEventId =
      linkedEventIdArray &&
      Array.isArray(linkedEventIdArray) &&
      linkedEventIdArray.length > 0
        ? linkedEventIdArray[0]
        : undefined;

    if (!audioFile.filepath) {
      return res
        .status(500)
        .json({
          ok: false,
          error: { message: 'Uploaded file path is missing.' },
        });
    }

    // At this point, audioFile.filepath points to the temporary location of the uploaded file.
    // We need to send this file to the Python backend.

    const pythonEndpoint = `${PYTHON_PROCESSING_SERVICE_URL}/api/internal/process_audio_note_data`;
    appServiceLogger.info(
      `[${operationName}] Forwarding audio to Python backend.`,
      {
        pythonEndpoint,
        userId,
        title,
        linkedEventId,
        audioFilePath: audioFile.filepath,
      }
    );

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
      // Using resilientGot for the call to Python backend
      const gotOptions = {
        body: backendFormData, // Pass FormData instance as body
        headers: {
          // 'got' will set Content-Type automatically for FormData
          // Add any auth headers if Python service requires them
        },
        // resilientGot handles timeout internally, defaults to 15s.
        // maxBodyLength/maxContentLength are not direct got options,
        // but got typically handles large streams. Monitor if issues arise.
        responseType: 'json' as 'json', // Expect a JSON response
      };

      const pythonServiceResponseData = (await resilientGot(
        'post',
        pythonEndpoint,
        gotOptions,
        `${operationName}_PythonBackendCall`
      )) as PythonBackendResponse;

      // Clean up the temporary file uploaded by formidable
      fs.unlink(audioFile.filepath, (unlinkErr) => {
        if (unlinkErr)
          appServiceLogger.error(
            `[${operationName}] Error deleting temp audio file.`,
            {
              filepath: audioFile.filepath,
              error: unlinkErr.message,
              stack: unlinkErr.stack,
            }
          );
      });

      // Check Python backend response
      // resilientGot returns the body directly, so we access properties on pythonServiceResponseData
      if (
        pythonServiceResponseData &&
        (pythonServiceResponseData.ok ||
          pythonServiceResponseData.status === 'success') &&
        pythonServiceResponseData.data
      ) {
        appServiceLogger.info(
          `[${operationName}] Python backend processed audio successfully.`,
          { userId, title, responseData: pythonServiceResponseData.data }
        );
        return res.status(200).json({
          ok: true,
          message: 'Audio note processed successfully.',
          data: pythonServiceResponseData.data,
        });
      } else {
        const errorMsg =
          pythonServiceResponseData?.error?.message ||
          pythonServiceResponseData?.message ||
          'Unknown error from Python processing service.';
        appServiceLogger.error(
          `[${operationName}] Error response from Python backend.`,
          {
            userId,
            title,
            errorMsg,
            pythonResponseData: pythonServiceResponseData,
          }
        );
        return res
          .status(500)
          .json({
            ok: false,
            error: {
              message: errorMsg,
              code:
                pythonServiceResponseData?.error?.code ||
                'PYTHON_PROCESSING_FAILED',
            },
          });
      }
    } catch (serviceCallError: any) {
      // Catch errors from resilientGot or file operations
      fs.unlink(audioFile.filepath, (unlinkErr) => {
        // Ensure cleanup on error too
        if (unlinkErr)
          appServiceLogger.error(
            `[${operationName}] Error deleting temp audio file after service call error.`,
            {
              filepath: audioFile.filepath,
              error: unlinkErr.message,
              stack: unlinkErr.stack,
            }
          );
      });

      appServiceLogger.error(
        `[${operationName}] Error calling Python backend or during file ops.`,
        {
          userId,
          title,
          error: serviceCallError.message,
          stack: serviceCallError.stack,
          details: serviceCallError,
        }
      );

      let errorMessage = 'Error communicating with audio processing service.';
      // If serviceCallError is from resilientGot, it might have response details
      if (serviceCallError.response?.body) {
        try {
          const errorBody =
            typeof serviceCallError.response.body === 'string'
              ? JSON.parse(serviceCallError.response.body)
              : serviceCallError.response.body;
          errorMessage =
            errorBody.message ||
            errorBody.error?.message ||
            JSON.stringify(errorBody);
        } catch (e) {
          errorMessage =
            typeof serviceCallError.response.body === 'string'
              ? serviceCallError.response.body
              : 'Unparseable error from service';
        }
      } else if (serviceCallError.message) {
        errorMessage = serviceCallError.message;
      }
      return res
        .status(502)
        .json({
          ok: false,
          error: {
            message: errorMessage,
            code: 'PYTHON_SERVICE_COMMUNICATION_ERROR',
          },
        });
    }
  } catch (error: any) {
    appServiceLogger.error(`[${operationName}] Overall error in API handler.`, {
      error: error.message,
      stack: error.stack,
      details: error,
    });
    return res
      .status(500)
      .json({
        ok: false,
        error: {
          message: `Server error: ${error.message || 'Failed to process request'}`,
        },
      });
  }
}
