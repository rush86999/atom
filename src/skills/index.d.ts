/**
 * Skills Index - Finance Capabilities Registration
 * Registers finance skills as Atom agent capabilities ready for wake word activation
 */
import { FinanceSkillRegistration } from './financeSkillIndex';
import { TaxSkillRegistration } from './taxSkillIndex';
declare const financeSkillConfig: {
    wakeWordTriggers: string[];
    activationPatterns: string[];
    naturalLanguagePatterns: string[];
};
export declare function registerFinanceSkills(): Promise<{
    success: boolean;
    registeredSkills: any;
    wakeWordTriggers: string[];
    naturalLanguageSupport: boolean;
    error?: undefined;
} | {
    success: boolean;
    error: any;
    registeredSkills?: undefined;
    wakeWordTriggers?: undefined;
    naturalLanguageSupport?: undefined;
}>;
export declare class FinanceVoiceHandler {
    private isActive;
    handleWakeWordActivation(context: any): Promise<{
        message: string;
        examples: string[];
        isFinanceMode: boolean;
    }>;
    processFinanceVoiceCommand(voiceText: string, context: any): Promise<any>;
    getFinancePrompt(context: any): string;
}
export declare const financeVoiceHandler: FinanceVoiceHandler;
export declare function registerResearchSkills(): Promise<{
    success: boolean;
    registeredSkills: any;
    naturalLanguageSupport: boolean;
    error?: undefined;
} | {
    success: boolean;
    error: any;
    registeredSkills?: undefined;
    naturalLanguageSupport?: undefined;
}>;
export declare function registerLegalSkills(): Promise<{
    success: boolean;
    registeredSkills: any;
    naturalLanguageSupport: boolean;
    error?: undefined;
} | {
    success: boolean;
    error: any;
    registeredSkills?: undefined;
    naturalLanguageSupport?: undefined;
}>;
export declare function registerTaxSkills(): Promise<{
    success: boolean;
    registeredSkills: number;
    naturalLanguageSupport: boolean;
    error?: undefined;
} | {
    success: boolean;
    error: any;
    registeredSkills?: undefined;
    naturalLanguageSupport?: undefined;
}>;
export { FinanceSkillRegistration as FinanceCapabilities };
export { TaxSkillRegistration as TaxCapabilities };
export { financeSkillConfig as FinanceCommandConfig };
export * as boxSkills from './boxSkills';
export * as asanaSkills from './asanaSkills';
export * as trelloSkills from './trelloSkills';
export * as jiraSkills from './jiraSkills';
export * as shopifySkills from './shopifySkills';
declare const _default: {
    registerFinanceSkills: typeof registerFinanceSkills;
    financeVoiceHandler: FinanceVoiceHandler;
    financeSkillConfig: {
        wakeWordTriggers: string[];
        activationPatterns: string[];
        naturalLanguagePatterns: string[];
    };
    allFinanceSkills: any;
    financeAgentTools: any;
};
export default _default;
