"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const Category_Event = {
    title: 'Category_Event schema',
    version: 0,
    description: 'describes a Category_Event',
    primaryKey: 'id',
    type: 'object',
    properties: {
        id: {
            type: 'string',
        },
        userId: {
            type: 'string',
        },
        categoryId: {
            type: 'string',
        },
        eventId: {
            type: 'string',
        },
        updatedAt: {
            type: 'string',
        },
        createdDate: {
            type: 'string',
        },
    },
    required: [
        'id',
        'userId',
        'categoryId',
        'eventId',
        'updatedAt',
        'createdDate',
    ],
    indexes: [
        ['userId', 'categoryId', 'eventId'],
        ['userId', 'eventId', 'categoryId'],
    ],
};
exports.default = Category_Event;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiQ2F0ZWdvcnlfRXZlbnQuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJDYXRlZ29yeV9FdmVudC50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOztBQUFBLE1BQU0sY0FBYyxHQUFHO0lBQ3JCLEtBQUssRUFBRSx1QkFBdUI7SUFDOUIsT0FBTyxFQUFFLENBQUM7SUFDVixXQUFXLEVBQUUsNEJBQTRCO0lBQ3pDLFVBQVUsRUFBRSxJQUFJO0lBQ2hCLElBQUksRUFBRSxRQUFRO0lBQ2QsVUFBVSxFQUFFO1FBQ1YsRUFBRSxFQUFFO1lBQ0YsSUFBSSxFQUFFLFFBQVE7U0FDZjtRQUNELE1BQU0sRUFBRTtZQUNOLElBQUksRUFBRSxRQUFRO1NBQ2Y7UUFDRCxVQUFVLEVBQUU7WUFDVixJQUFJLEVBQUUsUUFBUTtTQUNmO1FBQ0QsT0FBTyxFQUFFO1lBQ1AsSUFBSSxFQUFFLFFBQVE7U0FDZjtRQUNELFNBQVMsRUFBRTtZQUNULElBQUksRUFBRSxRQUFRO1NBQ2Y7UUFDRCxXQUFXLEVBQUU7WUFDWCxJQUFJLEVBQUUsUUFBUTtTQUNmO0tBQ0Y7SUFDRCxRQUFRLEVBQUU7UUFDUixJQUFJO1FBQ0osUUFBUTtRQUNSLFlBQVk7UUFDWixTQUFTO1FBQ1QsV0FBVztRQUNYLGFBQWE7S0FDZDtJQUNELE9BQU8sRUFBRTtRQUNQLENBQUMsUUFBUSxFQUFFLFlBQVksRUFBRSxTQUFTLENBQUM7UUFDbkMsQ0FBQyxRQUFRLEVBQUUsU0FBUyxFQUFFLFlBQVksQ0FBQztLQUNwQztDQUNGLENBQUM7QUFFRixrQkFBZSxjQUFjLENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJjb25zdCBDYXRlZ29yeV9FdmVudCA9IHtcbiAgdGl0bGU6ICdDYXRlZ29yeV9FdmVudCBzY2hlbWEnLFxuICB2ZXJzaW9uOiAwLFxuICBkZXNjcmlwdGlvbjogJ2Rlc2NyaWJlcyBhIENhdGVnb3J5X0V2ZW50JyxcbiAgcHJpbWFyeUtleTogJ2lkJyxcbiAgdHlwZTogJ29iamVjdCcsXG4gIHByb3BlcnRpZXM6IHtcbiAgICBpZDoge1xuICAgICAgdHlwZTogJ3N0cmluZycsXG4gICAgfSxcbiAgICB1c2VySWQ6IHtcbiAgICAgIHR5cGU6ICdzdHJpbmcnLFxuICAgIH0sXG4gICAgY2F0ZWdvcnlJZDoge1xuICAgICAgdHlwZTogJ3N0cmluZycsXG4gICAgfSxcbiAgICBldmVudElkOiB7XG4gICAgICB0eXBlOiAnc3RyaW5nJyxcbiAgICB9LFxuICAgIHVwZGF0ZWRBdDoge1xuICAgICAgdHlwZTogJ3N0cmluZycsXG4gICAgfSxcbiAgICBjcmVhdGVkRGF0ZToge1xuICAgICAgdHlwZTogJ3N0cmluZycsXG4gICAgfSxcbiAgfSxcbiAgcmVxdWlyZWQ6IFtcbiAgICAnaWQnLFxuICAgICd1c2VySWQnLFxuICAgICdjYXRlZ29yeUlkJyxcbiAgICAnZXZlbnRJZCcsXG4gICAgJ3VwZGF0ZWRBdCcsXG4gICAgJ2NyZWF0ZWREYXRlJyxcbiAgXSxcbiAgaW5kZXhlczogW1xuICAgIFsndXNlcklkJywgJ2NhdGVnb3J5SWQnLCAnZXZlbnRJZCddLFxuICAgIFsndXNlcklkJywgJ2V2ZW50SWQnLCAnY2F0ZWdvcnlJZCddLFxuICBdLFxufTtcblxuZXhwb3J0IGRlZmF1bHQgQ2F0ZWdvcnlfRXZlbnQ7XG4iXX0=