"use strict";
/**
 * Skills Index - Finance Capabilities Registration
 * Registers finance skills as Atom agent capabilities ready for wake word activation
 */
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
exports.shopifySkills = exports.jiraSkills = exports.trelloSkills = exports.asanaSkills = exports.boxSkills = exports.FinanceCommandConfig = exports.TaxCapabilities = exports.FinanceCapabilities = exports.financeVoiceHandler = exports.FinanceVoiceHandler = void 0;
exports.registerFinanceSkills = registerFinanceSkills;
exports.registerResearchSkills = registerResearchSkills;
exports.registerLegalSkills = registerLegalSkills;
exports.registerTaxSkills = registerTaxSkills;
const agentSkillRegistry_1 = require("../services/agentSkillRegistry");
const financeSkillIndex_1 = require("./financeSkillIndex");
Object.defineProperty(exports, "FinanceCapabilities", { enumerable: true, get: function () { return financeSkillIndex_1.FinanceSkillRegistration; } });
const financeVoiceAgent_1 = require("./financeVoiceAgent");
const researchSkillIndex_1 = require("./researchSkillIndex");
const legalSkillIndex_1 = require("./legalSkillIndex");
const taxSkillIndex_1 = require("./taxSkillIndex");
Object.defineProperty(exports, "TaxCapabilities", { enumerable: true, get: function () { return taxSkillIndex_1.TaxSkillRegistration; } });
// Finance skill activation triggers
const financeSkillConfig = {
    wakeWordTriggers: [
        'finance',
        'money',
        'budget',
        'spending',
        'net worth',
        'investment',
        'goals',
        'savings',
        'account',
    ],
    activationPatterns: [
        '^what.*net.*worth',
        '^show.*budget',
        '^how.*much.*spend',
        '^create.*budget',
        '^set.*goal',
        '^where.*money.*go',
        '^investment.*portfolio',
        '^finance.*help',
    ],
    naturalLanguagePatterns: [
        'what is my net worth',
        'show my budget for this month',
        'how much did I spend on dining',
        'create a grocery budget',
        'am I on track for retirement',
        'investment performance this quarter',
        'show my financial goals',
        'budget breakdown',
        'overspending detection',
    ],
};
exports.FinanceCommandConfig = financeSkillConfig;
// Register all finance skills with Atom agent
async function registerFinanceSkills() {
    console.log('🔥 Registering Atom Finance Skills for Wake Word Activation');
    try {
        // Register each finance skill
        for (const skill of financeSkillIndex_1.allFinanceSkills) {
            await (0, agentSkillRegistry_1.registerSkill)(skill);
        }
        // Register finance-specific tools for LLM function calling
        for (const tool of financeSkillIndex_1.financeAgentTools) {
            await (0, agentSkillRegistry_1.registerSkill)({
                name: tool.name,
                description: tool.description || 'Finance tool',
                parameters: {}, // Tool-specific parameters assigned during registry
                handler: tool.handler,
            });
        }
        console.log('✅ Finance skills registered successfully');
        return {
            success: true,
            registeredSkills: financeSkillIndex_1.allFinanceSkills.length + financeSkillIndex_1.financeAgentTools.length,
            wakeWordTriggers: financeSkillConfig.wakeWordTriggers,
            naturalLanguageSupport: true,
        };
    }
    catch (error) {
        console.error('❌ Failed to register finance skills:', error);
        return {
            success: false,
            error: error.message,
        };
    }
}
// Voice Command Handler Integration
class FinanceVoiceHandler {
    isActive = false;
    async handleWakeWordActivation(context) {
        this.isActive = true;
        return {
            message: '💰 Finance agent activated. Ask me anything about your money!',
            examples: financeSkillConfig.naturalLanguagePatterns.slice(0, 6),
            isFinanceMode: true,
        };
    }
    async processFinanceVoiceCommand(voiceText, context) {
        const userId = context?.userId || 'current_user';
        try {
            // Clean wake word from start of phrase if present
            const cleanedText = voiceText.replace(/^(atom|hey atom)\s*/gi, '').trim();
            return await financeVoiceAgent_1.processVoiceFinance.processVoiceFinanceCommand(userId, cleanedText, {
                ...context,
                interface: 'voice',
                transactionSource: 'wake_word',
            });
        }
        catch (error) {
            return {
                ok: false,
                response: "I couldn't process your finance request. Try rephrasing or type it out.",
                suggestions: [
                    "What's my net worth",
                    'Show budget',
                    'Spending this month',
                ],
            };
        }
    }
    getFinancePrompt(context) {
        return `💰 You are now in finance mode. Use any of these commands:\n${financeSkillConfig.naturalLanguagePatterns.join('\n• ')}`;
    }
}
exports.FinanceVoiceHandler = FinanceVoiceHandler;
// Export singleton
exports.financeVoiceHandler = new FinanceVoiceHandler();
// Register all research skills with Atom agent
async function registerResearchSkills() {
    console.log('🔬 Registering Atom Research Skills for Wake Word Activation');
    try {
        // Register each research skill
        for (const skill of researchSkillIndex_1.researchSkills) {
            await (0, agentSkillRegistry_1.registerSkill)(skill);
        }
        console.log('✅ Research skills registered successfully');
        return {
            success: true,
            registeredSkills: researchSkillIndex_1.researchSkills.length,
            naturalLanguageSupport: true,
        };
    }
    catch (error) {
        console.error('❌ Failed to register research skills:', error);
        return {
            success: false,
            error: error.message,
        };
    }
}
// Register all legal skills with Atom agent
async function registerLegalSkills() {
    console.log('⚖️ Registering Atom Legal Skills for Wake Word Activation');
    try {
        // Register each legal skill
        for (const skill of legalSkillIndex_1.legalSkills) {
            await (0, agentSkillRegistry_1.registerSkill)(skill);
        }
        console.log('✅ Legal skills registered successfully');
        return {
            success: true,
            registeredSkills: legalSkillIndex_1.legalSkills.length,
            naturalLanguageSupport: true,
        };
    }
    catch (error) {
        console.error('❌ Failed to register legal skills:', error);
        return {
            success: false,
            error: error.message,
        };
    }
}
// Register all tax skills with Atom agent
async function registerTaxSkills() {
    console.log('💸 Registering Atom Tax Skills for Wake Word Activation');
    try {
        // Register each tax skill
        for (const skill of taxSkillIndex_1.allTaxSkills) {
            await (0, agentSkillRegistry_1.registerSkill)(skill);
        }
        // Register tax-specific tools for LLM function calling
        for (const tool of taxSkillIndex_1.taxAgentTools) {
            await (0, agentSkillRegistry_1.registerSkill)({
                name: tool.name,
                description: tool.description || 'Tax tool',
                parameters: {}, // Tool-specific parameters assigned during registry
                handler: tool.handler,
            });
        }
        console.log('✅ Tax skills registered successfully');
        return {
            success: true,
            registeredSkills: taxSkillIndex_1.allTaxSkills.length + taxSkillIndex_1.taxAgentTools.length,
            naturalLanguageSupport: true,
        };
    }
    catch (error) {
        console.error('❌ Failed to register tax skills:', error);
        return {
            success: false,
            error: error.message,
        };
    }
}
// Auto-registration on import
registerFinanceSkills().catch(console.error);
registerResearchSkills().catch(console.error);
registerLegalSkills().catch(console.error);
registerTaxSkills().catch(console.error);
exports.boxSkills = __importStar(require("./boxSkills"));
exports.asanaSkills = __importStar(require("./asanaSkills"));
exports.trelloSkills = __importStar(require("./trelloSkills"));
exports.jiraSkills = __importStar(require("./jiraSkills"));
exports.shopifySkills = __importStar(require("./shopifySkills"));
// Default export for import
exports.default = {
    registerFinanceSkills,
    financeVoiceHandler: exports.financeVoiceHandler,
    financeSkillConfig,
    allFinanceSkills: financeSkillIndex_1.allFinanceSkills,
    financeAgentTools: financeSkillIndex_1.financeAgentTools,
};
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiaW5kZXguanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJpbmRleC50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiO0FBQUE7OztHQUdHOzs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7QUF3REgsc0RBa0NDO0FBdURELHdEQXVCQztBQUdELGtEQXVCQztBQUdELDhDQWlDQztBQXBPRCx1RUFBZ0Y7QUFDaEYsMkRBSTZCO0FBd09RLG9HQXpPbkMsNENBQXdCLE9BeU84QjtBQXZPeEQsMkRBQTBEO0FBQzFELDZEQUFzRDtBQUN0RCx1REFBZ0Q7QUFDaEQsbURBSXlCO0FBaU9RLGdHQWxPL0Isb0NBQW9CLE9Ba08wQjtBQS9OaEQsb0NBQW9DO0FBQ3BDLE1BQU0sa0JBQWtCLEdBQUc7SUFDekIsZ0JBQWdCLEVBQUU7UUFDaEIsU0FBUztRQUNULE9BQU87UUFDUCxRQUFRO1FBQ1IsVUFBVTtRQUNWLFdBQVc7UUFDWCxZQUFZO1FBQ1osT0FBTztRQUNQLFNBQVM7UUFDVCxTQUFTO0tBQ1Y7SUFFRCxrQkFBa0IsRUFBRTtRQUNsQixtQkFBbUI7UUFDbkIsZUFBZTtRQUNmLG1CQUFtQjtRQUNuQixpQkFBaUI7UUFDakIsWUFBWTtRQUNaLG1CQUFtQjtRQUNuQix3QkFBd0I7UUFDeEIsZ0JBQWdCO0tBQ2pCO0lBRUQsdUJBQXVCLEVBQUU7UUFDdkIsc0JBQXNCO1FBQ3RCLCtCQUErQjtRQUMvQixnQ0FBZ0M7UUFDaEMseUJBQXlCO1FBQ3pCLDhCQUE4QjtRQUM5QixxQ0FBcUM7UUFDckMseUJBQXlCO1FBQ3pCLGtCQUFrQjtRQUNsQix3QkFBd0I7S0FDekI7Q0FDRixDQUFDO0FBNEw2QixrREFBb0I7QUExTG5ELDhDQUE4QztBQUN2QyxLQUFLLFVBQVUscUJBQXFCO0lBQ3pDLE9BQU8sQ0FBQyxHQUFHLENBQUMsNkRBQTZELENBQUMsQ0FBQztJQUUzRSxJQUFJLENBQUM7UUFDSCw4QkFBOEI7UUFDOUIsS0FBSyxNQUFNLEtBQUssSUFBSSxvQ0FB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LENBQUMsS0FBSyxDQUFDLENBQUM7QUFDOUMsbUJBQW1CLEVBQUUsQ0FBQyxLQUFLLENBQUMsT0FBTyxDQUFDLEtBQUssQ0FBQyxDQUFDO0FBQzNDLGlCQUFpQixFQUFFLENBQUMsS0FBSyxDQUFDLE9BQU8sQ0FBQyxLQUFLLENBQUMsQ0FBQztBQU16Qyx5REFBeUM7QUFDekMsNkRBQTZDO0FBQzdDLCtEQUErQztBQUMvQywyREFBMkM7QUFDM0MsaUVBQWlEO0FBRWpELDRCQUE0QjtBQUM1QixrQkFBZTtJQUNiLHFCQUFxQjtJQUNyQixtQkFBbUIsRUFBbkIsMkJBQW1CO0lBQ25CLGtCQUFrQjtJQUNsQixnQkFBZ0IsRUFBaEIsb0NBQWdCO0lBQ2hCLGlCQUFpQixFQUFqQixxQ0FBaUI7Q0FDbEIsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbIi8qKlxuICogU2tpbGxzIEluZGV4IC0gRmluYW5jZSBDYXBhYmlsaXRpZXMgUmVnaXN0cmF0aW9uXG4gKiBSZWdpc3RlcnMgZmluYW5jZSBza2lsbHMgYXMgQXRvbSBhZ2VudCBjYXBhYmlsaXRpZXMgcmVhZHkgZm9yIHdha2Ugd29yZCBhY3RpdmF0aW9uXG4gKi9cblxuaW1wb3J0IHsgcmVnaXN0ZXJTa2lsbCwgU2tpbGxEZWZpbml0aW9uIH0gZnJvbSAnLi4vc2VydmljZXMvYWdlbnRTa2lsbFJlZ2lzdHJ5JztcbmltcG9ydCB7XG4gIGFsbEZpbmFuY2VTa2lsbHMsXG4gIGZpbmFuY2VBZ2VudFRvb2xzLFxuICBGaW5hbmNlU2tpbGxSZWdpc3RyYXRpb24sXG59IGZyb20gJy4vZmluYW5jZVNraWxsSW5kZXgnO1xuaW1wb3J0IHsgcHJvY2Vzc1ZvaWNlRmluYW5jZSB9IGZyb20gJy4vZmluYW5jZVZvaWNlQWdlbnQnO1xuaW1wb3J0IHsgcmVzZWFyY2hTa2lsbHMgfSBmcm9tICcuL3Jlc2VhcmNoU2tpbGxJbmRleCc7XG5pbXBvcnQgeyBsZWdhbFNraWxscyB9IGZyb20gJy4vbGVnYWxTa2lsbEluZGV4JztcbmltcG9ydCB7XG4gIGFsbFRheFNraWxscyxcbiAgdGF4QWdlbnRUb29scyxcbiAgVGF4U2tpbGxSZWdpc3RyYXRpb24sXG59IGZyb20gJy4vdGF4U2tpbGxJbmRleCc7XG5cbi8vIEZpbmFuY2Ugc2tpbGwgYWN0aXZhdGlvbiB0cmlnZ2Vyc1xuY29uc3QgZmluYW5jZVNraWxsQ29uZmlnID0ge1xuICB3YWtlV29yZFRyaWdnZXJzOiBbXG4gICAgJ2ZpbmFuY2UnLFxuICAgICdtb25leScsXG4gICAgJ2J1ZGdldCcsXG4gICAgJ3NwZW5kaW5nJyxcbiAgICAnbmV0IHdvcnRoJyxcbiAgICAnaW52ZXN0bWVudCcsXG4gICAgJ2dvYWxzJyxcbiAgICAnc2F2aW5ncycsXG4gICAgJ2FjY291bnQnLFxuICBdLFxuXG4gIGFjdGl2YXRpb25QYXR0ZXJuczogW1xuICAgICded2hhdC4qbmV0Lip3b3J0aCcsXG4gICAgJ15zaG93LipidWRnZXQnLFxuICAgICdeaG93LiptdWNoLipzcGVuZCcsXG4gICAgJ15jcmVhdGUuKmJ1ZGdldCcsXG4gICAgJ15zZXQuKmdvYWwnLFxuICAgICded2hlcmUuKm1vbmV5LipnbycsXG4gICAgJ15pbnZlc3RtZW50Lipwb3J0Zm9saW8nLFxuICAgICdeZmluYW5jZS4qaGVscCcsXG4gIF0sXG5cbiAgbmF0dXJhbExhbmd1YWdlUGF0dGVybnM6IFtcbiAgICAnd2hhdCBpcyBteSBuZXQgd29ydGgnLFxuICAgICdzaG93IG15IGJ1ZGdldCBmb3IgdGhpcyBtb250aCcsXG4gICAgJ2hvdyBtdWNoIGRpZCBJIHNwZW5kIG9uIGRpbmluZycsXG4gICAgJ2NyZWF0ZSBhIGdyb2NlcnkgYnVkZ2V0JyxcbiAgICAnYW0gSSBvbiB0cmFjayBmb3IgcmV0aXJlbWVudCcsXG4gICAgJ2ludmVzdG1lbnQgcGVyZm9ybWFuY2UgdGhpcyBxdWFydGVyJyxcbiAgICAnc2hvdyBteSBmaW5hbmNpYWwgZ29hbHMnLFxuICAgICdidWRnZXQgYnJlYWtkb3duJyxcbiAgICAnb3ZlcnNwZW5kaW5nIGRldGVjdGlvbicsXG4gIF0sXG59O1xuXG4vLyBSZWdpc3RlciBhbGwgZmluYW5jZSBza2lsbHMgd2l0aCBBdG9tIGFnZW50XG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gcmVnaXN0ZXJGaW5hbmNlU2tpbGxzKCkge1xuICBjb25zb2xlLmxvZygn8J+UpSBSZWdpc3RlcmluZyBBdG9tIEZpbmFuY2UgU2tpbGxzIGZvciBXYWtlIFdvcmQgQWN0aXZhdGlvbicpO1xuXG4gIHRyeSB7XG4gICAgLy8gUmVnaXN0ZXIgZWFjaCBmaW5hbmNlIHNraWxsXG4gICAgZm9yIChjb25zdCBza2lsbCBvZiBhbGxGaW5hbmNlU2tpbGxzKSB7XG4gICAgICBhd2FpdCByZWdpc3RlclNraWxsKHNraWxsKTtcbiAgICB9XG5cbiAgICAvLyBSZWdpc3RlciBmaW5hbmNlLXNwZWNpZmljIHRvb2xzIGZvciBMTE0gZnVuY3Rpb24gY2FsbGluZ1xuICAgIGZvciAoY29uc3QgdG9vbCBvZiBmaW5hbmNlQWdlbnRUb29scykge1xuICAgICAgYXdhaXQgcmVnaXN0ZXJTa2lsbCh7XG4gICAgICAgIG5hbWU6IHRvb2wubmFtZSxcbiAgICAgICAgZGVzY3JpcHRpb246IHRvb2wuZGVzY3JpcHRpb24gfHwgJ0ZpbmFuY2UgdG9vbCcsXG4gICAgICAgIHBhcmFtZXRlcnM6IHt9LCAvLyBUb29sLXNwZWNpZmljIHBhcmFtZXRlcnMgYXNzaWduZWQgZHVyaW5nIHJlZ2lzdHJ5XG4gICAgICAgIGhhbmRsZXI6IHRvb2wuaGFuZGxlcixcbiAgICAgIH0gYXMgU2tpbGxEZWZpbml0aW9uKTtcbiAgICB9XG5cbiAgICBjb25zb2xlLmxvZygn4pyFIEZpbmFuY2Ugc2tpbGxzIHJlZ2lzdGVyZWQgc3VjY2Vzc2Z1bGx5Jyk7XG5cbiAgICByZXR1cm4ge1xuICAgICAgc3VjY2VzczogdHJ1ZSxcbiAgICAgIHJlZ2lzdGVyZWRTa2lsbHM6IGFsbEZpbmFuY2VTa2lsbHMubGVuZ3RoICsgZmluYW5jZUFnZW50VG9vbHMubGVuZ3RoLFxuICAgICAgd2FrZVdvcmRUcmlnZ2VyczogZmluYW5jZVNraWxsQ29uZmlnLndha2VXb3JkVHJpZ2dlcnMsXG4gICAgICBuYXR1cmFsTGFuZ3VhZ2VTdXBwb3J0OiB0cnVlLFxuICAgIH07XG4gIH0gY2F0Y2ggKGVycm9yKSB7XG4gICAgY29uc29sZS5lcnJvcign4p2MIEZhaWxlZCB0byByZWdpc3RlciBmaW5hbmNlIHNraWxsczonLCBlcnJvcik7XG4gICAgcmV0dXJuIHtcbiAgICAgIHN1Y2Nlc3M6IGZhbHNlLFxuICAgICAgZXJyb3I6IGVycm9yLm1lc3NhZ2UsXG4gICAgfTtcbiAgfVxufVxuXG4vLyBWb2ljZSBDb21tYW5kIEhhbmRsZXIgSW50ZWdyYXRpb25cbmV4cG9ydCBjbGFzcyBGaW5hbmNlVm9pY2VIYW5kbGVyIHtcbiAgcHJpdmF0ZSBpc0FjdGl2ZSA9IGZhbHNlO1xuXG4gIGFzeW5jIGhhbmRsZVdha2VXb3JkQWN0aXZhdGlvbihjb250ZXh0OiBhbnkpIHtcbiAgICB0aGlzLmlzQWN0aXZlID0gdHJ1ZTtcblxuICAgIHJldHVybiB7XG4gICAgICBtZXNzYWdlOiAn8J+SsCBGaW5hbmNlIGFnZW50IGFjdGl2YXRlZC4gQXNrIG1lIGFueXRoaW5nIGFib3V0IHlvdXIgbW9uZXkhJyxcbiAgICAgIGV4YW1wbGVzOiBmaW5hbmNlU2tpbGxDb25maWcubmF0dXJhbExhbmd1YWdlUGF0dGVybnMuc2xpY2UoMCwgNiksXG4gICAgICBpc0ZpbmFuY2VNb2RlOiB0cnVlLFxuICAgIH07XG4gIH1cblxuICBhc3luYyBwcm9jZXNzRmluYW5jZVZvaWNlQ29tbWFuZCh2b2ljZVRleHQ6IHN0cmluZywgY29udGV4dDogYW55KSB7XG4gICAgY29uc3QgdXNlcklkID0gY29udGV4dD8udXNlcklkIHx8ICdjdXJyZW50X3VzZXInO1xuXG4gICAgdHJ5IHtcbiAgICAgIC8vIENsZWFuIHdha2Ugd29yZCBmcm9tIHN0YXJ0IG9mIHBocmFzZSBpZiBwcmVzZW50XG4gICAgICBjb25zdCBjbGVhbmVkVGV4dCA9IHZvaWNlVGV4dC5yZXBsYWNlKC9eKGF0b218aGV5IGF0b20pXFxzKi9naSwgJycpLnRyaW0oKTtcblxuICAgICAgcmV0dXJuIGF3YWl0IHByb2Nlc3NWb2ljZUZpbmFuY2UucHJvY2Vzc1ZvaWNlRmluYW5jZUNvbW1hbmQoXG4gICAgICAgIHVzZXJJZCxcbiAgICAgICAgY2xlYW5lZFRleHQsXG4gICAgICAgIHtcbiAgICAgICAgICAuLi5jb250ZXh0LFxuICAgICAgICAgIGludGVyZmFjZTogJ3ZvaWNlJyxcbiAgICAgICAgICB0cmFuc2FjdGlvblNvdXJjZTogJ3dha2Vfd29yZCcsXG4gICAgICAgIH1cbiAgICAgICk7XG4gICAgfSBjYXRjaCAoZXJyb3IpIHtcbiAgICAgIHJldHVybiB7XG4gICAgICAgIG9rOiBmYWxzZSxcbiAgICAgICAgcmVzcG9uc2U6XG4gICAgICAgICAgXCJJIGNvdWxkbid0IHByb2Nlc3MgeW91ciBmaW5hbmNlIHJlcXVlc3QuIFRyeSByZXBocmFzaW5nIG9yIHR5cGUgaXQgb3V0LlwiLFxuICAgICAgICBzdWdnZXN0aW9uczogW1xuICAgICAgICAgIFwiV2hhdCdzIG15IG5ldCB3b3J0aFwiLFxuICAgICAgICAgICdTaG93IGJ1ZGdldCcsXG4gICAgICAgICAgJ1NwZW5kaW5nIHRoaXMgbW9udGgnLFxuICAgICAgICBdLFxuICAgICAgfTtcbiAgICB9XG4gIH1cblxuICBnZXRGaW5hbmNlUHJvbXB0KGNvbnRleHQ6IGFueSk6IHN0cmluZyB7XG4gICAgcmV0dXJuIGDwn5KwIFlvdSBhcmUgbm93IGluIGZpbmFuY2UgbW9kZS4gVXNlIGFueSBvZiB0aGVzZSBjb21tYW5kczpcXG4ke2ZpbmFuY2VTa2lsbENvbmZpZy5uYXR1cmFsTGFuZ3VhZ2VQYXR0ZXJucy5qb2luKCdcXG7igKIgJyl9YDtcbiAgfVxufVxuXG4vLyBFeHBvcnQgc2luZ2xldG9uXG5leHBvcnQgY29uc3QgZmluYW5jZVZvaWNlSGFuZGxlciA9IG5ldyBGaW5hbmNlVm9pY2VIYW5kbGVyKCk7XG5cbi8vIFJlZ2lzdGVyIGFsbCByZXNlYXJjaCBza2lsbHMgd2l0aCBBdG9tIGFnZW50XG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gcmVnaXN0ZXJSZXNlYXJjaFNraWxscygpIHtcbiAgY29uc29sZS5sb2coJ/CflKwgUmVnaXN0ZXJpbmcgQXRvbSBSZXNlYXJjaCBTa2lsbHMgZm9yIFdha2UgV29yZCBBY3RpdmF0aW9uJyk7XG5cbiAgdHJ5IHtcbiAgICAvLyBSZWdpc3RlciBlYWNoIHJlc2VhcmNoIHNraWxsXG4gICAgZm9yIChjb25zdCBza2lsbCBvZiByZXNlYXJjaFNraWxscykge1xuICAgICAgYXdhaXQgcmVnaXN0ZXJTa2lsbChza2lsbCk7XG4gICAgfVxuXG4gICAgY29uc29sZS5sb2coJ+KchSBSZXNlYXJjaCBza2lsbHMgcmVnaXN0ZXJlZCBzdWNjZXNzZnVsbHknKTtcblxuICAgIHJldHVybiB7XG4gICAgICBzdWNjZXNzOiB0cnVlLFxuICAgICAgcmVnaXN0ZXJlZFNraWxsczogcmVzZWFyY2hTa2lsbHMubGVuZ3RoLFxuICAgICAgbmF0dXJhbExhbmd1YWdlU3VwcG9ydDogdHJ1ZSxcbiAgICB9O1xuICB9IGNhdGNoIChlcnJvcikge1xuICAgIGNvbnNvbGUuZXJyb3IoJ+KdjCBGYWlsZWQgdG8gcmVnaXN0ZXIgcmVzZWFyY2ggc2tpbGxzOicsIGVycm9yKTtcbiAgICByZXR1cm4ge1xuICAgICAgc3VjY2VzczogZmFsc2UsXG4gICAgICBlcnJvcjogZXJyb3IubWVzc2FnZSxcbiAgICB9O1xuICB9XG59XG5cbi8vIFJlZ2lzdGVyIGFsbCBsZWdhbCBza2lsbHMgd2l0aCBBdG9tIGFnZW50XG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gcmVnaXN0ZXJMZWdhbFNraWxscygpIHtcbiAgY29uc29sZS5sb2coJ+Kalu+4jyBSZWdpc3RlcmluZyBBdG9tIExlZ2FsIFNraWxscyBmb3IgV2FrZSBXb3JkIEFjdGl2YXRpb24nKTtcblxuICB0cnkge1xuICAgIC8vIFJlZ2lzdGVyIGVhY2ggbGVnYWwgc2tpbGxcbiAgICBmb3IgKGNvbnN0IHNraWxsIG9mIGxlZ2FsU2tpbGxzKSB7XG4gICAgICBhd2FpdCByZWdpc3RlclNraWxsKHNraWxsKTtcbiAgICB9XG5cbiAgICBjb25zb2xlLmxvZygn4pyFIExlZ2FsIHNraWxscyByZWdpc3RlcmVkIHN1Y2Nlc3NmdWxseScpO1xuXG4gICAgcmV0dXJuIHtcbiAgICAgIHN1Y2Nlc3M6IHRydWUsXG4gICAgICByZWdpc3RlcmVkU2tpbGxzOiBsZWdhbFNraWxscy5sZW5ndGgsXG4gICAgICBuYXR1cmFsTGFuZ3VhZ2VTdXBwb3J0OiB0cnVlLFxuICAgIH07XG4gIH0gY2F0Y2ggKGVycm9yKSB7XG4gICAgY29uc29sZS5lcnJvcign4p2MIEZhaWxlZCB0byByZWdpc3RlciBsZWdhbCBza2lsbHM6JywgZXJyb3IpO1xuICAgIHJldHVybiB7XG4gICAgICBzdWNjZXNzOiBmYWxzZSxcbiAgICAgIGVycm9yOiBlcnJvci5tZXNzYWdlLFxuICAgIH07XG4gIH1cbn1cblxuLy8gUmVnaXN0ZXIgYWxsIHRheCBza2lsbHMgd2l0aCBBdG9tIGFnZW50XG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gcmVnaXN0ZXJUYXhTa2lsbHMoKSB7XG4gIGNvbnNvbGUubG9nKCfwn5K4IFJlZ2lzdGVyaW5nIEF0b20gVGF4IFNraWxscyBmb3IgV2FrZSBXb3JkIEFjdGl2YXRpb24nKTtcblxuICB0cnkge1xuICAgIC8vIFJlZ2lzdGVyIGVhY2ggdGF4IHNraWxsXG4gICAgZm9yIChjb25zdCBza2lsbCBvZiBhbGxUYXhTa2lsbHMpIHtcbiAgICAgIGF3YWl0IHJlZ2lzdGVyU2tpbGwoc2tpbGwpO1xuICAgIH1cblxuICAgIC8vIFJlZ2lzdGVyIHRheC1zcGVjaWZpYyB0b29scyBmb3IgTExNIGZ1bmN0aW9uIGNhbGxpbmdcbiAgICBmb3IgKGNvbnN0IHRvb2wgb2YgdGF4QWdlbnRUb29scykge1xuICAgICAgYXdhaXQgcmVnaXN0ZXJTa2lsbCh7XG4gICAgICAgIG5hbWU6IHRvb2wubmFtZSxcbiAgICAgICAgZGVzY3JpcHRpb246IHRvb2wuZGVzY3JpcHRpb24gfHwgJ1RheCB0b29sJyxcbiAgICAgICAgcGFyYW1ldGVyczoge30sIC8vIFRvb2wtc3BlY2lmaWMgcGFyYW1ldGVycyBhc3NpZ25lZCBkdXJpbmcgcmVnaXN0cnlcbiAgICAgICAgaGFuZGxlcjogdG9vbC5oYW5kbGVyLFxuICAgICAgfSBhcyBTa2lsbERlZmluaXRpb24pO1xuICAgIH1cblxuICAgIGNvbnNvbGUubG9nKCfinIUgVGF4IHNraWxscyByZWdpc3RlcmVkIHN1Y2Nlc3NmdWxseScpO1xuXG4gICAgcmV0dXJuIHtcbiAgICAgIHN1Y2Nlc3M6IHRydWUsXG4gICAgICByZWdpc3RlcmVkU2tpbGxzOiBhbGxUYXhTa2lsbHMubGVuZ3RoICsgdGF4QWdlbnRUb29scy5sZW5ndGgsXG4gICAgICBuYXR1cmFsTGFuZ3VhZ2VTdXBwb3J0OiB0cnVlLFxuICAgIH07XG4gIH0gY2F0Y2ggKGVycm9yKSB7XG4gICAgY29uc29sZS5lcnJvcign4p2MIEZhaWxlZCB0byByZWdpc3RlciB0YXggc2tpbGxzOicsIGVycm9yKTtcbiAgICByZXR1cm4ge1xuICAgICAgc3VjY2VzczogZmFsc2UsXG4gICAgICBlcnJvcjogZXJyb3IubWVzc2FnZSxcbiAgICB9O1xuICB9XG59XG5cbi8vIEF1dG8tcmVnaXN0cmF0aW9uIG9uIGltcG9ydFxucmVnaXN0ZXJGaW5hbmNlU2tpbGxzKCkuY2F0Y2goY29uc29sZS5lcnJvcik7XG5yZWdpc3RlclJlc2VhcmNoU2tpbGxzKCkuY2F0Y2goY29uc29sZS5lcnJvcik7XG5yZWdpc3RlckxlZ2FsU2tpbGxzKCkuY2F0Y2goY29uc29sZS5lcnJvcik7XG5yZWdpc3RlclRheFNraWxscygpLmNhdGNoKGNvbnNvbGUuZXJyb3IpO1xuXG4vLyBJbnRlZ3JhdGlvbiBleHBvcnRzXG5leHBvcnQgeyBGaW5hbmNlU2tpbGxSZWdpc3RyYXRpb24gYXMgRmluYW5jZUNhcGFiaWxpdGllcyB9O1xuZXhwb3J0IHsgVGF4U2tpbGxSZWdpc3RyYXRpb24gYXMgVGF4Q2FwYWJpbGl0aWVzIH07XG5leHBvcnQgeyBmaW5hbmNlU2tpbGxDb25maWcgYXMgRmluYW5jZUNvbW1hbmRDb25maWcgfTtcbmV4cG9ydCAqIGFzIGJveFNraWxscyBmcm9tICcuL2JveFNraWxscyc7XG5leHBvcnQgKiBhcyBhc2FuYVNraWxscyBmcm9tICcuL2FzYW5hU2tpbGxzJztcbmV4cG9ydCAqIGFzIHRyZWxsb1NraWxscyBmcm9tICcuL3RyZWxsb1NraWxscyc7XG5leHBvcnQgKiBhcyBqaXJhU2tpbGxzIGZyb20gJy4vamlyYVNraWxscyc7XG5leHBvcnQgKiBhcyBzaG9waWZ5U2tpbGxzIGZyb20gJy4vc2hvcGlmeVNraWxscyc7XG5cbi8vIERlZmF1bHQgZXhwb3J0IGZvciBpbXBvcnRcbmV4cG9ydCBkZWZhdWx0IHtcbiAgcmVnaXN0ZXJGaW5hbmNlU2tpbGxzLFxuICBmaW5hbmNlVm9pY2VIYW5kbGVyLFxuICBmaW5hbmNlU2tpbGxDb25maWcsXG4gIGFsbEZpbmFuY2VTa2lsbHMsXG4gIGZpbmFuY2VBZ2VudFRvb2xzLFxufTtcbiJdfQ==