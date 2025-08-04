import { AutopilotType, AutopilotApiResponse } from '../../autopilot/_libs/types';
export declare function enableAutopilot(userId: string, query: string): Promise<AutopilotApiResponse<AutopilotType | null>>;
export declare function disableAutopilot(userId: string, query: string): Promise<AutopilotApiResponse<{
    success: boolean;
}>>;
export declare function getAutopilotStatus(userId: string, query: string): Promise<AutopilotApiResponse<AutopilotType | AutopilotType[] | null>>;
