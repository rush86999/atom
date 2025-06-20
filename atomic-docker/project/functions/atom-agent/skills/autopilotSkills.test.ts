import {
  enableAutopilot,
  disableAutopilot,
  getAutopilotStatus,
} from './autopilotSkills';
import * as apiHelper from '../../autopilot/_libs/api-helper'; // To mock its functions
import { AutopilotType, ScheduleAssistWithMeetingQueueBodyType, AutopilotApiResponse } from '../../autopilot/_libs/types';

// Mock the api-helper module
jest.mock('../../autopilot/_libs/api-helper', () => ({
  createDailyFeaturesApplyEventTrigger: jest.fn(),
  upsertAutopilotOne: jest.fn(),
  deleteScheduledEventForAutopilot: jest.fn(),
  deleteAutopilotGivenId: jest.fn(),
  listAutopilotsGivenUserId: jest.fn(),
  getAutopilotGivenId: jest.fn(),
}));

// Mock dayjs for consistent date generation if needed, though current skills might not require deep mocking of it.
// For now, we'll rely on the actual dayjs unless tests become flaky due to timestamps.
// jest.mock('dayjs', () => {
//   const actualDayjs = jest.requireActual('dayjs');
//   // Mock specific functions if needed, e.g., actualDayjs.tz.guess = () => 'Test/Timezone';
//   return actualDayjs;
// });

