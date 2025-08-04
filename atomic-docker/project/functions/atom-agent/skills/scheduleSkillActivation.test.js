import { handleScheduleSkillActivation } from './schedulingSkills';
jest.mock('@/agendaService', () => ({
    agenda: {
        schedule: jest.fn(),
        every: jest.fn(),
    },
}));
describe('handleScheduleSkillActivation', () => {
    it('should call scheduleTask with the correct parameters', async () => {
        const userId = 'test-user';
        const entities = {
            skill_to_schedule: 'SendEmail',
            activation_time: 'tomorrow at 9am',
            skill_entities: {
                to: 'test@example.com',
                subject: 'Test',
                body: 'This is a test',
            },
        };
        const result = await handleScheduleSkillActivation(userId, entities);
        expect(result).toEqual('Task "SendEmail" has been scheduled for tomorrow at 9am.');
    });
});
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoic2NoZWR1bGVTa2lsbEFjdGl2YXRpb24udGVzdC5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbInNjaGVkdWxlU2tpbGxBY3RpdmF0aW9uLnRlc3QudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6IkFBQUEsT0FBTyxFQUFFLDZCQUE2QixFQUFFLE1BQU0sb0JBQW9CLENBQUM7QUFHbkUsSUFBSSxDQUFDLElBQUksQ0FBQyxpQkFBaUIsRUFBRSxHQUFHLEVBQUUsQ0FBQyxDQUFDO0lBQ2xDLE1BQU0sRUFBRTtRQUNOLFFBQVEsRUFBRSxJQUFJLENBQUMsRUFBRSxFQUFFO1FBQ25CLEtBQUssRUFBRSxJQUFJLENBQUMsRUFBRSxFQUFFO0tBQ2pCO0NBQ0YsQ0FBQyxDQUFDLENBQUM7QUFFSixRQUFRLENBQUMsK0JBQStCLEVBQUUsR0FBRyxFQUFFO0lBQzdDLEVBQUUsQ0FBQyxzREFBc0QsRUFBRSxLQUFLLElBQUksRUFBRTtRQUNwRSxNQUFNLE1BQU0sR0FBRyxXQUFXLENBQUM7UUFDM0IsTUFBTSxRQUFRLEdBQUc7WUFDZixpQkFBaUIsRUFBRSxXQUFXO1lBQzlCLGVBQWUsRUFBRSxpQkFBaUI7WUFDbEMsY0FBYyxFQUFFO2dCQUNkLEVBQUUsRUFBRSxrQkFBa0I7Z0JBQ3RCLE9BQU8sRUFBRSxNQUFNO2dCQUNmLElBQUksRUFBRSxnQkFBZ0I7YUFDdkI7U0FDRixDQUFDO1FBRUYsTUFBTSxNQUFNLEdBQUcsTUFBTSw2QkFBNkIsQ0FBQyxNQUFNLEVBQUUsUUFBUSxDQUFDLENBQUM7UUFFckUsTUFBTSxDQUFDLE1BQU0sQ0FBQyxDQUFDLE9BQU8sQ0FDcEIsMERBQTBELENBQzNELENBQUM7SUFDSixDQUFDLENBQUMsQ0FBQztBQUNMLENBQUMsQ0FBQyxDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IHsgaGFuZGxlU2NoZWR1bGVTa2lsbEFjdGl2YXRpb24gfSBmcm9tICcuL3NjaGVkdWxpbmdTa2lsbHMnO1xuaW1wb3J0IHsgc2NoZWR1bGVUYXNrIH0gZnJvbSAnLi9zY2hlZHVsaW5nU2tpbGxzJztcblxuamVzdC5tb2NrKCdAL2FnZW5kYVNlcnZpY2UnLCAoKSA9PiAoe1xuICBhZ2VuZGE6IHtcbiAgICBzY2hlZHVsZTogamVzdC5mbigpLFxuICAgIGV2ZXJ5OiBqZXN0LmZuKCksXG4gIH0sXG59KSk7XG5cbmRlc2NyaWJlKCdoYW5kbGVTY2hlZHVsZVNraWxsQWN0aXZhdGlvbicsICgpID0+IHtcbiAgaXQoJ3Nob3VsZCBjYWxsIHNjaGVkdWxlVGFzayB3aXRoIHRoZSBjb3JyZWN0IHBhcmFtZXRlcnMnLCBhc3luYyAoKSA9PiB7XG4gICAgY29uc3QgdXNlcklkID0gJ3Rlc3QtdXNlcic7XG4gICAgY29uc3QgZW50aXRpZXMgPSB7XG4gICAgICBza2lsbF90b19zY2hlZHVsZTogJ1NlbmRFbWFpbCcsXG4gICAgICBhY3RpdmF0aW9uX3RpbWU6ICd0b21vcnJvdyBhdCA5YW0nLFxuICAgICAgc2tpbGxfZW50aXRpZXM6IHtcbiAgICAgICAgdG86ICd0ZXN0QGV4YW1wbGUuY29tJyxcbiAgICAgICAgc3ViamVjdDogJ1Rlc3QnLFxuICAgICAgICBib2R5OiAnVGhpcyBpcyBhIHRlc3QnLFxuICAgICAgfSxcbiAgICB9O1xuXG4gICAgY29uc3QgcmVzdWx0ID0gYXdhaXQgaGFuZGxlU2NoZWR1bGVTa2lsbEFjdGl2YXRpb24odXNlcklkLCBlbnRpdGllcyk7XG5cbiAgICBleHBlY3QocmVzdWx0KS50b0VxdWFsKFxuICAgICAgJ1Rhc2sgXCJTZW5kRW1haWxcIiBoYXMgYmVlbiBzY2hlZHVsZWQgZm9yIHRvbW9ycm93IGF0IDlhbS4nXG4gICAgKTtcbiAgfSk7XG59KTtcbiJdfQ==