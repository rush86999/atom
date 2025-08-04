import React from 'react';
interface ChatMessageActionsProps extends React.ComponentProps<'div'> {
    emailContent: React.MutableRefObject<HTMLDivElement>;
}
export declare function EmailContentCopy({ emailContent, className, ...props }: ChatMessageActionsProps): JSX.Element;
export {};
