import { ReceiverTimezoneFormDataResponseType } from '@libs/skills/orderCalendar/generateMeetingInvite/types';
import RequiredFieldsType from '../RequiredFieldsType';
import UserInputToJSONType from '@libs/types/UserInputToJSONType';
import DateTimeJSONType from '@libs/datetime/DateTimeJSONJSONType';
export type SystemMessageType = {
    role: 'system';
    content: string;
};
export type UserMessageType = {
    role: 'user';
    content: string;
};
export type AssistantMessageType = {
    role: 'assistant';
    content: string;
};
export type MessageHistoryType = (AssistantMessageType | UserMessageType | SystemMessageType)[];
export type SkillType = 'pending' | 'ask-availability' | 'find-event' | 'find-events' | 'find-next-event' | 'add-task' | 'block-off-time' | 'cancel-meeting' | 'create-event' | 'delete-event' | 'delete-priority' | 'delete-task' | 'edit-add-preferred-time-to-preferred-times' | 'edit-event' | 'edit-remove-preferred-time-to-preferred-times' | 'find-meeting-time-with-permission' | 'generate-meeting-invite' | 'remove-all-preferred-times' | 'resolve-conflicting-events' | 'schedule-meeting' | 'send-meeting-invite' | 'update-meeting' | 'update-priority' | 'update-task';
export type SkillMessageHistoryType = {
    skill: SkillType;
    messages: MessageHistoryType;
    query: 'missing_fields' | 'completed' | 'event_not_found' | 'pending';
    required?: RequiredFieldsType;
    formData?: ReceiverTimezoneFormDataResponseType;
    prevData?: any;
    prevDataExtra?: any;
    prevJsonBody?: UserInputToJSONType;
    prevDateJsonBody?: DateTimeJSONType;
    prevDateTimeJsonBody?: any;
    htmlEmail?: string;
};
