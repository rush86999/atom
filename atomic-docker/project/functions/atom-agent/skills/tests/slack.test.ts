import { handleSendSlackMessage, handleSlackMyAgenda } from '../slack';
import * as slackSkills from '../slackSkills';
import * as calendarSkills from '../calendarSkills';

jest.mock('../slackSkills', () => ({
    sendSlackMessage: jest.fn(),
}));

jest.mock('../calendarSkills', () => ({
    listUpcomingEvents: jest.fn(),
}));

describe('slack skill', () => {
    afterEach(() => {
        jest.clearAllMocks();
    });

    describe('handleSendSlackMessage', () => {
        it('should send a Slack message', async () => {
            (slackSkills.sendSlackMessage as jest.Mock).mockResolvedValue({
                ok: true,
            });

            const result = await handleSendSlackMessage('test-user', { slack_channel: 'test-channel', message_text: 'Test message' });

            expect(result).toBe('Message sent to Slack channel/user test-channel.');
        });

        it('should return an error message when the channel is missing', async () => {
            const result = await handleSendSlackMessage('test-user', { message_text: 'Test message' });

            expect(result).toBe('Slack channel/user ID is required to send a message via NLU.');
        });

        it('should return an error message when the message text is missing', async () => {
            const result = await handleSendSlackMessage('test-user', { slack_channel: 'test-channel' });

            expect(result).toBe('Message text is required to send a Slack message via NLU.');
        });

        it('should return an error message when an error occurs', async () => {
            (slackSkills.sendSlackMessage as jest.Mock).mockRejectedValue(new Error('Test Error'));

            const result = await handleSendSlackMessage('test-user', { slack_channel: 'test-channel', message_text: 'Test message' });

            expect(result).toBe('Sorry, there was an issue sending your Slack message.');
        });
    });

    describe('handleSlackMyAgenda', () => {
        it('should send the agenda to Slack', async () => {
            const mockEvents = [
                {
                    summary: 'Test Event 1',
                    startTime: new Date().toISOString(),
                    endTime: new Date().toISOString(),
                },
            ];
            (calendarSkills.listUpcomingEvents as jest.Mock).mockResolvedValue(mockEvents);
            (slackSkills.sendSlackMessage as jest.Mock).mockResolvedValue({
                ok: true,
            });

            const result = await handleSlackMyAgenda('test-user', {});

            expect(result).toBe("I've sent your agenda to your Slack DM (NLU path)!");
        });

        it('should send a message when there are no events', async () => {
            (calendarSkills.listUpcomingEvents as jest.Mock).mockResolvedValue([]);
            (slackSkills.sendSlackMessage as jest.Mock).mockResolvedValue({
                ok: true,
            });

            const result = await handleSlackMyAgenda('test-user', {});

            expect(result).toBe("I've checked your calendar; no upcoming events. Sent a note to your Slack DM (NLU path).");
        });

        it('should return an error message when an error occurs', async () => {
            (calendarSkills.listUpcomingEvents as jest.Mock).mockRejectedValue(new Error('Test Error'));

            const result = await handleSlackMyAgenda('test-user', {});

            expect(result).toBe('Sorry, an error occurred while processing your agenda for Slack (NLU path).');
        });
    });
});
