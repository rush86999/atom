"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.config = void 0;
exports.default = handler;
const formidable_1 = __importDefault(require("formidable"));
const note_utils_1 = require("../../../project/functions/note_utils");
exports.config = {
    api: {
        bodyParser: false,
    },
};
async function handler(req, res) {
    if (req.method === 'POST') {
        const form = new formidable_1.default.IncomingForm();
        form.parse(req, async (err, fields, files) => {
            if (err) {
                res.status(500).json({ message: 'Error parsing form data' });
                return;
            }
            const audioFile = files.audio;
            const title = fields.title;
            if (!audioFile) {
                res.status(400).json({ message: 'No audio file uploaded' });
                return;
            }
            const audioFilePath = audioFile.filepath;
            const result = await (0, note_utils_1.process_silent_audio_recording_for_notion)(audioFilePath, title);
            if (result.status === 'success') {
                res.status(200).json(result.data);
            }
            else {
                res.status(500).json({ message: result.message });
            }
        });
    }
    else {
        res.status(405).json({ message: 'Method not allowed' });
    }
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiY3JlYXRlLW5vdGUtZnJvbS1zaWxlbnQtYXVkaW8tcmVjb3JkaW5nLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsiY3JlYXRlLW5vdGUtZnJvbS1zaWxlbnQtYXVkaW8tcmVjb3JkaW5nLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiI7Ozs7OztBQVlBLDBCQW1DQztBQTlDRCw0REFBb0M7QUFHcEMsc0VBQWtHO0FBRXJGLFFBQUEsTUFBTSxHQUFHO0lBQ3BCLEdBQUcsRUFBRTtRQUNILFVBQVUsRUFBRSxLQUFLO0tBQ2xCO0NBQ0YsQ0FBQztBQUVhLEtBQUssVUFBVSxPQUFPLENBQ25DLEdBQW1CLEVBQ25CLEdBQW9CO0lBRXBCLElBQUksR0FBRyxDQUFDLE1BQU0sS0FBSyxNQUFNLEVBQUUsQ0FBQztRQUMxQixNQUFNLElBQUksR0FBRyxJQUFJLG9CQUFVLENBQUMsWUFBWSxFQUFFLENBQUM7UUFDM0MsSUFBSSxDQUFDLEtBQUssQ0FBQyxHQUFHLEVBQUUsS0FBSyxFQUFFLEdBQUcsRUFBRSxNQUFNLEVBQUUsS0FBSyxFQUFFLEVBQUU7WUFDM0MsSUFBSSxHQUFHLEVBQUUsQ0FBQztnQkFDUixHQUFHLENBQUMsTUFBTSxDQUFDLEdBQUcsQ0FBQyxDQUFDLElBQUksQ0FBQyxFQUFFLE9BQU8sRUFBRSx5QkFBeUIsRUFBRSxDQUFDLENBQUM7Z0JBQzdELE9BQU87WUFDVCxDQUFDO1lBRUQsTUFBTSxTQUFTLEdBQUcsS0FBSyxDQUFDLEtBQUssQ0FBQztZQUM5QixNQUFNLEtBQUssR0FBRyxNQUFNLENBQUMsS0FBZSxDQUFDO1lBRXJDLElBQUksQ0FBQyxTQUFTLEVBQUUsQ0FBQztnQkFDZixHQUFHLENBQUMsTUFBTSxDQUFDLEdBQUcsQ0FBQyxDQUFDLElBQUksQ0FBQyxFQUFFLE9BQU8sRUFBRSx3QkFBd0IsRUFBRSxDQUFDLENBQUM7Z0JBQzVELE9BQU87WUFDVCxDQUFDO1lBRUQsTUFBTSxhQUFhLEdBQUcsU0FBUyxDQUFDLFFBQVEsQ0FBQztZQUN6QyxNQUFNLE1BQU0sR0FBRyxNQUFNLElBQUEsc0RBQXlDLEVBQzVELGFBQWEsRUFDYixLQUFLLENBQ04sQ0FBQztZQUVGLElBQUksTUFBTSxDQUFDLE1BQU0sS0FBSyxTQUFTLEVBQUUsQ0FBQztnQkFDaEMsR0FBRyxDQUFDLE1BQU0sQ0FBQyxHQUFHLENBQUMsQ0FBQyxJQUFJLENBQUMsTUFBTSxDQUFDLElBQUksQ0FBQyxDQUFDO1lBQ3BDLENBQUM7aUJBQU0sQ0FBQztnQkFDTixHQUFHLENBQUMsTUFBTSxDQUFDLEdBQUcsQ0FBQyxDQUFDLElBQUksQ0FBQyxFQUFFLE9BQU8sRUFBRSxNQUFNLENBQUMsT0FBTyxFQUFFLENBQUMsQ0FBQztZQUNwRCxDQUFDO1FBQ0gsQ0FBQyxDQUFDLENBQUM7SUFDTCxDQUFDO1NBQU0sQ0FBQztRQUNOLEdBQUcsQ0FBQyxNQUFNLENBQUMsR0FBRyxDQUFDLENBQUMsSUFBSSxDQUFDLEVBQUUsT0FBTyxFQUFFLG9CQUFvQixFQUFFLENBQUMsQ0FBQztJQUMxRCxDQUFDO0FBQ0gsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB0eXBlIHsgTmV4dEFwaVJlcXVlc3QsIE5leHRBcGlSZXNwb25zZSB9IGZyb20gJ25leHQnO1xuaW1wb3J0IGZvcm1pZGFibGUgZnJvbSAnZm9ybWlkYWJsZSc7XG5pbXBvcnQgZnMgZnJvbSAnZnMnO1xuaW1wb3J0IHBhdGggZnJvbSAncGF0aCc7XG5pbXBvcnQgeyBwcm9jZXNzX3NpbGVudF9hdWRpb19yZWNvcmRpbmdfZm9yX25vdGlvbiB9IGZyb20gJy4uLy4uLy4uL3Byb2plY3QvZnVuY3Rpb25zL25vdGVfdXRpbHMnO1xuXG5leHBvcnQgY29uc3QgY29uZmlnID0ge1xuICBhcGk6IHtcbiAgICBib2R5UGFyc2VyOiBmYWxzZSxcbiAgfSxcbn07XG5cbmV4cG9ydCBkZWZhdWx0IGFzeW5jIGZ1bmN0aW9uIGhhbmRsZXIoXG4gIHJlcTogTmV4dEFwaVJlcXVlc3QsXG4gIHJlczogTmV4dEFwaVJlc3BvbnNlXG4pIHtcbiAgaWYgKHJlcS5tZXRob2QgPT09ICdQT1NUJykge1xuICAgIGNvbnN0IGZvcm0gPSBuZXcgZm9ybWlkYWJsZS5JbmNvbWluZ0Zvcm0oKTtcbiAgICBmb3JtLnBhcnNlKHJlcSwgYXN5bmMgKGVyciwgZmllbGRzLCBmaWxlcykgPT4ge1xuICAgICAgaWYgKGVycikge1xuICAgICAgICByZXMuc3RhdHVzKDUwMCkuanNvbih7IG1lc3NhZ2U6ICdFcnJvciBwYXJzaW5nIGZvcm0gZGF0YScgfSk7XG4gICAgICAgIHJldHVybjtcbiAgICAgIH1cblxuICAgICAgY29uc3QgYXVkaW9GaWxlID0gZmlsZXMuYXVkaW87XG4gICAgICBjb25zdCB0aXRsZSA9IGZpZWxkcy50aXRsZSBhcyBzdHJpbmc7XG5cbiAgICAgIGlmICghYXVkaW9GaWxlKSB7XG4gICAgICAgIHJlcy5zdGF0dXMoNDAwKS5qc29uKHsgbWVzc2FnZTogJ05vIGF1ZGlvIGZpbGUgdXBsb2FkZWQnIH0pO1xuICAgICAgICByZXR1cm47XG4gICAgICB9XG5cbiAgICAgIGNvbnN0IGF1ZGlvRmlsZVBhdGggPSBhdWRpb0ZpbGUuZmlsZXBhdGg7XG4gICAgICBjb25zdCByZXN1bHQgPSBhd2FpdCBwcm9jZXNzX3NpbGVudF9hdWRpb19yZWNvcmRpbmdfZm9yX25vdGlvbihcbiAgICAgICAgYXVkaW9GaWxlUGF0aCxcbiAgICAgICAgdGl0bGVcbiAgICAgICk7XG5cbiAgICAgIGlmIChyZXN1bHQuc3RhdHVzID09PSAnc3VjY2VzcycpIHtcbiAgICAgICAgcmVzLnN0YXR1cygyMDApLmpzb24ocmVzdWx0LmRhdGEpO1xuICAgICAgfSBlbHNlIHtcbiAgICAgICAgcmVzLnN0YXR1cyg1MDApLmpzb24oeyBtZXNzYWdlOiByZXN1bHQubWVzc2FnZSB9KTtcbiAgICAgIH1cbiAgICB9KTtcbiAgfSBlbHNlIHtcbiAgICByZXMuc3RhdHVzKDQwNSkuanNvbih7IG1lc3NhZ2U6ICdNZXRob2Qgbm90IGFsbG93ZWQnIH0pO1xuICB9XG59XG4iXX0=