const Category_Event = {
  title: 'Category_Event schema',
  version: 0,
  description: 'describes a Category_Event',
  primaryKey: 'id',
  type: 'object',
  properties: {
    id: {
      type: 'string',
    },
    userId: {
      type: 'string',
    },
    categoryId: {
      type: 'string',
    },
    eventId: {
      type: 'string',
    },
    updatedAt: {
      type: 'string',
    },
    createdDate: {
      type: 'string',
    },
  },
  required: [
    'id',
    'userId',
    'categoryId',
    'eventId',
    'updatedAt',
    'createdDate',
  ],
  indexes: [
    ['userId', 'categoryId', 'eventId'],
    ['userId', 'eventId', 'categoryId'],
  ],
};

export default Category_Event;
