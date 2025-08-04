import { AdvancedResearchAgent } from './advancedResearchSkill';

class AdvancedResearchSkill {
  public handler = new AdvancedResearchAgent(null as any).analyze;
}

export { AdvancedResearchSkill };
