import { useSpeechRecognition } from "./useSpeechRecognition";

export const useVoiceIO = (options?: { wakeWord?: string; onTranscript?: (t: string) => void }) => {
    const speech = useSpeechRecognition();

    return {
        ...speech,
        isSupported: speech.browserSupportsSpeechRecognition,
        wakeWordActive: speech.wakeWordEnabled,
        toggleWakeWord: speech.setWakeWordMode
    };
};

export default useVoiceIO;
