import { processGuidanceRequest } from './guidance_orchestrator';

describe('GuidanceOrchestrator', () => {
  it('should be able to process a simple query', async () => {
    const response = await processGuidanceRequest(
      'How do I create a pivot table in SpreadsheetApp?',
      'user123',
      'SpreadsheetApp'
    );
    expect(response.messageToUser).toContain("Here's what I found");
  });
});
