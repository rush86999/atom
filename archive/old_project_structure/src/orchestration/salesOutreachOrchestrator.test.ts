import { runSalesOutreach } from './salesOutreachOrchestrator';
import * as hubspotSkills from '../../atomic-docker/project/functions/atom-agent/skills/hubspotSkills';
import * as emailSkills from '../../atomic-docker/project/functions/atom-agent/skills/emailSkills';
import { ContentCreationAgent } from '../skills/contentCreationSkill';
import { HubSpotContact } from '../../atomic-docker/project/functions/atom-agent/types';

// Mock the dependencies
jest.mock('../../atomic-docker/project/functions/atom-agent/skills/hubspotSkills');
jest.mock('../../atomic-docker/project/functions/atom-agent/skills/emailSkills');
jest.mock('../skills/contentCreationSkill');

const mockedHubspotSkills = hubspotSkills as jest.Mocked<typeof hubspotSkills>;
const mockedEmailSkills = emailSkills as jest.mocked<typeof emailSkills>;
const mockedContentCreationAgent = ContentCreationAgent as jest.MockedClass<typeof ContentCreationAgent>;

describe('runSalesOutreach', () => {
  const userId = 'test-user';

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('should run successfully and create drafts for new contacts', async () => {
    const mockContacts: HubSpotContact[] = [
      { id: '1', properties: { firstname: 'John', company: 'Doe Inc.', email: 'john.doe@example.com' } } as any,
      { id: '2', properties: { firstname: 'Jane', company: 'Smith LLC', email: 'jane.smith@example.com' } } as any,
    ];

    mockedHubspotSkills.getNewHubSpotContacts.mockResolvedValue({ ok: true, data: mockContacts });
    mockedContentCreationAgent.prototype.analyze.mockResolvedValue({ generatedContent: 'Generated email body', contentType: 'email' } as any);
    mockedEmailSkills.createGmailDraft.mockResolvedValue({ success: true, emailId: 'draft-123', message: 'Draft created' });

    const result = await runSalesOutreach(userId);

    expect(result.success).toBe(true);
    expect(result.contactsProcessed).toBe(2);
    expect(result.draftsCreated).toBe(2);
    expect(result.errors.length).toBe(0);
    expect(mockedHubspotSkills.getNewHubSpotContacts).toHaveBeenCalledTimes(1);
    expect(mockedContentCreationAgent.prototype.analyze).toHaveBeenCalledTimes(2);
    expect(mockedEmailSkills.createGmailDraft).toHaveBeenCalledTimes(2);
  });

  it('should handle the case where there are no new contacts', async () => {
    mockedHubspotSkills.getNewHubSpotContacts.mockResolvedValue({ ok: true, data: [] });

    const result = await runSalesOutreach(userId);

    expect(result.success).toBe(true);
    expect(result.message).toContain('No new contacts found');
    expect(result.contactsProcessed).toBe(0);
    expect(result.draftsCreated).toBe(0);
    expect(mockedContentCreationAgent.prototype.analyze).not.toHaveBeenCalled();
    expect(mockedEmailSkills.createGmailDraft).not.toHaveBeenCalled();
  });

  it('should handle errors from the HubSpot API', async () => {
    mockedHubspotSkills.getNewHubSpotContacts.mockResolvedValue({ ok: false, error: { message: 'HubSpot API error' } } as any);

    const result = await runSalesOutreach(userId);

    expect(result.success).toBe(false);
    expect(result.message).toContain('Failed to retrieve new HubSpot contacts');
  });

  it('should handle errors from the content creation agent', async () => {
    const mockContacts: HubSpotContact[] = [
      { id: '1', properties: { firstname: 'John', company: 'Doe Inc.', email: 'john.doe@example.com' } } as any,
    ];
    mockedHubspotSkills.getNewHubSpotContacts.mockResolvedValue({ ok: true, data: mockContacts });
    mockedContentCreationAgent.prototype.analyze.mockResolvedValue({ generatedContent: null } as any);

    const result = await runSalesOutreach(userId);

    expect(result.success).toBe(false);
    expect(result.errors.length).toBe(1);
    expect(result.errors[0]).toContain('Failed to generate email content');
    expect(result.draftsCreated).toBe(0);
  });

  it('should handle errors from Gmail draft creation', async () => {
    const mockContacts: HubSpotContact[] = [
      { id: '1', properties: { firstname: 'John', company: 'Doe Inc.', email: 'john.doe@example.com' } } as any,
    ];
    mockedHubspotSkills.getNewHubSpotContacts.mockResolvedValue({ ok: true, data: mockContacts });
    mockedContentCreationAgent.prototype.analyze.mockResolvedValue({ generatedContent: 'Generated email body' } as any);
    mockedEmailSkills.createGmailDraft.mockResolvedValue({ success: false, message: 'Gmail API error' });

    const result = await runSalesOutreach(userId);

    expect(result.success).toBe(false);
    expect(result.errors.length).toBe(1);
    expect(result.errors[0]).toContain('Failed to create draft');
    expect(result.draftsCreated).toBe(0);
  });

  it('should skip contacts with no email address', async () => {
    const mockContacts: HubSpotContact[] = [
      { id: '1', properties: { firstname: 'John', company: 'Doe Inc.', email: null } } as any,
    ];
    mockedHubspotSkills.getNewHubSpotContacts.mockResolvedValue({ ok: true, data: mockContacts });

    const result = await runSalesOutreach(userId);

    expect(result.success).toBe(false); // success is false because there was an error/warning
    expect(result.errors.length).toBe(1);
    expect(result.errors[0]).toContain('Skipping contact ID 1 due to missing email address');
    expect(result.contactsProcessed).toBe(1);
    expect(result.draftsCreated).toBe(0);
    expect(mockedContentCreationAgent.prototype.analyze).not.toHaveBeenCalled();
  });
});
