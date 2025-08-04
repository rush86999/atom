"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const Reminder = {
    title: 'Reminder schema',
    version: 0,
    description: 'describes a Reminder',
    primaryKey: 'id',
    type: 'object',
    properties: {
        id: {
            type: 'string',
        },
        eventId: {
            type: 'string',
        },
        userId: {
            type: 'string',
        },
        reminderDate: {
            type: ['string', 'null'],
        },
        timezone: {
            type: 'string',
        },
        minutes: {
            type: ['number', 'null'],
        },
        method: {
            type: 'string',
        },
        useDefault: {
            type: 'boolean',
        },
        updatedAt: {
            type: 'string',
        },
        createdDate: {
            type: 'string',
        },
    },
    required: ['id', 'eventId', 'userId', 'updatedAt', 'createdDate'],
    indexes: ['userId'],
};
exports.default = Reminder;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiUmVtaW5kZXIuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJSZW1pbmRlci50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOztBQUFBLE1BQU0sUUFBUSxHQUFHO0lBQ2YsS0FBSyxFQUFFLGlCQUFpQjtJQUN4QixPQUFPLEVBQUUsQ0FBQztJQUNWLFdBQVcsRUFBRSxzQkFBc0I7SUFDbkMsVUFBVSxFQUFFLElBQUk7SUFDaEIsSUFBSSxFQUFFLFFBQVE7SUFDZCxVQUFVLEVBQUU7UUFDVixFQUFFLEVBQUU7WUFDRixJQUFJLEVBQUUsUUFBUTtTQUNmO1FBQ0QsT0FBTyxFQUFFO1lBQ1AsSUFBSSxFQUFFLFFBQVE7U0FDZjtRQUNELE1BQU0sRUFBRTtZQUNOLElBQUksRUFBRSxRQUFRO1NBQ2Y7UUFDRCxZQUFZLEVBQUU7WUFDWixJQUFJLEVBQUUsQ0FBQyxRQUFRLEVBQUUsTUFBTSxDQUFDO1NBQ3pCO1FBQ0QsUUFBUSxFQUFFO1lBQ1IsSUFBSSxFQUFFLFFBQVE7U0FDZjtRQUNELE9BQU8sRUFBRTtZQUNQLElBQUksRUFBRSxDQUFDLFFBQVEsRUFBRSxNQUFNLENBQUM7U0FDekI7UUFDRCxNQUFNLEVBQUU7WUFDTixJQUFJLEVBQUUsUUFBUTtTQUNmO1FBQ0QsVUFBVSxFQUFFO1lBQ1YsSUFBSSxFQUFFLFNBQVM7U0FDaEI7UUFDRCxTQUFTLEVBQUU7WUFDVCxJQUFJLEVBQUUsUUFBUTtTQUNmO1FBQ0QsV0FBVyxFQUFFO1lBQ1gsSUFBSSxFQUFFLFFBQVE7U0FDZjtLQUNGO0lBQ0QsUUFBUSxFQUFFLENBQUMsSUFBSSxFQUFFLFNBQVMsRUFBRSxRQUFRLEVBQUUsV0FBVyxFQUFFLGFBQWEsQ0FBQztJQUNqRSxPQUFPLEVBQUUsQ0FBQyxRQUFRLENBQUM7Q0FDcEIsQ0FBQztBQUVGLGtCQUFlLFFBQVEsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImNvbnN0IFJlbWluZGVyID0ge1xuICB0aXRsZTogJ1JlbWluZGVyIHNjaGVtYScsXG4gIHZlcnNpb246IDAsXG4gIGRlc2NyaXB0aW9uOiAnZGVzY3JpYmVzIGEgUmVtaW5kZXInLFxuICBwcmltYXJ5S2V5OiAnaWQnLFxuICB0eXBlOiAnb2JqZWN0JyxcbiAgcHJvcGVydGllczoge1xuICAgIGlkOiB7XG4gICAgICB0eXBlOiAnc3RyaW5nJyxcbiAgICB9LFxuICAgIGV2ZW50SWQ6IHtcbiAgICAgIHR5cGU6ICdzdHJpbmcnLFxuICAgIH0sXG4gICAgdXNlcklkOiB7XG4gICAgICB0eXBlOiAnc3RyaW5nJyxcbiAgICB9LFxuICAgIHJlbWluZGVyRGF0ZToge1xuICAgICAgdHlwZTogWydzdHJpbmcnLCAnbnVsbCddLFxuICAgIH0sXG4gICAgdGltZXpvbmU6IHtcbiAgICAgIHR5cGU6ICdzdHJpbmcnLFxuICAgIH0sXG4gICAgbWludXRlczoge1xuICAgICAgdHlwZTogWydudW1iZXInLCAnbnVsbCddLFxuICAgIH0sXG4gICAgbWV0aG9kOiB7XG4gICAgICB0eXBlOiAnc3RyaW5nJyxcbiAgICB9LFxuICAgIHVzZURlZmF1bHQ6IHtcbiAgICAgIHR5cGU6ICdib29sZWFuJyxcbiAgICB9LFxuICAgIHVwZGF0ZWRBdDoge1xuICAgICAgdHlwZTogJ3N0cmluZycsXG4gICAgfSxcbiAgICBjcmVhdGVkRGF0ZToge1xuICAgICAgdHlwZTogJ3N0cmluZycsXG4gICAgfSxcbiAgfSxcbiAgcmVxdWlyZWQ6IFsnaWQnLCAnZXZlbnRJZCcsICd1c2VySWQnLCAndXBkYXRlZEF0JywgJ2NyZWF0ZWREYXRlJ10sXG4gIGluZGV4ZXM6IFsndXNlcklkJ10sXG59O1xuXG5leHBvcnQgZGVmYXVsdCBSZW1pbmRlcjtcbiJdfQ==