import { searchUserEmails as searchGmail } from '../gmail-service/service';
import { searchUserOutlookEmails } from '../outlook-service/service';
import { getUserEmailContent as getGmailContent } from '../gmail-service/service';
import { getUserOutlookEmailContent } from '../outlook-service/service';

async function searchUserEmails(userId: string, query: string, maxResults: number = 10) {
  const gmailResults = await searchGmail(userId, query, maxResults);
  const outlookResults = await searchUserOutlookEmails(userId, query, maxResults);
  return { gmail: gmailResults, outlook: outlookResults };
}

async function getUserEmailContent(userId: string, emailId: string, service: 'gmail' | 'outlook') {
  if (service === 'gmail') {
    return await getGmailContent(userId, emailId);
  } else {
    return await getUserOutlookEmailContent(userId, emailId);
  }
}

export { searchUserEmails, getUserEmailContent };
