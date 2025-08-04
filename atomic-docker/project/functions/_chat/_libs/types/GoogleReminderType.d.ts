type OverrideType = {
    method?: 'email' | 'popup';
    minutes?: number;
};
export type OverrideTypes = OverrideType[];
export type GoogleReminderType = {
    overrides: OverrideTypes;
    useDefault: boolean;
};
export {};
