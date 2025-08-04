import RequiredFieldsType from '@libs/types/RequiredFieldsType';

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
};

export default requiredFields;
