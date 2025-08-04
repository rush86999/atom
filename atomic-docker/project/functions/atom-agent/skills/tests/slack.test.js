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
            slackSkills.sendSlackMessage.mockResolvedValue({
                ok: true,
            });
            const result = await handleSendSlackMessage('test-user', {
                slack_channel: 'test-channel',
                message_text: 'Test message',
            });
            expect(result).toBe('Message sent to Slack channel/user test-channel.');
        });
        it('should return an error message when the channel is missing', async () => {
            const result = await handleSendSlackMessage('test-user', {
                message_text: 'Test message',
            });
            expect(result).toBe('Slack channel/user ID is required to send a message via NLU.');
        });
        it('should return an error message when the message text is missing', async () => {
            const result = await handleSendSlackMessage('test-user', {
                slack_channel: 'test-channel',
            });
            expect(result).toBe('Message text is required to send a Slack message via NLU.');
        });
        it('should return an error message when an error occurs', async () => {
            slackSkills.sendSlackMessage.mockRejectedValue(new Error('Test Error'));
            const result = await handleSendSlackMessage('test-user', {
                slack_channel: 'test-channel',
                message_text: 'Test message',
            });
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
            calendarSkills.listUpcomingEvents.mockResolvedValue(mockEvents);
            slackSkills.sendSlackMessage.mockResolvedValue({
                ok: true,
            });
            const result = await handleSlackMyAgenda('test-user', {});
            expect(result).toBe("I've sent your agenda to your Slack DM (NLU path)!");
        });
        it('should send a message when there are no events', async () => {
            calendarSkills.listUpcomingEvents.mockResolvedValue([]);
            slackSkills.sendSlackMessage.mockResolvedValue({
                ok: true,
            });
            const result = await handleSlackMyAgenda('test-user', {});
            expect(result).toBe("I've checked your calendar; no upcoming events. Sent a note to your Slack DM (NLU path).");
        });
        it('should return an error message when an error occurs', async () => {
            calendarSkills.listUpcomingEvents.mockRejectedValue(new Error('Test Error'));
            const result = await handleSlackMyAgenda('test-user', {});
            expect(result).toBe('Sorry, an error occurred while processing your agenda for Slack (NLU path).');
        });
    });
});
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoic2xhY2sudGVzdC5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbInNsYWNrLnRlc3QudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6IkFBQUEsT0FBTyxFQUFFLHNCQUFzQixFQUFFLG1CQUFtQixFQUFFLE1BQU0sVUFBVSxDQUFDO0FBQ3ZFLE9BQU8sS0FBSyxXQUFXLE1BQU0sZ0JBQWdCLENBQUM7QUFDOUMsT0FBTyxLQUFLLGNBQWMsTUFBTSxtQkFBbUIsQ0FBQztBQUVwRCxJQUFJLENBQUMsSUFBSSxDQUFDLGdCQUFnQixFQUFFLEdBQUcsRUFBRSxDQUFDLENBQUM7SUFDakMsZ0JBQWdCLEVBQUUsSUFBSSxDQUFDLEVBQUUsRUFBRTtDQUM1QixDQUFDLENBQUMsQ0FBQztBQUVKLElBQUksQ0FBQyxJQUFJLENBQUMsbUJBQW1CLEVBQUUsR0FBRyxFQUFFLENBQUMsQ0FBQztJQUNwQyxrQkFBa0IsRUFBRSxJQUFJLENBQUMsRUFBRSxFQUFFO0NBQzlCLENBQUMsQ0FBQyxDQUFDO0FBRUosUUFBUSxDQUFDLGFBQWEsRUFBRSxHQUFHLEVBQUU7SUFDM0IsU0FBUyxDQUFDLEdBQUcsRUFBRTtRQUNiLElBQUksQ0FBQyxhQUFhLEVBQUUsQ0FBQztJQUN2QixDQUFDLENBQUMsQ0FBQztJQUVILFFBQVEsQ0FBQyx3QkFBd0IsRUFBRSxHQUFHLEVBQUU7UUFDdEMsRUFBRSxDQUFDLDZCQUE2QixFQUFFLEtBQUssSUFBSSxFQUFFO1lBQzFDLFdBQVcsQ0FBQyxnQkFBOEIsQ0FBQyxpQkFBaUIsQ0FBQztnQkFDNUQsRUFBRSxFQUFFLElBQUk7YUFDVCxDQUFDLENBQUM7WUFFSCxNQUFNLE1BQU0sR0FBRyxNQUFNLHNCQUFzQixDQUFDLFdBQVcsRUFBRTtnQkFDdkQsYUFBYSxFQUFFLGNBQWM7Z0JBQzdCLFlBQVksRUFBRSxjQUFjO2FBQzdCLENBQUMsQ0FBQztZQUVILE1BQU0sQ0FBQyxNQUFNLENBQUMsQ0FBQyxJQUFJLENBQUMsa0RBQWtELENBQUMsQ0FBQztR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QUFJLENBQ2pCLDZFQUE2RSxDQUM5RSxDQUFDO1FBQ0osQ0FBQyxDQUFDLENBQUM7SUFDTCxDQUFDLENBQUMsQ0FBQztBQUNMLENBQUMsQ0FBQyxDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IHsgaGFuZGxlU2VuZFNsYWNrTWVzc2FnZSwgaGFuZGxlU2xhY2tNeUFnZW5kYSB9IGZyb20gJy4uL3NsYWNrJztcbmltcG9ydCAqIGFzIHNsYWNrU2tpbGxzIGZyb20gJy4uL3NsYWNrU2tpbGxzJztcbmltcG9ydCAqIGFzIGNhbGVuZGFyU2tpbGxzIGZyb20gJy4uL2NhbGVuZGFyU2tpbGxzJztcblxuamVzdC5tb2NrKCcuLi9zbGFja1NraWxscycsICgpID0+ICh7XG4gIHNlbmRTbGFja01lc3NhZ2U6IGplc3QuZm4oKSxcbn0pKTtcblxuamVzdC5tb2NrKCcuLi9jYWxlbmRhclNraWxscycsICgpID0+ICh7XG4gIGxpc3RVcGNvbWluZ0V2ZW50czogamVzdC5mbigpLFxufSkpO1xuXG5kZXNjcmliZSgnc2xhY2sgc2tpbGwnLCAoKSA9PiB7XG4gIGFmdGVyRWFjaCgoKSA9PiB7XG4gICAgamVzdC5jbGVhckFsbE1vY2tzKCk7XG4gIH0pO1xuXG4gIGRlc2NyaWJlKCdoYW5kbGVTZW5kU2xhY2tNZXNzYWdlJywgKCkgPT4ge1xuICAgIGl0KCdzaG91bGQgc2VuZCBhIFNsYWNrIG1lc3NhZ2UnLCBhc3luYyAoKSA9PiB7XG4gICAgICAoc2xhY2tTa2lsbHMuc2VuZFNsYWNrTWVzc2FnZSBhcyBqZXN0Lk1vY2spLm1vY2tSZXNvbHZlZFZhbHVlKHtcbiAgICAgICAgb2s6IHRydWUsXG4gICAgICB9KTtcblxuICAgICAgY29uc3QgcmVzdWx0ID0gYXdhaXQgaGFuZGxlU2VuZFNsYWNrTWVzc2FnZSgndGVzdC11c2VyJywge1xuICAgICAgICBzbGFja19jaGFubmVsOiAndGVzdC1jaGFubmVsJyxcbiAgICAgICAgbWVzc2FnZV90ZXh0OiAnVGVzdCBtZXNzYWdlJyxcbiAgICAgIH0pO1xuXG4gICAgICBleHBlY3QocmVzdWx0KS50b0JlKCdNZXNzYWdlIHNlbnQgdG8gU2xhY2sgY2hhbm5lbC91c2VyIHRlc3QtY2hhbm5lbC4nKTtcbiAgICB9KTtcblxuICAgIGl0KCdzaG91bGQgcmV0dXJuIGFuIGVycm9yIG1lc3NhZ2Ugd2hlbiB0aGUgY2hhbm5lbCBpcyBtaXNzaW5nJywgYXN5bmMgKCkgPT4ge1xuICAgICAgY29uc3QgcmVzdWx0ID0gYXdhaXQgaGFuZGxlU2VuZFNsYWNrTWVzc2FnZSgndGVzdC11c2VyJywge1xuICAgICAgICBtZXNzYWdlX3RleHQ6ICdUZXN0IG1lc3NhZ2UnLFxuICAgICAgfSk7XG5cbiAgICAgIGV4cGVjdChyZXN1bHQpLnRvQmUoXG4gICAgICAgICdTbGFjayBjaGFubmVsL3VzZXIgSUQgaXMgcmVxdWlyZWQgdG8gc2VuZCBhIG1lc3NhZ2UgdmlhIE5MVS4nXG4gICAgICApO1xuICAgIH0pO1xuXG4gICAgaXQoJ3Nob3VsZCByZXR1cm4gYW4gZXJyb3IgbWVzc2FnZSB3aGVuIHRoZSBtZXNzYWdlIHRleHQgaXMgbWlzc2luZycsIGFzeW5jICgpID0+IHtcbiAgICAgIGNvbnN0IHJlc3VsdCA9IGF3YWl0IGhhbmRsZVNlbmRTbGFja01lc3NhZ2UoJ3Rlc3QtdXNlcicsIHtcbiAgICAgICAgc2xhY2tfY2hhbm5lbDogJ3Rlc3QtY2hhbm5lbCcsXG4gICAgICB9KTtcblxuICAgICAgZXhwZWN0KHJlc3VsdCkudG9CZShcbiAgICAgICAgJ01lc3NhZ2UgdGV4dCBpcyByZXF1aXJlZCB0byBzZW5kIGEgU2xhY2sgbWVzc2FnZSB2aWEgTkxVLidcbiAgICAgICk7XG4gICAgfSk7XG5cbiAgICBpdCgnc2hvdWxkIHJldHVybiBhbiBlcnJvciBtZXNzYWdlIHdoZW4gYW4gZXJyb3Igb2NjdXJzJywgYXN5bmMgKCkgPT4ge1xuICAgICAgKHNsYWNrU2tpbGxzLnNlbmRTbGFja01lc3NhZ2UgYXMgamVzdC5Nb2NrKS5tb2NrUmVqZWN0ZWRWYWx1ZShcbiAgICAgICAgbmV3IEVycm9yKCdUZXN0IEVycm9yJylcbiAgICAgICk7XG5cbiAgICAgIGNvbnN0IHJlc3VsdCA9IGF3YWl0IGhhbmRsZVNlbmRTbGFja01lc3NhZ2UoJ3Rlc3QtdXNlcicsIHtcbiAgICAgICAgc2xhY2tfY2hhbm5lbDogJ3Rlc3QtY2hhbm5lbCcsXG4gICAgICAgIG1lc3NhZ2VfdGV4dDogJ1Rlc3QgbWVzc2FnZScsXG4gICAgICB9KTtcblxuICAgICAgZXhwZWN0KHJlc3VsdCkudG9CZShcbiAgICAgICAgJ1NvcnJ5LCB0aGVyZSB3YXMgYW4gaXNzdWUgc2VuZGluZyB5b3VyIFNsYWNrIG1lc3NhZ2UuJ1xuICAgICAgKTtcbiAgICB9KTtcbiAgfSk7XG5cbiAgZGVzY3JpYmUoJ2hhbmRsZVNsYWNrTXlBZ2VuZGEnLCAoKSA9PiB7XG4gICAgaXQoJ3Nob3VsZCBzZW5kIHRoZSBhZ2VuZGEgdG8gU2xhY2snLCBhc3luYyAoKSA9PiB7XG4gICAgICBjb25zdCBtb2NrRXZlbnRzID0gW1xuICAgICAgICB7XG4gICAgICAgICAgc3VtbWFyeTogJ1Rlc3QgRXZlbnQgMScsXG4gICAgICAgICAgc3RhcnRUaW1lOiBuZXcgRGF0ZSgpLnRvSVNPU3RyaW5nKCksXG4gICAgICAgICAgZW5kVGltZTogbmV3IERhdGUoKS50b0lTT1N0cmluZygpLFxuICAgICAgICB9LFxuICAgICAgXTtcbiAgICAgIChjYWxlbmRhclNraWxscy5saXN0VXBjb21pbmdFdmVudHMgYXMgamVzdC5Nb2NrKS5tb2NrUmVzb2x2ZWRWYWx1ZShcbiAgICAgICAgbW9ja0V2ZW50c1xuICAgICAgKTtcbiAgICAgIChzbGFja1NraWxscy5zZW5kU2xhY2tNZXNzYWdlIGFzIGplc3QuTW9jaykubW9ja1Jlc29sdmVkVmFsdWUoe1xuICAgICAgICBvazogdHJ1ZSxcbiAgICAgIH0pO1xuXG4gICAgICBjb25zdCByZXN1bHQgPSBhd2FpdCBoYW5kbGVTbGFja015QWdlbmRhKCd0ZXN0LXVzZXInLCB7fSk7XG5cbiAgICAgIGV4cGVjdChyZXN1bHQpLnRvQmUoXCJJJ3ZlIHNlbnQgeW91ciBhZ2VuZGEgdG8geW91ciBTbGFjayBETSAoTkxVIHBhdGgpIVwiKTtcbiAgICB9KTtcblxuICAgIGl0KCdzaG91bGQgc2VuZCBhIG1lc3NhZ2Ugd2hlbiB0aGVyZSBhcmUgbm8gZXZlbnRzJywgYXN5bmMgKCkgPT4ge1xuICAgICAgKGNhbGVuZGFyU2tpbGxzLmxpc3RVcGNvbWluZ0V2ZW50cyBhcyBqZXN0Lk1vY2spLm1vY2tSZXNvbHZlZFZhbHVlKFtdKTtcbiAgICAgIChzbGFja1NraWxscy5zZW5kU2xhY2tNZXNzYWdlIGFzIGplc3QuTW9jaykubW9ja1Jlc29sdmVkVmFsdWUoe1xuICAgICAgICBvazogdHJ1ZSxcbiAgICAgIH0pO1xuXG4gICAgICBjb25zdCByZXN1bHQgPSBhd2FpdCBoYW5kbGVTbGFja015QWdlbmRhKCd0ZXN0LXVzZXInLCB7fSk7XG5cbiAgICAgIGV4cGVjdChyZXN1bHQpLnRvQmUoXG4gICAgICAgIFwiSSd2ZSBjaGVja2VkIHlvdXIgY2FsZW5kYXI7IG5vIHVwY29taW5nIGV2ZW50cy4gU2VudCBhIG5vdGUgdG8geW91ciBTbGFjayBETSAoTkxVIHBhdGgpLlwiXG4gICAgICApO1xuICAgIH0pO1xuXG4gICAgaXQoJ3Nob3VsZCByZXR1cm4gYW4gZXJyb3IgbWVzc2FnZSB3aGVuIGFuIGVycm9yIG9jY3VycycsIGFzeW5jICgpID0+IHtcbiAgICAgIChjYWxlbmRhclNraWxscy5saXN0VXBjb21pbmdFdmVudHMgYXMgamVzdC5Nb2NrKS5tb2NrUmVqZWN0ZWRWYWx1ZShcbiAgICAgICAgbmV3IEVycm9yKCdUZXN0IEVycm9yJylcbiAgICAgICk7XG5cbiAgICAgIGNvbnN0IHJlc3VsdCA9IGF3YWl0IGhhbmRsZVNsYWNrTXlBZ2VuZGEoJ3Rlc3QtdXNlcicsIHt9KTtcblxuICAgICAgZXhwZWN0KHJlc3VsdCkudG9CZShcbiAgICAgICAgJ1NvcnJ5LCBhbiBlcnJvciBvY2N1cnJlZCB3aGlsZSBwcm9jZXNzaW5nIHlvdXIgYWdlbmRhIGZvciBTbGFjayAoTkxVIHBhdGgpLidcbiAgICAgICk7XG4gICAgfSk7XG4gIH0pO1xufSk7XG4iXX0=