import { SkillDefinition } from '../services/agentSkillRegistry';
import { advancedResearchSkill } from './advancedResearchSkill';

class AdvancedResearchSkill {
    public handler = advancedResearchSkill;
}

export const researchSkills: SkillDefinition[] = [
  {
    name: 'advancedResearch',
    description: 'Performs advanced research using various sources.',
    parameters: {
      topic: {
        type: 'string',
        description: 'The topic to research.',
        required: true,
      },
      source: {
        type: 'string',
        description: 'The source to use for research (e.g., web, academic, news).',
        required: false,
      },
    },
    handler: new AdvancedResearchSkill().handler,
  },
];

export { AdvancedResearchSkill };
