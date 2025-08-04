import { Platform } from 'react-native';

// android redirect: com.googleusercontent.apps.159344105155-uh4g7h127eg5r7nv0hm333ftk0nehpaq:/oauth2redirect/google
export const googleConfig =
  Platform.OS === 'android'
    ? {
        issuer: 'https://accounts.google.com',
        clientId:
          '159344105155-rmomk5vti4hbr0euohtdklltqh7432qk.apps.googleusercontent.com',
        redirectUrl:
          'com.googleusercontent.apps.159344105155-rmomk5vti4hbr0euohtdklltqh7432qk:/oauth2redirect',
        scopes: [
          'https://www.googleapis.com/auth/calendar.readonly',
          'https://www.googleapis.com/auth/calendar.events',
          'https://www.googleapis.com/auth/contacts.readonly',
        ],
      }
    : {
        issuer: 'https://accounts.google.com',
        clientId:
          '159344105155-2a6grpvmkki1dkkche8o7bishssrd1qb.apps.googleusercontent.com',
        redirectUrl:
          'com.googleusercontent.apps.159344105155-2a6grpvmkki1dkkche8o7bishssrd1qb:/oauth2redirect/google',
        scopes: [
          'https://www.googleapis.com/auth/calendar.readonly',
          'https://www.googleapis.com/auth/calendar.events',
          'https://www.googleapis.com/auth/contacts.readonly',
        ],
      };
