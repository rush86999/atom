"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const Attendee = {
    title: 'Attendee schema',
    version: 0,
    description: 'describes a Attendee',
    primaryKey: 'id',
    type: 'object',
    properties: {
        id: {
            type: 'string',
        },
        userId: {
            type: 'string',
        },
        name: {
            type: ['string', 'null'],
        },
        contactId: {
            type: ['string', 'null'],
        },
        emails: {
            type: ['array', 'null'],
            uniqueItems: true,
            items: {
                type: 'object',
                properties: {
                    primary: {
                        type: 'boolean',
                    },
                    value: {
                        type: 'string',
                    },
                    type: {
                        type: 'string',
                    },
                    displayName: {
                        type: 'string',
                    },
                },
            },
        },
        phoneNumbers: {
            type: ['array', 'null'],
            uniqueItems: true,
            items: {
                type: 'object',
                properties: {
                    primary: {
                        type: 'boolean',
                    },
                    value: {
                        type: 'string',
                    },
                    type: {
                        type: 'string',
                    },
                },
            },
        },
        imAddresses: {
            type: ['array', 'null'],
            uniqueItems: true,
            items: {
                type: 'object',
                properties: {
                    primary: {
                        type: 'boolean',
                    },
                    username: {
                        type: 'string',
                    },
                    service: {
                        type: 'string',
                    },
                    type: {
                        type: 'string',
                    },
                },
            },
        },
        eventId: {
            type: 'string',
        },
        additionalGuests: {
            type: 'number',
        },
        comment: {
            type: ['string', 'null'],
        },
        responseStatus: {
            type: ['string', 'null'],
        },
        optional: {
            type: 'boolean',
        },
        resource: {
            type: 'boolean',
        },
        updatedAt: {
            type: 'string',
        },
        createdDate: {
            type: 'string',
        },
    },
    required: ['id', 'name', 'userId', 'eventId', 'updatedAt', 'createdDate'],
    indexes: ['userId', 'eventId'],
};
exports.default = Attendee;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiQXR0ZW5kZWUuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJBdHRlbmRlZS50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOztBQUFBLE1BQU0sUUFBUSxHQUFHO0lBQ2YsS0FBSyxFQUFFLGlCQUFpQjtJQUN4QixPQUFPLEVBQUUsQ0FBQztJQUNWLFdBQVcsRUFBRSxzQkFBc0I7SUFDbkMsVUFBVSxFQUFFLElBQUk7SUFDaEIsSUFBSSxFQUFFLFFBQVE7SUFDZCxVQUFVLEVBQUU7UUFDVixFQUFFLEVBQUU7WUFDRixJQUFJLEVBQUUsUUFBUTtTQUNmO1FBQ0QsTUFBTSxFQUFFO1lBQ04sSUFBSSxFQUFFLFFBQVE7U0FDZjtRQUNELElBQUksRUFBRTtZQUNKLElBQUksRUFBRSxDQUFDLFFBQVEsRUFBRSxNQUFNLENBQUM7U0FDekI7UUFDRCxTQUFTLEVBQUU7WUFDVCxJQUFJLEVBQUUsQ0FBQyxRQUFRLEVBQUUsTUFBTSxDQUFDO1NBQ3pCO1FBQ0QsTUFBTSxFQUFFO1lBQ04sSUFBSSxFQUFFLENBQUMsT0FBTyxFQUFFLE1BQU0sQ0FBQztZQUN2QixXQUFXLEVBQUUsSUFBSTtZQUNqQixLQUFLLEVBQUU7Z0JBQ0wsSUFBSSxFQUFFLFFBQVE7Z0JBQ2QsVUFBVSxFQUFFO29CQUNWLE9BQU8sRUFBRTt3QkFDUCxJQUFJLEVBQUUsU0FBUztxQkFDaEI7b0JBQ0QsS0FBSyxFQUFFO3dCQUNMLElBQUksRUFBRSxRQUFRO3FCQUNmO29CQUNELElBQUksRUFBRTt3QkFDSixJQUFJLEVBQUUsUUFBUTtxQkFDZjtvQkFDRCxXQUFXLEVBQUU7d0JBQ1gsSUFBSSxFQUFFLFFBQVE7cUJBQ2Y7aUJBQ0Y7YUFDRjtTQUNGO1FBQ0QsWUFBWSxFQUFFO1lBQ1osSUFBSSxFQUFFLENBQUMsT0FBTyxFQUFFLE1BQU0sQ0FBQztZQUN2QixXQUFXLEVBQUUsSUFBSTtZQUNqQixLQUFLLEVBQUU7Z0JBQ0wsSUFBSSxFQUFFLFFBQVE7Z0JBQ2QsVUFBVSxFQUFFO29CQUNWLE9BQU8sRUFBRTt3QkFDUCxJQUFJLEVBQUUsU0FBUztxQkFDaEI7b0JBQ0QsS0FBSyxFQUFFO3dCQUNMLElBQUksRUFBRSxRQUFRO3FCQUNmO29CQUNELElBQUksRUFBRTt3QkFDSixJQUFJLEVBQUUsUUFBUTtxQkFDZjtpQkFDRjthQUNGO1NBQ0Y7UUFDRCxXQUFXLEVBQUU7WUFDWCxJQUFJLEVBQUUsQ0FBQyxPQUFPLEVBQUUsTUFBTSxDQUFDO1lBQ3ZCLFdBQVcsRUFBRSxJQUFJO1lBQ2pCLEtBQUssRUFBRTtnQkFDTCxJQUFJLEVBQUUsUUFBUTtnQkFDZCxVQUFVLEVBQUU7b0JBQ1YsT0FBTyxFQUFFO3dCQUNQLElBQUksRUFBRSxTQUFTO3FCQUNoQjtvQkFDRCxRQUFRLEVBQUU7d0JBQ1IsSUFBSSxFQUFFLFFBQVE7cUJBQ2Y7b0JBQ0QsT0FBTyxFQUFFO3dCQUNQLElBQUksRUFBRSxRQUFRO3FCQUNmO29CQUNELElBQUksRUFBRTt3QkFDSixJQUFJLEVBQUUsUUFBUTtxQkFDZjtpQkFDRjthQUNGO1NBQ0Y7UUFDRCxPQUFPLEVBQUU7WUFDUCxJQUFJLEVBQUUsUUFBUTtTQUNmO1FBQ0QsZ0JBQWdCLEVBQUU7WUFDaEIsSUFBSSxFQUFFLFFBQVE7U0FDZjtRQUNELE9BQU8sRUFBRTtZQUNQLElBQUksRUFBRSxDQUFDLFFBQVEsRUFBRSxNQUFNLENBQUM7U0FDekI7UUFDRCxjQUFjLEVBQUU7WUFDZCxJQUFJLEVBQUUsQ0FBQyxRQUFRLEVBQUUsTUFBTSxDQUFDO1NBQ3pCO1FBQ0QsUUFBUSxFQUFFO1lBQ1IsSUFBSSxFQUFFLFNBQVM7U0FDaEI7UUFDRCxRQUFRLEVBQUU7WUFDUixJQUFJLEVBQUUsU0FBUztTQUNoQjtRQUNELFNBQVMsRUFBRTtZQUNULElBQUksRUFBRSxRQUFRO1NBQ2Y7UUFDRCxXQUFXLEVBQUU7WUFDWCxJQUFJLEVBQUUsUUFBUTtTQUNmO0tBQ0Y7SUFDRCxRQUFRLEVBQUUsQ0FBQyxJQUFJLEVBQUUsTUFBTSxFQUFFLFFBQVEsRUFBRSxTQUFTLEVBQUUsV0FBVyxFQUFFLGFBQWEsQ0FBQztJQUN6RSxPQUFPLEVBQUUsQ0FBQyxRQUFRLEVBQUUsU0FBUyxDQUFDO0NBQy9CLENBQUM7QUFFRixrQkFBZSxRQUFRLENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJjb25zdCBBdHRlbmRlZSA9IHtcbiAgdGl0bGU6ICdBdHRlbmRlZSBzY2hlbWEnLFxuICB2ZXJzaW9uOiAwLFxuICBkZXNjcmlwdGlvbjogJ2Rlc2NyaWJlcyBhIEF0dGVuZGVlJyxcbiAgcHJpbWFyeUtleTogJ2lkJyxcbiAgdHlwZTogJ29iamVjdCcsXG4gIHByb3BlcnRpZXM6IHtcbiAgICBpZDoge1xuICAgICAgdHlwZTogJ3N0cmluZycsXG4gICAgfSxcbiAgICB1c2VySWQ6IHtcbiAgICAgIHR5cGU6ICdzdHJpbmcnLFxuICAgIH0sXG4gICAgbmFtZToge1xuICAgICAgdHlwZTogWydzdHJpbmcnLCAnbnVsbCddLFxuICAgIH0sXG4gICAgY29udGFjdElkOiB7XG4gICAgICB0eXBlOiBbJ3N0cmluZycsICdudWxsJ10sXG4gICAgfSxcbiAgICBlbWFpbHM6IHtcbiAgICAgIHR5cGU6IFsnYXJyYXknLCAnbnVsbCddLFxuICAgICAgdW5pcXVlSXRlbXM6IHRydWUsXG4gICAgICBpdGVtczoge1xuICAgICAgICB0eXBlOiAnb2JqZWN0JyxcbiAgICAgICAgcHJvcGVydGllczoge1xuICAgICAgICAgIHByaW1hcnk6IHtcbiAgICAgICAgICAgIHR5cGU6ICdib29sZWFuJyxcbiAgICAgICAgICB9LFxuICAgICAgICAgIHZhbHVlOiB7XG4gICAgICAgICAgICB0eXBlOiAnc3RyaW5nJyxcbiAgICAgICAgICB9LFxuICAgICAgICAgIHR5cGU6IHtcbiAgICAgICAgICAgIHR5cGU6ICdzdHJpbmcnLFxuICAgICAgICAgIH0sXG4gICAgICAgICAgZGlzcGxheU5hbWU6IHtcbiAgICAgICAgICAgIHR5cGU6ICdzdHJpbmcnLFxuICAgICAgICAgIH0sXG4gICAgICAgIH0sXG4gICAgICB9LFxuICAgIH0sXG4gICAgcGhvbmVOdW1iZXJzOiB7XG4gICAgICB0eXBlOiBbJ2FycmF5JywgJ251bGwnXSxcbiAgICAgIHVuaXF1ZUl0ZW1zOiB0cnVlLFxuICAgICAgaXRlbXM6IHtcbiAgICAgICAgdHlwZTogJ29iamVjdCcsXG4gICAgICAgIHByb3BlcnRpZXM6IHtcbiAgICAgICAgICBwcmltYXJ5OiB7XG4gICAgICAgICAgICB0eXBlOiAnYm9vbGVhbicsXG4gICAgICAgICAgfSxcbiAgICAgICAgICB2YWx1ZToge1xuICAgICAgICAgICAgdHlwZTogJ3N0cmluZycsXG4gICAgICAgICAgfSxcbiAgICAgICAgICB0eXBlOiB7XG4gICAgICAgICAgICB0eXBlOiAnc3RyaW5nJyxcbiAgICAgICAgICB9LFxuICAgICAgICB9LFxuICAgICAgfSxcbiAgICB9LFxuICAgIGltQWRkcmVzc2VzOiB7XG4gICAgICB0eXBlOiBbJ2FycmF5JywgJ251bGwnXSxcbiAgICAgIHVuaXF1ZUl0ZW1zOiB0cnVlLFxuICAgICAgaXRlbXM6IHtcbiAgICAgICAgdHlwZTogJ29iamVjdCcsXG4gICAgICAgIHByb3BlcnRpZXM6IHtcbiAgICAgICAgICBwcmltYXJ5OiB7XG4gICAgICAgICAgICB0eXBlOiAnYm9vbGVhbicsXG4gICAgICAgICAgfSxcbiAgICAgICAgICB1c2VybmFtZToge1xuICAgICAgICAgICAgdHlwZTogJ3N0cmluZycsXG4gICAgICAgICAgfSxcbiAgICAgICAgICBzZXJ2aWNlOiB7XG4gICAgICAgICAgICB0eXBlOiAnc3RyaW5nJyxcbiAgICAgICAgICB9LFxuICAgICAgICAgIHR5cGU6IHtcbiAgICAgICAgICAgIHR5cGU6ICdzdHJpbmcnLFxuICAgICAgICAgIH0sXG4gICAgICAgIH0sXG4gICAgICB9LFxuICAgIH0sXG4gICAgZXZlbnRJZDoge1xuICAgICAgdHlwZTogJ3N0cmluZycsXG4gICAgfSxcbiAgICBhZGRpdGlvbmFsR3Vlc3RzOiB7XG4gICAgICB0eXBlOiAnbnVtYmVyJyxcbiAgICB9LFxuICAgIGNvbW1lbnQ6IHtcbiAgICAgIHR5cGU6IFsnc3RyaW5nJywgJ251bGwnXSxcbiAgICB9LFxuICAgIHJlc3BvbnNlU3RhdHVzOiB7XG4gICAgICB0eXBlOiBbJ3N0cmluZycsICdudWxsJ10sXG4gICAgfSxcbiAgICBvcHRpb25hbDoge1xuICAgICAgdHlwZTogJ2Jvb2xlYW4nLFxuICAgIH0sXG4gICAgcmVzb3VyY2U6IHtcbiAgICAgIHR5cGU6ICdib29sZWFuJyxcbiAgICB9LFxuICAgIHVwZGF0ZWRBdDoge1xuICAgICAgdHlwZTogJ3N0cmluZycsXG4gICAgfSxcbiAgICBjcmVhdGVkRGF0ZToge1xuICAgICAgdHlwZTogJ3N0cmluZycsXG4gICAgfSxcbiAgfSxcbiAgcmVxdWlyZWQ6IFsnaWQnLCAnbmFtZScsICd1c2VySWQnLCAnZXZlbnRJZCcsICd1cGRhdGVkQXQnLCAnY3JlYXRlZERhdGUnXSxcbiAgaW5kZXhlczogWyd1c2VySWQnLCAnZXZlbnRJZCddLFxufTtcblxuZXhwb3J0IGRlZmF1bHQgQXR0ZW5kZWU7XG4iXX0=