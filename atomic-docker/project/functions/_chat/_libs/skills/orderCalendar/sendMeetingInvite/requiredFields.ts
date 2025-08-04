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
    {
      and: [
        { value: 'attendees', type: 'chat' },
        { value: 'attendees[].isHost', type: 'chat' },
        { value: 'attendees[].email', type: 'chat' },
      ],
    },
    { value: 'receiverTimezone', type: 'form' },
    { value: 'dayAvailabilitySummary', type: 'form' },
  ],

  optional: [
    { value: 'description', type: 'chat' },
    { value: 'conferenceApp', type: 'chat' },
    { value: 'attendees', type: 'chat' },
    { value: 'summary', type: 'chat' },
    { value: 'notes', type: 'chat' },
    { value: 'alarms', type: 'chat' },
    { value: 'conference', type: 'chat' },
    { value: 'transparency', type: 'chat' },
    { value: 'visibility', type: 'chat' },
  ],
  dateTime: {
    required: [],
    optional: [
      {
        oneOf: [
          { value: 'duration', type: 'chat' },
          { value: 'endTime', type: 'chat' },
        ],
      },
      { value: 'recur', type: 'chat' },
      {
        oneOf: [
          { value: 'findTimeWindowStart.day', type: 'chat' },
          { value: 'findTimeWindowStart.isoWeekday', type: 'chat' },
        ],
      },
      {
        oneOf: [
          {
            and: [
              { value: 'findTimeWindowStart.hour', type: 'chat' },
              { value: 'findTimeWindowStart.minute', type: 'chat' },
            ],
          },
          { value: 'findTimeWindowStart.startTime', type: 'chat' },
        ],
      },
      {
        oneOf: [
          { value: 'findTimeWindowEnd.day', type: 'chat' },
          { value: 'findTimeWindowEnd.isoWeekday', type: 'chat' },
        ],
      },
      {
        oneOf: [
          {
            and: [
              { value: 'findTimeWindowEnd.hour', type: 'chat' },
              { value: 'findTimeWindowEnd.minute', type: 'chat' },
            ],
          },
          { value: 'findTimeWindowEnd.startTime', type: 'chat' },
        ],
      },
    ],
  },
};

export default requiredFields;
