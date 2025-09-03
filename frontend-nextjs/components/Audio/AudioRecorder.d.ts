import React from 'react';
interface AudioRecorderProps {
    userId: string;
    initialLinkedEventId?: string;
    initialSuggestedTitle?: string;
    onRecordingComplete: (notionPageUrl: string, title: string, summaryPreview?: string) => void;
    onRecordingError: (errorMessage: string) => void;
}
declare const AudioRecorder: React.FC<AudioRecorderProps>;
export default AudioRecorder;
