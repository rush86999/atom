import { SkillDefinition, ToolImplementation } from '../types';
export declare const taxSkills: SkillDefinition[];
export declare const taxAgentTools: ToolImplementation[];
export declare const TaxSkillRegistration: {
    name: string;
    version: string;
    description: string;
    capabilities: string[];
    activationPrefixes: string[];
    voiceTriggers: string[];
    desktopCommands: string[];
    webCommands: string;
    apiEndpoints: {
        web: string;
        desktop: string;
        mobile: string;
    };
};
export declare const allTaxSkills: SkillDefinition[];
