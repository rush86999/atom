import { Configuration } from '@azure/msal-node';

export function getMsalConfig(): Configuration {
  return {
    auth: {
      clientId: process.env.OUTLOOK_CLIENT_ID || '',
      authority: 'https://login.microsoftonline.com/common',
      clientSecret: process.env.OUTLOOK_CLIENT_SECRET || '',
    },
  };
}
