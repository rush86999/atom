import { SkillResponse } from '../../atomic-docker/project/functions/atom-agent/types';
export declare function startSilentAudioRecording(userId: string): Promise<SkillResponse<any>>;
export declare function stopSilentAudioRecording(userId: string): Promise<SkillResponse<any>>;
