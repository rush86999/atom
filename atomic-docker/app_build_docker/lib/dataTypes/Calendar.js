"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const Calendar = {
    title: 'Calendar schema',
    version: 0,
    description: 'describes a Calendar',
    primaryKey: 'id',
    type: 'object',
    properties: {
        id: {
            type: 'string',
        },
        userId: {
            type: 'string',
        },
        title: {
            type: ['string', 'null'],
        },
        backgroundColor: {
            type: ['string', 'null'],
        },
        foregroundColor: {
            type: ['string', 'null'],
        },
        colorId: {
            type: ['string', 'null'],
        },
        account: {
            type: ['object', 'null'],
            properties: {
                id: {
                    type: 'string',
                },
                isLocal: {
                    type: 'boolean',
                },
                name: {
                    type: ['string', 'null'],
                },
                type: {
                    type: ['string', 'null'],
                },
            },
        },
        accessLevel: {
            type: ['string', 'null'],
        },
        resource: {
            type: ['string', 'null'],
        },
        modifiable: {
            type: 'boolean',
        },
        globalPrimary: {
            type: 'boolean',
        },
        defaultReminders: {
            type: ['array', 'null'],
            uniqueItems: true,
            items: {
                type: 'object',
                properties: {
                    method: {
                        type: ['string', 'null'],
                    },
                    minutes: {
                        type: ['number', 'null'],
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
    },
    required: ['id', 'updatedAt', 'createdDate'],
    indexes: ['userId'],
};
exports.default = Calendar;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiQ2FsZW5kYXIuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJDYWxlbmRhci50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOztBQUFBLE1BQU0sUUFBUSxHQUFHO0lBQ2YsS0FBSyxFQUFFLGlCQUFpQjtJQUN4QixPQUFPLEVBQUUsQ0FBQztJQUNWLFdBQVcsRUFBRSxzQkFBc0I7SUFDbkMsVUFBVSxFQUFFLElBQUk7SUFDaEIsSUFBSSxFQUFFLFFBQVE7SUFDZCxVQUFVLEVBQUU7UUFDVixFQUFFLEVBQUU7WUFDRixJQUFJLEVBQUUsUUFBUTtTQUNmO1FBQ0QsTUFBTSxFQUFFO1lBQ04sSUFBSSxFQUFFLFFBQVE7U0FDZjtRQUNELEtBQUssRUFBRTtZQUNMLElBQUksRUFBRSxDQUFDLFFBQVEsRUFBRSxNQUFNLENBQUM7U0FDekI7UUFDRCxlQUFlLEVBQUU7WUFDZixJQUFJLEVBQUUsQ0FBQyxRQUFRLEVBQUUsTUFBTSxDQUFDO1NBQ3pCO1FBQ0QsZUFBZSxFQUFFO1lBQ2YsSUFBSSxFQUFFLENBQUMsUUFBUSxFQUFFLE1BQU0sQ0FBQztTQUN6QjtRQUNELE9BQU8sRUFBRTtZQUNQLElBQUksRUFBRSxDQUFDLFFBQVEsRUFBRSxNQUFNLENBQUM7U0FDekI7UUFDRCxPQUFPLEVBQUU7WUFDUCxJQUFJLEVBQUUsQ0FBQyxRQUFRLEVBQUUsTUFBTSxDQUFDO1lBQ3hCLFVBQVUsRUFBRTtnQkFDVixFQUFFLEVBQUU7b0JBQ0YsSUFBSSxFQUFFLFFBQVE7aUJBQ2Y7Z0JBQ0QsT0FBTyxFQUFFO29CQUNQLElBQUksRUFBRSxTQUFTO2lCQUNoQjtnQkFDRCxJQUFJLEVBQUU7b0JBQ0osSUFBSSxFQUFFLENBQUMsUUFBUSxFQUFFLE1BQU0sQ0FBQztpQkFDekI7Z0JBQ0QsSUFBSSxFQUFFO29CQUNKLElBQUksRUFBRSxDQUFDLFFBQVEsRUFBRSxNQUFNLENBQUM7aUJBQ3pCO2FBQ0Y7U0FDRjtRQUNELFdBQVcsRUFBRTtZQUNYLElBQUksRUFBRSxDQUFDLFFBQVEsRUFBRSxNQUFNLENBQUM7U0FDekI7UUFDRCxRQUFRLEVBQUU7WUFDUixJQUFJLEVBQUUsQ0FBQyxRQUFRLEVBQUUsTUFBTSxDQUFDO1NBQ3pCO1FBQ0QsVUFBVSxFQUFFO1lBQ1YsSUFBSSxFQUFFLFNBQVM7U0FDaEI7UUFDRCxhQUFhLEVBQUU7WUFDYixJQUFJLEVBQUUsU0FBUztTQUNoQjtRQUNELGdCQUFnQixFQUFFO1lBQ2hCLElBQUksRUFBRSxDQUFDLE9BQU8sRUFBRSxNQUFNLENBQUM7WUFDdkIsV0FBVyxFQUFFLElBQUk7WUFDakIsS0FBSyxFQUFFO2dCQUNMLElBQUksRUFBRSxRQUFRO2dCQUNkLFVBQVUsRUFBRTtvQkFDVixNQUFNLEVBQUU7d0JBQ04sSUFBSSxFQUFFLENBQUMsUUFBUSxFQUFFLE1BQU0sQ0FBQztxQkFDekI7b0JBQ0QsT0FBTyxFQUFFO3dCQUNQLElBQUksRUFBRSxDQUFDLFFBQVEsRUFBRSxNQUFNLENBQUM7cUJBQ3pCO2lCQUNGO2FBQ0Y7U0FDRjtRQUNELFNBQVMsRUFBRTtZQUNULElBQUksRUFBRSxRQUFRO1NBQ2Y7UUFDRCxXQUFXLEVBQUU7WUFDWCxJQUFJLEVBQUUsUUFBUTtTQUNmO0tBQ0Y7SUFDRCxRQUFRLEVBQUUsQ0FBQyxJQUFJLEVBQUUsV0FBVyxFQUFFLGFBQWEsQ0FBQztJQUM1QyxPQUFPLEVBQUUsQ0FBQyxRQUFRLENBQUM7Q0FDcEIsQ0FBQztBQUVGLGtCQUFlLFFBQVEsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImNvbnN0IENhbGVuZGFyID0ge1xuICB0aXRsZTogJ0NhbGVuZGFyIHNjaGVtYScsXG4gIHZlcnNpb246IDAsXG4gIGRlc2NyaXB0aW9uOiAnZGVzY3JpYmVzIGEgQ2FsZW5kYXInLFxuICBwcmltYXJ5S2V5OiAnaWQnLFxuICB0eXBlOiAnb2JqZWN0JyxcbiAgcHJvcGVydGllczoge1xuICAgIGlkOiB7XG4gICAgICB0eXBlOiAnc3RyaW5nJyxcbiAgICB9LFxuICAgIHVzZXJJZDoge1xuICAgICAgdHlwZTogJ3N0cmluZycsXG4gICAgfSxcbiAgICB0aXRsZToge1xuICAgICAgdHlwZTogWydzdHJpbmcnLCAnbnVsbCddLFxuICAgIH0sXG4gICAgYmFja2dyb3VuZENvbG9yOiB7XG4gICAgICB0eXBlOiBbJ3N0cmluZycsICdudWxsJ10sXG4gICAgfSxcbiAgICBmb3JlZ3JvdW5kQ29sb3I6IHtcbiAgICAgIHR5cGU6IFsnc3RyaW5nJywgJ251bGwnXSxcbiAgICB9LFxuICAgIGNvbG9ySWQ6IHtcbiAgICAgIHR5cGU6IFsnc3RyaW5nJywgJ251bGwnXSxcbiAgICB9LFxuICAgIGFjY291bnQ6IHtcbiAgICAgIHR5cGU6IFsnb2JqZWN0JywgJ251bGwnXSxcbiAgICAgIHByb3BlcnRpZXM6IHtcbiAgICAgICAgaWQ6IHtcbiAgICAgICAgICB0eXBlOiAnc3RyaW5nJyxcbiAgICAgICAgfSxcbiAgICAgICAgaXNMb2NhbDoge1xuICAgICAgICAgIHR5cGU6ICdib29sZWFuJyxcbiAgICAgICAgfSxcbiAgICAgICAgbmFtZToge1xuICAgICAgICAgIHR5cGU6IFsnc3RyaW5nJywgJ251bGwnXSxcbiAgICAgICAgfSxcbiAgICAgICAgdHlwZToge1xuICAgICAgICAgIHR5cGU6IFsnc3RyaW5nJywgJ251bGwnXSxcbiAgICAgICAgfSxcbiAgICAgIH0sXG4gICAgfSxcbiAgICBhY2Nlc3NMZXZlbDoge1xuICAgICAgdHlwZTogWydzdHJpbmcnLCAnbnVsbCddLFxuICAgIH0sXG4gICAgcmVzb3VyY2U6IHtcbiAgICAgIHR5cGU6IFsnc3RyaW5nJywgJ251bGwnXSxcbiAgICB9LFxuICAgIG1vZGlmaWFibGU6IHtcbiAgICAgIHR5cGU6ICdib29sZWFuJyxcbiAgICB9LFxuICAgIGdsb2JhbFByaW1hcnk6IHtcbiAgICAgIHR5cGU6ICdib29sZWFuJyxcbiAgICB9LFxuICAgIGRlZmF1bHRSZW1pbmRlcnM6IHtcbiAgICAgIHR5cGU6IFsnYXJyYXknLCAnbnVsbCddLFxuICAgICAgdW5pcXVlSXRlbXM6IHRydWUsXG4gICAgICBpdGVtczoge1xuICAgICAgICB0eXBlOiAnb2JqZWN0JyxcbiAgICAgICAgcHJvcGVydGllczoge1xuICAgICAgICAgIG1ldGhvZDoge1xuICAgICAgICAgICAgdHlwZTogWydzdHJpbmcnLCAnbnVsbCddLFxuICAgICAgICAgIH0sXG4gICAgICAgICAgbWludXRlczoge1xuICAgICAgICAgICAgdHlwZTogWydudW1iZXInLCAnbnVsbCddLFxuICAgICAgICAgIH0sXG4gICAgICAgIH0sXG4gICAgICB9LFxuICAgIH0sXG4gICAgdXBkYXRlZEF0OiB7XG4gICAgICB0eXBlOiAnc3RyaW5nJyxcbiAgICB9LFxuICAgIGNyZWF0ZWREYXRlOiB7XG4gICAgICB0eXBlOiAnc3RyaW5nJyxcbiAgICB9LFxuICB9LFxuICByZXF1aXJlZDogWydpZCcsICd1cGRhdGVkQXQnLCAnY3JlYXRlZERhdGUnXSxcbiAgaW5kZXhlczogWyd1c2VySWQnXSxcbn07XG5cbmV4cG9ydCBkZWZhdWx0IENhbGVuZGFyO1xuIl19