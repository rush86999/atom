"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
// json schema
const Event = {
    title: 'Event schema',
    version: 0,
    description: 'describes an event',
    primaryKey: 'id',
    type: 'object',
    properties: {
        id: {
            type: 'string',
        },
        userId: {
            type: 'string',
        },
        startDate: {
            type: 'string',
        },
        endDate: {
            type: 'string',
        },
        allDay: {
            type: ['boolean', 'null'],
        },
        recurrence: {
            type: ['array', 'null'],
            uniqueItems: true,
            items: {
                type: 'string',
            },
        },
        byWeekDay: {
            type: ['array', 'null'],
            uniqueItems: true,
            items: {
                type: 'string',
            },
        },
        recurrenceRule: {
            type: ['object', 'null'],
            properties: {
                frequency: {
                    type: 'string',
                },
                endDate: {
                    type: 'string',
                },
                occurrence: {
                    type: 'number',
                },
                byWeekDay: {
                    type: ['array', 'null'],
                    uniqueItems: true,
                    items: {
                        type: 'string',
                    },
                },
                interval: {
                    type: 'number',
                },
            },
        },
        location: {
            type: ['object', 'string'],
            properties: {
                title: {
                    type: 'string',
                },
                proximity: {
                    type: 'string',
                },
                radius: {
                    type: 'number',
                },
                coords: {
                    type: 'object',
                    properties: {
                        latitude: {
                            type: 'number',
                        },
                        longitude: {
                            type: 'number',
                        },
                    },
                },
                address: {
                    type: 'object',
                    properties: {
                        houseNumber: {
                            type: 'number',
                        },
                        prefixDirection: {
                            type: 'string',
                        },
                        prefixType: {
                            type: 'string',
                        },
                        streetName: {
                            type: 'string',
                        },
                        streetType: {
                            type: 'string',
                        },
                        suffixDirection: {
                            type: 'string',
                        },
                        city: {
                            type: 'string',
                        },
                        state: {
                            type: 'string',
                        },
                        postalCode: {
                            type: 'string',
                        },
                        country: {
                            type: 'string',
                        },
                    },
                },
            },
        },
        notes: {
            type: ['string', 'null'],
        },
        attachments: {
            type: ['array', 'null'],
            uniqueItems: true,
            items: {
                type: 'object',
                properties: {
                    title: {
                        type: 'string',
                    },
                    fileUrl: {
                        type: 'string',
                    },
                    mimeType: {
                        type: 'string',
                    },
                    iconLink: {
                        type: 'string',
                    },
                    fileId: {
                        type: 'string',
                    },
                },
            },
        },
        links: {
            type: ['array', 'null'],
            uniqueItems: true,
            items: {
                type: 'object',
                properties: {
                    title: {
                        type: 'string',
                    },
                    link: {
                        type: 'string',
                    },
                },
            },
        },
        timezone: {
            type: ['string', 'null'],
        },
        taskId: {
            type: ['string', 'null'],
        },
        taskType: {
            type: ['string', 'null'],
        },
        priority: {
            type: 'number',
            minimum: 1,
            maximum: 10,
        },
        followUpEventId: {
            type: ['string', 'null'],
        },
        isFollowUp: {
            type: 'boolean',
        },
        isPreEvent: {
            type: 'boolean',
        },
        isPostEvent: {
            type: 'boolean',
        },
        preEventId: {
            type: ['string', 'null'],
        },
        postEventId: {
            type: ['string', 'null'],
        },
        forEventId: {
            type: ['string', 'null'],
        },
        modifiable: {
            type: 'boolean',
        },
        conferenceId: {
            type: ['string', 'null'],
        },
        maxAttendees: {
            type: 'number',
        },
        attendeesOmitted: {
            type: 'boolean',
        },
        sendUpdates: {
            type: ['string', 'null'],
        },
        anyoneCanAddSelf: {
            type: 'boolean',
        },
        guestsCanInviteOthers: {
            type: 'boolean',
        },
        guestsCanModify: {
            type: 'boolean',
        },
        guestsCanSeeOtherGuests: {
            type: 'boolean',
        },
        locked: {
            type: 'boolean',
        },
        originalStartDate: {
            type: ['string', 'null'],
        },
        originalTimezone: {
            type: ['string', 'null'],
        },
        originalAllDay: {
            type: 'boolean',
        },
        status: {
            type: ['string', 'null'],
        },
        summary: {
            type: ['string', 'null'],
        },
        transparency: {
            type: ['string', 'null'],
        },
        visibility: {
            type: ['string', 'null'],
        },
        recurringEventId: {
            type: ['string', 'null'],
        },
        iCalUID: {
            type: ['string', 'null'],
        },
        htmlLink: {
            type: ['string', 'null'],
        },
        colorId: {
            type: ['string', 'null'],
        },
        source: {
            type: ['object', 'null'],
            properties: {
                url: {
                    type: 'string',
                },
                title: {
                    type: 'string',
                },
            },
        },
        creator: {
            type: ['object', 'null'],
            properties: {
                id: {
                    type: 'string',
                },
                email: {
                    type: 'string',
                },
                displayName: {
                    type: 'string',
                },
                self: {
                    type: 'boolean',
                },
            },
        },
        extendedProperties: {
            type: ['object', 'null'],
            properties: {
                private: {
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
                shared: {
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
        organizer: {
            type: ['object', 'null'],
            properties: {
                id: {
                    type: 'string',
                },
                email: {
                    type: 'string',
                },
                displayName: {
                    type: 'string',
                },
                self: {
                    type: 'boolean',
                },
            },
        },
        endTimeUnspecified: {
            type: 'boolean',
        },
        hangoutLink: {
            type: ['string', 'null'],
        },
        eventType: {
            type: ['string', 'null'],
        },
        privateCopy: {
            type: 'boolean',
        },
        calendarId: {
            type: 'string',
        },
        backgroundColor: {
            type: ['string', 'null'],
        },
        foregroundColor: {
            type: ['string', 'null'],
        },
        useDefaultAlarms: {
            type: 'boolean',
        },
        positiveImpactScore: {
            type: ['number', 'null'],
        },
        negativeImpactScore: {
            type: ['number', 'null'],
        },
        positiveImpactDayOfWeek: {
            type: ['number', 'null'],
        },
        positiveImpactTime: {
            type: ['string', 'null'],
            format: 'time',
        },
        negativeImpactDayOfWeek: {
            type: ['number', 'null'],
        },
        negativeImpactTime: {
            type: ['string', 'null'],
            format: 'time',
        },
        preferredDayOfWeek: {
            type: ['number', 'null'],
        },
        preferredTime: {
            type: ['string', 'null'],
            format: 'time',
        },
        isExternalMeeting: {
            type: 'boolean',
        },
        isExternalMeetingModifiable: {
            type: 'boolean',
        },
        isMeetingModifiable: {
            type: 'boolean',
        },
        isMeeting: {
            type: 'boolean',
        },
        dailyTaskList: {
            type: 'boolean',
        },
        weeklyTaskList: {
            type: 'boolean',
        },
        isBreak: {
            type: 'boolean',
        },
        preferredStartTimeRange: {
            type: ['string', 'null'],
            format: 'time',
        },
        preferredEndTimeRange: {
            type: ['string', 'null'],
            format: 'time',
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
        timeBlocking: {
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
        userModifiedAvailability: {
            type: ['boolean', 'null'],
        },
        userModifiedTimeBlocking: {
            type: ['boolean', 'null'],
        },
        userModifiedTimePreference: {
            type: ['boolean', 'null'],
        },
        userModifiedReminders: {
            type: ['boolean', 'null'],
        },
        userModifiedPriorityLevel: {
            type: ['boolean', 'null'],
        },
        userModifiedCategories: {
            type: ['boolean', 'null'],
        },
        userModifiedModifiable: {
            type: ['boolean', 'null'],
        },
        userModifiedIsBreak: {
            type: ['boolean', 'null'],
        },
        softDeadline: {
            type: ['string', 'null'],
        },
        hardDeadline: {
            type: ['string', 'null'],
        },
        copyIsMeeting: {
            type: ['boolean', 'null'],
        },
        copyIsExternalMeeting: {
            type: ['boolean', 'null'],
        },
        userModifiedIsMeeting: {
            type: ['boolean', 'null'],
        },
        userModifiedIsExternalMeeting: {
            type: ['boolean', 'null'],
        },
        duration: {
            type: ['number', 'null'],
        },
        copyDuration: {
            type: ['boolean', 'null'],
        },
        userModifiedDuration: {
            type: ['boolean', 'null'],
        },
        method: {
            type: ['string', 'null'],
        },
        unlink: {
            type: ['boolean', 'null'],
        },
        copyColor: {
            type: ['boolean', 'null'],
        },
        userModifiedColor: {
            type: ['boolean', 'null'],
        },
        localSynced: {
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
    indexes: ['userId', 'startDate'],
};
exports.default = Event;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiRXZlbnQuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJFdmVudC50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOztBQUFBLGNBQWM7QUFDZCxNQUFNLEtBQUssR0FBRztJQUNaLEtBQUssRUFBRSxjQUFjO0lBQ3JCLE9BQU8sRUFBRSxDQUFDO0lBQ1YsV0FBVyxFQUFFLG9CQUFvQjtJQUNqQyxVQUFVLEVBQUUsSUFBSTtJQUNoQixJQUFJLEVBQUUsUUFBUTtJQUNkLFVBQVUsRUFBRTtRQUNWLEVBQUUsRUFBRTtZQUNGLElBQUksRUFBRSxRQUFRO1NBQ2Y7UUFDRCxNQUFNLEVBQUU7WUFDTixJQUFJLEVBQUUsUUFBUTtTQUNmO1FBQ0QsU0FBUyxFQUFFO1lBQ1QsSUFBSSxFQUFFLFFBQVE7U0FDZjtRQUNELE9BQU8sRUFBRTtZQUNQLElBQUksRUFBRSxRQUFRO1NBQ2Y7UUFDRCxNQUFNLEVBQUU7WUFDTixJQUFJLEVBQUUsQ0FBQyxTQUFTLEVBQUUsTUFBTSxDQUFDO1NBQzFCO1FBQ0QsVUFBVSxFQUFFO1lBQ1YsSUFBSSxFQUFFLENBQUMsT0FBTyxFQUFFLE1BQU0sQ0FBQztZQUN2QixXQUFXLEVBQUUsSUFBSTtZQUNqQixLQUFLLEVBQUU7Z0JBQ0wsSUFBSSxFQUFFLFFBQVE7YUFDZjtTQUNGO1FBQ0QsU0FBUyxFQUFFO1lBQ1QsSUFBSSxFQUFFLENBQUMsT0FBTyxFQUFFLE1BQU0sQ0FBQztZQUN2QixXQUFXLEVBQUUsSUFBSTtZQUNqQixLQUFLLEVBQUU7Z0JBQ0wsSUFBSSxFQUFFLFFBQVE7YUFDZjtTQUNGO1FBQ0QsY0FBYyxFQUFFO1lBQ2QsSUFBSSxFQUFFLENBQUMsUUFBUSxFQUFFLE1BQU0sQ0FBQztZQUN4QixVQUFVLEVBQUU7Z0JBQ1YsU0FBUyxFQUFFO29CQUNULElBQUksRUFBRSxRQUFRO2lCQUNmO2dCQUNELE9BQU8sRUFBRTtvQkFDUCxJQUFJLEVBQUUsUUFBUTtpQkFDZjtnQkFDRCxVQUFVLEVBQUU7b0JBQ1YsSUFBSSxFQUFF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QVMsRUFBRSxNQUFNLENBQUM7U0FDMUI7UUFDRCxTQUFTLEVBQUU7WUFDVCxJQUFJLEVBQUUsQ0FBQyxTQUFTLEVBQUUsTUFBTSxDQUFDO1NBQzFCO1FBQ0QsaUJBQWlCLEVBQUU7WUFDakIsSUFBSSxFQUFFLENBQUMsU0FBUyxFQUFFLE1BQU0sQ0FBQztTQUMxQjtRQUNELFdBQVcsRUFBRTtZQUNYLElBQUksRUFBRSxDQUFDLFNBQVMsRUFBRSxNQUFNLENBQUM7U0FDMUI7UUFDRCxTQUFTLEVBQUU7WUFDVCxJQUFJLEVBQUUsUUFBUTtTQUNmO1FBQ0QsV0FBVyxFQUFFO1lBQ1gsSUFBSSxFQUFFLFFBQVE7U0FDZjtLQUNGO0lBQ0QsUUFBUSxFQUFFLENBQUMsSUFBSSxFQUFFLFFBQVEsRUFBRSxXQUFXLEVBQUUsYUFBYSxDQUFDO0lBQ3RELE9BQU8sRUFBRSxDQUFDLFFBQVEsRUFBRSxXQUFXLENBQUM7Q0FDakMsQ0FBQztBQUVGLGtCQUFlLEtBQUssQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbIi8vIGpzb24gc2NoZW1hXG5jb25zdCBFdmVudCA9IHtcbiAgdGl0bGU6ICdFdmVudCBzY2hlbWEnLFxuICB2ZXJzaW9uOiAwLFxuICBkZXNjcmlwdGlvbjogJ2Rlc2NyaWJlcyBhbiBldmVudCcsXG4gIHByaW1hcnlLZXk6ICdpZCcsXG4gIHR5cGU6ICdvYmplY3QnLFxuICBwcm9wZXJ0aWVzOiB7XG4gICAgaWQ6IHtcbiAgICAgIHR5cGU6ICdzdHJpbmcnLFxuICAgIH0sXG4gICAgdXNlcklkOiB7XG4gICAgICB0eXBlOiAnc3RyaW5nJyxcbiAgICB9LFxuICAgIHN0YXJ0RGF0ZToge1xuICAgICAgdHlwZTogJ3N0cmluZycsXG4gICAgfSxcbiAgICBlbmREYXRlOiB7XG4gICAgICB0eXBlOiAnc3RyaW5nJyxcbiAgICB9LFxuICAgIGFsbERheToge1xuICAgICAgdHlwZTogWydib29sZWFuJywgJ251bGwnXSxcbiAgICB9LFxuICAgIHJlY3VycmVuY2U6IHtcbiAgICAgIHR5cGU6IFsnYXJyYXknLCAnbnVsbCddLFxuICAgICAgdW5pcXVlSXRlbXM6IHRydWUsXG4gICAgICBpdGVtczoge1xuICAgICAgICB0eXBlOiAnc3RyaW5nJyxcbiAgICAgIH0sXG4gICAgfSxcbiAgICBieVdlZWtEYXk6IHtcbiAgICAgIHR5cGU6IFsnYXJyYXknLCAnbnVsbCddLFxuICAgICAgdW5pcXVlSXRlbXM6IHRydWUsXG4gICAgICBpdGVtczoge1xuICAgICAgICB0eXBlOiAnc3RyaW5nJyxcbiAgICAgIH0sXG4gICAgfSxcbiAgICByZWN1cnJlbmNlUnVsZToge1xuICAgICAgdHlwZTogWydvYmplY3QnLCAnbnVsbCddLFxuICAgICAgcHJvcGVydGllczoge1xuICAgICAgICBmcmVxdWVuY3k6IHtcbiAgICAgICAgICB0eXBlOiAnc3RyaW5nJyxcbiAgICAgICAgfSxcbiAgICAgICAgZW5kRGF0ZToge1xuICAgICAgICAgIHR5cGU6ICdzdHJpbmcnLFxuICAgICAgICB9LFxuICAgICAgICBvY2N1cnJlbmNlOiB7XG4gICAgICAgICAgdHlwZTogJ251bWJlcicsXG4gICAgICAgIH0sXG4gICAgICAgIGJ5V2Vla0RheToge1xuICAgICAgICAgIHR5cGU6IFsnYXJyYXknLCAnbnVsbCddLFxuICAgICAgICAgIHVuaXF1ZUl0ZW1zOiB0cnVlLFxuICAgICAgICAgIGl0ZW1zOiB7XG4gICAgICAgICAgICB0eXBlOiAnc3RyaW5nJyxcbiAgICAgICAgICB9LFxuICAgICAgICB9LFxuICAgICAgICBpbnRlcnZhbDoge1xuICAgICAgICAgIHR5cGU6ICdudW1iZXInLFxuICAgICAgICB9LFxuICAgICAgfSxcbiAgICB9LFxuICAgIGxvY2F0aW9uOiB7XG4gICAgICB0eXBlOiBbJ29iamVjdCcsICdzdHJpbmcnXSxcbiAgICAgIHByb3BlcnRpZXM6IHtcbiAgICAgICAgdGl0bGU6IHtcbiAgICAgICAgICB0eXBlOiAnc3RyaW5nJyxcbiAgICAgICAgfSxcbiAgICAgICAgcHJveGltaXR5OiB7XG4gICAgICAgICAgdHlwZTogJ3N0cmluZycsXG4gICAgICAgIH0sXG4gICAgICAgIHJhZGl1czoge1xuICAgICAgICAgIHR5cGU6ICdudW1iZXInLFxuICAgICAgICB9LFxuICAgICAgICBjb29yZHM6IHtcbiAgICAgICAgICB0eXBlOiAnb2JqZWN0JyxcbiAgICAgICAgICBwcm9wZXJ0aWVzOiB7XG4gICAgICAgICAgICBsYXRpdHVkZToge1xuICAgICAgICAgICAgICB0eXBlOiAnbnVtYmVyJyxcbiAgICAgICAgICAgIH0sXG4gICAgICAgICAgICBsb25naXR1ZGU6IHtcbiAgICAgICAgICAgICAgdHlwZTogJ251bWJlcicsXG4gICAgICAgICAgICB9LFxuICAgICAgICAgIH0sXG4gICAgICAgIH0sXG4gICAgICAgIGFkZHJlc3M6IHtcbiAgICAgICAgICB0eXBlOiAnb2JqZWN0JyxcbiAgICAgICAgICBwcm9wZXJ0aWVzOiB7XG4gICAgICAgICAgICBob3VzZU51bWJlcjoge1xuICAgICAgICAgICAgICB0eXBlOiAnbnVtYmVyJyxcbiAgICAgICAgICAgIH0sXG4gICAgICAgICAgICBwcmVmaXhEaXJlY3Rpb246IHtcbiAgICAgICAgICAgICAgdHlwZTogJ3N0cmluZycsXG4gICAgICAgICAgICB9LFxuICAgICAgICAgICAgcHJlZml4VHlwZToge1xuICAgICAgICAgICAgICB0eXBlOiAnc3RyaW5nJyxcbiAgICAgICAgICAgIH0sXG4gICAgICAgICAgICBzdHJlZXROYW1lOiB7XG4gICAgICAgICAgICAgIHR5cGU6ICdzdHJpbmcnLFxuICAgICAgICAgICAgfSxcbiAgICAgICAgICAgIHN0cmVldFR5cGU6IHtcbiAgICAgICAgICAgICAgdHlwZTogJ3N0cmluZycsXG4gICAgICAgICAgICB9LFxuICAgICAgICAgICAgc3VmZml4RGlyZWN0aW9uOiB7XG4gICAgICAgICAgICAgIHR5cGU6ICdzdHJpbmcnLFxuICAgICAgICAgICAgfSxcbiAgICAgICAgICAgIGNpdHk6IHtcbiAgICAgICAgICAgICAgdHlwZTogJ3N0cmluZycsXG4gICAgICAgICAgICB9LFxuICAgICAgICAgICAgc3RhdGU6IHtcbiAgICAgICAgICAgICAgdHlwZTogJ3N0cmluZycsXG4gICAgICAgICAgICB9LFxuICAgICAgICAgICAgcG9zdGFsQ29kZToge1xuICAgICAgICAgICAgICB0eXBlOiAnc3RyaW5nJyxcbiAgICAgICAgICAgIH0sXG4gICAgICAgICAgICBjb3VudHJ5OiB7XG4gICAgICAgICAgICAgIHR5cGU6ICdzdHJpbmcnLFxuICAgICAgICAgICAgfSxcbiAgICAgICAgICB9LFxuICAgICAgICB9LFxuICAgICAgfSxcbiAgICB9LFxuICAgIG5vdGVzOiB7XG4gICAgICB0eXBlOiBbJ3N0cmluZycsICdudWxsJ10sXG4gICAgfSxcbiAgICBhdHRhY2htZW50czoge1xuICAgICAgdHlwZTogWydhcnJheScsICdudWxsJ10sXG4gICAgICB1bmlxdWVJdGVtczogdHJ1ZSxcbiAgICAgIGl0ZW1zOiB7XG4gICAgICAgIHR5cGU6ICdvYmplY3QnLFxuICAgICAgICBwcm9wZXJ0aWVzOiB7XG4gICAgICAgICAgdGl0bGU6IHtcbiAgICAgICAgICAgIHR5cGU6ICdzdHJpbmcnLFxuICAgICAgICAgIH0sXG4gICAgICAgICAgZmlsZVVybDoge1xuICAgICAgICAgICAgdHlwZTogJ3N0cmluZycsXG4gICAgICAgICAgfSxcbiAgICAgICAgICBtaW1lVHlwZToge1xuICAgICAgICAgICAgdHlwZTogJ3N0cmluZycsXG4gICAgICAgICAgfSxcbiAgICAgICAgICBpY29uTGluazoge1xuICAgICAgICAgICAgdHlwZTogJ3N0cmluZycsXG4gICAgICAgICAgfSxcbiAgICAgICAgICBmaWxlSWQ6IHtcbiAgICAgICAgICAgIHR5cGU6ICdzdHJpbmcnLFxuICAgICAgICAgIH0sXG4gICAgICAgIH0sXG4gICAgICB9LFxuICAgIH0sXG4gICAgbGlua3M6IHtcbiAgICAgIHR5cGU6IFsnYXJyYXknLCAnbnVsbCddLFxuICAgICAgdW5pcXVlSXRlbXM6IHRydWUsXG4gICAgICBpdGVtczoge1xuICAgICAgICB0eXBlOiAnb2JqZWN0JyxcbiAgICAgICAgcHJvcGVydGllczoge1xuICAgICAgICAgIHRpdGxlOiB7XG4gICAgICAgICAgICB0eXBlOiAnc3RyaW5nJyxcbiAgICAgICAgICB9LFxuICAgICAgICAgIGxpbms6IHtcbiAgICAgICAgICAgIHR5cGU6ICdzdHJpbmcnLFxuICAgICAgICAgIH0sXG4gICAgICAgIH0sXG4gICAgICB9LFxuICAgIH0sXG4gICAgdGltZXpvbmU6IHtcbiAgICAgIHR5cGU6IFsnc3RyaW5nJywgJ251bGwnXSxcbiAgICB9LFxuICAgIHRhc2tJZDoge1xuICAgICAgdHlwZTogWydzdHJpbmcnLCAnbnVsbCddLFxuICAgIH0sXG4gICAgdGFza1R5cGU6IHtcbiAgICAgIHR5cGU6IFsnc3RyaW5nJywgJ251bGwnXSxcbiAgICB9LFxuICAgIHByaW9yaXR5OiB7XG4gICAgICB0eXBlOiAnbnVtYmVyJyxcbiAgICAgIG1pbmltdW06IDEsXG4gICAgICBtYXhpbXVtOiAxMCxcbiAgICB9LFxuICAgIGZvbGxvd1VwRXZlbnRJZDoge1xuICAgICAgdHlwZTogWydzdHJpbmcnLCAnbnVsbCddLFxuICAgIH0sXG4gICAgaXNGb2xsb3dVcDoge1xuICAgICAgdHlwZTogJ2Jvb2xlYW4nLFxuICAgIH0sXG4gICAgaXNQcmVFdmVudDoge1xuICAgICAgdHlwZTogJ2Jvb2xlYW4nLFxuICAgIH0sXG4gICAgaXNQb3N0RXZlbnQ6IHtcbiAgICAgIHR5cGU6ICdib29sZWFuJyxcbiAgICB9LFxuICAgIHByZUV2ZW50SWQ6IHtcbiAgICAgIHR5cGU6IFsnc3RyaW5nJywgJ251bGwnXSxcbiAgICB9LFxuICAgIHBvc3RFdmVudElkOiB7XG4gICAgICB0eXBlOiBbJ3N0cmluZycsICdudWxsJ10sXG4gICAgfSxcbiAgICBmb3JFdmVudElkOiB7XG4gICAgICB0eXBlOiBbJ3N0cmluZycsICdudWxsJ10sXG4gICAgfSxcbiAgICBtb2RpZmlhYmxlOiB7XG4gICAgICB0eXBlOiAnYm9vbGVhbicsXG4gICAgfSxcbiAgICBjb25mZXJlbmNlSWQ6IHtcbiAgICAgIHR5cGU6IFsnc3RyaW5nJywgJ251bGwnXSxcbiAgICB9LFxuICAgIG1heEF0dGVuZGVlczoge1xuICAgICAgdHlwZTogJ251bWJlcicsXG4gICAgfSxcbiAgICBhdHRlbmRlZXNPbWl0dGVkOiB7XG4gICAgICB0eXBlOiAnYm9vbGVhbicsXG4gICAgfSxcbiAgICBzZW5kVXBkYXRlczoge1xuICAgICAgdHlwZTogWydzdHJpbmcnLCAnbnVsbCddLFxuICAgIH0sXG4gICAgYW55b25lQ2FuQWRkU2VsZjoge1xuICAgICAgdHlwZTogJ2Jvb2xlYW4nLFxuICAgIH0sXG4gICAgZ3Vlc3RzQ2FuSW52aXRlT3RoZXJzOiB7XG4gICAgICB0eXBlOiAnYm9vbGVhbicsXG4gICAgfSxcbiAgICBndWVzdHNDYW5Nb2RpZnk6IHtcbiAgICAgIHR5cGU6ICdib29sZWFuJyxcbiAgICB9LFxuICAgIGd1ZXN0c0NhblNlZU90aGVyR3Vlc3RzOiB7XG4gICAgICB0eXBlOiAnYm9vbGVhbicsXG4gICAgfSxcbiAgICBsb2NrZWQ6IHtcbiAgICAgIHR5cGU6ICdib29sZWFuJyxcbiAgICB9LFxuICAgIG9yaWdpbmFsU3RhcnREYXRlOiB7XG4gICAgICB0eXBlOiBbJ3N0cmluZycsICdudWxsJ10sXG4gICAgfSxcbiAgICBvcmlnaW5hbFRpbWV6b25lOiB7XG4gICAgICB0eXBlOiBbJ3N0cmluZycsICdudWxsJ10sXG4gICAgfSxcbiAgICBvcmlnaW5hbEFsbERheToge1xuICAgICAgdHlwZTogJ2Jvb2xlYW4nLFxuICAgIH0sXG4gICAgc3RhdHVzOiB7XG4gICAgICB0eXBlOiBbJ3N0cmluZycsICdudWxsJ10sXG4gICAgfSxcbiAgICBzdW1tYXJ5OiB7XG4gICAgICB0eXBlOiBbJ3N0cmluZycsICdudWxsJ10sXG4gICAgfSxcbiAgICB0cmFuc3BhcmVuY3k6IHtcbiAgICAgIHR5cGU6IFsnc3RyaW5nJywgJ251bGwnXSxcbiAgICB9LFxuICAgIHZpc2liaWxpdHk6IHtcbiAgICAgIHR5cGU6IFsnc3RyaW5nJywgJ251bGwnXSxcbiAgICB9LFxuICAgIHJlY3VycmluZ0V2ZW50SWQ6IHtcbiAgICAgIHR5cGU6IFsnc3RyaW5nJywgJ251bGwnXSxcbiAgICB9LFxuICAgIGlDYWxVSUQ6IHtcbiAgICAgIHR5cGU6IFsnc3RyaW5nJywgJ251bGwnXSxcbiAgICB9LFxuICAgIGh0bWxMaW5rOiB7XG4gICAgICB0eXBlOiBbJ3N0cmluZycsICdudWxsJ10sXG4gICAgfSxcbiAgICBjb2xvcklkOiB7XG4gICAgICB0eXBlOiBbJ3N0cmluZycsICdudWxsJ10sXG4gICAgfSxcbiAgICBzb3VyY2U6IHtcbiAgICAgIHR5cGU6IFsnb2JqZWN0JywgJ251bGwnXSxcbiAgICAgIHByb3BlcnRpZXM6IHtcbiAgICAgICAgdXJsOiB7XG4gICAgICAgICAgdHlwZTogJ3N0cmluZycsXG4gICAgICAgIH0sXG4gICAgICAgIHRpdGxlOiB7XG4gICAgICAgICAgdHlwZTogJ3N0cmluZycsXG4gICAgICAgIH0sXG4gICAgICB9LFxuICAgIH0sXG4gICAgY3JlYXRvcjoge1xuICAgICAgdHlwZTogWydvYmplY3QnLCAnbnVsbCddLFxuICAgICAgcHJvcGVydGllczoge1xuICAgICAgICBpZDoge1xuICAgICAgICAgIHR5cGU6ICdzdHJpbmcnLFxuICAgICAgICB9LFxuICAgICAgICBlbWFpbDoge1xuICAgICAgICAgIHR5cGU6ICdzdHJpbmcnLFxuICAgICAgICB9LFxuICAgICAgICBkaXNwbGF5TmFtZToge1xuICAgICAgICAgIHR5cGU6ICdzdHJpbmcnLFxuICAgICAgICB9LFxuICAgICAgICBzZWxmOiB7XG4gICAgICAgICAgdHlwZTogJ2Jvb2xlYW4nLFxuICAgICAgICB9LFxuICAgICAgfSxcbiAgICB9LFxuICAgIGV4dGVuZGVkUHJvcGVydGllczoge1xuICAgICAgdHlwZTogWydvYmplY3QnLCAnbnVsbCddLFxuICAgICAgcHJvcGVydGllczoge1xuICAgICAgICBwcml2YXRlOiB7XG4gICAgICAgICAgdHlwZTogJ29iamVjdCcsXG4gICAgICAgICAgcHJvcGVydGllczoge1xuICAgICAgICAgICAga2V5czoge1xuICAgICAgICAgICAgICB0eXBlOiAnYXJyYXknLFxuICAgICAgICAgICAgICB1bmlxdWVJdGVtczogdHJ1ZSxcbiAgICAgICAgICAgICAgaXRlbXM6IHtcbiAgICAgICAgICAgICAgICB0eXBlOiAnc3RyaW5nJyxcbiAgICAgICAgICAgICAgfSxcbiAgICAgICAgICAgIH0sXG4gICAgICAgICAgICB2YWx1ZXM6IHtcbiAgICAgICAgICAgICAgdHlwZTogJ2FycmF5JyxcbiAgICAgICAgICAgICAgdW5pcXVlSXRlbXM6IHRydWUsXG4gICAgICAgICAgICAgIGl0ZW1zOiB7XG4gICAgICAgICAgICAgICAgdHlwZTogJ3N0cmluZycsXG4gICAgICAgICAgICAgIH0sXG4gICAgICAgICAgICB9LFxuICAgICAgICAgIH0sXG4gICAgICAgIH0sXG4gICAgICAgIHNoYXJlZDoge1xuICAgICAgICAgIHR5cGU6ICdvYmplY3QnLFxuICAgICAgICAgIHByb3BlcnRpZXM6IHtcbiAgICAgICAgICAgIGtleXM6IHtcbiAgICAgICAgICAgICAgdHlwZTogJ2FycmF5JyxcbiAgICAgICAgICAgICAgdW5pcXVlSXRlbXM6IHRydWUsXG4gICAgICAgICAgICAgIGl0ZW1zOiB7XG4gICAgICAgICAgICAgICAgdHlwZTogJ3N0cmluZycsXG4gICAgICAgICAgICAgIH0sXG4gICAgICAgICAgICB9LFxuICAgICAgICAgICAgdmFsdWVzOiB7XG4gICAgICAgICAgICAgIHR5cGU6ICdhcnJheScsXG4gICAgICAgICAgICAgIHVuaXF1ZUl0ZW1zOiB0cnVlLFxuICAgICAgICAgICAgICBpdGVtczoge1xuICAgICAgICAgICAgICAgIHR5cGU6ICdzdHJpbmcnLFxuICAgICAgICAgICAgICB9LFxuICAgICAgICAgICAgfSxcbiAgICAgICAgICB9LFxuICAgICAgICB9LFxuICAgICAgfSxcbiAgICB9LFxuICAgIG9yZ2FuaXplcjoge1xuICAgICAgdHlwZTogWydvYmplY3QnLCAnbnVsbCddLFxuICAgICAgcHJvcGVydGllczoge1xuICAgICAgICBpZDoge1xuICAgICAgICAgIHR5cGU6ICdzdHJpbmcnLFxuICAgICAgICB9LFxuICAgICAgICBlbWFpbDoge1xuICAgICAgICAgIHR5cGU6ICdzdHJpbmcnLFxuICAgICAgICB9LFxuICAgICAgICBkaXNwbGF5TmFtZToge1xuICAgICAgICAgIHR5cGU6ICdzdHJpbmcnLFxuICAgICAgICB9LFxuICAgICAgICBzZWxmOiB7XG4gICAgICAgICAgdHlwZTogJ2Jvb2xlYW4nLFxuICAgICAgICB9LFxuICAgICAgfSxcbiAgICB9LFxuICAgIGVuZFRpbWVVbnNwZWNpZmllZDoge1xuICAgICAgdHlwZTogJ2Jvb2xlYW4nLFxuICAgIH0sXG4gICAgaGFuZ291dExpbms6IHtcbiAgICAgIHR5cGU6IFsnc3RyaW5nJywgJ251bGwnXSxcbiAgICB9LFxuICAgIGV2ZW50VHlwZToge1xuICAgICAgdHlwZTogWydzdHJpbmcnLCAnbnVsbCddLFxuICAgIH0sXG4gICAgcHJpdmF0ZUNvcHk6IHtcbiAgICAgIHR5cGU6ICdib29sZWFuJyxcbiAgICB9LFxuICAgIGNhbGVuZGFySWQ6IHtcbiAgICAgIHR5cGU6ICdzdHJpbmcnLFxuICAgIH0sXG4gICAgYmFja2dyb3VuZENvbG9yOiB7XG4gICAgICB0eXBlOiBbJ3N0cmluZycsICdudWxsJ10sXG4gICAgfSxcbiAgICBmb3JlZ3JvdW5kQ29sb3I6IHtcbiAgICAgIHR5cGU6IFsnc3RyaW5nJywgJ251bGwnXSxcbiAgICB9LFxuICAgIHVzZURlZmF1bHRBbGFybXM6IHtcbiAgICAgIHR5cGU6ICdib29sZWFuJyxcbiAgICB9LFxuICAgIHBvc2l0aXZlSW1wYWN0U2NvcmU6IHtcbiAgICAgIHR5cGU6IFsnbnVtYmVyJywgJ251bGwnXSxcbiAgICB9LFxuICAgIG5lZ2F0aXZlSW1wYWN0U2NvcmU6IHtcbiAgICAgIHR5cGU6IFsnbnVtYmVyJywgJ251bGwnXSxcbiAgICB9LFxuICAgIHBvc2l0aXZlSW1wYWN0RGF5T2ZXZWVrOiB7XG4gICAgICB0eXBlOiBbJ251bWJlcicsICdudWxsJ10sXG4gICAgfSxcbiAgICBwb3NpdGl2ZUltcGFjdFRpbWU6IHtcbiAgICAgIHR5cGU6IFsnc3RyaW5nJywgJ251bGwnXSxcbiAgICAgIGZvcm1hdDogJ3RpbWUnLFxuICAgIH0sXG4gICAgbmVnYXRpdmVJbXBhY3REYXlPZldlZWs6IHtcbiAgICAgIHR5cGU6IFsnbnVtYmVyJywgJ251bGwnXSxcbiAgICB9LFxuICAgIG5lZ2F0aXZlSW1wYWN0VGltZToge1xuICAgICAgdHlwZTogWydzdHJpbmcnLCAnbnVsbCddLFxuICAgICAgZm9ybWF0OiAndGltZScsXG4gICAgfSxcbiAgICBwcmVmZXJyZWREYXlPZldlZWs6IHtcbiAgICAgIHR5cGU6IFsnbnVtYmVyJywgJ251bGwnXSxcbiAgICB9LFxuICAgIHByZWZlcnJlZFRpbWU6IHtcbiAgICAgIHR5cGU6IFsnc3RyaW5nJywgJ251bGwnXSxcbiAgICAgIGZvcm1hdDogJ3RpbWUnLFxuICAgIH0sXG4gICAgaXNFeHRlcm5hbE1lZXRpbmc6IHtcbiAgICAgIHR5cGU6ICdib29sZWFuJyxcbiAgICB9LFxuICAgIGlzRXh0ZXJuYWxNZWV0aW5nTW9kaWZpYWJsZToge1xuICAgICAgdHlwZTogJ2Jvb2xlYW4nLFxuICAgIH0sXG4gICAgaXNNZWV0aW5nTW9kaWZpYWJsZToge1xuICAgICAgdHlwZTogJ2Jvb2xlYW4nLFxuICAgIH0sXG4gICAgaXNNZWV0aW5nOiB7XG4gICAgICB0eXBlOiAnYm9vbGVhbicsXG4gICAgfSxcbiAgICBkYWlseVRhc2tMaXN0OiB7XG4gICAgICB0eXBlOiAnYm9vbGVhbicsXG4gICAgfSxcbiAgICB3ZWVrbHlUYXNrTGlzdDoge1xuICAgICAgdHlwZTogJ2Jvb2xlYW4nLFxuICAgIH0sXG4gICAgaXNCcmVhazoge1xuICAgICAgdHlwZTogJ2Jvb2xlYW4nLFxuICAgIH0sXG4gICAgcHJlZmVycmVkU3RhcnRUaW1lUmFuZ2U6IHtcbiAgICAgIHR5cGU6IFsnc3RyaW5nJywgJ251bGwnXSxcbiAgICAgIGZvcm1hdDogJ3RpbWUnLFxuICAgIH0sXG4gICAgcHJlZmVycmVkRW5kVGltZVJhbmdlOiB7XG4gICAgICB0eXBlOiBbJ3N0cmluZycsICdudWxsJ10sXG4gICAgICBmb3JtYXQ6ICd0aW1lJyxcbiAgICB9LFxuICAgIGNvcHlBdmFpbGFiaWxpdHk6IHtcbiAgICAgIHR5cGU6IFsnYm9vbGVhbicsICdudWxsJ10sXG4gICAgfSxcbiAgICBjb3B5VGltZUJsb2NraW5nOiB7XG4gICAgICB0eXBlOiBbJ2Jvb2xlYW4nLCAnbnVsbCddLFxuICAgIH0sXG4gICAgY29weVRpbWVQcmVmZXJlbmNlOiB7XG4gICAgICB0eXBlOiBbJ2Jvb2xlYW4nLCAnbnVsbCddLFxuICAgIH0sXG4gICAgY29weVJlbWluZGVyczoge1xuICAgICAgdHlwZTogWydib29sZWFuJywgJ251bGwnXSxcbiAgICB9LFxuICAgIGNvcHlQcmlvcml0eUxldmVsOiB7XG4gICAgICB0eXBlOiBbJ2Jvb2xlYW4nLCAnbnVsbCddLFxuICAgIH0sXG4gICAgY29weU1vZGlmaWFibGU6IHtcbiAgICAgIHR5cGU6IFsnYm9vbGVhbicsICdudWxsJ10sXG4gICAgfSxcbiAgICBjb3B5Q2F0ZWdvcmllczoge1xuICAgICAgdHlwZTogWydib29sZWFuJywgJ251bGwnXSxcbiAgICB9LFxuICAgIGNvcHlJc0JyZWFrOiB7XG4gICAgICB0eXBlOiBbJ2Jvb2xlYW4nLCAnbnVsbCddLFxuICAgIH0sXG4gICAgdGltZUJsb2NraW5nOiB7XG4gICAgICB0eXBlOiBbJ29iamVjdCcsICdudWxsJ10sXG4gICAgICBwcm9wZXJ0aWVzOiB7XG4gICAgICAgIGJlZm9yZUV2ZW50OiB7XG4gICAgICAgICAgdHlwZTogWydudW1iZXInLCAnbnVsbCddLFxuICAgICAgICB9LFxuICAgICAgICBhZnRlckV2ZW50OiB7XG4gICAgICAgICAgdHlwZTogWydudW1iZXInLCAnbnVsbCddLFxuICAgICAgICB9LFxuICAgICAgfSxcbiAgICB9LFxuICAgIHVzZXJNb2RpZmllZEF2YWlsYWJpbGl0eToge1xuICAgICAgdHlwZTogWydib29sZWFuJywgJ251bGwnXSxcbiAgICB9LFxuICAgIHVzZXJNb2RpZmllZFRpbWVCbG9ja2luZzoge1xuICAgICAgdHlwZTogWydib29sZWFuJywgJ251bGwnXSxcbiAgICB9LFxuICAgIHVzZXJNb2RpZmllZFRpbWVQcmVmZXJlbmNlOiB7XG4gICAgICB0eXBlOiBbJ2Jvb2xlYW4nLCAnbnVsbCddLFxuICAgIH0sXG4gICAgdXNlck1vZGlmaWVkUmVtaW5kZXJzOiB7XG4gICAgICB0eXBlOiBbJ2Jvb2xlYW4nLCAnbnVsbCddLFxuICAgIH0sXG4gICAgdXNlck1vZGlmaWVkUHJpb3JpdHlMZXZlbDoge1xuICAgICAgdHlwZTogWydib29sZWFuJywgJ251bGwnXSxcbiAgICB9LFxuICAgIHVzZXJNb2RpZmllZENhdGVnb3JpZXM6IHtcbiAgICAgIHR5cGU6IFsnYm9vbGVhbicsICdudWxsJ10sXG4gICAgfSxcbiAgICB1c2VyTW9kaWZpZWRNb2RpZmlhYmxlOiB7XG4gICAgICB0eXBlOiBbJ2Jvb2xlYW4nLCAnbnVsbCddLFxuICAgIH0sXG4gICAgdXNlck1vZGlmaWVkSXNCcmVhazoge1xuICAgICAgdHlwZTogWydib29sZWFuJywgJ251bGwnXSxcbiAgICB9LFxuICAgIHNvZnREZWFkbGluZToge1xuICAgICAgdHlwZTogWydzdHJpbmcnLCAnbnVsbCddLFxuICAgIH0sXG4gICAgaGFyZERlYWRsaW5lOiB7XG4gICAgICB0eXBlOiBbJ3N0cmluZycsICdudWxsJ10sXG4gICAgfSxcbiAgICBjb3B5SXNNZWV0aW5nOiB7XG4gICAgICB0eXBlOiBbJ2Jvb2xlYW4nLCAnbnVsbCddLFxuICAgIH0sXG4gICAgY29weUlzRXh0ZXJuYWxNZWV0aW5nOiB7XG4gICAgICB0eXBlOiBbJ2Jvb2xlYW4nLCAnbnVsbCddLFxuICAgIH0sXG4gICAgdXNlck1vZGlmaWVkSXNNZWV0aW5nOiB7XG4gICAgICB0eXBlOiBbJ2Jvb2xlYW4nLCAnbnVsbCddLFxuICAgIH0sXG4gICAgdXNlck1vZGlmaWVkSXNFeHRlcm5hbE1lZXRpbmc6IHtcbiAgICAgIHR5cGU6IFsnYm9vbGVhbicsICdudWxsJ10sXG4gICAgfSxcbiAgICBkdXJhdGlvbjoge1xuICAgICAgdHlwZTogWydudW1iZXInLCAnbnVsbCddLFxuICAgIH0sXG4gICAgY29weUR1cmF0aW9uOiB7XG4gICAgICB0eXBlOiBbJ2Jvb2xlYW4nLCAnbnVsbCddLFxuICAgIH0sXG4gICAgdXNlck1vZGlmaWVkRHVyYXRpb246IHtcbiAgICAgIHR5cGU6IFsnYm9vbGVhbicsICdudWxsJ10sXG4gICAgfSxcbiAgICBtZXRob2Q6IHtcbiAgICAgIHR5cGU6IFsnc3RyaW5nJywgJ251bGwnXSxcbiAgICB9LFxuICAgIHVubGluazoge1xuICAgICAgdHlwZTogWydib29sZWFuJywgJ251bGwnXSxcbiAgICB9LFxuICAgIGNvcHlDb2xvcjoge1xuICAgICAgdHlwZTogWydib29sZWFuJywgJ251bGwnXSxcbiAgICB9LFxuICAgIHVzZXJNb2RpZmllZENvbG9yOiB7XG4gICAgICB0eXBlOiBbJ2Jvb2xlYW4nLCAnbnVsbCddLFxuICAgIH0sXG4gICAgbG9jYWxTeW5jZWQ6IHtcbiAgICAgIHR5cGU6IFsnYm9vbGVhbicsICdudWxsJ10sXG4gICAgfSxcbiAgICB1cGRhdGVkQXQ6IHtcbiAgICAgIHR5cGU6ICdzdHJpbmcnLFxuICAgIH0sXG4gICAgY3JlYXRlZERhdGU6IHtcbiAgICAgIHR5cGU6ICdzdHJpbmcnLFxuICAgIH0sXG4gIH0sXG4gIHJlcXVpcmVkOiBbJ2lkJywgJ3VzZXJJZCcsICd1cGRhdGVkQXQnLCAnY3JlYXRlZERhdGUnXSxcbiAgaW5kZXhlczogWyd1c2VySWQnLCAnc3RhcnREYXRlJ10sXG59O1xuXG5leHBvcnQgZGVmYXVsdCBFdmVudDtcbiJdfQ==