const Reminder = {
  title: 'Reminder schema',
  version: 0,
  description: 'describes a Reminder',
  primaryKey: 'id',
  type: 'object',
  properties: {
    id: {
      type: 'string',
    },
    eventId: {
      type: 'string',
    },
    userId: {
      type: 'string',
    },
    reminderDate: {
      type: ['string', 'null'],
    },
    timezone: {
      type: 'string',
    },
    minutes: {
      type: ['number', 'null'],
    },
    method: {
      type: 'string',
    },
    useDefault: {
      type: 'boolean',
    },
    updatedAt: {
      type: 'string',
    },
    createdDate: {
      type: 'string',
    },
  },
  required: ['id', 'eventId', 'userId', 'updatedAt', 'createdDate'],
  indexes: ['userId'],
};

export default Reminder;
