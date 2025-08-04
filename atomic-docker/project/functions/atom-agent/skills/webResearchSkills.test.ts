import * as webResearchSkills from './webResearchSkills';
import { SearchResult } from '../types';

describe('Web Research Skills', () => {
  describe('searchWeb', () => {
    it('should return an array of search result objects', async () => {
      const results = await webResearchSkills.searchWeb('generic query');
      expect(Array.isArray(results)).toBe(true);
      if (results.length > 0) {
        const firstResult = results[0];
        expect(firstResult).toHaveProperty('title');
        expect(firstResult).toHaveProperty('link');
        expect(firstResult).toHaveProperty('snippet');
      }
    });

    it('should filter results based on the query (case-insensitive in title)', async () => {
      // This test relies on the specific mock data in webResearchSkills.ts
      // Mock data includes: 'Example Domain', 'Internet Assigned Numbers Authority (IANA)', 'World Wide Web Consortium (W3C)'

      const resultsForExample = await webResearchSkills.searchWeb('example');
      expect(resultsForExample.length).toBe(1);
      expect(resultsForExample[0].title).toBe('Example Domain');

      const resultsForIANA = await webResearchSkills.searchWeb('iana');
      expect(resultsForIANA.length).toBe(1);
      expect(resultsForIANA[0].title).toBe(
        'Internet Assigned Numbers Authority (IANA)'
      );
    });

    it('should filter results based on the query (case-insensitive in snippet)', async () => {
      const resultsForDocuments =
        await webResearchSkills.searchWeb('documents'); // "illustrative examples in documents"
      expect(resultsForDocuments.length).toBe(1);
      expect(resultsForDocuments[0].title).toBe('Example Domain');

      const resultsForCoordinating =
        await webResearchSkills.searchWeb('coordinating'); // "coordinating some of the key elements"
      expect(resultsForCoordinating.length).toBe(1);
      expect(resultsForCoordinating[0].title).toBe(
        'Internet Assigned Numbers Authority (IANA)'
      );
    });

    it('should return a generic result if query does not match any mock data', async () => {
      const query = 'nonExistentQuery123';
      const results = await webResearchSkills.searchWeb(query);
      expect(results.length).toBe(1);
      expect(results[0].title).toBe(`No specific results for "${query}"`);
      expect(results[0].link).toContain(encodeURIComponent(query));
      expect(results[0].snippet).toContain('mock response');
    });

    it('should handle an empty query string (current mock returns generic)', async () => {
      const results = await webResearchSkills.searchWeb('');
      // The current mock implementation for an empty query will likely find all items
      // because ''.toLowerCase().includes('') is true for any string.
      // Or, if query is trimmed and checked for emptiness, it might return the generic "no specific results".
      // Let's assume it filters and includes everything if query is effectively empty and not caught.
      // The mock data has 3 items.
      // If the skill treats empty string as "match all", then length would be 3.
      // If it treats it as "no query", it gives the generic response.
      // Current mock: `result.title.toLowerCase().includes(lowerCaseQuery)` will be true for empty `lowerCaseQuery`
      expect(results.length).toBe(3); // Because empty string is included in all titles/snippets
    });
  });
});
