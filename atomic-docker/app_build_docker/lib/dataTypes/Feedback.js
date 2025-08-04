"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const Feedback = {
    title: 'Feedback schema',
    version: 0,
    description: 'describes a Feedback',
    primaryKey: 'id',
    type: 'object',
    properties: {
        id: {
            type: 'string',
        },
        userId: {
            type: 'string',
        },
        question1_A: {
            type: 'boolean',
        },
        question1_B: {
            type: 'boolean',
        },
        question1_C: {
            type: 'boolean',
        },
        question2: {
            type: ['string', 'null'],
        },
        question3: {
            type: ['string', 'null'],
        },
        question4: {
            type: ['string', 'null'],
        },
        lastSeen: {
            type: 'string',
        },
        count: {
            type: 'number',
        },
        updatedAt: {
            type: 'string',
        },
        createdDate: {
            type: 'string',
        },
    },
    required: ['updatedAt', 'createdDate', 'userId'],
    indexes: ['userId'],
};
exports.default = Feedback;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiRmVlZGJhY2suanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJGZWVkYmFjay50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOztBQUFBLE1BQU0sUUFBUSxHQUFHO0lBQ2YsS0FBSyxFQUFFLGlCQUFpQjtJQUN4QixPQUFPLEVBQUUsQ0FBQztJQUNWLFdBQVcsRUFBRSxzQkFBc0I7SUFDbkMsVUFBVSxFQUFFLElBQUk7SUFDaEIsSUFBSSxFQUFFLFFBQVE7SUFDZCxVQUFVLEVBQUU7UUFDVixFQUFFLEVBQUU7WUFDRixJQUFJLEVBQUUsUUFBUTtTQUNmO1FBQ0QsTUFBTSxFQUFFO1lBQ04sSUFBSSxFQUFFLFFBQVE7U0FDZjtRQUNELFdBQVcsRUFBRTtZQUNYLElBQUksRUFBRSxTQUFTO1NBQ2hCO1FBQ0QsV0FBVyxFQUFFO1lBQ1gsSUFBSSxFQUFFLFNBQVM7U0FDaEI7UUFDRCxXQUFXLEVBQUU7WUFDWCxJQUFJLEVBQUUsU0FBUztTQUNoQjtRQUNELFNBQVMsRUFBRTtZQUNULElBQUksRUFBRSxDQUFDLFFBQVEsRUFBRSxNQUFNLENBQUM7U0FDekI7UUFDRCxTQUFTLEVBQUU7WUFDVCxJQUFJLEVBQUUsQ0FBQyxRQUFRLEVBQUUsTUFBTSxDQUFDO1NBQ3pCO1FBQ0QsU0FBUyxFQUFFO1lBQ1QsSUFBSSxFQUFFLENBQUMsUUFBUSxFQUFFLE1BQU0sQ0FBQztTQUN6QjtRQUNELFFBQVEsRUFBRTtZQUNSLElBQUksRUFBRSxRQUFRO1NBQ2Y7UUFDRCxLQUFLLEVBQUU7WUFDTCxJQUFJLEVBQUUsUUFBUTtTQUNmO1FBQ0QsU0FBUyxFQUFFO1lBQ1QsSUFBSSxFQUFFLFFBQVE7U0FDZjtRQUNELFdBQVcsRUFBRTtZQUNYLElBQUksRUFBRSxRQUFRO1NBQ2Y7S0FDRjtJQUNELFFBQVEsRUFBRSxDQUFDLFdBQVcsRUFBRSxhQUFhLEVBQUUsUUFBUSxDQUFDO0lBQ2hELE9BQU8sRUFBRSxDQUFDLFFBQVEsQ0FBQztDQUNwQixDQUFDO0FBRUYsa0JBQWUsUUFBUSxDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiY29uc3QgRmVlZGJhY2sgPSB7XG4gIHRpdGxlOiAnRmVlZGJhY2sgc2NoZW1hJyxcbiAgdmVyc2lvbjogMCxcbiAgZGVzY3JpcHRpb246ICdkZXNjcmliZXMgYSBGZWVkYmFjaycsXG4gIHByaW1hcnlLZXk6ICdpZCcsXG4gIHR5cGU6ICdvYmplY3QnLFxuICBwcm9wZXJ0aWVzOiB7XG4gICAgaWQ6IHtcbiAgICAgIHR5cGU6ICdzdHJpbmcnLFxuICAgIH0sXG4gICAgdXNlcklkOiB7XG4gICAgICB0eXBlOiAnc3RyaW5nJyxcbiAgICB9LFxuICAgIHF1ZXN0aW9uMV9BOiB7XG4gICAgICB0eXBlOiAnYm9vbGVhbicsXG4gICAgfSxcbiAgICBxdWVzdGlvbjFfQjoge1xuICAgICAgdHlwZTogJ2Jvb2xlYW4nLFxuICAgIH0sXG4gICAgcXVlc3Rpb24xX0M6IHtcbiAgICAgIHR5cGU6ICdib29sZWFuJyxcbiAgICB9LFxuICAgIHF1ZXN0aW9uMjoge1xuICAgICAgdHlwZTogWydzdHJpbmcnLCAnbnVsbCddLFxuICAgIH0sXG4gICAgcXVlc3Rpb24zOiB7XG4gICAgICB0eXBlOiBbJ3N0cmluZycsICdudWxsJ10sXG4gICAgfSxcbiAgICBxdWVzdGlvbjQ6IHtcbiAgICAgIHR5cGU6IFsnc3RyaW5nJywgJ251bGwnXSxcbiAgICB9LFxuICAgIGxhc3RTZWVuOiB7XG4gICAgICB0eXBlOiAnc3RyaW5nJyxcbiAgICB9LFxuICAgIGNvdW50OiB7XG4gICAgICB0eXBlOiAnbnVtYmVyJyxcbiAgICB9LFxuICAgIHVwZGF0ZWRBdDoge1xuICAgICAgdHlwZTogJ3N0cmluZycsXG4gICAgfSxcbiAgICBjcmVhdGVkRGF0ZToge1xuICAgICAgdHlwZTogJ3N0cmluZycsXG4gICAgfSxcbiAgfSxcbiAgcmVxdWlyZWQ6IFsndXBkYXRlZEF0JywgJ2NyZWF0ZWREYXRlJywgJ3VzZXJJZCddLFxuICBpbmRleGVzOiBbJ3VzZXJJZCddLFxufTtcblxuZXhwb3J0IGRlZmF1bHQgRmVlZGJhY2s7XG4iXX0=