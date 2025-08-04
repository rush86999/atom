"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.default = handler;
// Mock data representing a company's internal knowledge base (like Confluence or Notion)
const allArticles = [
    {
        id: 'kb-1',
        title: 'How to Set Up Your VPN',
        content: 'To set up your VPN, please download the GlobalProtect client from the IT portal and follow the on-screen instructions. Contact IT support for any issues.',
        category: 'IT',
        lastUpdated: '2024-06-15',
    },
    {
        id: 'kb-2',
        title: 'Submitting Expense Reports',
        content: 'All expense reports must be submitted through the "Expenses" app on your employee dashboard. Please ensure all receipts are attached.',
        category: 'HR',
        lastUpdated: '2024-07-01',
    },
    {
        id: 'kb-3',
        title: 'Requesting Time Off',
        content: 'Paid time off (PTO) can be requested via the Workday portal under the "Absence" section. Requests should be submitted at least two weeks in advance.',
        category: 'HR',
        lastUpdated: '2024-05-20',
    },
    {
        id: 'kb-4',
        title: 'Git Branching Strategy',
        content: 'Our standard Git branching strategy is GitFlow. Please create feature branches from `develop` and submit pull requests for review.',
        category: 'Engineering',
        lastUpdated: '2024-07-25',
    },
    {
        id: 'kb-5',
        title: 'Accessing Staging Environments',
        content: 'To access the staging environment, you must be connected to the VPN. The credentials can be found in the secure password vault.',
        category: 'Engineering',
        lastUpdated: '2024-07-18',
    },
    {
        id: 'kb-6',
        title: 'Resetting Your Corporate Password',
        content: 'If you have forgotten your password, you can reset it by visiting the login page and clicking "Forgot Password". A reset link will be sent to your recovery email.',
        category: 'IT',
        lastUpdated: '2024-07-28',
    },
];
/**
 * API handler for searching the knowledge base.
 * It filters articles based on a query parameter and simulates a network delay.
 *
 * @param {NextApiRequest} req - The incoming API request. Expects a 'q' query parameter.
 * @param {NextApiResponse<Article[] | { message: string }>} res - The outgoing API response.
 */
