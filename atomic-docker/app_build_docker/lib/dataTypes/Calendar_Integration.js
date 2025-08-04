"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const Calendar_Integration = {
    title: 'Calendar_Integration schema',
    version: 0,
    description: 'describes a Calendar_Integration',
    primaryKey: 'id',
    type: 'object',
    properties: {
        id: {
            type: 'string',
        },
        token: {
            type: ['string', 'null'],
        },
        refreshToken: {
            type: ['string', 'null'],
        },
        resource: {
            type: ['string', 'null'],
        },
        name: {
            type: ['string', 'null'],
        },
        enabled: {
            type: 'boolean',
        },
        syncEnabled: {
            type: 'boolean',
        },
        expiresAt: {
            type: ['string', 'null'],
        },
        pageToken: {
            type: ['string', 'null'],
        },
        syncToken: {
            type: ['string', 'null'],
        },
        appId: {
            type: ['string', 'null'],
        },
        appEmail: {
            type: ['string', 'null'],
        },
        appAccountId: {
            type: ['string', 'null'],
        },
        contactName: {
            type: ['string', 'null'],
        },
        contactEmail: {
            type: ['string', 'null'],
        },
        colors: {
            type: ['array', 'null'],
            uniqueItems: true,
            items: {
                type: 'object',
                properties: {
                    id: {
                        type: 'string',
                    },
                    background: {
                        type: 'string',
                    },
                    foreground: {
                        type: 'string',
                    },
                    itemType: {
                        type: 'string',
                    },
                },
            },
        },
        updatedAt: {
            type: 'string',
        },
        createdDate: {
            type: 'string',
        },
        userId: {
            type: 'string',
        },
    },
    required: [
        'resource',
        'name',
        'enabled',
        'updatedAt',
        'createdDate',
        'userId',
    ],
    indexes: ['userId'],
};
exports.default = Calendar_Integration;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiQ2FsZW5kYXJfSW50ZWdyYXRpb24uanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJDYWxlbmRhcl9JbnRlZ3JhdGlvbi50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOztBQUFBLE1BQU0sb0JBQW9CLEdBQUc7SUFDM0IsS0FBSyxFQUFFLDZCQUE2QjtJQUNwQyxPQUFPLEVBQUUsQ0FBQztJQUNWLFdBQVcsRUFBRSxrQ0FBa0M7SUFDL0MsVUFBVSxFQUFFLElBQUk7SUFDaEIsSUFBSSxFQUFFLFFBQVE7SUFDZCxVQUFVLEVBQUU7UUFDVixFQUFFLEVBQUU7WUFDRixJQUFJLEVBQUUsUUFBUTtTQUNmO1FBQ0QsS0FBSyxFQUFFO1lBQ0wsSUFBSSxFQUFFLENBQUMsUUFBUSxFQUFFLE1BQU0sQ0FBQztTQUN6QjtRQUNELFlBQVksRUFBRTtZQUNaLElBQUksRUFBRSxDQUFDLFFBQVEsRUFBRSxNQUFNLENBQUM7U0FDekI7UUFDRCxRQUFRLEVBQUU7WUFDUixJQUFJLEVBQUUsQ0FBQyxRQUFRLEVBQUUsTUFBTSxDQUFDO1NBQ3pCO1FBQ0QsSUFBSSxFQUFFO1lBQ0osSUFBSSxFQUFFLENBQUMsUUFBUSxFQUFFLE1BQU0sQ0FBQztTQUN6QjtRQUNELE9BQU8sRUFBRTtZQUNQLElBQUksRUFBRSxTQUFTO1NBQ2hCO1FBQ0QsV0FBVyxFQUFFO1lBQ1gsSUFBSSxFQUFFLFNBQVM7U0FDaEI7UUFDRCxTQUFTLEVBQUU7WUFDVCxJQUFJLEVBQUUsQ0FBQyxRQUFRLEVBQUUsTUFBTSxDQUFDO1NBQ3pCO1FBQ0QsU0FBUyxFQUFFO1lBQ1QsSUFBSSxFQUFFLENBQUMsUUFBUSxFQUFFLE1BQU0sQ0FBQztTQUN6QjtRQUNELFNBQVMsRUFBRTtZQUNULElBQUksRUFBRSxDQUFDLFFBQVEsRUFBRSxNQUFNLENBQUM7U0FDekI7UUFDRCxLQUFLLEVBQUU7WUFDTCxJQUFJLEVBQUUsQ0FBQyxRQUFRLEVBQUUsTUFBTSxDQUFDO1NBQ3pCO1FBQ0QsUUFBUSxFQUFFO1lBQ1IsSUFBSSxFQUFFLENBQUMsUUFBUSxFQUFFLE1BQU0sQ0FBQztTQUN6QjtRQUNELFlBQVksRUFBRTtZQUNaLElBQUksRUFBRSxDQUFDLFFBQVEsRUFBRSxNQUFNLENBQUM7U0FDekI7UUFDRCxXQUFXLEVBQUU7WUFDWCxJQUFJLEVBQUUsQ0FBQyxRQUFRLEVBQUUsTUFBTSxDQUFDO1NBQ3pCO1FBQ0QsWUFBWSxFQUFFO1lBQ1osSUFBSSxFQUFFLENBQUMsUUFBUSxFQUFFLE1BQU0sQ0FBQztTQUN6QjtRQUNELE1BQU0sRUFBRTtZQUNOLElBQUksRUFBRSxDQUFDLE9BQU8sRUFBRSxNQUFNLENBQUM7WUFDdkIsV0FBVyxFQUFFLElBQUk7WUFDakIsS0FBSyxFQUFFO2dCQUNMLElBQUksRUFBRSxRQUFRO2dCQUNkLFVBQVUsRUFBRTtvQkFDVixFQUFFLEVBQUU7d0JBQ0YsSUFBSSxFQUFFLFFBQVE7cUJBQ2Y7b0JBQ0QsVUFBVSxFQUFFO3dCQUNWLElBQUksRUFBRSxRQUFRO3FCQUNmO29CQUNELFVBQVUsRUFBRTt3QkFDVixJQUFJLEVBQUUsUUFBUTtxQkFDZjtvQkFDRCxRQUFRLEVBQUU7d0JBQ1IsSUFBSSxFQUFFLFFBQVE7cUJBQ2Y7aUJBQ0Y7YUFDRjtTQUNGO1FBQ0QsU0FBUyxFQUFFO1lBQ1QsSUFBSSxFQUFFLFFBQVE7U0FDZjtRQUNELFdBQVcsRUFBRTtZQUNYLElBQUksRUFBRSxRQUFRO1NBQ2Y7UUFDRCxNQUFNLEVBQUU7WUFDTixJQUFJLEVBQUUsUUFBUTtTQUNmO0tBQ0Y7SUFDRCxRQUFRLEVBQUU7UUFDUixVQUFVO1FBQ1YsTUFBTTtRQUNOLFNBQVM7UUFDVCxXQUFXO1FBQ1gsYUFBYTtRQUNiLFFBQVE7S0FDVDtJQUNELE9BQU8sRUFBRSxDQUFDLFFBQVEsQ0FBQztDQUNwQixDQUFDO0FBRUYsa0JBQWUsb0JBQW9CLENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJjb25zdCBDYWxlbmRhcl9JbnRlZ3JhdGlvbiA9IHtcbiAgdGl0bGU6ICdDYWxlbmRhcl9JbnRlZ3JhdGlvbiBzY2hlbWEnLFxuICB2ZXJzaW9uOiAwLFxuICBkZXNjcmlwdGlvbjogJ2Rlc2NyaWJlcyBhIENhbGVuZGFyX0ludGVncmF0aW9uJyxcbiAgcHJpbWFyeUtleTogJ2lkJyxcbiAgdHlwZTogJ29iamVjdCcsXG4gIHByb3BlcnRpZXM6IHtcbiAgICBpZDoge1xuICAgICAgdHlwZTogJ3N0cmluZycsXG4gICAgfSxcbiAgICB0b2tlbjoge1xuICAgICAgdHlwZTogWydzdHJpbmcnLCAnbnVsbCddLFxuICAgIH0sXG4gICAgcmVmcmVzaFRva2VuOiB7XG4gICAgICB0eXBlOiBbJ3N0cmluZycsICdudWxsJ10sXG4gICAgfSxcbiAgICByZXNvdXJjZToge1xuICAgICAgdHlwZTogWydzdHJpbmcnLCAnbnVsbCddLFxuICAgIH0sXG4gICAgbmFtZToge1xuICAgICAgdHlwZTogWydzdHJpbmcnLCAnbnVsbCddLFxuICAgIH0sXG4gICAgZW5hYmxlZDoge1xuICAgICAgdHlwZTogJ2Jvb2xlYW4nLFxuICAgIH0sXG4gICAgc3luY0VuYWJsZWQ6IHtcbiAgICAgIHR5cGU6ICdib29sZWFuJyxcbiAgICB9LFxuICAgIGV4cGlyZXNBdDoge1xuICAgICAgdHlwZTogWydzdHJpbmcnLCAnbnVsbCddLFxuICAgIH0sXG4gICAgcGFnZVRva2VuOiB7XG4gICAgICB0eXBlOiBbJ3N0cmluZycsICdudWxsJ10sXG4gICAgfSxcbiAgICBzeW5jVG9rZW46IHtcbiAgICAgIHR5cGU6IFsnc3RyaW5nJywgJ251bGwnXSxcbiAgICB9LFxuICAgIGFwcElkOiB7XG4gICAgICB0eXBlOiBbJ3N0cmluZycsICdudWxsJ10sXG4gICAgfSxcbiAgICBhcHBFbWFpbDoge1xuICAgICAgdHlwZTogWydzdHJpbmcnLCAnbnVsbCddLFxuICAgIH0sXG4gICAgYXBwQWNjb3VudElkOiB7XG4gICAgICB0eXBlOiBbJ3N0cmluZycsICdudWxsJ10sXG4gICAgfSxcbiAgICBjb250YWN0TmFtZToge1xuICAgICAgdHlwZTogWydzdHJpbmcnLCAnbnVsbCddLFxuICAgIH0sXG4gICAgY29udGFjdEVtYWlsOiB7XG4gICAgICB0eXBlOiBbJ3N0cmluZycsICdudWxsJ10sXG4gICAgfSxcbiAgICBjb2xvcnM6IHtcbiAgICAgIHR5cGU6IFsnYXJyYXknLCAnbnVsbCddLFxuICAgICAgdW5pcXVlSXRlbXM6IHRydWUsXG4gICAgICBpdGVtczoge1xuICAgICAgICB0eXBlOiAnb2JqZWN0JyxcbiAgICAgICAgcHJvcGVydGllczoge1xuICAgICAgICAgIGlkOiB7XG4gICAgICAgICAgICB0eXBlOiAnc3RyaW5nJyxcbiAgICAgICAgICB9LFxuICAgICAgICAgIGJhY2tncm91bmQ6IHtcbiAgICAgICAgICAgIHR5cGU6ICdzdHJpbmcnLFxuICAgICAgICAgIH0sXG4gICAgICAgICAgZm9yZWdyb3VuZDoge1xuICAgICAgICAgICAgdHlwZTogJ3N0cmluZycsXG4gICAgICAgICAgfSxcbiAgICAgICAgICBpdGVtVHlwZToge1xuICAgICAgICAgICAgdHlwZTogJ3N0cmluZycsXG4gICAgICAgICAgfSxcbiAgICAgICAgfSxcbiAgICAgIH0sXG4gICAgfSxcbiAgICB1cGRhdGVkQXQ6IHtcbiAgICAgIHR5cGU6ICdzdHJpbmcnLFxuICAgIH0sXG4gICAgY3JlYXRlZERhdGU6IHtcbiAgICAgIHR5cGU6ICdzdHJpbmcnLFxuICAgIH0sXG4gICAgdXNlcklkOiB7XG4gICAgICB0eXBlOiAnc3RyaW5nJyxcbiAgICB9LFxuICB9LFxuICByZXF1aXJlZDogW1xuICAgICdyZXNvdXJjZScsXG4gICAgJ25hbWUnLFxuICAgICdlbmFibGVkJyxcbiAgICAndXBkYXRlZEF0JyxcbiAgICAnY3JlYXRlZERhdGUnLFxuICAgICd1c2VySWQnLFxuICBdLFxuICBpbmRleGVzOiBbJ3VzZXJJZCddLFxufTtcblxuZXhwb3J0IGRlZmF1bHQgQ2FsZW5kYXJfSW50ZWdyYXRpb247XG4iXX0=