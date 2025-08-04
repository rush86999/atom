// User Helper Module - user-related operations and utilities
import { ApolloClient, InMemoryCache, NormalizedCacheObject } from '@apollo/client';
import { UserType } from '../../types/UserType';
import { UserContactInfoType } from '../../types/UserContactInfoType';
import got from 'got';
import { postgraphileGraphUrl, postgraphileAdminSecret } from '../../constants';
import { graphileClient } from '../../graphile/client';
import { v4 as uuid } from 'uuid';

// Logger for user operations
const userLogger = {
  info: console.log.bind(console, '[UserHelpers] INFO:'),
  error: console.error.bind(console, '[UserHelpers] ERROR:'),
  warn: console.warn.bind(console, '[UserHelpers] WARN:'),
};

// GraphQL client configuration
const getGraphQLClient = (): ApolloClient<NormalizedCacheObject> => {
  return new ApolloClient({
    uri: postgraphileGraphUrl,
    cache: new InMemoryCache(),
    headers: {
      'X-Postgraphile-Admin-Secret': postgraphileAdminSecret,
      'X-Postgraphile-Role': 'admin',
    },
  });
};

// Get user by ID
export const getUserGivenId = async (userId: string): Promise<UserType | null> => {
  try {
    if (!userId) {
      userLogger.warn('User ID is required');
      return null;
    }

    const query = `
      query GetUserById($id: uuid!) {
        User_by_pk(id: $id) {
          createdDate
          deleted
          email
          id
          name
          updatedAt
          timezone
          cloneExistingEvents
          mergedOutlookEvents
          primaryEmail
          active
          defaultEndTime
        }
      }
    `;

    const result = await graphileClient.request(query, { id: userId });
    const user = result?.User_by_pk;

    if (!user) {
      userLogger.warn('User not found', { userId });
      return null;
    }

    userLogger.info('Successfully retrieved user', { userId, email: user.email });
    return user as UserType;

  } catch (error) {
    userLogger.error('Error getting user by ID:', error);
    return null;
  }
};

// Update user name by ID
export const updateUserNameGivenId = async (
  userId: string,
  name: string
): Promise<boolean> => {
  try {
    if (!userId) {
      userLogger.error('User ID is required');
      return false;
    }

    const query = `
      mutation UpdateUserName($id: uuid!, $name: String!) {
        update_User_by_pk(
          pk_columns: { id: $id }
          _set: { name: $name }
        ) {
          id
          name
          updatedAt
        }
      }
    `;

    const result = await graphileClient.request(query, { id: userId, name });

    if (result?.update_User_by_pk) {
      userLogger.info('Successfully updated user name', { userId, newName: name });
      return true;
    }

    return false;

  } catch (error) {
    userLogger.error('Error updating user name:', error);
    return false;
  }
};

// List user contact infos by user ID
export const listUserContactInfosByUserId = async (userId: string): Promise<UserContactInfoType[]> => {
  try {
    if (!userId) {
      userLogger.warn('User ID is required');
      return [];
    }

    const query = `
      query ListUserContactInfosByUserId($userId: uuid!) {
        User_Contact_Info(where: { userId: { _eq: $userId } }) {
          id
          userId
          contact
          emails
          phoneNumbers
          timezone
          updatedAt
          createdDate
          disabled
        }
      }
    `;

    const result = await graphileClient.request(query, { userId });
    const contactInfos = result?.User_Contact_Info || [];

    userLogger.info('Successfully retrieved user contact infos', {
      userId,
      count: contactInfos.length
    });

    return contactInfos as UserContactInfoType[];

  } catch (error) {
    userLogger.error('Error listing user contact infos:', error);
    return [];
  }
};

// Get multiple contact infos by IDs
export const getContactInfosByIds = async (ids: string[]): Promise<UserContactInfoType[]> => {
  try {
    if (!ids || ids.length === 0) {
      return [];
    }

    const query = `
      query GetContactInfosByIds($ids: [String!]!) {
        User_Contact_Info(where: { id: { _in: $ids } }) {
          id
          userId
          contact
          emails
          phoneNumbers
          timezone
          updatedAt
          createdDate
          disabled
        }
      }
    `;

    const result = await graphileClient.request(query, { ids });
    const contactInfos = result?.User_Contact_Info || [];

    userLogger.info('Successfully retrieved contact infos', {
      contactInfoCount: contactInfos.length,
      requestedCount: ids.length
    });

    return contactInfos as UserContactInfoType[];

  } catch (error) {
    userLogger.error('Error getting contact infos by IDs:', error);
    return [];
  }
};

