"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const Conference = {
    title: 'Conference schema',
    version: 0,
    description: 'describes a Conference',
    primaryKey: 'id',
    type: 'object',
    properties: {
        id: {
            type: 'string',
        },
        userId: {
            type: 'string',
        },
        requestId: {
            type: ['string', 'null'],
        },
        type: {
            type: ['string', 'null'],
        },
        status: {
            type: ['string', 'null'],
        },
        calendarId: {
            type: 'string',
        },
        iconUri: {
            type: ['string', 'null'],
        },
        name: {
            type: ['string', 'null'],
        },
        notes: {
            type: ['string', 'null'],
        },
        entryPoints: {
            type: ['array', 'null'],
            uniqueItems: true,
            items: {
                type: 'object',
                properties: {
                    entryPointFeatures: {
                        type: 'array',
                        uniqueItems: true,
                        items: {
                            type: 'string',
                        },
                    },
                    regionCode: {
                        type: 'string',
                    },
                    entryPointType: {
                        type: 'string',
                    },
                    uri: {
                        type: 'string',
                    },
                    label: {
                        type: 'string',
                    },
                    pin: {
                        type: 'string',
                    },
                    accessCode: {
                        type: 'string',
                    },
                    meetingCode: {
                        type: 'string',
                    },
                    passcode: {
                        type: 'string',
                    },
                    password: {
                        type: 'string',
                    },
                },
            },
        },
        parameters: {
            type: ['object', 'null'],
            properties: {
                addOnParameters: {
                    type: 'object',
                    properties: {
                        parameters: {
                            type: 'array',
                            uniqueItems: true,
                            items: {
                                type: 'object',
                                properties: {
                                    keys: {
                                        type: 'array',
                                        uniqueItems: true,
                                        items: {
                                            type: 'string',
                                        },
                                    },
                                    values: {
                                        type: 'array',
                                        uniqueItems: true,
                                        items: {
                                            type: 'string',
                                        },
                                    },
                                },
                            },
                        },
                    },
                },
            },
        },
        app: {
            type: 'string',
        },
        key: {
            type: ['string', 'null'],
        },
        hangoutLink: {
            type: ['string', 'null'],
        },
        joinUrl: {
            type: ['string', 'null'],
        },
        startUrl: {
            type: ['string', 'null'],
        },
        zoomPrivateMeeting: {
            type: ['boolean', 'null'],
        },
        updatedAt: {
            type: 'string',
        },
        createdDate: {
            type: 'string',
        },
    },
    required: ['id', 'userId', 'calendarId', 'app', 'updatedAt', 'createdDate'],
    indexes: ['userId'],
};
exports.default = Conference;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiQ29uZmVyZW5jZS5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbIkNvbmZlcmVuY2UudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7QUFBQSxNQUFNLFVBQVUsR0FBRztJQUNqQixLQUFLLEVBQUUsbUJBQW1CO0lBQzFCLE9BQU8sRUFBRSxDQUFDO0lBQ1YsV0FBVyxFQUFFLHdCQUF3QjtJQUNyQyxVQUFVLEVBQUUsSUFBSTtJQUNoQixJQUFJLEVBQUUsUUFBUTtJQUNkLFVBQVUsRUFBRTtRQUNWLEVBQUUsRUFBRTtZQUNGLElBQUksRUFBRSxRQUFRO1NBQ2Y7UUFDRCxNQUFNLEVBQUU7WUFDTixJQUFJLEVBQUUsUUFBUTtTQUNmO1FBQ0QsU0FBUyxFQUFFO1lBQ1QsSUFBSSxFQUFFLENBQUMsUUFBUSxFQUFFLE1BQU0sQ0FBQztTQUN6QjtRQUNELElBQUksRUFBRTtZQUNKLElBQUksRUFBRSxDQUFDLFFBQVEsRUFBRSxNQUFNLENBQUM7U0FDekI7UUFDRCxNQUFNLEVBQUU7WUFDTixJQUFJLEVBQUUsQ0FBQyxRQUFRLEVBQUUsTUFBTSxDQUFDO1NBQ3pCO1FBQ0QsVUFBVSxFQUFFO1lBQ1YsSUFBSSxFQUFFLFFBQVE7U0FDZjtRQUNELE9BQU8sRUFBRTtZQUNQLElBQUksRUFBRSxDQUFDLFFBQVEsRUFBRSxNQUFNLENBQUM7U0FDekI7UUFDRCxJQUFJLEVBQUU7WUFDSixJQUFJLEVBQUUsQ0FBQyxRQUFRLEVBQUUsTUFBTSxDQUFDO1NBQ3pCO1FBQ0QsS0FBSyxFQUFFO1lBQ0wsSUFBSSxFQUFFLENBQUMsUUFBUSxFQUFFLE1BQU0sQ0FBQztTQUN6QjtRQUNELFdBQVcsRUFBRTtZQUNYLElBQUksRUFBRSxDQUFDLE9BQU8sRUFBRSxNQUFNLENBQUM7WUFDdkIsV0FBVyxFQUFFLElBQUk7WUFDakIsS0FBSyxFQUFFO2dCQUNMLElBQUksRUFBRSxRQUFRO2dCQUNkLFVBQVUsRUFBRTtvQkFDVixrQkFBa0IsRUFBRTt3QkFDbEIsSUFBSSxFQUFFLE9BQU87d0JBQ2IsV0FBVyxFQUFFLElBQUk7d0JBQ2pCLEtBQUssRUFBRTs0QkFDTCxJQUFJLEVBQUUsUUFBUTt5QkFDZjtxQkFDRjtvQkFDRCxVQUFVLEVBQUU7d0JBQ1YsSUFBSSxFQUFFLFFBQVE7cUJBQ2Y7b0JBQ0QsY0FBYyxFQUFFO3dCQUNkLElBQUksRUFBRSxRQUFRO3FCQUNmO29CQUNELEdBQUcsRUFBRTt3QkFDSCxJQUFJLEVBQUUsUUFBUTtxQkFDZjtvQkFDRCxLQUFLLEVBQUU7d0JBQ0wsSUFBSSxFQUFFLFFBQVE7cUJBQ2Y7b0JBQ0QsR0FBRyxFQUFFO3dCQUNILElBQUksRUFBRSxRQUFRO3FCQUNmO29CQUNELFVBQVUsRUFBRTt3QkFDVixJQUFJLEVBQUUsUUFBUTtxQkFDZjtvQkFDRCxXQUFXLEVBQUU7d0JBQ1gsSUFBSSxFQUFFLFFBQVE7cUJBQ2Y7b0JBQ0QsUUFBUSxFQUFFO3dCQUNSLElBQUksRUFBRSxRQUFRO3FCQUNmO29CQUNELFFBQVEsRUFBRTt3QkFDUixJQUFJLEVBQUUsUUFBUTtxQkFDZjtpQkFDRjthQUNGO1NBQ0Y7UUFDRCxVQUFVLEVBQUU7WUFDVixJQUFJLEVBQUUsQ0FBQyxRQUFRLEVBQUUsTUFBTSxDQUFDO1lBQ3hCLFVBQVUsRUFBRTtnQkFDVixlQUFlLEVBQUU7b0JBQ2YsSUFBSSxFQUFFLFFBQVE7b0JBQ2QsVUFBVSxFQUFFO3dCQUNWLFVBQVUsRUFBRTs0QkFDVixJQUFJLEVBQUUsT0FBTzs0QkFDYixXQUFXLEVBQUUsSUFBSTs0QkFDakIsS0FBSyxFQUFFO2dDQUNMLElBQUksRUFBRSxRQUFRO2dDQUNkLFVBQVUsRUFBRTtvQ0FDVixJQUFJLEVBQUU7d0NBQ0osSUFBSSxFQUFFLE9BQU87d0NBQ2IsV0FBVyxFQUFFLElBQUk7d0NBQ2pCLEtBQUssRUFBRTs0Q0FDTCxJQUFJLEVBQUUsUUFBUTt5Q0FDZjtxQ0FDRjtvQ0FDRCxNQUFNLEVBQUU7d0NBQ04sSUFBSSxFQUFFLE9BQU87d0NBQ2IsV0FBVyxFQUFFLElBQUk7d0NBQ2pCLEtBQUssRUFBRTs0Q0FDTCxJQUFJLEVBQUUsUUFBUTt5Q0FDZjtxQ0FDRjtpQ0FDRjs2QkFDRjt5QkFDRjtxQkFDRjtpQkFDRjthQUNGO1NBQ0Y7UUFDRCxHQUFHLEVBQUU7WUFDSCxJQUFJLEVBQUUsUUFBUTtTQUNmO1FBQ0QsR0FBRyxFQUFFO1lBQ0gsSUFBSSxFQUFFLENBQUMsUUFBUSxFQUFFLE1BQU0sQ0FBQztTQUN6QjtRQUNELFdBQVcsRUFBRTtZQUNYLElBQUksRUFBRSxDQUFDLFFBQVEsRUFBRSxNQUFNLENBQUM7U0FDekI7UUFDRCxPQUFPLEVBQUU7WUFDUCxJQUFJLEVBQUUsQ0FBQyxRQUFRLEVBQUUsTUFBTSxDQUFDO1NBQ3pCO1FBQ0QsUUFBUSxFQUFFO1lBQ1IsSUFBSSxFQUFFLENBQUMsUUFBUSxFQUFFLE1BQU0sQ0FBQztTQUN6QjtRQUNELGtCQUFrQixFQUFFO1lBQ2xCLElBQUksRUFBRSxDQUFDLFNBQVMsRUFBRSxNQUFNLENBQUM7U0FDMUI7UUFDRCxTQUFTLEVBQUU7WUFDVCxJQUFJLEVBQUUsUUFBUTtTQUNmO1FBQ0QsV0FBVyxFQUFFO1lBQ1gsSUFBSSxFQUFFLFFBQVE7U0FDZjtLQUNGO0lBQ0QsUUFBUSxFQUFFLENBQUMsSUFBSSxFQUFFLFFBQVEsRUFBRSxZQUFZLEVBQUUsS0FBSyxFQUFFLFdBQVcsRUFBRSxhQUFhLENBQUM7SUFDM0UsT0FBTyxFQUFFLENBQUMsUUFBUSxDQUFDO0NBQ3BCLENBQUM7QUFFRixrQkFBZSxVQUFVLENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJjb25zdCBDb25mZXJlbmNlID0ge1xuICB0aXRsZTogJ0NvbmZlcmVuY2Ugc2NoZW1hJyxcbiAgdmVyc2lvbjogMCxcbiAgZGVzY3JpcHRpb246ICdkZXNjcmliZXMgYSBDb25mZXJlbmNlJyxcbiAgcHJpbWFyeUtleTogJ2lkJyxcbiAgdHlwZTogJ29iamVjdCcsXG4gIHByb3BlcnRpZXM6IHtcbiAgICBpZDoge1xuICAgICAgdHlwZTogJ3N0cmluZycsXG4gICAgfSxcbiAgICB1c2VySWQ6IHtcbiAgICAgIHR5cGU6ICdzdHJpbmcnLFxuICAgIH0sXG4gICAgcmVxdWVzdElkOiB7XG4gICAgICB0eXBlOiBbJ3N0cmluZycsICdudWxsJ10sXG4gICAgfSxcbiAgICB0eXBlOiB7XG4gICAgICB0eXBlOiBbJ3N0cmluZycsICdudWxsJ10sXG4gICAgfSxcbiAgICBzdGF0dXM6IHtcbiAgICAgIHR5cGU6IFsnc3RyaW5nJywgJ251bGwnXSxcbiAgICB9LFxuICAgIGNhbGVuZGFySWQ6IHtcbiAgICAgIHR5cGU6ICdzdHJpbmcnLFxuICAgIH0sXG4gICAgaWNvblVyaToge1xuICAgICAgdHlwZTogWydzdHJpbmcnLCAnbnVsbCddLFxuICAgIH0sXG4gICAgbmFtZToge1xuICAgICAgdHlwZTogWydzdHJpbmcnLCAnbnVsbCddLFxuICAgIH0sXG4gICAgbm90ZXM6IHtcbiAgICAgIHR5cGU6IFsnc3RyaW5nJywgJ251bGwnXSxcbiAgICB9LFxuICAgIGVudHJ5UG9pbnRzOiB7XG4gICAgICB0eXBlOiBbJ2FycmF5JywgJ251bGwnXSxcbiAgICAgIHVuaXF1ZUl0ZW1zOiB0cnVlLFxuICAgICAgaXRlbXM6IHtcbiAgICAgICAgdHlwZTogJ29iamVjdCcsXG4gICAgICAgIHByb3BlcnRpZXM6IHtcbiAgICAgICAgICBlbnRyeVBvaW50RmVhdHVyZXM6IHtcbiAgICAgICAgICAgIHR5cGU6ICdhcnJheScsXG4gICAgICAgICAgICB1bmlxdWVJdGVtczogdHJ1ZSxcbiAgICAgICAgICAgIGl0ZW1zOiB7XG4gICAgICAgICAgICAgIHR5cGU6ICdzdHJpbmcnLFxuICAgICAgICAgICAgfSxcbiAgICAgICAgICB9LFxuICAgICAgICAgIHJlZ2lvbkNvZGU6IHtcbiAgICAgICAgICAgIHR5cGU6ICdzdHJpbmcnLFxuICAgICAgICAgIH0sXG4gICAgICAgICAgZW50cnlQb2ludFR5cGU6IHtcbiAgICAgICAgICAgIHR5cGU6ICdzdHJpbmcnLFxuICAgICAgICAgIH0sXG4gICAgICAgICAgdXJpOiB7XG4gICAgICAgICAgICB0eXBlOiAnc3RyaW5nJyxcbiAgICAgICAgICB9LFxuICAgICAgICAgIGxhYmVsOiB7XG4gICAgICAgICAgICB0eXBlOiAnc3RyaW5nJyxcbiAgICAgICAgICB9LFxuICAgICAgICAgIHBpbjoge1xuICAgICAgICAgICAgdHlwZTogJ3N0cmluZycsXG4gICAgICAgICAgfSxcbiAgICAgICAgICBhY2Nlc3NDb2RlOiB7XG4gICAgICAgICAgICB0eXBlOiAnc3RyaW5nJyxcbiAgICAgICAgICB9LFxuICAgICAgICAgIG1lZXRpbmdDb2RlOiB7XG4gICAgICAgICAgICB0eXBlOiAnc3RyaW5nJyxcbiAgICAgICAgICB9LFxuICAgICAgICAgIHBhc3Njb2RlOiB7XG4gICAgICAgICAgICB0eXBlOiAnc3RyaW5nJyxcbiAgICAgICAgICB9LFxuICAgICAgICAgIHBhc3N3b3JkOiB7XG4gICAgICAgICAgICB0eXBlOiAnc3RyaW5nJyxcbiAgICAgICAgICB9LFxuICAgICAgICB9LFxuICAgICAgfSxcbiAgICB9LFxuICAgIHBhcmFtZXRlcnM6IHtcbiAgICAgIHR5cGU6IFsnb2JqZWN0JywgJ251bGwnXSxcbiAgICAgIHByb3BlcnRpZXM6IHtcbiAgICAgICAgYWRkT25QYXJhbWV0ZXJzOiB7XG4gICAgICAgICAgdHlwZTogJ29iamVjdCcsXG4gICAgICAgICAgcHJvcGVydGllczoge1xuICAgICAgICAgICAgcGFyYW1ldGVyczoge1xuICAgICAgICAgICAgICB0eXBlOiAnYXJyYXknLFxuICAgICAgICAgICAgICB1bmlxdWVJdGVtczogdHJ1ZSxcbiAgICAgICAgICAgICAgaXRlbXM6IHtcbiAgICAgICAgICAgICAgICB0eXBlOiAnb2JqZWN0JyxcbiAgICAgICAgICAgICAgICBwcm9wZXJ0aWVzOiB7XG4gICAgICAgICAgICAgICAgICBrZXlzOiB7XG4gICAgICAgICAgICAgICAgICAgIHR5cGU6ICdhcnJheScsXG4gICAgICAgICAgICAgICAgICAgIHVuaXF1ZUl0ZW1zOiB0cnVlLFxuICAgICAgICAgICAgICAgICAgICBpdGVtczoge1xuICAgICAgICAgICAgICAgICAgICAgIHR5cGU6ICdzdHJpbmcnLFxuICAgICAgICAgICAgICAgICAgICB9LFxuICAgICAgICAgICAgICAgICAgfSxcbiAgICAgICAgICAgICAgICAgIHZhbHVlczoge1xuICAgICAgICAgICAgICAgICAgICB0eXBlOiAnYXJyYXknLFxuICAgICAgICAgICAgICAgICAgICB1bmlxdWVJdGVtczogdHJ1ZSxcbiAgICAgICAgICAgICAgICAgICAgaXRlbXM6IHtcbiAgICAgICAgICAgICAgICAgICAgICB0eXBlOiAnc3RyaW5nJyxcbiAgICAgICAgICAgICAgICAgICAgfSxcbiAgICAgICAgICAgICAgICAgIH0sXG4gICAgICAgICAgICAgICAgfSxcbiAgICAgICAgICAgICAgfSxcbiAgICAgICAgICAgIH0sXG4gICAgICAgICAgfSxcbiAgICAgICAgfSxcbiAgICAgIH0sXG4gICAgfSxcbiAgICBhcHA6IHtcbiAgICAgIHR5cGU6ICdzdHJpbmcnLFxuICAgIH0sXG4gICAga2V5OiB7XG4gICAgICB0eXBlOiBbJ3N0cmluZycsICdudWxsJ10sXG4gICAgfSxcbiAgICBoYW5nb3V0TGluazoge1xuICAgICAgdHlwZTogWydzdHJpbmcnLCAnbnVsbCddLFxuICAgIH0sXG4gICAgam9pblVybDoge1xuICAgICAgdHlwZTogWydzdHJpbmcnLCAnbnVsbCddLFxuICAgIH0sXG4gICAgc3RhcnRVcmw6IHtcbiAgICAgIHR5cGU6IFsnc3RyaW5nJywgJ251bGwnXSxcbiAgICB9LFxuICAgIHpvb21Qcml2YXRlTWVldGluZzoge1xuICAgICAgdHlwZTogWydib29sZWFuJywgJ251bGwnXSxcbiAgICB9LFxuICAgIHVwZGF0ZWRBdDoge1xuICAgICAgdHlwZTogJ3N0cmluZycsXG4gICAgfSxcbiAgICBjcmVhdGVkRGF0ZToge1xuICAgICAgdHlwZTogJ3N0cmluZycsXG4gICAgfSxcbiAgfSxcbiAgcmVxdWlyZWQ6IFsnaWQnLCAndXNlcklkJywgJ2NhbGVuZGFySWQnLCAnYXBwJywgJ3VwZGF0ZWRBdCcsICdjcmVhdGVkRGF0ZSddLFxuICBpbmRleGVzOiBbJ3VzZXJJZCddLFxufTtcblxuZXhwb3J0IGRlZmF1bHQgQ29uZmVyZW5jZTtcbiJdfQ==