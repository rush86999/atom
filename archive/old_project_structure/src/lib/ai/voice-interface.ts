import { LLMRouter } from './llm-router';
import { getDatabase } from '../database';

interface VoiceConfig {
    language: string;
    voice: string;
    speed: number;
}

interface TranscriptionResult {
    text: string;
    confidence: number;
    language: string;
}

interface SpeechResult {
    audioBase64: string;
    format: 'mp3' | 'wav';
}

/**
 * Voice Interface Service
 * Handles speech-to-text and text-to-speech for voice interactions
 */
export class VoiceInterface {
    private tenantId: string;
    private llmRouter: LLMRouter;
    private config: VoiceConfig;

    constructor(tenantId: string, config?: Partial<VoiceConfig>) {
        this.tenantId = tenantId;
        this.llmRouter = new LLMRouter(getDatabase());
        this.config = {
            language: config?.language || 'en-US',
            voice: config?.voice || 'alloy',
            speed: config?.speed || 1.0,
        };
    }

    /**
     * Transcribe audio to text using OpenAI Whisper
     */
    async transcribe(audioBase64: string): Promise<TranscriptionResult> {
        const apiKey = process.env.PLATFORM_OPENAI_API_KEY;
        if (!apiKey) {
            throw new Error('OpenAI API key not configured for voice');
        }

        // Decode base64 to buffer
        const audioBuffer = Buffer.from(audioBase64, 'base64');

        // Create form data
        const formData = new FormData();
        formData.append('file', new Blob([audioBuffer]), 'audio.webm');
        formData.append('model', 'whisper-1');
        formData.append('language', this.config.language.split('-')[0]);

        const response = await fetch('https://api.openai.com/v1/audio/transcriptions', {
            method: 'POST',
            headers: {
                Authorization: `Bearer ${apiKey}`,
            },
            body: formData,
        });

        if (!response.ok) {
            throw new Error(`Transcription failed: ${response.statusText}`);
        }

        const result = await response.json();

        return {
            text: result.text,
            confidence: 0.95, // Whisper doesn't return confidence
            language: this.config.language,
        };
    }

    /**
     * Convert text to speech using OpenAI TTS
     */
    async speak(text: string): Promise<SpeechResult> {
        const apiKey = process.env.PLATFORM_OPENAI_API_KEY;
        if (!apiKey) {
            throw new Error('OpenAI API key not configured for voice');
        }

        const response = await fetch('https://api.openai.com/v1/audio/speech', {
            method: 'POST',
            headers: {
                Authorization: `Bearer ${apiKey}`,
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                model: 'tts-1',
                voice: this.config.voice,
                input: text,
                speed: this.config.speed,
            }),
        });

        if (!response.ok) {
            throw new Error(`TTS failed: ${response.statusText}`);
        }

        const audioBuffer = await response.arrayBuffer();
        const audioBase64 = Buffer.from(audioBuffer).toString('base64');

        return {
            audioBase64,
            format: 'mp3',
        };
    }

    /**
     * Full voice conversation - transcribe, process, respond with speech
     */
    async converse(audioBase64: string): Promise<{
        userText: string;
        assistantText: string;
        audioResponse: SpeechResult;
    }> {
        // Step 1: Transcribe user audio
        const transcription = await this.transcribe(audioBase64);

        // Step 2: Process with LLM
        const response = await this.llmRouter.call(this.tenantId, {
            type: 'chat',
            messages: [{ role: 'user', content: transcription.text }],
            model: 'gpt-4o-mini',
        });

        const assistantText = response.content || 'I apologize, I could not generate a response.';

        // Step 3: Convert response to speech
        const audioResponse = await this.speak(assistantText);

        return {
            userText: transcription.text,
            assistantText,
            audioResponse,
        };
    }

    /**
     * Process voice command (for quick actions)
     */
    async processCommand(audioBase64: string): Promise<{
        command: string;
        action: string;
        parameters: Record<string, unknown>;
        executed: boolean;
    }> {
        const transcription = await this.transcribe(audioBase64);

        const prompt = `Parse this voice command and extract the action and parameters.
    
Command: "${transcription.text}"

Return JSON with:
- action: one of "send_message", "schedule_meeting", "search_contacts", "create_task", "get_analytics", "unknown"
- parameters: relevant parameters extracted from the command
- confidence: 0-1 confidence score

JSON:`;

        const response = await this.llmRouter.call(this.tenantId, {
            type: 'analysis',
            messages: [{ role: 'user', content: prompt }],
            model: 'gpt-4o-mini',
        });

        try {
            const jsonMatch = response.content?.match(/\{[\s\S]*\}/);
            if (jsonMatch) {
                const parsed = JSON.parse(jsonMatch[0]);
                return {
                    command: transcription.text,
                    action: parsed.action,
                    parameters: parsed.parameters || {},
                    executed: parsed.action !== 'unknown',
                };
            }
        } catch (error) {
            console.error('Failed to parse command:', error);
        }

        return {
            command: transcription.text,
            action: 'unknown',
            parameters: {},
            executed: false,
        };
    }

    /**
     * Get available voices
     */
    static getAvailableVoices(): { id: string; name: string; gender: string }[] {
        return [
            { id: 'alloy', name: 'Alloy', gender: 'neutral' },
            { id: 'echo', name: 'Echo', gender: 'male' },
            { id: 'fable', name: 'Fable', gender: 'neutral' },
            { id: 'onyx', name: 'Onyx', gender: 'male' },
            { id: 'nova', name: 'Nova', gender: 'female' },
            { id: 'shimmer', name: 'Shimmer', gender: 'female' },
        ];
    }
}

export default VoiceInterface;
