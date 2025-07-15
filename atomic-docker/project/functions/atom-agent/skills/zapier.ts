import { ZapTriggerResponse, ZapData } from '../../types';
import { triggerZap as trigger } from './zapierSkills';
import { handleError } from '../../_utils/errorHandler';

export async function handleTriggerZap(entities: any): Promise<string> {
    try {
        const { zap_name, data } = entities;
        if (!zap_name || typeof zap_name !== 'string') {
            return "Zap name is required to trigger a Zap via NLU.";
        } else {
            const zapData: ZapData = (typeof data === 'object' && data !== null) ? data : {};
            const response: ZapTriggerResponse = await trigger(zap_name, zapData);
            if (response.success) {
                return `Zap triggered via NLU: ${response.message} (Run ID: ${response.runId})`;
            } else {
                return `Failed to trigger Zap via NLU: ${response.message}`;
            }
        }
    } catch (error: any) {
        return handleError(error, "Sorry, I couldn't trigger the Zap due to an error (NLU path).");
    }
}
