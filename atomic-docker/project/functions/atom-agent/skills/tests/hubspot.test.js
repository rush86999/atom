import { handleGetHubSpotContactByEmail, handleCreateHubSpotContact, } from '../hubspot';
import * as hubspotSkills from '../hubspotSkills';
jest.mock('../hubspotSkills', () => ({
    getHubSpotContactByEmail: jest.fn(),
    createHubSpotContact: jest.fn(),
}));
describe('hubspot skill', () => {
    afterEach(() => {
        jest.clearAllMocks();
    });
    describe('handleGetHubSpotContactByEmail', () => {
        it('should return a HubSpot contact', async () => {
            const mockContact = {
                id: 'test-contact-id',
                properties: {
                    firstname: 'Test',
                    lastname: 'User',
                    email: 'test@example.com',
                    company: 'Test Company',
                    createdate: new Date().toISOString(),
                    lastmodifieddate: new Date().toISOString(),
                },
            };
            hubspotSkills.getHubSpotContactByEmail.mockResolvedValue(mockContact);
            const result = await handleGetHubSpotContactByEmail('test-user', {
                email: 'test@example.com',
            });
            expect(result).toContain('HubSpot Contact Found:');
            expect(result).toContain('Test User');
        });
        it('should return a message when no contact is found', async () => {
            hubspotSkills.getHubSpotContactByEmail.mockResolvedValue(null);
            const result = await handleGetHubSpotContactByEmail('test-user', {
                email: 'test@example.com',
            });
            expect(result).toBe('No HubSpot contact found with email: test@example.com.');
        });
        it('should return an error message when the email is missing', async () => {
            const result = await handleGetHubSpotContactByEmail('test-user', {});
            expect(result).toBe('Email is required and must be a non-empty string to get a HubSpot contact by email.');
        });
        it('should return an error message when an error occurs', async () => {
            hubspotSkills.getHubSpotContactByEmail.mockRejectedValue(new Error('Test Error'));
            const result = await handleGetHubSpotContactByEmail('test-user', {
                email: 'test@example.com',
            });
            expect(result).toBe('Sorry, an error occurred while trying to retrieve the HubSpot contact.');
        });
    });
    describe('handleCreateHubSpotContact', () => {
        it('should create a HubSpot contact', async () => {
            const mockContact = {
                id: 'test-contact-id',
                properties: {
                    firstname: 'Test',
                    lastname: 'User',
                    email: 'test@example.com',
                    company: 'Test Company',
                },
            };
            hubspotSkills.createHubSpotContact.mockResolvedValue({
                success: true,
                contactId: 'test-contact-id',
                hubSpotContact: mockContact,
            });
            const result = await handleCreateHubSpotContact('test-user', {
                email: 'test@example.com',
            });
            expect(result).toContain('HubSpot contact created via NLU!');
        });
        it('should return an error message when the email is missing', async () => {
            const result = await handleCreateHubSpotContact('test-user', {});
            expect(result).toBe('Email is required (and must be a string) to create a HubSpot contact via NLU.');
        });
        it('should return an error message when an error occurs', async () => {
            hubspotSkills.createHubSpotContact.mockRejectedValue(new Error('Test Error'));
            const result = await handleCreateHubSpotContact('test-user', {
                email: 'test@example.com',
            });
            expect(result).toBe('Sorry, there was an issue creating the HubSpot contact based on your request.');
        });
    });
});
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiaHVic3BvdC50ZXN0LmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsiaHVic3BvdC50ZXN0LnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiJBQUFBLE9BQU8sRUFDTCw4QkFBOEIsRUFDOUIsMEJBQTBCLEdBQzNCLE1BQU0sWUFBWSxDQUFDO0FBQ3BCLE9BQU8sS0FBSyxhQUFhLE1BQU0sa0JBQWtCLENBQUM7QUFHbEQsSUFBSSxDQUFDLElBQUksQ0FBQyxrQkFBa0IsRUFBRSxHQUFHLEVBQUUsQ0FBQyxDQUFDO0lBQ25DLHdCQUF3QixFQUFFLElBQUksQ0FBQyxFQUFFLEVBQUU7SUFDbkMsb0JBQW9CLEVBQUUsSUFBSSxDQUFDLEVBQUUsRUFBRTtDQUNoQyxDQUFDLENBQUMsQ0FBQztBQUVKLFFBQVEsQ0FBQyxlQUFlLEVBQUUsR0FBRyxFQUFFO0lBQzdCLFNBQVMsQ0FBQyxHQUFHLEVBQUU7UUFDYixJQUFJLENBQUMsYUFBYSxFQUFFLENBQUM7SUFDdkIsQ0FBQyxDQUFDLENBQUM7SUFFSCxRQUFRLENBQUMsZ0NBQWdDLEVBQUUsR0FBRyxFQUFFO1FBQzlDLEVBQUUsQ0FBQyxpQ0FBaUMsRUFBRSxLQUFLLElBQUksRUFBRTtZQUMvQyxNQUFNLFdBQVcsR0FBRztnQkFDbEIsRUFBRSxFQUFFLGlCQUFpQjtnQkFDckIsVUFBVSxFQUFFO29CQUNWLFNBQVMsRUFBRSxNQUFNO29CQUNqQixRQUFRLEVBQUUsTUFBTTtvQkFDaEIsS0FBSyxFQUFFLGtCQUFrQjtvQkFDekIsT0FBTyxFQUFFLGNBQWM7b0JBQ3ZCLFVBQVUsRUFBRSxJQUFJLElBQUksRUFBRSxDQUFDLFdBQVcsRUFBRTtvQkFDcEMsZ0JBQWdCLEVBQUUsSUFBSSxJQUFJLEVBQUUsQ0FBQyxXQUFXLEVBQUU7aUJBQzNDO2FBQ0YsQ0FBQztZQUNELGFBQWEsQ0FBQyx3QkFBc0MsQ0FBQyxpQkFBaUIsQ0FDckUsV0FBVyxDQUNaLENBQUM7WUFFRixNQUFNLE1BQU0sR0FBRyxNQUFNLDhCQUE4QixD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LE1BQU0sMEJBQTBCLENBQUMsV0FBVyxFQUFFO2dCQUMzRCxLQUFLLEVBQUUsa0JBQWtCO2FBQzFCLENBQUMsQ0FBQztZQUVILE1BQU0sQ0FBQyxNQUFNLENBQUMsQ0FBQyxJQUFJLENBQ2pCLCtFQUErRSxDQUNoRixDQUFDO1FBQ0osQ0FBQyxDQUFDLENBQUM7SUFDTCxDQUFDLENBQUMsQ0FBQztBQUNMLENBQUMsQ0FBQyxDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IHtcbiAgaGFuZGxlR2V0SHViU3BvdENvbnRhY3RCeUVtYWlsLFxuICBoYW5kbGVDcmVhdGVIdWJTcG90Q29udGFjdCxcbn0gZnJvbSAnLi4vaHVic3BvdCc7XG5pbXBvcnQgKiBhcyBodWJzcG90U2tpbGxzIGZyb20gJy4uL2h1YnNwb3RTa2lsbHMnO1xuaW1wb3J0IHsgQVRPTV9IVUJTUE9UX1BPUlRBTF9JRCB9IGZyb20gJy4uLy4uL19saWJzL2NvbnN0YW50cyc7XG5cbmplc3QubW9jaygnLi4vaHVic3BvdFNraWxscycsICgpID0+ICh7XG4gIGdldEh1YlNwb3RDb250YWN0QnlFbWFpbDogamVzdC5mbigpLFxuICBjcmVhdGVIdWJTcG90Q29udGFjdDogamVzdC5mbigpLFxufSkpO1xuXG5kZXNjcmliZSgnaHVic3BvdCBza2lsbCcsICgpID0+IHtcbiAgYWZ0ZXJFYWNoKCgpID0+IHtcbiAgICBqZXN0LmNsZWFyQWxsTW9ja3MoKTtcbiAgfSk7XG5cbiAgZGVzY3JpYmUoJ2hhbmRsZUdldEh1YlNwb3RDb250YWN0QnlFbWFpbCcsICgpID0+IHtcbiAgICBpdCgnc2hvdWxkIHJldHVybiBhIEh1YlNwb3QgY29udGFjdCcsIGFzeW5jICgpID0+IHtcbiAgICAgIGNvbnN0IG1vY2tDb250YWN0ID0ge1xuICAgICAgICBpZDogJ3Rlc3QtY29udGFjdC1pZCcsXG4gICAgICAgIHByb3BlcnRpZXM6IHtcbiAgICAgICAgICBmaXJzdG5hbWU6ICdUZXN0JyxcbiAgICAgICAgICBsYXN0bmFtZTogJ1VzZXInLFxuICAgICAgICAgIGVtYWlsOiAndGVzdEBleGFtcGxlLmNvbScsXG4gICAgICAgICAgY29tcGFueTogJ1Rlc3QgQ29tcGFueScsXG4gICAgICAgICAgY3JlYXRlZGF0ZTogbmV3IERhdGUoKS50b0lTT1N0cmluZygpLFxuICAgICAgICAgIGxhc3Rtb2RpZmllZGRhdGU6IG5ldyBEYXRlKCkudG9JU09TdHJpbmcoKSxcbiAgICAgICAgfSxcbiAgICAgIH07XG4gICAgICAoaHVic3BvdFNraWxscy5nZXRIdWJTcG90Q29udGFjdEJ5RW1haWwgYXMgamVzdC5Nb2NrKS5tb2NrUmVzb2x2ZWRWYWx1ZShcbiAgICAgICAgbW9ja0NvbnRhY3RcbiAgICAgICk7XG5cbiAgICAgIGNvbnN0IHJlc3VsdCA9IGF3YWl0IGhhbmRsZUdldEh1YlNwb3RDb250YWN0QnlFbWFpbCgndGVzdC11c2VyJywge1xuICAgICAgICBlbWFpbDogJ3Rlc3RAZXhhbXBsZS5jb20nLFxuICAgICAgfSk7XG5cbiAgICAgIGV4cGVjdChyZXN1bHQpLnRvQ29udGFpbignSHViU3BvdCBDb250YWN0IEZvdW5kOicpO1xuICAgICAgZXhwZWN0KHJlc3VsdCkudG9Db250YWluKCdUZXN0IFVzZXInKTtcbiAgICB9KTtcblxuICAgIGl0KCdzaG91bGQgcmV0dXJuIGEgbWVzc2FnZSB3aGVuIG5vIGNvbnRhY3QgaXMgZm91bmQnLCBhc3luYyAoKSA9PiB7XG4gICAgICAoaHVic3BvdFNraWxscy5nZXRIdWJTcG90Q29udGFjdEJ5RW1haWwgYXMgamVzdC5Nb2NrKS5tb2NrUmVzb2x2ZWRWYWx1ZShcbiAgICAgICAgbnVsbFxuICAgICAgKTtcblxuICAgICAgY29uc3QgcmVzdWx0ID0gYXdhaXQgaGFuZGxlR2V0SHViU3BvdENvbnRhY3RCeUVtYWlsKCd0ZXN0LXVzZXInLCB7XG4gICAgICAgIGVtYWlsOiAndGVzdEBleGFtcGxlLmNvbScsXG4gICAgICB9KTtcblxuICAgICAgZXhwZWN0KHJlc3VsdCkudG9CZShcbiAgICAgICAgJ05vIEh1YlNwb3QgY29udGFjdCBmb3VuZCB3aXRoIGVtYWlsOiB0ZXN0QGV4YW1wbGUuY29tLidcbiAgICAgICk7XG4gICAgfSk7XG5cbiAgICBpdCgnc2hvdWxkIHJldHVybiBhbiBlcnJvciBtZXNzYWdlIHdoZW4gdGhlIGVtYWlsIGlzIG1pc3NpbmcnLCBhc3luYyAoKSA9PiB7XG4gICAgICBjb25zdCByZXN1bHQgPSBhd2FpdCBoYW5kbGVHZXRIdWJTcG90Q29udGFjdEJ5RW1haWwoJ3Rlc3QtdXNlcicsIHt9KTtcblxuICAgICAgZXhwZWN0KHJlc3VsdCkudG9CZShcbiAgICAgICAgJ0VtYWlsIGlzIHJlcXVpcmVkIGFuZCBtdXN0IGJlIGEgbm9uLWVtcHR5IHN0cmluZyB0byBnZXQgYSBIdWJTcG90IGNvbnRhY3QgYnkgZW1haWwuJ1xuICAgICAgKTtcbiAgICB9KTtcblxuICAgIGl0KCdzaG91bGQgcmV0dXJuIGFuIGVycm9yIG1lc3NhZ2Ugd2hlbiBhbiBlcnJvciBvY2N1cnMnLCBhc3luYyAoKSA9PiB7XG4gICAgICAoaHVic3BvdFNraWxscy5nZXRIdWJTcG90Q29udGFjdEJ5RW1haWwgYXMgamVzdC5Nb2NrKS5tb2NrUmVqZWN0ZWRWYWx1ZShcbiAgICAgICAgbmV3IEVycm9yKCdUZXN0IEVycm9yJylcbiAgICAgICk7XG5cbiAgICAgIGNvbnN0IHJlc3VsdCA9IGF3YWl0IGhhbmRsZUdldEh1YlNwb3RDb250YWN0QnlFbWFpbCgndGVzdC11c2VyJywge1xuICAgICAgICBlbWFpbDogJ3Rlc3RAZXhhbXBsZS5jb20nLFxuICAgICAgfSk7XG5cbiAgICAgIGV4cGVjdChyZXN1bHQpLnRvQmUoXG4gICAgICAgICdTb3JyeSwgYW4gZXJyb3Igb2NjdXJyZWQgd2hpbGUgdHJ5aW5nIHRvIHJldHJpZXZlIHRoZSBIdWJTcG90IGNvbnRhY3QuJ1xuICAgICAgKTtcbiAgICB9KTtcbiAgfSk7XG5cbiAgZGVzY3JpYmUoJ2hhbmRsZUNyZWF0ZUh1YlNwb3RDb250YWN0JywgKCkgPT4ge1xuICAgIGl0KCdzaG91bGQgY3JlYXRlIGEgSHViU3BvdCBjb250YWN0JywgYXN5bmMgKCkgPT4ge1xuICAgICAgY29uc3QgbW9ja0NvbnRhY3QgPSB7XG4gICAgICAgIGlkOiAndGVzdC1jb250YWN0LWlkJyxcbiAgICAgICAgcHJvcGVydGllczoge1xuICAgICAgICAgIGZpcnN0bmFtZTogJ1Rlc3QnLFxuICAgICAgICAgIGxhc3RuYW1lOiAnVXNlcicsXG4gICAgICAgICAgZW1haWw6ICd0ZXN0QGV4YW1wbGUuY29tJyxcbiAgICAgICAgICBjb21wYW55OiAnVGVzdCBDb21wYW55JyxcbiAgICAgICAgfSxcbiAgICAgIH07XG4gICAgICAoaHVic3BvdFNraWxscy5jcmVhdGVIdWJTcG90Q29udGFjdCBhcyBqZXN0Lk1vY2spLm1vY2tSZXNvbHZlZFZhbHVlKHtcbiAgICAgICAgc3VjY2VzczogdHJ1ZSxcbiAgICAgICAgY29udGFjdElkOiAndGVzdC1jb250YWN0LWlkJyxcbiAgICAgICAgaHViU3BvdENvbnRhY3Q6IG1vY2tDb250YWN0LFxuICAgICAgfSk7XG5cbiAgICAgIGNvbnN0IHJlc3VsdCA9IGF3YWl0IGhhbmRsZUNyZWF0ZUh1YlNwb3RDb250YWN0KCd0ZXN0LXVzZXInLCB7XG4gICAgICAgIGVtYWlsOiAndGVzdEBleGFtcGxlLmNvbScsXG4gICAgICB9KTtcblxuICAgICAgZXhwZWN0KHJlc3VsdCkudG9Db250YWluKCdIdWJTcG90IGNvbnRhY3QgY3JlYXRlZCB2aWEgTkxVIScpO1xuICAgIH0pO1xuXG4gICAgaXQoJ3Nob3VsZCByZXR1cm4gYW4gZXJyb3IgbWVzc2FnZSB3aGVuIHRoZSBlbWFpbCBpcyBtaXNzaW5nJywgYXN5bmMgKCkgPT4ge1xuICAgICAgY29uc3QgcmVzdWx0ID0gYXdhaXQgaGFuZGxlQ3JlYXRlSHViU3BvdENvbnRhY3QoJ3Rlc3QtdXNlcicsIHt9KTtcblxuICAgICAgZXhwZWN0KHJlc3VsdCkudG9CZShcbiAgICAgICAgJ0VtYWlsIGlzIHJlcXVpcmVkIChhbmQgbXVzdCBiZSBhIHN0cmluZykgdG8gY3JlYXRlIGEgSHViU3BvdCBjb250YWN0IHZpYSBOTFUuJ1xuICAgICAgKTtcbiAgICB9KTtcblxuICAgIGl0KCdzaG91bGQgcmV0dXJuIGFuIGVycm9yIG1lc3NhZ2Ugd2hlbiBhbiBlcnJvciBvY2N1cnMnLCBhc3luYyAoKSA9PiB7XG4gICAgICAoaHVic3BvdFNraWxscy5jcmVhdGVIdWJTcG90Q29udGFjdCBhcyBqZXN0Lk1vY2spLm1vY2tSZWplY3RlZFZhbHVlKFxuICAgICAgICBuZXcgRXJyb3IoJ1Rlc3QgRXJyb3InKVxuICAgICAgKTtcblxuICAgICAgY29uc3QgcmVzdWx0ID0gYXdhaXQgaGFuZGxlQ3JlYXRlSHViU3BvdENvbnRhY3QoJ3Rlc3QtdXNlcicsIHtcbiAgICAgICAgZW1haWw6ICd0ZXN0QGV4YW1wbGUuY29tJyxcbiAgICAgIH0pO1xuXG4gICAgICBleHBlY3QocmVzdWx0KS50b0JlKFxuICAgICAgICAnU29ycnksIHRoZXJlIHdhcyBhbiBpc3N1ZSBjcmVhdGluZyB0aGUgSHViU3BvdCBjb250YWN0IGJhc2VkIG9uIHlvdXIgcmVxdWVzdC4nXG4gICAgICApO1xuICAgIH0pO1xuICB9KTtcbn0pO1xuIl19