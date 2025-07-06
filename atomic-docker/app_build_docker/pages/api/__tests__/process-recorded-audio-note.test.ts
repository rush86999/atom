import handler from '../process-recorded-audio-note'; // Adjust path to your API route
import { createMocks, RequestMethod } from 'node-mocks-http'; // For mocking req/res
import formidable from 'formidable';
import fs from 'fs';
import { appServiceLogger } from '../../../lib/logger'; // Actual logger
import { resilientGot } from '../../../lib/api-backend-helper'; // The resilientGot we want to mock

// Mock formidable
jest.mock('formidable');

// Mock fs, specifically createReadStream and unlink
jest.mock('fs', () => ({
    ...jest.requireActual('fs'), // Import and retain default behavior
    createReadStream: jest.fn().mockReturnValue({ pipe: jest.fn(), on: jest.fn() }), // Simple mock for stream
    unlink: jest.fn((path, callback) => callback(null)), // Mock unlink to succeed by default
}));


// Mock resilientGot from its actual module path
jest.mock('../../../lib/api-backend-helper', () => ({
    ...jest.requireActual('../../../lib/api-backend-helper'), // Keep other exports
    resilientGot: jest.fn(), // Mock resilientGot specifically
}));
const mockedResilientGot = resilientGot as jest.Mock;


// Mock the logger
jest.mock('../../../lib/logger', () => ({
    appServiceLogger: {
        info: jest.fn(),
        warn: jest.fn(),
        error: jest.fn(),
        debug: jest.fn(),
    },
}));
const mockedLogger = appServiceLogger as jest.Mocked<typeof appServiceLogger>;


describe('/api/process-recorded-audio-note API Endpoint', () => {
    let mockParse: jest.Mock;

    beforeEach(() => {
        mockedLogger.info.mockClear();
        mockedLogger.warn.mockClear();
        mockedLogger.error.mockClear();
        mockedLogger.debug.mockClear();
        mockedResilientGot.mockReset();
        (fs.unlink as jest.Mock).mockClear();


        // Setup formidable mock for each test
        mockParse = jest.fn((req, callback) => {
            // Simulate successful parsing with mock data by default
            const mockFiles = {
                audio_file: [{ filepath: 'mock/path/audio.wav', originalFilename: 'audio.wav' }],
            };
            const mockFields = {
                title: ['Test Title'],
                user_id: ['test-user-id'],
            };
            callback(null, mockFields, mockFiles);
        });
        (formidable as jest.Mock).mockImplementation(() => ({
            parse: mockParse,
            keepExtensions: true,
        }));
    });

    it('should return 405 if method is not POST', async () => {
        const { req, res } = createMocks({ method: 'GET' });
        await handler(req as any, res as any);
        expect(res._getStatusCode()).toBe(405);
    });

    it('should return 400 if audio_file is missing', async () => {
        mockParse.mockImplementationOnce((req, callback) => {
            callback(null, { title: ['Test'], user_id: ['user1'] }, {}); // No audio_file
        });
        const { req, res } = createMocks({ method: 'POST' });
        await handler(req as any, res as any);
        expect(res._getStatusCode()).toBe(400);
        expect(JSON.parse(res._getData()).error.message).toBe('No audio file uploaded.');
    });

    it('should return 400 if title is missing', async () => {
        mockParse.mockImplementationOnce((req, callback) => {
            callback(null, { user_id: ['user1'] }, { audio_file: [{ filepath: 'mock/path/audio.wav' }] });
        });
        const { req, res } = createMocks({ method: 'POST' });
        await handler(req as any, res as any);
        expect(res._getStatusCode()).toBe(400);
        expect(JSON.parse(res._getData()).error.message).toBe('Missing title for the audio note.');
    });


    it('should call Python backend via resilientGot and return success if Python backend succeeds', async () => {
        const mockPythonResponse = { ok: true, data: { notion_page_url: 'http://notion.so/page', title: 'Processed Title' } };
        mockedResilientGot.mockResolvedValueOnce(mockPythonResponse);

        const { req, res } = createMocks({ method: 'POST' });
        // Simulate formidable parsing correctly
        // Default mockParse setup already does this.

        await handler(req as any, res as any);

        expect(res._getStatusCode()).toBe(200);
        expect(JSON.parse(res._getData()).data).toEqual(mockPythonResponse.data);
        expect(mockedResilientGot).toHaveBeenCalledTimes(1);
        expect(mockedResilientGot).toHaveBeenCalledWith(
            'post',
            expect.stringContaining('/api/internal/process_audio_note_data'),
            expect.objectContaining({ body: expect.any(FormData) }), // Check that body is FormData
            expect.stringContaining('_PythonBackendCall')
        );
        expect(mockedLogger.info).toHaveBeenCalledWith(expect.stringContaining('Python backend processed audio successfully.'), expect.anything());
        expect(fs.unlink).toHaveBeenCalledWith('mock/path/audio.wav', expect.any(Function));
    });

    it('should return 500 and log error if Python backend returns an error status', async () => {
        const mockPythonErrorResponse = { ok: false, error: { message: 'Python processing error', code: 'PYTHON_ERROR' } };
        mockedResilientGot.mockResolvedValueOnce(mockPythonErrorResponse); // resilientGot succeeds, but Python service returns error

        const { req, res } = createMocks({ method: 'POST' });
        await handler(req as any, res as any);

        expect(res._getStatusCode()).toBe(500);
        expect(JSON.parse(res._getData()).error.message).toBe('Python processing error');
        expect(mockedLogger.error).toHaveBeenCalledWith(
            expect.stringContaining('Error response from Python backend.'),
            expect.objectContaining({ errorMsg: 'Python processing error' })
        );
        expect(fs.unlink).toHaveBeenCalledWith('mock/path/audio.wav', expect.any(Function));
    });

    it('should return 502 and log error if resilientGot throws (Python service communication failure)', async () => {
        const resilientGotError = new Error('Network connection to Python service failed');
        mockedResilientGot.mockRejectedValueOnce(resilientGotError);

        const { req, res } = createMocks({ method: 'POST' });
        await handler(req as any, res as any);

        expect(res._getStatusCode()).toBe(502);
        expect(JSON.parse(res._getData()).error.message).toBe('Network connection to Python service failed');
        expect(mockedLogger.error).toHaveBeenCalledWith(
            expect.stringContaining('Error calling Python backend or during file ops.'),
            expect.objectContaining({ error: resilientGotError.message })
        );
        expect(fs.unlink).toHaveBeenCalledWith('mock/path/audio.wav', expect.any(Function));
    });

    it('should log formidable parsing error and return 500', async () => {
        const parsingError = new Error('Formidable failed');
        mockParse.mockImplementationOnce((req, callback) => {
            callback(parsingError, {}, {});
        });
        const { req, res } = createMocks({ method: 'POST' });

        await handler(req as any, res as any);

        expect(res._getStatusCode()).toBe(500);
        expect(JSON.parse(res._getData()).error.message).toContain('Server error: Formidable failed');
        expect(mockedLogger.error).toHaveBeenCalledWith(
            expect.stringContaining('Formidable parsing error.'),
            expect.objectContaining({ error: parsingError.message })
        );
    });
});
