const Conference = {
  title: 'Conference schema',
  version: 0,
  description: 'describes a Conference',
  primaryKey: 'id',
  type: 'object',
  properties: {
    id: {
      type: 'string',
    },
    userId: {
      type: 'string',
    },
    requestId: {
      type: ['string', 'null'],
    },
    type: {
      type: ['string', 'null'],
    },
    status: {
      type: ['string', 'null'],
    },
    calendarId: {
      type: 'string',
    },
    iconUri: {
      type: ['string', 'null'],
    },
    name: {
      type: ['string', 'null'],
    },
    notes: {
      type: ['string', 'null'],
    },
    entryPoints: {
      type: ['array', 'null'],
      uniqueItems: true,
      items: {
        type: 'object',
        properties: {
          entryPointFeatures: {
            type: 'array',
            uniqueItems: true,
            items: {
              type: 'string',
            },
          },
          regionCode: {
            type: 'string',
          },
          entryPointType: {
            type: 'string',
          },
          uri: {
            type: 'string',
          },
          label: {
            type: 'string',
          },
          pin: {
            type: 'string',
          },
          accessCode: {
            type: 'string',
          },
          meetingCode: {
            type: 'string',
          },
          passcode: {
            type: 'string',
          },
          password: {
            type: 'string',
          },
        },
      },
    },
    parameters: {
      type: ['object', 'null'],
      properties: {
        addOnParameters: {
          type: 'object',
          properties: {
            parameters: {
              type: 'array',
              uniqueItems: true,
              items: {
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
        },
      },
    },
    app: {
      type: 'string',
    },
    key: {
      type: ['string', 'null'],
    },
    hangoutLink: {
      type: ['string', 'null'],
    },
    joinUrl: {
      type: ['string', 'null'],
    },
    startUrl: {
      type: ['string', 'null'],
    },
    zoomPrivateMeeting: {
      type: ['boolean', 'null'],
    },
    updatedAt: {
      type: 'string',
    },
    createdDate: {
      type: 'string',
    },
  },
  required: ['id', 'userId', 'calendarId', 'app', 'updatedAt', 'createdDate'],
  indexes: ['userId'],
};

export default Conference;
