const Invite = {
  title: 'Invite schema',
  version: 0,
  description: 'describes a Invite',
  primaryKey: 'id',
  type: 'object',
  properties: {
    id: {
      type: 'string',
    },
    userId: {
      type: 'string',
    },
    emails: {
      type: ['array', 'null'],
      uniqueItems: true,
      items: {
        type: 'string',
      },
    },
    phoneNumbers: {
      type: ['array', 'null'],
      uniqueItems: true,
      items: {
        type: 'string',
      },
    },
    imAddresses: {
      type: ['array', 'null'],
      uniqueItems: true,
      items: {
        type: 'string',
      },
    },
    categories: {
      type: ['array', 'null'],
      uniqueItems: true,
      items: {
        type: 'string',
      },
    },
    availableSlots: {
      type: ['array', 'null'],
      uniqueItems: true,
      items: {
        type: 'string',
      },
    },
    name: {
      type: ['string', 'null'],
    },
    eventId: {
      type: 'string',
    },
    emailId: {
      type: 'string',
    },
    contactId: {
      type: ['string', 'null'],
    },
    phoneId: {
      type: ['string', 'null'],
    },
    updatedAt: {
      type: 'string',
    },
    createdDate: {
      type: 'string',
    },
  },
  required: ['id', 'userId', 'emailId', 'updatedAt', 'createdDate'],
  indexes: ['userId', 'emailId'],
};

export default Invite;
