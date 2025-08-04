import DateTimeJSONType from '@libs/datetime/DateTimeJSONJSONType';
import RequiredFieldsType from './RequiredFieldsType';
import UserInputToJSONType from './UserInputToJSONType';
type ResponseActionType = {
    query: 'missing_fields' | 'completed' | 'event_not_found';
    data: RequiredFieldsType | string;
    skill: string;
    prevData?: object;
    prevDataExtra?: object;
    prevJsonBody?: UserInputToJSONType;
    prevDateJsonBody?: DateTimeJSONType;
    prevDateTimeJsonBody?: any;
    htmlEmail?: string;
};
export default ResponseActionType;
