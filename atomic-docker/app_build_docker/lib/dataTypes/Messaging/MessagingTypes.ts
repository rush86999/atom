import { ReceiverTimezoneFormDataResponseType } from "./ReceiverTimezoneFormDataResponseType"
import RequiredFieldsType from "./RequiredFieldsType"

export type SystemMessageType = {
    role: 'system',
    content: string // prompt
}

export type UserMessageType = {
    role: 'user',
    content: string // user input
}

export type AssistantMessageType = {
    role: 'assistant',
    content: string // gpt output
}

export type MessageHistoryType = (AssistantMessageType | UserMessageType | SystemMessageType)[]

export type SkillType = 'pending' | 'ask-availability' | 'find-event' | 'find-events' | 'find-next-event' | 'add-task' | 'block-off-time' | 'cancel-meeting' | 'create-event' | 'delete-event' | 'delete-priority' | 'delete-task' | 'edit-add-preferred-time-to-preferred-times' | 'edit-event' | 'edit-remove-preferred-time-to-preferred-times' | 'find-meeting-time-with-permission' | 'generate-meeting-invite' | 'remove-all-preferred-times' | 'resolve-conflicting-events' | 'schedule-meeting' | 'send-meeting-invite' | 'update-meeting' | 'update-priority' | 'update-task'

export type SkillMessageHistoryType = {
    skill: SkillType,
    messages: MessageHistoryType,
    query: 'missing_fields' | 'completed' | 'event_not_found' | 'pending' | 'error',
    required?: RequiredFieldsType,
    formData?: ReceiverTimezoneFormDataResponseType,
    prevData?: any,
    prevDataExtra?: any,
    prevJsonBody?: any,
    prevDateJsonBody?: any,
    prevDateTimeJsonBody?: any,
    htmlEmail?: string,
}

export type UserChatType = {
    role: 'user' | 'assistant',
    content: string,
    id: number,
    date: string,
    audioUrl?: string; // Added for TTS audio playback
}

export type ChatHistoryType = UserChatType[]

export type SkillChatHistoryType = SkillMessageHistoryType[]

export type ChatBrainBodyType = {
    chat: SkillMessageHistoryType,
    userId: string,
    timezone: string,
    active?: boolean,
    id: string,
}



