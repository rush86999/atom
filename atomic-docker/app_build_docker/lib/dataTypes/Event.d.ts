declare const Event: {
    title: string;
    version: number;
    description: string;
    primaryKey: string;
    type: string;
    properties: {
        id: {
            type: string;
        };
        userId: {
            type: string;
        };
        startDate: {
            type: string;
        };
        endDate: {
            type: string;
        };
        allDay: {
            type: string[];
        };
        recurrence: {
            type: string[];
            uniqueItems: boolean;
            items: {
                type: string;
            };
        };
        byWeekDay: {
            type: string[];
            uniqueItems: boolean;
            items: {
                type: string;
            };
        };
        recurrenceRule: {
            type: string[];
            properties: {
                frequency: {
                    type: string;
                };
                endDate: {
                    type: string;
                };
                occurrence: {
                    type: string;
                };
                byWeekDay: {
                    type: string[];
                    uniqueItems: boolean;
                    items: {
                        type: string;
                    };
                };
                interval: {
                    type: string;
                };
            };
        };
        location: {
            type: string[];
            properties: {
                title: {
                    type: string;
                };
                proximity: {
                    type: string;
                };
                radius: {
                    type: string;
                };
                coords: {
                    type: string;
                    properties: {
                        latitude: {
                            type: string;
                        };
                        longitude: {
                            type: string;
                        };
                    };
                };
                address: {
                    type: string;
                    properties: {
                        houseNumber: {
                            type: string;
                        };
                        prefixDirection: {
                            type: string;
                        };
                        prefixType: {
                            type: string;
                        };
                        streetName: {
                            type: string;
                        };
                        streetType: {
                            type: string;
                        };
                        suffixDirection: {
                            type: string;
                        };
                        city: {
                            type: string;
                        };
                        state: {
                            type: string;
                        };
                        postalCode: {
                            type: string;
                        };
                        country: {
                            type: string;
                        };
                    };
                };
            };
        };
        notes: {
            type: string[];
        };
        attachments: {
            type: string[];
            uniqueItems: boolean;
            items: {
                type: string;
                properties: {
                    title: {
                        type: string;
                    };
                    fileUrl: {
                        type: string;
                    };
                    mimeType: {
                        type: string;
                    };
                    iconLink: {
                        type: string;
                    };
                    fileId: {
                        type: string;
                    };
                };
            };
        };
        links: {
            type: string[];
            uniqueItems: boolean;
            items: {
                type: string;
                properties: {
                    title: {
                        type: string;
                    };
                    link: {
                        type: string;
                    };
                };
            };
        };
        timezone: {
            type: string[];
        };
        taskId: {
            type: string[];
        };
        taskType: {
            type: string[];
        };
        priority: {
            type: string;
            minimum: number;
            maximum: number;
        };
        followUpEventId: {
            type: string[];
        };
        isFollowUp: {
            type: string;
        };
        isPreEvent: {
            type: string;
        };
        isPostEvent: {
            type: string;
        };
        preEventId: {
            type: string[];
        };
        postEventId: {
            type: string[];
        };
        forEventId: {
            type: string[];
        };
        modifiable: {
            type: string;
        };
        conferenceId: {
            type: string[];
        };
        maxAttendees: {
            type: string;
        };
        attendeesOmitted: {
            type: string;
        };
        sendUpdates: {
            type: string[];
        };
        anyoneCanAddSelf: {
            type: string;
        };
        guestsCanInviteOthers: {
            type: string;
        };
        guestsCanModify: {
            type: string;
        };
        guestsCanSeeOtherGuests: {
            type: string;
        };
        locked: {
            type: string;
        };
        originalStartDate: {
            type: string[];
        };
        originalTimezone: {
            type: string[];
        };
        originalAllDay: {
            type: string;
        };
        status: {
            type: string[];
        };
        summary: {
            type: string[];
        };
        transparency: {
            type: string[];
        };
        visibility: {
            type: string[];
        };
        recurringEventId: {
            type: string[];
        };
        iCalUID: {
            type: string[];
        };
        htmlLink: {
            type: string[];
        };
        colorId: {
            type: string[];
        };
        source: {
            type: string[];
            properties: {
                url: {
                    type: string;
                };
                title: {
                    type: string;
                };
            };
        };
        creator: {
            type: string[];
            properties: {
                id: {
                    type: string;
                };
                email: {
                    type: string;
                };
                displayName: {
                    type: string;
                };
                self: {
                    type: string;
                };
            };
        };
        extendedProperties: {
            type: string[];
            properties: {
                private: {
                    type: string;
                    properties: {
                        keys: {
                            type: string;
                            uniqueItems: boolean;
                            items: {
                                type: string;
                            };
                        };
                        values: {
                            type: string;
                            uniqueItems: boolean;
                            items: {
                                type: string;
                            };
                        };
                    };
                };
                shared: {
                    type: string;
                    properties: {
                        keys: {
                            type: string;
                            uniqueItems: boolean;
                            items: {
                                type: string;
                            };
                        };
                        values: {
                            type: string;
                            uniqueItems: boolean;
                            items: {
                                type: string;
                            };
                        };
                    };
                };
            };
        };
        organizer: {
            type: string[];
            properties: {
                id: {
                    type: string;
                };
                email: {
                    type: string;
                };
                displayName: {
                    type: string;
                };
                self: {
                    type: string;
                };
            };
        };
        endTimeUnspecified: {
            type: string;
        };
        hangoutLink: {
            type: string[];
        };
        eventType: {
            type: string[];
        };
        privateCopy: {
            type: string;
        };
        calendarId: {
            type: string;
        };
        backgroundColor: {
            type: string[];
        };
        foregroundColor: {
            type: string[];
        };
        useDefaultAlarms: {
            type: string;
        };
        positiveImpactScore: {
            type: string[];
        };
        negativeImpactScore: {
            type: string[];
        };
        positiveImpactDayOfWeek: {
            type: string[];
        };
        positiveImpactTime: {
            type: string[];
            format: string;
        };
        negativeImpactDayOfWeek: {
            type: string[];
        };
        negativeImpactTime: {
            type: string[];
            format: string;
        };
        preferredDayOfWeek: {
            type: string[];
        };
        preferredTime: {
            type: string[];
            format: string;
        };
        isExternalMeeting: {
            type: string;
        };
        isExternalMeetingModifiable: {
            type: string;
        };
        isMeetingModifiable: {
            type: string;
        };
        isMeeting: {
            type: string;
        };
        dailyTaskList: {
            type: string;
        };
        weeklyTaskList: {
            type: string;
        };
        isBreak: {
            type: string;
        };
        preferredStartTimeRange: {
            type: string[];
            format: string;
        };
        preferredEndTimeRange: {
            type: string[];
            format: string;
        };
        copyAvailability: {
            type: string[];
        };
        copyTimeBlocking: {
            type: string[];
        };
        copyTimePreference: {
            type: string[];
        };
        copyReminders: {
            type: string[];
        };
        copyPriorityLevel: {
            type: string[];
        };
        copyModifiable: {
            type: string[];
        };
        copyCategories: {
            type: string[];
        };
        copyIsBreak: {
            type: string[];
        };
        timeBlocking: {
            type: string[];
            properties: {
                beforeEvent: {
                    type: string[];
                };
                afterEvent: {
                    type: string[];
                };
            };
        };
        userModifiedAvailability: {
            type: string[];
        };
        userModifiedTimeBlocking: {
            type: string[];
        };
        userModifiedTimePreference: {
            type: string[];
        };
        userModifiedReminders: {
            type: string[];
        };
        userModifiedPriorityLevel: {
            type: string[];
        };
        userModifiedCategories: {
            type: string[];
        };
        userModifiedModifiable: {
            type: string[];
        };
        userModifiedIsBreak: {
            type: string[];
        };
        softDeadline: {
            type: string[];
        };
        hardDeadline: {
            type: string[];
        };
        copyIsMeeting: {
            type: string[];
        };
        copyIsExternalMeeting: {
            type: string[];
        };
        userModifiedIsMeeting: {
            type: string[];
        };
        userModifiedIsExternalMeeting: {
            type: string[];
        };
        duration: {
            type: string[];
        };
        copyDuration: {
            type: string[];
        };
        userModifiedDuration: {
            type: string[];
        };
        method: {
            type: string[];
        };
        unlink: {
            type: string[];
        };
        copyColor: {
            type: string[];
        };
        userModifiedColor: {
            type: string[];
        };
        localSynced: {
            type: string[];
        };
        updatedAt: {
            type: string;
        };
        createdDate: {
            type: string;
        };
    };
    required: string[];
    indexes: string[];
};
export default Event;
