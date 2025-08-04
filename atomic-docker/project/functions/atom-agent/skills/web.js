import { searchWeb as search } from './webResearchSkills';
import { handleError } from '../../_utils/errorHandler';
export async function handleSearchWeb(entities) {
    try {
        const { query } = entities;
        if (!query || typeof query !== 'string') {
            return 'A search query is required to search the web via NLU.';
        }
        else {
            const results = await search(query);
            if (results.length === 0) {
                return `No web results found for "${query}" (via NLU).`;
            }
            else {
                const resultList = results
                    .map((result) => `- ${result.title}\n  Link: ${result.link}\n  Snippet: ${result.snippet}`)
                    .join('\n\n');
                return `Web search results for "${query}" (via NLU):\n\n${resultList}`;
            }
        }
    }
    catch (error) {
        return handleError(error, "Sorry, I couldn't perform the web search due to an error (NLU path).");
    }
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoid2ViLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsid2ViLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiJBQUNBLE9BQU8sRUFBRSxTQUFTLElBQUksTUFBTSxFQUFFLE1BQU0scUJBQXFCLENBQUM7QUFDMUQsT0FBTyxFQUFFLFdBQVcsRUFBRSxNQUFNLDJCQUEyQixDQUFDO0FBRXhELE1BQU0sQ0FBQyxLQUFLLFVBQVUsZUFBZSxDQUFDLFFBQWE7SUFDakQsSUFBSSxDQUFDO1FBQ0gsTUFBTSxFQUFFLEtBQUssRUFBRSxHQUFHLFFBQVEsQ0FBQztRQUMzQixJQUFJLENBQUMsS0FBSyxJQUFJLE9BQU8sS0FBSyxLQUFLLFFBQVEsRUFBRSxDQUFDO1lBQ3hDLE9BQU8sdURBQXVELENBQUM7UUFDakUsQ0FBQzthQUFNLENBQUM7WUFDTixNQUFNLE9BQU8sR0FBbUIsTUFBTSxNQUFNLENBQUMsS0FBSyxDQUFDLENBQUM7WUFDcEQsSUFBSSxPQUFPLENBQUMsTUFBTSxLQUFLLENBQUMsRUFBRSxDQUFDO2dCQUN6QixPQUFPLDZCQUE2QixLQUFLLGNBQWMsQ0FBQztZQUMxRCxDQUFDO2lCQUFNLENBQUM7Z0JBQ04sTUFBTSxVQUFVLEdBQUcsT0FBTztxQkFDdkIsR0FBRyxDQUNGLENBQUMsTUFBTSxFQUFFLEVBQUUsQ0FDVCxLQUFLLE1BQU0sQ0FBQyxLQUFLLGFBQWEsTUFBTSxDQUFDLElBQUksZ0JBQWdCLE1BQU0sQ0FBQyxPQUFPLEVBQUUsQ0FDNUU7cUJBQ0EsSUFBSSxDQUFDLE1BQU0sQ0FBQyxDQUFDO2dCQUNoQixPQUFPLDJCQUEyQixLQUFLLG1CQUFtQixVQUFVLEVBQUUsQ0FBQztZQUN6RSxDQUFDO1FBQ0gsQ0FBQztJQUNILENBQUM7SUFBQyxPQUFPLEtBQVUsRUFBRSxDQUFDO1FBQ3BCLE9BQU8sV0FBVyxDQUNoQixLQUFLLEVBQ0wsc0VBQXNFLENBQ3ZFLENBQUM7SUFDSixDQUFDO0FBQ0gsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7IFNlYXJjaFJlc3VsdCB9IGZyb20gJy4uLy4uL3R5cGVzJztcbmltcG9ydCB7IHNlYXJjaFdlYiBhcyBzZWFyY2ggfSBmcm9tICcuL3dlYlJlc2VhcmNoU2tpbGxzJztcbmltcG9ydCB7IGhhbmRsZUVycm9yIH0gZnJvbSAnLi4vLi4vX3V0aWxzL2Vycm9ySGFuZGxlcic7XG5cbmV4cG9ydCBhc3luYyBmdW5jdGlvbiBoYW5kbGVTZWFyY2hXZWIoZW50aXRpZXM6IGFueSk6IFByb21pc2U8c3RyaW5nPiB7XG4gIHRyeSB7XG4gICAgY29uc3QgeyBxdWVyeSB9ID0gZW50aXRpZXM7XG4gICAgaWYgKCFxdWVyeSB8fCB0eXBlb2YgcXVlcnkgIT09ICdzdHJpbmcnKSB7XG4gICAgICByZXR1cm4gJ0Egc2VhcmNoIHF1ZXJ5IGlzIHJlcXVpcmVkIHRvIHNlYXJjaCB0aGUgd2ViIHZpYSBOTFUuJztcbiAgICB9IGVsc2Uge1xuICAgICAgY29uc3QgcmVzdWx0czogU2VhcmNoUmVzdWx0W10gPSBhd2FpdCBzZWFyY2gocXVlcnkpO1xuICAgICAgaWYgKHJlc3VsdHMubGVuZ3RoID09PSAwKSB7XG4gICAgICAgIHJldHVybiBgTm8gd2ViIHJlc3VsdHMgZm91bmQgZm9yIFwiJHtxdWVyeX1cIiAodmlhIE5MVSkuYDtcbiAgICAgIH0gZWxzZSB7XG4gICAgICAgIGNvbnN0IHJlc3VsdExpc3QgPSByZXN1bHRzXG4gICAgICAgICAgLm1hcChcbiAgICAgICAgICAgIChyZXN1bHQpID0+XG4gICAgICAgICAgICAgIGAtICR7cmVzdWx0LnRpdGxlfVxcbiAgTGluazogJHtyZXN1bHQubGlua31cXG4gIFNuaXBwZXQ6ICR7cmVzdWx0LnNuaXBwZXR9YFxuICAgICAgICAgIClcbiAgICAgICAgICAuam9pbignXFxuXFxuJyk7XG4gICAgICAgIHJldHVybiBgV2ViIHNlYXJjaCByZXN1bHRzIGZvciBcIiR7cXVlcnl9XCIgKHZpYSBOTFUpOlxcblxcbiR7cmVzdWx0TGlzdH1gO1xuICAgICAgfVxuICAgIH1cbiAgfSBjYXRjaCAoZXJyb3I6IGFueSkge1xuICAgIHJldHVybiBoYW5kbGVFcnJvcihcbiAgICAgIGVycm9yLFxuICAgICAgXCJTb3JyeSwgSSBjb3VsZG4ndCBwZXJmb3JtIHRoZSB3ZWIgc2VhcmNoIGR1ZSB0byBhbiBlcnJvciAoTkxVIHBhdGgpLlwiXG4gICAgKTtcbiAgfVxufVxuIl19