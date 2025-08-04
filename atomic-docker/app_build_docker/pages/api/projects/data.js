"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.default = handler;
// This is our mock database for project management data (like Jira or Asana).
const mockProjectData = {
    project: {
        id: 'proj-apollo',
        name: 'Project Apollo',
        description: 'A mission to revolutionize space travel through AI-driven logistics.',
        status: 'On Track',
    },
    tasks: [
        {
            id: 'task-101',
            title: 'Develop propulsion system prototype',
            status: 'In Progress',
            assignee: 'Alex Ray',
        },
        {
            id: 'task-102',
            title: 'Design user interface for mission control',
            status: 'In Progress',
            assignee: 'Casey Jordan',
        },
        {
            id: 'task-103',
            title: 'Set up CI/CD pipeline for deployment',
            status: 'Done',
            assignee: 'Dev Team',
        },
        {
            id: 'task-104',
            title: 'Perform initial risk assessment',
            status: 'Done',
            assignee: 'Alex Ray',
        },
        {
            id: 'task-105',
            title: 'Finalize Q3 budget and resource allocation',
            status: 'To Do',
            assignee: 'Casey Jordan',
        },
    ],
    team: [
        { id: 'team-1', name: 'Alex Ray', role: 'Lead Engineer' },
        { id: 'team-2', name: 'Casey Jordan', role: 'UX/UI Designer' },
    ],
    activityStream: [
        {
            id: 'act-1',
            description: 'Casey Jordan updated the status of "Design user interface for mission control" to "In Progress".',
            timestamp: '2024-08-01T10:00:00Z',
        },
        {
            id: 'act-2',
            description: 'Alex Ray completed the task "Perform initial risk assessment".',
            timestamp: '2024-07-31T15:30:00Z',
        },
        {
            id: 'act-3',
            description: 'A new task "Finalize Q3 budget and resource allocation" was added to the project.',
            timestamp: '2024-07-30T11:00:00Z',
        },
    ],
};
/**
 * API handler for fetching project management data.
 * Simulates a network request with a 1-second delay.
 *
 * @param {NextApiRequest} req - The incoming API request.
 * @param {NextApiResponse<ProjectData>} res - The outgoing API response.
 */
