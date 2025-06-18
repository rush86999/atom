import { getHubSpotContactByEmail, createHubSpotContact, logEmailToHubSpotContact, getHubSpotContactActivities } from './hubspotSkills';
import { ATOM_HUBSPOT_API_KEY } from '../_libs/constants';
import { Client } from '@hubspot/api-client';
import {
  HubSpotContactProperties,
  GetHubSpotContactResponse,
  CreateHubSpotContactResponse,
  HubSpotContact,
  HubSpotEmailEngagementProperties,
  HubSpotEngagement,
  LogEngagementResponse,
  GetContactActivitiesResponse
} from '../types';
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
const mockExpectedContact: HubSpotContact = {
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
(Client as jest.Mock).mockImplementation(() => mockHubSpotClientInstance);

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
const setMockApiKey = (key: string | null) => {
  jest.spyOn(require('../_libs/constants'), 'ATOM_HUBSPOT_API_KEY', 'get').mockReturnValue(key);
};


describe('hubspotSkills', () => {
  let consoleErrorSpy: jest.SpyInstance;
  let consoleLogSpy: jest.SpyInstance;

  beforeEach(() => {
    // Reset mocks before each test
    resetAllCrmMocks(); // Reset all CRM method mocks
    (Client as jest.Mock).mockImplementation(() => mockHubSpotClientInstance); // Ensure client is reset
    setMockApiKey('test-api-key'); // Reset to default valid API key

    // Spy on console.error and console.log
    consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
    consoleLogSpy = jest.spyOn(console, 'log').mockImplementation(() => {});
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
      mockContactsSearchApi.mockResolvedValue({ results: [mockApiContactResult] });
      const result = await getHubSpotContactByEmail(testUserId, testEmail);
      expect(result).toEqual(mockExpectedContact);
      expect(mockContactsSearchApi).toHaveBeenCalledWith({
        query: testEmail,
        properties: ['email', 'firstname', 'lastname', 'company', 'hs_object_id', 'createdate', 'lastmodifieddate'],
        filterGroups: [{ filters: [{ propertyName: 'email', operator: 'EQ', value: testEmail }] }],
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
      (apiError as any).response = { body: 'Some error body' };
      mockContactsSearchApi.mockRejectedValue(apiError);
      const result = await getHubSpotContactByEmail(testUserId, testEmail);
      expect(result).toBeNull();
      expect(consoleErrorSpy).toHaveBeenCalledWith(`Error fetching HubSpot contact by email ${testEmail} for userId ${testUserId}:`, apiError.message);
      expect(consoleErrorSpy).toHaveBeenCalledWith('HubSpot API Error Body:', 'Some error body');
    });
  });

  describe('createHubSpotContact', () => {
    const testUserId = 'user123';
    const contactProperties: HubSpotContactProperties = {
      email: 'new@example.com',
      firstname: 'New',
      lastname: 'User',
      company: 'New Company',
    };

    it('should create a contact and return success response', async () => {
      const createdApiContact = { ...mockApiContactResult, id: '67890', properties: { ...mockApiContactResult.properties, ...contactProperties }, createdAt: new Date(), updatedAt: new Date() };
      mockContactsBasicApiCreate.mockResolvedValue(createdApiContact);

      const result = await createHubSpotContact(testUserId, contactProperties);

      const expectedCreatedContact: HubSpotContact = {
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
      expect(mockContactsBasicApiCreate).toHaveBeenCalledWith({ properties: contactProperties });
      expect(consoleLogSpy).toHaveBeenCalledWith(`createHubSpotContact called for userId: ${testUserId} with properties:`, contactProperties);
    });

    it('should return error if email is missing', async () => {
      const propertiesWithoutEmail: HubSpotContactProperties = { firstname: 'No', lastname: 'Email' };
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
      (apiError as any).response = { body: Buffer.from(JSON.stringify({ message: "Detailed API error" })) };
      mockContactsBasicApiCreate.mockRejectedValue(apiError);
      const result = await createHubSpotContact(testUserId, contactProperties);
      expect(result.success).toBe(false);
      expect(result.message).toBe('Failed to create contact in HubSpot: Detailed API error');
      expect(consoleErrorSpy).toHaveBeenCalledWith(`Error creating HubSpot contact for userId ${testUserId} with email ${contactProperties.email}:`, apiError.message);
      expect(consoleErrorSpy).toHaveBeenCalledWith('HubSpot API Error Body:', {"message": "Detailed API error"});
    });

     it('should return specific message if contact already exists (CONFLICT)', async () => {
      const apiConflictError = new Error('Conflict');
      (apiConflictError as any).response = { body: Buffer.from(JSON.stringify({ message: "Contact already exists.", category: "CONFLICT" })) };
      mockContactsBasicApiCreate.mockRejectedValue(apiConflictError);
      const result = await createHubSpotContact(testUserId, contactProperties);
      expect(result.success).toBe(false);
      expect(result.message).toBe('Failed to create contact in HubSpot: A contact with this email already exists.');
    });
  });

  describe('logEmailToHubSpotContact', () => {
    const userId = 'user-test-123';
    const contactId = 'contact-456';
    const emailDetails: HubSpotEmailEngagementProperties = {
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
            types: [{ associationCategory: 'HUBSPOT_DEFINED', associationTypeId: CONTACT_TO_ENGAGEMENT_ASSOCIATION_TYPE_ID }],
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
       (apiError as any).response = { body: Buffer.from(JSON.stringify({ message: "Detailed creation error" })) };
      mockEngagementsBasicApiCreate.mockRejectedValue(apiError);

      const result = await logEmailToHubSpotContact(userId, contactId, emailDetails);

      expect(result.success).toBe(false);
      expect(result.message).toBe('Failed to log email to HubSpot: Detailed creation error');
      expect(consoleErrorSpy).toHaveBeenCalledWith(`Error logging email to HubSpot contact ${contactId} for userId ${userId}:`, apiError.message);
    });
     it('should return error if contactId is missing', async () => {
      const result = await logEmailToHubSpotContact(userId, '', emailDetails);
      expect(result).toEqual({ success: false, message: 'Contact ID is required to log an email.' });
      expect(mockEngagementsBasicApiCreate).not.toHaveBeenCalled();
    });

    it('should return error if essential emailDetails are missing', async () => {
      // @ts-ignore
      const result = await logEmailToHubSpotContact(userId, contactId, { subject: 'missing other fields' });
      expect(result).toEqual({ success: false, message: 'Email details (activityTimestamp, subject, htmlBody) are required.' });
      expect(mockEngagementsBasicApiCreate).not.toHaveBeenCalled();
    });
  });

  describe('getHubSpotContactActivities', () => {
    const userId = 'user-test-456';
    const contactId = 'contact-789';
    const mockEngagementId1 = 'eng-111';
    const mockEngagementId2 = 'eng-222';

    const mockAssociationPage = (ids: string[]) => ({
      results: ids.map(id => ({ toObjectId: id, type: 'contact_to_engagement' })), // Simplified, check actual type string if needed
      paging: { next: { after: ids.length > 0 ? 'nextpagecursor' : undefined } }
    });

    const mockEngagementSearchResult = (id: string, type: 'EMAIL' | 'MEETING' = 'EMAIL') => ({
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
        results: [mockEngagementSearchResult(mockEngagementId1), mockEngagementSearchResult(mockEngagementId2)],
        paging: { next: { after: 'nextSearchCursor' } }
      });

      const result = await getHubSpotContactActivities(userId, contactId);

      expect(result.success).toBe(true);
      expect(result.activities.length).toBe(2);
      expect(result.activities[0].id).toBe(mockEngagementId1);
      expect(result.nextPage).toBe('nextSearchCursor'); // This should be from searchApi.doSearch paging
      expect(mockAssociationsV4BasicApiGetPage).toHaveBeenCalledWith("0-1", contactId, "0-31", undefined, 50);
      expect(mockEngagementsSearchApiDoSearch).toHaveBeenCalledWith(expect.objectContaining({
        filterGroups: [
          { filters: [
              { propertyName: 'hs_object_id', operator: 'IN', values: [mockEngagementId1, mockEngagementId2] }
          ]}
        ],
        limit: 10,
        sorts: [{ propertyName: 'hs_timestamp', direction: 'DESCENDING' }],
      }));
    });

    it('should retrieve activities with specific filters (EMAIL, limit 5, ASC, since)', async () => {
      const sinceDate = new Date('2023-01-01T00:00:00.000Z');
      const sinceTimestamp = sinceDate.getTime().toString();
      mockAssociationsV4BasicApiGetPage.mockResolvedValue(mockAssociationPage([mockEngagementId1]));
      mockEngagementsSearchApiDoSearch.mockResolvedValue({ results: [mockEngagementSearchResult(mockEngagementId1, 'EMAIL')] });

      await getHubSpotContactActivities(userId, contactId, {
        activityTypes: ['EMAIL'],
        limit: 5,
        sort: 'ASC',
        since: sinceDate.toISOString(),
      });

      expect(mockEngagementsSearchApiDoSearch).toHaveBeenCalledWith(expect.objectContaining({
        filterGroups: [
          { filters: expect.arrayContaining([
            { propertyName: 'hs_engagement_type', operator: 'IN', values: ['EMAIL'] },
            { propertyName: 'hs_timestamp', operator: 'GTE', value: sinceTimestamp },
            { propertyName: 'hs_object_id', operator: 'IN', values: [mockEngagementId1] }
          ])}
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
      expect(result).toEqual({ success: false, activities: [], message: 'Contact ID is required.' });
      expect(mockAssociationsV4BasicApiGetPage).not.toHaveBeenCalled();
    });
  });
});
