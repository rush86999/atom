import { handleListGoogleMeetEvents, handleGetGoogleMeetEventDetails, } from '../googleMeet';
import * as calendarSkills from '../calendarSkills';
jest.mock('../calendarSkills', () => ({
    listUpcomingGoogleMeetEvents: jest.fn(),
    getGoogleMeetEventDetails: jest.fn(),
}));
describe('googleMeet skill', () => {
    afterEach(() => {
        jest.clearAllMocks();
    });
    describe('handleListGoogleMeetEvents', () => {
        it('should return a list of Google Meet events', async () => {
            const mockResponse = {
                ok: true,
                events: [
                    {
                        summary: 'Test Meet Event 1',
                        startTime: new Date().toISOString(),
                        conferenceData: {
                            entryPoints: [
                                {
                                    entryPointType: 'video',
                                    uri: 'https://meet.google.com/123',
                                },
                            ],
                        },
                    },
                ],
            };
            calendarSkills.listUpcomingGoogleMeetEvents.mockResolvedValue(mockResponse);
            const result = await handleListGoogleMeetEvents('test-user', {});
            expect(result).toContain('Your Upcoming Google Meet Events (via NLU):');
            expect(result).toContain('Test Meet Event 1');
        });
        it('should return a message when there are no events', async () => {
            calendarSkills.listUpcomingGoogleMeetEvents.mockResolvedValue({
                ok: true,
                events: [],
            });
            const result = await handleListGoogleMeetEvents('test-user', {});
            expect(result).toBe('No upcoming Google Meet events found (via NLU).');
        });
        it('should return an error message when an error occurs', async () => {
            calendarSkills.listUpcomingGoogleMeetEvents.mockRejectedValue(new Error('Test Error'));
            const result = await handleListGoogleMeetEvents('test-user', {});
            expect(result).toBe('Sorry, an unexpected error occurred while fetching your Google Meet events (NLU path).');
        });
    });
    describe('handleGetGoogleMeetEventDetails', () => {
        it('should return the details of a Google Meet event', async () => {
            const mockResponse = {
                ok: true,
                event: {
                    summary: 'Test Meet Event 1',
                    startTime: new Date().toISOString(),
                    endTime: new Date().toISOString(),
                    conferenceData: {
                        entryPoints: [
                            {
                                entryPointType: 'video',
                                uri: 'https://meet.google.com/123',
                            },
                        ],
                    },
                },
            };
            calendarSkills.getGoogleMeetEventDetails.mockResolvedValue(mockResponse);
            const result = await handleGetGoogleMeetEventDetails('test-user', {
                event_id: '123',
            });
            expect(result).toContain('Event (via NLU): Test Meet Event 1');
        });
        it('should return an error message when the event ID is missing', async () => {
            const result = await handleGetGoogleMeetEventDetails('test-user', {});
            expect(result).toBe('Google Calendar Event ID is required to get details via NLU.');
        });
        it('should return an error message when an error occurs', async () => {
            calendarSkills.getGoogleMeetEventDetails.mockRejectedValue(new Error('Test Error'));
            const result = await handleGetGoogleMeetEventDetails('test-user', {
                event_id: '123',
            });
            expect(result).toBe('Sorry, an unexpected error occurred while fetching details for event 123 (NLU path).');
        });
    });
});
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiZ29vZ2xlTWVldC50ZXN0LmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsiZ29vZ2xlTWVldC50ZXN0LnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiJBQUFBLE9BQU8sRUFDTCwwQkFBMEIsRUFDMUIsK0JBQStCLEdBQ2hDLE1BQU0sZUFBZSxDQUFDO0FBQ3ZCLE9BQU8sS0FBSyxjQUFjLE1BQU0sbUJBQW1CLENBQUM7QUFFcEQsSUFBSSxDQUFDLElBQUksQ0FBQyxtQkFBbUIsRUFBRSxHQUFHLEVBQUUsQ0FBQyxDQUFDO0lBQ3BDLDRCQUE0QixFQUFFLElBQUksQ0FBQyxFQUFFLEVBQUU7SUFDdkMseUJBQXlCLEVBQUUsSUFBSSxDQUFDLEVBQUUsRUFBRTtDQUNyQyxDQUFDLENBQUMsQ0FBQztBQUVKLFFBQVEsQ0FBQyxrQkFBa0IsRUFBRSxHQUFHLEVBQUU7SUFDaEMsU0FBUyxDQUFDLEdBQUcsRUFBRTtRQUNiLElBQUksQ0FBQyxhQUFhLEVBQUUsQ0FBQztJQUN2QixDQUFDLENBQUMsQ0FBQztJQUVILFFBQVEsQ0FBQyw0QkFBNEIsRUFBRSxHQUFHLEVBQUU7UUFDMUMsRUFBRSxDQUFDLDRDQUE0QyxFQUFFLEtBQUssSUFBSSxFQUFFO1lBQzFELE1BQU0sWUFBWSxHQUFHO2dCQUNuQixFQUFFLEVBQUUsSUFBSTtnQkFDUixNQUFNLEVBQUU7b0JBQ047d0JBQ0UsT0FBTyxFQUFFLG1CQUFtQjt3QkFDNUIsU0FBUyxFQUFFLElBQUksSUFBSSxFQUFFLENBQUMsV0FBVyxFQUFFO3dCQUNuQyxjQUFjLEVBQUU7NEJBQ2QsV0FBVyxFQUFFO2dDQUNYO29DQUNFLGNBQWMsRUFBRSxPQUFPO29DQUN2QixHQUFHLEVBQUUsNkJBQTZCO2lDQUNuQzs2QkFDRjt5QkFDRjtxQkFDRjtpQkFDRjthQUNGLENBQUM7WUFFQSxjQUFjLENBQUMsNEJBQ2hCLENBQUMsaUJBQWlCLENBQUMsWUFBWSxDQUFDLENBQUM7WUFFbEMsTUFBTSxNQUFNLEdBQUcsTUFBTSwwQkFB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QyxDQUFDLENBQUM7QUFDTCxDQUFDLENBQUMsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7XG4gIGhhbmRsZUxpc3RHb29nbGVNZWV0RXZlbnRzLFxuICBoYW5kbGVHZXRHb29nbGVNZWV0RXZlbnREZXRhaWxzLFxufSBmcm9tICcuLi9nb29nbGVNZWV0JztcbmltcG9ydCAqIGFzIGNhbGVuZGFyU2tpbGxzIGZyb20gJy4uL2NhbGVuZGFyU2tpbGxzJztcblxuamVzdC5tb2NrKCcuLi9jYWxlbmRhclNraWxscycsICgpID0+ICh7XG4gIGxpc3RVcGNvbWluZ0dvb2dsZU1lZXRFdmVudHM6IGplc3QuZm4oKSxcbiAgZ2V0R29vZ2xlTWVldEV2ZW50RGV0YWlsczogamVzdC5mbigpLFxufSkpO1xuXG5kZXNjcmliZSgnZ29vZ2xlTWVldCBza2lsbCcsICgpID0+IHtcbiAgYWZ0ZXJFYWNoKCgpID0+IHtcbiAgICBqZXN0LmNsZWFyQWxsTW9ja3MoKTtcbiAgfSk7XG5cbiAgZGVzY3JpYmUoJ2hhbmRsZUxpc3RHb29nbGVNZWV0RXZlbnRzJywgKCkgPT4ge1xuICAgIGl0KCdzaG91bGQgcmV0dXJuIGEgbGlzdCBvZiBHb29nbGUgTWVldCBldmVudHMnLCBhc3luYyAoKSA9PiB7XG4gICAgICBjb25zdCBtb2NrUmVzcG9uc2UgPSB7XG4gICAgICAgIG9rOiB0cnVlLFxuICAgICAgICBldmVudHM6IFtcbiAgICAgICAgICB7XG4gICAgICAgICAgICBzdW1tYXJ5OiAnVGVzdCBNZWV0IEV2ZW50IDEnLFxuICAgICAgICAgICAgc3RhcnRUaW1lOiBuZXcgRGF0ZSgpLnRvSVNPU3RyaW5nKCksXG4gICAgICAgICAgICBjb25mZXJlbmNlRGF0YToge1xuICAgICAgICAgICAgICBlbnRyeVBvaW50czogW1xuICAgICAgICAgICAgICAgIHtcbiAgICAgICAgICAgICAgICAgIGVudHJ5UG9pbnRUeXBlOiAndmlkZW8nLFxuICAgICAgICAgICAgICAgICAgdXJpOiAnaHR0cHM6Ly9tZWV0Lmdvb2dsZS5jb20vMTIzJyxcbiAgICAgICAgICAgICAgICB9LFxuICAgICAgICAgICAgICBdLFxuICAgICAgICAgICAgfSxcbiAgICAgICAgICB9LFxuICAgICAgICBdLFxuICAgICAgfTtcbiAgICAgIChcbiAgICAgICAgY2FsZW5kYXJTa2lsbHMubGlzdFVwY29taW5nR29vZ2xlTWVldEV2ZW50cyBhcyBqZXN0Lk1vY2tcbiAgICAgICkubW9ja1Jlc29sdmVkVmFsdWUobW9ja1Jlc3BvbnNlKTtcblxuICAgICAgY29uc3QgcmVzdWx0ID0gYXdhaXQgaGFuZGxlTGlzdEdvb2dsZU1lZXRFdmVudHMoJ3Rlc3QtdXNlcicsIHt9KTtcblxuICAgICAgZXhwZWN0KHJlc3VsdCkudG9Db250YWluKCdZb3VyIFVwY29taW5nIEdvb2dsZSBNZWV0IEV2ZW50cyAodmlhIE5MVSk6Jyk7XG4gICAgICBleHBlY3QocmVzdWx0KS50b0NvbnRhaW4oJ1Rlc3QgTWVldCBFdmVudCAxJyk7XG4gICAgfSk7XG5cbiAgICBpdCgnc2hvdWxkIHJldHVybiBhIG1lc3NhZ2Ugd2hlbiB0aGVyZSBhcmUgbm8gZXZlbnRzJywgYXN5bmMgKCkgPT4ge1xuICAgICAgKFxuICAgICAgICBjYWxlbmRhclNraWxscy5saXN0VXBjb21pbmdHb29nbGVNZWV0RXZlbnRzIGFzIGplc3QuTW9ja1xuICAgICAgKS5tb2NrUmVzb2x2ZWRWYWx1ZSh7XG4gICAgICAgIG9rOiB0cnVlLFxuICAgICAgICBldmVudHM6IFtdLFxuICAgICAgfSk7XG5cbiAgICAgIGNvbnN0IHJlc3VsdCA9IGF3YWl0IGhhbmRsZUxpc3RHb29nbGVNZWV0RXZlbnRzKCd0ZXN0LXVzZXInLCB7fSk7XG5cbiAgICAgIGV4cGVjdChyZXN1bHQpLnRvQmUoJ05vIHVwY29taW5nIEdvb2dsZSBNZWV0IGV2ZW50cyBmb3VuZCAodmlhIE5MVSkuJyk7XG4gICAgfSk7XG5cbiAgICBpdCgnc2hvdWxkIHJldHVybiBhbiBlcnJvciBtZXNzYWdlIHdoZW4gYW4gZXJyb3Igb2NjdXJzJywgYXN5bmMgKCkgPT4ge1xuICAgICAgKFxuICAgICAgICBjYWxlbmRhclNraWxscy5saXN0VXBjb21pbmdHb29nbGVNZWV0RXZlbnRzIGFzIGplc3QuTW9ja1xuICAgICAgKS5tb2NrUmVqZWN0ZWRWYWx1ZShuZXcgRXJyb3IoJ1Rlc3QgRXJyb3InKSk7XG5cbiAgICAgIGNvbnN0IHJlc3VsdCA9IGF3YWl0IGhhbmRsZUxpc3RHb29nbGVNZWV0RXZlbnRzKCd0ZXN0LXVzZXInLCB7fSk7XG5cbiAgICAgIGV4cGVjdChyZXN1bHQpLnRvQmUoXG4gICAgICAgICdTb3JyeSwgYW4gdW5leHBlY3RlZCBlcnJvciBvY2N1cnJlZCB3aGlsZSBmZXRjaGluZyB5b3VyIEdvb2dsZSBNZWV0IGV2ZW50cyAoTkxVIHBhdGgpLidcbiAgICAgICk7XG4gICAgfSk7XG4gIH0pO1xuXG4gIGRlc2NyaWJlKCdoYW5kbGVHZXRHb29nbGVNZWV0RXZlbnREZXRhaWxzJywgKCkgPT4ge1xuICAgIGl0KCdzaG91bGQgcmV0dXJuIHRoZSBkZXRhaWxzIG9mIGEgR29vZ2xlIE1lZXQgZXZlbnQnLCBhc3luYyAoKSA9PiB7XG4gICAgICBjb25zdCBtb2NrUmVzcG9uc2UgPSB7XG4gICAgICAgIG9rOiB0cnVlLFxuICAgICAgICBldmVudDoge1xuICAgICAgICAgIHN1bW1hcnk6ICdUZXN0IE1lZXQgRXZlbnQgMScsXG4gICAgICAgICAgc3RhcnRUaW1lOiBuZXcgRGF0ZSgpLnRvSVNPU3RyaW5nKCksXG4gICAgICAgICAgZW5kVGltZTogbmV3IERhdGUoKS50b0lTT1N0cmluZygpLFxuICAgICAgICAgIGNvbmZlcmVuY2VEYXRhOiB7XG4gICAgICAgICAgICBlbnRyeVBvaW50czogW1xuICAgICAgICAgICAgICB7XG4gICAgICAgICAgICAgICAgZW50cnlQb2ludFR5cGU6ICd2aWRlbycsXG4gICAgICAgICAgICAgICAgdXJpOiAnaHR0cHM6Ly9tZWV0Lmdvb2dsZS5jb20vMTIzJyxcbiAgICAgICAgICAgICAgfSxcbiAgICAgICAgICAgIF0sXG4gICAgICAgICAgfSxcbiAgICAgICAgfSxcbiAgICAgIH07XG4gICAgICAoY2FsZW5kYXJTa2lsbHMuZ2V0R29vZ2xlTWVldEV2ZW50RGV0YWlscyBhcyBqZXN0Lk1vY2spLm1vY2tSZXNvbHZlZFZhbHVlKFxuICAgICAgICBtb2NrUmVzcG9uc2VcbiAgICAgICk7XG5cbiAgICAgIGNvbnN0IHJlc3VsdCA9IGF3YWl0IGhhbmRsZUdldEdvb2dsZU1lZXRFdmVudERldGFpbHMoJ3Rlc3QtdXNlcicsIHtcbiAgICAgICAgZXZlbnRfaWQ6ICcxMjMnLFxuICAgICAgfSk7XG5cbiAgICAgIGV4cGVjdChyZXN1bHQpLnRvQ29udGFpbignRXZlbnQgKHZpYSBOTFUpOiBUZXN0IE1lZXQgRXZlbnQgMScpO1xuICAgIH0pO1xuXG4gICAgaXQoJ3Nob3VsZCByZXR1cm4gYW4gZXJyb3IgbWVzc2FnZSB3aGVuIHRoZSBldmVudCBJRCBpcyBtaXNzaW5nJywgYXN5bmMgKCkgPT4ge1xuICAgICAgY29uc3QgcmVzdWx0ID0gYXdhaXQgaGFuZGxlR2V0R29vZ2xlTWVldEV2ZW50RGV0YWlscygndGVzdC11c2VyJywge30pO1xuXG4gICAgICBleHBlY3QocmVzdWx0KS50b0JlKFxuICAgICAgICAnR29vZ2xlIENhbGVuZGFyIEV2ZW50IElEIGlzIHJlcXVpcmVkIHRvIGdldCBkZXRhaWxzIHZpYSBOTFUuJ1xuICAgICAgKTtcbiAgICB9KTtcblxuICAgIGl0KCdzaG91bGQgcmV0dXJuIGFuIGVycm9yIG1lc3NhZ2Ugd2hlbiBhbiBlcnJvciBvY2N1cnMnLCBhc3luYyAoKSA9PiB7XG4gICAgICAoY2FsZW5kYXJTa2lsbHMuZ2V0R29vZ2xlTWVldEV2ZW50RGV0YWlscyBhcyBqZXN0Lk1vY2spLm1vY2tSZWplY3RlZFZhbHVlKFxuICAgICAgICBuZXcgRXJyb3IoJ1Rlc3QgRXJyb3InKVxuICAgICAgKTtcblxuICAgICAgY29uc3QgcmVzdWx0ID0gYXdhaXQgaGFuZGxlR2V0R29vZ2xlTWVldEV2ZW50RGV0YWlscygndGVzdC11c2VyJywge1xuICAgICAgICBldmVudF9pZDogJzEyMycsXG4gICAgICB9KTtcblxuICAgICAgZXhwZWN0KHJlc3VsdCkudG9CZShcbiAgICAgICAgJ1NvcnJ5LCBhbiB1bmV4cGVjdGVkIGVycm9yIG9jY3VycmVkIHdoaWxlIGZldGNoaW5nIGRldGFpbHMgZm9yIGV2ZW50IDEyMyAoTkxVIHBhdGgpLidcbiAgICAgICk7XG4gICAgfSk7XG4gIH0pO1xufSk7XG4iXX0=