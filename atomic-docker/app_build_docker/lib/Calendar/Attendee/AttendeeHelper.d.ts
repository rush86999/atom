import { AttendeeEmailType, AttendeePhoneNumberType, AttendeeImAddressType } from '@lib/dataTypes/AttendeeType';
import { ApolloClient, NormalizedCacheObject } from '@apollo/client';
export declare const upsertAttendeesInDb: (client: ApolloClient<NormalizedCacheObject>, id: string, userId: string, eventId: string, emails: AttendeeEmailType[], name?: string | null, contactId?: string | null, phoneNumbers?: AttendeePhoneNumberType[] | null, imAddresses?: AttendeeImAddressType[] | null, additionalGuests?: number | null, optional?: boolean | null, resource?: boolean | null) => Promise<void>;
export declare const deleteAttendeesForEvents: (client: ApolloClient<NormalizedCacheObject>, eventIds: string[]) => Promise<void>;
export declare const deleteAttendeesForEvent: (client: ApolloClient<NormalizedCacheObject>, eventId: string) => Promise<void>;
export declare const listAttendeesForEvent: (client: ApolloClient<NormalizedCacheObject>, eventId: string) => Promise<any>;
/** end */
