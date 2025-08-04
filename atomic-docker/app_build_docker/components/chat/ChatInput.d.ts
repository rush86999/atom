type Props = {
    sendMessage: (text: string) => void;
    isNewSession: boolean;
    callNewSession: () => void;
};
declare const ChatInput: ({ sendMessage, isNewSession, callNewSession }: Props) => JSX.Element;
export default ChatInput;
