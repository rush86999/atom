"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const Contact_Event = {
    title: 'Contact_Event schema',
    version: 0,
    description: 'describes a Contact_Event',
    primaryKey: 'id',
    type: 'object',
    properties: {
        id: {
            type: 'string',
        },
        contactId: {
            type: 'string',
        },
        eventId: {
            type: 'string',
        },
        userId: {
            type: 'string',
        },
        updatedAt: {
            type: 'string',
        },
        createdDate: {
            type: 'string',
        },
    },
    required: ['contactId', 'eventId', 'userId', 'updatedAt', 'createdDate'],
    indexes: [
        ['contactId', 'eventId'],
        ['eventId', 'contactId'],
    ],
};
exports.default = Contact_Event;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiQ29udGFjdF9FdmVudC5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbIkNvbnRhY3RfRXZlbnQudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7QUFBQSxNQUFNLGFBQWEsR0FBRztJQUNwQixLQUFLLEVBQUUsc0JBQXNCO0lBQzdCLE9BQU8sRUFBRSxDQUFDO0lBQ1YsV0FBVyxFQUFFLDJCQUEyQjtJQUN4QyxVQUFVLEVBQUUsSUFBSTtJQUNoQixJQUFJLEVBQUUsUUFBUTtJQUNkLFVBQVUsRUFBRTtRQUNWLEVBQUUsRUFBRTtZQUNGLElBQUksRUFBRSxRQUFRO1NBQ2Y7UUFDRCxTQUFTLEVBQUU7WUFDVCxJQUFJLEVBQUUsUUFBUTtTQUNmO1FBQ0QsT0FBTyxFQUFFO1lBQ1AsSUFBSSxFQUFFLFFBQVE7U0FDZjtRQUNELE1BQU0sRUFBRTtZQUNOLElBQUksRUFBRSxRQUFRO1NBQ2Y7UUFDRCxTQUFTLEVBQUU7WUFDVCxJQUFJLEVBQUUsUUFBUTtTQUNmO1FBQ0QsV0FBVyxFQUFFO1lBQ1gsSUFBSSxFQUFFLFFBQVE7U0FDZjtLQUNGO0lBQ0QsUUFBUSxFQUFFLENBQUMsV0FBVyxFQUFFLFNBQVMsRUFBRSxRQUFRLEVBQUUsV0FBVyxFQUFFLGFBQWEsQ0FBQztJQUN4RSxPQUFPLEVBQUU7UUFDUCxDQUFDLFdBQVcsRUFBRSxTQUFTLENBQUM7UUFDeEIsQ0FBQyxTQUFTLEVBQUUsV0FBVyxDQUFDO0tBQ3pCO0NBQ0YsQ0FBQztBQUVGLGtCQUFlLGFBQWEsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImNvbnN0IENvbnRhY3RfRXZlbnQgPSB7XG4gIHRpdGxlOiAnQ29udGFjdF9FdmVudCBzY2hlbWEnLFxuICB2ZXJzaW9uOiAwLFxuICBkZXNjcmlwdGlvbjogJ2Rlc2NyaWJlcyBhIENvbnRhY3RfRXZlbnQnLFxuICBwcmltYXJ5S2V5OiAnaWQnLFxuICB0eXBlOiAnb2JqZWN0JyxcbiAgcHJvcGVydGllczoge1xuICAgIGlkOiB7XG4gICAgICB0eXBlOiAnc3RyaW5nJyxcbiAgICB9LFxuICAgIGNvbnRhY3RJZDoge1xuICAgICAgdHlwZTogJ3N0cmluZycsXG4gICAgfSxcbiAgICBldmVudElkOiB7XG4gICAgICB0eXBlOiAnc3RyaW5nJyxcbiAgICB9LFxuICAgIHVzZXJJZDoge1xuICAgICAgdHlwZTogJ3N0cmluZycsXG4gICAgfSxcbiAgICB1cGRhdGVkQXQ6IHtcbiAgICAgIHR5cGU6ICdzdHJpbmcnLFxuICAgIH0sXG4gICAgY3JlYXRlZERhdGU6IHtcbiAgICAgIHR5cGU6ICdzdHJpbmcnLFxuICAgIH0sXG4gIH0sXG4gIHJlcXVpcmVkOiBbJ2NvbnRhY3RJZCcsICdldmVudElkJywgJ3VzZXJJZCcsICd1cGRhdGVkQXQnLCAnY3JlYXRlZERhdGUnXSxcbiAgaW5kZXhlczogW1xuICAgIFsnY29udGFjdElkJywgJ2V2ZW50SWQnXSxcbiAgICBbJ2V2ZW50SWQnLCAnY29udGFjdElkJ10sXG4gIF0sXG59O1xuXG5leHBvcnQgZGVmYXVsdCBDb250YWN0X0V2ZW50O1xuIl19