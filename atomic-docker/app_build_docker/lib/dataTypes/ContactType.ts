export type ContactEmailType = {
  primary: boolean;
  value: string;
  type?: string;
  displayName?: string;
};

export type ContactPhoneType = {
  primary: boolean;
  value: string;
  type?: string;
};

export type ImAddressType = {
  primary: boolean;
  username: string;
  service: string;
  type?: string;
};

export type linkAddress = {
  primary: boolean;
  value: string;
  type?: string;
};

export type ContactType = {
  id: string;
  userId: string;
  name?: string;
  firstName?: string;
  middleName?: string;
  lastName?: string;
  maidenName?: string;
  namePrefix?: string;
  nameSuffix?: string;
  nickname?: string;
  phoneticFirstName?: string;
  phoneticMiddleName?: string;
  phoneticLastName?: string;
  company?: string;
  jobTitle?: string;
  department?: string;
  notes?: string;
  imageAvailable: boolean;
  contactType?: string;
  emails?: ContactEmailType[];
  phoneNumbers?: ContactPhoneType[];
  imAddresses?: ImAddressType[];
  linkAddresses?: linkAddress[];
  app?: string;
  updatedAt: string;
  createdDate: string;
  deleted: boolean;
};
