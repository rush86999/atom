import { runAutonomousWebAppFlow } from './devOpsOrchestrator';
import { runAutonomousSystem } from './autonomousSystemOrchestrator';

// Mock the autonomousSystemOrchestrator module
jest.mock('./autonomousSystemOrchestrator', () => ({
    runAutonomousSystem: jest.fn(),
}));

describe('runAutonomousWebAppFlow', () => {
    it('should call runAutonomousSystem with the correct parameters', async () => {
        const userId = 'test-user';
        const owner = 'test-owner';
        const repo = 'test-repo';
        const jiraProjectKey = 'TEST';
        const slackChannelId = 'C12345';

        await runAutonomousWebAppFlow(
            userId,
            owner,
            repo,
            jiraProjectKey,
            slackChannelId
        );

        expect(runAutonomousSystem).toHaveBeenCalledWith(
            userId,
            owner,
            repo,
            jiraProjectKey,
            slackChannelId
        );
    });
});