function handler(req, res) {
    // Extract the search query from the request.
    const { q: searchQuery } = req.query;
    // Simulate a network delay of 1 second.
    setTimeout(() => {
        // If there's no search query, return all articles.
        if (!searchQuery || typeof searchQuery !== 'string') {
            res.status(200).json(allArticles);
            return;
        }
        // Filter articles based on the search query (case-insensitive).
        const lowercasedQuery = searchQuery.toLowerCase();
        const results = allArticles.filter((article) => article.title.toLowerCase().includes(lowercasedQuery) ||
            article.content.toLowerCase().includes(lowercasedQuery));
        res.status(200).json(results);
    }, 1000); // 1-second delay
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoia25vd2xlZGdlLWJhc2UuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJrbm93bGVkZ2UtYmFzZS50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOztBQXNFQSwwQkF5QkM7QUFwRkQseUZBQXlGO0FBQ3pGLE1BQU0sV0FBVyxHQUFjO0lBQzdCO1FBQ0UsRUFBRSxFQUFFLE1BQU07UUFDVixLQUFLLEVBQUUsd0JBQXdCO1FBQy9CLE9BQU8sRUFDTCwySkFBMko7UUFDN0osUUFBUSxFQUFFLElBQUk7UUFDZCxXQUFXLEVBQUUsWUFBWTtLQUMxQjtJQUNEO1FBQ0UsRUFBRSxFQUFFLE1BQU07UUFDVixLQUFLLEVBQUUsNEJBQTRCO1FBQ25DLE9BQU8sRUFDTCx1SUFBdUk7UUFDekksUUFBUSxFQUFFLElBQUk7UUFDZCxXQUFXLEVBQUUsWUFBWTtLQUMxQjtJQUNEO1FBQ0UsRUFBRSxFQUFFLE1BQU07UUFDVixLQUFLLEVBQUUscUJBQXFCO1FBQzVCLE9BQU8sRUFDTCxzSkFBc0o7UUFDeEosUUFBUSxFQUFFLElBQUk7UUFDZCxXQUFXLEVBQUUsWUFBWTtLQUMxQjtJQUNEO1FBQ0UsRUFBRSxFQUFFLE1BQU07UUFDVixLQUFLLEVBQUUsd0JBQXdCO1FBQy9CLE9BQU8sRUFDTCxvSUFBb0k7UUFDdEksUUFBUSxFQUFFLGFBQWE7UUFDdkIsV0FBVyxFQUFFLFlBQVk7S0FDMUI7SUFDRDtRQUNFLEVBQUUsRUFBRSxNQUFNO1FBQ1YsS0FBSyxFQUFFLGdDQUFnQztRQUN2QyxPQUFPLEVBQ0wsaUlBQWlJO1FBQ25JLFFBQVEsRUFBRSxhQUFhO1FBQ3ZCLFdBQVcsRUFBRSxZQUFZO0tBQzFCO0lBQ0Q7UUFDRSxFQUFFLEVBQUUsTUFBTTtRQUNWLEtBQUssRUFBRSxtQ0FBbUM7UUFDMUMsT0FBTyxFQUNMLG9LQUFvSztRQUN0SyxRQUFRLEVBQUUsSUFBSTtRQUNkLFdBQVcsRUFBRSxZQUFZO0tBQzFCO0NBQ0YsQ0FBQztBQUVGOzs7Ozs7R0FNRztBQUNILFNBQXdCLE9BQU8sQ0FDN0IsR0FBbUIsRUFDbkIsR0FBcUQ7SUFFckQsNkNBQTZDO0lBQzdDLE1BQU0sRUFBRSxDQUFDLEVBQUUsV0FBVyxFQUFFLEdBQUcsR0FBRyxDQUFDLEtBQUssQ0FBQztJQUVyQyx3Q0FBd0M7SUFDeEMsVUFBVSxDQUFDLEdBQUcsRUFBRTtRQUNkLG1EQUFtRDtRQUNuRCxJQUFJLENBQUMsV0FBVyxJQUFJLE9BQU8sV0FBVyxLQUFLLFFBQVEsRUFBRSxDQUFDO1lBQ3BELEdBQUcsQ0FBQyxNQUFNLENBQUMsR0FBRyxDQUFDLENBQUMsSUFBSSxDQUFDLFdBQVcsQ0FBQyxDQUFDO1lBQ2xDLE9BQU87UUFDVCxDQUFDO1FBRUQsZ0VBQWdFO1FBQ2hFLE1BQU0sZUFBZSxHQUFHLFdBQVcsQ0FBQyxXQUFXLEVBQUUsQ0FBQztRQUNsRCxNQUFNLE9BQU8sR0FBRyxXQUFXLENBQUMsTUFBTSxDQUNoQyxDQUFDLE9BQU8sRUFBRSxFQUFFLENBQ1YsT0FBTyxDQUFDLEtBQUssQ0FBQyxXQUFXLEVBQUUsQ0FBQyxRQUFRLENBQUMsZUFBZSxDQUFDO1lBQ3JELE9BQU8sQ0FBQyxPQUFPLENBQUMsV0FBVyxFQUFFLENBQUMsUUFBUSxDQUFDLGVBQWUsQ0FBQyxDQUMxRCxDQUFDO1FBRUYsR0FBRyxDQUFDLE1BQU0sQ0FBQyxHQUFHLENBQUMsQ0FBQyxJQUFJLENBQUMsT0FBTyxDQUFDLENBQUM7SUFDaEMsQ0FBQyxFQUFFLElBQUksQ0FBQyxDQUFDLENBQUMsaUJBQWlCO0FBQzdCLENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgdHlwZSB7IE5leHRBcGlSZXF1ZXN0LCBOZXh0QXBpUmVzcG9uc2UgfSBmcm9tICduZXh0JztcblxuLy8gRGVmaW5lIHRoZSBzdHJ1Y3R1cmUgZm9yIGEga25vd2xlZGdlIGJhc2UgYXJ0aWNsZVxuZXhwb3J0IGludGVyZmFjZSBBcnRpY2xlIHtcbiAgaWQ6IHN0cmluZztcbiAgdGl0bGU6IHN0cmluZztcbiAgY29udGVudDogc3RyaW5nO1xuICBjYXRlZ29yeTogJ0hSJyB8ICdJVCcgfCAnRW5naW5lZXJpbmcnO1xuICBsYXN0VXBkYXRlZDogc3RyaW5nO1xufVxuXG4vLyBNb2NrIGRhdGEgcmVwcmVzZW50aW5nIGEgY29tcGFueSdzIGludGVybmFsIGtub3dsZWRnZSBiYXNlIChsaWtlIENvbmZsdWVuY2Ugb3IgTm90aW9uKVxuY29uc3QgYWxsQXJ0aWNsZXM6IEFydGljbGVbXSA9IFtcbiAge1xuICAgIGlkOiAna2ItMScsXG4gICAgdGl0bGU6ICdIb3cgdG8gU2V0IFVwIFlvdXIgVlBOJyxcbiAgICBjb250ZW50OlxuICAgICAgJ1RvIHNldCB1cCB5b3VyIFZQTiwgcGxlYXNlIGRvd25sb2FkIHRoZSBHbG9iYWxQcm90ZWN0IGNsaWVudCBmcm9tIHRoZSBJVCBwb3J0YWwgYW5kIGZvbGxvdyB0aGUgb24tc2NyZWVuIGluc3RydWN0aW9ucy4gQ29udGFjdCBJVCBzdXBwb3J0IGZvciBhbnkgaXNzdWVzLicsXG4gICAgY2F0ZWdvcnk6ICdJVCcsXG4gICAgbGFzdFVwZGF0ZWQ6ICcyMDI0LTA2LTE1JyxcbiAgfSxcbiAge1xuICAgIGlkOiAna2ItMicsXG4gICAgdGl0bGU6ICdTdWJtaXR0aW5nIEV4cGVuc2UgUmVwb3J0cycsXG4gICAgY29udGVudDpcbiAgICAgICdBbGwgZXhwZW5zZSByZXBvcnRzIG11c3QgYmUgc3VibWl0dGVkIHRocm91Z2ggdGhlIFwiRXhwZW5zZXNcIiBhcHAgb24geW91ciBlbXBsb3llZSBkYXNoYm9hcmQuIFBsZWFzZSBlbnN1cmUgYWxsIHJlY2VpcHRzIGFyZSBhdHRhY2hlZC4nLFxuICAgIGNhdGVnb3J5OiAnSFInLFxuICAgIGxhc3RVcGRhdGVkOiAnMjAyNC0wNy0wMScsXG4gIH0sXG4gIHtcbiAgICBpZDogJ2tiLTMnLFxuICAgIHRpdGxlOiAnUmVxdWVzdGluZyBUaW1lIE9mZicsXG4gICAgY29udGVudDpcbiAgICAgICdQYWlkIHRpbWUgb2ZmIChQVE8pIGNhbiBiZSByZXF1ZXN0ZWQgdmlhIHRoZSBXb3JrZGF5IHBvcnRhbCB1bmRlciB0aGUgXCJBYnNlbmNlXCIgc2VjdGlvbi4gUmVxdWVzdHMgc2hvdWxkIGJlIHN1Ym1pdHRlZCBhdCBsZWFzdCB0d28gd2Vla3MgaW4gYWR2YW5jZS4nLFxuICAgIGNhdGVnb3J5OiAnSFInLFxuICAgIGxhc3RVcGRhdGVkOiAnMjAyNC0wNS0yMCcsXG4gIH0sXG4gIHtcbiAgICBpZDogJ2tiLTQnLFxuICAgIHRpdGxlOiAnR2l0IEJyYW5jaGluZyBTdHJhdGVneScsXG4gICAgY29udGVudDpcbiAgICAgICdPdXIgc3RhbmRhcmQgR2l0IGJyYW5jaGluZyBzdHJhdGVneSBpcyBHaXRGbG93LiBQbGVhc2UgY3JlYXRlIGZlYXR1cmUgYnJhbmNoZXMgZnJvbSBgZGV2ZWxvcGAgYW5kIHN1Ym1pdCBwdWxsIHJlcXVlc3RzIGZvciByZXZpZXcuJyxcbiAgICBjYXRlZ29yeTogJ0VuZ2luZWVyaW5nJyxcbiAgICBsYXN0VXBkYXRlZDogJzIwMjQtMDctMjUnLFxuICB9LFxuICB7XG4gICAgaWQ6ICdrYi01JyxcbiAgICB0aXRsZTogJ0FjY2Vzc2luZyBTdGFnaW5nIEVudmlyb25tZW50cycsXG4gICAgY29udGVudDpcbiAgICAgICdUbyBhY2Nlc3MgdGhlIHN0YWdpbmcgZW52aXJvbm1lbnQsIHlvdSBtdXN0IGJlIGNvbm5lY3RlZCB0byB0aGUgVlBOLiBUaGUgY3JlZGVudGlhbHMgY2FuIGJlIGZvdW5kIGluIHRoZSBzZWN1cmUgcGFzc3dvcmQgdmF1bHQuJyxcbiAgICBjYXRlZ29yeTogJ0VuZ2luZWVyaW5nJyxcbiAgICBsYXN0VXBkYXRlZDogJzIwMjQtMDctMTgnLFxuICB9LFxuICB7XG4gICAgaWQ6ICdrYi02JyxcbiAgICB0aXRsZTogJ1Jlc2V0dGluZyBZb3VyIENvcnBvcmF0ZSBQYXNzd29yZCcsXG4gICAgY29udGVudDpcbiAgICAgICdJZiB5b3UgaGF2ZSBmb3Jnb3R0ZW4geW91ciBwYXNzd29yZCwgeW91IGNhbiByZXNldCBpdCBieSB2aXNpdGluZyB0aGUgbG9naW4gcGFnZSBhbmQgY2xpY2tpbmcgXCJGb3Jnb3QgUGFzc3dvcmRcIi4gQSByZXNldCBsaW5rIHdpbGwgYmUgc2VudCB0byB5b3VyIHJlY292ZXJ5IGVtYWlsLicsXG4gICAgY2F0ZWdvcnk6ICdJVCcsXG4gICAgbGFzdFVwZGF0ZWQ6ICcyMDI0LTA3LTI4JyxcbiAgfSxcbl07XG5cbi8qKlxuICogQVBJIGhhbmRsZXIgZm9yIHNlYXJjaGluZyB0aGUga25vd2xlZGdlIGJhc2UuXG4gKiBJdCBmaWx0ZXJzIGFydGljbGVzIGJhc2VkIG9uIGEgcXVlcnkgcGFyYW1ldGVyIGFuZCBzaW11bGF0ZXMgYSBuZXR3b3JrIGRlbGF5LlxuICpcbiAqIEBwYXJhbSB7TmV4dEFwaVJlcXVlc3R9IHJlcSAtIFRoZSBpbmNvbWluZyBBUEkgcmVxdWVzdC4gRXhwZWN0cyBhICdxJyBxdWVyeSBwYXJhbWV0ZXIuXG4gKiBAcGFyYW0ge05leHRBcGlSZXNwb25zZTxBcnRpY2xlW10gfCB7IG1lc3NhZ2U6IHN0cmluZyB9Pn0gcmVzIC0gVGhlIG91dGdvaW5nIEFQSSByZXNwb25zZS5cbiAqL1xuZXhwb3J0IGRlZmF1bHQgZnVuY3Rpb24gaGFuZGxlcihcbiAgcmVxOiBOZXh0QXBpUmVxdWVzdCxcbiAgcmVzOiBOZXh0QXBpUmVzcG9uc2U8QXJ0aWNsZVtdIHwgeyBtZXNzYWdlOiBzdHJpbmcgfT5cbikge1xuICAvLyBFeHRyYWN0IHRoZSBzZWFyY2ggcXVlcnkgZnJvbSB0aGUgcmVxdWVzdC5cbiAgY29uc3QgeyBxOiBzZWFyY2hRdWVyeSB9ID0gcmVxLnF1ZXJ5O1xuXG4gIC8vIFNpbXVsYXRlIGEgbmV0d29yayBkZWxheSBvZiAxIHNlY29uZC5cbiAgc2V0VGltZW91dCgoKSA9PiB7XG4gICAgLy8gSWYgdGhlcmUncyBubyBzZWFyY2ggcXVlcnksIHJldHVybiBhbGwgYXJ0aWNsZXMuXG4gICAgaWYgKCFzZWFyY2hRdWVyeSB8fCB0eXBlb2Ygc2VhcmNoUXVlcnkgIT09ICdzdHJpbmcnKSB7XG4gICAgICByZXMuc3RhdHVzKDIwMCkuanNvbihhbGxBcnRpY2xlcyk7XG4gICAgICByZXR1cm47XG4gICAgfVxuXG4gICAgLy8gRmlsdGVyIGFydGljbGVzIGJhc2VkIG9uIHRoZSBzZWFyY2ggcXVlcnkgKGNhc2UtaW5zZW5zaXRpdmUpLlxuICAgIGNvbnN0IGxvd2VyY2FzZWRRdWVyeSA9IHNlYXJjaFF1ZXJ5LnRvTG93ZXJDYXNlKCk7XG4gICAgY29uc3QgcmVzdWx0cyA9IGFsbEFydGljbGVzLmZpbHRlcihcbiAgICAgIChhcnRpY2xlKSA9PlxuICAgICAgICBhcnRpY2xlLnRpdGxlLnRvTG93ZXJDYXNlKCkuaW5jbHVkZXMobG93ZXJjYXNlZFF1ZXJ5KSB8fFxuICAgICAgICBhcnRpY2xlLmNvbnRlbnQudG9Mb3dlckNhc2UoKS5pbmNsdWRlcyhsb3dlcmNhc2VkUXVlcnkpXG4gICAgKTtcblxuICAgIHJlcy5zdGF0dXMoMjAwKS5qc29uKHJlc3VsdHMpO1xuICB9LCAxMDAwKTsgLy8gMS1zZWNvbmQgZGVsYXlcbn1cbiJdfQ==