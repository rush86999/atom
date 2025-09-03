import React, { ReactNode } from 'react';
interface WakeWordContextType {
    isWakeWordEnabled: boolean;
    isListening: boolean;
    wakeWordError: string | null;
    toggleWakeWord: (forceEnable?: boolean) => void;
    startListening: () => void;
    stopListening: () => void;
}
export declare const WakeWordProvider: React.FC<{
    children: ReactNode;
}>;
export declare const useWakeWord: () => WakeWordContextType;
export {};
