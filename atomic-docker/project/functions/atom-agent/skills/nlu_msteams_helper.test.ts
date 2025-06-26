import { buildMSTeamsSearchQuery } from './nlu_msteams_helper';
import { StructuredMSTeamsQuery } from './llm_msteams_query_understander';

describe('buildMSTeamsSearchQuery', () => {
  it('should build a KQL query with textKeywords and fromUser', () => {
    const params: StructuredMSTeamsQuery = {
      textKeywords: 'project update',
      fromUser: 'john.doe@example.com',
    };
    // Order of terms joined by AND might vary, so check for components.
    const result = buildMSTeamsSearchQuery(params);
    expect(result).toContain('project update');
    expect(result).toContain('from:john.doe@example.com');
    expect(result.split(' AND ').length).toBe(2);
  });

  it('should build a KQL query with subjectContains and onDate', () => {
    const params: StructuredMSTeamsQuery = {
      subjectContains: 'Weekly Sync',
      onDate: '2024-03-10',
    };
    const result = buildMSTeamsSearchQuery(params);
    expect(result).toContain('subject:Weekly Sync');
    expect(result).toContain('created:2024-03-10');
    expect(result.split(' AND ').length).toBe(2);
  });

  it('should build a KQL query with exactPhrase and hasFile', () => {
    const params: StructuredMSTeamsQuery = {
      exactPhrase: 'must review this document',
      hasFile: true,
    };
    const result = buildMSTeamsSearchQuery(params);
    expect(result).toContain('"must review this document"');
    expect(result).toContain('hasattachment:true');
    expect(result.split(' AND ').length).toBe(2);
  });

  it('should build a KQL query with date range (afterDate and beforeDate)', () => {
    const params: StructuredMSTeamsQuery = {
      afterDate: '2024-01-01',
      beforeDate: '2024-01-31',
      textKeywords: 'planning session',
    };
    const result = buildMSTeamsSearchQuery(params);
    expect(result).toContain('created:2024-01-01..2024-01-31');
    expect(result).toContain('planning session');
  });

  it('should handle only afterDate', () => {
    const params: StructuredMSTeamsQuery = { afterDate: '2024-02-15' };
    expect(buildMSTeamsSearchQuery(params)).toBe('created>=2024-02-15');
  });

  it('should handle only beforeDate', () => {
    const params: StructuredMSTeamsQuery = { beforeDate: '2024-02-20' };
    expect(buildMSTeamsSearchQuery(params)).toBe('created<=2024-02-20');
  });

  it('should include mentionsUser and inChatOrChannel as text keywords', () => {
    const params: StructuredMSTeamsQuery = {
      mentionsUser: 'Sarah Connor',
      inChatOrChannel: 'Project Terminator Chat',
    };
    const result = buildMSTeamsSearchQuery(params);
    expect(result).toContain('"Sarah Connor"');
    expect(result).toContain('"Project Terminator Chat"');
  });

  it('should handle hasLink by adding (http OR https)', () => {
    const params: StructuredMSTeamsQuery = {
      hasLink: true,
    };
    expect(buildMSTeamsSearchQuery(params)).toBe('(http OR https)');
  });

  it('should combine multiple parameters with AND', () => {
    const params: StructuredMSTeamsQuery = {
      fromUser: 'test@example.com',
      textKeywords: 'urgent task',
      subjectContains: 'Action Required',
      onDate: '2023-01-15',
      hasFile: true,
    };
    const result = buildMSTeamsSearchQuery(params);
    expect(result).toContain('urgent task');
    expect(result).toContain('from:test@example.com');
    expect(result).toContain('subject:Action Required');
    expect(result).toContain('created:2023-01-15');
    expect(result).toContain('hasattachment:true');
    // Check that terms are ANDed together
    const parts = result.split(' AND ');
    expect(parts.length).toBe(5); // 5 terms should be ANDed
  });

  it('should return an empty string for an empty params object', () => {
    const params: StructuredMSTeamsQuery = {};
    expect(buildMSTeamsSearchQuery(params)).toBe('');
  });

  it('should trim whitespace from parameters', () => {
    const params: StructuredMSTeamsQuery = {
      textKeywords: '  leading and trailing spaces  ',
      fromUser: '  user@example.com  ',
    };
    const result = buildMSTeamsSearchQuery(params);
    expect(result).toContain('leading and trailing spaces');
    expect(result).toContain('from:user@example.com');
  });
});
