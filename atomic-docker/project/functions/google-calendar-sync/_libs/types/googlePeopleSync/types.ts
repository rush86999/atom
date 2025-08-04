enum PERSONMETADATAOBJECT {
  OBJECT_TYPE_UNSPECIFIED,
  PERSON,
  PAGE,
}

enum AGERANGE {
  AGE_RANGE_UNSPECIFIED,
  LESS_THAN_EIGHTEEN,
  EIGHTEEN_TO_TWENTY,
  TWENTY_ONE_OR_OLDER,
}

type PersonMetadata = {
  sources: object[];
  previousResourceNames: string[];
  linkedPeopleResourceNames: string[];
  deleted: boolean;
  objectType: PERSONMETADATAOBJECT;
};

type Name = {
  metadata: FieldMetadata;
  displayName: string;
  displayNameLastFirst: string;
  unstructuredName: string;
  familyName: string;
  givenName: string;
  middleName: string;
  honorificPrefix: string;
  honorificSuffix: string;
  phoneticFullName: string;
  phoneticFamilyName: string;
  phoneticGivenName: string;
  phoneticMiddleName: string;
  phoneticHonorificPrefix: string;
  phoneticHonorificSuffix: string;
};

type FieldMetadata = {
  primary: boolean;
  sourcePrimary: boolean;
  verified: boolean;
  source: object;
};

type EmailType = 'home' | 'work' | 'other';

type EmailAddress = {
  metadata: FieldMetadata;
  value: string;
  type: EmailType;
  formattedType: string;
  displayName: string;
};

type Nickname = {
  metadata: FieldMetadata;
  value: string;
  type: string;
};

type Occupation = {
  metadata: FieldMetadata;
  value: string;
};

type DateType = {
  year: number;
  month: number;
  day: number;
};

type Organization = {
  metadata: FieldMetadata;
  type: string;
  formattedType: string;
  startDate: DateType;
  endDate: DateType;
  current: boolean;
  name: string;
  phoneticName: string;
  department: string;
  title: string;
  jobDescription: string;
  symbol: string;
  domain: string;
  location: string;
  costCenter: string;
  fullTimeEquivalentMillipercent: number;
};

type phoneType =
  | 'home'
  | 'work'
  | 'mobile'
  | 'homeFax'
  | 'workFax'
  | 'otherFax'
  | 'pager'
  | 'workMobile'
  | 'workPager'
  | 'main'
  | 'googleVoice'
  | 'other';

type PhoneNumber = {
  metadata: FieldMetadata;
  value: string;
  canonicalForm: string;
  type: phoneType;
  formattedType: string;
};

type Relation = {
  metadata: FieldMetadata;
  person: string;
  type: string;
  formattedType: string;
};

type Url = {
  metadata: FieldMetadata;
  value: string;
  type: string;
  formattedType: string;
};

type ImClient = {
  metadata: FieldMetadata;
  username: string;
  type: string;
  formattedType: string;
  protocol:
    | 'aim'
    | 'msn'
    | 'yahoo'
    | 'skype'
    | 'qq'
    | 'googleTalk'
    | 'icq'
    | 'jabber'
    | 'netMeeting';
  formattedProtocol: string;
};

type Biography = {
  metadata: FieldMetadata;
  value: string;
  contentType: 'CONTENT_TYPE_UNSPECIFIED' | 'TEXT_PLAIN' | 'TEXT_HTML';
};

type CoverPhoto = {
  metadata: FieldMetadata;
  url: string;
  default: boolean;
};

export type PersonType = {
  resourceName: string;
  etag: string;
  metadata: PersonMetadata;
  addresses: object[];
  ageRange: AGERANGE[];
  ageRanges: object[];
  biographies: Biography[];
  birthdays: object[];
  braggingRights: object[];
  calendarUrls: object[];
  clientData: object[];
  coverPhotos: CoverPhoto[];
  emailAddresses: EmailAddress[];
  events: object[];
  externalIds: object[];
  fileAses: object[];
  genders: object[];
  imClients: ImClient[];
  interests: object[];
  locales: object[];
  locations: object[];
  memberships: object[];
  miscKeywords: object[];
  names: Name[];
  nicknames: Nickname[];
  occupations: Occupation[];
  organizations: Organization[];
  phoneNumbers: PhoneNumber[];
  photos: object[];
  relations: Relation[];
  relationshipInterests: object[];
  relationshipStatuses: object[];
  residences: object[];
  sipAddresses: object[];
  skills: object[];
  taglines: object[];
  urls: Url[];
  userDefined: object[];
};

export type personListResponse = {
  connections: PersonType[];
  nextPageToken: string;
  nextSyncToken: string;
  totalPeople: number;
  totalItems: number;
};

export type EventTriggerType = {
  createdAt: string;
  id: string;
  name: string;
  resource: string;
  resourceId: string;
  updatedAt: string;
  userId: string;
};
