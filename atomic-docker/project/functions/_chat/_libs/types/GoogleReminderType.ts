type OverrideType = {
  method?: 'email' | 'popup'; // reminder type
  minutes?: number;
};

export type OverrideTypes = OverrideType[];

export type GoogleReminderType = {
  overrides: OverrideTypes;
  useDefault: boolean; // use calendar defaults
};
