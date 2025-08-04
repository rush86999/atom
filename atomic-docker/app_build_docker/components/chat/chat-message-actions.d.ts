import { UserChatType } from '@lib/dataTypes/Messaging/MessagingTypes';
interface ChatMessageActionsProps extends React.ComponentProps<'div'> {
    message: UserChatType;
}
export declare function ChatMessageActions({ message, className, ...props }: ChatMessageActionsProps): JSX.Element;
export {};
