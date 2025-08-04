import { createNotionPage } from './notionAndResearchSkills';
import { searchWeb } from './webResearchSkills';
async function getCompetitorNews(competitor) {
    const searchResults = await searchWeb(`news about ${competitor}`);
    // In a real app, we would process these search results to extract relevant information.
    // For now, we'll just return the first result.
    return searchResults[0]?.url || '';
}
async function analyzeCompetitorWebsite(competitor) {
    const searchResults = await searchWeb(`official website of ${competitor}`);
    // In a real app, we would scrape the website to extract relevant information.
    // For now, we'll just return the URL of the website.
    return searchResults[0]?.url || '';
}
export async function runCompetitorAnalysis(userId, competitors, notionDatabaseId) {
    for (const competitor of competitors) {
        const news = await getCompetitorNews(competitor);
        const website = await analyzeCompetitorWebsite(competitor);
        const summary = `
            Competitor: ${competitor}
            Latest News: ${news}
            Website: ${website}
        `;
        await createNotionPage(userId, {
            parent: { database_id: notionDatabaseId },
            properties: {
                title: {
                    title: [
                        {
                            text: {
                                content: `Competitor Analysis: ${competitor}`,
                            },
                        },
                    ],
                },
            },
            children: [
                {
                    object: 'block',
                    type: 'paragraph',
                    paragraph: {
                        rich_text: [
                            {
                                type: 'text',
                                text: {
                                    content: summary,
                                },
                            },
                        ],
                    },
                },
            ],
        });
    }
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiY29tcGV0aXRvckFuYWx5c2lzU2tpbGxzLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsiY29tcGV0aXRvckFuYWx5c2lzU2tpbGxzLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiJBQUNBLE9BQU8sRUFBRSxnQkFBZ0IsRUFBRSxNQUFNLDJCQUEyQixDQUFDO0FBQzdELE9BQU8sRUFBRSxTQUFTLEVBQUUsTUFBTSxxQkFBcUIsQ0FBQztBQUdoRCxLQUFLLFVBQVUsaUJBQWlCLENBQUMsVUFBa0I7SUFDakQsTUFBTSxhQUFhLEdBQUcsTUFBTSxTQUFTLENBQUMsY0FBYyxVQUFVLEVBQUUsQ0FBQyxDQUFDO0lBQ2xFLHdGQUF3RjtJQUN4RiwrQ0FBK0M7SUFDL0MsT0FBTyxhQUFhLENBQUMsQ0FBQyxDQUFDLEVBQUUsR0FBRyxJQUFJLEVBQUUsQ0FBQztBQUNyQyxDQUFDO0FBRUQsS0FBSyxVQUFVLHdCQUF3QixDQUFDLFVBQWtCO0lBQ3hELE1BQU0sYUFBYSxHQUFHLE1BQU0sU0FBUyxDQUFDLHVCQUF1QixVQUFVLEVBQUUsQ0FBQyxDQUFDO0lBQzNFLDhFQUE4RTtJQUM5RSxxREFBcUQ7SUFDckQsT0FBTyxhQUFhLENBQUMsQ0FBQyxDQUFDLEVBQUUsR0FBRyxJQUFJLEVBQUUsQ0FBQztBQUNyQyxDQUFDO0FBRUQsTUFBTSxDQUFDLEtBQUssVUFBVSxxQkFBcUIsQ0FDekMsTUFBYyxFQUNkLFdBQXFCLEVBQ3JCLGdCQUF3QjtJQUV4QixLQUFLLE1BQU0sVUFBVSxJQUFJLFdBQVcsRUFBRSxDQUFDO1FBQ3JDLE1BQU0sSUFBSSxHQUFHLE1BQU0saUJBQWlCLENBQUMsVUFBVSxDQUFDLENBQUM7UUFDakQsTUFBTSxPQUFPLEdBQUcsTUFBTSx3QkFBd0IsQ0FBQyxVQUFVLENBQUMsQ0FBQztRQUUzRCxNQUFNLE9BQU8sR0FBRzswQkFDTSxVQUFVOzJCQUNULElBQUk7dUJBQ1IsT0FBTztTQUNyQixDQUFDO1FBRU4sTUFBTSxnQkFBZ0IsQ0FBQyxNQUFNLEVBQUU7WUFDN0IsTUFBTSxFQUFFLEVBQUUsV0FBVyxFQUFFLGdCQUFnQixFQUFFO1lBQ3pDLFVBQVUsRUFBRTtnQkFDVixLQUFLLEVBQUU7b0JBQ0wsS0FBSyxFQUFFO3dCQUNMOzRCQUNFLElBQUksRUFBRTtnQ0FDSixPQUFPLEVBQUUsd0JBQXdCLFVBQVUsRUFBRTs2QkFDOUM7eUJBQ0Y7cUJBQ0Y7aUJBQ0Y7YUFDRjtZQUNELFFBQVEsRUFBRTtnQkFDUjtvQkFDRSxNQUFNLEVBQUUsT0FBTztvQkFDZixJQUFJLEVBQUUsV0FBVztvQkFDakIsU0FBUyxFQUFFO3dCQUNULFNBQVMsRUFBRTs0QkFDVDtnQ0FDRSxJQUFJLEVBQUUsTUFBTTtnQ0FDWixJQUFJLEVBQUU7b0NBQ0osT0FBTyxFQUFFLE9BQU87aUNBQ2pCOzZCQUNGO3lCQUNGO3FCQUNGO2lCQUNGO2FBQ0Y7U0FDRixDQUFDLENBQUM7SUFDTCxDQUFDO0FBQ0gsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7IE5vdGlvblRhc2sgfSBmcm9tICcuLi8uLi90eXBlcyc7XG5pbXBvcnQgeyBjcmVhdGVOb3Rpb25QYWdlIH0gZnJvbSAnLi9ub3Rpb25BbmRSZXNlYXJjaFNraWxscyc7XG5pbXBvcnQgeyBzZWFyY2hXZWIgfSBmcm9tICcuL3dlYlJlc2VhcmNoU2tpbGxzJztcbmltcG9ydCB7IGFuYWx5emVTZW50aW1lbnQgfSBmcm9tICcuLi8uLi9kZXNrdG9wL3RhdXJpL3NyYy9saWIvc2VudGltZW50JztcblxuYXN5bmMgZnVuY3Rpb24gZ2V0Q29tcGV0aXRvck5ld3MoY29tcGV0aXRvcjogc3RyaW5nKTogUHJvbWlzZTxzdHJpbmc+IHtcbiAgY29uc3Qgc2VhcmNoUmVzdWx0cyA9IGF3YWl0IHNlYXJjaFdlYihgbmV3cyBhYm91dCAke2NvbXBldGl0b3J9YCk7XG4gIC8vIEluIGEgcmVhbCBhcHAsIHdlIHdvdWxkIHByb2Nlc3MgdGhlc2Ugc2VhcmNoIHJlc3VsdHMgdG8gZXh0cmFjdCByZWxldmFudCBpbmZvcm1hdGlvbi5cbiAgLy8gRm9yIG5vdywgd2UnbGwganVzdCByZXR1cm4gdGhlIGZpcnN0IHJlc3VsdC5cbiAgcmV0dXJuIHNlYXJjaFJlc3VsdHNbMF0/LnVybCB8fCAnJztcbn1cblxuYXN5bmMgZnVuY3Rpb24gYW5hbHl6ZUNvbXBldGl0b3JXZWJzaXRlKGNvbXBldGl0b3I6IHN0cmluZyk6IFByb21pc2U8c3RyaW5nPiB7XG4gIGNvbnN0IHNlYXJjaFJlc3VsdHMgPSBhd2FpdCBzZWFyY2hXZWIoYG9mZmljaWFsIHdlYnNpdGUgb2YgJHtjb21wZXRpdG9yfWApO1xuICAvLyBJbiBhIHJlYWwgYXBwLCB3ZSB3b3VsZCBzY3JhcGUgdGhlIHdlYnNpdGUgdG8gZXh0cmFjdCByZWxldmFudCBpbmZvcm1hdGlvbi5cbiAgLy8gRm9yIG5vdywgd2UnbGwganVzdCByZXR1cm4gdGhlIFVSTCBvZiB0aGUgd2Vic2l0ZS5cbiAgcmV0dXJuIHNlYXJjaFJlc3VsdHNbMF0/LnVybCB8fCAnJztcbn1cblxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIHJ1bkNvbXBldGl0b3JBbmFseXNpcyhcbiAgdXNlcklkOiBzdHJpbmcsXG4gIGNvbXBldGl0b3JzOiBzdHJpbmdbXSxcbiAgbm90aW9uRGF0YWJhc2VJZDogc3RyaW5nXG4pOiBQcm9taXNlPHZvaWQ+IHtcbiAgZm9yIChjb25zdCBjb21wZXRpdG9yIG9mIGNvbXBldGl0b3JzKSB7XG4gICAgY29uc3QgbmV3cyA9IGF3YWl0IGdldENvbXBldGl0b3JOZXdzKGNvbXBldGl0b3IpO1xuICAgIGNvbnN0IHdlYnNpdGUgPSBhd2FpdCBhbmFseXplQ29tcGV0aXRvcldlYnNpdGUoY29tcGV0aXRvcik7XG5cbiAgICBjb25zdCBzdW1tYXJ5ID0gYFxuICAgICAgICAgICAgQ29tcGV0aXRvcjogJHtjb21wZXRpdG9yfVxuICAgICAgICAgICAgTGF0ZXN0IE5ld3M6ICR7bmV3c31cbiAgICAgICAgICAgIFdlYnNpdGU6ICR7d2Vic2l0ZX1cbiAgICAgICAgYDtcblxuICAgIGF3YWl0IGNyZWF0ZU5vdGlvblBhZ2UodXNlcklkLCB7XG4gICAgICBwYXJlbnQ6IHsgZGF0YWJhc2VfaWQ6IG5vdGlvbkRhdGFiYXNlSWQgfSxcbiAgICAgIHByb3BlcnRpZXM6IHtcbiAgICAgICAgdGl0bGU6IHtcbiAgICAgICAgICB0aXRsZTogW1xuICAgICAgICAgICAge1xuICAgICAgICAgICAgICB0ZXh0OiB7XG4gICAgICAgICAgICAgICAgY29udGVudDogYENvbXBldGl0b3IgQW5hbHlzaXM6ICR7Y29tcGV0aXRvcn1gLFxuICAgICAgICAgICAgICB9LFxuICAgICAgICAgICAgfSxcbiAgICAgICAgICBdLFxuICAgICAgICB9LFxuICAgICAgfSxcbiAgICAgIGNoaWxkcmVuOiBbXG4gICAgICAgIHtcbiAgICAgICAgICBvYmplY3Q6ICdibG9jaycsXG4gICAgICAgICAgdHlwZTogJ3BhcmFncmFwaCcsXG4gICAgICAgICAgcGFyYWdyYXBoOiB7XG4gICAgICAgICAgICByaWNoX3RleHQ6IFtcbiAgICAgICAgICAgICAge1xuICAgICAgICAgICAgICAgIHR5cGU6ICd0ZXh0JyxcbiAgICAgICAgICAgICAgICB0ZXh0OiB7XG4gICAgICAgICAgICAgICAgICBjb250ZW50OiBzdW1tYXJ5LFxuICAgICAgICAgICAgICAgIH0sXG4gICAgICAgICAgICAgIH0sXG4gICAgICAgICAgICBdLFxuICAgICAgICAgIH0sXG4gICAgICAgIH0sXG4gICAgICBdLFxuICAgIH0pO1xuICB9XG59XG4iXX0=