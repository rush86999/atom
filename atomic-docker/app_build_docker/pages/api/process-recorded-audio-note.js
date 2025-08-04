"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.config = void 0;
exports.default = handler;
const formidable_1 = __importDefault(require("formidable")); // Using formidable for robust file parsing
const fs_1 = __importDefault(require("fs"));
// import path from 'path'; // Path seems unused after formidable's internal handling
// import axios from 'axios'; // To call the Python backend - Will be replaced by resilientGot
const form_data_1 = __importDefault(require("form-data")); // Explicitly import FormData if not globally available or for clarity
const logger_1 = __importDefault(require("../../../lib/logger")); // Import the shared logger
const api_backend_helper_1 = require("../../../lib/api-backend-helper"); // Import resilientGot
// Disable Next.js body parser for this route as formidable will handle it
exports.config = {
    api: {
        bodyParser: false,
    },
};
// Determine the Python backend URL from environment variables
// This should point to the service that will actually process the audio (e.g., python-agent)
const PYTHON_PROCESSING_SERVICE_URL = process.env.PYTHON_API_SERVICE_BASE_URL || 'http://python-agent:5000'; // Default from compose
async function handler(req, res) {
    if (req.method !== 'POST') {
        res.setHeader('Allow', ['POST']);
        return res.status(405).end(`Method ${req.method} Not Allowed`);
    }
    const form = (0, formidable_1.default)({
        keepExtensions: true,
        // Define a temporary directory for uploads if needed, or let formidable handle it
        // uploadDir: path.join(process.cwd(), '.tmp_uploads'), // Ensure this dir exists and is writable
        // maxFileSize: 100 * 1024 * 1024, // 100MB limit example
    });
    try {
        const operationName = 'processRecordedAudioNoteAPI'; // For logging context
        const parsePromise = new Promise((resolve, reject) => {
            form.parse(req, (err, fields, files) => {
                if (err) {
                    logger_1.default.error(`[${operationName}] Formidable parsing error.`, { error: err.message, stack: err.stack, details: err });
                    return reject(err);
                }
                resolve({ fields, files });
            });
        });
        const { fields, files } = await parsePromise;
        logger_1.default.info(`[${operationName}] Form parsed successfully.`, {
            fileKeys: Object.keys(files),
            fieldKeys: Object.keys(fields).join(', '),
        });
        const audioFileArray = files.audio_file;
        const titleArray = fields.title;
        const userIdArray = fields.user_id;
        const linkedEventIdArray = fields.linked_event_id; // Optional
        if (!audioFileArray ||
            !Array.isArray(audioFileArray) ||
            audioFileArray.length === 0) {
            return res
                .status(400)
                .json({ ok: false, error: { message: 'No audio file uploaded.' } });
        }
        const audioFile = audioFileArray[0];
        if (!titleArray ||
            !Array.isArray(titleArray) ||
            titleArray.length === 0 ||
            !titleArray[0]) {
            return res
                .status(400)
                .json({
                ok: false,
                error: { message: 'Missing title for the audio note.' },
            });
        }
        const title = titleArray[0];
        if (!userIdArray ||
            !Array.isArray(userIdArray) ||
            userIdArray.length === 0 ||
            !userIdArray[0]) {
            return res
                .status(400)
                .json({ ok: false, error: { message: 'Missing user_id.' } });
        }
        const userId = userIdArray[0];
        const linkedEventId = linkedEventIdArray &&
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
        logger_1.default.info(`[${operationName}] Forwarding audio to Python backend.`, {
            pythonEndpoint,
            userId,
            title,
            linkedEventId,
            audioFilePath: audioFile.filepath,
        });
        const backendFormData = new form_data_1.default();
        const fileStream = fs_1.default.createReadStream(audioFile.filepath);
        // Use original filename or a generic one. Formidable provides originalFilename.
        const originalFilename = audioFile.originalFilename || 'audio.tmp';
        backendFormData.append('audio_file', fileStream, originalFilename); // Casting to any for FormData compatibility with stream
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
                responseType: 'json', // Expect a JSON response
            };
            const pythonServiceResponseData = (await (0, api_backend_helper_1.resilientGot)('post', pythonEndpoint, gotOptions, `${operationName}_PythonBackendCall`));
            // Clean up the temporary file uploaded by formidable
            fs_1.default.unlink(audioFile.filepath, (unlinkErr) => {
                if (unlinkErr)
                    logger_1.default.error(`[${operationName}] Error deleting temp audio file.`, {
                        filepath: audioFile.filepath,
                        error: unlinkErr.message,
                        stack: unlinkErr.stack,
                    });
            });
            // Check Python backend response
            // resilientGot returns the body directly, so we access properties on pythonServiceResponseData
            if (pythonServiceResponseData &&
                (pythonServiceResponseData.ok ||
                    pythonServiceResponseData.status === 'success') &&
                pythonServiceResponseData.data) {
                logger_1.default.info(`[${operationName}] Python backend processed audio successfully.`, { userId, title, responseData: pythonServiceResponseData.data });
                return res.status(200).json({
                    ok: true,
                    message: 'Audio note processed successfully.',
                    data: pythonServiceResponseData.data,
                });
            }
            else {
                const errorMsg = pythonServiceResponseData?.error?.message ||
                    pythonServiceResponseData?.message ||
                    'Unknown error from Python processing service.';
                logger_1.default.error(`[${operationName}] Error response from Python backend.`, {
                    userId,
                    title,
                    errorMsg,
                    pythonResponseData: pythonServiceResponseData,
                });
                return res
                    .status(500)
                    .json({
                    ok: false,
                    error: {
                        message: errorMsg,
                        code: pythonServiceResponseData?.error?.code ||
                            'PYTHON_PROCESSING_FAILED',
                    },
                });
            }
        }
        catch (serviceCallError) {
            // Catch errors from resilientGot or file operations
            fs_1.default.unlink(audioFile.filepath, (unlinkErr) => {
                // Ensure cleanup on error too
                if (unlinkErr)
                    logger_1.default.error(`[${operationName}] Error deleting temp audio file after service call error.`, {
                        filepath: audioFile.filepath,
                        error: unlinkErr.message,
                        stack: unlinkErr.stack,
                    });
            });
            logger_1.default.error(`[${operationName}] Error calling Python backend or during file ops.`, {
                userId,
                title,
                error: serviceCallError.message,
                stack: serviceCallError.stack,
                details: serviceCallError,
            });
            let errorMessage = 'Error communicating with audio processing service.';
            // If serviceCallError is from resilientGot, it might have response details
            if (serviceCallError.response?.body) {
                try {
                    const errorBody = typeof serviceCallError.response.body === 'string'
                        ? JSON.parse(serviceCallError.response.body)
                        : serviceCallError.response.body;
                    errorMessage =
                        errorBody.message ||
                            errorBody.error?.message ||
                            JSON.stringify(errorBody);
                }
                catch (e) {
                    errorMessage =
                        typeof serviceCallError.response.body === 'string'
                            ? serviceCallError.response.body
                            : 'Unparseable error from service';
                }
            }
            else if (serviceCallError.message) {
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
    }
    catch (error) {
        logger_1.default.error(`[${operationName}] Overall error in API handler.`, {
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
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoicHJvY2Vzcy1yZWNvcmRlZC1hdWRpby1ub3RlLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsicHJvY2Vzcy1yZWNvcmRlZC1hdWRpby1ub3RlLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiI7Ozs7OztBQStDQSwwQkFxUkM7QUFuVUQsNERBQW9DLENBQUMsMkNBQTJDO0FBQ2hGLDRDQUFvQjtBQUNwQixxRkFBcUY7QUFDckYsOEZBQThGO0FBQzlGLDBEQUFpQyxDQUFDLHNFQUFzRTtBQUV4RyxpRUFBbUQsQ0FBQywyQkFBMkI7QUFDL0Usd0VBQStELENBQUMsc0JBQXNCO0FBRXRGLDBFQUEwRTtBQUM3RCxRQUFBLE1BQU0sR0FBRztJQUNwQixHQUFHLEVBQUU7UUFDSCxVQUFVLEVBQUUsS0FBSztLQUNsQjtDQUNGLENBQUM7QUFFRiw4REFBOEQ7QUFDOUQsNkZBQTZGO0FBQzdGLE1BQU0sNkJBQTZCLEdBQ2pDLE9BQU8sQ0FBQyxHQUFHLENBQUMsMkJBQTJCLElBQUksMEJBQTBCLENBQUMsQ0FBQyx1QkFBdUI7QUEyQmpGLEtBQUssVUFBVSxPQUFPLENBQ25DLEdBQW1CLEVBQ25CLEdBQW9CO0lBRXBCLElBQUksR0FBRyxDQUFDLE1BQU0sS0FBSyxNQUFNLEVBQUUsQ0FBQztRQUMxQixHQUFHLENBQUMsU0FBUyxDQUFDLE9BQU8sRUFBRSxDQUFDLE1BQU0sQ0FBQyxDQUFDLENBQUM7UUFDakMsT0FBTyxHQUFHLENBQUMsTUFBTSxDQUFDLEdBQUcsQ0FBQyxDQUFDLEdBQUcsQ0FBQyxVQUFVLEdBQUcsQ0FBQyxNQUFNLGNBQWMsQ0FBQyxDQUFDO0lBQ2pFLENBQUM7SUFFRCxNQUFNLElBQUksR0FBRyxJQUFBLG9CQUFVLEVBQUM7UUFDdEIsY0FBYyxFQUFFLElBQUk7UUFDcEIsa0ZBQWtGO1FBQ2xGLGlHQUFpRztRQUNqRyx5REFBeUQ7S0FDMUQsQ0FBQyxDQUFDO0lBRUgsSUFBSSxDQUFDO1FBQ0gsTUFBTSxhQUFhLEdBQUcsNkJBQTZCLENBQUMs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LGdDQUFnQyxDQUFDO2dCQUN6QyxDQUFDO1lBQ0gsQ0FBQztpQkFBTSxJQUFJLGdCQUFnQixDQUFDLE9BQU8sRUFBRSxDQUFDO2dCQUNwQyxZQUFZLEdBQUcsZ0JBQWdCLENBQUMsT0FBTyxDQUFDO1lBQzFDLENBQUM7WUFDRCxPQUFPLEdBQUc7aUJBQ1AsTUFBTSxDQUFDLEdBQUcsQ0FBQztpQkFDWCxJQUFJLENBQUM7Z0JBQ0osRUFBRSxFQUFFLEtBQUs7Z0JBQ1QsS0FBSyxFQUFFO29CQUNMLE9BQU8sRUFBRSxZQUFZO29CQUNyQixJQUFJLEVBQUUsb0NBQW9DO2lCQUMzQzthQUNGLENBQUMsQ0FBQztRQUNQLENBQUM7SUFDSCxDQUFDO0lBQUMsT0FBTyxLQUFVLEVBQUUsQ0FBQztRQUNwQixnQkFBZ0IsQ0FBQyxLQUFLLENBQUMsSUFBSSxhQUFhLGlDQUFpQyxFQUFFO1lBQ3pFLEtBQUssRUFBRSxLQUFLLENBQUMsT0FBTztZQUNwQixLQUFLLEVBQUUsS0FBSyxDQUFDLEtBQUs7WUFDbEIsT0FBTyxFQUFFLEtBQUs7U0FDZixDQUFDLENBQUM7UUFDSCxPQUFPLEdBQUc7YUFDUCxNQUFNLENBQUMsR0FBRyxDQUFDO2FBQ1gsSUFBSSxDQUFDO1lBQ0osRUFBRSxFQUFFLEtBQUs7WUFDVCxLQUFLLEVBQUU7Z0JBQ0wsT0FBTyxFQUFFLGlCQUFpQixLQUFLLENBQUMsT0FBTyxJQUFJLDJCQUEyQixFQUFFO2FBQ3pFO1NBQ0YsQ0FBQyxDQUFDO0lBQ1AsQ0FBQztBQUNILENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgdHlwZSB7IE5leHRBcGlSZXF1ZXN0LCBOZXh0QXBpUmVzcG9uc2UgfSBmcm9tICduZXh0JztcbmltcG9ydCBmb3JtaWRhYmxlIGZyb20gJ2Zvcm1pZGFibGUnOyAvLyBVc2luZyBmb3JtaWRhYmxlIGZvciByb2J1c3QgZmlsZSBwYXJzaW5nXG5pbXBvcnQgZnMgZnJvbSAnZnMnO1xuLy8gaW1wb3J0IHBhdGggZnJvbSAncGF0aCc7IC8vIFBhdGggc2VlbXMgdW51c2VkIGFmdGVyIGZvcm1pZGFibGUncyBpbnRlcm5hbCBoYW5kbGluZ1xuLy8gaW1wb3J0IGF4aW9zIGZyb20gJ2F4aW9zJzsgLy8gVG8gY2FsbCB0aGUgUHl0aG9uIGJhY2tlbmQgLSBXaWxsIGJlIHJlcGxhY2VkIGJ5IHJlc2lsaWVudEdvdFxuaW1wb3J0IEZvcm1EYXRhIGZyb20gJ2Zvcm0tZGF0YSc7IC8vIEV4cGxpY2l0bHkgaW1wb3J0IEZvcm1EYXRhIGlmIG5vdCBnbG9iYWxseSBhdmFpbGFibGUgb3IgZm9yIGNsYXJpdHlcbmltcG9ydCBmcyBmcm9tICdmcyc7IC8vIEFscmVhZHkgaW1wb3J0ZWRcbmltcG9ydCBhcHBTZXJ2aWNlTG9nZ2VyIGZyb20gJy4uLy4uLy4uL2xpYi9sb2dnZXInOyAvLyBJbXBvcnQgdGhlIHNoYXJlZCBsb2dnZXJcbmltcG9ydCB7IHJlc2lsaWVudEdvdCB9IGZyb20gJy4uLy4uLy4uL2xpYi9hcGktYmFja2VuZC1oZWxwZXInOyAvLyBJbXBvcnQgcmVzaWxpZW50R290XG5cbi8vIERpc2FibGUgTmV4dC5qcyBib2R5IHBhcnNlciBmb3IgdGhpcyByb3V0ZSBhcyBmb3JtaWRhYmxlIHdpbGwgaGFuZGxlIGl0XG5leHBvcnQgY29uc3QgY29uZmlnID0ge1xuICBhcGk6IHtcbiAgICBib2R5UGFyc2VyOiBmYWxzZSxcbiAgfSxcbn07XG5cbi8vIERldGVybWluZSB0aGUgUHl0aG9uIGJhY2tlbmQgVVJMIGZyb20gZW52aXJvbm1lbnQgdmFyaWFibGVzXG4vLyBUaGlzIHNob3VsZCBwb2ludCB0byB0aGUgc2VydmljZSB0aGF0IHdpbGwgYWN0dWFsbHkgcHJvY2VzcyB0aGUgYXVkaW8gKGUuZy4sIHB5dGhvbi1hZ2VudClcbmNvbnN0IFBZVEhPTl9QUk9DRVNTSU5HX1NFUlZJQ0VfVVJMID1cbiAgcHJvY2Vzcy5lbnYuUFlUSE9OX0FQSV9TRVJWSUNFX0JBU0VfVVJMIHx8ICdodHRwOi8vcHl0aG9uLWFnZW50OjUwMDAnOyAvLyBEZWZhdWx0IGZyb20gY29tcG9zZVxuXG5pbnRlcmZhY2UgRm9ybWlkYWJsZVBhcnNlUmVzdWx0IHtcbiAgZmllbGRzOiBmb3JtaWRhYmxlLkZpZWxkcztcbiAgZmlsZXM6IGZvcm1pZGFibGUuRmlsZXM7XG59XG5cbmludGVyZmFjZSBQeXRob25CYWNrZW5kUmVzcG9uc2VEYXRhIHtcbiAgbm90aW9uX3BhZ2VfdXJsOiBzdHJpbmc7XG4gIHRpdGxlOiBzdHJpbmc7XG4gIHN1bW1hcnlfcHJldmlldz86IHN0cmluZztcbiAgLy8gb3RoZXIgZmllbGRzIGZyb20gdGhlIHB5dGhvbiBzZXJ2aWNlIGlmIG5lZWRlZFxufVxuXG5pbnRlcmZhY2UgUHl0aG9uQmFja2VuZFJlc3BvbnNlIHtcbiAgb2s6IGJvb2xlYW47XG4gIGRhdGE/OiBQeXRob25CYWNrZW5kUmVzcG9uc2VEYXRhO1xuICBlcnJvcj86IHtcbiAgICBtZXNzYWdlOiBzdHJpbmc7XG4gICAgY29kZT86IHN0cmluZztcbiAgICBkZXRhaWxzPzogYW55O1xuICB9O1xuICAvLyBDb21wYXRpYmlsaXR5IHdpdGggc2ltcGxlIHN0YXR1cy9tZXNzYWdlXG4gIHN0YXR1cz86ICdzdWNjZXNzJyB8ICdlcnJvcic7XG4gIG1lc3NhZ2U/OiBzdHJpbmc7XG59XG5cbmV4cG9ydCBkZWZhdWx0IGFzeW5jIGZ1bmN0aW9uIGhhbmRsZXIoXG4gIHJlcTogTmV4dEFwaVJlcXVlc3QsXG4gIHJlczogTmV4dEFwaVJlc3BvbnNlXG4pIHtcbiAgaWYgKHJlcS5tZXRob2QgIT09ICdQT1NUJykge1xuICAgIHJlcy5zZXRIZWFkZXIoJ0FsbG93JywgWydQT1NUJ10pO1xuICAgIHJldHVybiByZXMuc3RhdHVzKDQwNSkuZW5kKGBNZXRob2QgJHtyZXEubWV0aG9kfSBOb3QgQWxsb3dlZGApO1xuICB9XG5cbiAgY29uc3QgZm9ybSA9IGZvcm1pZGFibGUoe1xuICAgIGtlZXBFeHRlbnNpb25zOiB0cnVlLFxuICAgIC8vIERlZmluZSBhIHRlbXBvcmFyeSBkaXJlY3RvcnkgZm9yIHVwbG9hZHMgaWYgbmVlZGVkLCBvciBsZXQgZm9ybWlkYWJsZSBoYW5kbGUgaXRcbiAgICAvLyB1cGxvYWREaXI6IHBhdGguam9pbihwcm9jZXNzLmN3ZCgpLCAnLnRtcF91cGxvYWRzJyksIC8vIEVuc3VyZSB0aGlzIGRpciBleGlzdHMgYW5kIGlzIHdyaXRhYmxlXG4gICAgLy8gbWF4RmlsZVNpemU6IDEwMCAqIDEwMjQgKiAxMDI0LCAvLyAxMDBNQiBsaW1pdCBleGFtcGxlXG4gIH0pO1xuXG4gIHRyeSB7XG4gICAgY29uc3Qgb3BlcmF0aW9uTmFtZSA9ICdwcm9jZXNzUmVjb3JkZWRBdWRpb05vdGVBUEknOyAvLyBGb3IgbG9nZ2luZyBjb250ZXh0XG5cbiAgICBjb25zdCBwYXJzZVByb21pc2UgPSBuZXcgUHJvbWlzZTxGb3JtaWRhYmxlUGFyc2VSZXN1bHQ+KFxuICAgICAgKHJlc29sdmUsIHJlamVjdCkgPT4ge1xuICAgICAgICBmb3JtLnBhcnNlKHJlcSwgKGVyciwgZmllbGRzLCBmaWxlcykgPT4ge1xuICAgICAgICAgIGlmIChlcnIpIHtcbiAgICAgICAgICAgIGFwcFNlcnZpY2VMb2dnZXIuZXJyb3IoXG4gICAgICAgICAgICAgIGBbJHtvcGVyYXRpb25OYW1lfV0gRm9ybWlkYWJsZSBwYXJzaW5nIGVycm9yLmAsXG4gICAgICAgICAgICAgIHsgZXJyb3I6IGVyci5tZXNzYWdlLCBzdGFjazogZXJyLnN0YWNrLCBkZXRhaWxzOiBlcnIgfVxuICAgICAgICAgICAgKTtcbiAgICAgICAgICAgIHJldHVybiByZWplY3QoZXJyKTtcbiAgICAgICAgICB9XG4gICAgICAgICAgcmVzb2x2ZSh7IGZpZWxkcywgZmlsZXMgfSk7XG4gICAgICAgIH0pO1xuICAgICAgfVxuICAgICk7XG5cbiAgICBjb25zdCB7IGZpZWxkcywgZmlsZXMgfSA9IGF3YWl0IHBhcnNlUHJvbWlzZTtcbiAgICBhcHBTZXJ2aWNlTG9nZ2VyLmluZm8oYFske29wZXJhdGlvbk5hbWV9XSBGb3JtIHBhcnNlZCBzdWNjZXNzZnVsbHkuYCwge1xuICAgICAgZmlsZUtleXM6IE9iamVjdC5rZXlzKGZpbGVzKSxcbiAgICAgIGZpZWxkS2V5czogT2JqZWN0LmtleXMoZmllbGRzKS5qb2luKCcsICcpLFxuICAgIH0pO1xuXG4gICAgY29uc3QgYXVkaW9GaWxlQXJyYXkgPSBmaWxlcy5hdWRpb19maWxlO1xuICAgIGNvbnN0IHRpdGxlQXJyYXkgPSBmaWVsZHMudGl0bGU7XG4gICAgY29uc3QgdXNlcklkQXJyYXkgPSBmaWVsZHMudXNlcl9pZDtcbiAgICBjb25zdCBsaW5rZWRFdmVudElkQXJyYXkgPSBmaWVsZHMubGlua2VkX2V2ZW50X2lkOyAvLyBPcHRpb25hbFxuXG4gICAgaWYgKFxuICAgICAgIWF1ZGlvRmlsZUFycmF5IHx8XG4gICAgICAhQXJyYXkuaXNBcnJheShhdWRpb0ZpbGVBcnJheSkgfHxcbiAgICAgIGF1ZGlvRmlsZUFycmF5Lmxlbmd0aCA9PT0gMFxuICAgICkge1xuICAgICAgcmV0dXJuIHJlc1xuICAgICAgICAuc3RhdHVzKDQwMClcbiAgICAgICAgLmpzb24oeyBvazogZmFsc2UsIGVycm9yOiB7IG1lc3NhZ2U6ICdObyBhdWRpbyBmaWxlIHVwbG9hZGVkLicgfSB9KTtcbiAgICB9XG4gICAgY29uc3QgYXVkaW9GaWxlID0gYXVkaW9GaWxlQXJyYXlbMF07XG5cbiAgICBpZiAoXG4gICAgICAhdGl0bGVBcnJheSB8fFxuICAgICAgIUFycmF5LmlzQXJyYXkodGl0bGVBcnJheSkgfHxcbiAgICAgIHRpdGxlQXJyYXkubGVuZ3RoID09PSAwIHx8XG4gICAgICAhdGl0bGVBcnJheVswXVxuICAgICkge1xuICAgICAgcmV0dXJuIHJlc1xuICAgICAgICAuc3RhdHVzKDQwMClcbiAgICAgICAgLmpzb24oe1xuICAgICAgICAgIG9rOiBmYWxzZSxcbiAgICAgICAgICBlcnJvcjogeyBtZXNzYWdlOiAnTWlzc2luZyB0aXRsZSBmb3IgdGhlIGF1ZGlvIG5vdGUuJyB9LFxuICAgICAgICB9KTtcbiAgICB9XG4gICAgY29uc3QgdGl0bGUgPSB0aXRsZUFycmF5WzBdO1xuXG4gICAgaWYgKFxuICAgICAgIXVzZXJJZEFycmF5IHx8XG4gICAgICAhQXJyYXkuaXNBcnJheSh1c2VySWRBcnJheSkgfHxcbiAgICAgIHVzZXJJZEFycmF5Lmxlbmd0aCA9PT0gMCB8fFxuICAgICAgIXVzZXJJZEFycmF5WzBdXG4gICAgKSB7XG4gICAgICByZXR1cm4gcmVzXG4gICAgICAgIC5zdGF0dXMoNDAwKVxuICAgICAgICAuanNvbih7IG9rOiBmYWxzZSwgZXJyb3I6IHsgbWVzc2FnZTogJ01pc3NpbmcgdXNlcl9pZC4nIH0gfSk7XG4gICAgfVxuICAgIGNvbnN0IHVzZXJJZCA9IHVzZXJJZEFycmF5WzBdO1xuXG4gICAgY29uc3QgbGlua2VkRXZlbnRJZCA9XG4gICAgICBsaW5rZWRFdmVudElkQXJyYXkgJiZcbiAgICAgIEFycmF5LmlzQXJyYXkobGlua2VkRXZlbnRJZEFycmF5KSAmJlxuICAgICAgbGlua2VkRXZlbnRJZEFycmF5Lmxlbmd0aCA+IDBcbiAgICAgICAgPyBsaW5rZWRFdmVudElkQXJyYXlbMF1cbiAgICAgICAgOiB1bmRlZmluZWQ7XG5cbiAgICBpZiAoIWF1ZGlvRmlsZS5maWxlcGF0aCkge1xuICAgICAgcmV0dXJuIHJlc1xuICAgICAgICAuc3RhdHVzKDUwMClcbiAgICAgICAgLmpzb24oe1xuICAgICAgICAgIG9rOiBmYWxzZSxcbiAgICAgICAgICBlcnJvcjogeyBtZXNzYWdlOiAnVXBsb2FkZWQgZmlsZSBwYXRoIGlzIG1pc3NpbmcuJyB9LFxuICAgICAgICB9KTtcbiAgICB9XG5cbiAgICAvLyBBdCB0aGlzIHBvaW50LCBhdWRpb0ZpbGUuZmlsZXBhdGggcG9pbnRzIHRvIHRoZSB0ZW1wb3JhcnkgbG9jYXRpb24gb2YgdGhlIHVwbG9hZGVkIGZpbGUuXG4gICAgLy8gV2UgbmVlZCB0byBzZW5kIHRoaXMgZmlsZSB0byB0aGUgUHl0aG9uIGJhY2tlbmQuXG5cbiAgICBjb25zdCBweXRob25FbmRwb2ludCA9IGAke1BZVEhPTl9QUk9DRVNTSU5HX1NFUlZJQ0VfVVJMfS9hcGkvaW50ZXJuYWwvcHJvY2Vzc19hdWRpb19ub3RlX2RhdGFgO1xuICAgIGFwcFNlcnZpY2VMb2dnZXIuaW5mbyhcbiAgICAgIGBbJHtvcGVyYXRpb25OYW1lfV0gRm9yd2FyZGluZyBhdWRpbyB0byBQeXRob24gYmFja2VuZC5gLFxuICAgICAge1xuICAgICAgICBweXRob25FbmRwb2ludCxcbiAgICAgICAgdXNlcklkLFxuICAgICAgICB0aXRsZSxcbiAgICAgICAgbGlua2VkRXZlbnRJZCxcbiAgICAgICAgYXVkaW9GaWxlUGF0aDogYXVkaW9GaWxlLmZpbGVwYXRoLFxuICAgICAgfVxuICAgICk7XG5cbiAgICBjb25zdCBiYWNrZW5kRm9ybURhdGEgPSBuZXcgRm9ybURhdGEoKTtcbiAgICBjb25zdCBmaWxlU3RyZWFtID0gZnMuY3JlYXRlUmVhZFN0cmVhbShhdWRpb0ZpbGUuZmlsZXBhdGgpO1xuXG4gICAgLy8gVXNlIG9yaWdpbmFsIGZpbGVuYW1lIG9yIGEgZ2VuZXJpYyBvbmUuIEZvcm1pZGFibGUgcHJvdmlkZXMgb3JpZ2luYWxGaWxlbmFtZS5cbiAgICBjb25zdCBvcmlnaW5hbEZpbGVuYW1lID0gYXVkaW9GaWxlLm9yaWdpbmFsRmlsZW5hbWUgfHwgJ2F1ZGlvLnRtcCc7XG4gICAgYmFja2VuZEZvcm1EYXRhLmFwcGVuZCgnYXVkaW9fZmlsZScsIGZpbGVTdHJlYW0gYXMgYW55LCBvcmlnaW5hbEZpbGVuYW1lKTsgLy8gQ2FzdGluZyB0byBhbnkgZm9yIEZvcm1EYXRhIGNvbXBhdGliaWxpdHkgd2l0aCBzdHJlYW1cbiAgICBiYWNrZW5kRm9ybURhdGEuYXBwZW5kKCd0aXRsZScsIHRpdGxlKTtcbiAgICBiYWNrZW5kRm9ybURhdGEuYXBwZW5kKCd1c2VyX2lkJywgdXNlcklkKTtcbiAgICBpZiAobGlua2VkRXZlbnRJZCkge1xuICAgICAgYmFja2VuZEZvcm1EYXRhLmFwcGVuZCgnbGlua2VkX2V2ZW50X2lkJywgbGlua2VkRXZlbnRJZCk7XG4gICAgfVxuICAgIC8vIEFkZCBvdGhlciBuZWNlc3NhcnkgbWV0YWRhdGEgZm9yIHRoZSBQeXRob24gc2VydmljZVxuICAgIC8vIGJhY2tlbmRGb3JtRGF0YS5hcHBlbmQoJ25vdGlvbl9zb3VyY2VfdGV4dCcsICdJbi1QZXJzb24gQXVkaW8gTm90ZSB2aWEgQWdlbnQnKTtcblxuICAgIHRyeSB7XG4gICAgICAvLyBVc2luZyByZXNpbGllbnRHb3QgZm9yIHRoZSBjYWxsIHRvIFB5dGhvbiBiYWNrZW5kXG4gICAgICBjb25zdCBnb3RPcHRpb25zID0ge1xuICAgICAgICBib2R5OiBiYWNrZW5kRm9ybURhdGEsIC8vIFBhc3MgRm9ybURhdGEgaW5zdGFuY2UgYXMgYm9keVxuICAgICAgICBoZWFkZXJzOiB7XG4gICAgICAgICAgLy8gJ2dvdCcgd2lsbCBzZXQgQ29udGVudC1UeXBlIGF1dG9tYXRpY2FsbHkgZm9yIEZvcm1EYXRhXG4gICAgICAgICAgLy8gQWRkIGFueSBhdXRoIGhlYWRlcnMgaWYgUHl0aG9uIHNlcnZpY2UgcmVxdWlyZXMgdGhlbVxuICAgICAgICB9LFxuICAgICAgICAvLyByZXNpbGllbnRHb3QgaGFuZGxlcyB0aW1lb3V0IGludGVybmFsbHksIGRlZmF1bHRzIHRvIDE1cy5cbiAgICAgICAgLy8gbWF4Qm9keUxlbmd0aC9tYXhDb250ZW50TGVuZ3RoIGFyZSBub3QgZGlyZWN0IGdvdCBvcHRpb25zLFxuICAgICAgICAvLyBidXQgZ290IHR5cGljYWxseSBoYW5kbGVzIGxhcmdlIHN0cmVhbXMuIE1vbml0b3IgaWYgaXNzdWVzIGFyaXNlLlxuICAgICAgICByZXNwb25zZVR5cGU6ICdqc29uJyBhcyAnanNvbicsIC8vIEV4cGVjdCBhIEpTT04gcmVzcG9uc2VcbiAgICAgIH07XG5cbiAgICAgIGNvbnN0IHB5dGhvblNlcnZpY2VSZXNwb25zZURhdGEgPSAoYXdhaXQgcmVzaWxpZW50R290KFxuICAgICAgICAncG9zdCcsXG4gICAgICAgIHB5dGhvbkVuZHBvaW50LFxuICAgICAgICBnb3RPcHRpb25zLFxuICAgICAgICBgJHtvcGVyYXRpb25OYW1lfV9QeXRob25CYWNrZW5kQ2FsbGBcbiAgICAgICkpIGFzIFB5dGhvbkJhY2tlbmRSZXNwb25zZTtcblxuICAgICAgLy8gQ2xlYW4gdXAgdGhlIHRlbXBvcmFyeSBmaWxlIHVwbG9hZGVkIGJ5IGZvcm1pZGFibGVcbiAgICAgIGZzLnVubGluayhhdWRpb0ZpbGUuZmlsZXBhdGgsICh1bmxpbmtFcnIpID0+IHtcbiAgICAgICAgaWYgKHVubGlua0VycilcbiAgICAgICAgICBhcHBTZXJ2aWNlTG9nZ2VyLmVycm9yKFxuICAgICAgICAgICAgYFske29wZXJhdGlvbk5hbWV9XSBFcnJvciBkZWxldGluZyB0ZW1wIGF1ZGlvIGZpbGUuYCxcbiAgICAgICAgICAgIHtcbiAgICAgICAgICAgICAgZmlsZXBhdGg6IGF1ZGlvRmlsZS5maWxlcGF0aCxcbiAgICAgICAgICAgICAgZXJyb3I6IHVubGlua0Vyci5tZXNzYWdlLFxuICAgICAgICAgICAgICBzdGFjazogdW5saW5rRXJyLnN0YWNrLFxuICAgICAgICAgICAgfVxuICAgICAgICAgICk7XG4gICAgICB9KTtcblxuICAgICAgLy8gQ2hlY2sgUHl0aG9uIGJhY2tlbmQgcmVzcG9uc2VcbiAgICAgIC8vIHJlc2lsaWVudEdvdCByZXR1cm5zIHRoZSBib2R5IGRpcmVjdGx5LCBzbyB3ZSBhY2Nlc3MgcHJvcGVydGllcyBvbiBweXRob25TZXJ2aWNlUmVzcG9uc2VEYXRhXG4gICAgICBpZiAoXG4gICAgICAgIHB5dGhvblNlcnZpY2VSZXNwb25zZURhdGEgJiZcbiAgICAgICAgKHB5dGhvblNlcnZpY2VSZXNwb25zZURhdGEub2sgfHxcbiAgICAgICAgICBweXRob25TZXJ2aWNlUmVzcG9uc2VEYXRhLnN0YXR1cyA9PT0gJ3N1Y2Nlc3MnKSAmJlxuICAgICAgICBweXRob25TZXJ2aWNlUmVzcG9uc2VEYXRhLmRhdGFcbiAgICAgICkge1xuICAgICAgICBhcHBTZXJ2aWNlTG9nZ2VyLmluZm8oXG4gICAgICAgICAgYFske29wZXJhdGlvbk5hbWV9XSBQeXRob24gYmFja2VuZCBwcm9jZXNzZWQgYXVkaW8gc3VjY2Vzc2Z1bGx5LmAsXG4gICAgICAgICAgeyB1c2VySWQsIHRpdGxlLCByZXNwb25zZURhdGE6IHB5dGhvblNlcnZpY2VSZXNwb25zZURhdGEuZGF0YSB9XG4gICAgICAgICk7XG4gICAgICAgIHJldHVybiByZXMuc3RhdHVzKDIwMCkuanNvbih7XG4gICAgICAgICAgb2s6IHRydWUsXG4gICAgICAgICAgbWVzc2FnZTogJ0F1ZGlvIG5vdGUgcHJvY2Vzc2VkIHN1Y2Nlc3NmdWxseS4nLFxuICAgICAgICAgIGRhdGE6IHB5dGhvblNlcnZpY2VSZXNwb25zZURhdGEuZGF0YSxcbiAgICAgICAgfSk7XG4gICAgICB9IGVsc2Uge1xuICAgICAgICBjb25zdCBlcnJvck1zZyA9XG4gICAgICAgICAgcHl0aG9uU2VydmljZVJlc3BvbnNlRGF0YT8uZXJyb3I/Lm1lc3NhZ2UgfHxcbiAgICAgICAgICBweXRob25TZXJ2aWNlUmVzcG9uc2VEYXRhPy5tZXNzYWdlIHx8XG4gICAgICAgICAgJ1Vua25vd24gZXJyb3IgZnJvbSBQeXRob24gcHJvY2Vzc2luZyBzZXJ2aWNlLic7XG4gICAgICAgIGFwcFNlcnZpY2VMb2dnZXIuZXJyb3IoXG4gICAgICAgICAgYFske29wZXJhdGlvbk5hbWV9XSBFcnJvciByZXNwb25zZSBmcm9tIFB5dGhvbiBiYWNrZW5kLmAsXG4gICAgICAgICAge1xuICAgICAgICAgICAgdXNlcklkLFxuICAgICAgICAgICAgdGl0bGUsXG4gICAgICAgICAgICBlcnJvck1zZyxcbiAgICAgICAgICAgIHB5dGhvblJlc3BvbnNlRGF0YTogcHl0aG9uU2VydmljZVJlc3BvbnNlRGF0YSxcbiAgICAgICAgICB9XG4gICAgICAgICk7XG4gICAgICAgIHJldHVybiByZXNcbiAgICAgICAgICAuc3RhdHVzKDUwMClcbiAgICAgICAgICAuanNvbih7XG4gICAgICAgICAgICBvazogZmFsc2UsXG4gICAgICAgICAgICBlcnJvcjoge1xuICAgICAgICAgICAgICBtZXNzYWdlOiBlcnJvck1zZyxcbiAgICAgICAgICAgICAgY29kZTpcbiAgICAgICAgICAgICAgICBweXRob25TZXJ2aWNlUmVzcG9uc2VEYXRhPy5lcnJvcj8uY29kZSB8fFxuICAgICAgICAgICAgICAgICdQWVRIT05fUFJPQ0VTU0lOR19GQUlMRUQnLFxuICAgICAgICAgICAgfSxcbiAgICAgICAgICB9KTtcbiAgICAgIH1cbiAgICB9IGNhdGNoIChzZXJ2aWNlQ2FsbEVycm9yOiBhbnkpIHtcbiAgICAgIC8vIENhdGNoIGVycm9ycyBmcm9tIHJlc2lsaWVudEdvdCBvciBmaWxlIG9wZXJhdGlvbnNcbiAgICAgIGZzLnVubGluayhhdWRpb0ZpbGUuZmlsZXBhdGgsICh1bmxpbmtFcnIpID0+IHtcbiAgICAgICAgLy8gRW5zdXJlIGNsZWFudXAgb24gZXJyb3IgdG9vXG4gICAgICAgIGlmICh1bmxpbmtFcnIpXG4gICAgICAgICAgYXBwU2VydmljZUxvZ2dlci5lcnJvcihcbiAgICAgICAgICAgIGBbJHtvcGVyYXRpb25OYW1lfV0gRXJyb3IgZGVsZXRpbmcgdGVtcCBhdWRpbyBmaWxlIGFmdGVyIHNlcnZpY2UgY2FsbCBlcnJvci5gLFxuICAgICAgICAgICAge1xuICAgICAgICAgICAgICBmaWxlcGF0aDogYXVkaW9GaWxlLmZpbGVwYXRoLFxuICAgICAgICAgICAgICBlcnJvcjogdW5saW5rRXJyLm1lc3NhZ2UsXG4gICAgICAgICAgICAgIHN0YWNrOiB1bmxpbmtFcnIuc3RhY2ssXG4gICAgICAgICAgICB9XG4gICAgICAgICAgKTtcbiAgICAgIH0pO1xuXG4gICAgICBhcHBTZXJ2aWNlTG9nZ2VyLmVycm9yKFxuICAgICAgICBgWyR7b3BlcmF0aW9uTmFtZX1dIEVycm9yIGNhbGxpbmcgUHl0aG9uIGJhY2tlbmQgb3IgZHVyaW5nIGZpbGUgb3BzLmAsXG4gICAgICAgIHtcbiAgICAgICAgICB1c2VySWQsXG4gICAgICAgICAgdGl0bGUsXG4gICAgICAgICAgZXJyb3I6IHNlcnZpY2VDYWxsRXJyb3IubWVzc2FnZSxcbiAgICAgICAgICBzdGFjazogc2VydmljZUNhbGxFcnJvci5zdGFjayxcbiAgICAgICAgICBkZXRhaWxzOiBzZXJ2aWNlQ2FsbEVycm9yLFxuICAgICAgICB9XG4gICAgICApO1xuXG4gICAgICBsZXQgZXJyb3JNZXNzYWdlID0gJ0Vycm9yIGNvbW11bmljYXRpbmcgd2l0aCBhdWRpbyBwcm9jZXNzaW5nIHNlcnZpY2UuJztcbiAgICAgIC8vIElmIHNlcnZpY2VDYWxsRXJyb3IgaXMgZnJvbSByZXNpbGllbnRHb3QsIGl0IG1pZ2h0IGhhdmUgcmVzcG9uc2UgZGV0YWlsc1xuICAgICAgaWYgKHNlcnZpY2VDYWxsRXJyb3IucmVzcG9uc2U/LmJvZHkpIHtcbiAgICAgICAgdHJ5IHtcbiAgICAgICAgICBjb25zdCBlcnJvckJvZHkgPVxuICAgICAgICAgICAgdHlwZW9mIHNlcnZpY2VDYWxsRXJyb3IucmVzcG9uc2UuYm9keSA9PT0gJ3N0cmluZydcbiAgICAgICAgICAgICAgPyBKU09OLnBhcnNlKHNlcnZpY2VDYWxsRXJyb3IucmVzcG9uc2UuYm9keSlcbiAgICAgICAgICAgICAgOiBzZXJ2aWNlQ2FsbEVycm9yLnJlc3BvbnNlLmJvZHk7XG4gICAgICAgICAgZXJyb3JNZXNzYWdlID1cbiAgICAgICAgICAgIGVycm9yQm9keS5tZXNzYWdlIHx8XG4gICAgICAgICAgICBlcnJvckJvZHkuZXJyb3I/Lm1lc3NhZ2UgfHxcbiAgICAgICAgICAgIEpTT04uc3RyaW5naWZ5KGVycm9yQm9keSk7XG4gICAgICAgIH0gY2F0Y2ggKGUpIHtcbiAgICAgICAgICBlcnJvck1lc3NhZ2UgPVxuICAgICAgICAgICAgdHlwZW9mIHNlcnZpY2VDYWxsRXJyb3IucmVzcG9uc2UuYm9keSA9PT0gJ3N0cmluZydcbiAgICAgICAgICAgICAgPyBzZXJ2aWNlQ2FsbEVycm9yLnJlc3BvbnNlLmJvZHlcbiAgICAgICAgICAgICAgOiAnVW5wYXJzZWFibGUgZXJyb3IgZnJvbSBzZXJ2aWNlJztcbiAgICAgICAgfVxuICAgICAgfSBlbHNlIGlmIChzZXJ2aWNlQ2FsbEVycm9yLm1lc3NhZ2UpIHtcbiAgICAgICAgZXJyb3JNZXNzYWdlID0gc2VydmljZUNhbGxFcnJvci5tZXNzYWdlO1xuICAgICAgfVxuICAgICAgcmV0dXJuIHJlc1xuICAgICAgICAuc3RhdHVzKDUwMilcbiAgICAgICAgLmpzb24oe1xuICAgICAgICAgIG9rOiBmYWxzZSxcbiAgICAgICAgICBlcnJvcjoge1xuICAgICAgICAgICAgbWVzc2FnZTogZXJyb3JNZXNzYWdlLFxuICAgICAgICAgICAgY29kZTogJ1BZVEhPTl9TRVJWSUNFX0NPTU1VTklDQVRJT05fRVJST1InLFxuICAgICAgICAgIH0sXG4gICAgICAgIH0pO1xuICAgIH1cbiAgfSBjYXRjaCAoZXJyb3I6IGFueSkge1xuICAgIGFwcFNlcnZpY2VMb2dnZXIuZXJyb3IoYFske29wZXJhdGlvbk5hbWV9XSBPdmVyYWxsIGVycm9yIGluIEFQSSBoYW5kbGVyLmAsIHtcbiAgICAgIGVycm9yOiBlcnJvci5tZXNzYWdlLFxuICAgICAgc3RhY2s6IGVycm9yLnN0YWNrLFxuICAgICAgZGV0YWlsczogZXJyb3IsXG4gICAgfSk7XG4gICAgcmV0dXJuIHJlc1xuICAgICAgLnN0YXR1cyg1MDApXG4gICAgICAuanNvbih7XG4gICAgICAgIG9rOiBmYWxzZSxcbiAgICAgICAgZXJyb3I6IHtcbiAgICAgICAgICBtZXNzYWdlOiBgU2VydmVyIGVycm9yOiAke2Vycm9yLm1lc3NhZ2UgfHwgJ0ZhaWxlZCB0byBwcm9jZXNzIHJlcXVlc3QnfWAsXG4gICAgICAgIH0sXG4gICAgICB9KTtcbiAgfVxufVxuIl19