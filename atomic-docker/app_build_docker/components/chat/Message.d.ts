import { UserChatType } from "@lib/dataTypes/Messaging/MessagingTypes";
import React from "react";
type Props = {
    message: UserChatType;
    isLoading?: boolean;
    formData?: React.ReactNode;
    htmlEmail?: string;
};
declare function Message({ message, isLoading, formData, htmlEmail }: Props): JSX.Element;
export default Message;
