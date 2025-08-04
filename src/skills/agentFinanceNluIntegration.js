"use strict";
/**
 * Atom Agent Finance NLU Integration
 * Enables "Atom" wake word + natural language finance queries through existing NLU system
 * Integrates fully with wake word activation flow ➜ NLU processor ➜ finance agent
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.FinanceWakeFlow = exports.processFinanceThroughNlu = exports.activateFinanceThroughWakeWord = exports.financeNluHandler = void 0;
const agentNluSystem_1 = require("../services/agentNluSystem");
const financeAgentSkills_1 = require("./financeAgentSkills");
const financeVoiceAgent_1 = require("./financeVoiceAgent");
/**
 * Finance NLU Handler that plugs into Atom's existing wake-word activated system
 * Wake word "Atom" triggers agent ➜ this NLU handler processes finance commands naturally
 */
exports.financeNluHandler = {
    name: 'finance-handler',
    // Finance-specific intent recognition leveraging existing NLU
    intents: [
        {
            name: 'net_worth_query',
            patterns: [
                /what.*net.*worth/i,
                /how.*much.*(am|do).*worth/i,
                /financial.*position/i,
                /wealth.*summary/i,
            ],
        },
        {
            name: 'budget_query',
            patterns: [
                /budget.*status/i,
                /spending.*limit/i,
                /how.*much.*left.*for.*budget/i,
            ],
        },
        {
            name: 'spending_analysis',
            patterns: [
                /how.*much.*spent/i,
                /where.*money.*go/i,
                /spending.*breakdown/i,
                /expenses.*this.*month/i,
            ],
        },
        {
            name: 'create_budget',
            patterns: [/set.*budget/i, /create.*budget/i, /budget.*for.*\$(\d+)/i],
        },
        {
            name: 'financial_goals',
            patterns: [
                /show.*goals/i,
                /savings.*progress/i,
                /financial.*goals/i,
                /retirement.*tracking/i,
            ],
        },
        {
            name: 'investment_overview',
            patterns: [
                /investment.*portfolio/i,
                /portfolio.*performance/i,
                /stock.*investments/i,
            ],
        },
        {
            name: 'transaction_search',
            patterns: [
                /find.*transactions/i,
                /search.*purchases/i,
                /show.*spending/i,
            ],
        },
    ],
    /**
     * Processes any text entering Atom's NLU system after "Atom" wake word
     * Example flow: "Atom → show my net worth" ➜ NLU captures ➜ finance processing
     */
    async handleText(context, text) {
        const userId = context.user?.id || 'user';
        // Clean "Atom" wake word prefix if present
        const cleanText = text.replace(/^atom\s*/i, '').trim();
        if (!cleanText)
            return null;
        // Route through existing finance system
        return await (0, financeAgentSkills_1.handleFinanceQuery)(userId, cleanText, {
            ...context,
            source: 'voice_wake',
            interface: 'voice_nlu',
        });
    },
    /**
     * Voice-aware natural language processing leveraging existing Atom NLU
     */
    voiceProcessing: {
        handleWakeActivation: async (context) => {
            return {
                greeting: '💰 Finance mode activated! Say things like:',
                examples: [
                    'What is my net worth?',
                    'Show my budget',
                    'How much did I spend on restaurants?',
                    'Create a savings goal',
                    'Investment portfolio',
                ],
            };
        },
        processVoiceInput: async (voiceText, context) => {
            const userId = context.user?.id || 'user';
            // Direct voice processing through NLU layer
            return await financeVoiceAgent_1.processVoiceFinance.processVoiceFinanceCommand(userId, voiceText, {
                ...context,
                interface: 'voice_wake_nlu',
                timestamp: Date.now(),
            });
        },
    },
};
// Integration hook for existing Atom NLU system
const activateFinanceThroughWakeWord = async () => {
    await agentNluSystem_1.skillExecutor.registerNluHandler('finance', exports.financeNluHandler);
    console.log('🔊 Atom finance NLU integrated with wake word system');
    console.log('✅ Say "Atom" then any finance command naturally');
    return {
        awake: false,
        listenFor: [
            'what is my net worth',
            'show my budget',
            'how much did I spend on',
            'create a budget for',
            'show my financial goals',
            'investment portfolio',
            'compare this month to last',
        ],
        responseMode: 'conversational',
    };
};
exports.activateFinanceThroughWakeWord = activateFinanceThroughWakeWord;
// Direct finance command processing regardless of entry point
const processFinanceThroughNlu = async (context, text) => {
    return await exports.financeNluHandler.handleText(context, text);
};
exports.processFinanceThroughNlu = processFinanceThroughNlu;
// Auto-registration on module import
if (typeof window === 'undefined') {
    // Server-side: register immediately
    (0, exports.activateFinanceThroughWakeWord)().catch(console.error);
}
else {
    // Client-side: register when DOM ready
    try {
        (0, exports.activateFinanceThroughWakeWord)();
    }
    catch (error) {
        console.log('Finance NLU system ready for Atom wake word');
    }
}
// Activation flow documentation
exports.FinanceWakeFlow = {
    title: 'Atom Finance Activation Flow',
    description: 'How wake word + finance works through NLU',
    flow: [
        "User: 'Atom show my net worth'",
        'Wake Word Detector: Activates Atom agent',
        'NLU System: Detects finance intent → routes to finance handler',
        'Finance Agent: Processes query → returns formatted response',
        'Atom: Speaks back via voice/TTS',
    ],
    voiceCommands: [
        'Atom what is my net worth',
        'Atom show my budget for this month',
        'Atom how much did I spend on dining',
        'Atom create a travel goal of $2000',
        'Atom investment portfolio performance',
        'Atom help with budgets',
        'Atom compare this month to last',
    ],
    integration: 'Uses existing wake word system, no new wake words needed',
};
// Export for wake word system integration
exports.default = {
    handler: exports.financeNluHandler,
    activate: exports.activateFinanceThroughWakeWord,
    processFinanceThroughNlu: exports.processFinanceThroughNlu,
};
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiYWdlbnRGaW5hbmNlTmx1SW50ZWdyYXRpb24uanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJhZ2VudEZpbmFuY2VObHVJbnRlZ3JhdGlvbi50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiO0FBQUE7Ozs7R0FJRzs7O0FBRUgsK0RBSW9DO0FBQ3BDLDZEQUEwRDtBQUMxRCwyREFBMEQ7QUFFMUQ7OztHQUdHO0FBQ1UsUUFBQSxpQkFBaUIsR0FBZTtJQUMzQyxJQUFJLEVBQUUsaUJBQWlCO0lBRXZCLDhEQUE4RDtJQUM5RCxPQUFPLEVBQUU7UUFDUDtZQUNFLElBQUksRUFBRSxpQkFBaUI7WUFDdkIsUUFBUSxFQUFFO2dCQUNSLG1CQUFtQjtnQkFDbkIsNEJBQTRCO2dCQUM1QixzQkFBc0I7Z0JBQ3RCLGtCQUFrQjthQUNuQjtTQUNGO1FBQ0Q7WUFDRSxJQUFJLEVBQUUsY0FBYztZQUNwQixRQUFRLEVBQUU7Z0JBQ1IsaUJBQWlCO2dCQUNqQixrQkFBa0I7Z0JBQ2xCLCtCQUErQjthQUNoQztTQUNGO1FBQ0Q7WUFDRSxJQUFJLEVBQUUsbUJBQW1CO1lBQ3pCLFFBQVEsRUFBRTtnQkFDUixtQkFBbUI7Z0JBQ25CLG1CQUFtQjtnQkFDbkIsc0JBQXNCO2dCQUN0Qix3QkFBd0I7YUFDekI7U0FDRjtRQUNEO1lBQ0UsSUFBSSxFQUFFLGVBQWU7WUFDckIsUUFBUSxFQUFFLENBQUMsY0FBYyxFQUFFLGlCQUFpQixFQUFFLHVCQUF1QixDQUFDO1NBQ3ZFO1FBQ0Q7WUFDRSxJQUFJLEVBQUUsaUJBQWlCO1lBQ3ZCLFFBQVEsRUFBRTtnQkFDUixjQUFjO2dCQUNkLG9CQUFvQjtnQkFDcEIsbUJBQW1CO2dCQUNuQix1QkFBdUI7YUFDeEI7U0FDRjtRQUNEO1lBQ0UsSUFBSSxFQUFFLHFCQUFxQjtZQUMzQixRQUFRLEVBQUU7Z0JBQ1Isd0JBQXdCO2dCQUN4Qix5QkFBeUI7Z0JBQ3pCLHFCQUFxQjthQUN0QjtTQUNGO1FBQ0Q7WUFDRSxJQUFJLEVBQUUsb0JBQW9C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QUFDLE9BQU8sS0FBSyxFQUFFLENBQUM7UUFDZixPQUFPLENBQUMsR0FBRyxDQUFDLDZDQUE2QyxDQUFDLENBQUM7SUFDN0QsQ0FBQztBQUNILENBQUM7QUFFRCxnQ0FBZ0M7QUFDbkIsUUFBQSxlQUFlLEdBQUc7SUFDN0IsS0FBSyxFQUFFLDhCQUE4QjtJQUNyQyxXQUFXLEVBQUUsMkNBQTJDO0lBQ3hELElBQUksRUFBRTtRQUNKLGdDQUFnQztRQUNoQywwQ0FBMEM7UUFDMUMsZ0VBQWdFO1FBQ2hFLDZEQUE2RDtRQUM3RCxpQ0FBaUM7S0FDbEM7SUFDRCxhQUFhLEVBQUU7UUFDYiwyQkFBMkI7UUFDM0Isb0NBQW9DO1FBQ3BDLHFDQUFxQztRQUNyQyxvQ0FBb0M7UUFDcEMsdUNBQXVDO1FBQ3ZDLHdCQUF3QjtRQUN4QixpQ0FBaUM7S0FDbEM7SUFDRCxXQUFXLEVBQUUsMERBQTBEO0NBQ3hFLENBQUM7QUFFRiwwQ0FBMEM7QUFDMUMsa0JBQWU7SUFDYixPQUFPLEVBQUUseUJBQWlCO0lBQzFCLFFBQVEsRUFBRSxzQ0FBOEI7SUFDeEMsd0JBQXdCLEVBQXhCLGdDQUF3QjtDQUN6QixDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiLyoqXG4gKiBBdG9tIEFnZW50IEZpbmFuY2UgTkxVIEludGVncmF0aW9uXG4gKiBFbmFibGVzIFwiQXRvbVwiIHdha2Ugd29yZCArIG5hdHVyYWwgbGFuZ3VhZ2UgZmluYW5jZSBxdWVyaWVzIHRocm91Z2ggZXhpc3RpbmcgTkxVIHN5c3RlbVxuICogSW50ZWdyYXRlcyBmdWxseSB3aXRoIHdha2Ugd29yZCBhY3RpdmF0aW9uIGZsb3cg4p6cIE5MVSBwcm9jZXNzb3Ig4p6cIGZpbmFuY2UgYWdlbnRcbiAqL1xuXG5pbXBvcnQge1xuICBBZ2VudENvbnRleHQsXG4gIE5MVUhhbmRsZXIsXG4gIHNraWxsRXhlY3V0b3IsXG59IGZyb20gJy4uL3NlcnZpY2VzL2FnZW50Tmx1U3lzdGVtJztcbmltcG9ydCB7IGhhbmRsZUZpbmFuY2VRdWVyeSB9IGZyb20gJy4vZmluYW5jZUFnZW50U2tpbGxzJztcbmltcG9ydCB7IHByb2Nlc3NWb2ljZUZpbmFuY2UgfSBmcm9tICcuL2ZpbmFuY2VWb2ljZUFnZW50JztcblxuLyoqXG4gKiBGaW5hbmNlIE5MVSBIYW5kbGVyIHRoYXQgcGx1Z3MgaW50byBBdG9tJ3MgZXhpc3Rpbmcgd2FrZS13b3JkIGFjdGl2YXRlZCBzeXN0ZW1cbiAqIFdha2Ugd29yZCBcIkF0b21cIiB0cmlnZ2VycyBhZ2VudCDinpwgdGhpcyBOTFUgaGFuZGxlciBwcm9jZXNzZXMgZmluYW5jZSBjb21tYW5kcyBuYXR1cmFsbHlcbiAqL1xuZXhwb3J0IGNvbnN0IGZpbmFuY2VObHVIYW5kbGVyOiBOTFVIYW5kbGVyID0ge1xuICBuYW1lOiAnZmluYW5jZS1oYW5kbGVyJyxcblxuICAvLyBGaW5hbmNlLXNwZWNpZmljIGludGVudCByZWNvZ25pdGlvbiBsZXZlcmFnaW5nIGV4aXN0aW5nIE5MVVxuICBpbnRlbnRzOiBbXG4gICAge1xuICAgICAgbmFtZTogJ25ldF93b3J0aF9xdWVyeScsXG4gICAgICBwYXR0ZXJuczogW1xuICAgICAgICAvd2hhdC4qbmV0Lip3b3J0aC9pLFxuICAgICAgICAvaG93LiptdWNoLiooYW18ZG8pLip3b3J0aC9pLFxuICAgICAgICAvZmluYW5jaWFsLipwb3NpdGlvbi9pLFxuICAgICAgICAvd2VhbHRoLipzdW1tYXJ5L2ksXG4gICAgICBdLFxuICAgIH0sXG4gICAge1xuICAgICAgbmFtZTogJ2J1ZGdldF9xdWVyeScsXG4gICAgICBwYXR0ZXJuczogW1xuICAgICAgICAvYnVkZ2V0LipzdGF0dXMvaSxcbiAgICAgICAgL3NwZW5kaW5nLipsaW1pdC9pLFxuICAgICAgICAvaG93LiptdWNoLipsZWZ0Lipmb3IuKmJ1ZGdldC9pLFxuICAgICAgXSxcbiAgICB9LFxuICAgIHtcbiAgICAgIG5hbWU6ICdzcGVuZGluZ19hbmFseXNpcycsXG4gICAgICBwYXR0ZXJuczogW1xuICAgICAgICAvaG93LiptdWNoLipzcGVudC9pLFxuICAgICAgICAvd2hlcmUuKm1vbmV5Lipnby9pLFxuICAgICAgICAvc3BlbmRpbmcuKmJyZWFrZG93bi9pLFxuICAgICAgICAvZXhwZW5zZXMuKnRoaXMuKm1vbnRoL2ksXG4gICAgICBdLFxuICAgIH0sXG4gICAge1xuICAgICAgbmFtZTogJ2NyZWF0ZV9idWRnZXQnLFxuICAgICAgcGF0dGVybnM6IFsvc2V0LipidWRnZXQvaSwgL2NyZWF0ZS4qYnVkZ2V0L2ksIC9idWRnZXQuKmZvci4qXFwkKFxcZCspL2ldLFxuICAgIH0sXG4gICAge1xuICAgICAgbmFtZTogJ2ZpbmFuY2lhbF9nb2FscycsXG4gICAgICBwYXR0ZXJuczogW1xuICAgICAgICAvc2hvdy4qZ29hbHMvaSxcbiAgICAgICAgL3NhdmluZ3MuKnByb2dyZXNzL2ksXG4gICAgICAgIC9maW5hbmNpYWwuKmdvYWxzL2ksXG4gICAgICAgIC9yZXRpcmVtZW50Lip0cmFja2luZy9pLFxuICAgICAgXSxcbiAgICB9LFxuICAgIHtcbiAgICAgIG5hbWU6ICdpbnZlc3RtZW50X292ZXJ2aWV3JyxcbiAgICAgIHBhdHRlcm5zOiBbXG4gICAgICAgIC9pbnZlc3RtZW50Lipwb3J0Zm9saW8vaSxcbiAgICAgICAgL3BvcnRmb2xpby4qcGVyZm9ybWFuY2UvaSxcbiAgICAgICAgL3N0b2NrLippbnZlc3RtZW50cy9pLFxuICAgICAgXSxcbiAgICB9LFxuICAgIHtcbiAgICAgIG5hbWU6ICd0cmFuc2FjdGlvbl9zZWFyY2gnLFxuICAgICAgcGF0dGVybnM6IFtcbiAgICAgICAgL2ZpbmQuKnRyYW5zYWN0aW9ucy9pLFxuICAgICAgICAvc2VhcmNoLipwdXJjaGFzZXMvaSxcbiAgICAgICAgL3Nob3cuKnNwZW5kaW5nL2ksXG4gICAgICBdLFxuICAgIH0sXG4gIF0sXG5cbiAgLyoqXG4gICAqIFByb2Nlc3NlcyBhbnkgdGV4dCBlbnRlcmluZyBBdG9tJ3MgTkxVIHN5c3RlbSBhZnRlciBcIkF0b21cIiB3YWtlIHdvcmRcbiAgICogRXhhbXBsZSBmbG93OiBcIkF0b20g4oaSIHNob3cgbXkgbmV0IHdvcnRoXCIg4p6cIE5MVSBjYXB0dXJlcyDinpwgZmluYW5jZSBwcm9jZXNzaW5nXG4gICAqL1xuICBhc3luYyBoYW5kbGVUZXh0KGNvbnRleHQ6IEFnZW50Q29udGV4dCwgdGV4dDogc3RyaW5nKTogUHJvbWlzZTxhbnk+IHtcbiAgICBjb25zdCB1c2VySWQgPSBjb250ZXh0LnVzZXI/LmlkIHx8ICd1c2VyJztcblxuICAgIC8vIENsZWFuIFwiQXRvbVwiIHdha2Ugd29yZCBwcmVmaXggaWYgcHJlc2VudFxuICAgIGNvbnN0IGNsZWFuVGV4dCA9IHRleHQucmVwbGFjZSgvXmF0b21cXHMqL2ksICcnKS50cmltKCk7XG5cbiAgICBpZiAoIWNsZWFuVGV4dCkgcmV0dXJuIG51bGw7XG5cbiAgICAvLyBSb3V0ZSB0aHJvdWdoIGV4aXN0aW5nIGZpbmFuY2Ugc3lzdGVtXG4gICAgcmV0dXJuIGF3YWl0IGhhbmRsZUZpbmFuY2VRdWVyeSh1c2VySWQsIGNsZWFuVGV4dCwge1xuICAgICAgLi4uY29udGV4dCxcbiAgICAgIHNvdXJjZTogJ3ZvaWNlX3dha2UnLFxuICAgICAgaW50ZXJmYWNlOiAndm9pY2Vfbmx1JyxcbiAgICB9KTtcbiAgfSxcblxuICAvKipcbiAgICogVm9pY2UtYXdhcmUgbmF0dXJhbCBsYW5ndWFnZSBwcm9jZXNzaW5nIGxldmVyYWdpbmcgZXhpc3RpbmcgQXRvbSBOTFVcbiAgICovXG4gIHZvaWNlUHJvY2Vzc2luZzoge1xuICAgIGhhbmRsZVdha2VBY3RpdmF0aW9uOiBhc3luYyAoY29udGV4dDogQWdlbnRDb250ZXh0KSA9PiB7XG4gICAgICByZXR1cm4ge1xuICAgICAgICBncmVldGluZzogJ/CfkrAgRmluYW5jZSBtb2RlIGFjdGl2YXRlZCEgU2F5IHRoaW5ncyBsaWtlOicsXG4gICAgICAgIGV4YW1wbGVzOiBbXG4gICAgICAgICAgJ1doYXQgaXMgbXkgbmV0IHdvcnRoPycsXG4gICAgICAgICAgJ1Nob3cgbXkgYnVkZ2V0JyxcbiAgICAgICAgICAnSG93IG11Y2ggZGlkIEkgc3BlbmQgb24gcmVzdGF1cmFudHM/JyxcbiAgICAgICAgICAnQ3JlYXRlIGEgc2F2aW5ncyBnb2FsJyxcbiAgICAgICAgICAnSW52ZXN0bWVudCBwb3J0Zm9saW8nLFxuICAgICAgICBdLFxuICAgICAgfTtcbiAgICB9LFxuXG4gICAgcHJvY2Vzc1ZvaWNlSW5wdXQ6IGFzeW5jICh2b2ljZVRleHQ6IHN0cmluZywgY29udGV4dDogQWdlbnRDb250ZXh0KSA9PiB7XG4gICAgICBjb25zdCB1c2VySWQgPSBjb250ZXh0LnVzZXI/LmlkIHx8ICd1c2VyJztcblxuICAgICAgLy8gRGlyZWN0IHZvaWNlIHByb2Nlc3NpbmcgdGhyb3VnaCBOTFUgbGF5ZXJcbiAgICAgIHJldHVybiBhd2FpdCBwcm9jZXNzVm9pY2VGaW5hbmNlLnByb2Nlc3NWb2ljZUZpbmFuY2VDb21tYW5kKFxuICAgICAgICB1c2VySWQsXG4gICAgICAgIHZvaWNlVGV4dCxcbiAgICAgICAge1xuICAgICAgICAgIC4uLmNvbnRleHQsXG4gICAgICAgICAgaW50ZXJmYWNlOiAndm9pY2Vfd2FrZV9ubHUnLFxuICAgICAgICAgIHRpbWVzdGFtcDogRGF0ZS5ub3coKSxcbiAgICAgICAgfVxuICAgICAgKTtcbiAgICB9LFxuICB9LFxufTtcblxuLy8gSW50ZWdyYXRpb24gaG9vayBmb3IgZXhpc3RpbmcgQXRvbSBOTFUgc3lzdGVtXG5leHBvcnQgY29uc3QgYWN0aXZhdGVGaW5hbmNlVGhyb3VnaFdha2VXb3JkID0gYXN5bmMgKCkgPT4ge1xuICBhd2FpdCBza2lsbEV4ZWN1dG9yLnJlZ2lzdGVyTmx1SGFuZGxlcignZmluYW5jZScsIGZpbmFuY2VObHVIYW5kbGVyKTtcbiAgY29uc29sZS5sb2coJ/CflIogQXRvbSBmaW5hbmNlIE5MVSBpbnRlZ3JhdGVkIHdpdGggd2FrZSB3b3JkIHN5c3RlbScpO1xuICBjb25zb2xlLmxvZygn4pyFIFNheSBcIkF0b21cIiB0aGVuIGFueSBmaW5hbmNlIGNvbW1hbmQgbmF0dXJhbGx5Jyk7XG5cbiAgcmV0dXJuIHtcbiAgICBhd2FrZTogZmFsc2UsXG4gICAgbGlzdGVuRm9yOiBbXG4gICAgICAnd2hhdCBpcyBteSBuZXQgd29ydGgnLFxuICAgICAgJ3Nob3cgbXkgYnVkZ2V0JyxcbiAgICAgICdob3cgbXVjaCBkaWQgSSBzcGVuZCBvbicsXG4gICAgICAnY3JlYXRlIGEgYnVkZ2V0IGZvcicsXG4gICAgICAnc2hvdyBteSBmaW5hbmNpYWwgZ29hbHMnLFxuICAgICAgJ2ludmVzdG1lbnQgcG9ydGZvbGlvJyxcbiAgICAgICdjb21wYXJlIHRoaXMgbW9udGggdG8gbGFzdCcsXG4gICAgXSxcbiAgICByZXNwb25zZU1vZGU6ICdjb252ZXJzYXRpb25hbCcsXG4gIH07XG59O1xuXG4vLyBEaXJlY3QgZmluYW5jZSBjb21tYW5kIHByb2Nlc3NpbmcgcmVnYXJkbGVzcyBvZiBlbnRyeSBwb2ludFxuZXhwb3J0IGNvbnN0IHByb2Nlc3NGaW5hbmNlVGhyb3VnaE5sdSA9IGFzeW5jIChcbiAgY29udGV4dDogQWdlbnRDb250ZXh0LFxuICB0ZXh0OiBzdHJpbmdcbik6IFByb21pc2U8YW55PiA9PiB7XG4gIHJldHVybiBhd2FpdCBmaW5hbmNlTmx1SGFuZGxlci5oYW5kbGVUZXh0KGNvbnRleHQsIHRleHQpO1xufTtcblxuLy8gQXV0by1yZWdpc3RyYXRpb24gb24gbW9kdWxlIGltcG9ydFxuaWYgKHR5cGVvZiB3aW5kb3cgPT09ICd1bmRlZmluZWQnKSB7XG4gIC8vIFNlcnZlci1zaWRlOiByZWdpc3RlciBpbW1lZGlhdGVseVxuICBhY3RpdmF0ZUZpbmFuY2VUaHJvdWdoV2FrZVdvcmQoKS5jYXRjaChjb25zb2xlLmVycm9yKTtcbn0gZWxzZSB7XG4gIC8vIENsaWVudC1zaWRlOiByZWdpc3RlciB3aGVuIERPTSByZWFkeVxuICB0cnkge1xuICAgIGFjdGl2YXRlRmluYW5jZVRocm91Z2hXYWtlV29yZCgpO1xuICB9IGNhdGNoIChlcnJvcikge1xuICAgIGNvbnNvbGUubG9nKCdGaW5hbmNlIE5MVSBzeXN0ZW0gcmVhZHkgZm9yIEF0b20gd2FrZSB3b3JkJyk7XG4gIH1cbn1cblxuLy8gQWN0aXZhdGlvbiBmbG93IGRvY3VtZW50YXRpb25cbmV4cG9ydCBjb25zdCBGaW5hbmNlV2FrZUZsb3cgPSB7XG4gIHRpdGxlOiAnQXRvbSBGaW5hbmNlIEFjdGl2YXRpb24gRmxvdycsXG4gIGRlc2NyaXB0aW9uOiAnSG93IHdha2Ugd29yZCArIGZpbmFuY2Ugd29ya3MgdGhyb3VnaCBOTFUnLFxuICBmbG93OiBbXG4gICAgXCJVc2VyOiAnQXRvbSBzaG93IG15IG5ldCB3b3J0aCdcIixcbiAgICAnV2FrZSBXb3JkIERldGVjdG9yOiBBY3RpdmF0ZXMgQXRvbSBhZ2VudCcsXG4gICAgJ05MVSBTeXN0ZW06IERldGVjdHMgZmluYW5jZSBpbnRlbnQg4oaSIHJvdXRlcyB0byBmaW5hbmNlIGhhbmRsZXInLFxuICAgICdGaW5hbmNlIEFnZW50OiBQcm9jZXNzZXMgcXVlcnkg4oaSIHJldHVybnMgZm9ybWF0dGVkIHJlc3BvbnNlJyxcbiAgICAnQXRvbTogU3BlYWtzIGJhY2sgdmlhIHZvaWNlL1RUUycsXG4gIF0sXG4gIHZvaWNlQ29tbWFuZHM6IFtcbiAgICAnQXRvbSB3aGF0IGlzIG15IG5ldCB3b3J0aCcsXG4gICAgJ0F0b20gc2hvdyBteSBidWRnZXQgZm9yIHRoaXMgbW9udGgnLFxuICAgICdBdG9tIGhvdyBtdWNoIGRpZCBJIHNwZW5kIG9uIGRpbmluZycsXG4gICAgJ0F0b20gY3JlYXRlIGEgdHJhdmVsIGdvYWwgb2YgJDIwMDAnLFxuICAgICdBdG9tIGludmVzdG1lbnQgcG9ydGZvbGlvIHBlcmZvcm1hbmNlJyxcbiAgICAnQXRvbSBoZWxwIHdpdGggYnVkZ2V0cycsXG4gICAgJ0F0b20gY29tcGFyZSB0aGlzIG1vbnRoIHRvIGxhc3QnLFxuICBdLFxuICBpbnRlZ3JhdGlvbjogJ1VzZXMgZXhpc3Rpbmcgd2FrZSB3b3JkIHN5c3RlbSwgbm8gbmV3IHdha2Ugd29yZHMgbmVlZGVkJyxcbn07XG5cbi8vIEV4cG9ydCBmb3Igd2FrZSB3b3JkIHN5c3RlbSBpbnRlZ3JhdGlvblxuZXhwb3J0IGRlZmF1bHQge1xuICBoYW5kbGVyOiBmaW5hbmNlTmx1SGFuZGxlcixcbiAgYWN0aXZhdGU6IGFjdGl2YXRlRmluYW5jZVRocm91Z2hXYWtlV29yZCxcbiAgcHJvY2Vzc0ZpbmFuY2VUaHJvdWdoTmx1LFxufTtcbiJdfQ==