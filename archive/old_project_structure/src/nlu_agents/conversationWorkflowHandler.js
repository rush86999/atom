"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.ConversationWorkflowHandler = void 0;
atom / src / nlu_agents / conversationWorkflowHandler.ts
    < /file_path>;
const events_1 = require("events");
const uuid_1 = require("uuid");
const dayjs_1 = __importDefault(require("dayjs"));
class ConversationWorkflowHandler extends events_1.EventEmitter {
    constructor() {
        super();
        this.activeConversations = new Map();
        this.conversationMemory = new Map();
        this.intentClassifier = {
            patterns: new Map(),
            learnedIntents: new Map()
        };
        this.initializePatterns();
    }
    initializePatterns() {
        // Workflow creation patterns
        this.intentClassifier.patterns.set('CREATE_WORKFLOW', /(?:create|build|set up|automate|design)\s+(?:workflow|process|system|automation)/i);
        this.intentClassifier.patterns.set('MANAGE_WORKFLOW', /(?:manage|schedule|update|pause|cancel|monitor)\s+(?:workflow|process|automation)/i);
        this.intentClassifier.patterns.set('OPTIMIZE_PROCESS', /(?:optimize|improve|enhance|streamline)\s+(?:process|workflow|system)/i);
        this.intentClassifier.patterns.set('ANALYZE_IMPACT', /(?:impact|benefit|roi|outcome)\s+(?:of|from)\s+(?:automation|workflow)/i);
    }
    async processUserMessage(userId, text, context) {
        const sessionId = context?.sessionId || (0, uuid_1.v4)();
        let conversation = this.activeConversations.get(sessionId);
        if (!conversation) {
            conversation = this.createConversation(userId, sessionId);
            this.activeConversations.set(sessionId, conversation);
        }
        const intent = await this.extractIntent(text, context);
        conversation.messages.push({
            id: (0, uuid_1.v4)(),
            text,
            role: 'user',
            timestamp: (0, dayjs_1.default)().toISOString(),
            intent
        });
        const response = await this.generateResponse(conversation, intent, text);
        if (response.requiresConfirmation) {
            const confirmationId = (0, uuid_1.v4)();
            response.confirmationId = confirmationId;
            conversation.currentState.requiredConfirmations.push(confirmationId);
        }
        conversation.messages.push({
            id: (0, uuid_1.v4)(),
            text: response.response,
            role: 'assistant',
            timestamp: (0, dayjs_1.default)().toISOString(),
            actions: response.suggestedActions
        });
        this.updateConversationState(conversation, intent);
        return {
            response: response.response,
            followUp: response.followUp,
            suggestedActions: response.suggestedActions,
            requiresInput: response.requiresInput,
            metadata: {
                currentPhase: conversation.currentState.currentPhase,
                complexityScore: conversation.metadata.complexityScore,
                escalationLevel: conversation.metadata.escalationLevel
            }
        };
    }
    createConversation(userId, sessionId) {
        return {
            id: sessionId,
            userId,
            startTime: (0, dayjs_1.default)().toISOString(),
            messages: [],
            currentState: {
                currentPhase: 'discovery',
            }
        };
    }
}
exports.ConversationWorkflowHandler = ConversationWorkflowHandler;
//# sourceMappingURL=conversationWorkflowHandler.js.map