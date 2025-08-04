import RequiredFieldsType from '@chat/_libs/types/RequiredFieldsType';

// userId and timezone are already provided

const requiredFields: RequiredFieldsType = {
  required: [
    {
      oneOf: [
        { value: 'title', type: 'chat' },
        { value: 'summary', type: 'chat' },
      ],
    },
  ],

  optional: [
    { value: 'priority', type: 'chat' },
    { value: 'timePreferences', type: 'chat' },
    { value: 'description', type: 'chat' },
    { value: 'bufferTime', type: 'chat' },
    { value: 'notes', type: 'chat' },
    { value: 'summary', type: 'chat' },
    { value: 'alarms', type: 'chat' },
    { value: 'transparency', type: 'chat' },
    { value: 'visibility', type: 'chat' },
  ],
  dateTime: {
    required: [
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
    optional: [
      // 'startDate'
      {
        oneOf: [
          { value: 'duration', type: 'chat' },
          { value: 'endTime', type: 'chat' },
        ],
      },
      { value: 'recur', type: 'chat' },
    ],
  },
};

export default requiredFields;