describe('Autopilot Skills', () => {
  const userId = 'test-user-123';

  beforeEach(() => {
    // Reset mocks before each test
    jest.clearAllMocks();
  });

  describe('enableAutopilot', () => {
    const mockQueryComplex = JSON.stringify({
      timezone: 'America/New_York',
      payload: {
        windowStartDate: '2024-09-01T09:00:00.000Z',
        windowEndDate: '2024-09-08T17:00:00.000Z',
      }
    });
    const mockAutopilotData = { id: 'event-id-123', userId } as AutopilotType;

    it('should enable autopilot successfully when all API calls succeed', async () => {
      (apiHelper.createDailyFeaturesApplyEventTrigger as jest.Mock).mockResolvedValue({ ok: true, data: 'event-id-123' });
      (apiHelper.upsertAutopilotOne as jest.Mock).mockResolvedValue({ ok: true, data: mockAutopilotData });

      const result = await enableAutopilot(userId, mockQueryComplex);

      expect(apiHelper.createDailyFeaturesApplyEventTrigger).toHaveBeenCalled();
      expect(apiHelper.upsertAutopilotOne).toHaveBeenCalled();
      expect(result.ok).toBe(true);
      expect(result.data).toEqual(mockAutopilotData);
    });

    it('should return error if createDailyFeaturesApplyEventTrigger fails', async () => {
      (apiHelper.createDailyFeaturesApplyEventTrigger as jest.Mock).mockResolvedValue({ ok: false, error: { code: 'API_ERROR', message: 'Trigger failed' } });

      const result = await enableAutopilot(userId, mockQueryComplex);

      expect(apiHelper.createDailyFeaturesApplyEventTrigger).toHaveBeenCalled();
      expect(apiHelper.upsertAutopilotOne).not.toHaveBeenCalled();
      expect(result.ok).toBe(false);
      expect(result.error?.message).toBe('Trigger failed');
    });

    it('should call deleteScheduledEventForAutopilot if upsertAutopilotOne fails', async () => {
      (apiHelper.createDailyFeaturesApplyEventTrigger as jest.Mock).mockResolvedValue({ ok: true, data: 'event-id-123' });
      (apiHelper.upsertAutopilotOne as jest.Mock).mockResolvedValue({ ok: false, error: { code: 'DB_ERROR', message: 'Upsert failed' } });
      (apiHelper.deleteScheduledEventForAutopilot as jest.Mock).mockResolvedValue({ ok: true, data: {success: true}}); // Mock cleanup

      const result = await enableAutopilot(userId, mockQueryComplex);

      expect(apiHelper.createDailyFeaturesApplyEventTrigger).toHaveBeenCalled();
      expect(apiHelper.upsertAutopilotOne).toHaveBeenCalled();
      expect(apiHelper.deleteScheduledEventForAutopilot).toHaveBeenCalledWith('event-id-123');
      expect(result.ok).toBe(false);
      expect(result.error?.message).toBe('Upsert failed');
    });
     it('should handle simple string query for default behavior', async () => {
      (apiHelper.createDailyFeaturesApplyEventTrigger as jest.Mock).mockResolvedValue({ ok: true, data: 'event-id-default' });
      (apiHelper.upsertAutopilotOne as jest.Mock).mockResolvedValue({ ok: true, data: { ...mockAutopilotData, id: 'event-id-default' } });

      const simpleQuery = "just enable it"; // Not JSON
      await enableAutopilot(userId, simpleQuery);

      expect(apiHelper.createDailyFeaturesApplyEventTrigger).toHaveBeenCalledWith(
        expect.objectContaining({ userId }),
        expect.objectContaining({ userId })
      );
      // Check that payload uses defaults (hard to check exact dates without more complex mocking of dayjs)
      const callArgs = (apiHelper.createDailyFeaturesApplyEventTrigger as jest.Mock).mock.calls[0];
      expect(callArgs[0].payload.timezone).toBeDefined(); // Default timezone was applied
    });
  });

  describe('disableAutopilot', () => {
    const eventId = 'event-to-disable-456';

    it('should disable autopilot successfully when all API calls succeed', async () => {
      (apiHelper.deleteScheduledEventForAutopilot as jest.Mock).mockResolvedValue({ ok: true, data: { success: true } });
      (apiHelper.deleteAutopilotGivenId as jest.Mock).mockResolvedValue({ ok: true, data: { id: eventId } as AutopilotType }); // Mock the deleted record

      const result = await disableAutopilot(userId, eventId); // Query is eventId directly

      expect(apiHelper.deleteScheduledEventForAutopilot).toHaveBeenCalledWith(eventId);
      expect(apiHelper.deleteAutopilotGivenId).toHaveBeenCalledWith(eventId);
      expect(result.ok).toBe(true);
      expect(result.data?.success).toBe(true);
    });

    it('should return error if eventId is not provided in query', async () => {
        const result = await disableAutopilot(userId, ""); // Empty query
        expect(result.ok).toBe(false);
        expect(result.error?.code).toBe('VALIDATION_ERROR');
        expect(result.error?.message).toContain('eventId (autopilotId) is required');
        expect(apiHelper.deleteScheduledEventForAutopilot).not.toHaveBeenCalled();
        expect(apiHelper.deleteAutopilotGivenId).not.toHaveBeenCalled();
    });

    it('should proceed to delete DB record even if deleting scheduled event fails, but reflect overall outcome based on DB deletion', async () => {
      (apiHelper.deleteScheduledEventForAutopilot as jest.Mock).mockResolvedValue({ ok: false, error: { code: 'API_ERROR', message: 'Event deletion failed' } });
      (apiHelper.deleteAutopilotGivenId as jest.Mock).mockResolvedValue({ ok: true, data: { id: eventId } as AutopilotType });

      const result = await disableAutopilot(userId, eventId);

      expect(apiHelper.deleteScheduledEventForAutopilot).toHaveBeenCalledWith(eventId);
      expect(apiHelper.deleteAutopilotGivenId).toHaveBeenCalledWith(eventId);
      // This scenario is tricky: if event deletion fails, it's a warning. Success depends on DB deletion.
      // The current logic in disableAutopilot returns ok:true if deleteAutopilotGivenId is ok.
      expect(result.ok).toBe(true);
      expect(result.data?.success).toBe(true);
    });

    it('should return error if deleteAutopilotGivenId fails', async () => {
      (apiHelper.deleteScheduledEventForAutopilot as jest.Mock).mockResolvedValue({ ok: true, data: { success: true } });
      (apiHelper.deleteAutopilotGivenId as jest.Mock).mockResolvedValue({ ok: false, error: { code: 'DB_ERROR', message: 'DB deletion failed' } });

      const result = await disableAutopilot(userId, eventId);

      expect(apiHelper.deleteScheduledEventForAutopilot).toHaveBeenCalledWith(eventId);
      expect(apiHelper.deleteAutopilotGivenId).toHaveBeenCalledWith(eventId);
      expect(result.ok).toBe(false);
      expect(result.error?.message).toBe('DB deletion failed');
    });
  });

  describe('getAutopilotStatus', () => {
    const specificAutopilotId = 'ap-specific-789';
    const mockAutopilotDetail = { id: specificAutopilotId, userId, scheduleAt: 'tomorrow' } as AutopilotType;
    const mockAutopilotList = [{ id: 'ap-list-001', userId, scheduleAt: 'today' }] as AutopilotType[];

    it('should call getAutopilotGivenId if autopilotId is provided in query', async () => {
      (apiHelper.getAutopilotGivenId as jest.Mock).mockResolvedValue({ ok: true, data: mockAutopilotDetail });

      const result = await getAutopilotStatus(userId, specificAutopilotId); // Query is autopilotId

      expect(apiHelper.getAutopilotGivenId).toHaveBeenCalledWith(specificAutopilotId);
      expect(apiHelper.listAutopilotsGivenUserId).not.toHaveBeenCalled();
      expect(result.ok).toBe(true);
      expect(result.data).toEqual(mockAutopilotDetail);
    });

    it('should call listAutopilotsGivenUserId if no autopilotId is provided in query', async () => {
      // Note: listAutopilotsGivenUserId in api-helper returns a single AutopilotType | null, not an array.
      // The skill reflects this. If it were to return an array, this test and skill would change.
      (apiHelper.listAutopilotsGivenUserId as jest.Mock).mockResolvedValue({ ok: true, data: mockAutopilotList[0] });


      const result = await getAutopilotStatus(userId, ""); // Empty query

      expect(apiHelper.listAutopilotsGivenUserId).toHaveBeenCalledWith(userId);
      expect(apiHelper.getAutopilotGivenId).not.toHaveBeenCalled();
      expect(result.ok).toBe(true);
      expect(result.data).toEqual(mockAutopilotList[0]);
    });

    it('should handle JSON query for specific autopilotId', async () => {
      (apiHelper.getAutopilotGivenId as jest.Mock).mockResolvedValue({ ok: true, data: mockAutopilotDetail });
      const queryJson = JSON.stringify({ autopilotId: specificAutopilotId });
      await getAutopilotStatus(userId, queryJson);
      expect(apiHelper.getAutopilotGivenId).toHaveBeenCalledWith(specificAutopilotId);
    });

    it('should return error if the API call fails (getAutopilotGivenId)', async () => {
      (apiHelper.getAutopilotGivenId as jest.Mock).mockResolvedValue({ ok: false, error: { code: 'API_ERROR', message: 'Fetch failed' } });
      const result = await getAutopilotStatus(userId, specificAutopilotId);
      expect(result.ok).toBe(false);
      expect(result.error?.message).toBe('Fetch failed');
    });

    it('should return error if the API call fails (listAutopilotsGivenUserId)', async () => {
      (apiHelper.listAutopilotsGivenUserId as jest.Mock).mockResolvedValue({ ok: false, error: { code: 'API_ERROR', message: 'List fetch failed' } });
      const result = await getAutopilotStatus(userId, "");
      expect(result.ok).toBe(false);
      expect(result.error?.message).toBe('List fetch failed');
    });
  });
});
