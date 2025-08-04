export type AttendeeEmailType = {
  primary: boolean;
  value: string;
  type?: string;
  displayName?: string;
};

export type AttendeePhoneNumberType = {
  primary: boolean;
  value: string;
  type?: string;
};

export type AttendeeImAddressType = {
  primary: boolean;
  username: string;
  service: string;
  type?: string;
};

export type AttendeeType = {
  id: string;
  userId: string;
  name?: string;
  contactId?: string;
  emails: AttendeeEmailType[];
  phoneNumbers?: AttendeePhoneNumberType[];
  imAddresses?: AttendeeImAddressType[];
  eventId: string;
  additionalGuests?: number;
  comment?: string;
  responseStatus?: string;
  optional?: boolean;
  resource?: boolean;
  updatedAt: string;
  createdDate: string;
  deleted: boolean;
};
