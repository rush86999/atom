const Calendar_Integration = {
  title: 'Calendar_Integration schema',
  version: 0,
  description: 'describes a Calendar_Integration',
  primaryKey: 'id',
  type: 'object',
  properties: {
    id: {
      type: 'string',
    },
    token: {
      type: ['string', 'null'],
    },
    refreshToken: {
      type: ['string', 'null'],
    },
    resource: {
      type: ['string', 'null'],
    },
    name: {
      type: ['string', 'null'],
    },
    enabled: {
      type: 'boolean',
    },
    syncEnabled: {
      type: 'boolean',
    },
    expiresAt: {
      type: ['string', 'null'],
    },
    pageToken: {
      type: ['string', 'null'],
    },
    syncToken: {
      type: ['string', 'null'],
    },
    appId: {
      type: ['string', 'null'],
    },
    appEmail: {
      type: ['string', 'null'],
    },
    appAccountId: {
      type: ['string', 'null'],
    },
    contactName: {
      type: ['string', 'null'],
    },
    contactEmail: {
      type: ['string', 'null'],
    },
    colors: {
      type: ['array', 'null'],
      uniqueItems: true,
      items: {
        type: 'object',
        properties: {
          id: {
            type: 'string',
          },
          background: {
            type: 'string',
          },
          foreground: {
            type: 'string',
          },
          itemType: {
            type: 'string',
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
    userId: {
      type: 'string',
    },
  },
  required: [
    'resource',
    'name',
    'enabled',
    'updatedAt',
    'createdDate',
    'userId',
  ],
  indexes: ['userId'],
};

export default Calendar_Integration;
