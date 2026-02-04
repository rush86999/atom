"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.DEFAULT_TEMPERATURE_LEAD_SYNTHESIS = exports.DEFAULT_TEMPERATURE_PRACTICAL = exports.DEFAULT_TEMPERATURE_CREATIVE = exports.DEFAULT_TEMPERATURE_ANALYTICAL = exports.DEFAULT_MODEL_LEAD_SYNTHESIS = exports.DEFAULT_MODEL_FOR_AGENTS = void 0;
exports.safeParseJSON = safeParseJSON;
exports.DEFAULT_MODEL_FOR_AGENTS = 'mixtral-8x7b-32768'; // Or any other preferred model
exports.DEFAULT_MODEL_LEAD_SYNTHESIS = 'mixtral-8x7b-32768'; // Could be a more powerful model
exports.DEFAULT_TEMPERATURE_ANALYTICAL = 0.2;
exports.DEFAULT_TEMPERATURE_CREATIVE = 0.8;
exports.DEFAULT_TEMPERATURE_PRACTICAL = 0.4;
exports.DEFAULT_TEMPERATURE_LEAD_SYNTHESIS = 0.3;
// Helper to safely parse JSON from LLM
function safeParseJSON(jsonString, agentName, task) {
    if (!jsonString) {
        console.warn(`[${agentName}] LLM response for task '${task}' was empty.`);
        return null;
    }
    try {
        return JSON.parse(jsonString);
    }
    catch (error) {
        console.error(`[${agentName}] Failed to parse JSON response for task '${task}'. Error: ${error}. Response: ${jsonString.substring(0, 200)}...`);
        return null;
    }
}
//# sourceMappingURL=nlu_types.js.map