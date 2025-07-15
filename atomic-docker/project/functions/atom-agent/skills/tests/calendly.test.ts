import { handleListCalendlyEventTypes, handleListCalendlyScheduledEvents } from '../calendly';
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
            (calendlySkills.listCalendlyEventTypes as jest.Mock).mockResolvedValue(mockResponse);

            const result = await handleListCalendlyEventTypes('test-user', {});

            expect(result).toContain('Your Calendly Event Types (via NLU):');
            expect(result).toContain('Test Event Type 1');
        });

        it('should return a message when there are no event types', async () => {
            (calendlySkills.listCalendlyEventTypes as jest.Mock).mockResolvedValue({
                ok: true,
                collection: [],
            });

            const result = await handleListCalendlyEventTypes('test-user', {});

            expect(result).toBe('No active Calendly event types found (via NLU).');
        });

        it('should return an error message when an error occurs', async () => {
            (calendlySkills.listCalendlyEventTypes as jest.Mock).mockRejectedValue(new Error('Test Error'));

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
            (calendlySkills.listCalendlyScheduledEvents as jest.Mock).mockResolvedValue(mockResponse);

            const result = await handleListCalendlyScheduledEvents('test-user', {});

            expect(result).toContain('Your Calendly Bookings (active, via NLU):');
            expect(result).toContain('Test Scheduled Event 1');
        });

        it('should return a message when there are no scheduled events', async () => {
            (calendlySkills.listCalendlyScheduledEvents as jest.Mock).mockResolvedValue({
                ok: true,
                collection: [],
            });

            const result = await handleListCalendlyScheduledEvents('test-user', {});

            expect(result).toBe('No active scheduled Calendly bookings found (via NLU).');
        });

        it('should return an error message when an error occurs', async () => {
            (calendlySkills.listCalendlyScheduledEvents as jest.Mock).mockRejectedValue(new Error('Test Error'));

            const result = await handleListCalendlyScheduledEvents('test-user', {});

            expect(result).toBe('Sorry, an unexpected error occurred while fetching your Calendly bookings (NLU path).');
        });
    });
});
