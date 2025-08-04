"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const Category = {
    title: 'Category schema',
    version: 0,
    description: 'describes a Category',
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
            type: 'string',
        },
        copyAvailability: {
            type: ['boolean', 'null'],
        },
        copyTimeBlocking: {
            type: ['boolean', 'null'],
        },
        copyTimePreference: {
            type: ['boolean', 'null'],
        },
        copyReminders: {
            type: ['boolean', 'null'],
        },
        copyPriorityLevel: {
            type: ['boolean', 'null'],
        },
        copyModifiable: {
            type: ['boolean', 'null'],
        },
        defaultAvailability: {
            type: ['boolean', 'null'],
        },
        defaultTimeBlocking: {
            type: ['object', 'null'],
            properties: {
                beforeEvent: {
                    type: ['number', 'null'],
                },
                afterEvent: {
                    type: ['number', 'null'],
                },
            },
        },
        defaultTimePreference: {
            type: ['object', 'null'],
            properties: {
                preferredDayOfWeek: {
                    type: ['number', 'null'],
                },
                preferredTime: {
                    type: ['string', 'null'],
                    format: 'time',
                },
                preferredStartTimeRange: {
                    type: ['string', 'null'],
                    format: 'time',
                },
                preferredEndTimeRange: {
                    type: ['string', 'null'],
                    format: 'time',
                },
            },
        },
        defaultReminders: {
            type: ['array', 'null'],
            uniqueItems: true,
            items: {
                type: 'number',
            },
        },
        defaultPriorityLevel: {
            type: ['number', 'null'],
        },
        defaultModifiable: {
            type: ['boolean', 'null'],
        },
        copyIsBreak: {
            type: ['boolean', 'null'],
        },
        defaultIsBreak: {
            type: ['boolean', 'null'],
        },
        color: {
            type: ['string', 'null'],
        },
        copyIsMeeting: {
            type: ['boolean', 'null'],
        },
        copyIsExternalMeeting: {
            type: ['boolean', 'null'],
        },
        defaultIsMeeting: {
            type: ['boolean', 'null'],
        },
        defaultIsExternalMeeting: {
            type: ['boolean', 'null'],
        },
        defaultMeetingModifiable: {
            type: ['boolean', 'null'],
        },
        defaultExternalMeetingModifiable: {
            type: ['boolean', 'null'],
        },
        updatedAt: {
            type: 'string',
        },
        createdDate: {
            type: 'string',
        },
    },
    required: ['id', 'name', 'updatedAt', 'createdDate'],
    indexes: ['userId'],
};
exports.default = Category;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiQ2F0ZWdvcnkuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJDYXRlZ29yeS50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOztBQUFBLE1BQU0sUUFBUSxHQUFHO0lBQ2YsS0FBSyxFQUFFLGlCQUFpQjtJQUN4QixPQUFPLEVBQUUsQ0FBQztJQUNWLFdBQVcsRUFBRSxzQkFBc0I7SUFDbkMsVUFBVSxFQUFFLElBQUk7SUFDaEIsSUFBSSxFQUFFLFFBQVE7SUFDZCxVQUFVLEVBQUU7UUFDVixFQUFFLEVBQUU7WUFDRixJQUFJLEVBQUUsUUFBUTtTQUNmO1FBQ0QsTUFBTSxFQUFFO1lBQ04sSUFBSSxFQUFFLFFBQVE7U0FDZjtRQUNELElBQUksRUFBRTtZQUNKLElBQUksRUFBRSxRQUFRO1NBQ2Y7UUFDRCxnQkFBZ0IsRUFBRTtZQUNoQixJQUFJLEVBQUUsQ0FBQyxTQUFTLEVBQUUsTUFBTSxDQUFDO1NBQzFCO1FBQ0QsZ0JBQWdCLEVBQUU7WUFDaEIsSUFBSSxFQUFFLENBQUMsU0FBUyxFQUFFLE1BQU0sQ0FBQztTQUMxQjtRQUNELGtCQUFrQixFQUFFO1lBQ2xCLElBQUksRUFBRSxDQUFDLFNBQVMsRUFBRSxNQUFNLENBQUM7U0FDMUI7UUFDRCxhQUFhLEVBQUU7WUFDYixJQUFJLEVBQUUsQ0FBQyxTQUFTLEVBQUUsTUFBTSxDQUFDO1NBQzFCO1FBQ0QsaUJBQWlCLEVBQUU7WUFDakIsSUFBSSxFQUFFLENBQUMsU0FBUyxFQUFFLE1BQU0sQ0FBQztTQUMxQjtRQUNELGNBQWMsRUFBRTtZQUNkLElBQUksRUFBRSxDQUFDLFNBQVMsRUFBRSxNQUFNLENBQUM7U0FDMUI7UUFDRCxtQkFBbUIsRUFBRTtZQUNuQixJQUFJLEVBQUUsQ0FBQyxTQUFTLEVBQUUsTUFBTSxDQUFDO1NBQzFCO1FBQ0QsbUJBQW1CLEVBQUU7WUFDbkIsSUFBSSxFQUFFLENBQUMsUUFBUSxFQUFFLE1BQU0sQ0FBQztZQUN4QixVQUFVLEVBQUU7Z0JBQ1YsV0FBVyxFQUFFO29CQUNYLElBQUksRUFBRSxDQUFDLFFBQVEsRUFBRSxNQUFNLENBQUM7aUJBQ3pCO2dCQUNELFVBQVUsRUFBRTtvQkFDVixJQUFJLEVBQUUsQ0FBQyxRQUFRLEVBQUUsTUFBTSxDQUFDO2lCQUN6QjthQUNGO1NBQ0Y7UUFDRCxxQkFBcUIsRUFBRTtZQUNyQixJQUFJLEVBQUUsQ0FBQyxRQUFRLEVBQUUsTUFBTSxDQUFDO1lBQ3hCLFVBQVUsRUFBRTtnQkFDVixrQkFBa0IsRUFBRTtvQkFDbEIsSUFBSSxFQUFFLENBQUMsUUFBUSxFQUFFLE1BQU0sQ0FBQztpQkFDekI7Z0JBQ0QsYUFBYSxFQUFFO29CQUNiLElBQUksRUFBRSxDQUFDLFFBQVEsRUFBRSxNQUFNLENBQUM7b0JBQ3hCLE1BQU0sRUFBRSxNQUFNO2lCQUNmO2dCQUNELHVCQUF1QixFQUFFO29CQUN2QixJQUFJLEVBQUUsQ0FBQyxRQUFRLEVBQUUsTUFBTSxDQUFDO29CQUN4QixNQUFNLEVBQUUsTUFBTTtpQkFDZjtnQkFDRCxxQkFBcUIsRUFBRTtvQkFDckIsSUFBSSxFQUFFLENBQUMsUUFBUSxFQUFFLE1BQU0sQ0FBQztvQkFDeEIsTUFBTSxFQUFFLE1BQU07aUJBQ2Y7YUFDRjtTQUNGO1FBQ0QsZ0JBQWdCLEVBQUU7WUFDaEIsSUFBSSxFQUFFLENBQUMsT0FBTyxFQUFFLE1BQU0sQ0FBQztZQUN2QixXQUFXLEVBQUUsSUFBSTtZQUNqQixLQUFLLEVBQUU7Z0JBQ0wsSUFBSSxFQUFFLFFBQVE7YUFDZjtTQUNGO1FBQ0Qsb0JBQW9CLEVBQUU7WUFDcEIsSUFBSSxFQUFFLENBQUMsUUFBUSxFQUFFLE1BQU0sQ0FBQztTQUN6QjtRQUNELGlCQUFpQixFQUFFO1lBQ2pCLElBQUksRUFBRSxDQUFDLFNBQVMsRUFBRSxNQUFNLENBQUM7U0FDMUI7UUFDRCxXQUFXLEVBQUU7WUFDWCxJQUFJLEVBQUUsQ0FBQyxTQUFTLEVBQUUsTUFBTSxDQUFDO1NBQzFCO1FBQ0QsY0FBYyxFQUFFO1lBQ2QsSUFBSSxFQUFFLENBQUMsU0FBUyxFQUFFLE1BQU0sQ0FBQztTQUMxQjtRQUNELEtBQUssRUFBRTtZQUNMLElBQUksRUFBRSxDQUFDLFFBQVEsRUFBRSxNQUFNLENBQUM7U0FDekI7UUFDRCxhQUFhLEVBQUU7WUFDYixJQUFJLEVBQUUsQ0FBQyxTQUFTLEVBQUUsTUFBTSxDQUFDO1NBQzFCO1FBQ0QscUJBQXFCLEVBQUU7WUFDckIsSUFBSSxFQUFFLENBQUMsU0FBUyxFQUFFLE1BQU0sQ0FBQztTQUMxQjtRQUNELGdCQUFnQixFQUFFO1lBQ2hCLElBQUksRUFBRSxDQUFDLFNBQVMsRUFBRSxNQUFNLENBQUM7U0FDMUI7UUFDRCx3QkFBd0IsRUFBRTtZQUN4QixJQUFJLEVBQUUsQ0FBQyxTQUFTLEVBQUUsTUFBTSxDQUFDO1NBQzFCO1FBQ0Qsd0JBQXdCLEVBQUU7WUFDeEIsSUFBSSxFQUFFLENBQUMsU0FBUyxFQUFFLE1BQU0sQ0FBQztTQUMxQjtRQUNELGdDQUFnQyxFQUFFO1lBQ2hDLElBQUksRUFBRSxDQUFDLFNBQVMsRUFBRSxNQUFNLENBQUM7U0FDMUI7UUFDRCxTQUFTLEVBQUU7WUFDVCxJQUFJLEVBQUUsUUFBUTtTQUNmO1FBQ0QsV0FBVyxFQUFFO1lBQ1gsSUFBSSxFQUFFLFFBQVE7U0FDZjtLQUNGO0lBQ0QsUUFBUSxFQUFFLENBQUMsSUFBSSxFQUFFLE1BQU0sRUFBRSxXQUFXLEVBQUUsYUFBYSxDQUFDO0lBQ3BELE9BQU8sRUFBRSxDQUFDLFFBQVEsQ0FBQztDQUNwQixDQUFDO0FBRUYsa0JBQWUsUUFBUSxDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiY29uc3QgQ2F0ZWdvcnkgPSB7XG4gIHRpdGxlOiAnQ2F0ZWdvcnkgc2NoZW1hJyxcbiAgdmVyc2lvbjogMCxcbiAgZGVzY3JpcHRpb246ICdkZXNjcmliZXMgYSBDYXRlZ29yeScsXG4gIHByaW1hcnlLZXk6ICdpZCcsXG4gIHR5cGU6ICdvYmplY3QnLFxuICBwcm9wZXJ0aWVzOiB7XG4gICAgaWQ6IHtcbiAgICAgIHR5cGU6ICdzdHJpbmcnLFxuICAgIH0sXG4gICAgdXNlcklkOiB7XG4gICAgICB0eXBlOiAnc3RyaW5nJyxcbiAgICB9LFxuICAgIG5hbWU6IHtcbiAgICAgIHR5cGU6ICdzdHJpbmcnLFxuICAgIH0sXG4gICAgY29weUF2YWlsYWJpbGl0eToge1xuICAgICAgdHlwZTogWydib29sZWFuJywgJ251bGwnXSxcbiAgICB9LFxuICAgIGNvcHlUaW1lQmxvY2tpbmc6IHtcbiAgICAgIHR5cGU6IFsnYm9vbGVhbicsICdudWxsJ10sXG4gICAgfSxcbiAgICBjb3B5VGltZVByZWZlcmVuY2U6IHtcbiAgICAgIHR5cGU6IFsnYm9vbGVhbicsICdudWxsJ10sXG4gICAgfSxcbiAgICBjb3B5UmVtaW5kZXJzOiB7XG4gICAgICB0eXBlOiBbJ2Jvb2xlYW4nLCAnbnVsbCddLFxuICAgIH0sXG4gICAgY29weVByaW9yaXR5TGV2ZWw6IHtcbiAgICAgIHR5cGU6IFsnYm9vbGVhbicsICdudWxsJ10sXG4gICAgfSxcbiAgICBjb3B5TW9kaWZpYWJsZToge1xuICAgICAgdHlwZTogWydib29sZWFuJywgJ251bGwnXSxcbiAgICB9LFxuICAgIGRlZmF1bHRBdmFpbGFiaWxpdHk6IHtcbiAgICAgIHR5cGU6IFsnYm9vbGVhbicsICdudWxsJ10sXG4gICAgfSxcbiAgICBkZWZhdWx0VGltZUJsb2NraW5nOiB7XG4gICAgICB0eXBlOiBbJ29iamVjdCcsICdudWxsJ10sXG4gICAgICBwcm9wZXJ0aWVzOiB7XG4gICAgICAgIGJlZm9yZUV2ZW50OiB7XG4gICAgICAgICAgdHlwZTogWydudW1iZXInLCAnbnVsbCddLFxuICAgICAgICB9LFxuICAgICAgICBhZnRlckV2ZW50OiB7XG4gICAgICAgICAgdHlwZTogWydudW1iZXInLCAnbnVsbCddLFxuICAgICAgICB9LFxuICAgICAgfSxcbiAgICB9LFxuICAgIGRlZmF1bHRUaW1lUHJlZmVyZW5jZToge1xuICAgICAgdHlwZTogWydvYmplY3QnLCAnbnVsbCddLFxuICAgICAgcHJvcGVydGllczoge1xuICAgICAgICBwcmVmZXJyZWREYXlPZldlZWs6IHtcbiAgICAgICAgICB0eXBlOiBbJ251bWJlcicsICdudWxsJ10sXG4gICAgICAgIH0sXG4gICAgICAgIHByZWZlcnJlZFRpbWU6IHtcbiAgICAgICAgICB0eXBlOiBbJ3N0cmluZycsICdudWxsJ10sXG4gICAgICAgICAgZm9ybWF0OiAndGltZScsXG4gICAgICAgIH0sXG4gICAgICAgIHByZWZlcnJlZFN0YXJ0VGltZVJhbmdlOiB7XG4gICAgICAgICAgdHlwZTogWydzdHJpbmcnLCAnbnVsbCddLFxuICAgICAgICAgIGZvcm1hdDogJ3RpbWUnLFxuICAgICAgICB9LFxuICAgICAgICBwcmVmZXJyZWRFbmRUaW1lUmFuZ2U6IHtcbiAgICAgICAgICB0eXBlOiBbJ3N0cmluZycsICdudWxsJ10sXG4gICAgICAgICAgZm9ybWF0OiAndGltZScsXG4gICAgICAgIH0sXG4gICAgICB9LFxuICAgIH0sXG4gICAgZGVmYXVsdFJlbWluZGVyczoge1xuICAgICAgdHlwZTogWydhcnJheScsICdudWxsJ10sXG4gICAgICB1bmlxdWVJdGVtczogdHJ1ZSxcbiAgICAgIGl0ZW1zOiB7XG4gICAgICAgIHR5cGU6ICdudW1iZXInLFxuICAgICAgfSxcbiAgICB9LFxuICAgIGRlZmF1bHRQcmlvcml0eUxldmVsOiB7XG4gICAgICB0eXBlOiBbJ251bWJlcicsICdudWxsJ10sXG4gICAgfSxcbiAgICBkZWZhdWx0TW9kaWZpYWJsZToge1xuICAgICAgdHlwZTogWydib29sZWFuJywgJ251bGwnXSxcbiAgICB9LFxuICAgIGNvcHlJc0JyZWFrOiB7XG4gICAgICB0eXBlOiBbJ2Jvb2xlYW4nLCAnbnVsbCddLFxuICAgIH0sXG4gICAgZGVmYXVsdElzQnJlYWs6IHtcbiAgICAgIHR5cGU6IFsnYm9vbGVhbicsICdudWxsJ10sXG4gICAgfSxcbiAgICBjb2xvcjoge1xuICAgICAgdHlwZTogWydzdHJpbmcnLCAnbnVsbCddLFxuICAgIH0sXG4gICAgY29weUlzTWVldGluZzoge1xuICAgICAgdHlwZTogWydib29sZWFuJywgJ251bGwnXSxcbiAgICB9LFxuICAgIGNvcHlJc0V4dGVybmFsTWVldGluZzoge1xuICAgICAgdHlwZTogWydib29sZWFuJywgJ251bGwnXSxcbiAgICB9LFxuICAgIGRlZmF1bHRJc01lZXRpbmc6IHtcbiAgICAgIHR5cGU6IFsnYm9vbGVhbicsICdudWxsJ10sXG4gICAgfSxcbiAgICBkZWZhdWx0SXNFeHRlcm5hbE1lZXRpbmc6IHtcbiAgICAgIHR5cGU6IFsnYm9vbGVhbicsICdudWxsJ10sXG4gICAgfSxcbiAgICBkZWZhdWx0TWVldGluZ01vZGlmaWFibGU6IHtcbiAgICAgIHR5cGU6IFsnYm9vbGVhbicsICdudWxsJ10sXG4gICAgfSxcbiAgICBkZWZhdWx0RXh0ZXJuYWxNZWV0aW5nTW9kaWZpYWJsZToge1xuICAgICAgdHlwZTogWydib29sZWFuJywgJ251bGwnXSxcbiAgICB9LFxuICAgIHVwZGF0ZWRBdDoge1xuICAgICAgdHlwZTogJ3N0cmluZycsXG4gICAgfSxcbiAgICBjcmVhdGVkRGF0ZToge1xuICAgICAgdHlwZTogJ3N0cmluZycsXG4gICAgfSxcbiAgfSxcbiAgcmVxdWlyZWQ6IFsnaWQnLCAnbmFtZScsICd1cGRhdGVkQXQnLCAnY3JlYXRlZERhdGUnXSxcbiAgaW5kZXhlczogWyd1c2VySWQnXSxcbn07XG5cbmV4cG9ydCBkZWZhdWx0IENhdGVnb3J5O1xuIl19