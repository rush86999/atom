const User = {
  title: 'User schema',
  version: 0,
  description: 'describes a User',
  primaryKey: 'id',
  type: 'object',
  properties: {
    id: {
      type: 'string',
    },
    email: {
      type: 'string',
    },
    name: {
      type: ['string', 'null'],
    },
    updatedAt: {
      type: 'string',
    },
    createdDate: {
      type: 'string',
    },
  },
  required: ['id', 'updatedAt', 'createdDate'],
};

export default User;
