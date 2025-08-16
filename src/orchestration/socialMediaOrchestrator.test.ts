import { postTweet } from './socialMediaOrchestrator';
import * as socialMediaSkills from '../skills/socialMediaSkills';

jest.mock('../skills/socialMediaSkills');

const mockSocialMediaSkills = socialMediaSkills as jest.Mocked<
  typeof socialMediaSkills
>;

describe('socialMediaOrchestrator', () => {
  afterEach(() => {
    jest.clearAllMocks();
  });

  describe('postTweet', () => {
    it('should call postToTwitter and return the result', async () => {
      const mockSuccessResponse = { ok: true, data: { success: true } };
      mockSocialMediaSkills.postToTwitter.mockResolvedValue(
        mockSuccessResponse as any
      );

      const result = await postTweet('user-123', 'Test tweet');

      expect(result).toEqual(mockSuccessResponse);
      expect(mockSocialMediaSkills.postToTwitter).toHaveBeenCalledWith(
        'user-123',
        'Test tweet'
      );
    });

    it('should handle errors from postToTwitter', async () => {
      const mockErrorResponse = {
        ok: false,
        error: { code: 'TWITTER_API_ERROR', message: 'Failed to post' },
      };
      mockSocialMediaSkills.postToTwitter.mockResolvedValue(
        mockErrorResponse as any
      );

      const result = await postTweet('user-123', 'Test tweet');

      expect(result).toEqual(mockErrorResponse);
      expect(mockSocialMediaSkills.postToTwitter).toHaveBeenCalledWith(
        'user-123',
        'Test tweet'
      );
    });
  });
});
