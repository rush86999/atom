import * as zapierSkills from './zapierSkills';
import { ZapTriggerResponse } from '../types'; // Assuming ZapData is defined within zapierSkills or not explicitly typed for response

describe('Zapier Skills', () => {
  describe('triggerZap', () => {
    it('should return a success response with zapName and runId for a valid trigger', async () => {
      const zapName = 'TestZap';
      const data: zapierSkills.ZapData = { testKey: 'testValue' };

      const response = await zapierSkills.triggerZap(zapName, data);

      expect(response.success).toBe(true);
      expect(response.zapName).toBe(zapName);
      expect(response.runId).toBeDefined();
      expect(typeof response.runId).toBe('string');
      expect(response.message).toContain(`Zap "${zapName}" triggered successfully (mock).`);
    });

    it('should handle triggering a Zap with empty data', async () => {
      const zapName = 'ZapWithNoData';
      const data: zapierSkills.ZapData = {};

      const response = await zapierSkills.triggerZap(zapName, data);

      expect(response.success).toBe(true);
      expect(response.zapName).toBe(zapName);
      expect(response.runId).toBeDefined();
      expect(response.message).toContain(`Zap "${zapName}" triggered successfully (mock).`);
    });

    it('should return a failure response if zapName is missing', async () => {
      // Test with zapName as empty string, null, or undefined as per JS/TS practices
      // The skill currently checks for !zapName, which covers empty string.
      const data: zapierSkills.ZapData = { key: 'value' };

      const response = await zapierSkills.triggerZap('', data); // Empty string for zapName

      expect(response.success).toBe(false);
      expect(response.message).toBe('Zap name is required.');
      expect(response.runId).toBeUndefined();
      expect(response.zapName).toBeUndefined(); // Or it might be the empty string depending on implementation
    });

    // Example of console log spying if needed, though less critical for mock functions
    it('should log the zapName and data', async () => {
        const consoleSpy = jest.spyOn(console, 'log');
        const zapName = 'LoggingTestZap';
        const data = { item: 'logging item' };

        await zapierSkills.triggerZap(zapName, data);

        expect(consoleSpy).toHaveBeenCalledWith(`Triggering Zap: "${zapName}" with data:`, data);
        expect(consoleSpy).toHaveBeenCalledWith(expect.stringContaining(`Mock Zap "${zapName}" triggered successfully. Run ID:`));

        consoleSpy.mockRestore(); // Clean up spy
      });
  });
});
