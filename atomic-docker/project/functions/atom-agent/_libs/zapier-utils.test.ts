import {
    addZapierWebhook,
    listZapierWebhooks,
    deleteZapierWebhook,
    getZapierWebhookUrl
} from './zapier-utils';
import * as tokenUtils from './token-utils'; // To mock encryptToken and decryptToken
import * as constants from './constants';
import got from 'got';

// Mocks
jest.mock('got');
const mockedGot = got as jest.Mocked<typeof got>;

jest.mock('./token-utils', () => ({
    encryptToken: jest.fn(),
    decryptToken: jest.fn(),
}));
const mockedEncryptToken = tokenUtils.encryptToken as jest.Mock;
const mockedDecryptToken = tokenUtils.decryptToken as jest.Mock;

// Mock constants module
jest.mock('./constants', () => ({
    ...jest.requireActual('./constants'),
    HASURA_GRAPHQL_URL: 'mock_hasura_url_zapier',
    HASURA_ADMIN_SECRET: 'mock_hasura_secret_zapier',
}));

// Helper to override Hasura constants for specific tests
const mockHasuraConfig = (url?: string | null, secret?: string | null) => {
    Object.defineProperty(constants, 'HASURA_GRAPHQL_URL', { value: url, configurable: true, writable: true });
    Object.defineProperty(constants, 'HASURA_ADMIN_SECRET', { value: secret, configurable: true, writable: true });
};


