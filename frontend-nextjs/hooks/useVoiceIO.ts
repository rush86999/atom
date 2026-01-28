import { useSpeechRecognition, UseSpeechRecognitionReturn } from './useSpeechRecognition';

export interface UseVoiceIOReturn extends UseSpeechRecognitionReturn {
    // Add any specific overrides if needed, but for now it's a direct proxy
}

export function useVoiceIO(): UseVoiceIOReturn {
    return useSpeechRecognition();
}

export default useVoiceIO;
