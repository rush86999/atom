"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const User_Preference = {
    title: 'user_preference schema',
    version: 0,
    description: 'describes a user_preference',
    primaryKey: 'id',
    type: 'object',
    properties: {
        id: {
            type: 'string',
        },
        userId: {
            type: 'string',
        },
        reminders: {
            type: ['array', 'null'],
            uniqueItems: true,
            items: {
                type: 'number',
            },
        },
        followUp: {
            type: ['array', 'null'],
            uniqueItems: true,
            items: {
                type: 'number',
            },
        },
        isPublicCalendar: {
            type: 'boolean',
        },
        publicCalendarCategories: {
            type: ['array', 'null'],
            uniqueItems: true,
            items: {
                type: 'string',
            },
        },
        startTimes: {
            type: ['array', 'null'],
            uniqueItems: true,
            items: {
                type: 'object',
                properties: {
                    day: {
                        type: 'number',
                    },
                    hour: {
                        type: 'number',
                    },
                    minutes: {
                        type: 'number',
                    },
                },
            },
        },
        endTimes: {
            type: ['array', 'null'],
            uniqueItems: true,
            items: {
                type: 'object',
                properties: {
                    day: {
                        type: 'number',
                    },
                    hour: {
                        type: 'number',
                    },
                    minutes: {
                        type: 'number',
                    },
                },
            },
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
        copyCategories: {
            type: ['boolean', 'null'],
        },
        copyIsBreak: {
            type: ['boolean', 'null'],
        },
        maxWorkLoadPercent: {
            type: ['number', 'null'],
        },
        backToBackMeetings: {
            type: ['boolean', 'null'],
        },
        maxNumberOfMeeting: {
            type: ['number', 'null'],
        },
        minNumberOfBreaks: {
            type: ['number', 'null'],
        },
        breakLength: {
            type: ['number', 'null'],
        },
        breakColor: {
            type: ['string', 'null'],
        },
        copyIsMeeting: {
            type: ['number', 'null'],
        },
        copyIsExternalMeeting: {
            type: ['number', 'null'],
        },
        copyColor: {
            type: ['boolean', 'null'],
        },
        onBoarded: {
            type: ['boolean', 'null'],
        },
        updatedAt: {
            type: 'string',
        },
        createdDate: {
            type: 'string',
        },
    },
    required: ['id', 'userId', 'updatedAt', 'createdDate'],
    indexes: ['userId'],
};
exports.default = User_Preference;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiVXNlcl9QcmVmZXJlbmNlLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsiVXNlcl9QcmVmZXJlbmNlLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiI7O0FBQUEsTUFBTSxlQUFlLEdBQUc7SUFDdEIsS0FBSyxFQUFFLHdCQUF3QjtJQUMvQixPQUFPLEVBQUUsQ0FBQztJQUNWLFdBQVcsRUFBRSw2QkFBNkI7SUFDMUMsVUFBVSxFQUFFLElBQUk7SUFDaEIsSUFBSSxFQUFFLFFBQVE7SUFDZCxVQUFVLEVBQUU7UUFDVixFQUFFLEVBQUU7WUFDRixJQUFJLEVBQUUsUUFBUTtTQUNmO1FBQ0QsTUFBTSxFQUFFO1lBQ04sSUFBSSxFQUFFLFFBQVE7U0FDZjtRQUNELFNBQVMsRUFBRTtZQUNULElBQUksRUFBRSxDQUFDLE9BQU8sRUFBRSxNQUFNLENBQUM7WUFDdkIsV0FBVyxFQUFFLElBQUk7WUFDakIsS0FBSyxFQUFFO2dCQUNMLElBQUksRUFBRSxRQUFRO2FBQ2Y7U0FDRjtRQUNELFFBQVEsRUFBRTtZQUNSLElBQUksRUFBRSxDQUFDLE9BQU8sRUFBRSxNQUFNLENBQUM7WUFDdkIsV0FBVyxFQUFFLElBQUk7WUFDakIsS0FBSyxFQUFFO2dCQUNMLElBQUksRUFBRSxRQUFRO2FBQ2Y7U0FDRjtRQUNELGdCQUFnQixFQUFFO1lBQ2hCLElBQUksRUFBRSxTQUFTO1NBQ2hCO1FBQ0Qsd0JBQXdCLEVBQUU7WUFDeEIsSUFBSSxFQUFFLENBQUMsT0FBTyxFQUFFLE1BQU0sQ0FBQztZQUN2QixXQUFXLEVBQUUsSUFBSTtZQUNqQixLQUFLLEVBQUU7Z0JBQ0wsSUFBSSxFQUFFLFFBQVE7YUFDZjtTQUNGO1FBQ0QsVUFBVSxFQUFFO1lBQ1YsSUFBSSxFQUFFLENBQUMsT0FBTyxFQUFFLE1BQU0sQ0FBQztZQUN2QixXQUFXLEVBQUUsSUFBSTtZQUNqQixLQUFLLEVBQUU7Z0JBQ0wsSUFBSSxFQUFFLFFBQVE7Z0JBQ2QsVUFBVSxFQUFFO29CQUNWLEdBQUcsRUFBRTt3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ZmVyZW5jZSBzY2hlbWEnLFxuICB2ZXJzaW9uOiAwLFxuICBkZXNjcmlwdGlvbjogJ2Rlc2NyaWJlcyBhIHVzZXJfcHJlZmVyZW5jZScsXG4gIHByaW1hcnlLZXk6ICdpZCcsXG4gIHR5cGU6ICdvYmplY3QnLFxuICBwcm9wZXJ0aWVzOiB7XG4gICAgaWQ6IHtcbiAgICAgIHR5cGU6ICdzdHJpbmcnLFxuICAgIH0sXG4gICAgdXNlcklkOiB7XG4gICAgICB0eXBlOiAnc3RyaW5nJyxcbiAgICB9LFxuICAgIHJlbWluZGVyczoge1xuICAgICAgdHlwZTogWydhcnJheScsICdudWxsJ10sXG4gICAgICB1bmlxdWVJdGVtczogdHJ1ZSxcbiAgICAgIGl0ZW1zOiB7XG4gICAgICAgIHR5cGU6ICdudW1iZXInLFxuICAgICAgfSxcbiAgICB9LFxuICAgIGZvbGxvd1VwOiB7XG4gICAgICB0eXBlOiBbJ2FycmF5JywgJ251bGwnXSxcbiAgICAgIHVuaXF1ZUl0ZW1zOiB0cnVlLFxuICAgICAgaXRlbXM6IHtcbiAgICAgICAgdHlwZTogJ251bWJlcicsXG4gICAgICB9LFxuICAgIH0sXG4gICAgaXNQdWJsaWNDYWxlbmRhcjoge1xuICAgICAgdHlwZTogJ2Jvb2xlYW4nLFxuICAgIH0sXG4gICAgcHVibGljQ2FsZW5kYXJDYXRlZ29yaWVzOiB7XG4gICAgICB0eXBlOiBbJ2FycmF5JywgJ251bGwnXSxcbiAgICAgIHVuaXF1ZUl0ZW1zOiB0cnVlLFxuICAgICAgaXRlbXM6IHtcbiAgICAgICAgdHlwZTogJ3N0cmluZycsXG4gICAgICB9LFxuICAgIH0sXG4gICAgc3RhcnRUaW1lczoge1xuICAgICAgdHlwZTogWydhcnJheScsICdudWxsJ10sXG4gICAgICB1bmlxdWVJdGVtczogdHJ1ZSxcbiAgICAgIGl0ZW1zOiB7XG4gICAgICAgIHR5cGU6ICdvYmplY3QnLFxuICAgICAgICBwcm9wZXJ0aWVzOiB7XG4gICAgICAgICAgZGF5OiB7XG4gICAgICAgICAgICB0eXBlOiAnbnVtYmVyJyxcbiAgICAgICAgICB9LFxuICAgICAgICAgIGhvdXI6IHtcbiAgICAgICAgICAgIHR5cGU6ICdudW1iZXInLFxuICAgICAgICAgIH0sXG4gICAgICAgICAgbWludXRlczoge1xuICAgICAgICAgICAgdHlwZTogJ251bWJlcicsXG4gICAgICAgICAgfSxcbiAgICAgICAgfSxcbiAgICAgIH0sXG4gICAgfSxcbiAgICBlbmRUaW1lczoge1xuICAgICAgdHlwZTogWydhcnJheScsICdudWxsJ10sXG4gICAgICB1bmlxdWVJdGVtczogdHJ1ZSxcbiAgICAgIGl0ZW1zOiB7XG4gICAgICAgIHR5cGU6ICdvYmplY3QnLFxuICAgICAgICBwcm9wZXJ0aWVzOiB7XG4gICAgICAgICAgZGF5OiB7XG4gICAgICAgICAgICB0eXBlOiAnbnVtYmVyJyxcbiAgICAgICAgICB9LFxuICAgICAgICAgIGhvdXI6IHtcbiAgICAgICAgICAgIHR5cGU6ICdudW1iZXInLFxuICAgICAgICAgIH0sXG4gICAgICAgICAgbWludXRlczoge1xuICAgICAgICAgICAgdHlwZTogJ251bWJlcicsXG4gICAgICAgICAgfSxcbiAgICAgICAgfSxcbiAgICAgIH0sXG4gICAgfSxcbiAgICBjb3B5QXZhaWxhYmlsaXR5OiB7XG4gICAgICB0eXBlOiBbJ2Jvb2xlYW4nLCAnbnVsbCddLFxuICAgIH0sXG4gICAgY29weVRpbWVCbG9ja2luZzoge1xuICAgICAgdHlwZTogWydib29sZWFuJywgJ251bGwnXSxcbiAgICB9LFxuICAgIGNvcHlUaW1lUHJlZmVyZW5jZToge1xuICAgICAgdHlwZTogWydib29sZWFuJywgJ251bGwnXSxcbiAgICB9LFxuICAgIGNvcHlSZW1pbmRlcnM6IHtcbiAgICAgIHR5cGU6IFsnYm9vbGVhbicsICdudWxsJ10sXG4gICAgfSxcbiAgICBjb3B5UHJpb3JpdHlMZXZlbDoge1xuICAgICAgdHlwZTogWydib29sZWFuJywgJ251bGwnXSxcbiAgICB9LFxuICAgIGNvcHlNb2RpZmlhYmxlOiB7XG4gICAgICB0eXBlOiBbJ2Jvb2xlYW4nLCAnbnVsbCddLFxuICAgIH0sXG4gICAgY29weUNhdGVnb3JpZXM6IHtcbiAgICAgIHR5cGU6IFsnYm9vbGVhbicsICdudWxsJ10sXG4gICAgfSxcbiAgICBjb3B5SXNCcmVhazoge1xuICAgICAgdHlwZTogWydib29sZWFuJywgJ251bGwnXSxcbiAgICB9LFxuICAgIG1heFdvcmtMb2FkUGVyY2VudDoge1xuICAgICAgdHlwZTogWydudW1iZXInLCAnbnVsbCddLFxuICAgIH0sXG4gICAgYmFja1RvQmFja01lZXRpbmdzOiB7XG4gICAgICB0eXBlOiBbJ2Jvb2xlYW4nLCAnbnVsbCddLFxuICAgIH0sXG4gICAgbWF4TnVtYmVyT2ZNZWV0aW5nOiB7XG4gICAgICB0eXBlOiBbJ251bWJlcicsICdudWxsJ10sXG4gICAgfSxcbiAgICBtaW5OdW1iZXJPZkJyZWFrczoge1xuICAgICAgdHlwZTogWydudW1iZXInLCAnbnVsbCddLFxuICAgIH0sXG4gICAgYnJlYWtMZW5ndGg6IHtcbiAgICAgIHR5cGU6IFsnbnVtYmVyJywgJ251bGwnXSxcbiAgICB9LFxuICAgIGJyZWFrQ29sb3I6IHtcbiAgICAgIHR5cGU6IFsnc3RyaW5nJywgJ251bGwnXSxcbiAgICB9LFxuICAgIGNvcHlJc01lZXRpbmc6IHtcbiAgICAgIHR5cGU6IFsnbnVtYmVyJywgJ251bGwnXSxcbiAgICB9LFxuICAgIGNvcHlJc0V4dGVybmFsTWVldGluZzoge1xuICAgICAgdHlwZTogWydudW1iZXInLCAnbnVsbCddLFxuICAgIH0sXG4gICAgY29weUNvbG9yOiB7XG4gICAgICB0eXBlOiBbJ2Jvb2xlYW4nLCAnbnVsbCddLFxuICAgIH0sXG4gICAgb25Cb2FyZGVkOiB7XG4gICAgICB0eXBlOiBbJ2Jvb2xlYW4nLCAnbnVsbCddLFxuICAgIH0sXG4gICAgdXBkYXRlZEF0OiB7XG4gICAgICB0eXBlOiAnc3RyaW5nJyxcbiAgICB9LFxuICAgIGNyZWF0ZWREYXRlOiB7XG4gICAgICB0eXBlOiAnc3RyaW5nJyxcbiAgICB9LFxuICB9LFxuICByZXF1aXJlZDogWydpZCcsICd1c2VySWQnLCAndXBkYXRlZEF0JywgJ2NyZWF0ZWREYXRlJ10sXG4gIGluZGV4ZXM6IFsndXNlcklkJ10sXG59O1xuXG5leHBvcnQgZGVmYXVsdCBVc2VyX1ByZWZlcmVuY2U7XG4iXX0=