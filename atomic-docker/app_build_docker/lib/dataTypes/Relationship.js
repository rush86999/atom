"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const Relationship = {
    title: 'Relationship schema',
    version: 0,
    description: 'describes a Relationship',
    primaryKey: 'id',
    type: 'object',
    properties: {
        id: {
            type: 'string',
        },
        contactId: {
            type: 'string',
        },
        name: {
            type: 'string',
        },
        label: {
            type: 'string',
        },
        updatedAt: {
            type: 'string',
        },
        createdDate: {
            type: 'string',
        },
    },
    required: ['id', 'contactId', 'name', 'label', 'updatedAt', 'createdDate'],
    indexes: ['contactId'],
};
exports.default = Relationship;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiUmVsYXRpb25zaGlwLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsiUmVsYXRpb25zaGlwLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiI7O0FBQUEsTUFBTSxZQUFZLEdBQUc7SUFDbkIsS0FBSyxFQUFFLHFCQUFxQjtJQUM1QixPQUFPLEVBQUUsQ0FBQztJQUNWLFdBQVcsRUFBRSwwQkFBMEI7SUFDdkMsVUFBVSxFQUFFLElBQUk7SUFDaEIsSUFBSSxFQUFFLFFBQVE7SUFDZCxVQUFVLEVBQUU7UUFDVixFQUFFLEVBQUU7WUFDRixJQUFJLEVBQUUsUUFBUTtTQUNmO1FBQ0QsU0FBUyxFQUFFO1lBQ1QsSUFBSSxFQUFFLFFBQVE7U0FDZjtRQUNELElBQUksRUFBRTtZQUNKLElBQUksRUFBRSxRQUFRO1NBQ2Y7UUFDRCxLQUFLLEVBQUU7WUFDTCxJQUFJLEVBQUUsUUFBUTtTQUNmO1FBQ0QsU0FBUyxFQUFFO1lBQ1QsSUFBSSxFQUFFLFFBQVE7U0FDZjtRQUNELFdBQVcsRUFBRTtZQUNYLElBQUksRUFBRSxRQUFRO1NBQ2Y7S0FDRjtJQUNELFFBQVEsRUFBRSxDQUFDLElBQUksRUFBRSxXQUFXLEVBQUUsTUFBTSxFQUFFLE9BQU8sRUFBRSxXQUFXLEVBQUUsYUFBYSxDQUFDO0lBQzFFLE9BQU8sRUFBRSxDQUFDLFdBQVcsQ0FBQztDQUN2QixDQUFDO0FBRUYsa0JBQWUsWUFBWSxDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiY29uc3QgUmVsYXRpb25zaGlwID0ge1xuICB0aXRsZTogJ1JlbGF0aW9uc2hpcCBzY2hlbWEnLFxuICB2ZXJzaW9uOiAwLFxuICBkZXNjcmlwdGlvbjogJ2Rlc2NyaWJlcyBhIFJlbGF0aW9uc2hpcCcsXG4gIHByaW1hcnlLZXk6ICdpZCcsXG4gIHR5cGU6ICdvYmplY3QnLFxuICBwcm9wZXJ0aWVzOiB7XG4gICAgaWQ6IHtcbiAgICAgIHR5cGU6ICdzdHJpbmcnLFxuICAgIH0sXG4gICAgY29udGFjdElkOiB7XG4gICAgICB0eXBlOiAnc3RyaW5nJyxcbiAgICB9LFxuICAgIG5hbWU6IHtcbiAgICAgIHR5cGU6ICdzdHJpbmcnLFxuICAgIH0sXG4gICAgbGFiZWw6IHtcbiAgICAgIHR5cGU6ICdzdHJpbmcnLFxuICAgIH0sXG4gICAgdXBkYXRlZEF0OiB7XG4gICAgICB0eXBlOiAnc3RyaW5nJyxcbiAgICB9LFxuICAgIGNyZWF0ZWREYXRlOiB7XG4gICAgICB0eXBlOiAnc3RyaW5nJyxcbiAgICB9LFxuICB9LFxuICByZXF1aXJlZDogWydpZCcsICdjb250YWN0SWQnLCAnbmFtZScsICdsYWJlbCcsICd1cGRhdGVkQXQnLCAnY3JlYXRlZERhdGUnXSxcbiAgaW5kZXhlczogWydjb250YWN0SWQnXSxcbn07XG5cbmV4cG9ydCBkZWZhdWx0IFJlbGF0aW9uc2hpcDtcbiJdfQ==