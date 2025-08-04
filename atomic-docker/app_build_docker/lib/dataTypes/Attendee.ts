const Attendee = {
  title: 'Attendee schema',
  version: 0,
  description: 'describes a Attendee',
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
      type: ['string', 'null'],
    },
    contactId: {
      type: ['string', 'null'],
    },
    emails: {
      type: ['array', 'null'],
      uniqueItems: true,
      items: {
        type: 'object',
        properties: {
          primary: {
            type: 'boolean',
          },
          value: {
            type: 'string',
          },
          type: {
            type: 'string',
          },
          displayName: {
            type: 'string',
          },
        },
      },
    },
    phoneNumbers: {
      type: ['array', 'null'],
      uniqueItems: true,
      items: {
        type: 'object',
        properties: {
          primary: {
            type: 'boolean',
          },
          value: {
            type: 'string',
          },
          type: {
            type: 'string',
          },
        },
      },
    },
    imAddresses: {
      type: ['array', 'null'],
      uniqueItems: true,
      items: {
        type: 'object',
        properties: {
          primary: {
            type: 'boolean',
          },
          username: {
            type: 'string',
          },
          service: {
            type: 'string',
          },
          type: {
            type: 'string',
          },
        },
      },
    },
    eventId: {
      type: 'string',
    },
    additionalGuests: {
      type: 'number',
    },
    comment: {
      type: ['string', 'null'],
    },
    responseStatus: {
      type: ['string', 'null'],
    },
    optional: {
      type: 'boolean',
    },
    resource: {
      type: 'boolean',
    },
    updatedAt: {
      type: 'string',
    },
    createdDate: {
      type: 'string',
    },
  },
  required: ['id', 'name', 'userId', 'eventId', 'updatedAt', 'createdDate'],
  indexes: ['userId', 'eventId'],
};

export default Attendee;
