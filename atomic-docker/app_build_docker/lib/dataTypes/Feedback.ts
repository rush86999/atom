const Feedback = {
  title: 'Feedback schema',
  version: 0,
  description: 'describes a Feedback',
  primaryKey: 'id',
  type: 'object',
  properties: {
    id: {
      type: 'string',
    },
    userId: {
      type: 'string',
    },
    question1_A: {
      type: 'boolean',
    },
    question1_B: {
      type: 'boolean',
    },
    question1_C: {
      type: 'boolean',
    },
    question2: {
      type: ['string', 'null'],
    },
    question3: {
      type: ['string', 'null'],
    },
    question4: {
      type: ['string', 'null'],
    },
    lastSeen: {
      type: 'string',
    },
    count: {
      type: 'number',
    },
    updatedAt: {
      type: 'string',
    },
    createdDate: {
      type: 'string',
    },
  },
  required: ['updatedAt', 'createdDate', 'userId'],
  indexes: ['userId'],
};

export default Feedback;
