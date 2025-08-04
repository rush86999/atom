"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const User = {
    title: 'User schema',
    version: 0,
    description: 'describes a User',
    primaryKey: 'id',
    type: 'object',
    properties: {
        id: {
            type: 'string',
        },
        email: {
            type: 'string',
        },
        name: {
            type: ['string', 'null'],
        },
        updatedAt: {
            type: 'string',
        },
        createdDate: {
            type: 'string',
        },
    },
    required: ['id', 'updatedAt', 'createdDate'],
};
exports.default = User;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiVXNlci5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbIlVzZXIudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7QUFBQSxNQUFNLElBQUksR0FBRztJQUNYLEtBQUssRUFBRSxhQUFhO0lBQ3BCLE9BQU8sRUFBRSxDQUFDO0lBQ1YsV0FBVyxFQUFFLGtCQUFrQjtJQUMvQixVQUFVLEVBQUUsSUFBSTtJQUNoQixJQUFJLEVBQUUsUUFBUTtJQUNkLFVBQVUsRUFBRTtRQUNWLEVBQUUsRUFBRTtZQUNGLElBQUksRUFBRSxRQUFRO1NBQ2Y7UUFDRCxLQUFLLEVBQUU7WUFDTCxJQUFJLEVBQUUsUUFBUTtTQUNmO1FBQ0QsSUFBSSxFQUFFO1lBQ0osSUFBSSxFQUFFLENBQUMsUUFBUSxFQUFFLE1BQU0sQ0FBQztTQUN6QjtRQUNELFNBQVMsRUFBRTtZQUNULElBQUksRUFBRSxRQUFRO1NBQ2Y7UUFDRCxXQUFXLEVBQUU7WUFDWCxJQUFJLEVBQUUsUUFBUTtTQUNmO0tBQ0Y7SUFDRCxRQUFRLEVBQUUsQ0FBQyxJQUFJLEVBQUUsV0FBVyxFQUFFLGFBQWEsQ0FBQztDQUM3QyxDQUFDO0FBRUYsa0JBQWUsSUFBSSxDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiY29uc3QgVXNlciA9IHtcbiAgdGl0bGU6ICdVc2VyIHNjaGVtYScsXG4gIHZlcnNpb246IDAsXG4gIGRlc2NyaXB0aW9uOiAnZGVzY3JpYmVzIGEgVXNlcicsXG4gIHByaW1hcnlLZXk6ICdpZCcsXG4gIHR5cGU6ICdvYmplY3QnLFxuICBwcm9wZXJ0aWVzOiB7XG4gICAgaWQ6IHtcbiAgICAgIHR5cGU6ICdzdHJpbmcnLFxuICAgIH0sXG4gICAgZW1haWw6IHtcbiAgICAgIHR5cGU6ICdzdHJpbmcnLFxuICAgIH0sXG4gICAgbmFtZToge1xuICAgICAgdHlwZTogWydzdHJpbmcnLCAnbnVsbCddLFxuICAgIH0sXG4gICAgdXBkYXRlZEF0OiB7XG4gICAgICB0eXBlOiAnc3RyaW5nJyxcbiAgICB9LFxuICAgIGNyZWF0ZWREYXRlOiB7XG4gICAgICB0eXBlOiAnc3RyaW5nJyxcbiAgICB9LFxuICB9LFxuICByZXF1aXJlZDogWydpZCcsICd1cGRhdGVkQXQnLCAnY3JlYXRlZERhdGUnXSxcbn07XG5cbmV4cG9ydCBkZWZhdWx0IFVzZXI7XG4iXX0=