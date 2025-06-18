import { getHubSpotContactByEmail, createHubSpotContact } from './hubspotSkills';
import { ATOM_HUBSPOT_API_KEY } from '../_libs/constants';
import { Client } from '@hubspot/api-client';
import { HubSpotContactProperties, GetHubSpotContactResponse, CreateHubSpotContactResponse, HubSpotContact } from '../types';

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
const mockDoSearch = jest.fn();
const mockCreate = jest.fn();

// Mock the Client constructor and its methods
const mockHubSpotClientInstance = {
  crm: {
    contacts: {
      searchApi: {
        doSearch: mockDoSearch,
      },
      basicApi: {
        create: mockCreate,
      },
    },
  },
};

// Mock the default export of the Client
(Client as jest.Mock).mockImplementation(() => mockHubSpotClientInstance);


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
    jest.clearAllMocks();
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
      mockDoSearch.mockResolvedValue({ results: [mockApiContactResult] });
      const result = await getHubSpotContactByEmail(testUserId, testEmail);
      expect(result).toEqual(mockExpectedContact);
      expect(mockDoSearch).toHaveBeenCalledWith({
        query: testEmail,
        properties: ['email', 'firstname', 'lastname', 'company', 'hs_object_id', 'createdate', 'lastmodifieddate'],
        filterGroups: [{ filters: [{ propertyName: 'email', operator: 'EQ', value: testEmail }] }],
      });
      expect(consoleLogSpy).toHaveBeenCalledWith(`getHubSpotContactByEmail called for userId: ${testUserId}, email: ${testEmail}`);
    });

    it('should return null if contact not found', async () => {
      mockDoSearch.mockResolvedValue({ results: [] });
      const result = await getHubSpotContactByEmail(testUserId, testEmail);
      expect(result).toBeNull();
      expect(consoleLogSpy).toHaveBeenCalledWith(`No HubSpot contact found for email: ${testEmail}`);
    });

    it('should return null and log error if API key is missing', async () => {
      setMockApiKey(null); // Simulate missing API key
      const result = await getHubSpotContactByEmail(testUserId, testEmail);
      expect(result).toBeNull();
      expect(consoleErrorSpy).toHaveBeenCalledWith('HubSpot API key not configured.');
      expect(mockDoSearch).not.toHaveBeenCalled();
    });

    it('should return null and log error if HubSpot API call fails', async () => {
      const apiError = new Error('HubSpot API Error');
      (apiError as any).response = { body: 'Some error body' };
      mockDoSearch.mockRejectedValue(apiError);
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
      mockCreate.mockResolvedValue(createdApiContact);

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
      expect(mockCreate).toHaveBeenCalledWith({ properties: contactProperties });
      expect(consoleLogSpy).toHaveBeenCalledWith(`createHubSpotContact called for userId: ${testUserId} with properties:`, contactProperties);
    });

    it('should return error if email is missing', async () => {
      const propertiesWithoutEmail: HubSpotContactProperties = { firstname: 'No', lastname: 'Email' };
      const result = await createHubSpotContact(testUserId, propertiesWithoutEmail);
      expect(result).toEqual({
        success: false,
        message: 'Email is required to create a HubSpot contact.',
      });
      expect(mockCreate).not.toHaveBeenCalled();
    });

    it('should return error if API key is missing', async () => {
      setMockApiKey(null); // Simulate missing API key
      const result = await createHubSpotContact(testUserId, contactProperties);
      expect(result).toEqual({
        success: false,
        message: 'HubSpot API key not configured.',
      });
      expect(mockCreate).not.toHaveBeenCalled();
      expect(consoleErrorSpy).toHaveBeenCalledWith('HubSpot API key not configured.');
    });

    it('should return error and log if HubSpot API call fails', async () => {
      const apiError = new Error('HubSpot Create Error');
      (apiError as any).response = { body: Buffer.from(JSON.stringify({ message: "Detailed API error" })) };
      mockCreate.mockRejectedValue(apiError);
      const result = await createHubSpotContact(testUserId, contactProperties);
      expect(result.success).toBe(false);
      expect(result.message).toBe('Failed to create contact in HubSpot: Detailed API error');
      expect(consoleErrorSpy).toHaveBeenCalledWith(`Error creating HubSpot contact for userId ${testUserId} with email ${contactProperties.email}:`, apiError.message);
      expect(consoleErrorSpy).toHaveBeenCalledWith('HubSpot API Error Body:', {"message": "Detailed API error"});
    });

     it('should return specific message if contact already exists (CONFLICT)', async () => {
      const apiConflictError = new Error('Conflict');
      (apiConflictError as any).response = { body: Buffer.from(JSON.stringify({ message: "Contact already exists.", category: "CONFLICT" })) };
      mockCreate.mockRejectedValue(apiConflictError);
      const result = await createHubSpotContact(testUserId, contactProperties);
      expect(result.success).toBe(false);
      expect(result.message).toBe('Failed to create contact in HubSpot: A contact with this email already exists.');
    });
  });
});
