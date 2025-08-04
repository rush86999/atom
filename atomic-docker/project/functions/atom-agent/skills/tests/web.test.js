import { handleSearchWeb } from '../web';
import * as webResearchSkills from '../webResearchSkills';
jest.mock('../webResearchSkills', () => ({
    searchWeb: jest.fn(),
}));
describe('web skill', () => {
    afterEach(() => {
        jest.clearAllMocks();
    });
    describe('handleSearchWeb', () => {
        it('should return a list of web search results', async () => {
            const mockResults = [
                {
                    title: 'Test Result 1',
                    link: 'https://example.com/1',
                    snippet: 'This is a test result.',
                },
                {
                    title: 'Test Result 2',
                    link: 'https://example.com/2',
                    snippet: 'This is another test result.',
                },
            ];
            webResearchSkills.searchWeb.mockResolvedValue(mockResults);
            const result = await handleSearchWeb({ query: 'test' });
            expect(result).toContain('Web search results for "test" (via NLU):');
            expect(result).toContain('Test Result 1');
            expect(result).toContain('Test Result 2');
        });
        it('should return a message when there are no web search results', async () => {
            webResearchSkills.searchWeb.mockResolvedValue([]);
            const result = await handleSearchWeb({ query: 'test' });
            expect(result).toBe('No web results found for "test" (via NLU).');
        });
        it('should return an error message when the query is missing', async () => {
            const result = await handleSearchWeb({});
            expect(result).toBe('A search query is required to search the web via NLU.');
        });
        it('should return an error message when an error occurs', async () => {
            webResearchSkills.searchWeb.mockRejectedValue(new Error('Test Error'));
            const result = await handleSearchWeb({ query: 'test' });
            expect(result).toBe("Sorry, I couldn't perform the web search due to an error (NLU path).");
        });
    });
});
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoid2ViLnRlc3QuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJ3ZWIudGVzdC50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiQUFBQSxPQUFPLEVBQUUsZUFBZSxFQUFFLE1BQU0sUUFBUSxDQUFDO0FBQ3pDLE9BQU8sS0FBSyxpQkFBaUIsTUFBTSxzQkFBc0IsQ0FBQztBQUUxRCxJQUFJLENBQUMsSUFBSSxDQUFDLHNCQUFzQixFQUFFLEdBQUcsRUFBRSxDQUFDLENBQUM7SUFDdkMsU0FBUyxFQUFFLElBQUksQ0FBQyxFQUFFLEVBQUU7Q0FDckIsQ0FBQyxDQUFDLENBQUM7QUFFSixRQUFRLENBQUMsV0FBVyxFQUFFLEdBQUcsRUFBRTtJQUN6QixTQUFTLENBQUMsR0FBRyxFQUFFO1FBQ2IsSUFBSSxDQUFDLGFBQWEsRUFBRSxDQUFDO0lBQ3ZCLENBQUMsQ0FBQyxDQUFDO0lBRUgsUUFBUSxDQUFDLGlCQUFpQixFQUFFLEdBQUcsRUFBRTtRQUMvQixFQUFFLENBQUMsNENBQTRDLEVBQUUsS0FBSyxJQUFJLEVBQUU7WUFDMUQsTUFBTSxXQUFXLEdBQUc7Z0JBQ2xCO29CQUNFLEtBQUssRUFBRSxlQUFlO29CQUN0QixJQUFJLEVBQUUsdUJBQXVCO29CQUM3QixPQUFPLEVBQUUsd0JBQXdCO2lCQUNsQztnQkFDRDtvQkFDRSxLQUFLLEVBQUUsZUFBZTtvQkFDdEIsSUFBSSxFQUFFLHVCQUF1QjtvQkFDN0IsT0FBTyxFQUFFLDhCQUE4QjtpQkFDeEM7YUFDRixDQUFDO1lBQ0QsaUJBQWlCLENBQUMsU0FBdUIsQ0FBQyxpQkFBaUIsQ0FBQyxXQUFXLENBQUMsQ0FBQztZQUUxRSxNQUFNLE1BQU0sR0FBRyxNQUFNLGVBQWUsQ0FBQyxFQUFFLEtBQUssRUFBRSxNQUFNLEVBQUUsQ0FBQyxDQUFDO1lBRXhELE1BQU0sQ0FBQyxNQUFNLENBQUMsQ0FBQyxTQUFTLENBQUMsMENBQTBDLENBQUMsQ0FBQztZQUNyRSxNQUFNLENBQUMsTUFBTSxDQUFDLENBQUMsU0FBUyxDQUFDLGVBQWUsQ0FBQyxDQUFDO1lBQzFDLE1BQU0sQ0FBQyxNQUFNLENBQUMsQ0FBQyxTQUFTLENBQUMsZUFBZSxDQUFDLENBQUM7UUFDNUMsQ0FBQyxDQUFDLENBQUM7UUFFSCxFQUFFLENBQUMsOERBQThELEVBQUUsS0FBSyxJQUFJLEVBQUU7WUFDM0UsaUJBQWlCLENBQUMsU0FBdUIsQ0FBQyxpQkFBaUIsQ0FBQyxFQUFFLENBQUMsQ0FBQztZQUVqRSxNQUFNLE1BQU0sR0FBRyxNQUFNLGVBQWUsQ0FBQyxFQUFFLEtBQUssRUFBRSxNQUFNLEVBQUUsQ0FBQyxDQUFDO1lBRXhELE1BQU0sQ0FBQyxNQUFNLENBQUMsQ0FBQyxJQUFJLENBQUMsNENBQTRDLENBQUMsQ0FBQztRQUNwRSxDQUFDLENBQUMsQ0FBQztRQUVILEVBQUUsQ0FBQywwREFBMEQsRUFBRSxLQUFLLElBQUksRUFBRTtZQUN4RSxNQUFNLE1BQU0sR0FBRyxNQUFNLGVBQWUsQ0FBQyxFQUFFLENBQUMsQ0FBQztZQUV6QyxNQUFNLENBQUMsTUFBTSxDQUFDLENBQUMsSUFBSSxDQUNqQix1REFBdUQsQ0FDeEQsQ0FBQztRQUNKLENBQUMsQ0FBQyxDQUFDO1FBRUgsRUFBRSxDQUFDLHFEQUFxRCxFQUFFLEtBQUssSUFBSSxFQUFFO1lBQ2xFLGlCQUFpQixDQUFDLFNBQXVCLENBQUMsaUJBQWlCLENBQzFELElBQUksS0FBSyxDQUFDLFlBQVksQ0FBQyxDQUN4QixDQUFDO1lBRUYsTUFBTSxNQUFNLEdBQUcsTUFBTSxlQUFlLENBQUMsRUFBRSxLQUFLLEVBQUUsTUFBTSxFQUFFLENBQUMsQ0FBQztZQUV4RCxNQUFNLENBQUMsTUFBTSxDQUFDLENBQUMsSUFBSSxDQUNqQixzRUFBc0UsQ0FDdkUsQ0FBQztRQUNKLENBQUMsQ0FBQyxDQUFDO0lBQ0wsQ0FBQyxDQUFDLENBQUM7QUFDTCxDQUFDLENBQUMsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7IGhhbmRsZVNlYXJjaFdlYiB9IGZyb20gJy4uL3dlYic7XG5pbXBvcnQgKiBhcyB3ZWJSZXNlYXJjaFNraWxscyBmcm9tICcuLi93ZWJSZXNlYXJjaFNraWxscyc7XG5cbmplc3QubW9jaygnLi4vd2ViUmVzZWFyY2hTa2lsbHMnLCAoKSA9PiAoe1xuICBzZWFyY2hXZWI6IGplc3QuZm4oKSxcbn0pKTtcblxuZGVzY3JpYmUoJ3dlYiBza2lsbCcsICgpID0+IHtcbiAgYWZ0ZXJFYWNoKCgpID0+IHtcbiAgICBqZXN0LmNsZWFyQWxsTW9ja3MoKTtcbiAgfSk7XG5cbiAgZGVzY3JpYmUoJ2hhbmRsZVNlYXJjaFdlYicsICgpID0+IHtcbiAgICBpdCgnc2hvdWxkIHJldHVybiBhIGxpc3Qgb2Ygd2ViIHNlYXJjaCByZXN1bHRzJywgYXN5bmMgKCkgPT4ge1xuICAgICAgY29uc3QgbW9ja1Jlc3VsdHMgPSBbXG4gICAgICAgIHtcbiAgICAgICAgICB0aXRsZTogJ1Rlc3QgUmVzdWx0IDEnLFxuICAgICAgICAgIGxpbms6ICdodHRwczovL2V4YW1wbGUuY29tLzEnLFxuICAgICAgICAgIHNuaXBwZXQ6ICdUaGlzIGlzIGEgdGVzdCByZXN1bHQuJyxcbiAgICAgICAgfSxcbiAgICAgICAge1xuICAgICAgICAgIHRpdGxlOiAnVGVzdCBSZXN1bHQgMicsXG4gICAgICAgICAgbGluazogJ2h0dHBzOi8vZXhhbXBsZS5jb20vMicsXG4gICAgICAgICAgc25pcHBldDogJ1RoaXMgaXMgYW5vdGhlciB0ZXN0IHJlc3VsdC4nLFxuICAgICAgICB9LFxuICAgICAgXTtcbiAgICAgICh3ZWJSZXNlYXJjaFNraWxscy5zZWFyY2hXZWIgYXMgamVzdC5Nb2NrKS5tb2NrUmVzb2x2ZWRWYWx1ZShtb2NrUmVzdWx0cyk7XG5cbiAgICAgIGNvbnN0IHJlc3VsdCA9IGF3YWl0IGhhbmRsZVNlYXJjaFdlYih7IHF1ZXJ5OiAndGVzdCcgfSk7XG5cbiAgICAgIGV4cGVjdChyZXN1bHQpLnRvQ29udGFpbignV2ViIHNlYXJjaCByZXN1bHRzIGZvciBcInRlc3RcIiAodmlhIE5MVSk6Jyk7XG4gICAgICBleHBlY3QocmVzdWx0KS50b0NvbnRhaW4oJ1Rlc3QgUmVzdWx0IDEnKTtcbiAgICAgIGV4cGVjdChyZXN1bHQpLnRvQ29udGFpbignVGVzdCBSZXN1bHQgMicpO1xuICAgIH0pO1xuXG4gICAgaXQoJ3Nob3VsZCByZXR1cm4gYSBtZXNzYWdlIHdoZW4gdGhlcmUgYXJlIG5vIHdlYiBzZWFyY2ggcmVzdWx0cycsIGFzeW5jICgpID0+IHtcbiAgICAgICh3ZWJSZXNlYXJjaFNraWxscy5zZWFyY2hXZWIgYXMgamVzdC5Nb2NrKS5tb2NrUmVzb2x2ZWRWYWx1ZShbXSk7XG5cbiAgICAgIGNvbnN0IHJlc3VsdCA9IGF3YWl0IGhhbmRsZVNlYXJjaFdlYih7IHF1ZXJ5OiAndGVzdCcgfSk7XG5cbiAgICAgIGV4cGVjdChyZXN1bHQpLnRvQmUoJ05vIHdlYiByZXN1bHRzIGZvdW5kIGZvciBcInRlc3RcIiAodmlhIE5MVSkuJyk7XG4gICAgfSk7XG5cbiAgICBpdCgnc2hvdWxkIHJldHVybiBhbiBlcnJvciBtZXNzYWdlIHdoZW4gdGhlIHF1ZXJ5IGlzIG1pc3NpbmcnLCBhc3luYyAoKSA9PiB7XG4gICAgICBjb25zdCByZXN1bHQgPSBhd2FpdCBoYW5kbGVTZWFyY2hXZWIoe30pO1xuXG4gICAgICBleHBlY3QocmVzdWx0KS50b0JlKFxuICAgICAgICAnQSBzZWFyY2ggcXVlcnkgaXMgcmVxdWlyZWQgdG8gc2VhcmNoIHRoZSB3ZWIgdmlhIE5MVS4nXG4gICAgICApO1xuICAgIH0pO1xuXG4gICAgaXQoJ3Nob3VsZCByZXR1cm4gYW4gZXJyb3IgbWVzc2FnZSB3aGVuIGFuIGVycm9yIG9jY3VycycsIGFzeW5jICgpID0+IHtcbiAgICAgICh3ZWJSZXNlYXJjaFNraWxscy5zZWFyY2hXZWIgYXMgamVzdC5Nb2NrKS5tb2NrUmVqZWN0ZWRWYWx1ZShcbiAgICAgICAgbmV3IEVycm9yKCdUZXN0IEVycm9yJylcbiAgICAgICk7XG5cbiAgICAgIGNvbnN0IHJlc3VsdCA9IGF3YWl0IGhhbmRsZVNlYXJjaFdlYih7IHF1ZXJ5OiAndGVzdCcgfSk7XG5cbiAgICAgIGV4cGVjdChyZXN1bHQpLnRvQmUoXG4gICAgICAgIFwiU29ycnksIEkgY291bGRuJ3QgcGVyZm9ybSB0aGUgd2ViIHNlYXJjaCBkdWUgdG8gYW4gZXJyb3IgKE5MVSBwYXRoKS5cIlxuICAgICAgKTtcbiAgICB9KTtcbiAgfSk7XG59KTtcbiJdfQ==