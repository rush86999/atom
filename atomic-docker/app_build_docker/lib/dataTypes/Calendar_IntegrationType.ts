export type colorType = {
  id: string;
  background: string;
  foreground: string;
  itemType: 'calendar' | 'event';
};

export type CalendarIntegrationType = {
  id: string;
  userId: string;
  token?: string;
  refreshToken?: string;
  resource?: string;
  name?: string;
  enabled?: boolean;
  syncEnabled?: boolean;
  pageToken?: string;
  syncToken?: string;
  deleted?: boolean;
  appId?: string;
  appEmail?: string;
  appAccountId?: string;
  contactName?: string;
  contactEmail?: string;
  colors?: colorType[];
  clientType?: 'ios' | 'android' | 'web' | 'atomic-web';
  expiresAt?: string;
  updatedAt: string;
  createdDate: string;
};
