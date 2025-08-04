const Category = {
  title: 'Category schema',
  version: 0,
  description: 'describes a Category',
  primaryKey: 'id',
  type: 'object',
  properties: {
    id: {
      type: 'string',
    },
    userId: {
      type: 'string',
    },
    name: {
      type: 'string',
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
    defaultAvailability: {
      type: ['boolean', 'null'],
    },
    defaultTimeBlocking: {
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
    defaultTimePreference: {
      type: ['object', 'null'],
      properties: {
        preferredDayOfWeek: {
          type: ['number', 'null'],
        },
        preferredTime: {
          type: ['string', 'null'],
          format: 'time',
        },
        preferredStartTimeRange: {
          type: ['string', 'null'],
          format: 'time',
        },
        preferredEndTimeRange: {
          type: ['string', 'null'],
          format: 'time',
        },
      },
    },
    defaultReminders: {
      type: ['array', 'null'],
      uniqueItems: true,
      items: {
        type: 'number',
      },
    },
    defaultPriorityLevel: {
      type: ['number', 'null'],
    },
    defaultModifiable: {
      type: ['boolean', 'null'],
    },
    copyIsBreak: {
      type: ['boolean', 'null'],
    },
    defaultIsBreak: {
      type: ['boolean', 'null'],
    },
    color: {
      type: ['string', 'null'],
    },
    copyIsMeeting: {
      type: ['boolean', 'null'],
    },
    copyIsExternalMeeting: {
      type: ['boolean', 'null'],
    },
    defaultIsMeeting: {
      type: ['boolean', 'null'],
    },
    defaultIsExternalMeeting: {
      type: ['boolean', 'null'],
    },
    defaultMeetingModifiable: {
      type: ['boolean', 'null'],
    },
    defaultExternalMeetingModifiable: {
      type: ['boolean', 'null'],
    },
    updatedAt: {
      type: 'string',
    },
    createdDate: {
      type: 'string',
    },
  },
  required: ['id', 'name', 'updatedAt', 'createdDate'],
  indexes: ['userId'],
};

export default Category;
