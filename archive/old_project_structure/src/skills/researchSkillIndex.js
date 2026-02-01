"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.AdvancedResearchSkill = void 0;
const advancedResearchSkill_1 = require("./advancedResearchSkill");
class AdvancedResearchSkill {
    constructor() {
        this.handler = new advancedResearchSkill_1.AdvancedResearchAgent(null).analyze;
    }
}
exports.AdvancedResearchSkill = AdvancedResearchSkill;
//# sourceMappingURL=researchSkillIndex.js.map