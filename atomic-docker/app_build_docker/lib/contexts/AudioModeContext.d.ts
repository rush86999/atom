import { ReactNode } from "react";
interface AudioModeContextType {
    isAudioModeEnabled: boolean;
    toggleAudioMode: () => void;
    replyRequestCount: number;
    triggerReplyListen: () => void;
}
export declare const AudioModeProvider: ({ children }: {
    children: ReactNode;
}) => JSX.Element;
export declare const useAudioMode: () => AudioModeContextType;
export {};
