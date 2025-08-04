import {
  getCanvaTokens,
  refreshAccessToken,
  createDesign,
} from './canvaSkills';
import { createAdminGraphQLClient } from '../../atomic-docker/project/functions/_utils/dbService';
import {
  decrypt,
  encrypt,
} from '../../atomic-docker/project/functions/_utils/crypto';
import { AuthorizationCode } from 'simple-oauth2';
import axios from 'axios';

jest.mock('../../atomic-docker/project/functions/_utils/dbService');
jest.mock('../../atomic-docker/project/functions/_utils/crypto');
jest.mock('simple-oauth2');
jest.mock('axios');

const mockedCreateAdminGraphQLClient = createAdminGraphQLClient as jest.Mock;
const mockedDecrypt = decrypt as jest.Mock;
const mockedEncrypt = encrypt as jest.Mock;
const mockedAuthorizationCode = AuthorizationCode as jest.Mock;
const mockedAxios = axios as jest.Mocked<typeof axios>;

describe('canvaSkills', () => {
  const userId = 'test-user-id';
  const encryptionKey = 'test-encryption-key';

  beforeEach(() => {
    jest.clearAllMocks();
    process.env.CANVA_TOKEN_ENCRYPTION_KEY = encryptionKey;
    process.env.CANVA_CLIENT_ID = 'test-client-id';
    process.env.CANVA_CLIENT_SECRET = 'test-client-secret';
  });

  describe('getCanvaTokens', () => {
    it('should return null if no tokens are found', async () => {
      mockedCreateAdminGraphQLClient.mockReturnValue({
        request: jest.fn().mockResolvedValue({ user_canva_tokens: [] }),
      });
      const tokens = await getCanvaTokens(userId);
      expect(tokens).toBeNull();
    });

    it('should return decrypted tokens if found', async () => {
      const encrypted_access_token = 'encrypted-access-token';
      const encrypted_refresh_token = 'encrypted-refresh-token';
      const token_expiry_timestamp = new Date().toISOString();
      mockedCreateAdminGraphQLClient.mockReturnValue({
        request: jest.fn().mockResolvedValue({
          user_canva_tokens: [
            {
              encrypted_access_token,
              encrypted_refresh_token,
              token_expiry_timestamp,
            },
          ],
        }),
      });
      mockedDecrypt.mockImplementation((token, key) => {
        if (token === encrypted_access_token) return 'decrypted-access-token';
        if (token === encrypted_refresh_token) return 'decrypted-refresh-token';
        return '';
      });

      const tokens = await getCanvaTokens(userId);

      expect(tokens).toEqual({
        accessToken: 'decrypted-access-token',
        refreshToken: 'decrypted-refresh-token',
        expiresAt: token_expiry_timestamp,
      });
      expect(mockedDecrypt).toHaveBeenCalledWith(
        encrypted_access_token,
        encryptionKey
      );
      expect(mockedDecrypt).toHaveBeenCalledWith(
        encrypted_refresh_token,
        encryptionKey
      );
    });
  });

  describe('refreshAccessToken', () => {
    it('should refresh the access token and update the database', async () => {
      const refreshToken = 'test-refresh-token';
      const newAccessToken = 'new-access-token';
      const newRefreshToken = 'new-refresh-token';
      const expiresAt = new Date(Date.now() + 3600 * 1000);

      const mockToken = {
        refresh: jest.fn().mockResolvedValue({
          token: {
            access_token: newAccessToken,
            refresh_token: newRefreshToken,
            expires_at: expiresAt,
            scope: 'design:content:write profile:read',
          },
        }),
      };

      const mockCreateToken = jest.fn().mockReturnValue(mockToken);
      mockedAuthorizationCode.mockImplementation(() => ({
        createToken: mockCreateToken,
      }));

      mockedEncrypt.mockImplementation((token, key) => `encrypted-${token}`);

      const mockRequest = jest.fn().mockResolvedValue({});
      mockedCreateAdminGraphQLClient.mockReturnValue({
        request: mockRequest,
      });

      const result = await refreshAccessToken(userId, refreshToken);

      expect(result).toBe(newAccessToken);
      expect(mockRequest).toHaveBeenCalledWith(expect.any(String), {
        userId,
        accessToken: `encrypted-${newAccessToken}`,
        refreshToken: `encrypted-${newRefreshToken}`,
        expiryTimestamp: expiresAt.toISOString(),
        scopesArr: ['design:content:write', 'profile:read'],
      });
    });
  });

  describe('createDesign', () => {
    it('should create a design with a valid access token', async () => {
      const title = 'Test Design';
      const accessToken = 'valid-access-token';
      const designData = {
        id: 'design-id',
        title,
        urls: { edit_url: 'edit-url' },
      };

      jest
        .spyOn(global, 'Date')
        .mockImplementation(() => new Date('2025-01-01T00:00:00.000Z'));

      const getCanvaTokensMock = jest.fn().mockResolvedValue({
        accessToken,
        refreshToken: 'refresh-token',
        expiresAt: new Date('2025-01-02T00:00:00.000Z').toISOString(),
      });

      const canvaSkills = require('./canvaSkills');
      canvaSkills.getCanvaTokens = getCanvaTokensMock;

      mockedAxios.post.mockResolvedValue({ data: designData });

      const result = await createDesign(userId, title);

      expect(result).toEqual(designData);
      expect(mockedAxios.post).toHaveBeenCalledWith(
        'https://api.canva.com/rest/v1/designs',
        { title, design_type: { type: 'preset', name: 'presentation' } },
        {
          headers: {
            Authorization: `Bearer ${accessToken}`,
            'Content-Type': 'application/json',
          },
        }
      );
    });
  });
});
