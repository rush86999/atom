export type ColorType = {
  id: string;
  background: string;
  foreground: string;
  itemType: 'calendar' | 'event';
};

export type CalendarClientType = 'ios' | 'android' | 'web' | 'atomic-web';

export type CalendarIntegrationType = {
  id: string;
  userId: string;
  token?: string;
  refreshToken?: string;
  resource?: string;
  name?: string;
  enabled?: boolean;
  syncEnabled?: boolean;
  deleted?: boolean;
  appId?: string;
  appEmail?: string;
  appAccountId?: string;
  contactName?: string;
  contactEmail?: string;
  colors?: ColorType[];
  clientType?: CalendarClientType;
  expiresAt?: string;
  updatedAt: string;
  createdDate: string;
  pageToken?: string;
  syncToken?: string;
};
