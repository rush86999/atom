import { handleTriggerZap } from '../zapier';
import * as zapierSkills from '../zapierSkills';

jest.mock('../zapierSkills', () => ({
  triggerZap: jest.fn(),
}));

describe('zapier skill', () => {
  afterEach(() => {
    jest.clearAllMocks();
  });

  describe('handleTriggerZap', () => {
    it('should trigger a Zap', async () => {
      (zapierSkills.triggerZap as jest.Mock).mockResolvedValue({
        success: true,
        message: 'Zap triggered successfully',
        runId: 'test-run-id',
      });

      const result = await handleTriggerZap({ zap_name: 'test-zap' });

      expect(result).toContain(
        'Zap triggered via NLU: Zap triggered successfully'
      );
    });

    it('should return an error message when the zap name is missing', async () => {
      const result = await handleTriggerZap({});

      expect(result).toBe('Zap name is required to trigger a Zap via NLU.');
    });

    it('should return an error message when an error occurs', async () => {
      (zapierSkills.triggerZap as jest.Mock).mockRejectedValue(
        new Error('Test Error')
      );

      const result = await handleTriggerZap({ zap_name: 'test-zap' });

      expect(result).toBe(
        "Sorry, I couldn't trigger the Zap due to an error (NLU path)."
      );
    });
  });
});
