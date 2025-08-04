import { getHubSpotContactByEmail, createHubSpotContact, logEmailToHubSpotContact, getHubSpotContactActivities, } from './hubspotSkills';
import { Client } from '@hubspot/api-client';
import { CONTACT_TO_ENGAGEMENT_ASSOCIATION_TYPE_ID } from './hubspotSkills'; // Import the constant
// Mock an example HubSpotContact for consistent use in tests
const mockApiContactResult = {
    id: '12345',
    properties: {
        hs_object_id: '12345',
        createdate: new Date().toISOString(),
        lastmodifieddate: new Date().toISOString(),
        email: 'test@example.com',
        firstname: 'Test',
        lastname: 'User',
        company: 'Test Company',
    },
    createdAt: new Date(), // Date object
    updatedAt: new Date(), // Date object
    archived: false,
};
// This is how the function is expected to transform it
const mockExpectedContact = {
    id: '12345',
    properties: {
        hs_object_id: '12345',
        createdate: mockApiContactResult.properties.createdate,
        lastmodifieddate: mockApiContactResult.properties.lastmodifieddate,
        email: 'test@example.com',
        firstname: 'Test',
        lastname: 'User',
        company: 'Test Company',
    },
    createdAt: mockApiContactResult.createdAt.toISOString(),
    updatedAt: mockApiContactResult.updatedAt.toISOString(),
    archived: false,
};
// Mock @hubspot/api-client
jest.mock('@hubspot/api-client');
// Contacts API mocks
const mockContactsSearchApi = jest.fn();
const mockContactsBasicApiCreate = jest.fn();
// Engagements API mocks
const mockEngagementsBasicApiCreate = jest.fn();
const mockEngagementsSearchApiDoSearch = jest.fn();
// Associations API V4 mocks
const mockAssociationsV4BasicApiGetPage = jest.fn();
// Mock the Client constructor and its methods more comprehensively
const mockHubSpotClientInstance = {
    crm: {
        contacts: {
            searchApi: { doSearch: mockContactsSearchApi },
            basicApi: { create: mockContactsBasicApiCreate },
        },
        engagements: {
            basicApi: { create: mockEngagementsBasicApiCreate },
            searchApi: { doSearch: mockEngagementsSearchApiDoSearch },
        },
        associations: {
            v4: {
                basicApi: { getPage: mockAssociationsV4BasicApiGetPage },
            },
        },
    },
};
// Mock the default export of the Client
Client.mockImplementation(() => mockHubSpotClientInstance);
// Helper to reset all crm method mocks
const resetAllCrmMocks = () => {
    mockContactsSearchApi.mockReset();
    mockContactsBasicApiCreate.mockReset();
    mockEngagementsBasicApiCreate.mockReset();
    mockEngagementsSearchApiDoSearch.mockReset();
    mockAssociationsV4BasicApiGetPage.mockReset();
};
// Mock constants
jest.mock('../_libs/constants', () => ({
    ATOM_HUBSPOT_API_KEY: 'test-api-key', // Default mock value
}));
// Helper to change the mock API key for specific tests
const setMockApiKey = (key) => {
    jest
        .spyOn(require('../_libs/constants'), 'ATOM_HUBSPOT_API_KEY', 'get')
        .mockReturnValue(key);
};
describe('hubspotSkills', () => {
    let consoleErrorSpy;
    let consoleLogSpy;
    beforeEach(() => {
        // Reset mocks before each test
        resetAllCrmMocks(); // Reset all CRM method mocks
        Client.mockImplementation(() => mockHubSpotClientInstance); // Ensure client is reset
        setMockApiKey('test-api-key'); // Reset to default valid API key
        // Spy on console.error and console.log
        consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => { });
        consoleLogSpy = jest.spyOn(console, 'log').mockImplementation(() => { });
    });
    afterEach(() => {
        // Restore original console spies
        consoleErrorSpy.mockRestore();
        consoleLogSpy.mockRestore();
    });
    describe('getHubSpotContactByEmail', () => {
        const testEmail = 'test@example.com';
        const testUserId = 'user123';
        it('should return a contact if found', async () => {
            mockContactsSearchApi.mockResolvedValue({
                results: [mockApiContactResult],
            });
            const result = await getHubSpotContactByEmail(testUserId, testEmail);
            expect(result).toEqual(mockExpectedContact);
            expect(mockContactsSearchApi).toHaveBeenCalledWith({
                query: testEmail,
                properties: [
                    'email',
                    'firstname',
                    'lastname',
                    'company',
                    'hs_object_id',
                    'createdate',
                    'lastmodifieddate',
                ],
                filterGroups: [
                    {
                        filters: [
                            { propertyName: 'email', operator: 'EQ', value: testEmail },
                        ],
                    },
                ],
            });
            expect(consoleLogSpy).toHaveBeenCalledWith(`getHubSpotContactByEmail called for userId: ${testUserId}, email: ${testEmail}`);
        });
        it('should return null if contact not found', async () => {
            mockContactsSearchApi.mockResolvedValue({ results: [] });
            const result = await getHubSpotContactByEmail(testUserId, testEmail);
            expect(result).toBeNull();
            expect(consoleLogSpy).toHaveBeenCalledWith(`No HubSpot contact found for email: ${testEmail}`);
        });
        it('should return null and log error if API key is missing', async () => {
            setMockApiKey(null); // Simulate missing API key
            const result = await getHubSpotContactByEmail(testUserId, testEmail);
            expect(result).toBeNull();
            expect(consoleErrorSpy).toHaveBeenCalledWith('HubSpot API key not configured.');
            expect(mockContactsSearchApi).not.toHaveBeenCalled();
        });
        it('should return null and log error if HubSpot API call fails', async () => {
            const apiError = new Error('HubSpot API Error');
            apiError.response = { body: 'Some error body' };
            mockContactsSearchApi.mockRejectedValue(apiError);
            const result = await getHubSpotContactByEmail(testUserId, testEmail);
            expect(result).toBeNull();
            expect(consoleErrorSpy).toHaveBeenCalledWith(`Error fetching HubSpot contact by email ${testEmail} for userId ${testUserId}:`, apiError.message);
            expect(consoleErrorSpy).toHaveBeenCalledWith('HubSpot API Error Body:', 'Some error body');
        });
    });
    describe('createHubSpotContact', () => {
        const testUserId = 'user123';
        const contactProperties = {
            email: 'new@example.com',
            firstname: 'New',
            lastname: 'User',
            company: 'New Company',
        };
        it('should create a contact and return success response', async () => {
            const createdApiContact = {
                ...mockApiContactResult,
                id: '67890',
                properties: {
                    ...mockApiContactResult.properties,
                    ...contactProperties,
                },
                createdAt: new Date(),
                updatedAt: new Date(),
            };
            mockContactsBasicApiCreate.mockResolvedValue(createdApiContact);
            const result = await createHubSpotContact(testUserId, contactProperties);
            const expectedCreatedContact = {
                ...mockExpectedContact,
                id: '67890',
                properties: { ...mockExpectedContact.properties, ...contactProperties },
                createdAt: createdApiContact.createdAt.toISOString(),
                updatedAt: createdApiContact.updatedAt.toISOString(),
            };
            expect(result).toEqual({
                success: true,
                contactId: createdApiContact.id,
                message: 'Contact created successfully in HubSpot.',
                hubSpotContact: expectedCreatedContact,
            });
            expect(mockContactsBasicApiCreate).toHaveBeenCalledWith({
                properties: contactProperties,
            });
            expect(consoleLogSpy).toHaveBeenCalledWith(`createHubSpotContact called for userId: ${testUserId} with properties:`, contactProperties);
        });
        it('should return error if email is missing', async () => {
            const propertiesWithoutEmail = {
                firstname: 'No',
                lastname: 'Email',
            };
            const result = await createHubSpotContact(testUserId, propertiesWithoutEmail);
            expect(result).toEqual({
                success: false,
                message: 'Email is required to create a HubSpot contact.',
            });
            expect(mockContactsBasicApiCreate).not.toHaveBeenCalled();
        });
        it('should return error if API key is missing', async () => {
            setMockApiKey(null); // Simulate missing API key
            const result = await createHubSpotContact(testUserId, contactProperties);
            expect(result).toEqual({
                success: false,
                message: 'HubSpot API key not configured.',
            });
            expect(mockContactsBasicApiCreate).not.toHaveBeenCalled();
            expect(consoleErrorSpy).toHaveBeenCalledWith('HubSpot API key not configured.');
        });
        it('should return error and log if HubSpot API call fails', async () => {
            const apiError = new Error('HubSpot Create Error');
            apiError.response = {
                body: Buffer.from(JSON.stringify({ message: 'Detailed API error' })),
            };
            mockContactsBasicApiCreate.mockRejectedValue(apiError);
            const result = await createHubSpotContact(testUserId, contactProperties);
            expect(result.success).toBe(false);
            expect(result.message).toBe('Failed to create contact in HubSpot: Detailed API error');
            expect(consoleErrorSpy).toHaveBeenCalledWith(`Error creating HubSpot contact for userId ${testUserId} with email ${contactProperties.email}:`, apiError.message);
            expect(consoleErrorSpy).toHaveBeenCalledWith('HubSpot API Error Body:', {
                message: 'Detailed API error',
            });
        });
        it('should return specific message if contact already exists (CONFLICT)', async () => {
            const apiConflictError = new Error('Conflict');
            apiConflictError.response = {
                body: Buffer.from(JSON.stringify({
                    message: 'Contact already exists.',
                    category: 'CONFLICT',
                })),
            };
            mockContactsBasicApiCreate.mockRejectedValue(apiConflictError);
            const result = await createHubSpotContact(testUserId, contactProperties);
            expect(result.success).toBe(false);
            expect(result.message).toBe('Failed to create contact in HubSpot: A contact with this email already exists.');
        });
    });
    describe('logEmailToHubSpotContact', () => {
        const userId = 'user-test-123';
        const contactId = 'contact-456';
        const emailDetails = {
            activityTimestamp: Date.now(),
            subject: 'Test Email Subject',
            htmlBody: '<p>This is a test email body.</p>',
            direction: 'OUTGOING',
        };
        const mockEngagementId = 'eng-789';
        const mockCreatedDate = new Date();
        const mockUpdatedDate = new Date();
        const mockEngagementApiResponse = {
            id: mockEngagementId,
            properties: {
                hs_object_id: mockEngagementId,
                hs_engagement_type: 'EMAIL',
                hs_timestamp: emailDetails.activityTimestamp.toString(),
                hs_email_subject: emailDetails.subject,
                hs_body_preview: emailDetails.htmlBody.substring(0, 512),
                hs_email_direction: emailDetails.direction,
                createdate: mockCreatedDate.toISOString(),
                lastmodifieddate: mockUpdatedDate.toISOString(),
            },
            createdAt: mockCreatedDate,
            updatedAt: mockUpdatedDate,
            archived: false,
            associations: {},
        };
        it('should successfully log an email and return engagement details', async () => {
            mockEngagementsBasicApiCreate.mockResolvedValue(mockEngagementApiResponse);
            const result = await logEmailToHubSpotContact(userId, contactId, emailDetails);
            expect(result.success).toBe(true);
            expect(result.engagementId).toBe(mockEngagementId);
            expect(result.message).toBe('Email logged successfully to HubSpot contact.');
            expect(result.hubSpotEngagement).toBeDefined();
            expect(result.hubSpotEngagement?.id).toBe(mockEngagementId);
            expect(result.hubSpotEngagement?.properties.hs_email_subject).toBe(emailDetails.subject);
            expect(mockEngagementsBasicApiCreate).toHaveBeenCalledWith({
                properties: {
                    hs_timestamp: emailDetails.activityTimestamp.toString(),
                    hs_engagement_type: 'EMAIL',
                    hs_email_subject: emailDetails.subject,
                    hs_body_preview: emailDetails.htmlBody.substring(0, 512),
                    hs_email_direction: emailDetails.direction,
                },
                associations: [
                    {
                        to: { id: contactId },
                        types: [
                            {
                                associationCategory: 'HUBSPOT_DEFINED',
                                associationTypeId: CONTACT_TO_ENGAGEMENT_ASSOCIATION_TYPE_ID,
                            },
                        ],
                    },
                ],
            });
            expect(consoleLogSpy).toHaveBeenCalledWith(`logEmailToHubSpotContact called for userId: ${userId}, contactId: ${contactId}`);
        });
        it('should return error if API key is missing', async () => {
            setMockApiKey(null);
            const result = await logEmailToHubSpotContact(userId, contactId, emailDetails);
            expect(result.success).toBe(false);
            expect(result.message).toBe('HubSpot API key not configured.');
            expect(mockEngagementsBasicApiCreate).not.toHaveBeenCalled();
        });
        it('should return error if HubSpot API create call fails', async () => {
            const apiError = new Error('HubSpot API Create Engagement Error');
            apiError.response = {
                body: Buffer.from(JSON.stringify({ message: 'Detailed creation error' })),
            };
            mockEngagementsBasicApiCreate.mockRejectedValue(apiError);
            const result = await logEmailToHubSpotContact(userId, contactId, emailDetails);
            expect(result.success).toBe(false);
            expect(result.message).toBe('Failed to log email to HubSpot: Detailed creation error');
            expect(consoleErrorSpy).toHaveBeenCalledWith(`Error logging email to HubSpot contact ${contactId} for userId ${userId}:`, apiError.message);
        });
        it('should return error if contactId is missing', async () => {
            const result = await logEmailToHubSpotContact(userId, '', emailDetails);
            expect(result).toEqual({
                success: false,
                message: 'Contact ID is required to log an email.',
            });
            expect(mockEngagementsBasicApiCreate).not.toHaveBeenCalled();
        });
        it('should return error if essential emailDetails are missing', async () => {
            // @ts-ignore
            const result = await logEmailToHubSpotContact(userId, contactId, {
                subject: 'missing other fields',
            });
            expect(result).toEqual({
                success: false,
                message: 'Email details (activityTimestamp, subject, htmlBody) are required.',
            });
            expect(mockEngagementsBasicApiCreate).not.toHaveBeenCalled();
        });
    });
    describe('getHubSpotContactActivities', () => {
        const userId = 'user-test-456';
        const contactId = 'contact-789';
        const mockEngagementId1 = 'eng-111';
        const mockEngagementId2 = 'eng-222';
        const mockAssociationPage = (ids) => ({
            results: ids.map((id) => ({
                toObjectId: id,
                type: 'contact_to_engagement',
            })), // Simplified, check actual type string if needed
            paging: {
                next: { after: ids.length > 0 ? 'nextpagecursor' : undefined },
            },
        });
        const mockEngagementSearchResult = (id, type = 'EMAIL') => ({
            id,
            properties: {
                hs_object_id: id,
                hs_engagement_type: type,
                hs_timestamp: new Date().toISOString(),
                hs_email_subject: `Subject for ${id}`,
                hs_body_preview: `Body for ${id}`,
                createdate: new Date().toISOString(),
                lastmodifieddate: new Date().toISOString(),
            },
            createdAt: new Date(),
            updatedAt: new Date(),
            archived: false,
        });
        it('should retrieve activities with default filters', async () => {
            mockAssociationsV4BasicApiGetPage.mockResolvedValue(mockAssociationPage([mockEngagementId1, mockEngagementId2]));
            mockEngagementsSearchApiDoSearch.mockResolvedValue({
                results: [
                    mockEngagementSearchResult(mockEngagementId1),
                    mockEngagementSearchResult(mockEngagementId2),
                ],
                paging: { next: { after: 'nextSearchCursor' } },
            });
            const result = await getHubSpotContactActivities(userId, contactId);
            expect(result.success).toBe(true);
            expect(result.activities.length).toBe(2);
            expect(result.activities[0].id).toBe(mockEngagementId1);
            expect(result.nextPage).toBe('nextSearchCursor'); // This should be from searchApi.doSearch paging
            expect(mockAssociationsV4BasicApiGetPage).toHaveBeenCalledWith('0-1', contactId, '0-31', undefined, 50);
            expect(mockEngagementsSearchApiDoSearch).toHaveBeenCalledWith(expect.objectContaining({
                filterGroups: [
                    {
                        filters: [
                            {
                                propertyName: 'hs_object_id',
                                operator: 'IN',
                                values: [mockEngagementId1, mockEngagementId2],
                            },
                        ],
                    },
                ],
                limit: 10,
                sorts: [{ propertyName: 'hs_timestamp', direction: 'DESCENDING' }],
            }));
        });
        it('should retrieve activities with specific filters (EMAIL, limit 5, ASC, since)', async () => {
            const sinceDate = new Date('2023-01-01T00:00:00.000Z');
            const sinceTimestamp = sinceDate.getTime().toString();
            mockAssociationsV4BasicApiGetPage.mockResolvedValue(mockAssociationPage([mockEngagementId1]));
            mockEngagementsSearchApiDoSearch.mockResolvedValue({
                results: [mockEngagementSearchResult(mockEngagementId1, 'EMAIL')],
            });
            await getHubSpotContactActivities(userId, contactId, {
                activityTypes: ['EMAIL'],
                limit: 5,
                sort: 'ASC',
                since: sinceDate.toISOString(),
            });
            expect(mockEngagementsSearchApiDoSearch).toHaveBeenCalledWith(expect.objectContaining({
                filterGroups: [
                    {
                        filters: expect.arrayContaining([
                            {
                                propertyName: 'hs_engagement_type',
                                operator: 'IN',
                                values: ['EMAIL'],
                            },
                            {
                                propertyName: 'hs_timestamp',
                                operator: 'GTE',
                                value: sinceTimestamp,
                            },
                            {
                                propertyName: 'hs_object_id',
                                operator: 'IN',
                                values: [mockEngagementId1],
                            },
                        ]),
                    },
                ],
                limit: 5,
                sorts: [{ propertyName: 'hs_timestamp', direction: 'ASCENDING' }],
            }));
        });
        it('should return empty activities if no associations found', async () => {
            mockAssociationsV4BasicApiGetPage.mockResolvedValue(mockAssociationPage([])); // No associations
            const result = await getHubSpotContactActivities(userId, contactId);
            expect(result.success).toBe(true);
            expect(result.activities.length).toBe(0);
            expect(result.message).toBe('No activities found for this contact.');
            expect(mockEngagementsSearchApiDoSearch).not.toHaveBeenCalled();
        });
        it('should return empty activities if associations found but search returns none', async () => {
            mockAssociationsV4BasicApiGetPage.mockResolvedValue(mockAssociationPage([mockEngagementId1]));
            mockEngagementsSearchApiDoSearch.mockResolvedValue({ results: [] }); // Search returns no items
            const result = await getHubSpotContactActivities(userId, contactId);
            expect(result.success).toBe(true);
            expect(result.activities.length).toBe(0);
            expect(result.message).toBe('No activities found matching criteria.');
        });
        it('should return error if API key is missing', async () => {
            setMockApiKey(null);
            const result = await getHubSpotContactActivities(userId, contactId);
            expect(result.success).toBe(false);
            expect(result.message).toBe('HubSpot API key not configured.');
            expect(mockAssociationsV4BasicApiGetPage).not.toHaveBeenCalled();
            expect(mockEngagementsSearchApiDoSearch).not.toHaveBeenCalled();
        });
        it('should return error if associations API call fails', async () => {
            const apiError = new Error('Assoc API Error');
            mockAssociationsV4BasicApiGetPage.mockRejectedValue(apiError);
            const result = await getHubSpotContactActivities(userId, contactId);
            expect(result.success).toBe(false);
            expect(result.message).toContain('Failed to fetch contact activities: Assoc API Error');
            expect(consoleErrorSpy).toHaveBeenCalledWith(`Error fetching HubSpot contact activities for contact ${contactId}, userId ${userId}:`, apiError.message);
        });
        it('should return error if engagements search API call fails', async () => {
            mockAssociationsV4BasicApiGetPage.mockResolvedValue(mockAssociationPage([mockEngagementId1]));
            const apiError = new Error('Search API Error');
            mockEngagementsSearchApiDoSearch.mockRejectedValue(apiError);
            const result = await getHubSpotContactActivities(userId, contactId);
            expect(result.success).toBe(false);
            expect(result.message).toContain('Failed to fetch contact activities: Search API Error');
        });
        it('should return error if contactId is missing', async () => {
            const result = await getHubSpotContactActivities(userId, '');
            expect(result).toEqual({
                success: false,
                activities: [],
                message: 'Contact ID is required.',
            });
            expect(mockAssociationsV4BasicApiGetPage).not.toHaveBeenCalled();
        });
    });
});
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiaHVic3BvdFNraWxscy50ZXN0LmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsiaHVic3BvdFNraWxscy50ZXN0LnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiJBQUFBLE9BQU8sRUFDTCx3QkFBd0IsRUFDeEIsb0JBQW9CLEVBQ3BCLHdCQUF3QixFQUN4QiwyQkFBMkIsR0FDNUIsTUFBTSxpQkFBaUIsQ0FBQztBQUV6QixPQUFPLEVBQUUsTUFBTSxFQUFFLE1BQU0scUJBQXFCLENBQUM7QUFXN0MsT0FBTyxFQUFFLHlDQUF5QyxFQUFFLE1BQU0saUJBQWlCLENBQUMsQ0FBQyxzQkFBc0I7QUFFbkcsNkRBQTZEO0FBQzdELE1BQU0sb0JBQW9CLEdBQUc7SUFDM0IsRUFBRSxFQUFFLE9BQU87SUFDWCxVQUFVLEVBQUU7UUFDVixZQUFZLEVBQUUsT0FBTztRQUNyQixVQUFVLEVBQUUsSUFBSSxJQUFJLEVBQUUsQ0FBQyxXQUFXLEVBQUU7UUFDcEMsZ0JBQWdCLEVBQUUsSUFBSSxJQUFJLEVBQUUsQ0FBQyxXQUFXLEVBQUU7UUFDMUMsS0FBSyxFQUFFLGtCQUFrQjtRQUN6QixTQUFTLEVBQUUsTUFBTTtRQUNqQixRQUFRLEVBQUUsTUFBTTtRQUNoQixPQUFPLEVBQUUsY0FBYztLQUN4QjtJQUNELFNBQVMsRUFBRSxJQUFJLElBQUksRUFBRSxFQUFFLGNBQWM7SUFDckMsU0FBUyxFQUFFLElBQUksSUFBSSxFQUFFLEVBQUUsY0FBYztJQUNyQyxRQUFRLEVBQUUsS0FBSztDQUNoQixDQUFDO0FBRUYsdURBQXVEO0FBQ3ZELE1BQU0sbUJBQW1CLEdBQW1CO0lBQzFDLEVBQUUsRUFBRSxPQUFPO0lBQ1gsVUFBVSxFQUFFO1FBQ1YsWUFBWSxFQUFFLE9BQU87UUFDckIsVUFBVSxFQUFFLG9CQUFvQixDQUFDLFVBQVUsQ0FBQyxVQUFVO1FBQ3RELGdCQUFnQixFQUFFLG9CQUFvQixDQUFDLFVBQVUsQ0FBQyxnQkFBZ0I7UUFDbEUsS0FBSyxFQUFFLGtCQUFrQjtR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SCxFQUFFLENBQUMsNkNBQTZDLEVBQUUsS0FBSyxJQUFJLEVBQUU7WUFDM0QsTUFBTSxNQUFNLEdBQUcsTUFBTSwyQkFBMkIsQ0FBQyxNQUFNLEVBQUUsRUFBRSxDQUFDLENBQUM7WUFDN0QsTUFBTSxDQUFDLE1BQU0sQ0FBQyxDQUFDLE9BQU8sQ0FBQztnQkFDckIsT0FBTyxFQUFFLEtBQUs7Z0JBQ2QsVUFBVSxFQUFFLEVBQUU7Z0JBQ2QsT0FBTyxFQUFFLHlCQUF5QjthQUNuQyxDQUFDLENBQUM7WUFDSCxNQUFNLENBQUMsaUNBQWlDLENBQUMsQ0FBQyxHQUFHLENBQUMsZ0JBQWdCLEVBQUUsQ0FBQztRQUNuRSxDQUFDLENBQUMsQ0FBQztJQUNMLENBQUMsQ0FBQyxDQUFDO0FBQ0wsQ0FBQyxDQUFDLENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQge1xuICBnZXRIdWJTcG90Q29udGFjdEJ5RW1haWwsXG4gIGNyZWF0ZUh1YlNwb3RDb250YWN0LFxuICBsb2dFbWFpbFRvSHViU3BvdENvbnRhY3QsXG4gIGdldEh1YlNwb3RDb250YWN0QWN0aXZpdGllcyxcbn0gZnJvbSAnLi9odWJzcG90U2tpbGxzJztcbmltcG9ydCB7IEFUT01fSFVCU1BPVF9BUElfS0VZIH0gZnJvbSAnLi4vX2xpYnMvY29uc3RhbnRzJztcbmltcG9ydCB7IENsaWVudCB9IGZyb20gJ0BodWJzcG90L2FwaS1jbGllbnQnO1xuaW1wb3J0IHtcbiAgSHViU3BvdENvbnRhY3RQcm9wZXJ0aWVzLFxuICBHZXRIdWJTcG90Q29udGFjdFJlc3BvbnNlLFxuICBDcmVhdGVIdWJTcG90Q29udGFjdFJlc3BvbnNlLFxuICBIdWJTcG90Q29udGFjdCxcbiAgSHViU3BvdEVtYWlsRW5nYWdlbWVudFByb3BlcnRpZXMsXG4gIEh1YlNwb3RFbmdhZ2VtZW50LFxuICBMb2dFbmdhZ2VtZW50UmVzcG9uc2UsXG4gIEdldENvbnRhY3RBY3Rpdml0aWVzUmVzcG9uc2UsXG59IGZyb20gJy4uL3R5cGVzJztcbmltcG9ydCB7IENPTlRBQ1RfVE9fRU5HQUdFTUVOVF9BU1NPQ0lBVElPTl9UWVBFX0lEIH0gZnJvbSAnLi9odWJzcG90U2tpbGxzJzsgLy8gSW1wb3J0IHRoZSBjb25zdGFudFxuXG4vLyBNb2NrIGFuIGV4YW1wbGUgSHViU3BvdENvbnRhY3QgZm9yIGNvbnNpc3RlbnQgdXNlIGluIHRlc3RzXG5jb25zdCBtb2NrQXBpQ29udGFjdFJlc3VsdCA9IHtcbiAgaWQ6ICcxMjM0NScsXG4gIHByb3BlcnRpZXM6IHtcbiAgICBoc19vYmplY3RfaWQ6ICcxMjM0NScsXG4gICAgY3JlYXRlZGF0ZTogbmV3IERhdGUoKS50b0lTT1N0cmluZygpLFxuICAgIGxhc3Rtb2RpZmllZGRhdGU6IG5ldyBEYXRlKCkudG9JU09TdHJpbmcoKSxcbiAgICBlbWFpbDogJ3Rlc3RAZXhhbXBsZS5jb20nLFxuICAgIGZpcnN0bmFtZTogJ1Rlc3QnLFxuICAgIGxhc3RuYW1lOiAnVXNlcicsXG4gICAgY29tcGFueTogJ1Rlc3QgQ29tcGFueScsXG4gIH0sXG4gIGNyZWF0ZWRBdDogbmV3IERhdGUoKSwgLy8gRGF0ZSBvYmplY3RcbiAgdXBkYXRlZEF0OiBuZXcgRGF0ZSgpLCAvLyBEYXRlIG9iamVjdFxuICBhcmNoaXZlZDogZmFsc2UsXG59O1xuXG4vLyBUaGlzIGlzIGhvdyB0aGUgZnVuY3Rpb24gaXMgZXhwZWN0ZWQgdG8gdHJhbnNmb3JtIGl0XG5jb25zdCBtb2NrRXhwZWN0ZWRDb250YWN0OiBIdWJTcG90Q29udGFjdCA9IHtcbiAgaWQ6ICcxMjM0NScsXG4gIHByb3BlcnRpZXM6IHtcbiAgICBoc19vYmplY3RfaWQ6ICcxMjM0NScsXG4gICAgY3JlYXRlZGF0ZTogbW9ja0FwaUNvbnRhY3RSZXN1bHQucHJvcGVydGllcy5jcmVhdGVkYXRlLFxuICAgIGxhc3Rtb2RpZmllZGRhdGU6IG1vY2tBcGlDb250YWN0UmVzdWx0LnByb3BlcnRpZXMubGFzdG1vZGlmaWVkZGF0ZSxcbiAgICBlbWFpbDogJ3Rlc3RAZXhhbXBsZS5jb20nLFxuICAgIGZpcnN0bmFtZTogJ1Rlc3QnLFxuICAgIGxhc3RuYW1lOiAnVXNlcicsXG4gICAgY29tcGFueTogJ1Rlc3QgQ29tcGFueScsXG4gIH0sXG4gIGNyZWF0ZWRBdDogbW9ja0FwaUNvbnRhY3RSZXN1bHQuY3JlYXRlZEF0LnRvSVNPU3RyaW5nKCksXG4gIHVwZGF0ZWRBdDogbW9ja0FwaUNvbnRhY3RSZXN1bHQudXBkYXRlZEF0LnRvSVNPU3RyaW5nKCksXG4gIGFyY2hpdmVkOiBmYWxzZSxcbn07XG5cbi8vIE1vY2sgQGh1YnNwb3QvYXBpLWNsaWVudFxuamVzdC5tb2NrKCdAaHVic3BvdC9hcGktY2xpZW50Jyk7XG5cbi8vIENvbnRhY3RzIEFQSSBtb2Nrc1xuY29uc3QgbW9ja0NvbnRhY3RzU2VhcmNoQXBpID0gamVzdC5mbigpO1xuY29uc3QgbW9ja0NvbnRhY3RzQmFzaWNBcGlDcmVhdGUgPSBqZXN0LmZuKCk7XG5cbi8vIEVuZ2FnZW1lbnRzIEFQSSBtb2Nrc1xuY29uc3QgbW9ja0VuZ2FnZW1lbnRzQmFzaWNBcGlDcmVhdGUgPSBqZXN0LmZuKCk7XG5jb25zdCBtb2NrRW5nYWdlbWVudHNTZWFyY2hBcGlEb1NlYXJjaCA9IGplc3QuZm4oKTtcblxuLy8gQXNzb2NpYXRpb25zIEFQSSBWNCBtb2Nrc1xuY29uc3QgbW9ja0Fzc29jaWF0aW9uc1Y0QmFzaWNBcGlHZXRQYWdlID0gamVzdC5mbigpO1xuXG4vLyBNb2NrIHRoZSBDbGllbnQgY29uc3RydWN0b3IgYW5kIGl0cyBtZXRob2RzIG1vcmUgY29tcHJlaGVuc2l2ZWx5XG5jb25zdCBtb2NrSHViU3BvdENsaWVudEluc3RhbmNlID0ge1xuICBjcm06IHtcbiAgICBjb250YWN0czoge1xuICAgICAgc2VhcmNoQXBpOiB7IGRvU2VhcmNoOiBtb2NrQ29udGFjdHNTZWFyY2hBcGkgfSxcbiAgICAgIGJhc2ljQXBpOiB7IGNyZWF0ZTogbW9ja0NvbnRhY3RzQmFzaWNBcGlDcmVhdGUgfSxcbiAgICB9LFxuICAgIGVuZ2FnZW1lbnRzOiB7XG4gICAgICBiYXNpY0FwaTogeyBjcmVhdGU6IG1vY2tFbmdhZ2VtZW50c0Jhc2ljQXBpQ3JlYXRlIH0sXG4gICAgICBzZWFyY2hBcGk6IHsgZG9TZWFyY2g6IG1vY2tFbmdhZ2VtZW50c1NlYXJjaEFwaURvU2VhcmNoIH0sXG4gICAgfSxcbiAgICBhc3NvY2lhdGlvbnM6IHtcbiAgICAgIHY0OiB7XG4gICAgICAgIGJhc2ljQXBpOiB7IGdldFBhZ2U6IG1vY2tBc3NvY2lhdGlvbnNWNEJhc2ljQXBpR2V0UGFnZSB9LFxuICAgICAgfSxcbiAgICB9LFxuICB9LFxufTtcblxuLy8gTW9jayB0aGUgZGVmYXVsdCBleHBvcnQgb2YgdGhlIENsaWVudFxuKENsaWVudCBhcyBqZXN0Lk1vY2spLm1vY2tJbXBsZW1lbnRhdGlvbigoKSA9PiBtb2NrSHViU3BvdENsaWVudEluc3RhbmNlKTtcblxuLy8gSGVscGVyIHRvIHJlc2V0IGFsbCBjcm0gbWV0aG9kIG1vY2tzXG5jb25zdCByZXNldEFsbENybU1vY2tzID0gKCkgPT4ge1xuICBtb2NrQ29udGFjdHNTZWFyY2hBcGkubW9ja1Jlc2V0KCk7XG4gIG1vY2tDb250YWN0c0Jhc2ljQXBpQ3JlYXRlLm1vY2tSZXNldCgpO1xuICBtb2NrRW5nYWdlbWVudHNCYXNpY0FwaUNyZWF0ZS5tb2NrUmVzZXQoKTtcbiAgbW9ja0VuZ2FnZW1lbnRzU2VhcmNoQXBpRG9TZWFyY2gubW9ja1Jlc2V0KCk7XG4gIG1vY2tBc3NvY2lhdGlvbnNWNEJhc2ljQXBpR2V0UGFnZS5tb2NrUmVzZXQoKTtcbn07XG5cbi8vIE1vY2sgY29uc3RhbnRzXG5qZXN0Lm1vY2soJy4uL19saWJzL2NvbnN0YW50cycsICgpID0+ICh7XG4gIEFUT01fSFVCU1BPVF9BUElfS0VZOiAndGVzdC1hcGkta2V5JywgLy8gRGVmYXVsdCBtb2NrIHZhbHVlXG59KSk7XG5cbi8vIEhlbHBlciB0byBjaGFuZ2UgdGhlIG1vY2sgQVBJIGtleSBmb3Igc3BlY2lmaWMgdGVzdHNcbmNvbnN0IHNldE1vY2tBcGlLZXkgPSAoa2V5OiBzdHJpbmcgfCBudWxsKSA9PiB7XG4gIGplc3RcbiAgICAuc3B5T24ocmVxdWlyZSgnLi4vX2xpYnMvY29uc3RhbnRzJyksICdBVE9NX0hVQlNQT1RfQVBJX0tFWScsICdnZXQnKVxuICAgIC5tb2NrUmV0dXJuVmFsdWUoa2V5KTtcbn07XG5cbmRlc2NyaWJlKCdodWJzcG90U2tpbGxzJywgKCkgPT4ge1xuICBsZXQgY29uc29sZUVycm9yU3B5OiBqZXN0LlNweUluc3RhbmNlO1xuICBsZXQgY29uc29sZUxvZ1NweTogamVzdC5TcHlJbnN0YW5jZTtcblxuICBiZWZvcmVFYWNoKCgpID0+IHtcbiAgICAvLyBSZXNldCBtb2NrcyBiZWZvcmUgZWFjaCB0ZXN0XG4gICAgcmVzZXRBbGxDcm1Nb2NrcygpOyAvLyBSZXNldCBhbGwgQ1JNIG1ldGhvZCBtb2Nrc1xuICAgIChDbGllbnQgYXMgamVzdC5Nb2NrKS5tb2NrSW1wbGVtZW50YXRpb24oKCkgPT4gbW9ja0h1YlNwb3RDbGllbnRJbnN0YW5jZSk7IC8vIEVuc3VyZSBjbGllbnQgaXMgcmVzZXRcbiAgICBzZXRNb2NrQXBpS2V5KCd0ZXN0LWFwaS1rZXknKTsgLy8gUmVzZXQgdG8gZGVmYXVsdCB2YWxpZCBBUEkga2V5XG5cbiAgICAvLyBTcHkgb24gY29uc29sZS5lcnJvciBhbmQgY29uc29sZS5sb2dcbiAgICBjb25zb2xlRXJyb3JTcHkgPSBqZXN0LnNweU9uKGNvbnNvbGUsICdlcnJvcicpLm1vY2tJbXBsZW1lbnRhdGlvbigoKSA9PiB7fSk7XG4gICAgY29uc29sZUxvZ1NweSA9IGplc3Quc3B5T24oY29uc29sZSwgJ2xvZycpLm1vY2tJbXBsZW1lbnRhdGlvbigoKSA9PiB7fSk7XG4gIH0pO1xuXG4gIGFmdGVyRWFjaCgoKSA9PiB7XG4gICAgLy8gUmVzdG9yZSBvcmlnaW5hbCBjb25zb2xlIHNwaWVzXG4gICAgY29uc29sZUVycm9yU3B5Lm1vY2tSZXN0b3JlKCk7XG4gICAgY29uc29sZUxvZ1NweS5tb2NrUmVzdG9yZSgpO1xuICB9KTtcblxuICBkZXNjcmliZSgnZ2V0SHViU3BvdENvbnRhY3RCeUVtYWlsJywgKCkgPT4ge1xuICAgIGNvbnN0IHRlc3RFbWFpbCA9ICd0ZXN0QGV4YW1wbGUuY29tJztcbiAgICBjb25zdCB0ZXN0VXNlcklkID0gJ3VzZXIxMjMnO1xuXG4gICAgaXQoJ3Nob3VsZCByZXR1cm4gYSBjb250YWN0IGlmIGZvdW5kJywgYXN5bmMgKCkgPT4ge1xuICAgICAgbW9ja0NvbnRhY3RzU2VhcmNoQXBpLm1vY2tSZXNvbHZlZFZhbHVlKHtcbiAgICAgICAgcmVzdWx0czogW21vY2tBcGlDb250YWN0UmVzdWx0XSxcbiAgICAgIH0pO1xuICAgICAgY29uc3QgcmVzdWx0ID0gYXdhaXQgZ2V0SHViU3BvdENvbnRhY3RCeUVtYWlsKHRlc3RVc2VySWQsIHRlc3RFbWFpbCk7XG4gICAgICBleHBlY3QocmVzdWx0KS50b0VxdWFsKG1vY2tFeHBlY3RlZENvbnRhY3QpO1xuICAgICAgZXhwZWN0KG1vY2tDb250YWN0c1NlYXJjaEFwaSkudG9IYXZlQmVlbkNhbGxlZFdpdGgoe1xuICAgICAgICBxdWVyeTogdGVzdEVtYWlsLFxuICAgICAgICBwcm9wZXJ0aWVzOiBbXG4gICAgICAgICAgJ2VtYWlsJyxcbiAgICAgICAgICAnZmlyc3RuYW1lJyxcbiAgICAgICAgICAnbGFzdG5hbWUnLFxuICAgICAgICAgICdjb21wYW55JyxcbiAgICAgICAgICAnaHNfb2JqZWN0X2lkJyxcbiAgICAgICAgICAnY3JlYXRlZGF0ZScsXG4gICAgICAgICAgJ2xhc3Rtb2RpZmllZGRhdGUnLFxuICAgICAgICBdLFxuICAgICAgICBmaWx0ZXJHcm91cHM6IFtcbiAgICAgICAgICB7XG4gICAgICAgICAgICBmaWx0ZXJzOiBbXG4gICAgICAgICAgICAgIHsgcHJvcGVydHlOYW1lOiAnZW1haWwnLCBvcGVyYXRvcjogJ0VRJywgdmFsdWU6IHRlc3RFbWFpbCB9LFxuICAgICAgICAgICAgXSxcbiAgICAgICAgICB9LFxuICAgICAgICBdLFxuICAgICAgfSk7XG4gICAgICBleHBlY3QoY29uc29sZUxvZ1NweSkudG9IYXZlQmVlbkNhbGxlZFdpdGgoXG4gICAgICAgIGBnZXRIdWJTcG90Q29udGFjdEJ5RW1haWwgY2FsbGVkIGZvciB1c2VySWQ6ICR7dGVzdFVzZXJJZH0sIGVtYWlsOiAke3Rlc3RFbWFpbH1gXG4gICAgICApO1xuICAgIH0pO1xuXG4gICAgaXQoJ3Nob3VsZCByZXR1cm4gbnVsbCBpZiBjb250YWN0IG5vdCBmb3VuZCcsIGFzeW5jICgpID0+IHtcbiAgICAgIG1vY2tDb250YWN0c1NlYXJjaEFwaS5tb2NrUmVzb2x2ZWRWYWx1ZSh7IHJlc3VsdHM6IFtdIH0pO1xuICAgICAgY29uc3QgcmVzdWx0ID0gYXdhaXQgZ2V0SHViU3BvdENvbnRhY3RCeUVtYWlsKHRlc3RVc2VySWQsIHRlc3RFbWFpbCk7XG4gICAgICBleHBlY3QocmVzdWx0KS50b0JlTnVsbCgpO1xuICAgICAgZXhwZWN0KGNvbnNvbGVMb2dTcHkpLnRvSGF2ZUJlZW5DYWxsZWRXaXRoKFxuICAgICAgICBgTm8gSHViU3BvdCBjb250YWN0IGZvdW5kIGZvciBlbWFpbDogJHt0ZXN0RW1haWx9YFxuICAgICAgKTtcbiAgICB9KTtcblxuICAgIGl0KCdzaG91bGQgcmV0dXJuIG51bGwgYW5kIGxvZyBlcnJvciBpZiBBUEkga2V5IGlzIG1pc3NpbmcnLCBhc3luYyAoKSA9PiB7XG4gICAgICBzZXRNb2NrQXBpS2V5KG51bGwpOyAvLyBTaW11bGF0ZSBtaXNzaW5nIEFQSSBrZXlcbiAgICAgIGNvbnN0IHJlc3VsdCA9IGF3YWl0IGdldEh1YlNwb3RDb250YWN0QnlFbWFpbCh0ZXN0VXNlcklkLCB0ZXN0RW1haWwpO1xuICAgICAgZXhwZWN0KHJlc3VsdCkudG9CZU51bGwoKTtcbiAgICAgIGV4cGVjdChjb25zb2xlRXJyb3JTcHkpLnRvSGF2ZUJlZW5DYWxsZWRXaXRoKFxuICAgICAgICAnSHViU3BvdCBBUEkga2V5IG5vdCBjb25maWd1cmVkLidcbiAgICAgICk7XG4gICAgICBleHBlY3QobW9ja0NvbnRhY3RzU2VhcmNoQXBpKS5ub3QudG9IYXZlQmVlbkNhbGxlZCgpO1xuICAgIH0pO1xuXG4gICAgaXQoJ3Nob3VsZCByZXR1cm4gbnVsbCBhbmQgbG9nIGVycm9yIGlmIEh1YlNwb3QgQVBJIGNhbGwgZmFpbHMnLCBhc3luYyAoKSA9PiB7XG4gICAgICBjb25zdCBhcGlFcnJvciA9IG5ldyBFcnJvcignSHViU3BvdCBBUEkgRXJyb3InKTtcbiAgICAgIChhcGlFcnJvciBhcyBhbnkpLnJlc3BvbnNlID0geyBib2R5OiAnU29tZSBlcnJvciBib2R5JyB9O1xuICAgICAgbW9ja0NvbnRhY3RzU2VhcmNoQXBpLm1vY2tSZWplY3RlZFZhbHVlKGFwaUVycm9yKTtcbiAgICAgIGNvbnN0IHJlc3VsdCA9IGF3YWl0IGdldEh1YlNwb3RDb250YWN0QnlFbWFpbCh0ZXN0VXNlcklkLCB0ZXN0RW1haWwpO1xuICAgICAgZXhwZWN0KHJlc3VsdCkudG9CZU51bGwoKTtcbiAgICAgIGV4cGVjdChjb25zb2xlRXJyb3JTcHkpLnRvSGF2ZUJlZW5DYWxsZWRXaXRoKFxuICAgICAgICBgRXJyb3IgZmV0Y2hpbmcgSHViU3BvdCBjb250YWN0IGJ5IGVtYWlsICR7dGVzdEVtYWlsfSBmb3IgdXNlcklkICR7dGVzdFVzZXJJZH06YCxcbiAgICAgICAgYXBpRXJyb3IubWVzc2FnZVxuICAgICAgKTtcbiAgICAgIGV4cGVjdChjb25zb2xlRXJyb3JTcHkpLnRvSGF2ZUJlZW5DYWxsZWRXaXRoKFxuICAgICAgICAnSHViU3BvdCBBUEkgRXJyb3IgQm9keTonLFxuICAgICAgICAnU29tZSBlcnJvciBib2R5J1xuICAgICAgKTtcbiAgICB9KTtcbiAgfSk7XG5cbiAgZGVzY3JpYmUoJ2NyZWF0ZUh1YlNwb3RDb250YWN0JywgKCkgPT4ge1xuICAgIGNvbnN0IHRlc3RVc2VySWQgPSAndXNlcjEyMyc7XG4gICAgY29uc3QgY29udGFjdFByb3BlcnRpZXM6IEh1YlNwb3RDb250YWN0UHJvcGVydGllcyA9IHtcbiAgICAgIGVtYWlsOiAnbmV3QGV4YW1wbGUuY29tJyxcbiAgICAgIGZpcnN0bmFtZTogJ05ldycsXG4gICAgICBsYXN0bmFtZTogJ1VzZXInLFxuICAgICAgY29tcGFueTogJ05ldyBDb21wYW55JyxcbiAgICB9O1xuXG4gICAgaXQoJ3Nob3VsZCBjcmVhdGUgYSBjb250YWN0IGFuZCByZXR1cm4gc3VjY2VzcyByZXNwb25zZScsIGFzeW5jICgpID0+IHtcbiAgICAgIGNvbnN0IGNyZWF0ZWRBcGlDb250YWN0ID0ge1xuICAgICAgICAuLi5tb2NrQXBpQ29udGFjdFJlc3VsdCxcbiAgICAgICAgaWQ6ICc2Nzg5MCcsXG4gICAgICAgIHByb3BlcnRpZXM6IHtcbiAgICAgICAgICAuLi5tb2NrQXBpQ29udGFjdFJlc3VsdC5wcm9wZXJ0aWVzLFxuICAgICAgICAgIC4uLmNvbnRhY3RQcm9wZXJ0aWVzLFxuICAgICAgICB9LFxuICAgICAgICBjcmVhdGVkQXQ6IG5ldyBEYXRlKCksXG4gICAgICAgIHVwZGF0ZWRBdDogbmV3IERhdGUoKSxcbiAgICAgIH07XG4gICAgICBtb2NrQ29udGFjdHNCYXNpY0FwaUNyZWF0ZS5tb2NrUmVzb2x2ZWRWYWx1ZShjcmVhdGVkQXBpQ29udGFjdCk7XG5cbiAgICAgIGNvbnN0IHJlc3VsdCA9IGF3YWl0IGNyZWF0ZUh1YlNwb3RDb250YWN0KHRlc3RVc2VySWQsIGNvbnRhY3RQcm9wZXJ0aWVzKTtcblxuICAgICAgY29uc3QgZXhwZWN0ZWRDcmVhdGVkQ29udGFjdDogSHViU3BvdENvbnRhY3QgPSB7XG4gICAgICAgIC4uLm1vY2tFeHBlY3RlZENvbnRhY3QsXG4gICAgICAgIGlkOiAnNjc4OTAnLFxuICAgICAgICBwcm9wZXJ0aWVzOiB7IC4uLm1vY2tFeHBlY3RlZENvbnRhY3QucHJvcGVydGllcywgLi4uY29udGFjdFByb3BlcnRpZXMgfSxcbiAgICAgICAgY3JlYXRlZEF0OiBjcmVhdGVkQXBpQ29udGFjdC5jcmVhdGVkQXQudG9JU09TdHJpbmcoKSxcbiAgICAgICAgdXBkYXRlZEF0OiBjcmVhdGVkQXBpQ29udGFjdC51cGRhdGVkQXQudG9JU09TdHJpbmcoKSxcbiAgICAgIH07XG5cbiAgICAgIGV4cGVjdChyZXN1bHQpLnRvRXF1YWwoe1xuICAgICAgICBzdWNjZXNzOiB0cnVlLFxuICAgICAgICBjb250YWN0SWQ6IGNyZWF0ZWRBcGlDb250YWN0LmlkLFxuICAgICAgICBtZXNzYWdlOiAnQ29udGFjdCBjcmVhdGVkIHN1Y2Nlc3NmdWxseSBpbiBIdWJTcG90LicsXG4gICAgICAgIGh1YlNwb3RDb250YWN0OiBleHBlY3RlZENyZWF0ZWRDb250YWN0LFxuICAgICAgfSk7XG4gICAgICBleHBlY3QobW9ja0NvbnRhY3RzQmFzaWNBcGlDcmVhdGUpLnRvSGF2ZUJlZW5DYWxsZWRXaXRoKHtcbiAgICAgICAgcHJvcGVydGllczogY29udGFjdFByb3BlcnRpZXMsXG4gICAgICB9KTtcbiAgICAgIGV4cGVjdChjb25zb2xlTG9nU3B5KS50b0hhdmVCZWVuQ2FsbGVkV2l0aChcbiAgICAgICAgYGNyZWF0ZUh1YlNwb3RDb250YWN0IGNhbGxlZCBmb3IgdXNlcklkOiAke3Rlc3RVc2VySWR9IHdpdGggcHJvcGVydGllczpgLFxuICAgICAgICBjb250YWN0UHJvcGVydGllc1xuICAgICAgKTtcbiAgICB9KTtcblxuICAgIGl0KCdzaG91bGQgcmV0dXJuIGVycm9yIGlmIGVtYWlsIGlzIG1pc3NpbmcnLCBhc3luYyAoKSA9PiB7XG4gICAgICBjb25zdCBwcm9wZXJ0aWVzV2l0aG91dEVtYWlsOiBIdWJTcG90Q29udGFjdFByb3BlcnRpZXMgPSB7XG4gICAgICAgIGZpcnN0bmFtZTogJ05vJyxcbiAgICAgICAgbGFzdG5hbWU6ICdFbWFpbCcsXG4gICAgICB9O1xuICAgICAgY29uc3QgcmVzdWx0ID0gYXdhaXQgY3JlYXRlSHViU3BvdENvbnRhY3QoXG4gICAgICAgIHRlc3RVc2VySWQsXG4gICAgICAgIHByb3BlcnRpZXNXaXRob3V0RW1haWxcbiAgICAgICk7XG4gICAgICBleHBlY3QocmVzdWx0KS50b0VxdWFsKHtcbiAgICAgICAgc3VjY2VzczogZmFsc2UsXG4gICAgICAgIG1lc3NhZ2U6ICdFbWFpbCBpcyByZXF1aXJlZCB0byBjcmVhdGUgYSBIdWJTcG90IGNvbnRhY3QuJyxcbiAgICAgIH0pO1xuICAgICAgZXhwZWN0KG1vY2tDb250YWN0c0Jhc2ljQXBpQ3JlYXRlKS5ub3QudG9IYXZlQmVlbkNhbGxlZCgpO1xuICAgIH0pO1xuXG4gICAgaXQoJ3Nob3VsZCByZXR1cm4gZXJyb3IgaWYgQVBJIGtleSBpcyBtaXNzaW5nJywgYXN5bmMgKCkgPT4ge1xuICAgICAgc2V0TW9ja0FwaUtleShudWxsKTsgLy8gU2ltdWxhdGUgbWlzc2luZyBBUEkga2V5XG4gICAgICBjb25zdCByZXN1bHQgPSBhd2FpdCBjcmVhdGVIdWJTcG90Q29udGFjdCh0ZXN0VXNlcklkLCBjb250YWN0UHJvcGVydGllcyk7XG4gICAgICBleHBlY3QocmVzdWx0KS50b0VxdWFsKHtcbiAgICAgICAgc3VjY2VzczogZmFsc2UsXG4gICAgICAgIG1lc3NhZ2U6ICdIdWJTcG90IEFQSSBrZXkgbm90IGNvbmZpZ3VyZWQuJyxcbiAgICAgIH0pO1xuICAgICAgZXhwZWN0KG1vY2tDb250YWN0c0Jhc2ljQXBpQ3JlYXRlKS5ub3QudG9IYXZlQmVlbkNhbGxlZCgpO1xuICAgICAgZXhwZWN0KGNvbnNvbGVFcnJvclNweSkudG9IYXZlQmVlbkNhbGxlZFdpdGgoXG4gICAgICAgICdIdWJTcG90IEFQSSBrZXkgbm90IGNvbmZpZ3VyZWQuJ1xuICAgICAgKTtcbiAgICB9KTtcblxuICAgIGl0KCdzaG91bGQgcmV0dXJuIGVycm9yIGFuZCBsb2cgaWYgSHViU3BvdCBBUEkgY2FsbCBmYWlscycsIGFzeW5jICgpID0+IHtcbiAgICAgIGNvbnN0IGFwaUVycm9yID0gbmV3IEVycm9yKCdIdWJTcG90IENyZWF0ZSBFcnJvcicpO1xuICAgICAgKGFwaUVycm9yIGFzIGFueSkucmVzcG9uc2UgPSB7XG4gICAgICAgIGJvZHk6IEJ1ZmZlci5mcm9tKEpTT04uc3RyaW5naWZ5KHsgbWVzc2FnZTogJ0RldGFpbGVkIEFQSSBlcnJvcicgfSkpLFxuICAgICAgfTtcbiAgICAgIG1vY2tDb250YWN0c0Jhc2ljQXBpQ3JlYXRlLm1vY2tSZWplY3RlZFZhbHVlKGFwaUVycm9yKTtcbiAgICAgIGNvbnN0IHJlc3VsdCA9IGF3YWl0IGNyZWF0ZUh1YlNwb3RDb250YWN0KHRlc3RVc2VySWQsIGNvbnRhY3RQcm9wZXJ0aWVzKTtcbiAgICAgIGV4cGVjdChyZXN1bHQuc3VjY2VzcykudG9CZShmYWxzZSk7XG4gICAgICBleHBlY3QocmVzdWx0Lm1lc3NhZ2UpLnRvQmUoXG4gICAgICAgICdGYWlsZWQgdG8gY3JlYXRlIGNvbnRhY3QgaW4gSHViU3BvdDogRGV0YWlsZWQgQVBJIGVycm9yJ1xuICAgICAgKTtcbiAgICAgIGV4cGVjdChjb25zb2xlRXJyb3JTcHkpLnRvSGF2ZUJlZW5DYWxsZWRXaXRoKFxuICAgICAgICBgRXJyb3IgY3JlYXRpbmcgSHViU3BvdCBjb250YWN0IGZvciB1c2VySWQgJHt0ZXN0VXNlcklkfSB3aXRoIGVtYWlsICR7Y29udGFjdFByb3BlcnRpZXMuZW1haWx9OmAsXG4gICAgICAgIGFwaUVycm9yLm1lc3NhZ2VcbiAgICAgICk7XG4gICAgICBleHBlY3QoY29uc29sZUVycm9yU3B5KS50b0hhdmVCZWVuQ2FsbGVkV2l0aCgnSHViU3BvdCBBUEkgRXJyb3IgQm9keTonLCB7XG4gICAgICAgIG1lc3NhZ2U6ICdEZXRhaWxlZCBBUEkgZXJyb3InLFxuICAgICAgfSk7XG4gICAgfSk7XG5cbiAgICBpdCgnc2hvdWxkIHJldHVybiBzcGVjaWZpYyBtZXNzYWdlIGlmIGNvbnRhY3QgYWxyZWFkeSBleGlzdHMgKENPTkZMSUNUKScsIGFzeW5jICgpID0+IHtcbiAgICAgIGNvbnN0IGFwaUNvbmZsaWN0RXJyb3IgPSBuZXcgRXJyb3IoJ0NvbmZsaWN0Jyk7XG4gICAgICAoYXBpQ29uZmxpY3RFcnJvciBhcyBhbnkpLnJlc3BvbnNlID0ge1xuICAgICAgICBib2R5OiBCdWZmZXIuZnJvbShcbiAgICAgICAgICBKU09OLnN0cmluZ2lmeSh7XG4gICAgICAgICAgICBtZXNzYWdlOiAnQ29udGFjdCBhbHJlYWR5IGV4aXN0cy4nLFxuICAgICAgICAgICAgY2F0ZWdvcnk6ICdDT05GTElDVCcsXG4gICAgICAgICAgfSlcbiAgICAgICAgKSxcbiAgICAgIH07XG4gICAgICBtb2NrQ29udGFjdHNCYXNpY0FwaUNyZWF0ZS5tb2NrUmVqZWN0ZWRWYWx1ZShhcGlDb25mbGljdEVycm9yKTtcbiAgICAgIGNvbnN0IHJlc3VsdCA9IGF3YWl0IGNyZWF0ZUh1YlNwb3RDb250YWN0KHRlc3RVc2VySWQsIGNvbnRhY3RQcm9wZXJ0aWVzKTtcbiAgICAgIGV4cGVjdChyZXN1bHQuc3VjY2VzcykudG9CZShmYWxzZSk7XG4gICAgICBleHBlY3QocmVzdWx0Lm1lc3NhZ2UpLnRvQmUoXG4gICAgICAgICdGYWlsZWQgdG8gY3JlYXRlIGNvbnRhY3QgaW4gSHViU3BvdDogQSBjb250YWN0IHdpdGggdGhpcyBlbWFpbCBhbHJlYWR5IGV4aXN0cy4nXG4gICAgICApO1xuICAgIH0pO1xuICB9KTtcblxuICBkZXNjcmliZSgnbG9nRW1haWxUb0h1YlNwb3RDb250YWN0JywgKCkgPT4ge1xuICAgIGNvbnN0IHVzZXJJZCA9ICd1c2VyLXRlc3QtMTIzJztcbiAgICBjb25zdCBjb250YWN0SWQgPSAnY29udGFjdC00NTYnO1xuICAgIGNvbnN0IGVtYWlsRGV0YWlsczogSHViU3BvdEVtYWlsRW5nYWdlbWVudFByb3BlcnRpZXMgPSB7XG4gICAgICBhY3Rpdml0eVRpbWVzdGFtcDogRGF0ZS5ub3coKSxcbiAgICAgIHN1YmplY3Q6ICdUZXN0IEVtYWlsIFN1YmplY3QnLFxuICAgICAgaHRtbEJvZHk6ICc8cD5UaGlzIGlzIGEgdGVzdCBlbWFpbCBib2R5LjwvcD4nLFxuICAgICAgZGlyZWN0aW9uOiAnT1VUR09JTkcnLFxuICAgIH07XG4gICAgY29uc3QgbW9ja0VuZ2FnZW1lbnRJZCA9ICdlbmctNzg5JztcbiAgICBjb25zdCBtb2NrQ3JlYXRlZERhdGUgPSBuZXcgRGF0ZSgpO1xuICAgIGNvbnN0IG1vY2tVcGRhdGVkRGF0ZSA9IG5ldyBEYXRlKCk7XG5cbiAgICBjb25zdCBtb2NrRW5nYWdlbWVudEFwaVJlc3BvbnNlID0ge1xuICAgICAgaWQ6IG1vY2tFbmdhZ2VtZW50SWQsXG4gICAgICBwcm9wZXJ0aWVzOiB7XG4gICAgICAgIGhzX29iamVjdF9pZDogbW9ja0VuZ2FnZW1lbnRJZCxcbiAgICAgICAgaHNfZW5nYWdlbWVudF90eXBlOiAnRU1BSUwnLFxuICAgICAgICBoc190aW1lc3RhbXA6IGVtYWlsRGV0YWlscy5hY3Rpdml0eVRpbWVzdGFtcC50b1N0cmluZygpLFxuICAgICAgICBoc19lbWFpbF9zdWJqZWN0OiBlbWFpbERldGFpbHMuc3ViamVjdCxcbiAgICAgICAgaHNfYm9keV9wcmV2aWV3OiBlbWFpbERldGFpbHMuaHRtbEJvZHkuc3Vic3RyaW5nKDAsIDUxMiksXG4gICAgICAgIGhzX2VtYWlsX2RpcmVjdGlvbjogZW1haWxEZXRhaWxzLmRpcmVjdGlvbixcbiAgICAgICAgY3JlYXRlZGF0ZTogbW9ja0NyZWF0ZWREYXRlLnRvSVNPU3RyaW5nKCksXG4gICAgICAgIGxhc3Rtb2RpZmllZGRhdGU6IG1vY2tVcGRhdGVkRGF0ZS50b0lTT1N0cmluZygpLFxuICAgICAgfSxcbiAgICAgIGNyZWF0ZWRBdDogbW9ja0NyZWF0ZWREYXRlLFxuICAgICAgdXBkYXRlZEF0OiBtb2NrVXBkYXRlZERhdGUsXG4gICAgICBhcmNoaXZlZDogZmFsc2UsXG4gICAgICBhc3NvY2lhdGlvbnM6IHt9LFxuICAgIH07XG5cbiAgICBpdCgnc2hvdWxkIHN1Y2Nlc3NmdWxseSBsb2cgYW4gZW1haWwgYW5kIHJldHVybiBlbmdhZ2VtZW50IGRldGFpbHMnLCBhc3luYyAoKSA9PiB7XG4gICAgICBtb2NrRW5nYWdlbWVudHNCYXNpY0FwaUNyZWF0ZS5tb2NrUmVzb2x2ZWRWYWx1ZShcbiAgICAgICAgbW9ja0VuZ2FnZW1lbnRBcGlSZXNwb25zZVxuICAgICAgKTtcblxuICAgICAgY29uc3QgcmVzdWx0ID0gYXdhaXQgbG9nRW1haWxUb0h1YlNwb3RDb250YWN0KFxuICAgICAgICB1c2VySWQsXG4gICAgICAgIGNvbnRhY3RJZCxcbiAgICAgICAgZW1haWxEZXRhaWxzXG4gICAgICApO1xuXG4gICAgICBleHBlY3QocmVzdWx0LnN1Y2Nlc3MpLnRvQmUodHJ1ZSk7XG4gICAgICBleHBlY3QocmVzdWx0LmVuZ2FnZW1lbnRJZCkudG9CZShtb2NrRW5nYWdlbWVudElkKTtcbiAgICAgIGV4cGVjdChyZXN1bHQubWVzc2FnZSkudG9CZShcbiAgICAgICAgJ0VtYWlsIGxvZ2dlZCBzdWNjZXNzZnVsbHkgdG8gSHViU3BvdCBjb250YWN0LidcbiAgICAgICk7XG4gICAgICBleHBlY3QocmVzdWx0Lmh1YlNwb3RFbmdhZ2VtZW50KS50b0JlRGVmaW5lZCgpO1xuICAgICAgZXhwZWN0KHJlc3VsdC5odWJTcG90RW5nYWdlbWVudD8uaWQpLnRvQmUobW9ja0VuZ2FnZW1lbnRJZCk7XG4gICAgICBleHBlY3QocmVzdWx0Lmh1YlNwb3RFbmdhZ2VtZW50Py5wcm9wZXJ0aWVzLmhzX2VtYWlsX3N1YmplY3QpLnRvQmUoXG4gICAgICAgIGVtYWlsRGV0YWlscy5zdWJqZWN0XG4gICAgICApO1xuXG4gICAgICBleHBlY3QobW9ja0VuZ2FnZW1lbnRzQmFzaWNBcGlDcmVhdGUpLnRvSGF2ZUJlZW5DYWxsZWRXaXRoKHtcbiAgICAgICAgcHJvcGVydGllczoge1xuICAgICAgICAgIGhzX3RpbWVzdGFtcDogZW1haWxEZXRhaWxzLmFjdGl2aXR5VGltZXN0YW1wLnRvU3RyaW5nKCksXG4gICAgICAgICAgaHNfZW5nYWdlbWVudF90eXBlOiAnRU1BSUwnLFxuICAgICAgICAgIGhzX2VtYWlsX3N1YmplY3Q6IGVtYWlsRGV0YWlscy5zdWJqZWN0LFxuICAgICAgICAgIGhzX2JvZHlfcHJldmlldzogZW1haWxEZXRhaWxzLmh0bWxCb2R5LnN1YnN0cmluZygwLCA1MTIpLFxuICAgICAgICAgIGhzX2VtYWlsX2RpcmVjdGlvbjogZW1haWxEZXRhaWxzLmRpcmVjdGlvbixcbiAgICAgICAgfSxcbiAgICAgICAgYXNzb2NpYXRpb25zOiBbXG4gICAgICAgICAge1xuICAgICAgICAgICAgdG86IHsgaWQ6IGNvbnRhY3RJZCB9LFxuICAgICAgICAgICAgdHlwZXM6IFtcbiAgICAgICAgICAgICAge1xuICAgICAgICAgICAgICAgIGFzc29jaWF0aW9uQ2F0ZWdvcnk6ICdIVUJTUE9UX0RFRklORUQnLFxuICAgICAgICAgICAgICAgIGFzc29jaWF0aW9uVHlwZUlkOiBDT05UQUNUX1RPX0VOR0FHRU1FTlRfQVNTT0NJQVRJT05fVFlQRV9JRCxcbiAgICAgICAgICAgICAgfSxcbiAgICAgICAgICAgIF0sXG4gICAgICAgICAgfSxcbiAgICAgICAgXSxcbiAgICAgIH0pO1xuICAgICAgZXhwZWN0KGNvbnNvbGVMb2dTcHkpLnRvSGF2ZUJlZW5DYWxsZWRXaXRoKFxuICAgICAgICBgbG9nRW1haWxUb0h1YlNwb3RDb250YWN0IGNhbGxlZCBmb3IgdXNlcklkOiAke3VzZXJJZH0sIGNvbnRhY3RJZDogJHtjb250YWN0SWR9YFxuICAgICAgKTtcbiAgICB9KTtcblxuICAgIGl0KCdzaG91bGQgcmV0dXJuIGVycm9yIGlmIEFQSSBrZXkgaXMgbWlzc2luZycsIGFzeW5jICgpID0+IHtcbiAgICAgIHNldE1vY2tBcGlLZXkobnVsbCk7XG4gICAgICBjb25zdCByZXN1bHQgPSBhd2FpdCBsb2dFbWFpbFRvSHViU3BvdENvbnRhY3QoXG4gICAgICAgIHVzZXJJZCxcbiAgICAgICAgY29udGFjdElkLFxuICAgICAgICBlbWFpbERldGFpbHNcbiAgICAgICk7XG4gICAgICBleHBlY3QocmVzdWx0LnN1Y2Nlc3MpLnRvQmUoZmFsc2UpO1xuICAgICAgZXhwZWN0KHJlc3VsdC5tZXNzYWdlKS50b0JlKCdIdWJTcG90IEFQSSBrZXkgbm90IGNvbmZpZ3VyZWQuJyk7XG4gICAgICBleHBlY3QobW9ja0VuZ2FnZW1lbnRzQmFzaWNBcGlDcmVhdGUpLm5vdC50b0hhdmVCZWVuQ2FsbGVkKCk7XG4gICAgfSk7XG5cbiAgICBpdCgnc2hvdWxkIHJldHVybiBlcnJvciBpZiBIdWJTcG90IEFQSSBjcmVhdGUgY2FsbCBmYWlscycsIGFzeW5jICgpID0+IHtcbiAgICAgIGNvbnN0IGFwaUVycm9yID0gbmV3IEVycm9yKCdIdWJTcG90IEFQSSBDcmVhdGUgRW5nYWdlbWVudCBFcnJvcicpO1xuICAgICAgKGFwaUVycm9yIGFzIGFueSkucmVzcG9uc2UgPSB7XG4gICAgICAgIGJvZHk6IEJ1ZmZlci5mcm9tKFxuICAgICAgICAgIEpTT04uc3RyaW5naWZ5KHsgbWVzc2FnZTogJ0RldGFpbGVkIGNyZWF0aW9uIGVycm9yJyB9KVxuICAgICAgICApLFxuICAgICAgfTtcbiAgICAgIG1vY2tFbmdhZ2VtZW50c0Jhc2ljQXBpQ3JlYXRlLm1vY2tSZWplY3RlZFZhbHVlKGFwaUVycm9yKTtcblxuICAgICAgY29uc3QgcmVzdWx0ID0gYXdhaXQgbG9nRW1haWxUb0h1YlNwb3RDb250YWN0KFxuICAgICAgICB1c2VySWQsXG4gICAgICAgIGNvbnRhY3RJZCxcbiAgICAgICAgZW1haWxEZXRhaWxzXG4gICAgICApO1xuXG4gICAgICBleHBlY3QocmVzdWx0LnN1Y2Nlc3MpLnRvQmUoZmFsc2UpO1xuICAgICAgZXhwZWN0KHJlc3VsdC5tZXNzYWdlKS50b0JlKFxuICAgICAgICAnRmFpbGVkIHRvIGxvZyBlbWFpbCB0byBIdWJTcG90OiBEZXRhaWxlZCBjcmVhdGlvbiBlcnJvcidcbiAgICAgICk7XG4gICAgICBleHBlY3QoY29uc29sZUVycm9yU3B5KS50b0hhdmVCZWVuQ2FsbGVkV2l0aChcbiAgICAgICAgYEVycm9yIGxvZ2dpbmcgZW1haWwgdG8gSHViU3BvdCBjb250YWN0ICR7Y29udGFjdElkfSBmb3IgdXNlcklkICR7dXNlcklkfTpgLFxuICAgICAgICBhcGlFcnJvci5tZXNzYWdlXG4gICAgICApO1xuICAgIH0pO1xuICAgIGl0KCdzaG91bGQgcmV0dXJuIGVycm9yIGlmIGNvbnRhY3RJZCBpcyBtaXNzaW5nJywgYXN5bmMgKCkgPT4ge1xuICAgICAgY29uc3QgcmVzdWx0ID0gYXdhaXQgbG9nRW1haWxUb0h1YlNwb3RDb250YWN0KHVzZXJJZCwgJycsIGVtYWlsRGV0YWlscyk7XG4gICAgICBleHBlY3QocmVzdWx0KS50b0VxdWFsKHtcbiAgICAgICAgc3VjY2VzczogZmFsc2UsXG4gICAgICAgIG1lc3NhZ2U6ICdDb250YWN0IElEIGlzIHJlcXVpcmVkIHRvIGxvZyBhbiBlbWFpbC4nLFxuICAgICAgfSk7XG4gICAgICBleHBlY3QobW9ja0VuZ2FnZW1lbnRzQmFzaWNBcGlDcmVhdGUpLm5vdC50b0hhdmVCZWVuQ2FsbGVkKCk7XG4gICAgfSk7XG5cbiAgICBpdCgnc2hvdWxkIHJldHVybiBlcnJvciBpZiBlc3NlbnRpYWwgZW1haWxEZXRhaWxzIGFyZSBtaXNzaW5nJywgYXN5bmMgKCkgPT4ge1xuICAgICAgLy8gQHRzLWlnbm9yZVxuICAgICAgY29uc3QgcmVzdWx0ID0gYXdhaXQgbG9nRW1haWxUb0h1YlNwb3RDb250YWN0KHVzZXJJZCwgY29udGFjdElkLCB7XG4gICAgICAgIHN1YmplY3Q6ICdtaXNzaW5nIG90aGVyIGZpZWxkcycsXG4gICAgICB9KTtcbiAgICAgIGV4cGVjdChyZXN1bHQpLnRvRXF1YWwoe1xuICAgICAgICBzdWNjZXNzOiBmYWxzZSxcbiAgICAgICAgbWVzc2FnZTpcbiAgICAgICAgICAnRW1haWwgZGV0YWlscyAoYWN0aXZpdHlUaW1lc3RhbXAsIHN1YmplY3QsIGh0bWxCb2R5KSBhcmUgcmVxdWlyZWQuJyxcbiAgICAgIH0pO1xuICAgICAgZXhwZWN0KG1vY2tFbmdhZ2VtZW50c0Jhc2ljQXBpQ3JlYXRlKS5ub3QudG9IYXZlQmVlbkNhbGxlZCgpO1xuICAgIH0pO1xuICB9KTtcblxuICBkZXNjcmliZSgnZ2V0SHViU3BvdENvbnRhY3RBY3Rpdml0aWVzJywgKCkgPT4ge1xuICAgIGNvbnN0IHVzZXJJZCA9ICd1c2VyLXRlc3QtNDU2JztcbiAgICBjb25zdCBjb250YWN0SWQgPSAnY29udGFjdC03ODknO1xuICAgIGNvbnN0IG1vY2tFbmdhZ2VtZW50SWQxID0gJ2VuZy0xMTEnO1xuICAgIGNvbnN0IG1vY2tFbmdhZ2VtZW50SWQyID0gJ2VuZy0yMjInO1xuXG4gICAgY29uc3QgbW9ja0Fzc29jaWF0aW9uUGFnZSA9IChpZHM6IHN0cmluZ1tdKSA9PiAoe1xuICAgICAgcmVzdWx0czogaWRzLm1hcCgoaWQpID0+ICh7XG4gICAgICAgIHRvT2JqZWN0SWQ6IGlkLFxuICAgICAgICB0eXBlOiAnY29udGFjdF90b19lbmdhZ2VtZW50JyxcbiAgICAgIH0pKSwgLy8gU2ltcGxpZmllZCwgY2hlY2sgYWN0dWFsIHR5cGUgc3RyaW5nIGlmIG5lZWRlZFxuICAgICAgcGFnaW5nOiB7XG4gICAgICAgIG5leHQ6IHsgYWZ0ZXI6IGlkcy5sZW5ndGggPiAwID8gJ25leHRwYWdlY3Vyc29yJyA6IHVuZGVmaW5lZCB9LFxuICAgICAgfSxcbiAgICB9KTtcblxuICAgIGNvbnN0IG1vY2tFbmdhZ2VtZW50U2VhcmNoUmVzdWx0ID0gKFxuICAgICAgaWQ6IHN0cmluZyxcbiAgICAgIHR5cGU6ICdFTUFJTCcgfCAnTUVFVElORycgPSAnRU1BSUwnXG4gICAgKSA9PiAoe1xuICAgICAgaWQsXG4gICAgICBwcm9wZXJ0aWVzOiB7XG4gICAgICAgIGhzX29iamVjdF9pZDogaWQsXG4gICAgICAgIGhzX2VuZ2FnZW1lbnRfdHlwZTogdHlwZSxcbiAgICAgICAgaHNfdGltZXN0YW1wOiBuZXcgRGF0ZSgpLnRvSVNPU3RyaW5nKCksXG4gICAgICAgIGhzX2VtYWlsX3N1YmplY3Q6IGBTdWJqZWN0IGZvciAke2lkfWAsXG4gICAgICAgIGhzX2JvZHlfcHJldmlldzogYEJvZHkgZm9yICR7aWR9YCxcbiAgICAgICAgY3JlYXRlZGF0ZTogbmV3IERhdGUoKS50b0lTT1N0cmluZygpLFxuICAgICAgICBsYXN0bW9kaWZpZWRkYXRlOiBuZXcgRGF0ZSgpLnRvSVNPU3RyaW5nKCksXG4gICAgICB9LFxuICAgICAgY3JlYXRlZEF0OiBuZXcgRGF0ZSgpLFxuICAgICAgdXBkYXRlZEF0OiBuZXcgRGF0ZSgpLFxuICAgICAgYXJjaGl2ZWQ6IGZhbHNlLFxuICAgIH0pO1xuXG4gICAgaXQoJ3Nob3VsZCByZXRyaWV2ZSBhY3Rpdml0aWVzIHdpdGggZGVmYXVsdCBmaWx0ZXJzJywgYXN5bmMgKCkgPT4ge1xuICAgICAgbW9ja0Fzc29jaWF0aW9uc1Y0QmFzaWNBcGlHZXRQYWdlLm1vY2tSZXNvbHZlZFZhbHVlKFxuICAgICAgICBtb2NrQXNzb2NpYXRpb25QYWdlKFttb2NrRW5nYWdlbWVudElkMSwgbW9ja0VuZ2FnZW1lbnRJZDJdKVxuICAgICAgKTtcbiAgICAgIG1vY2tFbmdhZ2VtZW50c1NlYXJjaEFwaURvU2VhcmNoLm1vY2tSZXNvbHZlZFZhbHVlKHtcbiAgICAgICAgcmVzdWx0czogW1xuICAgICAgICAgIG1vY2tFbmdhZ2VtZW50U2VhcmNoUmVzdWx0KG1vY2tFbmdhZ2VtZW50SWQxKSxcbiAgICAgICAgICBtb2NrRW5nYWdlbWVudFNlYXJjaFJlc3VsdChtb2NrRW5nYWdlbWVudElkMiksXG4gICAgICAgIF0sXG4gICAgICAgIHBhZ2luZzogeyBuZXh0OiB7IGFmdGVyOiAnbmV4dFNlYXJjaEN1cnNvcicgfSB9LFxuICAgICAgfSk7XG5cbiAgICAgIGNvbnN0IHJlc3VsdCA9IGF3YWl0IGdldEh1YlNwb3RDb250YWN0QWN0aXZpdGllcyh1c2VySWQsIGNvbnRhY3RJZCk7XG5cbiAgICAgIGV4cGVjdChyZXN1bHQuc3VjY2VzcykudG9CZSh0cnVlKTtcbiAgICAgIGV4cGVjdChyZXN1bHQuYWN0aXZpdGllcy5sZW5ndGgpLnRvQmUoMik7XG4gICAgICBleHBlY3QocmVzdWx0LmFjdGl2aXRpZXNbMF0uaWQpLnRvQmUobW9ja0VuZ2FnZW1lbnRJZDEpO1xuICAgICAgZXhwZWN0KHJlc3VsdC5uZXh0UGFnZSkudG9CZSgnbmV4dFNlYXJjaEN1cnNvcicpOyAvLyBUaGlzIHNob3VsZCBiZSBmcm9tIHNlYXJjaEFwaS5kb1NlYXJjaCBwYWdpbmdcbiAgICAgIGV4cGVjdChtb2NrQXNzb2NpYXRpb25zVjRCYXNpY0FwaUdldFBhZ2UpLnRvSGF2ZUJlZW5DYWxsZWRXaXRoKFxuICAgICAgICAnMC0xJyxcbiAgICAgICAgY29udGFjdElkLFxuICAgICAgICAnMC0zMScsXG4gICAgICAgIHVuZGVmaW5lZCxcbiAgICAgICAgNTBcbiAgICAgICk7XG4gICAgICBleHBlY3QobW9ja0VuZ2FnZW1lbnRzU2VhcmNoQXBpRG9TZWFyY2gpLnRvSGF2ZUJlZW5DYWxsZWRXaXRoKFxuICAgICAgICBleHBlY3Qub2JqZWN0Q29udGFpbmluZyh7XG4gICAgICAgICAgZmlsdGVyR3JvdXBzOiBbXG4gICAgICAgICAgICB7XG4gICAgICAgICAgICAgIGZpbHRlcnM6IFtcbiAgICAgICAgICAgICAgICB7XG4gICAgICAgICAgICAgICAgICBwcm9wZXJ0eU5hbWU6ICdoc19vYmplY3RfaWQnLFxuICAgICAgICAgICAgICAgICAgb3BlcmF0b3I6ICdJTicsXG4gICAgICAgICAgICAgICAgICB2YWx1ZXM6IFttb2NrRW5nYWdlbWVudElkMSwgbW9ja0VuZ2FnZW1lbnRJZDJdLFxuICAgICAgICAgICAgICAgIH0sXG4gICAgICAgICAgICAgIF0sXG4gICAgICAgICAgICB9LFxuICAgICAgICAgIF0sXG4gICAgICAgICAgbGltaXQ6IDEwLFxuICAgICAgICAgIHNvcnRzOiBbeyBwcm9wZXJ0eU5hbWU6ICdoc190aW1lc3RhbXAnLCBkaXJlY3Rpb246ICdERVNDRU5ESU5HJyB9XSxcbiAgICAgICAgfSlcbiAgICAgICk7XG4gICAgfSk7XG5cbiAgICBpdCgnc2hvdWxkIHJldHJpZXZlIGFjdGl2aXRpZXMgd2l0aCBzcGVjaWZpYyBmaWx0ZXJzIChFTUFJTCwgbGltaXQgNSwgQVNDLCBzaW5jZSknLCBhc3luYyAoKSA9PiB7XG4gICAgICBjb25zdCBzaW5jZURhdGUgPSBuZXcgRGF0ZSgnMjAyMy0wMS0wMVQwMDowMDowMC4wMDBaJyk7XG4gICAgICBjb25zdCBzaW5jZVRpbWVzdGFtcCA9IHNpbmNlRGF0ZS5nZXRUaW1lKCkudG9TdHJpbmcoKTtcbiAgICAgIG1vY2tBc3NvY2lhdGlvbnNWNEJhc2ljQXBpR2V0UGFnZS5tb2NrUmVzb2x2ZWRWYWx1ZShcbiAgICAgICAgbW9ja0Fzc29jaWF0aW9uUGFnZShbbW9ja0VuZ2FnZW1lbnRJZDFdKVxuICAgICAgKTtcbiAgICAgIG1vY2tFbmdhZ2VtZW50c1NlYXJjaEFwaURvU2VhcmNoLm1vY2tSZXNvbHZlZFZhbHVlKHtcbiAgICAgICAgcmVzdWx0czogW21vY2tFbmdhZ2VtZW50U2VhcmNoUmVzdWx0KG1vY2tFbmdhZ2VtZW50SWQxLCAnRU1BSUwnKV0sXG4gICAgICB9KTtcblxuICAgICAgYXdhaXQgZ2V0SHViU3BvdENvbnRhY3RBY3Rpdml0aWVzKHVzZXJJZCwgY29udGFjdElkLCB7XG4gICAgICAgIGFjdGl2aXR5VHlwZXM6IFsnRU1BSUwnXSxcbiAgICAgICAgbGltaXQ6IDUsXG4gICAgICAgIHNvcnQ6ICdBU0MnLFxuICAgICAgICBzaW5jZTogc2luY2VEYXRlLnRvSVNPU3RyaW5nKCksXG4gICAgICB9KTtcblxuICAgICAgZXhwZWN0KG1vY2tFbmdhZ2VtZW50c1NlYXJjaEFwaURvU2VhcmNoKS50b0hhdmVCZWVuQ2FsbGVkV2l0aChcbiAgICAgICAgZXhwZWN0Lm9iamVjdENvbnRhaW5pbmcoe1xuICAgICAgICAgIGZpbHRlckdyb3VwczogW1xuICAgICAgICAgICAge1xuICAgICAgICAgICAgICBmaWx0ZXJzOiBleHBlY3QuYXJyYXlDb250YWluaW5nKFtcbiAgICAgICAgICAgICAgICB7XG4gICAgICAgICAgICAgICAgICBwcm9wZXJ0eU5hbWU6ICdoc19lbmdhZ2VtZW50X3R5cGUnLFxuICAgICAgICAgICAgICAgICAgb3BlcmF0b3I6ICdJTicsXG4gICAgICAgICAgICAgICAgICB2YWx1ZXM6IFsnRU1BSUwnXSxcbiAgICAgICAgICAgICAgICB9LFxuICAgICAgICAgICAgICAgIHtcbiAgICAgICAgICAgICAgICAgIHByb3BlcnR5TmFtZTogJ2hzX3RpbWVzdGFtcCcsXG4gICAgICAgICAgICAgICAgICBvcGVyYXRvcjogJ0dURScsXG4gICAgICAgICAgICAgICAgICB2YWx1ZTogc2luY2VUaW1lc3RhbXAsXG4gICAgICAgICAgICAgICAgfSxcbiAgICAgICAgICAgICAgICB7XG4gICAgICAgICAgICAgICAgICBwcm9wZXJ0eU5hbWU6ICdoc19vYmplY3RfaWQnLFxuICAgICAgICAgICAgICAgICAgb3BlcmF0b3I6ICdJTicsXG4gICAgICAgICAgICAgICAgICB2YWx1ZXM6IFttb2NrRW5nYWdlbWVudElkMV0sXG4gICAgICAgICAgICAgICAgfSxcbiAgICAgICAgICAgICAgXSksXG4gICAgICAgICAgICB9LFxuICAgICAgICAgIF0sXG4gICAgICAgICAgbGltaXQ6IDUsXG4gICAgICAgICAgc29ydHM6IFt7IHByb3BlcnR5TmFtZTogJ2hzX3RpbWVzdGFtcCcsIGRpcmVjdGlvbjogJ0FTQ0VORElORycgfV0sXG4gICAgICAgIH0pXG4gICAgICApO1xuICAgIH0pO1xuXG4gICAgaXQoJ3Nob3VsZCByZXR1cm4gZW1wdHkgYWN0aXZpdGllcyBpZiBubyBhc3NvY2lhdGlvbnMgZm91bmQnLCBhc3luYyAoKSA9PiB7XG4gICAgICBtb2NrQXNzb2NpYXRpb25zVjRCYXNpY0FwaUdldFBhZ2UubW9ja1Jlc29sdmVkVmFsdWUoXG4gICAgICAgIG1vY2tBc3NvY2lhdGlvblBhZ2UoW10pXG4gICAgICApOyAvLyBObyBhc3NvY2lhdGlvbnNcbiAgICAgIGNvbnN0IHJlc3VsdCA9IGF3YWl0IGdldEh1YlNwb3RDb250YWN0QWN0aXZpdGllcyh1c2VySWQsIGNvbnRhY3RJZCk7XG4gICAgICBleHBlY3QocmVzdWx0LnN1Y2Nlc3MpLnRvQmUodHJ1ZSk7XG4gICAgICBleHBlY3QocmVzdWx0LmFjdGl2aXRpZXMubGVuZ3RoKS50b0JlKDApO1xuICAgICAgZXhwZWN0KHJlc3VsdC5tZXNzYWdlKS50b0JlKCdObyBhY3Rpdml0aWVzIGZvdW5kIGZvciB0aGlzIGNvbnRhY3QuJyk7XG4gICAgICBleHBlY3QobW9ja0VuZ2FnZW1lbnRzU2VhcmNoQXBpRG9TZWFyY2gpLm5vdC50b0hhdmVCZWVuQ2FsbGVkKCk7XG4gICAgfSk7XG5cbiAgICBpdCgnc2hvdWxkIHJldHVybiBlbXB0eSBhY3Rpdml0aWVzIGlmIGFzc29jaWF0aW9ucyBmb3VuZCBidXQgc2VhcmNoIHJldHVybnMgbm9uZScsIGFzeW5jICgpID0+IHtcbiAgICAgIG1vY2tBc3NvY2lhdGlvbnNWNEJhc2ljQXBpR2V0UGFnZS5tb2NrUmVzb2x2ZWRWYWx1ZShcbiAgICAgICAgbW9ja0Fzc29jaWF0aW9uUGFnZShbbW9ja0VuZ2FnZW1lbnRJZDFdKVxuICAgICAgKTtcbiAgICAgIG1vY2tFbmdhZ2VtZW50c1NlYXJjaEFwaURvU2VhcmNoLm1vY2tSZXNvbHZlZFZhbHVlKHsgcmVzdWx0czogW10gfSk7IC8vIFNlYXJjaCByZXR1cm5zIG5vIGl0ZW1zXG4gICAgICBjb25zdCByZXN1bHQgPSBhd2FpdCBnZXRIdWJTcG90Q29udGFjdEFjdGl2aXRpZXModXNlcklkLCBjb250YWN0SWQpO1xuICAgICAgZXhwZWN0KHJlc3VsdC5zdWNjZXNzKS50b0JlKHRydWUpO1xuICAgICAgZXhwZWN0KHJlc3VsdC5hY3Rpdml0aWVzLmxlbmd0aCkudG9CZSgwKTtcbiAgICAgIGV4cGVjdChyZXN1bHQubWVzc2FnZSkudG9CZSgnTm8gYWN0aXZpdGllcyBmb3VuZCBtYXRjaGluZyBjcml0ZXJpYS4nKTtcbiAgICB9KTtcblxuICAgIGl0KCdzaG91bGQgcmV0dXJuIGVycm9yIGlmIEFQSSBrZXkgaXMgbWlzc2luZycsIGFzeW5jICgpID0+IHtcbiAgICAgIHNldE1vY2tBcGlLZXkobnVsbCk7XG4gICAgICBjb25zdCByZXN1bHQgPSBhd2FpdCBnZXRIdWJTcG90Q29udGFjdEFjdGl2aXRpZXModXNlcklkLCBjb250YWN0SWQpO1xuICAgICAgZXhwZWN0KHJlc3VsdC5zdWNjZXNzKS50b0JlKGZhbHNlKTtcbiAgICAgIGV4cGVjdChyZXN1bHQubWVzc2FnZSkudG9CZSgnSHViU3BvdCBBUEkga2V5IG5vdCBjb25maWd1cmVkLicpO1xuICAgICAgZXhwZWN0KG1vY2tBc3NvY2lhdGlvbnNWNEJhc2ljQXBpR2V0UGFnZSkubm90LnRvSGF2ZUJlZW5DYWxsZWQoKTtcbiAgICAgIGV4cGVjdChtb2NrRW5nYWdlbWVudHNTZWFyY2hBcGlEb1NlYXJjaCkubm90LnRvSGF2ZUJlZW5DYWxsZWQoKTtcbiAgICB9KTtcblxuICAgIGl0KCdzaG91bGQgcmV0dXJuIGVycm9yIGlmIGFzc29jaWF0aW9ucyBBUEkgY2FsbCBmYWlscycsIGFzeW5jICgpID0+IHtcbiAgICAgIGNvbnN0IGFwaUVycm9yID0gbmV3IEVycm9yKCdBc3NvYyBBUEkgRXJyb3InKTtcbiAgICAgIG1vY2tBc3NvY2lhdGlvbnNWNEJhc2ljQXBpR2V0UGFnZS5tb2NrUmVqZWN0ZWRWYWx1ZShhcGlFcnJvcik7XG4gICAgICBjb25zdCByZXN1bHQgPSBhd2FpdCBnZXRIdWJTcG90Q29udGFjdEFjdGl2aXRpZXModXNlcklkLCBjb250YWN0SWQpO1xuICAgICAgZXhwZWN0KHJlc3VsdC5zdWNjZXNzKS50b0JlKGZhbHNlKTtcbiAgICAgIGV4cGVjdChyZXN1bHQubWVzc2FnZSkudG9Db250YWluKFxuICAgICAgICAnRmFpbGVkIHRvIGZldGNoIGNvbnRhY3QgYWN0aXZpdGllczogQXNzb2MgQVBJIEVycm9yJ1xuICAgICAgKTtcbiAgICAgIGV4cGVjdChjb25zb2xlRXJyb3JTcHkpLnRvSGF2ZUJlZW5DYWxsZWRXaXRoKFxuICAgICAgICBgRXJyb3IgZmV0Y2hpbmcgSHViU3BvdCBjb250YWN0IGFjdGl2aXRpZXMgZm9yIGNvbnRhY3QgJHtjb250YWN0SWR9LCB1c2VySWQgJHt1c2VySWR9OmAsXG4gICAgICAgIGFwaUVycm9yLm1lc3NhZ2VcbiAgICAgICk7XG4gICAgfSk7XG5cbiAgICBpdCgnc2hvdWxkIHJldHVybiBlcnJvciBpZiBlbmdhZ2VtZW50cyBzZWFyY2ggQVBJIGNhbGwgZmFpbHMnLCBhc3luYyAoKSA9PiB7XG4gICAgICBtb2NrQXNzb2NpYXRpb25zVjRCYXNpY0FwaUdldFBhZ2UubW9ja1Jlc29sdmVkVmFsdWUoXG4gICAgICAgIG1vY2tBc3NvY2lhdGlvblBhZ2UoW21vY2tFbmdhZ2VtZW50SWQxXSlcbiAgICAgICk7XG4gICAgICBjb25zdCBhcGlFcnJvciA9IG5ldyBFcnJvcignU2VhcmNoIEFQSSBFcnJvcicpO1xuICAgICAgbW9ja0VuZ2FnZW1lbnRzU2VhcmNoQXBpRG9TZWFyY2gubW9ja1JlamVjdGVkVmFsdWUoYXBpRXJyb3IpO1xuICAgICAgY29uc3QgcmVzdWx0ID0gYXdhaXQgZ2V0SHViU3BvdENvbnRhY3RBY3Rpdml0aWVzKHVzZXJJZCwgY29udGFjdElkKTtcbiAgICAgIGV4cGVjdChyZXN1bHQuc3VjY2VzcykudG9CZShmYWxzZSk7XG4gICAgICBleHBlY3QocmVzdWx0Lm1lc3NhZ2UpLnRvQ29udGFpbihcbiAgICAgICAgJ0ZhaWxlZCB0byBmZXRjaCBjb250YWN0IGFjdGl2aXRpZXM6IFNlYXJjaCBBUEkgRXJyb3InXG4gICAgICApO1xuICAgIH0pO1xuICAgIGl0KCdzaG91bGQgcmV0dXJuIGVycm9yIGlmIGNvbnRhY3RJZCBpcyBtaXNzaW5nJywgYXN5bmMgKCkgPT4ge1xuICAgICAgY29uc3QgcmVzdWx0ID0gYXdhaXQgZ2V0SHViU3BvdENvbnRhY3RBY3Rpdml0aWVzKHVzZXJJZCwgJycpO1xuICAgICAgZXhwZWN0KHJlc3VsdCkudG9FcXVhbCh7XG4gICAgICAgIHN1Y2Nlc3M6IGZhbHNlLFxuICAgICAgICBhY3Rpdml0aWVzOiBbXSxcbiAgICAgICAgbWVzc2FnZTogJ0NvbnRhY3QgSUQgaXMgcmVxdWlyZWQuJyxcbiAgICAgIH0pO1xuICAgICAgZXhwZWN0KG1vY2tBc3NvY2lhdGlvbnNWNEJhc2ljQXBpR2V0UGFnZSkubm90LnRvSGF2ZUJlZW5DYWxsZWQoKTtcbiAgICB9KTtcbiAgfSk7XG59KTtcbiJdfQ==