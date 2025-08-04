import RequiredFieldsType from '@chat/_libs/types/RequiredFieldsType';

const requiredFields: RequiredFieldsType = {
  required: [
    {
      oneOf: [
        { value: 'title', type: 'chat' },
        { value: 'summary', type: 'chat' },
      ],
    },
  ],

  optional: [{ value: 'priority', type: 'chat' }],
  dateTime: {
    required: [
      {
        oneOf: [
          { value: 'dayOfWeek', type: 'chat' },
          { value: 'timeRange', type: 'chat' },
        ],
      },
    ],
  },
};

export default requiredFields;