describe('Zapier Utilities - zapier-utils.ts', () => {
    let consoleErrorSpy: jest.SpyInstance;
    const mockUserId = 'test-user-zap-util';
    const mockZapName = 'Test Zap';
    const mockWebhookUrl = 'https://hooks.zapier.com/hooks/catch/test/123/';
    const mockEncryptedUrl = 'encrypted_zap_url';
    const mockZapId = 'zap-uuid-123';

    beforeEach(() => {
        jest.clearAllMocks();
        consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
        // Restore default Hasura constants
        mockHasuraConfig('mock_hasura_url_zapier', 'mock_hasura_secret_zapier');
    });
    afterEach(() => {
        consoleErrorSpy.mockRestore();
    });

    describe('addZapierWebhook', () => {
        it('should add/update webhook successfully', async () => {
            mockedEncryptToken.mockResolvedValue(mockEncryptedUrl);
            mockedGot.post.mockResolvedValue({
                json: jest.fn().mockResolvedValue({ data: { insert_user_atom_agent_zapier_webhooks_one: { id: mockZapId, zap_name: mockZapName } } })
            } as any);

            const result = await addZapierWebhook(mockUserId, mockZapName, mockWebhookUrl);

            expect(mockedEncryptToken).toHaveBeenCalledWith(mockWebhookUrl);
            expect(mockedGot.post).toHaveBeenCalledWith('mock_hasura_url_zapier', expect.objectContaining({
                json: expect.objectContaining({
                    query: expect.stringContaining('mutation AddZapierWebhook'),
                    variables: { userId: mockUserId, zapName: mockZapName, encryptedUrl: mockEncryptedUrl }
                }),
                headers: { 'x-hasura-admin-secret': 'mock_hasura_secret_zapier' }
            }));
            expect(result).toEqual({ id: mockZapId, zap_name: mockZapName });
        });

        it('should throw if encryption fails', async () => {
            mockedEncryptToken.mockResolvedValue(null);
            await expect(addZapierWebhook(mockUserId, mockZapName, mockWebhookUrl))
                .rejects.toThrow('Webhook URL encryption failed.');
        });

        it('should throw if Hasura returns error', async () => {
            mockedEncryptToken.mockResolvedValue(mockEncryptedUrl);
            mockedGot.post.mockResolvedValue({
                json: jest.fn().mockResolvedValue({ errors: [{ message: "DB constraint error" }] })
            } as any);
            await expect(addZapierWebhook(mockUserId, mockZapName, mockWebhookUrl))
                .rejects.toThrow('Failed to save Zapier webhook: DB constraint error');
        });

        it('should throw if Hasura config is missing', async () => {
            mockHasuraConfig(null, 'secret');
            await expect(addZapierWebhook(mockUserId, mockZapName, mockWebhookUrl))
                .rejects.toThrow('Server configuration error for Zapier webhook storage.');
        });
    });

    describe('listZapierWebhooks', () => {
        it('should return list of webhooks', async () => {
            const mockList = [{ id: 'z1', zap_name: 'Zap1' }, { id: 'z2', zap_name: 'Zap2' }];
            mockedGot.post.mockResolvedValue({
                json: jest.fn().mockResolvedValue({ data: { user_atom_agent_zapier_webhooks: mockList } })
            } as any);
            const result = await listZapierWebhooks(mockUserId);
            expect(mockedGot.post).toHaveBeenCalledWith('mock_hasura_url_zapier', expect.objectContaining({
                json: expect.objectContaining({ query: expect.stringContaining('query ListZapierWebhooks') })
            }));
            expect(result).toEqual(mockList);
        });

        it('should return empty array if no webhooks', async () => {
            mockedGot.post.mockResolvedValue({
                json: jest.fn().mockResolvedValue({ data: { user_atom_agent_zapier_webhooks: [] } })
            } as any);
            const result = await listZapierWebhooks(mockUserId);
            expect(result).toEqual([]);
        });
    });

    describe('deleteZapierWebhook', () => {
        it('should delete webhook successfully', async () => {
            mockedGot.post.mockResolvedValue({
                json: jest.fn().mockResolvedValue({ data: { delete_user_atom_agent_zapier_webhooks: { affected_rows: 1 } } })
            } as any);
            const result = await deleteZapierWebhook(mockUserId, mockZapId);
            expect(mockedGot.post).toHaveBeenCalledWith('mock_hasura_url_zapier', expect.objectContaining({
                json: expect.objectContaining({ query: expect.stringContaining('mutation DeleteZapierWebhook') })
            }));
            expect(result).toEqual({ affected_rows: 1 });
        });
    });

    describe('getZapierWebhookUrl', () => {
        it('should get and decrypt webhook URL', async () => {
            mockedGot.post.mockResolvedValue({
                json: jest.fn().mockResolvedValue({ data: { user_atom_agent_zapier_webhooks: [{ webhook_url: mockEncryptedUrl }] } })
            } as any);
            mockedDecryptToken.mockResolvedValue(mockWebhookUrl);

            const result = await getZapierWebhookUrl(mockUserId, mockZapName);
            expect(mockedGot.post).toHaveBeenCalledWith('mock_hasura_url_zapier', expect.objectContaining({
                json: expect.objectContaining({ query: expect.stringContaining('query GetZapierWebhook') })
            }));
            expect(mockedDecryptToken).toHaveBeenCalledWith(mockEncryptedUrl);
            expect(result).toBe(mockWebhookUrl);
        });

        it('should return null if webhook not found', async () => {
            mockedGot.post.mockResolvedValue({
                json: jest.fn().mockResolvedValue({ data: { user_atom_agent_zapier_webhooks: [] } })
            } as any);
            const result = await getZapierWebhookUrl(mockUserId, mockZapName);
            expect(result).toBeNull();
        });

        it('should return null if decryption fails', async () => {
            mockedGot.post.mockResolvedValue({
                json: jest.fn().mockResolvedValue({ data: { user_atom_agent_zapier_webhooks: [{ webhook_url: mockEncryptedUrl }] } })
            } as any);
            mockedDecryptToken.mockResolvedValue(null);
            const result = await getZapierWebhookUrl(mockUserId, mockZapName);
            expect(result).toBeNull();
            expect(consoleErrorSpy).toHaveBeenCalledWith(expect.stringContaining('Failed to decrypt Zapier webhook URL'));
        });
    });
});
