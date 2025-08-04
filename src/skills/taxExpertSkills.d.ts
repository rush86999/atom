import { SkillResponse } from '../types';
import { EnrichedIntent } from '../nlu_agents/nlu_types';
export interface TaxQuery {
    intent: 'calculate_tax' | 'find_deductions' | 'get_tax_advice' | 'lookup_tax_law';
    parameters: {
        income?: number;
        filingStatus?: 'single' | 'married_jointly' | 'married_separately' | 'head_of_household';
        dependents?: number;
        query?: string;
    };
}
export declare function handleTaxQuery(userId: string, intent: EnrichedIntent, context?: any): Promise<SkillResponse<string>>;
