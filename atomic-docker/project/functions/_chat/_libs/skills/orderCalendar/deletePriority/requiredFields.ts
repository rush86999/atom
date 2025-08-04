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
};

export default requiredFields;
