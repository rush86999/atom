"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const Invite = {
    title: 'Invite schema',
    version: 0,
    description: 'describes a Invite',
    primaryKey: 'id',
    type: 'object',
    properties: {
        id: {
            type: 'string',
        },
        userId: {
            type: 'string',
        },
        emails: {
            type: ['array', 'null'],
            uniqueItems: true,
            items: {
                type: 'string',
            },
        },
        phoneNumbers: {
            type: ['array', 'null'],
            uniqueItems: true,
            items: {
                type: 'string',
            },
        },
        imAddresses: {
            type: ['array', 'null'],
            uniqueItems: true,
            items: {
                type: 'string',
            },
        },
        categories: {
            type: ['array', 'null'],
            uniqueItems: true,
            items: {
                type: 'string',
            },
        },
        availableSlots: {
            type: ['array', 'null'],
            uniqueItems: true,
            items: {
                type: 'string',
            },
        },
        name: {
            type: ['string', 'null'],
        },
        eventId: {
            type: 'string',
        },
        emailId: {
            type: 'string',
        },
        contactId: {
            type: ['string', 'null'],
        },
        phoneId: {
            type: ['string', 'null'],
        },
        updatedAt: {
            type: 'string',
        },
        createdDate: {
            type: 'string',
        },
    },
    required: ['id', 'userId', 'emailId', 'updatedAt', 'createdDate'],
    indexes: ['userId', 'emailId'],
};
exports.default = Invite;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiSW52aXRlLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsiSW52aXRlLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiI7O0FBQUEsTUFBTSxNQUFNLEdBQUc7SUFDYixLQUFLLEVBQUUsZUFBZTtJQUN0QixPQUFPLEVBQUUsQ0FBQztJQUNWLFdBQVcsRUFBRSxvQkFBb0I7SUFDakMsVUFBVSxFQUFFLElBQUk7SUFDaEIsSUFBSSxFQUFFLFFBQVE7SUFDZCxVQUFVLEVBQUU7UUFDVixFQUFFLEVBQUU7WUFDRixJQUFJLEVBQUUsUUFBUTtTQUNmO1FBQ0QsTUFBTSxFQUFFO1lBQ04sSUFBSSxFQUFFLFFBQVE7U0FDZjtRQUNELE1BQU0sRUFBRTtZQUNOLElBQUksRUFBRSxDQUFDLE9BQU8sRUFBRSxNQUFNLENBQUM7WUFDdkIsV0FBVyxFQUFFLElBQUk7WUFDakIsS0FBSyxFQUFFO2dCQUNMLElBQUksRUFBRSxRQUFRO2FBQ2Y7U0FDRjtRQUNELFlBQVksRUFBRTtZQUNaLElBQUksRUFBRSxDQUFDLE9BQU8sRUFBRSxNQUFNLENBQUM7WUFDdkIsV0FBVyxFQUFFLElBQUk7WUFDakIsS0FBSyxFQUFFO2dCQUNMLElBQUksRUFBRSxRQUFRO2FBQ2Y7U0FDRjtRQUNELFdBQVcsRUFBRTtZQUNYLElBQUksRUFBRSxDQUFDLE9BQU8sRUFBRSxNQUFNLENBQUM7WUFDdkIsV0FBVyxFQUFFLElBQUk7WUFDakIsS0FBSyxFQUFFO2dCQUNMLElBQUksRUFBRSxRQUFRO2FBQ2Y7U0FDRjtRQUNELFVBQVUsRUFBRTtZQUNWLElBQUksRUFBRSxDQUFDLE9BQU8sRUFBRSxNQUFNLENBQUM7WUFDdkIsV0FBVyxFQUFFLElBQUk7WUFDakIsS0FBSyxFQUFFO2dCQUNMLElBQUksRUFBRSxRQUFRO2FBQ2Y7U0FDRjtRQUNELGNBQWMsRUFBRTtZQUNkLElBQUksRUFBRSxDQUFDLE9BQU8sRUFBRSxNQUFNLENBQUM7WUFDdkIsV0FBVyxFQUFFLElBQUk7WUFDakIsS0FBSyxFQUFFO2dCQUNMLElBQUksRUFBRSxRQUFRO2FBQ2Y7U0FDRjtRQUNELElBQUksRUFBRTtZQUNKLElBQUksRUFBRSxDQUFDLFFBQVEsRUFBRSxNQUFNLENBQUM7U0FDekI7UUFDRCxPQUFPLEVBQUU7WUFDUCxJQUFJLEVBQUUsUUFBUTtTQUNmO1FBQ0QsT0FBTyxFQUFFO1lBQ1AsSUFBSSxFQUFFLFFBQVE7U0FDZjtRQUNELFNBQVMsRUFBRTtZQUNULElBQUksRUFBRSxDQUFDLFFBQVEsRUFBRSxNQUFNLENBQUM7U0FDekI7UUFDRCxPQUFPLEVBQUU7WUFDUCxJQUFJLEVBQUUsQ0FBQyxRQUFRLEVBQUUsTUFBTSxDQUFDO1NBQ3pCO1FBQ0QsU0FBUyxFQUFFO1lBQ1QsSUFBSSxFQUFFLFFBQVE7U0FDZjtRQUNELFdBQVcsRUFBRTtZQUNYLElBQUksRUFBRSxRQUFRO1NBQ2Y7S0FDRjtJQUNELFFBQVEsRUFBRSxDQUFDLElBQUksRUFBRSxRQUFRLEVBQUUsU0FBUyxFQUFFLFdBQVcsRUFBRSxhQUFhLENBQUM7SUFDakUsT0FBTyxFQUFFLENBQUMsUUFBUSxFQUFFLFNBQVMsQ0FBQztDQUMvQixDQUFDO0FBRUYsa0JBQWUsTUFBTSxDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiY29uc3QgSW52aXRlID0ge1xuICB0aXRsZTogJ0ludml0ZSBzY2hlbWEnLFxuICB2ZXJzaW9uOiAwLFxuICBkZXNjcmlwdGlvbjogJ2Rlc2NyaWJlcyBhIEludml0ZScsXG4gIHByaW1hcnlLZXk6ICdpZCcsXG4gIHR5cGU6ICdvYmplY3QnLFxuICBwcm9wZXJ0aWVzOiB7XG4gICAgaWQ6IHtcbiAgICAgIHR5cGU6ICdzdHJpbmcnLFxuICAgIH0sXG4gICAgdXNlcklkOiB7XG4gICAgICB0eXBlOiAnc3RyaW5nJyxcbiAgICB9LFxuICAgIGVtYWlsczoge1xuICAgICAgdHlwZTogWydhcnJheScsICdudWxsJ10sXG4gICAgICB1bmlxdWVJdGVtczogdHJ1ZSxcbiAgICAgIGl0ZW1zOiB7XG4gICAgICAgIHR5cGU6ICdzdHJpbmcnLFxuICAgICAgfSxcbiAgICB9LFxuICAgIHBob25lTnVtYmVyczoge1xuICAgICAgdHlwZTogWydhcnJheScsICdudWxsJ10sXG4gICAgICB1bmlxdWVJdGVtczogdHJ1ZSxcbiAgICAgIGl0ZW1zOiB7XG4gICAgICAgIHR5cGU6ICdzdHJpbmcnLFxuICAgICAgfSxcbiAgICB9LFxuICAgIGltQWRkcmVzc2VzOiB7XG4gICAgICB0eXBlOiBbJ2FycmF5JywgJ251bGwnXSxcbiAgICAgIHVuaXF1ZUl0ZW1zOiB0cnVlLFxuICAgICAgaXRlbXM6IHtcbiAgICAgICAgdHlwZTogJ3N0cmluZycsXG4gICAgICB9LFxuICAgIH0sXG4gICAgY2F0ZWdvcmllczoge1xuICAgICAgdHlwZTogWydhcnJheScsICdudWxsJ10sXG4gICAgICB1bmlxdWVJdGVtczogdHJ1ZSxcbiAgICAgIGl0ZW1zOiB7XG4gICAgICAgIHR5cGU6ICdzdHJpbmcnLFxuICAgICAgfSxcbiAgICB9LFxuICAgIGF2YWlsYWJsZVNsb3RzOiB7XG4gICAgICB0eXBlOiBbJ2FycmF5JywgJ251bGwnXSxcbiAgICAgIHVuaXF1ZUl0ZW1zOiB0cnVlLFxuICAgICAgaXRlbXM6IHtcbiAgICAgICAgdHlwZTogJ3N0cmluZycsXG4gICAgICB9LFxuICAgIH0sXG4gICAgbmFtZToge1xuICAgICAgdHlwZTogWydzdHJpbmcnLCAnbnVsbCddLFxuICAgIH0sXG4gICAgZXZlbnRJZDoge1xuICAgICAgdHlwZTogJ3N0cmluZycsXG4gICAgfSxcbiAgICBlbWFpbElkOiB7XG4gICAgICB0eXBlOiAnc3RyaW5nJyxcbiAgICB9LFxuICAgIGNvbnRhY3RJZDoge1xuICAgICAgdHlwZTogWydzdHJpbmcnLCAnbnVsbCddLFxuICAgIH0sXG4gICAgcGhvbmVJZDoge1xuICAgICAgdHlwZTogWydzdHJpbmcnLCAnbnVsbCddLFxuICAgIH0sXG4gICAgdXBkYXRlZEF0OiB7XG4gICAgICB0eXBlOiAnc3RyaW5nJyxcbiAgICB9LFxuICAgIGNyZWF0ZWREYXRlOiB7XG4gICAgICB0eXBlOiAnc3RyaW5nJyxcbiAgICB9LFxuICB9LFxuICByZXF1aXJlZDogWydpZCcsICd1c2VySWQnLCAnZW1haWxJZCcsICd1cGRhdGVkQXQnLCAnY3JlYXRlZERhdGUnXSxcbiAgaW5kZXhlczogWyd1c2VySWQnLCAnZW1haWxJZCddLFxufTtcblxuZXhwb3J0IGRlZmF1bHQgSW52aXRlO1xuIl19