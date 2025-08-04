type CommonLocals = {
    displayName: string;
    locale: string;
};
export type SmsLocals = CommonLocals & {
    code: string;
};
export type EmailLocals = CommonLocals & {
    link: string;
    email: string;
    newEmail: string;
    ticket: string;
    redirectTo: string;
    serverUrl: string;
    clientUrl: string;
    [key: string]: string;
};
export declare const renderTemplate: (view: string, locals: EmailLocals | SmsLocals) => Promise<string | null>;
export {};
