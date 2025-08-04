import { handleGetCalendarEvents, handleCreateCalendarEvent, } from '../calendar';
import * as calendarSkills from '../calendarSkills';
jest.mock('../calendarSkills', () => ({
    listUpcomingEvents: jest.fn(),
    createCalendarEvent: jest.fn(),
}));
describe('calendar skill', () => {
    afterEach(() => {
        jest.clearAllMocks();
    });
    describe('handleGetCalendarEvents', () => {
        it('should return a list of upcoming events', async () => {
            const mockEvents = [
                {
                    summary: 'Test Event 1',
                    startTime: new Date().toISOString(),
                    endTime: new Date().toISOString(),
                },
                {
                    summary: 'Test Event 2',
                    startTime: new Date().toISOString(),
                    endTime: new Date().toISOString(),
                },
            ];
            calendarSkills.listUpcomingEvents.mockResolvedValue(mockEvents);
            const result = await handleGetCalendarEvents('test-user', {});
            expect(result).toContain('Upcoming calendar events:');
            expect(result).toContain('Test Event 1');
            expect(result).toContain('Test Event 2');
        });
        it('should return a message when there are no upcoming events', async () => {
            calendarSkills.listUpcomingEvents.mockResolvedValue([]);
            const result = await handleGetCalendarEvents('test-user', {});
            expect(result).toBe("No upcoming calendar events found matching your criteria, or I couldn't access them.");
        });
        it('should return an error message when an error occurs', async () => {
            calendarSkills.listUpcomingEvents.mockRejectedValue(new Error('Test Error'));
            const result = await handleGetCalendarEvents('test-user', {});
            expect(result).toBe("Sorry, I couldn't fetch your calendar events due to an error.");
        });
    });
    describe('handleCreateCalendarEvent', () => {
        it('should create a new calendar event', async () => {
            const mockEvent = {
                summary: 'Test Event',
                start_time: new Date().toISOString(),
                end_time: new Date().toISOString(),
            };
            calendarSkills.createCalendarEvent.mockResolvedValue({
                success: true,
                message: 'Event created successfully',
                eventId: 'test-event-id',
            });
            const result = await handleCreateCalendarEvent('test-user', mockEvent);
            expect(result).toContain('Event created: Event created successfully');
        });
        it('should return an error message when the summary is missing', async () => {
            const mockEvent = {
                start_time: new Date().toISOString(),
                end_time: new Date().toISOString(),
            };
            const result = await handleCreateCalendarEvent('test-user', mockEvent);
            expect(result).toBe('Event summary is required to create an event via NLU.');
        });
        it('should return an error message when the start time is missing', async () => {
            const mockEvent = {
                summary: 'Test Event',
                end_time: new Date().toISOString(),
            };
            const result = await handleCreateCalendarEvent('test-user', mockEvent);
            expect(result).toBe('Event start time is required to create an event via NLU.');
        });
        it('should return an error message when the end time and duration are missing', async () => {
            const mockEvent = {
                summary: 'Test Event',
                start_time: new Date().toISOString(),
            };
            const result = await handleCreateCalendarEvent('test-user', mockEvent);
            expect(result).toBe('Event end time or duration is required to create an event via NLU.');
        });
        it('should return an error message when an error occurs', async () => {
            const mockEvent = {
                summary: 'Test Event',
                start_time: new Date().toISOString(),
                end_time: new Date().toISOString(),
            };
            calendarSkills.createCalendarEvent.mockRejectedValue(new Error('Test Error'));
            const result = await handleCreateCalendarEvent('test-user', mockEvent);
            expect(result).toBe("Sorry, I couldn't create the calendar event due to an error.");
        });
    });
});
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiY2FsZW5kYXIudGVzdC5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImNhbGVuZGFyLnRlc3QudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6IkFBQUEsT0FBTyxFQUNMLHVCQUF1QixFQUN2Qix5QkFBeUIsR0FDMUIsTUFBTSxhQUFhLENBQUM7QUFDckIsT0FBTyxLQUFLLGNBQWMsTUFBTSxtQkFBbUIsQ0FBQztBQUVwRCxJQUFJLENBQUMsSUFBSSxDQUFDLG1CQUFtQixFQUFFLEdBQUcsRUFBRSxDQUFDLENBQUM7SUFDcEMsa0JBQWtCLEVBQUUsSUFBSSxDQUFDLEVBQUUsRUFBRTtJQUM3QixtQkFBbUIsRUFBRSxJQUFJLENBQUMsRUFBRSxFQUFFO0NBQy9CLENBQUMsQ0FBQyxDQUFDO0FBRUosUUFBUSxDQUFDLGdCQUFnQixFQUFFLEdBQUcsRUFBRTtJQUM5QixTQUFTLENBQUMsR0FBRyxFQUFFO1FBQ2IsSUFBSSxDQUFDLGFBQWEsRUFBRSxDQUFDO0lBQ3ZCLENBQUMsQ0FBQyxDQUFDO0lBRUgsUUFBUSxDQUFDLHlCQUF5QixFQUFFLEdBQUcsRUFBRTtRQUN2QyxFQUFFLENBQUMseUNBQXlDLEVBQUUsS0FBSyxJQUFJLEVBQUU7WUFDdkQsTUFBTSxVQUFVLEdBQUc7Z0JBQ2pCO29CQUNFLE9BQU8sRUFBRSxjQUFjO29CQUN2QixTQUFTLEVBQUUsSUFBSSxJQUFJLEVBQUUsQ0FBQyxXQUFXLEVBQUU7b0JBQ25DLE9BQU8sRUFBRSxJQUFJLElBQUksRUFBRSxDQUFDLFdBQVcsRUFBRTtpQkFDbEM7Z0JBQ0Q7b0JBQ0UsT0FBTyxFQUFFLGNBQWM7b0JBQ3ZCLFNBQVMsRUFBRSxJQUFJLElBQUksRUFBRSxDQUFDLFdBQVcsRUFBRTtvQkFDbkMsT0FBTyxFQUFFLElBQUksSUFBSSxFQUFFLENBQUMsV0FBVyxFQUFFO2lCQUNsQzthQUNGLENBQUM7WUFDRCxjQUFjLENBQUMsa0JBQWdDLENBQUMsaUJBQWlCLENBQ2hFLFVBQVUsQ0FDWCxDQUFDO1lBRUYsTUFBTSxNQUFNLEdBQUcsTUFBTSx1QkFBdUIsQ0FBQyxXQUFXLEVBQUUsRUFBRSxDQUFDLENBQUM7WUFFOUQsTUFBTSxDQUFDLE1BQU0sQ0FBQyxDQUFDLFNBQVMsQ0FBQywyQkFBMkIsQ0FBQyxDQUFDO1lBQ3RELE1BQU0sQ0FBQyxNQUFNLENBQUMsQ0FBQyxTQUFTLENBQUMsY0FBYyxDQUFDLENBQUM7WUFDekMsTUFBTSxDQUFDLE1BQU0sQ0FBQyxDQUFDLFNBQVMsQ0FBQyxjQUFjLENBQUMsQ0FBQztRQUMzQyxDQUFDLENBQUMsQ0FBQztRQUVILEVBQUUsQ0FBQywyREFBMkQsRUFBRSxLQUFLLElBQUksRUFBRTtZQUN4RSxjQUFjLENBQUMsa0JBQWdDLENBQUMsaUJBQWlCLENBQUMsRUFBRSxDQUFDLENBQUM7WUFFdkUsTUFBTSxNQUFNLEdBQUcsTUFBTSx1QkFBdUIsQ0FBQyxXQUFXLEVBQUUsRUFBRSxDQUFDLENBQUM7WUFFOUQsTUFBTSxDQUFDLE1BQU0sQ0FBQyxDQUFDLElBQUksQ0FDakIsc0ZBQXNGLENBQ3ZGLENBQUM7UUFDSixDQUFDLENBQUMsQ0FBQztRQUVILEVBQUUsQ0FBQyxxREFBcUQsRUFBRSxLQUFLLElBQUksRUFBRTtZQUNsRSxjQUFjLENBQUMsa0JBQWdDLENBQUMsaUJBQWlCLENBQ2hFLElBQUksS0FBSyxDQUFDLFlBQVksQ0FBQyxDQUN4QixDQUFDO1lBRUYsTUFBTSxNQUFNLEdBQUcsTUFBTSx1QkFBdUIsQ0FBQyxXQUFXLEVBQUUsRUFBRSxDQUFDLENBQUM7WUFFOUQsTUFBTSxDQUFDLE1BQU0sQ0FBQyxDQUFDLElBQUksQ0FDakIsK0RBQStELENBQ2hFLENBQUM7UUFDSixDQUFDLENBQUMsQ0FBQztJQUNMLENBQUMsQ0FBQyxDQUFDO0lBRUgsUUFBUSxDQUFDLDJCQUEyQixFQUFFLEdBQUcsRUFBRTtRQUN6QyxFQUFFLENBQUMsb0NBQW9DLEVBQUUsS0FBSyxJQUFJLEVBQUU7WUFDbEQsTUFBTSxTQUFTLEdBQUc7Z0JBQ2hCLE9BQU8sRUFBRSxZQUFZO2dCQUNyQixVQUFVLEVBQUUsSUFBSSxJQUFJLEVBQUUsQ0FBQyxXQUFXLEVBQUU7Z0JBQ3BDLFFBQVEsRUFBRSxJQUFJLElBQUksRUFBRSxDQUFDLFdBQVcsRUFBRTthQUNuQyxDQUFDO1lBQ0QsY0FBYyxDQUFDLG1CQUFpQyxDQUFDLGlCQUFpQixDQUFDO2dCQUNsRSxPQUFPLEVBQUUsSUFBSTtnQkFDYixPQUFPLEVBQUUsNEJBQTRCO2dCQUNyQyxPQUFPLEVBQUUsZUFBZTthQUN6QixDQUFDLENBQUM7WUFFSCxNQUFNLE1BQU0sR0FBRyxNQUFNLHlCQUF5QixDQUFDLFdBQVcsRUFBRSxTQUFTLENBQUMsQ0FBQztZQUV2RSxNQUFNLENBQUMsTUFBTSxDQUFDLENBQUMsU0FBUyxDQUFDLDJDQUEyQyxDQUFDLENBQUM7UUFDeEUsQ0FBQyxDQUFDLENBQUM7UUFFSCxFQUFFLENBQUMsNERBQTRELEVBQUUsS0FBSyxJQUFJLEVBQUU7WUFDMUUsTUFBTSxTQUFTLEdBQUc7Z0JBQ2hCLFVBQVUsRUFBRSxJQUFJLElBQUksRUFBRSxDQUFDLFdBQVcsRUFBRTtnQkFDcEMsUUFBUSxFQUFFLElBQUksSUFBSSxFQUFFLENBQUMsV0FBVyxFQUFFO2FBQ25DLENBQUM7WUFFRixNQUFNLE1BQU0sR0FBRyxNQUFNLHlCQUF5QixDQUFDLFdBQVcsRUFBRSxTQUFTLENBQUMsQ0FBQztZQUV2RSxNQUFNLENBQUMsTUFBTSxDQUFDLENBQUMsSUFBSSxDQUNqQix1REFBdUQsQ0FDeEQsQ0FBQztRQUNKLENBQUMsQ0FBQyxDQUFDO1FBRUgsRUFBRSxDQUFDLCtEQUErRCxFQUFFLEtBQUssSUFBSSxFQUFFO1lBQzdFLE1BQU0sU0FBUyxHQUFHO2dCQUNoQixPQUFPLEVBQUUsWUFBWTtnQkFDckIsUUFBUSxFQUFFLElBQUksSUFBSSxFQUFFLENBQUMsV0FBVyxFQUFFO2FBQ25DLENBQUM7WUFFRixNQUFNLE1BQU0sR0FBRyxNQUFNLHlCQUF5QixDQUFDLFdBQVcsRUFBRSxTQUFTLENBQUMsQ0FBQztZQUV2RSxNQUFNLENBQUMsTUFBTSxDQUFDLENBQUMsSUFBSSxDQUNqQiwwREFBMEQsQ0FDM0QsQ0FBQztRQUNKLENBQUMsQ0FBQyxDQUFDO1FBRUgsRUFBRSxDQUFDLDJFQUEyRSxFQUFFLEtBQUssSUFBSSxFQUFFO1lBQ3pGLE1BQU0sU0FBUyxHQUFHO2dCQUNoQixPQUFPLEVBQUUsWUFBWTtnQkFDckIsVUFBVSxFQUFFLElBQUksSUFBSSxFQUFFLENBQUMsV0FBVyxFQUFFO2FBQ3JDLENBQUM7WUFFRixNQUFNLE1BQU0sR0FBRyxNQUFNLHlCQUF5QixDQUFDLFdBQVcsRUFBRSxTQUFTLENBQUMsQ0FBQztZQUV2RSxNQUFNLENBQUMsTUFBTSxDQUFDLENBQUMsSUFBSSxDQUNqQixvRUFBb0UsQ0FDckUsQ0FBQztRQUNKLENBQUMsQ0FBQyxDQUFDO1FBRUgsRUFBRSxDQUFDLHFEQUFxRCxFQUFFLEtBQUssSUFBSSxFQUFFO1lBQ25FLE1BQU0sU0FBUyxHQUFHO2dCQUNoQixPQUFPLEVBQUUsWUFBWTtnQkFDckIsVUFBVSxFQUFFLElBQUksSUFBSSxFQUFFLENBQUMsV0FBVyxFQUFFO2dCQUNwQyxRQUFRLEVBQUUsSUFBSSxJQUFJLEVBQUUsQ0FBQyxXQUFXLEVBQUU7YUFDbkMsQ0FBQztZQUNELGNBQWMsQ0FBQyxtQkFBaUMsQ0FBQyxpQkFBaUIsQ0FDakUsSUFBSSxLQUFLLENBQUMsWUFBWSxDQUFDLENBQ3hCLENBQUM7WUFFRixNQUFNLE1BQU0sR0FBRyxNQUFNLHlCQUF5QixDQUFDLFdBQVcsRUFBRSxTQUFTLENBQUMsQ0FBQztZQUV2RSxNQUFNLENBQUMsTUFBTSxDQUFDLENBQUMsSUFBSSxDQUNqQiw4REFBOEQsQ0FDL0QsQ0FBQztRQUNKLENBQUMsQ0FBQyxDQUFDO0lBQ0wsQ0FBQyxDQUFDLENBQUM7QUFDTCxDQUFDLENBQUMsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7XG4gIGhhbmRsZUdldENhbGVuZGFyRXZlbnRzLFxuICBoYW5kbGVDcmVhdGVDYWxlbmRhckV2ZW50LFxufSBmcm9tICcuLi9jYWxlbmRhcic7XG5pbXBvcnQgKiBhcyBjYWxlbmRhclNraWxscyBmcm9tICcuLi9jYWxlbmRhclNraWxscyc7XG5cbmplc3QubW9jaygnLi4vY2FsZW5kYXJTa2lsbHMnLCAoKSA9PiAoe1xuICBsaXN0VXBjb21pbmdFdmVudHM6IGplc3QuZm4oKSxcbiAgY3JlYXRlQ2FsZW5kYXJFdmVudDogamVzdC5mbigpLFxufSkpO1xuXG5kZXNjcmliZSgnY2FsZW5kYXIgc2tpbGwnLCAoKSA9PiB7XG4gIGFmdGVyRWFjaCgoKSA9PiB7XG4gICAgamVzdC5jbGVhckFsbE1vY2tzKCk7XG4gIH0pO1xuXG4gIGRlc2NyaWJlKCdoYW5kbGVHZXRDYWxlbmRhckV2ZW50cycsICgpID0+IHtcbiAgICBpdCgnc2hvdWxkIHJldHVybiBhIGxpc3Qgb2YgdXBjb21pbmcgZXZlbnRzJywgYXN5bmMgKCkgPT4ge1xuICAgICAgY29uc3QgbW9ja0V2ZW50cyA9IFtcbiAgICAgICAge1xuICAgICAgICAgIHN1bW1hcnk6ICdUZXN0IEV2ZW50IDEnLFxuICAgICAgICAgIHN0YXJ0VGltZTogbmV3IERhdGUoKS50b0lTT1N0cmluZygpLFxuICAgICAgICAgIGVuZFRpbWU6IG5ldyBEYXRlKCkudG9JU09TdHJpbmcoKSxcbiAgICAgICAgfSxcbiAgICAgICAge1xuICAgICAgICAgIHN1bW1hcnk6ICdUZXN0IEV2ZW50IDInLFxuICAgICAgICAgIHN0YXJ0VGltZTogbmV3IERhdGUoKS50b0lTT1N0cmluZygpLFxuICAgICAgICAgIGVuZFRpbWU6IG5ldyBEYXRlKCkudG9JU09TdHJpbmcoKSxcbiAgICAgICAgfSxcbiAgICAgIF07XG4gICAgICAoY2FsZW5kYXJTa2lsbHMubGlzdFVwY29taW5nRXZlbnRzIGFzIGplc3QuTW9jaykubW9ja1Jlc29sdmVkVmFsdWUoXG4gICAgICAgIG1vY2tFdmVudHNcbiAgICAgICk7XG5cbiAgICAgIGNvbnN0IHJlc3VsdCA9IGF3YWl0IGhhbmRsZUdldENhbGVuZGFyRXZlbnRzKCd0ZXN0LXVzZXInLCB7fSk7XG5cbiAgICAgIGV4cGVjdChyZXN1bHQpLnRvQ29udGFpbignVXBjb21pbmcgY2FsZW5kYXIgZXZlbnRzOicpO1xuICAgICAgZXhwZWN0KHJlc3VsdCkudG9Db250YWluKCdUZXN0IEV2ZW50IDEnKTtcbiAgICAgIGV4cGVjdChyZXN1bHQpLnRvQ29udGFpbignVGVzdCBFdmVudCAyJyk7XG4gICAgfSk7XG5cbiAgICBpdCgnc2hvdWxkIHJldHVybiBhIG1lc3NhZ2Ugd2hlbiB0aGVyZSBhcmUgbm8gdXBjb21pbmcgZXZlbnRzJywgYXN5bmMgKCkgPT4ge1xuICAgICAgKGNhbGVuZGFyU2tpbGxzLmxpc3RVcGNvbWluZ0V2ZW50cyBhcyBqZXN0Lk1vY2spLm1vY2tSZXNvbHZlZFZhbHVlKFtdKTtcblxuICAgICAgY29uc3QgcmVzdWx0ID0gYXdhaXQgaGFuZGxlR2V0Q2FsZW5kYXJFdmVudHMoJ3Rlc3QtdXNlcicsIHt9KTtcblxuICAgICAgZXhwZWN0KHJlc3VsdCkudG9CZShcbiAgICAgICAgXCJObyB1cGNvbWluZyBjYWxlbmRhciBldmVudHMgZm91bmQgbWF0Y2hpbmcgeW91ciBjcml0ZXJpYSwgb3IgSSBjb3VsZG4ndCBhY2Nlc3MgdGhlbS5cIlxuICAgICAgKTtcbiAgICB9KTtcblxuICAgIGl0KCdzaG91bGQgcmV0dXJuIGFuIGVycm9yIG1lc3NhZ2Ugd2hlbiBhbiBlcnJvciBvY2N1cnMnLCBhc3luYyAoKSA9PiB7XG4gICAgICAoY2FsZW5kYXJTa2lsbHMubGlzdFVwY29taW5nRXZlbnRzIGFzIGplc3QuTW9jaykubW9ja1JlamVjdGVkVmFsdWUoXG4gICAgICAgIG5ldyBFcnJvcignVGVzdCBFcnJvcicpXG4gICAgICApO1xuXG4gICAgICBjb25zdCByZXN1bHQgPSBhd2FpdCBoYW5kbGVHZXRDYWxlbmRhckV2ZW50cygndGVzdC11c2VyJywge30pO1xuXG4gICAgICBleHBlY3QocmVzdWx0KS50b0JlKFxuICAgICAgICBcIlNvcnJ5LCBJIGNvdWxkbid0IGZldGNoIHlvdXIgY2FsZW5kYXIgZXZlbnRzIGR1ZSB0byBhbiBlcnJvci5cIlxuICAgICAgKTtcbiAgICB9KTtcbiAgfSk7XG5cbiAgZGVzY3JpYmUoJ2hhbmRsZUNyZWF0ZUNhbGVuZGFyRXZlbnQnLCAoKSA9PiB7XG4gICAgaXQoJ3Nob3VsZCBjcmVhdGUgYSBuZXcgY2FsZW5kYXIgZXZlbnQnLCBhc3luYyAoKSA9PiB7XG4gICAgICBjb25zdCBtb2NrRXZlbnQgPSB7XG4gICAgICAgIHN1bW1hcnk6ICdUZXN0IEV2ZW50JyxcbiAgICAgICAgc3RhcnRfdGltZTogbmV3IERhdGUoKS50b0lTT1N0cmluZygpLFxuICAgICAgICBlbmRfdGltZTogbmV3IERhdGUoKS50b0lTT1N0cmluZygpLFxuICAgICAgfTtcbiAgICAgIChjYWxlbmRhclNraWxscy5jcmVhdGVDYWxlbmRhckV2ZW50IGFzIGplc3QuTW9jaykubW9ja1Jlc29sdmVkVmFsdWUoe1xuICAgICAgICBzdWNjZXNzOiB0cnVlLFxuICAgICAgICBtZXNzYWdlOiAnRXZlbnQgY3JlYXRlZCBzdWNjZXNzZnVsbHknLFxuICAgICAgICBldmVudElkOiAndGVzdC1ldmVudC1pZCcsXG4gICAgICB9KTtcblxuICAgICAgY29uc3QgcmVzdWx0ID0gYXdhaXQgaGFuZGxlQ3JlYXRlQ2FsZW5kYXJFdmVudCgndGVzdC11c2VyJywgbW9ja0V2ZW50KTtcblxuICAgICAgZXhwZWN0KHJlc3VsdCkudG9Db250YWluKCdFdmVudCBjcmVhdGVkOiBFdmVudCBjcmVhdGVkIHN1Y2Nlc3NmdWxseScpO1xuICAgIH0pO1xuXG4gICAgaXQoJ3Nob3VsZCByZXR1cm4gYW4gZXJyb3IgbWVzc2FnZSB3aGVuIHRoZSBzdW1tYXJ5IGlzIG1pc3NpbmcnLCBhc3luYyAoKSA9PiB7XG4gICAgICBjb25zdCBtb2NrRXZlbnQgPSB7XG4gICAgICAgIHN0YXJ0X3RpbWU6IG5ldyBEYXRlKCkudG9JU09TdHJpbmcoKSxcbiAgICAgICAgZW5kX3RpbWU6IG5ldyBEYXRlKCkudG9JU09TdHJpbmcoKSxcbiAgICAgIH07XG5cbiAgICAgIGNvbnN0IHJlc3VsdCA9IGF3YWl0IGhhbmRsZUNyZWF0ZUNhbGVuZGFyRXZlbnQoJ3Rlc3QtdXNlcicsIG1vY2tFdmVudCk7XG5cbiAgICAgIGV4cGVjdChyZXN1bHQpLnRvQmUoXG4gICAgICAgICdFdmVudCBzdW1tYXJ5IGlzIHJlcXVpcmVkIHRvIGNyZWF0ZSBhbiBldmVudCB2aWEgTkxVLidcbiAgICAgICk7XG4gICAgfSk7XG5cbiAgICBpdCgnc2hvdWxkIHJldHVybiBhbiBlcnJvciBtZXNzYWdlIHdoZW4gdGhlIHN0YXJ0IHRpbWUgaXMgbWlzc2luZycsIGFzeW5jICgpID0+IHtcbiAgICAgIGNvbnN0IG1vY2tFdmVudCA9IHtcbiAgICAgICAgc3VtbWFyeTogJ1Rlc3QgRXZlbnQnLFxuICAgICAgICBlbmRfdGltZTogbmV3IERhdGUoKS50b0lTT1N0cmluZygpLFxuICAgICAgfTtcblxuICAgICAgY29uc3QgcmVzdWx0ID0gYXdhaXQgaGFuZGxlQ3JlYXRlQ2FsZW5kYXJFdmVudCgndGVzdC11c2VyJywgbW9ja0V2ZW50KTtcblxuICAgICAgZXhwZWN0KHJlc3VsdCkudG9CZShcbiAgICAgICAgJ0V2ZW50IHN0YXJ0IHRpbWUgaXMgcmVxdWlyZWQgdG8gY3JlYXRlIGFuIGV2ZW50IHZpYSBOTFUuJ1xuICAgICAgKTtcbiAgICB9KTtcblxuICAgIGl0KCdzaG91bGQgcmV0dXJuIGFuIGVycm9yIG1lc3NhZ2Ugd2hlbiB0aGUgZW5kIHRpbWUgYW5kIGR1cmF0aW9uIGFyZSBtaXNzaW5nJywgYXN5bmMgKCkgPT4ge1xuICAgICAgY29uc3QgbW9ja0V2ZW50ID0ge1xuICAgICAgICBzdW1tYXJ5OiAnVGVzdCBFdmVudCcsXG4gICAgICAgIHN0YXJ0X3RpbWU6IG5ldyBEYXRlKCkudG9JU09TdHJpbmcoKSxcbiAgICAgIH07XG5cbiAgICAgIGNvbnN0IHJlc3VsdCA9IGF3YWl0IGhhbmRsZUNyZWF0ZUNhbGVuZGFyRXZlbnQoJ3Rlc3QtdXNlcicsIG1vY2tFdmVudCk7XG5cbiAgICAgIGV4cGVjdChyZXN1bHQpLnRvQmUoXG4gICAgICAgICdFdmVudCBlbmQgdGltZSBvciBkdXJhdGlvbiBpcyByZXF1aXJlZCB0byBjcmVhdGUgYW4gZXZlbnQgdmlhIE5MVS4nXG4gICAgICApO1xuICAgIH0pO1xuXG4gICAgaXQoJ3Nob3VsZCByZXR1cm4gYW4gZXJyb3IgbWVzc2FnZSB3aGVuIGFuIGVycm9yIG9jY3VycycsIGFzeW5jICgpID0+IHtcbiAgICAgIGNvbnN0IG1vY2tFdmVudCA9IHtcbiAgICAgICAgc3VtbWFyeTogJ1Rlc3QgRXZlbnQnLFxuICAgICAgICBzdGFydF90aW1lOiBuZXcgRGF0ZSgpLnRvSVNPU3RyaW5nKCksXG4gICAgICAgIGVuZF90aW1lOiBuZXcgRGF0ZSgpLnRvSVNPU3RyaW5nKCksXG4gICAgICB9O1xuICAgICAgKGNhbGVuZGFyU2tpbGxzLmNyZWF0ZUNhbGVuZGFyRXZlbnQgYXMgamVzdC5Nb2NrKS5tb2NrUmVqZWN0ZWRWYWx1ZShcbiAgICAgICAgbmV3IEVycm9yKCdUZXN0IEVycm9yJylcbiAgICAgICk7XG5cbiAgICAgIGNvbnN0IHJlc3VsdCA9IGF3YWl0IGhhbmRsZUNyZWF0ZUNhbGVuZGFyRXZlbnQoJ3Rlc3QtdXNlcicsIG1vY2tFdmVudCk7XG5cbiAgICAgIGV4cGVjdChyZXN1bHQpLnRvQmUoXG4gICAgICAgIFwiU29ycnksIEkgY291bGRuJ3QgY3JlYXRlIHRoZSBjYWxlbmRhciBldmVudCBkdWUgdG8gYW4gZXJyb3IuXCJcbiAgICAgICk7XG4gICAgfSk7XG4gIH0pO1xufSk7XG4iXX0=