const Calendar = {
  title: 'Calendar schema',
  version: 0,
  description: 'describes a Calendar',
  primaryKey: 'id',
  type: 'object',
  properties: {
    id: {
      type: 'string',
    },
    userId: {
      type: 'string',
    },
    title: {
      type: ['string', 'null'],
    },
    backgroundColor: {
      type: ['string', 'null'],
    },
    foregroundColor: {
      type: ['string', 'null'],
    },
    colorId: {
      type: ['string', 'null'],
    },
    account: {
      type: ['object', 'null'],
      properties: {
        id: {
          type: 'string',
        },
        isLocal: {
          type: 'boolean',
        },
        name: {
          type: ['string', 'null'],
        },
        type: {
          type: ['string', 'null'],
        },
      },
    },
    accessLevel: {
      type: ['string', 'null'],
    },
    resource: {
      type: ['string', 'null'],
    },
    modifiable: {
      type: 'boolean',
    },
    globalPrimary: {
      type: 'boolean',
    },
    defaultReminders: {
      type: ['array', 'null'],
      uniqueItems: true,
      items: {
        type: 'object',
        properties: {
          method: {
            type: ['string', 'null'],
          },
          minutes: {
            type: ['number', 'null'],
          },
        },
      },
    },
    updatedAt: {
      type: 'string',
    },
    createdDate: {
      type: 'string',
    },
  },
  required: ['id', 'updatedAt', 'createdDate'],
  indexes: ['userId'],
};

export default Calendar;
