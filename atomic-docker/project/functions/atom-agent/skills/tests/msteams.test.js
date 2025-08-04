import { handleListMicrosoftTeamsMeetings, handleGetMicrosoftTeamsMeetingDetails, } from '../msteams';
import * as msTeamsSkills from '../msTeamsSkills';
jest.mock('../msTeamsSkills', () => ({
    listMicrosoftTeamsMeetings: jest.fn(),
    getMicrosoftTeamsMeetingDetails: jest.fn(),
}));
describe('msteams skill', () => {
    afterEach(() => {
        jest.clearAllMocks();
    });
    describe('handleListMicrosoftTeamsMeetings', () => {
        it('should return a list of Microsoft Teams meetings', async () => {
            const mockResponse = {
                ok: true,
                events: [
                    {
                        subject: 'Test Teams Meeting 1',
                        id: '123',
                        start: { dateTime: new Date().toISOString() },
                        onlineMeeting: { joinUrl: 'https://example.com/join/1' },
                    },
                ],
            };
            msTeamsSkills.listMicrosoftTeamsMeetings.mockResolvedValue(mockResponse);
            const result = await handleListMicrosoftTeamsMeetings('test-user', {});
            expect(result).toContain('Your Microsoft Teams Meetings (via NLU):');
            expect(result).toContain('Test Teams Meeting 1');
        });
        it('should return a message when there are no meetings', async () => {
            msTeamsSkills.listMicrosoftTeamsMeetings.mockResolvedValue({
                ok: true,
                events: [],
            });
            const result = await handleListMicrosoftTeamsMeetings('test-user', {});
            expect(result).toBe('No Microsoft Teams meetings found matching your criteria (via NLU).');
        });
        it('should return an error message when an error occurs', async () => {
            msTeamsSkills.listMicrosoftTeamsMeetings.mockRejectedValue(new Error('Test Error'));
            const result = await handleListMicrosoftTeamsMeetings('test-user', {});
            expect(result).toBe('Sorry, an unexpected error occurred while fetching your Microsoft Teams meetings (NLU path).');
        });
    });
    describe('handleGetMicrosoftTeamsMeetingDetails', () => {
        it('should return the details of a Microsoft Teams meeting', async () => {
            const mockResponse = {
                ok: true,
                event: {
                    subject: 'Test Teams Meeting 1',
                    id: '123',
                    start: { dateTime: new Date().toISOString() },
                    end: { dateTime: new Date().toISOString() },
                    onlineMeeting: { joinUrl: 'https://example.com/join/1' },
                },
            };
            msTeamsSkills.getMicrosoftTeamsMeetingDetails.mockResolvedValue(mockResponse);
            const result = await handleGetMicrosoftTeamsMeetingDetails('test-user', {
                event_id: '123',
            });
            expect(result).toContain('Teams Meeting (via NLU): Test Teams Meeting 1');
        });
        it('should return an error message when the event ID is missing', async () => {
            const result = await handleGetMicrosoftTeamsMeetingDetails('test-user', {});
            expect(result).toBe('Microsoft Graph Event ID is required to get Teams meeting details via NLU.');
        });
        it('should return an error message when an error occurs', async () => {
            msTeamsSkills.getMicrosoftTeamsMeetingDetails.mockRejectedValue(new Error('Test Error'));
            const result = await handleGetMicrosoftTeamsMeetingDetails('test-user', {
                event_id: '123',
            });
            expect(result).toBe('Sorry, an unexpected error occurred while fetching details for Teams meeting 123 (NLU path).');
        });
    });
});
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoibXN0ZWFtcy50ZXN0LmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsibXN0ZWFtcy50ZXN0LnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiJBQUFBLE9BQU8sRUFDTCxnQ0FBZ0MsRUFDaEMscUNBQXFDLEdBQ3RDLE1BQU0sWUFBWSxDQUFDO0FBQ3BCLE9BQU8sS0FBSyxhQUFhLE1BQU0sa0JBQWtCLENBQUM7QUFFbEQsSUFBSSxDQUFDLElBQUksQ0FBQyxrQkFBa0IsRUFBRSxHQUFHLEVBQUUsQ0FBQyxDQUFDO0lBQ25DLDBCQUEwQixFQUFFLElBQUksQ0FBQyxFQUFFLEVBQUU7SUFDckMsK0JBQStCLEVBQUUsSUFBSSxDQUFDLEVBQUUsRUFBRTtDQUMzQyxDQUFDLENBQUMsQ0FBQztBQUVKLFFBQVEsQ0FBQyxlQUFlLEVBQUUsR0FBRyxFQUFFO0lBQzdCLFNBQVMsQ0FBQyxHQUFHLEVBQUU7UUFDYixJQUFJLENBQUMsYUFBYSxFQUFFLENBQUM7SUFDdkIsQ0FBQyxDQUFDLENBQUM7SUFFSCxRQUFRLENBQUMsa0NBQWtDLEVBQUUsR0FBRyxFQUFFO1FBQ2hELEVBQUUsQ0FBQyxrREFBa0QsRUFBRSxLQUFLLElBQUksRUFBRTtZQUNoRSxNQUFNLFlBQVksR0FBRztnQkFDbkIsRUFBRSxFQUFFLElBQUk7Z0JBQ1IsTUFBTSxFQUFFO29CQUNOO3dCQUNFLE9BQU8sRUFBRSxzQkFBc0I7d0JBQy9CLEVBQUUsRUFBRSxLQUFLO3dCQUNULEtBQUssRUFBRSxFQUFFLFFBQVEsRUFBRSxJQUFJLElBQUksRUFBRSxDQUFDLFdBQVcsRUFBRSxFQUFFO3dCQUM3QyxhQUFhLEVBQUUsRUFBRSxPQUFPLEVBQUUsNEJBQTRCLEVBQUU7cUJBQ3pEO2lCQUNGO2FBQ0YsQ0FBQztZQUNELGFBQWEsQ0FBQywwQkFBd0MsQ0FBQyxpQkFBaUIsQ0FDdkUsWUFBWSxDQUNiLENBQUM7WUFFRixNQUFNLE1BQU0sR0FBRyxNQUFNLGdDQUFnQyxDQUFDLFdBQVcsRUFBRSxFQUFFLENB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QUFDLENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQge1xuICBoYW5kbGVMaXN0TWljcm9zb2Z0VGVhbXNNZWV0aW5ncyxcbiAgaGFuZGxlR2V0TWljcm9zb2Z0VGVhbXNNZWV0aW5nRGV0YWlscyxcbn0gZnJvbSAnLi4vbXN0ZWFtcyc7XG5pbXBvcnQgKiBhcyBtc1RlYW1zU2tpbGxzIGZyb20gJy4uL21zVGVhbXNTa2lsbHMnO1xuXG5qZXN0Lm1vY2soJy4uL21zVGVhbXNTa2lsbHMnLCAoKSA9PiAoe1xuICBsaXN0TWljcm9zb2Z0VGVhbXNNZWV0aW5nczogamVzdC5mbigpLFxuICBnZXRNaWNyb3NvZnRUZWFtc01lZXRpbmdEZXRhaWxzOiBqZXN0LmZuKCksXG59KSk7XG5cbmRlc2NyaWJlKCdtc3RlYW1zIHNraWxsJywgKCkgPT4ge1xuICBhZnRlckVhY2goKCkgPT4ge1xuICAgIGplc3QuY2xlYXJBbGxNb2NrcygpO1xuICB9KTtcblxuICBkZXNjcmliZSgnaGFuZGxlTGlzdE1pY3Jvc29mdFRlYW1zTWVldGluZ3MnLCAoKSA9PiB7XG4gICAgaXQoJ3Nob3VsZCByZXR1cm4gYSBsaXN0IG9mIE1pY3Jvc29mdCBUZWFtcyBtZWV0aW5ncycsIGFzeW5jICgpID0+IHtcbiAgICAgIGNvbnN0IG1vY2tSZXNwb25zZSA9IHtcbiAgICAgICAgb2s6IHRydWUsXG4gICAgICAgIGV2ZW50czogW1xuICAgICAgICAgIHtcbiAgICAgICAgICAgIHN1YmplY3Q6ICdUZXN0IFRlYW1zIE1lZXRpbmcgMScsXG4gICAgICAgICAgICBpZDogJzEyMycsXG4gICAgICAgICAgICBzdGFydDogeyBkYXRlVGltZTogbmV3IERhdGUoKS50b0lTT1N0cmluZygpIH0sXG4gICAgICAgICAgICBvbmxpbmVNZWV0aW5nOiB7IGpvaW5Vcmw6ICdodHRwczovL2V4YW1wbGUuY29tL2pvaW4vMScgfSxcbiAgICAgICAgICB9LFxuICAgICAgICBdLFxuICAgICAgfTtcbiAgICAgIChtc1RlYW1zU2tpbGxzLmxpc3RNaWNyb3NvZnRUZWFtc01lZXRpbmdzIGFzIGplc3QuTW9jaykubW9ja1Jlc29sdmVkVmFsdWUoXG4gICAgICAgIG1vY2tSZXNwb25zZVxuICAgICAgKTtcblxuICAgICAgY29uc3QgcmVzdWx0ID0gYXdhaXQgaGFuZGxlTGlzdE1pY3Jvc29mdFRlYW1zTWVldGluZ3MoJ3Rlc3QtdXNlcicsIHt9KTtcblxuICAgICAgZXhwZWN0KHJlc3VsdCkudG9Db250YWluKCdZb3VyIE1pY3Jvc29mdCBUZWFtcyBNZWV0aW5ncyAodmlhIE5MVSk6Jyk7XG4gICAgICBleHBlY3QocmVzdWx0KS50b0NvbnRhaW4oJ1Rlc3QgVGVhbXMgTWVldGluZyAxJyk7XG4gICAgfSk7XG5cbiAgICBpdCgnc2hvdWxkIHJldHVybiBhIG1lc3NhZ2Ugd2hlbiB0aGVyZSBhcmUgbm8gbWVldGluZ3MnLCBhc3luYyAoKSA9PiB7XG4gICAgICAobXNUZWFtc1NraWxscy5saXN0TWljcm9zb2Z0VGVhbXNNZWV0aW5ncyBhcyBqZXN0Lk1vY2spLm1vY2tSZXNvbHZlZFZhbHVlKFxuICAgICAgICB7XG4gICAgICAgICAgb2s6IHRydWUsXG4gICAgICAgICAgZXZlbnRzOiBbXSxcbiAgICAgICAgfVxuICAgICAgKTtcblxuICAgICAgY29uc3QgcmVzdWx0ID0gYXdhaXQgaGFuZGxlTGlzdE1pY3Jvc29mdFRlYW1zTWVldGluZ3MoJ3Rlc3QtdXNlcicsIHt9KTtcblxuICAgICAgZXhwZWN0KHJlc3VsdCkudG9CZShcbiAgICAgICAgJ05vIE1pY3Jvc29mdCBUZWFtcyBtZWV0aW5ncyBmb3VuZCBtYXRjaGluZyB5b3VyIGNyaXRlcmlhICh2aWEgTkxVKS4nXG4gICAgICApO1xuICAgIH0pO1xuXG4gICAgaXQoJ3Nob3VsZCByZXR1cm4gYW4gZXJyb3IgbWVzc2FnZSB3aGVuIGFuIGVycm9yIG9jY3VycycsIGFzeW5jICgpID0+IHtcbiAgICAgIChtc1RlYW1zU2tpbGxzLmxpc3RNaWNyb3NvZnRUZWFtc01lZXRpbmdzIGFzIGplc3QuTW9jaykubW9ja1JlamVjdGVkVmFsdWUoXG4gICAgICAgIG5ldyBFcnJvcignVGVzdCBFcnJvcicpXG4gICAgICApO1xuXG4gICAgICBjb25zdCByZXN1bHQgPSBhd2FpdCBoYW5kbGVMaXN0TWljcm9zb2Z0VGVhbXNNZWV0aW5ncygndGVzdC11c2VyJywge30pO1xuXG4gICAgICBleHBlY3QocmVzdWx0KS50b0JlKFxuICAgICAgICAnU29ycnksIGFuIHVuZXhwZWN0ZWQgZXJyb3Igb2NjdXJyZWQgd2hpbGUgZmV0Y2hpbmcgeW91ciBNaWNyb3NvZnQgVGVhbXMgbWVldGluZ3MgKE5MVSBwYXRoKS4nXG4gICAgICApO1xuICAgIH0pO1xuICB9KTtcblxuICBkZXNjcmliZSgnaGFuZGxlR2V0TWljcm9zb2Z0VGVhbXNNZWV0aW5nRGV0YWlscycsICgpID0+IHtcbiAgICBpdCgnc2hvdWxkIHJldHVybiB0aGUgZGV0YWlscyBvZiBhIE1pY3Jvc29mdCBUZWFtcyBtZWV0aW5nJywgYXN5bmMgKCkgPT4ge1xuICAgICAgY29uc3QgbW9ja1Jlc3BvbnNlID0ge1xuICAgICAgICBvazogdHJ1ZSxcbiAgICAgICAgZXZlbnQ6IHtcbiAgICAgICAgICBzdWJqZWN0OiAnVGVzdCBUZWFtcyBNZWV0aW5nIDEnLFxuICAgICAgICAgIGlkOiAnMTIzJyxcbiAgICAgICAgICBzdGFydDogeyBkYXRlVGltZTogbmV3IERhdGUoKS50b0lTT1N0cmluZygpIH0sXG4gICAgICAgICAgZW5kOiB7IGRhdGVUaW1lOiBuZXcgRGF0ZSgpLnRvSVNPU3RyaW5nKCkgfSxcbiAgICAgICAgICBvbmxpbmVNZWV0aW5nOiB7IGpvaW5Vcmw6ICdodHRwczovL2V4YW1wbGUuY29tL2pvaW4vMScgfSxcbiAgICAgICAgfSxcbiAgICAgIH07XG4gICAgICAoXG4gICAgICAgIG1zVGVhbXNTa2lsbHMuZ2V0TWljcm9zb2Z0VGVhbXNNZWV0aW5nRGV0YWlscyBhcyBqZXN0Lk1vY2tcbiAgICAgICkubW9ja1Jlc29sdmVkVmFsdWUobW9ja1Jlc3BvbnNlKTtcblxuICAgICAgY29uc3QgcmVzdWx0ID0gYXdhaXQgaGFuZGxlR2V0TWljcm9zb2Z0VGVhbXNNZWV0aW5nRGV0YWlscygndGVzdC11c2VyJywge1xuICAgICAgICBldmVudF9pZDogJzEyMycsXG4gICAgICB9KTtcblxuICAgICAgZXhwZWN0KHJlc3VsdCkudG9Db250YWluKCdUZWFtcyBNZWV0aW5nICh2aWEgTkxVKTogVGVzdCBUZWFtcyBNZWV0aW5nIDEnKTtcbiAgICB9KTtcblxuICAgIGl0KCdzaG91bGQgcmV0dXJuIGFuIGVycm9yIG1lc3NhZ2Ugd2hlbiB0aGUgZXZlbnQgSUQgaXMgbWlzc2luZycsIGFzeW5jICgpID0+IHtcbiAgICAgIGNvbnN0IHJlc3VsdCA9IGF3YWl0IGhhbmRsZUdldE1pY3Jvc29mdFRlYW1zTWVldGluZ0RldGFpbHMoXG4gICAgICAgICd0ZXN0LXVzZXInLFxuICAgICAgICB7fVxuICAgICAgKTtcblxuICAgICAgZXhwZWN0KHJlc3VsdCkudG9CZShcbiAgICAgICAgJ01pY3Jvc29mdCBHcmFwaCBFdmVudCBJRCBpcyByZXF1aXJlZCB0byBnZXQgVGVhbXMgbWVldGluZyBkZXRhaWxzIHZpYSBOTFUuJ1xuICAgICAgKTtcbiAgICB9KTtcblxuICAgIGl0KCdzaG91bGQgcmV0dXJuIGFuIGVycm9yIG1lc3NhZ2Ugd2hlbiBhbiBlcnJvciBvY2N1cnMnLCBhc3luYyAoKSA9PiB7XG4gICAgICAoXG4gICAgICAgIG1zVGVhbXNTa2lsbHMuZ2V0TWljcm9zb2Z0VGVhbXNNZWV0aW5nRGV0YWlscyBhcyBqZXN0Lk1vY2tcbiAgICAgICkubW9ja1JlamVjdGVkVmFsdWUobmV3IEVycm9yKCdUZXN0IEVycm9yJykpO1xuXG4gICAgICBjb25zdCByZXN1bHQgPSBhd2FpdCBoYW5kbGVHZXRNaWNyb3NvZnRUZWFtc01lZXRpbmdEZXRhaWxzKCd0ZXN0LXVzZXInLCB7XG4gICAgICAgIGV2ZW50X2lkOiAnMTIzJyxcbiAgICAgIH0pO1xuXG4gICAgICBleHBlY3QocmVzdWx0KS50b0JlKFxuICAgICAgICAnU29ycnksIGFuIHVuZXhwZWN0ZWQgZXJyb3Igb2NjdXJyZWQgd2hpbGUgZmV0Y2hpbmcgZGV0YWlscyBmb3IgVGVhbXMgbWVldGluZyAxMjMgKE5MVSBwYXRoKS4nXG4gICAgICApO1xuICAgIH0pO1xuICB9KTtcbn0pO1xuIl19