/**
 * Atom Agent Finance Skills Index
 * Complete registration of all finance capabilities for Atom agent system
 */
import { SkillDefinition } from '../types';
export declare const financeSkills: SkillDefinition[];
export declare const voiceEnabledFinanceSkills: SkillDefinition[];
export declare const quickFinanceActions: {
    n: any;
    net_worth: any;
    "What's my net worth including all accounts and investments?\",\n  budget_status: \"Show my budget overview and spending status for this month\",\n  spending_analysis: \"Analyze my spending by category for this month\",\n  goals_overview: \"Display all my financial goals with current progress\",\n  investment_performance: \"Show my complete investment portfolio performance\",\n  finance_recommendations: \"Provide personalized financial recommendations\",\n  voice_finance_help: \"List voice commands for finance management\"\n};": any;
    const: {
        n: any;
        name: any;
        "Atom Finance Suite\",\n  version: \"2.0.0\",\n  description: \"Comprehensive financial management through natural language, voice commands, and intelligent insights\",\n  capabilities: [\n    \"Natural language finance queries\",\n    \"Voice-controlled finance management\", \n    \"Budget creation and tracking\",\n    \"Net worth calculation\",\n    \"Investment portfolio analysis\",\n    \"Financial goal management\",\n    \"Transaction search and insights\",\n    \"Multi-turn finance conversations\"\n  ],\n  activationPrefixes: [\n    \"finance\",\n    \"budget\", \n    \"spending\",\n    \"money\",\n    \"net worth\",\n    \"investment\",\n    \"savings\",\n    \"goals\",\n    \"transactions\"\n  ],\n  voiceTriggers: Object.keys(quickFinanceActions),\n  desktopCommands: Object.keys(quickFinanceActions).map(key => key.replace('_', ' ')),\n  webCommands: '/finance',\n  apiEndpoints: {\n    web: '/api/financial',\n    desktop: 'finance://',\n    mobile: 'atom://finance'\n  }\n};": any;
        const: any[];
    };
};
