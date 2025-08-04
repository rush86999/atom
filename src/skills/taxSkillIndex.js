"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.allTaxSkills = exports.TaxSkillRegistration = exports.taxAgentTools = exports.taxSkills = void 0;
const taxExpertSkills_1 = require("./taxExpertSkills");
exports.taxSkills = [
    {
        name: 'tax_query',
        description: 'Answer tax-related questions',
        parameters: {
            type: 'object',
            properties: {
                query: {
                    type: 'string',
                    description: 'The tax-related question to answer',
                },
            },
            required: ['query'],
        },
        handler: async (params, context) => {
            const userId = context?.metadata?.userId || 'user';
            return await (0, taxExpertSkills_1.handleTaxQuery)(userId, params.query);
        },
    },
];
exports.taxAgentTools = [
    {
        name: 'tax_query_handler',
        description: 'Handle tax-related queries through natural language',
        handler: async (params) => {
            return await (0, taxExpertSkills_1.handleTaxQuery)(params.userId, params.query);
        },
    },
];
exports.TaxSkillRegistration = {
    name: 'Tax Expert',
    version: '1.0.0',
    description: 'Provides information and answers questions about taxes.',
    capabilities: [
        'Tax calculation',
        'Tax deduction information',
        'General tax advice',
    ],
    activationPrefixes: ['tax', 'taxes'],
    voiceTriggers: ['tax help'],
    desktopCommands: ['calculate my taxes', 'find tax deductions'],
    webCommands: '/tax',
    apiEndpoints: {
        web: '/api/tax',
        desktop: 'tax://',
        mobile: 'atom://tax',
    },
};
exports.allTaxSkills = [...exports.taxSkills];
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoidGF4U2tpbGxJbmRleC5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbInRheFNraWxsSW5kZXgudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7O0FBQ0EsdURBQW1EO0FBRXRDLFFBQUEsU0FBUyxHQUFzQjtJQUMxQztRQUNFLElBQUksRUFBRSxXQUFXO1FBQ2pCLFdBQVcsRUFBRSw4QkFBOEI7UUFDM0MsVUFBVSxFQUFFO1lBQ1YsSUFBSSxFQUFFLFFBQVE7WUFDZCxVQUFVLEVBQUU7Z0JBQ1YsS0FBSyxFQUFFO29CQUNMLElBQUksRUFBRSxRQUFRO29CQUNkLFdBQVcsRUFBRSxvQ0FBb0M7aUJBQ2xEO2FBQ0Y7WUFDRCxRQUFRLEVBQUUsQ0FBQyxPQUFPLENBQUM7U0FDcEI7UUFDRCxPQUFPLEVBQUUsS0FBSyxFQUFFLE1BQVcsRUFBRSxPQUFZLEVBQUUsRUFBRTtZQUMzQyxNQUFNLE1BQU0sR0FBRyxPQUFPLEVBQUUsUUFBUSxFQUFFLE1BQU0sSUFBSSxNQUFNLENBQUM7WUFDbkQsT0FBTyxNQUFNLElBQUEsZ0NBQWMsRUFBQyxNQUFNLEVBQUUsTUFBTSxDQUFDLEtBQUssQ0FBQyxDQUFDO1FBQ3BELENBQUM7S0FDRjtDQUNGLENBQUM7QUFFVyxRQUFBLGFBQWEsR0FBeUI7SUFDakQ7UUFDRSxJQUFJLEVBQUUsbUJBQW1CO1FBQ3pCLFdBQVcsRUFBRSxxREFBcUQ7UUFDbEUsT0FBTyxFQUFFLEtBQUssRUFBRSxNQUFXLEVBQUUsRUFBRTtZQUM3QixPQUFPLE1BQU0sSUFBQSxnQ0FBYyxFQUFDLE1BQU0sQ0FBQyxNQUFNLEVBQUUsTUFBTSxDQUFDLEtBQUssQ0FBQyxDQUFDO1FBQzNELENBQUM7S0FDRjtDQUNGLENBQUM7QUFFVyxRQUFBLG9CQUFvQixHQUFHO0lBQ2xDLElBQUksRUFBRSxZQUFZO0lBQ2xCLE9BQU8sRUFBRSxPQUFPO0lBQ2hCLFdBQVcsRUFBRSx5REFBeUQ7SUFDdEUsWUFBWSxFQUFFO1FBQ1osaUJBQWlCO1FBQ2pCLDJCQUEyQjtRQUMzQixvQkFBb0I7S0FDckI7SUFDRCxrQkFBa0IsRUFBRSxDQUFDLEtBQUssRUFBRSxPQUFPLENBQUM7SUFDcEMsYUFBYSxFQUFFLENBQUMsVUFBVSxDQUFDO0lBQzNCLGVBQWUsRUFBRSxDQUFDLG9CQUFvQixFQUFFLHFCQUFxQixDQUFDO0lBQzlELFdBQVcsRUFBRSxNQUFNO0lBQ25CLFlBQVksRUFBRTtRQUNaLEdBQUcsRUFBRSxVQUFVO1FBQ2YsT0FBTyxFQUFFLFFBQVE7UUFDakIsTUFBTSxFQUFFLFlBQVk7S0FDckI7Q0FDRixDQUFDO0FBRVcsUUFBQSxZQUFZLEdBQUcsQ0FBQyxHQUFHLGlCQUFTLENBQUMsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7IFNraWxsRGVmaW5pdGlvbiwgVG9vbEltcGxlbWVudGF0aW9uIH0gZnJvbSAnLi4vdHlwZXMnO1xuaW1wb3J0IHsgaGFuZGxlVGF4UXVlcnkgfSBmcm9tICcuL3RheEV4cGVydFNraWxscyc7XG5cbmV4cG9ydCBjb25zdCB0YXhTa2lsbHM6IFNraWxsRGVmaW5pdGlvbltdID0gW1xuICB7XG4gICAgbmFtZTogJ3RheF9xdWVyeScsXG4gICAgZGVzY3JpcHRpb246ICdBbnN3ZXIgdGF4LXJlbGF0ZWQgcXVlc3Rpb25zJyxcbiAgICBwYXJhbWV0ZXJzOiB7XG4gICAgICB0eXBlOiAnb2JqZWN0JyxcbiAgICAgIHByb3BlcnRpZXM6IHtcbiAgICAgICAgcXVlcnk6IHtcbiAgICAgICAgICB0eXBlOiAnc3RyaW5nJyxcbiAgICAgICAgICBkZXNjcmlwdGlvbjogJ1RoZSB0YXgtcmVsYXRlZCBxdWVzdGlvbiB0byBhbnN3ZXInLFxuICAgICAgICB9LFxuICAgICAgfSxcbiAgICAgIHJlcXVpcmVkOiBbJ3F1ZXJ5J10sXG4gICAgfSxcbiAgICBoYW5kbGVyOiBhc3luYyAocGFyYW1zOiBhbnksIGNvbnRleHQ6IGFueSkgPT4ge1xuICAgICAgY29uc3QgdXNlcklkID0gY29udGV4dD8ubWV0YWRhdGE/LnVzZXJJZCB8fCAndXNlcic7XG4gICAgICByZXR1cm4gYXdhaXQgaGFuZGxlVGF4UXVlcnkodXNlcklkLCBwYXJhbXMucXVlcnkpO1xuICAgIH0sXG4gIH0sXG5dO1xuXG5leHBvcnQgY29uc3QgdGF4QWdlbnRUb29sczogVG9vbEltcGxlbWVudGF0aW9uW10gPSBbXG4gIHtcbiAgICBuYW1lOiAndGF4X3F1ZXJ5X2hhbmRsZXInLFxuICAgIGRlc2NyaXB0aW9uOiAnSGFuZGxlIHRheC1yZWxhdGVkIHF1ZXJpZXMgdGhyb3VnaCBuYXR1cmFsIGxhbmd1YWdlJyxcbiAgICBoYW5kbGVyOiBhc3luYyAocGFyYW1zOiBhbnkpID0+IHtcbiAgICAgIHJldHVybiBhd2FpdCBoYW5kbGVUYXhRdWVyeShwYXJhbXMudXNlcklkLCBwYXJhbXMucXVlcnkpO1xuICAgIH0sXG4gIH0sXG5dO1xuXG5leHBvcnQgY29uc3QgVGF4U2tpbGxSZWdpc3RyYXRpb24gPSB7XG4gIG5hbWU6ICdUYXggRXhwZXJ0JyxcbiAgdmVyc2lvbjogJzEuMC4wJyxcbiAgZGVzY3JpcHRpb246ICdQcm92aWRlcyBpbmZvcm1hdGlvbiBhbmQgYW5zd2VycyBxdWVzdGlvbnMgYWJvdXQgdGF4ZXMuJyxcbiAgY2FwYWJpbGl0aWVzOiBbXG4gICAgJ1RheCBjYWxjdWxhdGlvbicsXG4gICAgJ1RheCBkZWR1Y3Rpb24gaW5mb3JtYXRpb24nLFxuICAgICdHZW5lcmFsIHRheCBhZHZpY2UnLFxuICBdLFxuICBhY3RpdmF0aW9uUHJlZml4ZXM6IFsndGF4JywgJ3RheGVzJ10sXG4gIHZvaWNlVHJpZ2dlcnM6IFsndGF4IGhlbHAnXSxcbiAgZGVza3RvcENvbW1hbmRzOiBbJ2NhbGN1bGF0ZSBteSB0YXhlcycsICdmaW5kIHRheCBkZWR1Y3Rpb25zJ10sXG4gIHdlYkNvbW1hbmRzOiAnL3RheCcsXG4gIGFwaUVuZHBvaW50czoge1xuICAgIHdlYjogJy9hcGkvdGF4JyxcbiAgICBkZXNrdG9wOiAndGF4Oi8vJyxcbiAgICBtb2JpbGU6ICdhdG9tOi8vdGF4JyxcbiAgfSxcbn07XG5cbmV4cG9ydCBjb25zdCBhbGxUYXhTa2lsbHMgPSBbLi4udGF4U2tpbGxzXTtcbiJdfQ==