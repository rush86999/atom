import { postToTwitter } from './socialMediaSkills';
import { Client } from 'twitter-api-sdk';
import * as authService from '../services/authService';

jest.mock('twitter-api-sdk');
jest.mock('../services/authService');

const mockTwitterClient = Client as jest.MockedClass<typeof Client>;
const mockAuthService = authService as jest.Mocked<typeof authService>;

describe('socialMediaSkills', () => {
  afterEach(() => {
    jest.clearAllMocks();
  });

  describe('postToTwitter', () => {
    it('should post to Twitter successfully', async () => {
      mockAuthService.getTwitterCredentials.mockResolvedValue({
        bearerToken: 'test-token',
      });
      const mockCreateTweet = jest.fn().mockResolvedValue({});
      mockTwitterClient.prototype.tweets = {
        createTweet: mockCreateTweet,
      } as any;

      const result = await postToTwitter('user-123', 'Hello, Twitter!');

      expect(result.ok).toBe(true);
      expect(mockCreateTweet).toHaveBeenCalledWith({ text: 'Hello, Twitter!' });
    });

    it('should return an error if credentials are not found', async () => {
      mockAuthService.getTwitterCredentials.mockResolvedValue(null);

      const result = await postToTwitter('user-123', 'Hello, Twitter!');

      expect(result.ok).toBe(false);
      if (!result.ok) {
        expect(result.error.code).toBe('UNAUTHORIZED');
      }
    });

    it('should return an error if the Twitter API call fails', async () => {
      mockAuthService.getTwitterCredentials.mockResolvedValue({
        bearerToken: 'test-token',
      });
      const mockCreateTweet = jest
        .fn()
        .mockRejectedValue(new Error('Twitter API Error'));
      mockTwitterClient.prototype.tweets = {
        createTweet: mockCreateTweet,
      } as any;

      const result = await postToTwitter('user-123', 'Hello, Twitter!');

      expect(result.ok).toBe(false);
      if (!result.ok) {
        expect(result.error.code).toBe('TWITTER_API_ERROR');
        expect(result.error.message).toBe('Twitter API Error');
      }
    });
  });
});
