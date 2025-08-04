export type ObjectFieldType = { value: string; type: 'chat' | 'form' };
type AndType = { and: ObjectFieldType[] };
type OneOfType = { oneOf: (AndType | ObjectFieldType)[] };

type RequiredType = OneOfType | ObjectFieldType | AndType;

type OptionalType = OneOfType | ObjectFieldType | AndType;

type RequiredFieldsType = {
  required: RequiredType[];

  optional?: OptionalType[];
  dateTime?: {
    required: RequiredType[];
    optional?: OptionalType[];
  };
  attributes?: {
    required: RequiredType[];
    optional?: OptionalType[];
  };
  queryDate?: {
    required: RequiredType[];
    optional?: OptionalType[];
  };
};

export default RequiredFieldsType;
