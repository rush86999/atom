"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.default = handler;
// This is our mock database. In a real application, you would fetch this from a CRM like Salesforce or HubSpot.
const mockCrmData = {
    opportunities: [
        {
            id: 'opp1',
            name: 'Synergy Corp Website Revamp',
            stage: 'Qualification',
            value: 120000,
        },
        {
            id: 'opp2',
            name: 'Quantum Solutions Cloud Migration',
            stage: 'Proposal',
            value: 350000,
        },
        {
            id: 'opp3',
            name: 'Innovate LLC AI Chatbot',
            stage: 'Negotiation',
            value: 75000,
        },
    ],
    contacts: [
        { id: 'cont1', name: 'Laura Chen', opportunityId: 'opp1' },
        { id: 'cont2', name: 'David Rodriguez', opportunityId: 'opp2' },
        { id: 'cont3', name: 'Samantha Williams', opportunityId: 'opp3' },
    ],
    tasks: [
        {
            id: 'task1',
            description: 'Schedule discovery call with Synergy Corp',
            dueDate: '2024-08-05',
        },
        {
            id: 'task2',
            description: 'Finalize proposal for Quantum Solutions',
            dueDate: '2024-08-10',
        },
        {
            id: 'task3',
            description: 'Send updated contract to Innovate LLC',
            dueDate: '2024-07-30',
        },
    ],
};
/**
 * API handler for fetching CRM data.
 * It simulates a network request with a 1-second delay.
 *
 * @param {NextApiRequest} req - The incoming API request. The userId could be extracted from here.
 * @param {NextApiResponse<SalesData>} res - The outgoing API response.
 */
