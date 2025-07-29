import { SkillDefinition } from '../services/agentSkillRegistry';
import { legalDocumentAnalysisSkill } from './legalDocumentAnalysisSkill';

class LegalDocumentAnalysisSkill {
    public handler = legalDocumentAnalysisSkill;
}

export const legalSkills: SkillDefinition[] = [
  {
    name: 'legalDocumentAnalysis',
    description: 'Analyzes legal documents and provides insights.',
    parameters: {
      url: {
        type: 'string',
        description: 'The URL of the legal document to analyze.',
        required: true,
      },
    },
    handler: new LegalDocumentAnalysisSkill().handler,
  },
];

export { LegalDocumentAnalysisSkill };
