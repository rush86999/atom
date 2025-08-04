type emailAddress = {
    label: string;
    email: string;
};
type phoneNumber = {
    label: string;
    number: string;
};
type postalAddress = {
    label: string;
    formattedAddress: string;
    street: string;
    pobox: string;
    neighborhood: string;
    city: string;
    region: string;
    state: string;
    postCode: string;
    country: string;
};
type birthday = {
    year: number;
    month: number;
    day: number;
};
type imAddress = {
    username: string;
    service: string;
};
export type LocalContact = {
    recordID: string;
    backTitle: string;
    company: string;
    emailAddresses: emailAddress[];
    familyName: string;
    givenName: string;
    middleName: string;
    jobTitle: string;
    phoneNumbers: phoneNumber[];
    hasThumbnail: boolean;
    thumbnailPath: string;
    postalAddresses: postalAddress[];
    prefix: string;
    suffix: string;
    department: string;
    birthday: birthday;
    imAddresses: imAddress[];
};
export {};
