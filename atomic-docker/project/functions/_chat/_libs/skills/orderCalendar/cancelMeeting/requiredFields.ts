import RequiredFieldsType from '@chat/_libs/types/RequiredFieldsType';

// userId and timezone are already provided

const requiredFields: RequiredFieldsType = {
  required: [{ value: 'title', type: 'chat' }],
  optional: [],
  dateTime: {
    required: [],
    optional: [
      {
        oneOf: [
          { value: 'duration', type: 'chat' },
          { value: 'endTime', type: 'chat' },
        ],
      },
      {
        oneOf: [
          { value: 'day', type: 'chat' },
          { value: 'isoWeekday', type: 'chat' },
        ],
      },
      {
        oneOf: [
          {
            and: [
              { value: 'hour', type: 'chat' },
              { value: 'minute', type: 'chat' },
            ],
          },
          { value: 'startTime', type: 'chat' },
        ],
      },
    ],
  },
};

export default requiredFields;
