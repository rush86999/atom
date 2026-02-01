import { UnifiedMemorySystem } from './unified-memory';
import { getPythonClient } from '../api/python-client';

export class DocumentParser {
    /**
     * Parse document and extract text content
     */
    static async parseDocument(fileContent: Buffer, fileType: string, fileName: string): Promise<string> {
        try {
            const ext = fileType.toLowerCase().replace('.', '');

            // 1. Simple text formats - handle locally for speed
            if (['txt', 'md', 'csv'].includes(ext)) {
                return fileContent.toString('utf-8');
            }

            if (ext === 'json') {
                try {
                    const data = JSON.parse(fileContent.toString('utf-8'));
                    return JSON.stringify(data, null, 2);
                } catch {
                    return fileContent.toString('utf-8');
                }
            }

            // 2. Complex formats (PDF, DOCX, Images, PPTX) 
            // Delegate to the Python backend which uses Docling for high-fidelity extraction
            const doclingFormats = ['pdf', 'docx', 'doc', 'pptx', 'ppt', 'xlsx', 'xls', 'png', 'jpg', 'jpeg', 'tiff'];

            if (doclingFormats.includes(ext)) {
                console.log(`[DocumentParser] Using Docling bridge for ${fileName} (${ext})`);
                const python = getPythonClient();
                const response = await python.parseDocument(fileContent, fileName, ext);

                if (response.success && response.data?.success) {
                    return response.data.content;
                } else {
                    console.warn(`[DocumentParser] Docling bridge failed for ${fileName}:`, response.error || response.data?.error);
                }
            }

            // Fallback for unknown or failed formats
            return `[Parsing ${fileName} (${fileType})] - Rich parsing for this format is handled via specialized handlers.`;
        } catch (error) {
            console.error(`Failed to parse ${fileName}:`, error);
            return "";
        }
    }
}
