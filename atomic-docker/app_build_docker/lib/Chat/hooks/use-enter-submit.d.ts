import { type RefObject } from 'react';
export declare function useEnterSubmit(): {
    formRef: RefObject<HTMLFormElement>;
    onKeyDown: (event: React.KeyboardEvent<HTMLTextAreaElement>) => void;
};