function handler(req, res) {
    // You could use req.query.userId here to fetch user-specific data from a real CRM.
    // const { userId } = req.query;
    // Simulate a network delay of 1 second to mimic a real API call.
    setTimeout(() => {
        res.status(200).json(mockCrmData);
    }, 1000);
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiZGF0YS5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImRhdGEudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7QUFpRkEsMEJBV0M7QUFoRUQsZ0hBQWdIO0FBQ2hILE1BQU0sV0FBVyxHQUFjO0lBQzdCLGFBQWEsRUFBRTtRQUNiO1lBQ0UsRUFBRSxFQUFFLE1BQU07WUFDVixJQUFJLEVBQUUsNkJBQTZCO1lBQ25DLEtBQUssRUFBRSxlQUFlO1lBQ3RCLEtBQUssRUFBRSxNQUFNO1NBQ2Q7UUFDRDtZQUNFLEVBQUUsRUFBRSxNQUFNO1lBQ1YsSUFBSSxFQUFFLG1DQUFtQztZQUN6QyxLQUFLLEVBQUUsVUFBVTtZQUNqQixLQUFLLEVBQUUsTUFBTTtTQUNkO1FBQ0Q7WUFDRSxFQUFFLEVBQUUsTUFBTTtZQUNWLElBQUksRUFBRSx5QkFBeUI7WUFDL0IsS0FBSyxFQUFFLGFBQWE7WUFDcEIsS0FBSyxFQUFFLEtBQUs7U0FDYjtLQUNGO0lBQ0QsUUFBUSxFQUFFO1FBQ1IsRUFBRSxFQUFFLEVBQUUsT0FBTyxFQUFFLElBQUksRUFBRSxZQUFZLEVBQUUsYUFBYSxFQUFFLE1BQU0sRUFBRTtRQUMxRCxFQUFFLEVBQUUsRUFBRSxPQUFPLEVBQUUsSUFBSSxFQUFFLGlCQUFpQixFQUFFLGFBQWEsRUFBRSxNQUFNLEVBQUU7UUFDL0QsRUFBRSxFQUFFLEVBQUUsT0FBTyxFQUFFLElBQUksRUFBRSxtQkFBbUIsRUFBRSxhQUFhLEVBQUUsTUFBTSxFQUFFO0tBQ2xFO0lBQ0QsS0FBSyxFQUFFO1FBQ0w7WUFDRSxFQUFFLEVBQUUsT0FBTztZQUNYLFdBQVcsRUFBRSwyQ0FBMkM7WUFDeEQsT0FBTyxFQUFFLFlBQVk7U0FDdEI7UUFDRDtZQUNFLEVBQUUsRUFBRSxPQUFPO1lBQ1gsV0FBVyxFQUFFLHlDQUF5QztZQUN0RCxPQUFPLEVBQUUsWUFBWTtTQUN0QjtRQUNEO1lBQ0UsRUFBRSxFQUFFLE9BQU87WUFDWCxXQUFXLEVBQUUsdUNBQXVDO1lBQ3BELE9BQU8sRUFBRSxZQUFZO1NBQ3RCO0tBQ0Y7Q0FDRixDQUFDO0FBRUY7Ozs7OztHQU1HO0FBQ0gsU0FBd0IsT0FBTyxDQUM3QixHQUFtQixFQUNuQixHQUErQjtJQUUvQixtRkFBbUY7SUFDbkYsZ0NBQWdDO0lBRWhDLGlFQUFpRTtJQUNqRSxVQUFVLENBQUMsR0FBRyxFQUFFO1FBQ2QsR0FBRyxDQUFDLE1BQU0sQ0FBQyxHQUFHLENBQUMsQ0FBQyxJQUFJLENBQUMsV0FBVyxDQUFDLENBQUM7SUFDcEMsQ0FBQyxFQUFFLElBQUksQ0FBQyxDQUFDO0FBQ1gsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB0eXBlIHsgTmV4dEFwaVJlcXVlc3QsIE5leHRBcGlSZXNwb25zZSB9IGZyb20gJ25leHQnO1xuXG4vLyBEZWZpbmUgVHlwZVNjcmlwdCBpbnRlcmZhY2VzIGZvciBvdXIgZGF0YSBzdHJ1Y3R1cmVzIGZvciB0eXBlIHNhZmV0eS5cbmludGVyZmFjZSBPcHBvcnR1bml0eSB7XG4gIGlkOiBzdHJpbmc7XG4gIG5hbWU6IHN0cmluZztcbiAgc3RhZ2U6IHN0cmluZztcbiAgdmFsdWU6IG51bWJlcjtcbn1cblxuaW50ZXJmYWNlIENvbnRhY3Qge1xuICBpZDogc3RyaW5nO1xuICBuYW1lOiBzdHJpbmc7XG4gIG9wcG9ydHVuaXR5SWQ6IHN0cmluZztcbn1cblxuaW50ZXJmYWNlIFRhc2sge1xuICBpZDogc3RyaW5nO1xuICBkZXNjcmlwdGlvbjogc3RyaW5nO1xuICBkdWVEYXRlOiBzdHJpbmc7XG59XG5cbmludGVyZmFjZSBTYWxlc0RhdGEge1xuICBvcHBvcnR1bml0aWVzOiBPcHBvcnR1bml0eVtdO1xuICBjb250YWN0czogQ29udGFjdFtdO1xuICB0YXNrczogVGFza1tdO1xufVxuXG4vLyBUaGlzIGlzIG91ciBtb2NrIGRhdGFiYXNlLiBJbiBhIHJlYWwgYXBwbGljYXRpb24sIHlvdSB3b3VsZCBmZXRjaCB0aGlzIGZyb20gYSBDUk0gbGlrZSBTYWxlc2ZvcmNlIG9yIEh1YlNwb3QuXG5jb25zdCBtb2NrQ3JtRGF0YTogU2FsZXNEYXRhID0ge1xuICBvcHBvcnR1bml0aWVzOiBbXG4gICAge1xuICAgICAgaWQ6ICdvcHAxJyxcbiAgICAgIG5hbWU6ICdTeW5lcmd5IENvcnAgV2Vic2l0ZSBSZXZhbXAnLFxuICAgICAgc3RhZ2U6ICdRdWFsaWZpY2F0aW9uJyxcbiAgICAgIHZhbHVlOiAxMjAwMDAsXG4gICAgfSxcbiAgICB7XG4gICAgICBpZDogJ29wcDInLFxuICAgICAgbmFtZTogJ1F1YW50dW0gU29sdXRpb25zIENsb3VkIE1pZ3JhdGlvbicsXG4gICAgICBzdGFnZTogJ1Byb3Bvc2FsJyxcbiAgICAgIHZhbHVlOiAzNTAwMDAsXG4gICAgfSxcbiAgICB7XG4gICAgICBpZDogJ29wcDMnLFxuICAgICAgbmFtZTogJ0lubm92YXRlIExMQyBBSSBDaGF0Ym90JyxcbiAgICAgIHN0YWdlOiAnTmVnb3RpYXRpb24nLFxuICAgICAgdmFsdWU6IDc1MDAwLFxuICAgIH0sXG4gIF0sXG4gIGNvbnRhY3RzOiBbXG4gICAgeyBpZDogJ2NvbnQxJywgbmFtZTogJ0xhdXJhIENoZW4nLCBvcHBvcnR1bml0eUlkOiAnb3BwMScgfSxcbiAgICB7IGlkOiAnY29udDInLCBuYW1lOiAnRGF2aWQgUm9kcmlndWV6Jywgb3Bwb3J0dW5pdHlJZDogJ29wcDInIH0sXG4gICAgeyBpZDogJ2NvbnQzJywgbmFtZTogJ1NhbWFudGhhIFdpbGxpYW1zJywgb3Bwb3J0dW5pdHlJZDogJ29wcDMnIH0sXG4gIF0sXG4gIHRhc2tzOiBbXG4gICAge1xuICAgICAgaWQ6ICd0YXNrMScsXG4gICAgICBkZXNjcmlwdGlvbjogJ1NjaGVkdWxlIGRpc2NvdmVyeSBjYWxsIHdpdGggU3luZXJneSBDb3JwJyxcbiAgICAgIGR1ZURhdGU6ICcyMDI0LTA4LTA1JyxcbiAgICB9LFxuICAgIHtcbiAgICAgIGlkOiAndGFzazInLFxuICAgICAgZGVzY3JpcHRpb246ICdGaW5hbGl6ZSBwcm9wb3NhbCBmb3IgUXVhbnR1bSBTb2x1dGlvbnMnLFxuICAgICAgZHVlRGF0ZTogJzIwMjQtMDgtMTAnLFxuICAgIH0sXG4gICAge1xuICAgICAgaWQ6ICd0YXNrMycsXG4gICAgICBkZXNjcmlwdGlvbjogJ1NlbmQgdXBkYXRlZCBjb250cmFjdCB0byBJbm5vdmF0ZSBMTEMnLFxuICAgICAgZHVlRGF0ZTogJzIwMjQtMDctMzAnLFxuICAgIH0sXG4gIF0sXG59O1xuXG4vKipcbiAqIEFQSSBoYW5kbGVyIGZvciBmZXRjaGluZyBDUk0gZGF0YS5cbiAqIEl0IHNpbXVsYXRlcyBhIG5ldHdvcmsgcmVxdWVzdCB3aXRoIGEgMS1zZWNvbmQgZGVsYXkuXG4gKlxuICogQHBhcmFtIHtOZXh0QXBpUmVxdWVzdH0gcmVxIC0gVGhlIGluY29taW5nIEFQSSByZXF1ZXN0LiBUaGUgdXNlcklkIGNvdWxkIGJlIGV4dHJhY3RlZCBmcm9tIGhlcmUuXG4gKiBAcGFyYW0ge05leHRBcGlSZXNwb25zZTxTYWxlc0RhdGE+fSByZXMgLSBUaGUgb3V0Z29pbmcgQVBJIHJlc3BvbnNlLlxuICovXG5leHBvcnQgZGVmYXVsdCBmdW5jdGlvbiBoYW5kbGVyKFxuICByZXE6IE5leHRBcGlSZXF1ZXN0LFxuICByZXM6IE5leHRBcGlSZXNwb25zZTxTYWxlc0RhdGE+XG4pIHtcbiAgLy8gWW91IGNvdWxkIHVzZSByZXEucXVlcnkudXNlcklkIGhlcmUgdG8gZmV0Y2ggdXNlci1zcGVjaWZpYyBkYXRhIGZyb20gYSByZWFsIENSTS5cbiAgLy8gY29uc3QgeyB1c2VySWQgfSA9IHJlcS5xdWVyeTtcblxuICAvLyBTaW11bGF0ZSBhIG5ldHdvcmsgZGVsYXkgb2YgMSBzZWNvbmQgdG8gbWltaWMgYSByZWFsIEFQSSBjYWxsLlxuICBzZXRUaW1lb3V0KCgpID0+IHtcbiAgICByZXMuc3RhdHVzKDIwMCkuanNvbihtb2NrQ3JtRGF0YSk7XG4gIH0sIDEwMDApO1xufVxuIl19