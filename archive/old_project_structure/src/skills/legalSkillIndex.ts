import { LegalDocumentAnalysisAgent } from './legalDocumentAnalysisSkill';

class LegalDocumentAnalysisSkill {
  public handler = new LegalDocumentAnalysisAgent(null as any).analyze;
}

export { LegalDocumentAnalysisSkill };
