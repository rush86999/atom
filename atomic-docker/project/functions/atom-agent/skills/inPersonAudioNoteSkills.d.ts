import { ProcessedNLUResponse, AgentSkillContext } from '../types';
interface AgentSkillResponse {
    success: boolean;
    message: string;
    sessionTrackingId?: string;
}
/**
 * Handles the START_IN_PERSON_AUDIO_NOTE intent with direct client control.
 */
export declare function handleStartInPersonAudioNoteDirect(nluResult: ProcessedNLUResponse, // Use imported ProcessedNLUResponse
context: AgentSkillContext): Promise<AgentSkillResponse>;
/**
 * Handles the STOP_IN_PERSON_AUDIO_NOTE intent with direct client control.
 */
export declare function handleStopInPersonAudioNoteDirect(nluResult: ProcessedNLUResponse, // Use imported ProcessedNLUResponse
context: AgentSkillContext): Promise<AgentSkillResponse>;
/**
 * Handles the CANCEL_IN_PERSON_AUDIO_NOTE intent with direct client control.
 */
export declare function handleCancelInPersonAudioNoteDirect(nluResult: ProcessedNLUResponse, // Use imported ProcessedNLUResponse
context: AgentSkillContext): Promise<AgentSkillResponse>;
/**
 * Example of how these handlers might be registered or mapped in the agent's skill routing logic.
 * The actual mechanism will depend on the Atom agent's architecture.
 * This manifest should be imported and used by the agent's main router.
 */
export declare const InPersonAudioNoteDirectSkillManifest: {
    intentHandlers: {
        START_IN_PERSON_AUDIO_NOTE: typeof handleStartInPersonAudioNoteDirect;
        STOP_IN_PERSON_AUDIO_NOTE: typeof handleStopInPersonAudioNoteDirect;
        CANCEL_IN_PERSON_AUDIO_NOTE: typeof handleCancelInPersonAudioNoteDirect;
    };
    skillName: string;
    description: string;
};
export {};
