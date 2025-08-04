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
    { value: 'conferenceApp', type: 'chat' },
    { value: 'bufferTime', type: 'chat' },
    { value: 'oldTitle', type: 'chat' },
    { value: 'attendees', type: 'chat' },
    {
      and: [
        { value: 'attendees', type: 'chat' },
        { value: 'attendees[].isHost', type: 'chat' },
        { value: 'attendees[].email', type: 'chat' },
      ],
    },
    { value: 'summary', type: 'chat' },
    { value: 'notes', type: 'chat' },
    { value: 'alarms', type: 'chat' },
    { value: 'conference', type: 'chat' },
    { value: 'transparency', type: 'chat' },
    { value: 'visibility', type: 'chat' },
    {
      and: [
        { value: 'attendees', type: 'chat' },
        { value: 'attendees[].isHost', type: 'chat' },
        { value: 'attendees[].email', type: 'chat' },
      ],
    },
  ],
  dateTime: {
    required: [
      // 'startDate'
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
