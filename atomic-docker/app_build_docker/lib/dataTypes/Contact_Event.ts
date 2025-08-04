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

export default Contact_Event;
