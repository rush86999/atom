import { Skill, SkillResponse } from '../types';
import axios from 'axios';

class FinancialGoalsSkill implements Skill {
  name = 'financialGoals';
  description = 'Manage financial goals through conversation';

  triggerPatterns = [
    /set (a|the) (?:financial )?goal/i,
    /create (a|the) (?:financial )?goal/i,
    /new (?:financial )?goal/i,
    /add (?:a|the) (?:financial )?goal/i,
    /my goals/i,
    /show me (?:my )?goals?/i,
    /list goals?/i,
    /goal status/i,
    /update goal/i,
    /contribute to goal/i,
    /progress toward/i,
    /how (?:much|close) (?:to|am i to) (?:my )?goal/i,
    /save (?:up for|toward)/i
  ];

  async execute(context: any, input: string, userId: string): Promise<SkillResponse<string>> {
    try {
      const intent = await this.analyzeIntent(input);

      switch (intent.type) {
        case 'CREATE_GOAL':
          return await this.createGoal(intent.data, userId);
        case 'LIST_GOALS':
          return await this.listGoals(userId);
        case 'UPDATE_GOAL':
          return await this.updateGoal(intent.data, userId);
        case 'ADD_CONTRIBUTION':
          return await this.addContribution(intent.data, userId);
        default:
          return await this.listGoals(userId);
      }
    } catch (error) {
      return {
        ok: false,
        error: { code: 'GOAL_ERROR', message: 'Unable to process goal request' }
      };
    }
  }

  private async analyzeIntent(input: string) {
    const lower = input.toLowerCase();

    // Create goal patterns
    const createMatch = input.match(/(?:create|set) (?:a )?goal for (?:.*?) of \$?(\d+)/i);
    if (createMatch) {
      return {
        type: 'CREATE_GOAL',
        data: {
          title: input.split('for')[1]?.split(' of')[0]?.trim() || 'Financial Goal',
          targetAmount: parseFloat(createMatch[1]),
          goalType: 'savings'
        }
      };
    }

    // Add contribution patterns
    const contribMatch = input.match(/(?:add|contribute|put|deposit) \$?(\d+)/i);
    if (contribMatch) {
      return {
        type: 'ADD_CONTRIBUTION',
        data: {
          amount: parseFloat(contribMatch[1]),
          goalId: 1
        }
      };
    }

    return { type: 'LIST_GOALS', data: {} };
  }

  private async createGoal(data: any, userId: string): Promise<SkillResponse<string>> {
    try {
      const response = await axios.post('/api/goals', {
        userId,
        title: data.title,
        targetAmount: data.targetAmount,
        goalType: data.goalType || 'savings'
      });

      return {
        ok: true,
        data: `🎯 Great! I've created your goal "${data.title}" for $${data.targetAmount.toLocaleString()}.`
      };
    } catch (error) {
      return { ok: false, error: { code: 'CREATE_FAILED', message: 'Failed to create goal' } };
    }
  }

  private async listGoals(userId: string): Promise<SkillResponse<string>> {
    try {
      const response = await axios.get('/api/goals', { params: { userId } });
      const goals = response.data.goals;

      if (goals.length === 0) {
        return {
          ok: true,
          data: "💭 You don't have any goals yet. Say 'create a goal for vacation of $5000' to get started!"
        };
      }

      let text = "🎯 **Your Financial Goals:**\n\n";
      goals.forEach((goal: any) => {
        const progress = goal.progress || 0;
        const bar = '█'.repeat(Math.floor(progress/10)) + '░'.repeat(10-Math.floor(progress/10));
        text += `${goal.name}: ${bar} ${progress.toFixed(1)}% ($${goal.current}/${goal.target})\n`;
      });

      return { ok: true, data: text };
    } catch (error) {
      return { ok: false, error: { code: 'LIST_FAILED', message: 'Unable to fetch goals' } };
    }
  }

  private async updateGoal(data: any, userId: string): Promise<SkillResponse<string>> {
    try {
      await axios.put(`/api/goals/
