const Relationship = {
  title: 'Relationship schema',
  version: 0,
  description: 'describes a Relationship',
  primaryKey: 'id',
  type: 'object',
  properties: {
    id: {
      type: 'string',
    },
    contactId: {
      type: 'string',
    },
    name: {
      type: 'string',
    },
    label: {
      type: 'string',
    },
    updatedAt: {
      type: 'string',
    },
    createdDate: {
      type: 'string',
    },
  },
  required: ['id', 'contactId', 'name', 'label', 'updatedAt', 'createdDate'],
  indexes: ['contactId'],
};

export default Relationship;
