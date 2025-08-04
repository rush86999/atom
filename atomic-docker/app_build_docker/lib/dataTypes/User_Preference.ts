const User_Preference = {
  title: 'user_preference schema',
  version: 0,
  description: 'describes a user_preference',
  primaryKey: 'id',
  type: 'object',
  properties: {
    id: {
      type: 'string',
    },
    userId: {
      type: 'string',
    },
    reminders: {
      type: ['array', 'null'],
      uniqueItems: true,
      items: {
        type: 'number',
      },
    },
    followUp: {
      type: ['array', 'null'],
      uniqueItems: true,
      items: {
        type: 'number',
      },
    },
    isPublicCalendar: {
      type: 'boolean',
    },
    publicCalendarCategories: {
      type: ['array', 'null'],
      uniqueItems: true,
      items: {
        type: 'string',
      },
    },
    startTimes: {
      type: ['array', 'null'],
      uniqueItems: true,
      items: {
        type: 'object',
        properties: {
          day: {
            type: 'number',
          },
          hour: {
            type: 'number',
          },
          minutes: {
            type: 'number',
          },
        },
      },
    },
    endTimes: {
      type: ['array', 'null'],
      uniqueItems: true,
      items: {
        type: 'object',
        properties: {
          day: {
            type: 'number',
          },
          hour: {
            type: 'number',
          },
          minutes: {
            type: 'number',
          },
        },
      },
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
    maxWorkLoadPercent: {
      type: ['number', 'null'],
    },
    backToBackMeetings: {
      type: ['boolean', 'null'],
    },
    maxNumberOfMeeting: {
      type: ['number', 'null'],
    },
    minNumberOfBreaks: {
      type: ['number', 'null'],
    },
    breakLength: {
      type: ['number', 'null'],
    },
    breakColor: {
      type: ['string', 'null'],
    },
    copyIsMeeting: {
      type: ['number', 'null'],
    },
    copyIsExternalMeeting: {
      type: ['number', 'null'],
    },
    copyColor: {
      type: ['boolean', 'null'],
    },
    onBoarded: {
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
  indexes: ['userId'],
};

export default User_Preference;
