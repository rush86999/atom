const Contact = {
  title: 'Contact schema',
  version: 0,
  description: 'describes a Contact',
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
    firstName: {
      type: ['string', 'null'],
    },
    middleName: {
      type: ['string', 'null'],
    },
    lastName: {
      type: ['string', 'null'],
    },
    maidenName: {
      type: ['string', 'null'],
    },
    namePrefix: {
      type: ['string', 'null'],
    },
    nameSuffix: {
      type: ['string', 'null'],
    },
    nickname: {
      type: ['string', 'null'],
    },
    phoneticFirstName: {
      type: ['string', 'null'],
    },
    phoneticMiddleName: {
      type: ['string', 'null'],
    },
    phoneticLastName: {
      type: ['string', 'null'],
    },
    company: {
      type: ['string', 'null'],
    },
    jobTitle: {
      type: ['string', 'null'],
    },
    department: {
      type: ['string', 'null'],
    },
    notes: {
      type: ['string', 'null'],
    },
    imageAvailable: {
      type: 'boolean',
    },
    image: {
      type: ['string', 'null'],
    },
    contactType: {
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
    linkAddresses: {
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
    app: {
      type: ['string', 'null'],
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

export default Contact;
