import { handleListZoomMeetings, handleGetZoomMeetingDetails } from '../zoom';
import * as zoomSkills from '../zoomSkills';
jest.mock('../zoomSkills', () => ({
    listZoomMeetings: jest.fn(),
    getZoomMeetingDetails: jest.fn(),
}));
describe('zoom skill', () => {
    afterEach(() => {
        jest.clearAllMocks();
    });
    describe('handleListZoomMeetings', () => {
        it('should return a list of Zoom meetings', async () => {
            const mockResponse = {
                ok: true,
                meetings: [
                    {
                        topic: 'Test Meeting 1',
                        id: '123',
                        start_time: new Date().toISOString(),
                        join_url: 'https://example.com/join/1',
                    },
                ],
            };
            zoomSkills.listZoomMeetings.mockResolvedValue(mockResponse);
            const result = await handleListZoomMeetings('test-user', {});
            expect(result).toContain('Your Zoom Meetings (upcoming, via NLU):');
            expect(result).toContain('Test Meeting 1');
        });
        it('should return a message when there are no meetings', async () => {
            zoomSkills.listZoomMeetings.mockResolvedValue({
                ok: true,
                meetings: [],
            });
            const result = await handleListZoomMeetings('test-user', {});
            expect(result).toBe('No Zoom meetings found matching your criteria (via NLU).');
        });
        it('should return an error message when an error occurs', async () => {
            zoomSkills.listZoomMeetings.mockRejectedValue(new Error('Test Error'));
            const result = await handleListZoomMeetings('test-user', {});
            expect(result).toBe('Sorry, an unexpected error occurred while fetching your Zoom meetings (NLU path).');
        });
    });
    describe('handleGetZoomMeetingDetails', () => {
        it('should return the details of a Zoom meeting', async () => {
            const mockResponse = {
                ok: true,
                meeting: {
                    topic: 'Test Meeting 1',
                    id: '123',
                    start_time: new Date().toISOString(),
                    duration: 60,
                    join_url: 'https://example.com/join/1',
                    agenda: 'Test Agenda',
                },
            };
            zoomSkills.getZoomMeetingDetails.mockResolvedValue(mockResponse);
            const result = await handleGetZoomMeetingDetails('test-user', {
                meeting_id: '123',
            });
            expect(result).toContain('Zoom Meeting Details (via NLU):');
            expect(result).toContain('Test Meeting 1');
        });
        it('should return an error message when the meeting ID is missing', async () => {
            const result = await handleGetZoomMeetingDetails('test-user', {});
            expect(result).toBe('Zoom Meeting ID is required to get details via NLU.');
        });
        it('should return an error message when an error occurs', async () => {
            zoomSkills.getZoomMeetingDetails.mockRejectedValue(new Error('Test Error'));
            const result = await handleGetZoomMeetingDetails('test-user', {
                meeting_id: '123',
            });
            expect(result).toBe('Sorry, an unexpected error occurred while fetching details for Zoom meeting 123 (NLU path).');
        });
    });
});
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiem9vbS50ZXN0LmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsiem9vbS50ZXN0LnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiJBQUFBLE9BQU8sRUFBRSxzQkFBc0IsRUFBRSwyQkFBMkIsRUFBRSxNQUFNLFNBQVMsQ0FBQztBQUM5RSxPQUFPLEtBQUssVUFBVSxNQUFNLGVBQWUsQ0FBQztBQUU1QyxJQUFJLENBQUMsSUFBSSxDQUFDLGVBQWUsRUFBRSxHQUFHLEVBQUUsQ0FBQyxDQUFDO0lBQ2hDLGdCQUFnQixFQUFFLElBQUksQ0FBQyxFQUFFLEVBQUU7SUFDM0IscUJBQXFCLEVBQUUsSUFBSSxDQUFDLEVBQUUsRUFBRTtDQUNqQyxDQUFDLENBQUMsQ0FBQztBQUVKLFFBQVEsQ0FBQyxZQUFZLEVBQUUsR0FBRyxFQUFFO0lBQzFCLFNBQVMsQ0FBQyxHQUFHLEVBQUU7UUFDYixJQUFJLENBQUMsYUFBYSxFQUFFLENBQUM7SUFDdkIsQ0FBQyxDQUFDLENBQUM7SUFFSCxRQUFRLENBQUMsd0JBQXdCLEVBQUUsR0FBRyxFQUFFO1FBQ3RDLEVBQUUsQ0FBQyx1Q0FBdUMsRUFBRSxLQUFLLElBQUksRUFBRTtZQUNyRCxNQUFNLFlBQVksR0FBRztnQkFDbkIsRUFBRSxFQUFFLElBQUk7Z0JBQ1IsUUFBUSxFQUFFO29CQUNSO3dCQUNFLEtBQUssRUFBRSxnQkFBZ0I7d0JBQ3ZCLEVBQUUsRUFBRSxLQUFLO3dCQUNULFVBQVUsRUFBRSxJQUFJLElBQUksRUFBRSxDQUFDLFdBQVcsRUFBRTt3QkFDcEMsUUFBUSxFQUFFLDRCQUE0QjtxQkFDdkM7aUJBQ0Y7YUFDRixDQUFDO1lBQ0QsVUFBVSxDQUFDLGdCQUE4QixDQUFDLGlCQUFpQixDQUMxRCxZQUFZLENBQ2IsQ0FBQztZQUVGLE1BQU0sTUFBTSxHQUFHLE1BQU0sc0JBQXNCLENBQUMsV0FBVyxFQUFFLEVBQUUsQ0FBQyxDQUFDO1lBRTdELE1BQU0sQ0FBQyxNQUFNLENBQUMsQ0FBQyxTQUFTLENBQUMseUNB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dGluZ3MsIGhhbmRsZUdldFpvb21NZWV0aW5nRGV0YWlscyB9IGZyb20gJy4uL3pvb20nO1xuaW1wb3J0ICogYXMgem9vbVNraWxscyBmcm9tICcuLi96b29tU2tpbGxzJztcblxuamVzdC5tb2NrKCcuLi96b29tU2tpbGxzJywgKCkgPT4gKHtcbiAgbGlzdFpvb21NZWV0aW5nczogamVzdC5mbigpLFxuICBnZXRab29tTWVldGluZ0RldGFpbHM6IGplc3QuZm4oKSxcbn0pKTtcblxuZGVzY3JpYmUoJ3pvb20gc2tpbGwnLCAoKSA9PiB7XG4gIGFmdGVyRWFjaCgoKSA9PiB7XG4gICAgamVzdC5jbGVhckFsbE1vY2tzKCk7XG4gIH0pO1xuXG4gIGRlc2NyaWJlKCdoYW5kbGVMaXN0Wm9vbU1lZXRpbmdzJywgKCkgPT4ge1xuICAgIGl0KCdzaG91bGQgcmV0dXJuIGEgbGlzdCBvZiBab29tIG1lZXRpbmdzJywgYXN5bmMgKCkgPT4ge1xuICAgICAgY29uc3QgbW9ja1Jlc3BvbnNlID0ge1xuICAgICAgICBvazogdHJ1ZSxcbiAgICAgICAgbWVldGluZ3M6IFtcbiAgICAgICAgICB7XG4gICAgICAgICAgICB0b3BpYzogJ1Rlc3QgTWVldGluZyAxJyxcbiAgICAgICAgICAgIGlkOiAnMTIzJyxcbiAgICAgICAgICAgIHN0YXJ0X3RpbWU6IG5ldyBEYXRlKCkudG9JU09TdHJpbmcoKSxcbiAgICAgICAgICAgIGpvaW5fdXJsOiAnaHR0cHM6Ly9leGFtcGxlLmNvbS9qb2luLzEnLFxuICAgICAgICAgIH0sXG4gICAgICAgIF0sXG4gICAgICB9O1xuICAgICAgKHpvb21Ta2lsbHMubGlzdFpvb21NZWV0aW5ncyBhcyBqZXN0Lk1vY2spLm1vY2tSZXNvbHZlZFZhbHVlKFxuICAgICAgICBtb2NrUmVzcG9uc2VcbiAgICAgICk7XG5cbiAgICAgIGNvbnN0IHJlc3VsdCA9IGF3YWl0IGhhbmRsZUxpc3Rab29tTWVldGluZ3MoJ3Rlc3QtdXNlcicsIHt9KTtcblxuICAgICAgZXhwZWN0KHJlc3VsdCkudG9Db250YWluKCdZb3VyIFpvb20gTWVldGluZ3MgKHVwY29taW5nLCB2aWEgTkxVKTonKTtcbiAgICAgIGV4cGVjdChyZXN1bHQpLnRvQ29udGFpbignVGVzdCBNZWV0aW5nIDEnKTtcbiAgICB9KTtcblxuICAgIGl0KCdzaG91bGQgcmV0dXJuIGEgbWVzc2FnZSB3aGVuIHRoZXJlIGFyZSBubyBtZWV0aW5ncycsIGFzeW5jICgpID0+IHtcbiAgICAgICh6b29tU2tpbGxzLmxpc3Rab29tTWVldGluZ3MgYXMgamVzdC5Nb2NrKS5tb2NrUmVzb2x2ZWRWYWx1ZSh7XG4gICAgICAgIG9rOiB0cnVlLFxuICAgICAgICBtZWV0aW5nczogW10sXG4gICAgICB9KTtcblxuICAgICAgY29uc3QgcmVzdWx0ID0gYXdhaXQgaGFuZGxlTGlzdFpvb21NZWV0aW5ncygndGVzdC11c2VyJywge30pO1xuXG4gICAgICBleHBlY3QocmVzdWx0KS50b0JlKFxuICAgICAgICAnTm8gWm9vbSBtZWV0aW5ncyBmb3VuZCBtYXRjaGluZyB5b3VyIGNyaXRlcmlhICh2aWEgTkxVKS4nXG4gICAgICApO1xuICAgIH0pO1xuXG4gICAgaXQoJ3Nob3VsZCByZXR1cm4gYW4gZXJyb3IgbWVzc2FnZSB3aGVuIGFuIGVycm9yIG9jY3VycycsIGFzeW5jICgpID0+IHtcbiAgICAgICh6b29tU2tpbGxzLmxpc3Rab29tTWVldGluZ3MgYXMgamVzdC5Nb2NrKS5tb2NrUmVqZWN0ZWRWYWx1ZShcbiAgICAgICAgbmV3IEVycm9yKCdUZXN0IEVycm9yJylcbiAgICAgICk7XG5cbiAgICAgIGNvbnN0IHJlc3VsdCA9IGF3YWl0IGhhbmRsZUxpc3Rab29tTWVldGluZ3MoJ3Rlc3QtdXNlcicsIHt9KTtcblxuICAgICAgZXhwZWN0KHJlc3VsdCkudG9CZShcbiAgICAgICAgJ1NvcnJ5LCBhbiB1bmV4cGVjdGVkIGVycm9yIG9jY3VycmVkIHdoaWxlIGZldGNoaW5nIHlvdXIgWm9vbSBtZWV0aW5ncyAoTkxVIHBhdGgpLidcbiAgICAgICk7XG4gICAgfSk7XG4gIH0pO1xuXG4gIGRlc2NyaWJlKCdoYW5kbGVHZXRab29tTWVldGluZ0RldGFpbHMnLCAoKSA9PiB7XG4gICAgaXQoJ3Nob3VsZCByZXR1cm4gdGhlIGRldGFpbHMgb2YgYSBab29tIG1lZXRpbmcnLCBhc3luYyAoKSA9PiB7XG4gICAgICBjb25zdCBtb2NrUmVzcG9uc2UgPSB7XG4gICAgICAgIG9rOiB0cnVlLFxuICAgICAgICBtZWV0aW5nOiB7XG4gICAgICAgICAgdG9waWM6ICdUZXN0IE1lZXRpbmcgMScsXG4gICAgICAgICAgaWQ6ICcxMjMnLFxuICAgICAgICAgIHN0YXJ0X3RpbWU6IG5ldyBEYXRlKCkudG9JU09TdHJpbmcoKSxcbiAgICAgICAgICBkdXJhdGlvbjogNjAsXG4gICAgICAgICAgam9pbl91cmw6ICdodHRwczovL2V4YW1wbGUuY29tL2pvaW4vMScsXG4gICAgICAgICAgYWdlbmRhOiAnVGVzdCBBZ2VuZGEnLFxuICAgICAgICB9LFxuICAgICAgfTtcbiAgICAgICh6b29tU2tpbGxzLmdldFpvb21NZWV0aW5nRGV0YWlscyBhcyBqZXN0Lk1vY2spLm1vY2tSZXNvbHZlZFZhbHVlKFxuICAgICAgICBtb2NrUmVzcG9uc2VcbiAgICAgICk7XG5cbiAgICAgIGNvbnN0IHJlc3VsdCA9IGF3YWl0IGhhbmRsZUdldFpvb21NZWV0aW5nRGV0YWlscygndGVzdC11c2VyJywge1xuICAgICAgICBtZWV0aW5nX2lkOiAnMTIzJyxcbiAgICAgIH0pO1xuXG4gICAgICBleHBlY3QocmVzdWx0KS50b0NvbnRhaW4oJ1pvb20gTWVldGluZyBEZXRhaWxzICh2aWEgTkxVKTonKTtcbiAgICAgIGV4cGVjdChyZXN1bHQpLnRvQ29udGFpbignVGVzdCBNZWV0aW5nIDEnKTtcbiAgICB9KTtcblxuICAgIGl0KCdzaG91bGQgcmV0dXJuIGFuIGVycm9yIG1lc3NhZ2Ugd2hlbiB0aGUgbWVldGluZyBJRCBpcyBtaXNzaW5nJywgYXN5bmMgKCkgPT4ge1xuICAgICAgY29uc3QgcmVzdWx0ID0gYXdhaXQgaGFuZGxlR2V0Wm9vbU1lZXRpbmdEZXRhaWxzKCd0ZXN0LXVzZXInLCB7fSk7XG5cbiAgICAgIGV4cGVjdChyZXN1bHQpLnRvQmUoXG4gICAgICAgICdab29tIE1lZXRpbmcgSUQgaXMgcmVxdWlyZWQgdG8gZ2V0IGRldGFpbHMgdmlhIE5MVS4nXG4gICAgICApO1xuICAgIH0pO1xuXG4gICAgaXQoJ3Nob3VsZCByZXR1cm4gYW4gZXJyb3IgbWVzc2FnZSB3aGVuIGFuIGVycm9yIG9jY3VycycsIGFzeW5jICgpID0+IHtcbiAgICAgICh6b29tU2tpbGxzLmdldFpvb21NZWV0aW5nRGV0YWlscyBhcyBqZXN0Lk1vY2spLm1vY2tSZWplY3RlZFZhbHVlKFxuICAgICAgICBuZXcgRXJyb3IoJ1Rlc3QgRXJyb3InKVxuICAgICAgKTtcblxuICAgICAgY29uc3QgcmVzdWx0ID0gYXdhaXQgaGFuZGxlR2V0Wm9vbU1lZXRpbmdEZXRhaWxzKCd0ZXN0LXVzZXInLCB7XG4gICAgICAgIG1lZXRpbmdfaWQ6ICcxMjMnLFxuICAgICAgfSk7XG5cbiAgICAgIGV4cGVjdChyZXN1bHQpLnRvQmUoXG4gICAgICAgICdTb3JyeSwgYW4gdW5leHBlY3RlZCBlcnJvciBvY2N1cnJlZCB3aGlsZSBmZXRjaGluZyBkZXRhaWxzIGZvciBab29tIG1lZXRpbmcgMTIzIChOTFUgcGF0aCkuJ1xuICAgICAgKTtcbiAgICB9KTtcbiAgfSk7XG59KTtcbiJdfQ==