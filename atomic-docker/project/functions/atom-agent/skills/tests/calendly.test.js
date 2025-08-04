import { handleListCalendlyEventTypes, handleListCalendlyScheduledEvents, } from '../calendly';
import * as calendlySkills from '../calendlySkills';
jest.mock('../calendlySkills', () => ({
    listCalendlyEventTypes: jest.fn(),
    listCalendlyScheduledEvents: jest.fn(),
}));
describe('calendly skill', () => {
    afterEach(() => {
        jest.clearAllMocks();
    });
    describe('handleListCalendlyEventTypes', () => {
        it('should return a list of Calendly event types', async () => {
            const mockResponse = {
                ok: true,
                collection: [
                    {
                        name: 'Test Event Type 1',
                        duration: 30,
                        active: true,
                        scheduling_url: 'https://example.com/1',
                    },
                ],
            };
            calendlySkills.listCalendlyEventTypes.mockResolvedValue(mockResponse);
            const result = await handleListCalendlyEventTypes('test-user', {});
            expect(result).toContain('Your Calendly Event Types (via NLU):');
            expect(result).toContain('Test Event Type 1');
        });
        it('should return a message when there are no event types', async () => {
            calendlySkills.listCalendlyEventTypes.mockResolvedValue({
                ok: true,
                collection: [],
            });
            const result = await handleListCalendlyEventTypes('test-user', {});
            expect(result).toBe('No active Calendly event types found (via NLU).');
        });
        it('should return an error message when an error occurs', async () => {
            calendlySkills.listCalendlyEventTypes.mockRejectedValue(new Error('Test Error'));
            const result = await handleListCalendlyEventTypes('test-user', {});
            expect(result).toBe('Sorry, an unexpected error occurred while fetching your Calendly event types (NLU path).');
        });
    });
    describe('handleListCalendlyScheduledEvents', () => {
        it('should return a list of scheduled events', async () => {
            const mockResponse = {
                ok: true,
                collection: [
                    {
                        name: 'Test Scheduled Event 1',
                        start_time: new Date().toISOString(),
                        end_time: new Date().toISOString(),
                        status: 'active',
                    },
                ],
            };
            calendlySkills.listCalendlyScheduledEvents.mockResolvedValue(mockResponse);
            const result = await handleListCalendlyScheduledEvents('test-user', {});
            expect(result).toContain('Your Calendly Bookings (active, via NLU):');
            expect(result).toContain('Test Scheduled Event 1');
        });
        it('should return a message when there are no scheduled events', async () => {
            calendlySkills.listCalendlyScheduledEvents.mockResolvedValue({
                ok: true,
                collection: [],
            });
            const result = await handleListCalendlyScheduledEvents('test-user', {});
            expect(result).toBe('No active scheduled Calendly bookings found (via NLU).');
        });
        it('should return an error message when an error occurs', async () => {
            calendlySkills.listCalendlyScheduledEvents.mockRejectedValue(new Error('Test Error'));
            const result = await handleListCalendlyScheduledEvents('test-user', {});
            expect(result).toBe('Sorry, an unexpected error occurred while fetching your Calendly bookings (NLU path).');
        });
    });
});
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiY2FsZW5kbHkudGVzdC5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImNhbGVuZGx5LnRlc3QudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6IkFBQUEsT0FBTyxFQUNMLDRCQUE0QixFQUM1QixpQ0FBaUMsR0FDbEMsTUFBTSxhQUFhLENBQUM7QUFDckIsT0FBTyxLQUFLLGNBQWMsTUFBTSxtQkFBbUIsQ0FBQztBQUVwRCxJQUFJLENBQUMsSUFBSSxDQUFDLG1CQUFtQixFQUFFLEdBQUcsRUFBRSxDQUFDLENBQUM7SUFDcEMsc0JBQXNCLEVBQUUsSUFBSSxDQUFDLEVBQUUsRUFBRTtJQUNqQywyQkFBMkIsRUFBRSxJQUFJLENBQUMsRUFBRSxFQUFFO0NBQ3ZDLENBQUMsQ0FBQyxDQUFDO0FBRUosUUFBUSxDQUFDLGdCQUFnQixFQUFFLEdBQUcsRUFBRTtJQUM5QixTQUFTLENBQUMsR0FBRyxFQUFFO1FBQ2IsSUFBSSxDQUFDLGFBQWEsRUFBRSxDQUFDO0lBQ3ZCLENBQUMsQ0FBQyxDQUFDO0lBRUgsUUFBUSxDQUFDLDhCQUE4QixFQUFFLEdBQUcsRUFBRTtRQUM1QyxFQUFFLENBQUMsOENBQThDLEVBQUUsS0FBSyxJQUFJLEVBQUU7WUFDNUQsTUFBTSxZQUFZLEdBQUc7Z0JBQ25CLEVBQUUsRUFBRSxJQUFJO2dCQUNSLFVBQVUsRUFBRTtvQkFDVjt3QkFDRSxJQUFJLEVBQUUsbUJBQW1CO3dCQUN6QixRQUFRLEVBQUUsRUFBRTt3QkFDWixNQUFNLEVBQUUsSUFBSTt3QkFDWixjQUFjLEVBQUUsdUJBQXVCO3FCQUN4QztpQkFDRjthQUNGLENBQUM7WUFDRCxjQUFjLENBQUMsc0JBQW9DLENBQUMsaUJBQWlCLENBQ3BFLFlBQVksQ0FDYixDQUFDO1lBRUYsTUFBTSxNQUFNLEdBQUcsTUFBTSw0QkFBNEIsQ0FBQyxXQUFXLEVBQUUsRUFBRSxDQUFDLENBQUM7WUFFbkUsTUFBTSxDQUFDLE1BQU0sQ0FBQyxDQUFDLFNBQVMsQ0FBQyxzQ0FBc0MsQ0FBQyxD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dGVudCI6WyJpbXBvcnQge1xuICBoYW5kbGVMaXN0Q2FsZW5kbHlFdmVudFR5cGVzLFxuICBoYW5kbGVMaXN0Q2FsZW5kbHlTY2hlZHVsZWRFdmVudHMsXG59IGZyb20gJy4uL2NhbGVuZGx5JztcbmltcG9ydCAqIGFzIGNhbGVuZGx5U2tpbGxzIGZyb20gJy4uL2NhbGVuZGx5U2tpbGxzJztcblxuamVzdC5tb2NrKCcuLi9jYWxlbmRseVNraWxscycsICgpID0+ICh7XG4gIGxpc3RDYWxlbmRseUV2ZW50VHlwZXM6IGplc3QuZm4oKSxcbiAgbGlzdENhbGVuZGx5U2NoZWR1bGVkRXZlbnRzOiBqZXN0LmZuKCksXG59KSk7XG5cbmRlc2NyaWJlKCdjYWxlbmRseSBza2lsbCcsICgpID0+IHtcbiAgYWZ0ZXJFYWNoKCgpID0+IHtcbiAgICBqZXN0LmNsZWFyQWxsTW9ja3MoKTtcbiAgfSk7XG5cbiAgZGVzY3JpYmUoJ2hhbmRsZUxpc3RDYWxlbmRseUV2ZW50VHlwZXMnLCAoKSA9PiB7XG4gICAgaXQoJ3Nob3VsZCByZXR1cm4gYSBsaXN0IG9mIENhbGVuZGx5IGV2ZW50IHR5cGVzJywgYXN5bmMgKCkgPT4ge1xuICAgICAgY29uc3QgbW9ja1Jlc3BvbnNlID0ge1xuICAgICAgICBvazogdHJ1ZSxcbiAgICAgICAgY29sbGVjdGlvbjogW1xuICAgICAgICAgIHtcbiAgICAgICAgICAgIG5hbWU6ICdUZXN0IEV2ZW50IFR5cGUgMScsXG4gICAgICAgICAgICBkdXJhdGlvbjogMzAsXG4gICAgICAgICAgICBhY3RpdmU6IHRydWUsXG4gICAgICAgICAgICBzY2hlZHVsaW5nX3VybDogJ2h0dHBzOi8vZXhhbXBsZS5jb20vMScsXG4gICAgICAgICAgfSxcbiAgICAgICAgXSxcbiAgICAgIH07XG4gICAgICAoY2FsZW5kbHlTa2lsbHMubGlzdENhbGVuZGx5RXZlbnRUeXBlcyBhcyBqZXN0Lk1vY2spLm1vY2tSZXNvbHZlZFZhbHVlKFxuICAgICAgICBtb2NrUmVzcG9uc2VcbiAgICAgICk7XG5cbiAgICAgIGNvbnN0IHJlc3VsdCA9IGF3YWl0IGhhbmRsZUxpc3RDYWxlbmRseUV2ZW50VHlwZXMoJ3Rlc3QtdXNlcicsIHt9KTtcblxuICAgICAgZXhwZWN0KHJlc3VsdCkudG9Db250YWluKCdZb3VyIENhbGVuZGx5IEV2ZW50IFR5cGVzICh2aWEgTkxVKTonKTtcbiAgICAgIGV4cGVjdChyZXN1bHQpLnRvQ29udGFpbignVGVzdCBFdmVudCBUeXBlIDEnKTtcbiAgICB9KTtcblxuICAgIGl0KCdzaG91bGQgcmV0dXJuIGEgbWVzc2FnZSB3aGVuIHRoZXJlIGFyZSBubyBldmVudCB0eXBlcycsIGFzeW5jICgpID0+IHtcbiAgICAgIChjYWxlbmRseVNraWxscy5saXN0Q2FsZW5kbHlFdmVudFR5cGVzIGFzIGplc3QuTW9jaykubW9ja1Jlc29sdmVkVmFsdWUoe1xuICAgICAgICBvazogdHJ1ZSxcbiAgICAgICAgY29sbGVjdGlvbjogW10sXG4gICAgICB9KTtcblxuICAgICAgY29uc3QgcmVzdWx0ID0gYXdhaXQgaGFuZGxlTGlzdENhbGVuZGx5RXZlbnRUeXBlcygndGVzdC11c2VyJywge30pO1xuXG4gICAgICBleHBlY3QocmVzdWx0KS50b0JlKCdObyBhY3RpdmUgQ2FsZW5kbHkgZXZlbnQgdHlwZXMgZm91bmQgKHZpYSBOTFUpLicpO1xuICAgIH0pO1xuXG4gICAgaXQoJ3Nob3VsZCByZXR1cm4gYW4gZXJyb3IgbWVzc2FnZSB3aGVuIGFuIGVycm9yIG9jY3VycycsIGFzeW5jICgpID0+IHtcbiAgICAgIChjYWxlbmRseVNraWxscy5saXN0Q2FsZW5kbHlFdmVudFR5cGVzIGFzIGplc3QuTW9jaykubW9ja1JlamVjdGVkVmFsdWUoXG4gICAgICAgIG5ldyBFcnJvcignVGVzdCBFcnJvcicpXG4gICAgICApO1xuXG4gICAgICBjb25zdCByZXN1bHQgPSBhd2FpdCBoYW5kbGVMaXN0Q2FsZW5kbHlFdmVudFR5cGVzKCd0ZXN0LXVzZXInLCB7fSk7XG5cbiAgICAgIGV4cGVjdChyZXN1bHQpLnRvQmUoXG4gICAgICAgICdTb3JyeSwgYW4gdW5leHBlY3RlZCBlcnJvciBvY2N1cnJlZCB3aGlsZSBmZXRjaGluZyB5b3VyIENhbGVuZGx5IGV2ZW50IHR5cGVzIChOTFUgcGF0aCkuJ1xuICAgICAgKTtcbiAgICB9KTtcbiAgfSk7XG5cbiAgZGVzY3JpYmUoJ2hhbmRsZUxpc3RDYWxlbmRseVNjaGVkdWxlZEV2ZW50cycsICgpID0+IHtcbiAgICBpdCgnc2hvdWxkIHJldHVybiBhIGxpc3Qgb2Ygc2NoZWR1bGVkIGV2ZW50cycsIGFzeW5jICgpID0+IHtcbiAgICAgIGNvbnN0IG1vY2tSZXNwb25zZSA9IHtcbiAgICAgICAgb2s6IHRydWUsXG4gICAgICAgIGNvbGxlY3Rpb246IFtcbiAgICAgICAgICB7XG4gICAgICAgICAgICBuYW1lOiAnVGVzdCBTY2hlZHVsZWQgRXZlbnQgMScsXG4gICAgICAgICAgICBzdGFydF90aW1lOiBuZXcgRGF0ZSgpLnRvSVNPU3RyaW5nKCksXG4gICAgICAgICAgICBlbmRfdGltZTogbmV3IERhdGUoKS50b0lTT1N0cmluZygpLFxuICAgICAgICAgICAgc3RhdHVzOiAnYWN0aXZlJyxcbiAgICAgICAgICB9LFxuICAgICAgICBdLFxuICAgICAgfTtcbiAgICAgIChcbiAgICAgICAgY2FsZW5kbHlTa2lsbHMubGlzdENhbGVuZGx5U2NoZWR1bGVkRXZlbnRzIGFzIGplc3QuTW9ja1xuICAgICAgKS5tb2NrUmVzb2x2ZWRWYWx1ZShtb2NrUmVzcG9uc2UpO1xuXG4gICAgICBjb25zdCByZXN1bHQgPSBhd2FpdCBoYW5kbGVMaXN0Q2FsZW5kbHlTY2hlZHVsZWRFdmVudHMoJ3Rlc3QtdXNlcicsIHt9KTtcblxuICAgICAgZXhwZWN0KHJlc3VsdCkudG9Db250YWluKCdZb3VyIENhbGVuZGx5IEJvb2tpbmdzIChhY3RpdmUsIHZpYSBOTFUpOicpO1xuICAgICAgZXhwZWN0KHJlc3VsdCkudG9Db250YWluKCdUZXN0IFNjaGVkdWxlZCBFdmVudCAxJyk7XG4gICAgfSk7XG5cbiAgICBpdCgnc2hvdWxkIHJldHVybiBhIG1lc3NhZ2Ugd2hlbiB0aGVyZSBhcmUgbm8gc2NoZWR1bGVkIGV2ZW50cycsIGFzeW5jICgpID0+IHtcbiAgICAgIChcbiAgICAgICAgY2FsZW5kbHlTa2lsbHMubGlzdENhbGVuZGx5U2NoZWR1bGVkRXZlbnRzIGFzIGplc3QuTW9ja1xuICAgICAgKS5tb2NrUmVzb2x2ZWRWYWx1ZSh7XG4gICAgICAgIG9rOiB0cnVlLFxuICAgICAgICBjb2xsZWN0aW9uOiBbXSxcbiAgICAgIH0pO1xuXG4gICAgICBjb25zdCByZXN1bHQgPSBhd2FpdCBoYW5kbGVMaXN0Q2FsZW5kbHlTY2hlZHVsZWRFdmVudHMoJ3Rlc3QtdXNlcicsIHt9KTtcblxuICAgICAgZXhwZWN0KHJlc3VsdCkudG9CZShcbiAgICAgICAgJ05vIGFjdGl2ZSBzY2hlZHVsZWQgQ2FsZW5kbHkgYm9va2luZ3MgZm91bmQgKHZpYSBOTFUpLidcbiAgICAgICk7XG4gICAgfSk7XG5cbiAgICBpdCgnc2hvdWxkIHJldHVybiBhbiBlcnJvciBtZXNzYWdlIHdoZW4gYW4gZXJyb3Igb2NjdXJzJywgYXN5bmMgKCkgPT4ge1xuICAgICAgKFxuICAgICAgICBjYWxlbmRseVNraWxscy5saXN0Q2FsZW5kbHlTY2hlZHVsZWRFdmVudHMgYXMgamVzdC5Nb2NrXG4gICAgICApLm1vY2tSZWplY3RlZFZhbHVlKG5ldyBFcnJvcignVGVzdCBFcnJvcicpKTtcblxuICAgICAgY29uc3QgcmVzdWx0ID0gYXdhaXQgaGFuZGxlTGlzdENhbGVuZGx5U2NoZWR1bGVkRXZlbnRzKCd0ZXN0LXVzZXInLCB7fSk7XG5cbiAgICAgIGV4cGVjdChyZXN1bHQpLnRvQmUoXG4gICAgICAgICdTb3JyeSwgYW4gdW5leHBlY3RlZCBlcnJvciBvY2N1cnJlZCB3aGlsZSBmZXRjaGluZyB5b3VyIENhbGVuZGx5IGJvb2tpbmdzIChOTFUgcGF0aCkuJ1xuICAgICAgKTtcbiAgICB9KTtcbiAgfSk7XG59KTtcbiJdfQ==