function handler(req, res) {
    // Simulate a network delay of 1 second.
    setTimeout(() => {
        res.status(200).json(mockProjectData);
    }, 1000);
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiZGF0YS5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImRhdGEudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7QUE4R0EsMEJBUUM7QUFsRkQsOEVBQThFO0FBQzlFLE1BQU0sZUFBZSxHQUFnQjtJQUNuQyxPQUFPLEVBQUU7UUFDUCxFQUFFLEVBQUUsYUFBYTtRQUNqQixJQUFJLEVBQUUsZ0JBQWdCO1FBQ3RCLFdBQVcsRUFDVCxzRUFBc0U7UUFDeEUsTUFBTSxFQUFFLFVBQVU7S0FDbkI7SUFDRCxLQUFLLEVBQUU7UUFDTDtZQUNFLEVBQUUsRUFBRSxVQUFVO1lBQ2QsS0FBSyxFQUFFLHFDQUFxQztZQUM1QyxNQUFNLEVBQUUsYUFBYTtZQUNyQixRQUFRLEVBQUUsVUFBVTtTQUNyQjtRQUNEO1lBQ0UsRUFBRSxFQUFFLFVBQVU7WUFDZCxLQUFLLEVBQUUsMkNBQTJDO1lBQ2xELE1BQU0sRUFBRSxhQUFhO1lBQ3JCLFFBQVEsRUFBRSxjQUFjO1NBQ3pCO1FBQ0Q7WUFDRSxFQUFFLEVBQUUsVUFBVTtZQUNkLEtBQUssRUFBRSxzQ0FBc0M7WUFDN0MsTUFBTSxFQUFFLE1BQU07WUFDZCxRQUFRLEVBQUUsVUFBVTtTQUNyQjtRQUNEO1lBQ0UsRUFBRSxFQUFFLFVBQVU7WUFDZCxLQUFLLEVBQUUsaUNBQWlDO1lBQ3hDLE1BQU0sRUFBRSxNQUFNO1lBQ2QsUUFBUSxFQUFFLFVBQVU7U0FDckI7UUFDRDtZQUNFLEVBQUUsRUFBRSxVQUFVO1lBQ2QsS0FBSyxFQUFFLDRDQUE0QztZQUNuRCxNQUFNLEVBQUUsT0FBTztZQUNmLFFBQVEsRUFBRSxjQUFjO1NBQ3pCO0tBQ0Y7SUFDRCxJQUFJLEVBQUU7UUFDSixFQUFFLEVBQUUsRUFBRSxRQUFRLEVBQUUsSUFBSSxFQUFFLFVBQVUsRUFBRSxJQUFJLEVBQUUsZUFBZSxFQUFFO1FBQ3pELEVBQUUsRUFBRSxFQUFFLFFBQVEsRUFBRSxJQUFJLEVBQUUsY0FBYyxFQUFFLElBQUksRUFBRSxnQkFBZ0IsRUFBRTtLQUMvRDtJQUNELGNBQWMsRUFBRTtRQUNkO1lBQ0UsRUFBRSxFQUFFLE9BQU87WUFDWCxXQUFXLEVBQ1Qsa0dBQWtHO1lBQ3BHLFNBQVMsRUFBRSxzQkFBc0I7U0FDbEM7UUFDRDtZQUNFLEVBQUUsRUFBRSxPQUFPO1lBQ1gsV0FBVyxFQUNULGdFQUFnRTtZQUNsRSxTQUFTLEVBQUUsc0JBQXNCO1NBQ2xDO1FBQ0Q7WUFDRSxFQUFFLEVBQUUsT0FBTztZQUNYLFdBQVcsRUFDVCxtRkFBbUY7WUFDckYsU0FBUyxFQUFFLHNCQUFzQjtTQUNsQztLQUNGO0NBQ0YsQ0FBQztBQUVGOzs7Ozs7R0FNRztBQUNILFNBQXdCLE9BQU8sQ0FDN0IsR0FBbUIsRUFDbkIsR0FBaUM7SUFFakMsd0NBQXdDO0lBQ3hDLFVBQVUsQ0FBQyxHQUFHLEVBQUU7UUFDZCxHQUFHLENBQUMsTUFBTSxDQUFDLEdBQUcsQ0FBQyxDQUFDLElBQUksQ0FBQyxlQUFlLENBQUMsQ0FBQztJQUN4QyxDQUFDLEVBQUUsSUFBSSxDQUFDLENBQUM7QUFDWCxDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IHR5cGUgeyBOZXh0QXBpUmVxdWVzdCwgTmV4dEFwaVJlc3BvbnNlIH0gZnJvbSAnbmV4dCc7XG5cbi8vIERlZmluZSBUeXBlU2NyaXB0IGludGVyZmFjZXMgZm9yIG91ciBkYXRhIHN0cnVjdHVyZXMgZm9yIHR5cGUgc2FmZXR5LlxuaW50ZXJmYWNlIFByb2plY3Qge1xuICBpZDogc3RyaW5nO1xuICBuYW1lOiBzdHJpbmc7XG4gIGRlc2NyaXB0aW9uOiBzdHJpbmc7XG4gIHN0YXR1czogJ09uIFRyYWNrJyB8ICdBdCBSaXNrJyB8ICdPZmYgVHJhY2snO1xufVxuXG5pbnRlcmZhY2UgVGFzayB7XG4gIGlkOiBzdHJpbmc7XG4gIHRpdGxlOiBzdHJpbmc7XG4gIHN0YXR1czogJ1RvIERvJyB8ICdJbiBQcm9ncmVzcycgfCAnRG9uZSc7XG4gIGFzc2lnbmVlOiBzdHJpbmc7IC8vIFRlYW0gbWVtYmVyJ3MgbmFtZVxufVxuXG5pbnRlcmZhY2UgVGVhbU1lbWJlciB7XG4gIGlkOiBzdHJpbmc7XG4gIG5hbWU6IHN0cmluZztcbiAgcm9sZTogc3RyaW5nO1xufVxuXG5pbnRlcmZhY2UgQWN0aXZpdHkge1xuICBpZDogc3RyaW5nO1xuICBkZXNjcmlwdGlvbjogc3RyaW5nO1xuICB0aW1lc3RhbXA6IHN0cmluZztcbn1cblxuaW50ZXJmYWNlIFByb2plY3REYXRhIHtcbiAgcHJvamVjdDogUHJvamVjdDtcbiAgdGFza3M6IFRhc2tbXTtcbiAgdGVhbTogVGVhbU1lbWJlcltdO1xuICBhY3Rpdml0eVN0cmVhbTogQWN0aXZpdHlbXTtcbn1cblxuLy8gVGhpcyBpcyBvdXIgbW9jayBkYXRhYmFzZSBmb3IgcHJvamVjdCBtYW5hZ2VtZW50IGRhdGEgKGxpa2UgSmlyYSBvciBBc2FuYSkuXG5jb25zdCBtb2NrUHJvamVjdERhdGE6IFByb2plY3REYXRhID0ge1xuICBwcm9qZWN0OiB7XG4gICAgaWQ6ICdwcm9qLWFwb2xsbycsXG4gICAgbmFtZTogJ1Byb2plY3QgQXBvbGxvJyxcbiAgICBkZXNjcmlwdGlvbjpcbiAgICAgICdBIG1pc3Npb24gdG8gcmV2b2x1dGlvbml6ZSBzcGFjZSB0cmF2ZWwgdGhyb3VnaCBBSS1kcml2ZW4gbG9naXN0aWNzLicsXG4gICAgc3RhdHVzOiAnT24gVHJhY2snLFxuICB9LFxuICB0YXNrczogW1xuICAgIHtcbiAgICAgIGlkOiAndGFzay0xMDEnLFxuICAgICAgdGl0bGU6ICdEZXZlbG9wIHByb3B1bHNpb24gc3lzdGVtIHByb3RvdHlwZScsXG4gICAgICBzdGF0dXM6ICdJbiBQcm9ncmVzcycsXG4gICAgICBhc3NpZ25lZTogJ0FsZXggUmF5JyxcbiAgICB9LFxuICAgIHtcbiAgICAgIGlkOiAndGFzay0xMDInLFxuICAgICAgdGl0bGU6ICdEZXNpZ24gdXNlciBpbnRlcmZhY2UgZm9yIG1pc3Npb24gY29udHJvbCcsXG4gICAgICBzdGF0dXM6ICdJbiBQcm9ncmVzcycsXG4gICAgICBhc3NpZ25lZTogJ0Nhc2V5IEpvcmRhbicsXG4gICAgfSxcbiAgICB7XG4gICAgICBpZDogJ3Rhc2stMTAzJyxcbiAgICAgIHRpdGxlOiAnU2V0IHVwIENJL0NEIHBpcGVsaW5lIGZvciBkZXBsb3ltZW50JyxcbiAgICAgIHN0YXR1czogJ0RvbmUnLFxuICAgICAgYXNzaWduZWU6ICdEZXYgVGVhbScsXG4gICAgfSxcbiAgICB7XG4gICAgICBpZDogJ3Rhc2stMTA0JyxcbiAgICAgIHRpdGxlOiAnUGVyZm9ybSBpbml0aWFsIHJpc2sgYXNzZXNzbWVudCcsXG4gICAgICBzdGF0dXM6ICdEb25lJyxcbiAgICAgIGFzc2lnbmVlOiAnQWxleCBSYXknLFxuICAgIH0sXG4gICAge1xuICAgICAgaWQ6ICd0YXNrLTEwNScsXG4gICAgICB0aXRsZTogJ0ZpbmFsaXplIFEzIGJ1ZGdldCBhbmQgcmVzb3VyY2UgYWxsb2NhdGlvbicsXG4gICAgICBzdGF0dXM6ICdUbyBEbycsXG4gICAgICBhc3NpZ25lZTogJ0Nhc2V5IEpvcmRhbicsXG4gICAgfSxcbiAgXSxcbiAgdGVhbTogW1xuICAgIHsgaWQ6ICd0ZWFtLTEnLCBuYW1lOiAnQWxleCBSYXknLCByb2xlOiAnTGVhZCBFbmdpbmVlcicgfSxcbiAgICB7IGlkOiAndGVhbS0yJywgbmFtZTogJ0Nhc2V5IEpvcmRhbicsIHJvbGU6ICdVWC9VSSBEZXNpZ25lcicgfSxcbiAgXSxcbiAgYWN0aXZpdHlTdHJlYW06IFtcbiAgICB7XG4gICAgICBpZDogJ2FjdC0xJyxcbiAgICAgIGRlc2NyaXB0aW9uOlxuICAgICAgICAnQ2FzZXkgSm9yZGFuIHVwZGF0ZWQgdGhlIHN0YXR1cyBvZiBcIkRlc2lnbiB1c2VyIGludGVyZmFjZSBmb3IgbWlzc2lvbiBjb250cm9sXCIgdG8gXCJJbiBQcm9ncmVzc1wiLicsXG4gICAgICB0aW1lc3RhbXA6ICcyMDI0LTA4LTAxVDEwOjAwOjAwWicsXG4gICAgfSxcbiAgICB7XG4gICAgICBpZDogJ2FjdC0yJyxcbiAgICAgIGRlc2NyaXB0aW9uOlxuICAgICAgICAnQWxleCBSYXkgY29tcGxldGVkIHRoZSB0YXNrIFwiUGVyZm9ybSBpbml0aWFsIHJpc2sgYXNzZXNzbWVudFwiLicsXG4gICAgICB0aW1lc3RhbXA6ICcyMDI0LTA3LTMxVDE1OjMwOjAwWicsXG4gICAgfSxcbiAgICB7XG4gICAgICBpZDogJ2FjdC0zJyxcbiAgICAgIGRlc2NyaXB0aW9uOlxuICAgICAgICAnQSBuZXcgdGFzayBcIkZpbmFsaXplIFEzIGJ1ZGdldCBhbmQgcmVzb3VyY2UgYWxsb2NhdGlvblwiIHdhcyBhZGRlZCB0byB0aGUgcHJvamVjdC4nLFxuICAgICAgdGltZXN0YW1wOiAnMjAyNC0wNy0zMFQxMTowMDowMFonLFxuICAgIH0sXG4gIF0sXG59O1xuXG4vKipcbiAqIEFQSSBoYW5kbGVyIGZvciBmZXRjaGluZyBwcm9qZWN0IG1hbmFnZW1lbnQgZGF0YS5cbiAqIFNpbXVsYXRlcyBhIG5ldHdvcmsgcmVxdWVzdCB3aXRoIGEgMS1zZWNvbmQgZGVsYXkuXG4gKlxuICogQHBhcmFtIHtOZXh0QXBpUmVxdWVzdH0gcmVxIC0gVGhlIGluY29taW5nIEFQSSByZXF1ZXN0LlxuICogQHBhcmFtIHtOZXh0QXBpUmVzcG9uc2U8UHJvamVjdERhdGE+fSByZXMgLSBUaGUgb3V0Z29pbmcgQVBJIHJlc3BvbnNlLlxuICovXG5leHBvcnQgZGVmYXVsdCBmdW5jdGlvbiBoYW5kbGVyKFxuICByZXE6IE5leHRBcGlSZXF1ZXN0LFxuICByZXM6IE5leHRBcGlSZXNwb25zZTxQcm9qZWN0RGF0YT5cbikge1xuICAvLyBTaW11bGF0ZSBhIG5ldHdvcmsgZGVsYXkgb2YgMSBzZWNvbmQuXG4gIHNldFRpbWVvdXQoKCkgPT4ge1xuICAgIHJlcy5zdGF0dXMoMjAwKS5qc29uKG1vY2tQcm9qZWN0RGF0YSk7XG4gIH0sIDEwMDApO1xufVxuIl19