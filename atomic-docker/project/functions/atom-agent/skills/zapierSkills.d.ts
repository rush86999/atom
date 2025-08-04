import { ZapTriggerResponse } from '../types';
export interface ZapData {
    [key: string]: any;
}
export declare function triggerZap(userId: string, zapName: string, data: ZapData): Promise<ZapTriggerResponse>;
