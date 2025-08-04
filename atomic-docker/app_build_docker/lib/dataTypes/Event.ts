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

export default Event;
