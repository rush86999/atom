import { handleScheduleSkillActivation } from './schedulingSkills';
import { scheduleTask } from './schedulingSkills';

jest.mock('@/agendaService', () => ({
    agenda: {
        schedule: jest.fn(),
        every: jest.fn(),
    },
}));

describe('handleScheduleSkillActivation', () => {
    it('should call scheduleTask with the correct parameters', async () => {
        const userId = 'test-user';
        const entities = {
            skill_to_schedule: 'SendEmail',
            activation_time: 'tomorrow at 9am',
            skill_entities: {
                to: 'test@example.com',
                subject: 'Test',
                body: 'This is a test',
            },
        };

        const result = await handleScheduleSkillActivation(userId, entities);

        expect(result).toEqual('Task "SendEmail" has been scheduled for tomorrow at 9am.');
    });
});
