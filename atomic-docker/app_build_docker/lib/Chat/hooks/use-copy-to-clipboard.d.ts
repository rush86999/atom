export interface useCopyToClipboardProps {
    timeout?: number;
}
export declare function useCopyToClipboard({ timeout }: useCopyToClipboardProps): {
    isCopied: Boolean;
    copyToClipboard: (value: string) => void;
};
