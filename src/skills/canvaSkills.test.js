"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const canvaSkills_1 = require("./canvaSkills");
const dbService_1 = require("../../atomic-docker/project/functions/_utils/dbService");
const crypto_1 = require("../../atomic-docker/project/functions/_utils/crypto");
const simple_oauth2_1 = require("simple-oauth2");
const axios_1 = __importDefault(require("axios"));
jest.mock('../../atomic-docker/project/functions/_utils/dbService');
jest.mock('../../atomic-docker/project/functions/_utils/crypto');
jest.mock('simple-oauth2');
jest.mock('axios');
const mockedCreateAdminGraphQLClient = dbService_1.createAdminGraphQLClient;
const mockedDecrypt = crypto_1.decrypt;
const mockedEncrypt = crypto_1.encrypt;
const mockedAuthorizationCode = simple_oauth2_1.AuthorizationCode;
const mockedAxios = axios_1.default;
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
            const tokens = await (0, canvaSkills_1.getCanvaTokens)(userId);
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
                if (token === encrypted_access_token)
                    return 'decrypted-access-token';
                if (token === encrypted_refresh_token)
                    return 'decrypted-refresh-token';
                return '';
            });
            const tokens = await (0, canvaSkills_1.getCanvaTokens)(userId);
            expect(tokens).toEqual({
                accessToken: 'decrypted-access-token',
                refreshToken: 'decrypted-refresh-token',
                expiresAt: token_expiry_timestamp,
            });
            expect(mockedDecrypt).toHaveBeenCalledWith(encrypted_access_token, encryptionKey);
            expect(mockedDecrypt).toHaveBeenCalledWith(encrypted_refresh_token, encryptionKey);
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
            const result = await (0, canvaSkills_1.refreshAccessToken)(userId, refreshToken);
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
            const result = await (0, canvaSkills_1.createDesign)(userId, title);
            expect(result).toEqual(designData);
            expect(mockedAxios.post).toHaveBeenCalledWith('https://api.canva.com/rest/v1/designs', { title, design_type: { type: 'preset', name: 'presentation' } }, {
                headers: {
                    Authorization: `Bearer ${accessToken}`,
                    'Content-Type': 'application/json',
                },
            });
        });
    });
});
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiY2FudmFTa2lsbHMudGVzdC5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImNhbnZhU2tpbGxzLnRlc3QudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7Ozs7QUFBQSwrQ0FJdUI7QUFDdkIsc0ZBQWtHO0FBQ2xHLGdGQUc2RDtBQUM3RCxpREFBa0Q7QUFDbEQsa0RBQTBCO0FBRTFCLElBQUksQ0FBQyxJQUFJLENBQUMsd0RBQXdELENBQUMsQ0FBQztBQUNwRSxJQUFJLENBQUMsSUFBSSxDQUFDLHFEQUFxRCxDQUFDLENBQUM7QUFDakUsSUFBSSxDQUFDLElBQUksQ0FBQyxlQUFlLENBQUMsQ0FBQztBQUMzQixJQUFJLENBQUMsSUFBSSxDQUFDLE9BQU8sQ0FBQyxDQUFDO0FBRW5CLE1BQU0sOEJBQThCLEdBQUcsb0NBQXFDLENBQUM7QUFDN0UsTUFBTSxhQUFhLEdBQUcsZ0JBQW9CLENBQUM7QUFDM0MsTUFBTSxhQUFhLEdBQUcsZ0JBQW9CLENBQUM7QUFDM0MsTUFBTSx1QkFBdUIsR0FBRyxpQ0FBOEIsQ0FBQztBQUMvRCxNQUFNLFdBQVcsR0FBRyxlQUFrQyxDQUFDO0FBRXZELFFBQVEsQ0FBQyxhQUFhLEVBQUUsR0FBRyxFQUFFO0lBQzNCLE1BQU0sTUFBTSxHQUFHLGNBQWMsQ0FBQztJQUM5QixNQUFNLGFBQWEsR0FBRyxxQkFBcUIsQ0FBQztJQUU1QyxVQUFVLENBQUMsR0FBRyxFQUFFO1FBQ2QsSUFBSSxDQUFDLGFBQWEsRUFBRSxDQUFDO1FBQ3JCLE9BQU8sQ0FBQyxHQUFHLENBQUMsMEJBQTBCLEdBQUcsYUFBYSxDQUFDO1FBQ3ZELE9BQU8sQ0FBQyxHQUFHLENBQUMsZUFBZSxHQUFHLGdCQUFnQixDQUFDO1FBQy9DLE9BQU8sQ0FBQyxHQUFHLENBQUMsbUJBQW1CLEdBQUcsb0JBQW9CLENBQUM7SUFDekQsQ0FBQyxDQUFDLENBQUM7SUFFSCxRQUFRLENBQUMsZ0JBQWdCLEVBQUUsR0FBRyxFQUFFO1FBQzlCLEVBQUUsQ0FBQywyQ0FB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ZXNDb250ZW50IjpbImltcG9ydCB7XG4gIGdldENhbnZhVG9rZW5zLFxuICByZWZyZXNoQWNjZXNzVG9rZW4sXG4gIGNyZWF0ZURlc2lnbixcbn0gZnJvbSAnLi9jYW52YVNraWxscyc7XG5pbXBvcnQgeyBjcmVhdGVBZG1pbkdyYXBoUUxDbGllbnQgfSBmcm9tICcuLi8uLi9hdG9taWMtZG9ja2VyL3Byb2plY3QvZnVuY3Rpb25zL191dGlscy9kYlNlcnZpY2UnO1xuaW1wb3J0IHtcbiAgZGVjcnlwdCxcbiAgZW5jcnlwdCxcbn0gZnJvbSAnLi4vLi4vYXRvbWljLWRvY2tlci9wcm9qZWN0L2Z1bmN0aW9ucy9fdXRpbHMvY3J5cHRvJztcbmltcG9ydCB7IEF1dGhvcml6YXRpb25Db2RlIH0gZnJvbSAnc2ltcGxlLW9hdXRoMic7XG5pbXBvcnQgYXhpb3MgZnJvbSAnYXhpb3MnO1xuXG5qZXN0Lm1vY2soJy4uLy4uL2F0b21pYy1kb2NrZXIvcHJvamVjdC9mdW5jdGlvbnMvX3V0aWxzL2RiU2VydmljZScpO1xuamVzdC5tb2NrKCcuLi8uLi9hdG9taWMtZG9ja2VyL3Byb2plY3QvZnVuY3Rpb25zL191dGlscy9jcnlwdG8nKTtcbmplc3QubW9jaygnc2ltcGxlLW9hdXRoMicpO1xuamVzdC5tb2NrKCdheGlvcycpO1xuXG5jb25zdCBtb2NrZWRDcmVhdGVBZG1pbkdyYXBoUUxDbGllbnQgPSBjcmVhdGVBZG1pbkdyYXBoUUxDbGllbnQgYXMgamVzdC5Nb2NrO1xuY29uc3QgbW9ja2VkRGVjcnlwdCA9IGRlY3J5cHQgYXMgamVzdC5Nb2NrO1xuY29uc3QgbW9ja2VkRW5jcnlwdCA9IGVuY3J5cHQgYXMgamVzdC5Nb2NrO1xuY29uc3QgbW9ja2VkQXV0aG9yaXphdGlvbkNvZGUgPSBBdXRob3JpemF0aW9uQ29kZSBhcyBqZXN0Lk1vY2s7XG5jb25zdCBtb2NrZWRBeGlvcyA9IGF4aW9zIGFzIGplc3QuTW9ja2VkPHR5cGVvZiBheGlvcz47XG5cbmRlc2NyaWJlKCdjYW52YVNraWxscycsICgpID0+IHtcbiAgY29uc3QgdXNlcklkID0gJ3Rlc3QtdXNlci1pZCc7XG4gIGNvbnN0IGVuY3J5cHRpb25LZXkgPSAndGVzdC1lbmNyeXB0aW9uLWtleSc7XG5cbiAgYmVmb3JlRWFjaCgoKSA9PiB7XG4gICAgamVzdC5jbGVhckFsbE1vY2tzKCk7XG4gICAgcHJvY2Vzcy5lbnYuQ0FOVkFfVE9LRU5fRU5DUllQVElPTl9LRVkgPSBlbmNyeXB0aW9uS2V5O1xuICAgIHByb2Nlc3MuZW52LkNBTlZBX0NMSUVOVF9JRCA9ICd0ZXN0LWNsaWVudC1pZCc7XG4gICAgcHJvY2Vzcy5lbnYuQ0FOVkFfQ0xJRU5UX1NFQ1JFVCA9ICd0ZXN0LWNsaWVudC1zZWNyZXQnO1xuICB9KTtcblxuICBkZXNjcmliZSgnZ2V0Q2FudmFUb2tlbnMnLCAoKSA9PiB7XG4gICAgaXQoJ3Nob3VsZCByZXR1cm4gbnVsbCBpZiBubyB0b2tlbnMgYXJlIGZvdW5kJywgYXN5bmMgKCkgPT4ge1xuICAgICAgbW9ja2VkQ3JlYXRlQWRtaW5HcmFwaFFMQ2xpZW50Lm1vY2tSZXR1cm5WYWx1ZSh7XG4gICAgICAgIHJlcXVlc3Q6IGplc3QuZm4oKS5tb2NrUmVzb2x2ZWRWYWx1ZSh7IHVzZXJfY2FudmFfdG9rZW5zOiBbXSB9KSxcbiAgICAgIH0pO1xuICAgICAgY29uc3QgdG9rZW5zID0gYXdhaXQgZ2V0Q2FudmFUb2tlbnModXNlcklkKTtcbiAgICAgIGV4cGVjdCh0b2tlbnMpLnRvQmVOdWxsKCk7XG4gICAgfSk7XG5cbiAgICBpdCgnc2hvdWxkIHJldHVybiBkZWNyeXB0ZWQgdG9rZW5zIGlmIGZvdW5kJywgYXN5bmMgKCkgPT4ge1xuICAgICAgY29uc3QgZW5jcnlwdGVkX2FjY2Vzc190b2tlbiA9ICdlbmNyeXB0ZWQtYWNjZXNzLXRva2VuJztcbiAgICAgIGNvbnN0IGVuY3J5cHRlZF9yZWZyZXNoX3Rva2VuID0gJ2VuY3J5cHRlZC1yZWZyZXNoLXRva2VuJztcbiAgICAgIGNvbnN0IHRva2VuX2V4cGlyeV90aW1lc3RhbXAgPSBuZXcgRGF0ZSgpLnRvSVNPU3RyaW5nKCk7XG4gICAgICBtb2NrZWRDcmVhdGVBZG1pbkdyYXBoUUxDbGllbnQubW9ja1JldHVyblZhbHVlKHtcbiAgICAgICAgcmVxdWVzdDogamVzdC5mbigpLm1vY2tSZXNvbHZlZFZhbHVlKHtcbiAgICAgICAgICB1c2VyX2NhbnZhX3Rva2VuczogW1xuICAgICAgICAgICAge1xuICAgICAgICAgICAgICBlbmNyeXB0ZWRfYWNjZXNzX3Rva2VuLFxuICAgICAgICAgICAgICBlbmNyeXB0ZWRfcmVmcmVzaF90b2tlbixcbiAgICAgICAgICAgICAgdG9rZW5fZXhwaXJ5X3RpbWVzdGFtcCxcbiAgICAgICAgICAgIH0sXG4gICAgICAgICAgXSxcbiAgICAgICAgfSksXG4gICAgICB9KTtcbiAgICAgIG1vY2tlZERlY3J5cHQubW9ja0ltcGxlbWVudGF0aW9uKCh0b2tlbiwga2V5KSA9PiB7XG4gICAgICAgIGlmICh0b2tlbiA9PT0gZW5jcnlwdGVkX2FjY2Vzc190b2tlbikgcmV0dXJuICdkZWNyeXB0ZWQtYWNjZXNzLXRva2VuJztcbiAgICAgICAgaWYgKHRva2VuID09PSBlbmNyeXB0ZWRfcmVmcmVzaF90b2tlbikgcmV0dXJuICdkZWNyeXB0ZWQtcmVmcmVzaC10b2tlbic7XG4gICAgICAgIHJldHVybiAnJztcbiAgICAgIH0pO1xuXG4gICAgICBjb25zdCB0b2tlbnMgPSBhd2FpdCBnZXRDYW52YVRva2Vucyh1c2VySWQpO1xuXG4gICAgICBleHBlY3QodG9rZW5zKS50b0VxdWFsKHtcbiAgICAgICAgYWNjZXNzVG9rZW46ICdkZWNyeXB0ZWQtYWNjZXNzLXRva2VuJyxcbiAgICAgICAgcmVmcmVzaFRva2VuOiAnZGVjcnlwdGVkLXJlZnJlc2gtdG9rZW4nLFxuICAgICAgICBleHBpcmVzQXQ6IHRva2VuX2V4cGlyeV90aW1lc3RhbXAsXG4gICAgICB9KTtcbiAgICAgIGV4cGVjdChtb2NrZWREZWNyeXB0KS50b0hhdmVCZWVuQ2FsbGVkV2l0aChcbiAgICAgICAgZW5jcnlwdGVkX2FjY2Vzc190b2tlbixcbiAgICAgICAgZW5jcnlwdGlvbktleVxuICAgICAgKTtcbiAgICAgIGV4cGVjdChtb2NrZWREZWNyeXB0KS50b0hhdmVCZWVuQ2FsbGVkV2l0aChcbiAgICAgICAgZW5jcnlwdGVkX3JlZnJlc2hfdG9rZW4sXG4gICAgICAgIGVuY3J5cHRpb25LZXlcbiAgICAgICk7XG4gICAgfSk7XG4gIH0pO1xuXG4gIGRlc2NyaWJlKCdyZWZyZXNoQWNjZXNzVG9rZW4nLCAoKSA9PiB7XG4gICAgaXQoJ3Nob3VsZCByZWZyZXNoIHRoZSBhY2Nlc3MgdG9rZW4gYW5kIHVwZGF0ZSB0aGUgZGF0YWJhc2UnLCBhc3luYyAoKSA9PiB7XG4gICAgICBjb25zdCByZWZyZXNoVG9rZW4gPSAndGVzdC1yZWZyZXNoLXRva2VuJztcbiAgICAgIGNvbnN0IG5ld0FjY2Vzc1Rva2VuID0gJ25ldy1hY2Nlc3MtdG9rZW4nO1xuICAgICAgY29uc3QgbmV3UmVmcmVzaFRva2VuID0gJ25ldy1yZWZyZXNoLXRva2VuJztcbiAgICAgIGNvbnN0IGV4cGlyZXNBdCA9IG5ldyBEYXRlKERhdGUubm93KCkgKyAzNjAwICogMTAwMCk7XG5cbiAgICAgIGNvbnN0IG1vY2tUb2tlbiA9IHtcbiAgICAgICAgcmVmcmVzaDogamVzdC5mbigpLm1vY2tSZXNvbHZlZFZhbHVlKHtcbiAgICAgICAgICB0b2tlbjoge1xuICAgICAgICAgICAgYWNjZXNzX3Rva2VuOiBuZXdBY2Nlc3NUb2tlbixcbiAgICAgICAgICAgIHJlZnJlc2hfdG9rZW46IG5ld1JlZnJlc2hUb2tlbixcbiAgICAgICAgICAgIGV4cGlyZXNfYXQ6IGV4cGlyZXNBdCxcbiAgICAgICAgICAgIHNjb3BlOiAnZGVzaWduOmNvbnRlbnQ6d3JpdGUgcHJvZmlsZTpyZWFkJyxcbiAgICAgICAgICB9LFxuICAgICAgICB9KSxcbiAgICAgIH07XG5cbiAgICAgIGNvbnN0IG1vY2tDcmVhdGVUb2tlbiA9IGplc3QuZm4oKS5tb2NrUmV0dXJuVmFsdWUobW9ja1Rva2VuKTtcbiAgICAgIG1vY2tlZEF1dGhvcml6YXRpb25Db2RlLm1vY2tJbXBsZW1lbnRhdGlvbigoKSA9PiAoe1xuICAgICAgICBjcmVhdGVUb2tlbjogbW9ja0NyZWF0ZVRva2VuLFxuICAgICAgfSkpO1xuXG4gICAgICBtb2NrZWRFbmNyeXB0Lm1vY2tJbXBsZW1lbnRhdGlvbigodG9rZW4sIGtleSkgPT4gYGVuY3J5cHRlZC0ke3Rva2VufWApO1xuXG4gICAgICBjb25zdCBtb2NrUmVxdWVzdCA9IGplc3QuZm4oKS5tb2NrUmVzb2x2ZWRWYWx1ZSh7fSk7XG4gICAgICBtb2NrZWRDcmVhdGVBZG1pbkdyYXBoUUxDbGllbnQubW9ja1JldHVyblZhbHVlKHtcbiAgICAgICAgcmVxdWVzdDogbW9ja1JlcXVlc3QsXG4gICAgICB9KTtcblxuICAgICAgY29uc3QgcmVzdWx0ID0gYXdhaXQgcmVmcmVzaEFjY2Vzc1Rva2VuKHVzZXJJZCwgcmVmcmVzaFRva2VuKTtcblxuICAgICAgZXhwZWN0KHJlc3VsdCkudG9CZShuZXdBY2Nlc3NUb2tlbik7XG4gICAgICBleHBlY3QobW9ja1JlcXVlc3QpLnRvSGF2ZUJlZW5DYWxsZWRXaXRoKGV4cGVjdC5hbnkoU3RyaW5nKSwge1xuICAgICAgICB1c2VySWQsXG4gICAgICAgIGFjY2Vzc1Rva2VuOiBgZW5jcnlwdGVkLSR7bmV3QWNjZXNzVG9rZW59YCxcbiAgICAgICAgcmVmcmVzaFRva2VuOiBgZW5jcnlwdGVkLSR7bmV3UmVmcmVzaFRva2VufWAsXG4gICAgICAgIGV4cGlyeVRpbWVzdGFtcDogZXhwaXJlc0F0LnRvSVNPU3RyaW5nKCksXG4gICAgICAgIHNjb3Blc0FycjogWydkZXNpZ246Y29udGVudDp3cml0ZScsICdwcm9maWxlOnJlYWQnXSxcbiAgICAgIH0pO1xuICAgIH0pO1xuICB9KTtcblxuICBkZXNjcmliZSgnY3JlYXRlRGVzaWduJywgKCkgPT4ge1xuICAgIGl0KCdzaG91bGQgY3JlYXRlIGEgZGVzaWduIHdpdGggYSB2YWxpZCBhY2Nlc3MgdG9rZW4nLCBhc3luYyAoKSA9PiB7XG4gICAgICBjb25zdCB0aXRsZSA9ICdUZXN0IERlc2lnbic7XG4gICAgICBjb25zdCBhY2Nlc3NUb2tlbiA9ICd2YWxpZC1hY2Nlc3MtdG9rZW4nO1xuICAgICAgY29uc3QgZGVzaWduRGF0YSA9IHtcbiAgICAgICAgaWQ6ICdkZXNpZ24taWQnLFxuICAgICAgICB0aXRsZSxcbiAgICAgICAgdXJsczogeyBlZGl0X3VybDogJ2VkaXQtdXJsJyB9LFxuICAgICAgfTtcblxuICAgICAgamVzdFxuICAgICAgICAuc3B5T24oZ2xvYmFsLCAnRGF0ZScpXG4gICAgICAgIC5tb2NrSW1wbGVtZW50YXRpb24oKCkgPT4gbmV3IERhdGUoJzIwMjUtMDEtMDFUMDA6MDA6MDAuMDAwWicpKTtcblxuICAgICAgY29uc3QgZ2V0Q2FudmFUb2tlbnNNb2NrID0gamVzdC5mbigpLm1vY2tSZXNvbHZlZFZhbHVlKHtcbiAgICAgICAgYWNjZXNzVG9rZW4sXG4gICAgICAgIHJlZnJlc2hUb2tlbjogJ3JlZnJlc2gtdG9rZW4nLFxuICAgICAgICBleHBpcmVzQXQ6IG5ldyBEYXRlKCcyMDI1LTAxLTAyVDAwOjAwOjAwLjAwMFonKS50b0lTT1N0cmluZygpLFxuICAgICAgfSk7XG5cbiAgICAgIGNvbnN0IGNhbnZhU2tpbGxzID0gcmVxdWlyZSgnLi9jYW52YVNraWxscycpO1xuICAgICAgY2FudmFTa2lsbHMuZ2V0Q2FudmFUb2tlbnMgPSBnZXRDYW52YVRva2Vuc01vY2s7XG5cbiAgICAgIG1vY2tlZEF4aW9zLnBvc3QubW9ja1Jlc29sdmVkVmFsdWUoeyBkYXRhOiBkZXNpZ25EYXRhIH0pO1xuXG4gICAgICBjb25zdCByZXN1bHQgPSBhd2FpdCBjcmVhdGVEZXNpZ24odXNlcklkLCB0aXRsZSk7XG5cbiAgICAgIGV4cGVjdChyZXN1bHQpLnRvRXF1YWwoZGVzaWduRGF0YSk7XG4gICAgICBleHBlY3QobW9ja2VkQXhpb3MucG9zdCkudG9IYXZlQmVlbkNhbGxlZFdpdGgoXG4gICAgICAgICdodHRwczovL2FwaS5jYW52YS5jb20vcmVzdC92MS9kZXNpZ25zJyxcbiAgICAgICAgeyB0aXRsZSwgZGVzaWduX3R5cGU6IHsgdHlwZTogJ3ByZXNldCcsIG5hbWU6ICdwcmVzZW50YXRpb24nIH0gfSxcbiAgICAgICAge1xuICAgICAgICAgIGhlYWRlcnM6IHtcbiAgICAgICAgICAgIEF1dGhvcml6YXRpb246IGBCZWFyZXIgJHthY2Nlc3NUb2tlbn1gLFxuICAgICAgICAgICAgJ0NvbnRlbnQtVHlwZSc6ICdhcHBsaWNhdGlvbi9qc29uJyxcbiAgICAgICAgICB9LFxuICAgICAgICB9XG4gICAgICApO1xuICAgIH0pO1xuICB9KTtcbn0pO1xuIl19