// Get contact by name for a user
export const getContactByNameForUserId = async (
  userId: string,
  name: string
): Promise<UserContactInfoType | null> => {
  try {
    if (!userId || !name) {
      userLogger.warn('User ID and contact name are required');
      return null;
    }

    const query = `
      query GetContactByNameForUserId($userId: uuid!, $name: String!) {
        User_Contact_Info(
          where: {
            _and: [
              { userId: { _eq: $userId } },
n              { contact: { _ilike: $name } }
n            ]
n          }
n        ) {
n          id
n          userId
n          contact
n          emails
n          phoneNumbers
n          timezone
n          updatedAt
n          createdDate
n          disabled
n        }
n      }
n    `;

    const result = await graphileClient.request(query, {
      userId,
      name: `%${name}%`
    });

    const contacts = result?.User_Contact_Info || [];

    if (contacts.length === 0) {
      userLogger.warn('No contact found with matching name', { userId, name });
      return null;
    }

    const contact = contacts[0];
    userLogger.info('Successfully found contact', { userId, contactName: contact.contact });

    return contact as UserContactInfoType;

  } catch (error) {
    userLogger.error('Error finding contact by name:', error);
    return null;
  }
};

// Create or update user contact info
export const upsertUserContactInfo = async (
  contactInfo: Partial<UserContactInfoType>
): Promise<string | null> => {
  try {
    if (!contactInfo.userId) {
      userLogger.error('User ID is required for contact info');
      return null;
    }

    const contactInfoId = contactInfo.id || uuid();

    const query = `
      mutation UpsertUserContactInfo($contactInfo: [User_Contact_Info_insert_input!]!) {
        insert_User_Contact_Info(
          objects: $contactInfo
          on_conflict: {
            constraint: User_Contact_Info_pkey
            update_columns: [
              contact
              emails
              phoneNumbers
              timezone
              disabled
              updatedAt
            ]
          }
        ) {
          affected_rows
          returning {
            id
          }
        }
      }
    `;

    const upsertData = {
      id: contactInfoId,
      userId: contactInfo.userId,
      contact: contactInfo.contact || '',
      emails: contactInfo.emails || [],
      phoneNumbers: contactInfo.phoneNumbers || [],
      timezone: contactInfo.timezone || 'UTC',
      disabled: contactInfo.disabled || false,
      updatedAt: new Date().toISOString(),
      createdDate: new Date().toISOString(),
    };

    const result = await graphileClient.request(query, {
      contactInfo: [upsertData]
    });

    if (result?.insert_User_Contact_Info?.returning?.[0]) {
      userLogger.info('Successfully upserted user contact info', {
        userId: contactInfo.userId,
        contactInfoId,
        operation: contactInfo.id ? 'update' : 'create'
      });

      return contactInfoId;
    }

    return null;

  } catch (error) {
    userLogger.error('Error upserting user contact info:', error);
    return null;
  }
};

// Check if user exists by user ID
export const checkUserExists = async (userId: string): Promise<boolean> => {
  try {
    if (!userId) {
      return false;
    }

    const query = `
      query CheckUserExists($id: uuid!) {
        User_by_pk(id: $id) {
          id
        }
      }
    `;

    const result = await graphileClient.request(query, { id: userId });

    return !!result?.User_by_pk;

  } catch (error) {
    userLogger.error('Error checking user existence:', error);
    return false;
  }
};

// Get user preferences
export const getUserPreferences = async (userId: string): Promise<any> => {
  try {
    if (!userId) {
      userLogger.warn('User ID is required for preferences');
n      return null;
    }

    const query = `
      query GetUserPreferences($userId: uuid!) {
        User_Preference(where: { userId: { _eq: $userId } }) {
          id
          userId
          timezone
          defaultStartTime
          defaultEndTime
          copyAvailability
          copyTimeBlocking
          copyTimePreference
          copyReminders
          copyPriorityLevel
          copyModifiable
          followUp
          isPublicBooker
          publicBookerCategories
          createdDate
          updatedAt
        }
      }
    `;

    const result = await graphileClient.request(query, { userId });
    const preferences = result?.User_Preference || [];

    return preferences.length > 0 ? preferences[0] : null;

  } catch (error) {
    userLogger.error('Error getting user preferences:', error);
    return null;
  }
};

export default {
  getUserGivenId,
  updateUserNameGivenId,
  listUserContactInfosByUserId,
  getContactInfosByIds,
  getContactByNameForUserId,
  upsertUserContactInfo,
  checkUserExists,
  getUserPreferences,
};
