import { handleTriggerZap } from '../zapier';
import * as zapierSkills from '../zapierSkills';
jest.mock('../zapierSkills', () => ({
    triggerZap: jest.fn(),
}));
describe('zapier skill', () => {
    afterEach(() => {
        jest.clearAllMocks();
    });
    describe('handleTriggerZap', () => {
        it('should trigger a Zap', async () => {
            zapierSkills.triggerZap.mockResolvedValue({
                success: true,
                message: 'Zap triggered successfully',
                runId: 'test-run-id',
            });
            const result = await handleTriggerZap({ zap_name: 'test-zap' });
            expect(result).toContain('Zap triggered via NLU: Zap triggered successfully');
        });
        it('should return an error message when the zap name is missing', async () => {
            const result = await handleTriggerZap({});
            expect(result).toBe('Zap name is required to trigger a Zap via NLU.');
        });
        it('should return an error message when an error occurs', async () => {
            zapierSkills.triggerZap.mockRejectedValue(new Error('Test Error'));
            const result = await handleTriggerZap({ zap_name: 'test-zap' });
            expect(result).toBe("Sorry, I couldn't trigger the Zap due to an error (NLU path).");
        });
    });
});
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiemFwaWVyLnRlc3QuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJ6YXBpZXIudGVzdC50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiQUFBQSxPQUFPLEVBQUUsZ0JBQWdCLEVBQUUsTUFBTSxXQUFXLENBQUM7QUFDN0MsT0FBTyxLQUFLLFlBQVksTUFBTSxpQkFBaUIsQ0FBQztBQUVoRCxJQUFJLENBQUMsSUFBSSxDQUFDLGlCQUFpQixFQUFFLEdBQUcsRUFBRSxDQUFDLENBQUM7SUFDbEMsVUFBVSxFQUFFLElBQUksQ0FBQyxFQUFFLEVBQUU7Q0FDdEIsQ0FBQyxDQUFDLENBQUM7QUFFSixRQUFRLENBQUMsY0FBYyxFQUFFLEdBQUcsRUFBRTtJQUM1QixTQUFTLENBQUMsR0FBRyxFQUFFO1FBQ2IsSUFBSSxDQUFDLGFBQWEsRUFBRSxDQUFDO0lBQ3ZCLENBQUMsQ0FBQyxDQUFDO0lBRUgsUUFBUSxDQUFDLGtCQUFrQixFQUFFLEdBQUcsRUFBRTtRQUNoQyxFQUFFLENBQUMsc0JBQXNCLEVBQUUsS0FBSyxJQUFJLEVBQUU7WUFDbkMsWUFBWSxDQUFDLFVBQXdCLENBQUMsaUJBQWlCLENBQUM7Z0JBQ3ZELE9BQU8sRUFBRSxJQUFJO2dCQUNiLE9BQU8sRUFBRSw0QkFBNEI7Z0JBQ3JDLEtBQUssRUFBRSxhQUFhO2FBQ3JCLENBQUMsQ0FBQztZQUVILE1BQU0sTUFBTSxHQUFHLE1BQU0sZ0JBQWdCLENBQUMsRUFBRSxRQUFRLEVBQUUsVUFBVSxFQUFFLENBQUMsQ0FBQztZQUVoRSxNQUFNLENBQUMsTUFBTSxDQUFDLENBQUMsU0FBUyxDQUN0QixtREFBbUQsQ0FDcEQsQ0FBQztRQUNKLENBQUMsQ0FBQyxDQUFDO1FBRUgsRUFBRSxDQUFDLDZEQUE2RCxFQUFFLEtBQUssSUFBSSxFQUFFO1lBQzNFLE1BQU0sTUFBTSxHQUFHLE1BQU0sZ0JBQWdCLENBQUMsRUFBRSxDQUFDLENBQUM7WUFFMUMsTUFBTSxDQUFDLE1BQU0sQ0FBQyxDQUFDLElBQUksQ0FBQyxnREFBZ0QsQ0FBQyxDQUFDO1FBQ3hFLENBQUMsQ0FBQyxDQUFDO1FBRUgsRUFBRSxDQUFDLHFEQUFxRCxFQUFFLEtBQUssSUFBSSxFQUFFO1lBQ2xFLFlBQVksQ0FBQyxVQUF3QixDQUFDLGlCQUFpQixDQUN0RCxJQUFJLEtBQUssQ0FBQyxZQUFZLENBQUMsQ0FDeEIsQ0FBQztZQUVGLE1BQU0sTUFBTSxHQUFHLE1BQU0sZ0JBQWdCLENBQUMsRUFBRSxRQUFRLEVBQUUsVUFBVSxFQUFFLENBQUMsQ0FBQztZQUVoRSxNQUFNLENBQUMsTUFBTSxDQUFDLENBQUMsSUFBSSxDQUNqQiwrREFBK0QsQ0FDaEUsQ0FBQztRQUNKLENBQUMsQ0FBQyxDQUFDO0lBQ0wsQ0FBQyxDQUFDLENBQUM7QUFDTCxDQUFDLENBQUMsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7IGhhbmRsZVRyaWdnZXJaYXAgfSBmcm9tICcuLi96YXBpZXInO1xuaW1wb3J0ICogYXMgemFwaWVyU2tpbGxzIGZyb20gJy4uL3phcGllclNraWxscyc7XG5cbmplc3QubW9jaygnLi4vemFwaWVyU2tpbGxzJywgKCkgPT4gKHtcbiAgdHJpZ2dlclphcDogamVzdC5mbigpLFxufSkpO1xuXG5kZXNjcmliZSgnemFwaWVyIHNraWxsJywgKCkgPT4ge1xuICBhZnRlckVhY2goKCkgPT4ge1xuICAgIGplc3QuY2xlYXJBbGxNb2NrcygpO1xuICB9KTtcblxuICBkZXNjcmliZSgnaGFuZGxlVHJpZ2dlclphcCcsICgpID0+IHtcbiAgICBpdCgnc2hvdWxkIHRyaWdnZXIgYSBaYXAnLCBhc3luYyAoKSA9PiB7XG4gICAgICAoemFwaWVyU2tpbGxzLnRyaWdnZXJaYXAgYXMgamVzdC5Nb2NrKS5tb2NrUmVzb2x2ZWRWYWx1ZSh7XG4gICAgICAgIHN1Y2Nlc3M6IHRydWUsXG4gICAgICAgIG1lc3NhZ2U6ICdaYXAgdHJpZ2dlcmVkIHN1Y2Nlc3NmdWxseScsXG4gICAgICAgIHJ1bklkOiAndGVzdC1ydW4taWQnLFxuICAgICAgfSk7XG5cbiAgICAgIGNvbnN0IHJlc3VsdCA9IGF3YWl0IGhhbmRsZVRyaWdnZXJaYXAoeyB6YXBfbmFtZTogJ3Rlc3QtemFwJyB9KTtcblxuICAgICAgZXhwZWN0KHJlc3VsdCkudG9Db250YWluKFxuICAgICAgICAnWmFwIHRyaWdnZXJlZCB2aWEgTkxVOiBaYXAgdHJpZ2dlcmVkIHN1Y2Nlc3NmdWxseSdcbiAgICAgICk7XG4gICAgfSk7XG5cbiAgICBpdCgnc2hvdWxkIHJldHVybiBhbiBlcnJvciBtZXNzYWdlIHdoZW4gdGhlIHphcCBuYW1lIGlzIG1pc3NpbmcnLCBhc3luYyAoKSA9PiB7XG4gICAgICBjb25zdCByZXN1bHQgPSBhd2FpdCBoYW5kbGVUcmlnZ2VyWmFwKHt9KTtcblxuICAgICAgZXhwZWN0KHJlc3VsdCkudG9CZSgnWmFwIG5hbWUgaXMgcmVxdWlyZWQgdG8gdHJpZ2dlciBhIFphcCB2aWEgTkxVLicpO1xuICAgIH0pO1xuXG4gICAgaXQoJ3Nob3VsZCByZXR1cm4gYW4gZXJyb3IgbWVzc2FnZSB3aGVuIGFuIGVycm9yIG9jY3VycycsIGFzeW5jICgpID0+IHtcbiAgICAgICh6YXBpZXJTa2lsbHMudHJpZ2dlclphcCBhcyBqZXN0Lk1vY2spLm1vY2tSZWplY3RlZFZhbHVlKFxuICAgICAgICBuZXcgRXJyb3IoJ1Rlc3QgRXJyb3InKVxuICAgICAgKTtcblxuICAgICAgY29uc3QgcmVzdWx0ID0gYXdhaXQgaGFuZGxlVHJpZ2dlclphcCh7IHphcF9uYW1lOiAndGVzdC16YXAnIH0pO1xuXG4gICAgICBleHBlY3QocmVzdWx0KS50b0JlKFxuICAgICAgICBcIlNvcnJ5LCBJIGNvdWxkbid0IHRyaWdnZXIgdGhlIFphcCBkdWUgdG8gYW4gZXJyb3IgKE5MVSBwYXRoKS5cIlxuICAgICAgKTtcbiAgICB9KTtcbiAgfSk7XG59KTtcbiJdfQ==