import { handleGetHubSpotContactByEmail, handleCreateHubSpotContact } from '../hubspot';
import * as hubspotSkills from '../hubspotSkills';
import { ATOM_HUBSPOT_PORTAL_ID } from '../../_libs/constants';

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
            (hubspotSkills.getHubSpotContactByEmail as jest.Mock).mockResolvedValue(mockContact);

            const result = await handleGetHubSpotContactByEmail('test-user', { email: 'test@example.com' });

            expect(result).toContain('HubSpot Contact Found:');
            expect(result).toContain('Test User');
        });

        it('should return a message when no contact is found', async () => {
            (hubspotSkills.getHubSpotContactByEmail as jest.Mock).mockResolvedValue(null);

            const result = await handleGetHubSpotContactByEmail('test-user', { email: 'test@example.com' });

            expect(result).toBe('No HubSpot contact found with email: test@example.com.');
        });

        it('should return an error message when the email is missing', async () => {
            const result = await handleGetHubSpotContactByEmail('test-user', {});

            expect(result).toBe('Email is required and must be a non-empty string to get a HubSpot contact by email.');
        });

        it('should return an error message when an error occurs', async () => {
            (hubspotSkills.getHubSpotContactByEmail as jest.Mock).mockRejectedValue(new Error('Test Error'));

            const result = await handleGetHubSpotContactByEmail('test-user', { email: 'test@example.com' });

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
            (hubspotSkills.createHubSpotContact as jest.Mock).mockResolvedValue({
                success: true,
                contactId: 'test-contact-id',
                hubSpotContact: mockContact,
            });

            const result = await handleCreateHubSpotContact('test-user', { email: 'test@example.com' });

            expect(result).toContain('HubSpot contact created via NLU!');
        });

        it('should return an error message when the email is missing', async () => {
            const result = await handleCreateHubSpotContact('test-user', {});

            expect(result).toBe('Email is required (and must be a string) to create a HubSpot contact via NLU.');
        });

        it('should return an error message when an error occurs', async () => {
            (hubspotSkills.createHubSpotContact as jest.Mock).mockRejectedValue(new Error('Test Error'));

            const result = await handleCreateHubSpotContact('test-user', { email: 'test@example.com' });

            expect(result).toBe('Sorry, there was an issue creating the HubSpot contact based on your request.');
        });
    });
});
