"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.LegalDocumentAnalysisSkill = void 0;
const legalDocumentAnalysisSkill_1 = require("./legalDocumentAnalysisSkill");
class LegalDocumentAnalysisSkill {
    constructor() {
        this.handler = new legalDocumentAnalysisSkill_1.LegalDocumentAnalysisAgent(null).analyze;
    }
}
exports.LegalDocumentAnalysisSkill = LegalDocumentAnalysisSkill;
//# sourceMappingURL=legalSkillIndex.js.map