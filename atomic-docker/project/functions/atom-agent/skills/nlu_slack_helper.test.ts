import { buildSlackSearchQuery } from './nlu_slack_helper';
import { StructuredSlackQuery } from './llm_slack_query_understander';

describe('buildSlackSearchQuery', () => {
  it('should build a query with fromUser and textKeywords', () => {
    const params: StructuredSlackQuery = {
      fromUser: '@bob',
      textKeywords: 'Q1 report',
    };
    const expectedQuery = 'from:@bob Q1 report';
    expect(buildSlackSearchQuery(params)).toBe(expectedQuery);
  });

  it('should build a query with inChannel and onDate', () => {
    const params: StructuredSlackQuery = {
      inChannel: '#marketing',
      onDate: '2023-10-26',
    };
    const expectedQuery = 'in:#marketing on:2023-10-26';
    expect(buildSlackSearchQuery(params)).toBe(expectedQuery);
  });

  it('should build a query with exactPhrase and hasFile', () => {
    const params: StructuredSlackQuery = {
      exactPhrase: 'project deadline extension',
      hasFile: true,
    };
    const expectedQuery = '"project deadline extension" has:file';
    expect(buildSlackSearchQuery(params)).toBe(expectedQuery);
  });

  it('should build a query with afterDate and beforeDate', () => {
    const params: StructuredSlackQuery = {
      afterDate: '2023-09-01',
      beforeDate: '2023-09-30',
    };
    const expectedQuery = 'after:2023-09-01 before:2023-09-30';
    expect(buildSlackSearchQuery(params)).toBe(expectedQuery);
  });

  it('should handle mentionsUser and hasReaction', () => {
    const params: StructuredSlackQuery = {
      mentionsUser: 'Claire',
      hasReaction: ':eyes:',
    };
    const expectedQuery = 'mentions:Claire has::eyes:';
    expect(buildSlackSearchQuery(params)).toBe(expectedQuery);
  });

  it('should handle hasLink', () => {
    const params: StructuredSlackQuery = {
      hasLink: true,
      inChannel: 'C012ABCDEF',
    };
    const expectedQuery = 'in:C012ABCDEF has:link';
    expect(buildSlackSearchQuery(params)).toBe(expectedQuery);
  });

  it('should combine multiple parameters correctly', () => {
    const params: StructuredSlackQuery = {
      fromUser: 'david',
      inChannel: '#general',
      textKeywords: 'important update client meeting',
      afterDate: '2024-01-01',
      hasFile: true,
    };
    // Order might vary for textKeywords if not handled specifically, but all parts should be present.
    // For predictability in tests, ensure a consistent order or use a matcher that ignores order of space-separated terms.
    // Current implementation joins in a specific order.
    const expectedQuery =
      'from:david in:#general has:file after:2024-01-01 important update client meeting';
    expect(buildSlackSearchQuery(params)).toEqual(
      expect.stringContaining('from:david')
    );
    expect(buildSlackSearchQuery(params)).toEqual(
      expect.stringContaining('in:#general')
    );
    expect(buildSlackSearchQuery(params)).toEqual(
      expect.stringContaining('has:file')
    );
    expect(buildSlackSearchQuery(params)).toEqual(
      expect.stringContaining('after:2024-01-01')
    );
    expect(buildSlackSearchQuery(params)).toEqual(
      expect.stringContaining('important update client meeting')
    );
  });

  it('should return an empty string for empty params', () => {
    const params: StructuredSlackQuery = {};
    const expectedQuery = '';
    expect(buildSlackSearchQuery(params)).toBe(expectedQuery);
  });

  it('should trim whitespace from parameters', () => {
    const params: StructuredSlackQuery = {
      fromUser: '  @bob  ',
      textKeywords: '  Q1 report  ',
    };
    const expectedQuery = 'from:@bob Q1 report';
    expect(buildSlackSearchQuery(params)).toBe(expectedQuery);
  });

  it('should correctly format hasReaction by removing colons if present', () => {
    const params1: StructuredSlackQuery = { hasReaction: ':smile:' };
    expect(buildSlackSearchQuery(params1)).toBe('has::smile:');

    const params2: StructuredSlackQuery = { hasReaction: 'tada' };
    expect(buildSlackSearchQuery(params2)).toBe('has::tada:');
  });

  it('should not include onDate if afterDate or beforeDate is present', () => {
    const params: StructuredSlackQuery = {
      onDate: '2023-10-26',
      afterDate: '2023-10-25',
    };
    const expectedQuery = 'after:2023-10-25'; // onDate should be ignored
    expect(buildSlackSearchQuery(params)).toBe(expectedQuery);

    const params2: StructuredSlackQuery = {
      onDate: '2023-10-26',
      beforeDate: '2023-10-27',
    };
    const expectedQuery2 = 'before:2023-10-27'; // onDate should be ignored
    expect(buildSlackSearchQuery(params2)).toBe(expectedQuery2);

    const params3: StructuredSlackQuery = {
      onDate: '2023-10-26',
      afterDate: '2023-10-25',
      beforeDate: '2023-10-27',
    };
    const expectedQuery3 = 'after:2023-10-25 before:2023-10-27'; // onDate should be ignored
    expect(buildSlackSearchQuery(params3)).toBe(expectedQuery3);
  });
});
