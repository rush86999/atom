import { listUpcomingEvents, createCalendarEvent } from './skills/calendarSkills';
import { listRecentEmails, readEmail, sendEmail, EmailDetails } from './skills/emailSkills';
import { searchWeb } from './skills/webResearchSkills';
import { triggerZap, ZapData } from './skills/zapierSkills';
import {
  CalendarEvent, CreateEventResponse,
  Email, ReadEmailResponse, SendEmailResponse,
  SearchResult,
  ZapTriggerResponse,
  CalendarEvent // Ensure CalendarEvent is imported for Microsoft skills too
} from '../types';
import {
    listUpcomingEventsMicrosoft,
    createCalendarEventMicrosoft
} from './skills/microsoftCalendarSkills';
import {
    listRecentEmailsMicrosoft,
    readEmailMicrosoft,
    sendEmailMicrosoft
} from './skills/microsoftEmailSkills';
import {
    getAtomGoogleCalendarTokens,
    getAtomGmailTokens,
    getAtomMicrosoftGraphTokens
} from '../_libs/token-utils';

export async function handleMessage(message: string, userId: string): Promise<string> {
  const lowerCaseMessage = message.toLowerCase();
  // userId is now passed as a parameter

  if (lowerCaseMessage.startsWith('list events')) {
    try {
      const parts = message.split(' ');
      const limit = parts.length > 2 && !isNaN(parseInt(parts[2])) ? parseInt(parts[2]) : 10;

      let events: CalendarEvent[] = [];
      let serviceUsed = "";
      let attemptedServices: string[] = [];

      // TODO: Add a TODO comment in the handler regarding more explicit error objects from skills
      // if this refinement is still pending, to better distinguish "no results" from "error".
      // (Similar to the calendar skills). This applies to all skills.

      const googleCalendarTokens = await getAtomGoogleCalendarTokens(userId);
      if (googleCalendarTokens?.access_token) {
        attemptedServices.push("Google Calendar");
        console.log('Attempting to fetch from Google Calendar...');
        events = await listUpcomingEvents(userId, limit);
        if (events.length > 0) {
          serviceUsed = "Google Calendar";
        }
      }

      if (events.length === 0) { // If Google Calendar had no events, no tokens, or failed
        const msGraphTokens = await getAtomMicrosoftGraphTokens(userId);
        if (msGraphTokens?.access_token) {
          attemptedServices.push("Microsoft Outlook Calendar");
          console.log('Attempting to fetch from Microsoft Outlook Calendar...');
          events = await listUpcomingEventsMicrosoft(userId, limit);
          if (events.length > 0) {
            serviceUsed = "Microsoft Outlook Calendar";
          }
        }
      }

      if (!serviceUsed && attemptedServices.length === 0) {
        return "No calendar service connected. Please connect Google Calendar or Microsoft Outlook Calendar in settings.";
      }

      if (events.length === 0) {
        // If we attempted services but found no events
        if (attemptedServices.length > 0) {
             return `No upcoming events found in your connected calendar(s): ${attemptedServices.join(', ')}. This could also indicate an issue with the connection(s); please check settings if you expected events.`;
        } else { // Should be caught by !serviceUsed check, but as a fallback
            return "No calendar service connected. Please connect Google Calendar or Microsoft Outlook Calendar in settings.";
        }
      }

      const eventList = events.map(event =>
        `- ${event.summary} (${event.startTime} - ${event.endTime})${event.description ? ': ' + event.description : ''}${event.htmlLink ? ` [Link: ${event.htmlLink}]` : ''}`
      ).join('\n');
      return `Upcoming events from ${serviceUsed}:\n${eventList}`;

    } catch (error: any) {
      console.error('Error listing events:', error);
      return `Sorry, I couldn't create the calendar event. Error: ${error.message}`;
    }
  } else if (lowerCaseMessage.startsWith('list emails')) {
    try {
      const parts = message.split(' ');
      const limit = parts.length > 2 && !isNaN(parseInt(parts[2])) ? parseInt(parts[2]) : 10;

      let emails: Email[] = [];
      let serviceUsed = "";
      let attemptedServices: string[] = [];
      // TODO: Add a general TODO for all skills about more explicit error objects from skills
      // to distinguish "no results" from "an error occurred".

      const gmailTokens = await getAtomGmailTokens(userId);
      if (gmailTokens?.access_token) {
        attemptedServices.push("Gmail");
        console.log('Attempting to fetch from Gmail...');
        emails = await listRecentEmails(userId, limit); // Google/Gmail skill
        if (emails.length > 0) {
          serviceUsed = "Gmail";
        }
      }

      if (emails.length === 0) {
        const msGraphTokens = await getAtomMicrosoftGraphTokens(userId);
        if (msGraphTokens?.access_token) {
          attemptedServices.push("Microsoft Outlook");
          console.log('Attempting to fetch from Microsoft Outlook...');
          emails = await listRecentEmailsMicrosoft(userId, limit);
          if (emails.length > 0) {
            serviceUsed = "Microsoft Outlook";
          }
        }
      }

      if (!serviceUsed && attemptedServices.length === 0) {
        return "No email service connected. Please connect Gmail or Microsoft Outlook in settings.";
      }

      if (emails.length === 0) {
        if (attemptedServices.length > 0) {
            return `No recent emails found in your connected email account(s): ${attemptedServices.join(', ')}. This could also indicate an issue with the connection(s); please check settings.`;
        } else {
             return "No email service connected. Please connect Gmail or Microsoft Outlook in settings.";
        }
      }

      const emailList = emails.map((email, index) =>
        `${index + 1}. Subject: ${email.subject || 'N/A'}\n   From: ${email.sender || 'N/A'}\n   Date: ${email.timestamp ? new Date(email.timestamp).toLocaleString() : 'N/A'}\n   ID: ${email.id}`
      ).join('\n\n');
      return `Here are your recent emails from ${serviceUsed}:\n\n${emailList}\n\nUse 'read email <ID>' to read a specific email.`;

    } catch (error: any) {
      console.error('Error listing emails:', error);
      return `Sorry, I couldn't fetch recent emails. Error: ${error.message}`;
    }
  } else if (lowerCaseMessage.startsWith('read email')) {
    try {
      const parts = message.split(' ');
      if (parts.length < 3) {
        return "Please provide an email ID to read. Usage: read email <emailId>";
      }
      const emailId = parts[2];

      let response: ReadEmailResponse | null = null;
      let serviceUsed = "";
      // TODO: This is ambiguous if both are connected. For now, try Gmail then Outlook.
      // A better solution would be "read gmail <id>" or "read outlook <id>" or storing context from last "list emails"

      const gmailTokens = await getAtomGmailTokens(userId);
      if (gmailTokens?.access_token) {
        console.log(`Attempting to read email ${emailId} from Gmail...`);
        response = await readEmail(userId, emailId); // Google/Gmail skill
        serviceUsed = "Gmail";
        // If successfully read or explicitly not found by Gmail, don't try Outlook with the same ID.
        if (response.success || (response.message && response.message.includes('not found'))) {
          // Proceed with this response
        } else {
          // Gmail attempt failed for a reason other than "not found", maybe try Outlook.
          // For now, if it fails for any reason other than explicit "not found", we might still want to stop.
          // Let's assume for now: if an attempt is made and it doesn't succeed, we report that.
          // If it's a "not found", then it makes sense to try the next service.
          // This needs careful error message parsing from skills or better error objects.
          // For now, if success is false, and message does NOT indicate "not found", we stop.
          // If it IS "not found", response is kept and we might try next.
          if (!response.message || !response.message.toLowerCase().includes('not found')) {
             // Error was not "not found", so report this service's error
          } else {
            response = null; // Clear response to allow trying the next service
          }
        }
      }

      if (!response || (response && !response.success && response.message && response.message.toLowerCase().includes('not found'))) { // If Gmail not connected, or read failed as "not found"
        const msGraphTokens = await getAtomMicrosoftGraphTokens(userId);
        if (msGraphTokens?.access_token) {
          console.log(`Attempting to read email ${emailId} from Microsoft Outlook...`);
          response = await readEmailMicrosoft(userId, emailId);
          serviceUsed = "Microsoft Outlook";
        }
      }

      if (!response) { // No service was attempted or both failed silently before setting a response
          return "No email service connected or email ID is ambiguous. Please check settings or specify service.";
      }

      if (response.success && response.email) {
        const email = response.email;
        return `Email from ${serviceUsed}:\nSubject: ${email.subject || 'N/A'}\nFrom: ${email.sender || 'N/A'}\nTo: ${email.recipient || 'N/A'}\nDate: ${email.timestamp ? new Date(email.timestamp).toLocaleString() : 'N/A'}\n\nBody:\n${email.body || '(No body content)'}`;
      } else {
        return `Could not read email from ${serviceUsed || 'connected services'}. ${response.message || 'Email not found or access issue.'}`;
      }
    } catch (error: any) {
      console.error('Error reading email:', error);
      return `Sorry, I couldn't read the specified email. Error: ${error.message}`;
    }
  } else if (lowerCaseMessage.startsWith('send email')) {
    try {
      const emailDetailsJson = message.substring(message.indexOf('{')).trim();
      let emailDetails: EmailDetails;
      try {
        emailDetails = JSON.parse(emailDetailsJson);
      } catch (e) {
        return "Invalid email details format. Please provide JSON. Example: send email {\"to\":\"recipient@example.com\",\"subject\":\"Your Subject\",\"body\":\"Email content...\"}";
      }

      let response: SendEmailResponse | null = null;
      let serviceUsed = "";
      let serviceToTry: (() => Promise<SendEmailResponse | null>) | null = null;

      const gmailTokens = await getAtomGmailTokens(userId);
      const msGraphTokens = await getAtomMicrosoftGraphTokens(userId);

      // Default to Gmail if available, then Microsoft. User preference could be added later.
      if (gmailTokens?.access_token) {
        serviceToTry = async () => {
            console.log('Attempting to send email via Gmail...');
            serviceUsed = "Gmail";
            return await sendEmail(userId, emailDetails); // Google/Gmail skill
        };
      } else if (msGraphTokens?.access_token) {
         serviceToTry = async () => {
            console.log('Attempting to send email via Microsoft Outlook...');
            serviceUsed = "Microsoft Outlook";
            return await sendEmailMicrosoft(userId, emailDetails);
        };
      }

      if(serviceToTry) {
        response = await serviceToTry();
      } else {
         return "No email service connected to send from. Please connect Gmail or Microsoft Outlook in settings.";
      }

      if (response && response.success) {
        return `Email sent successfully via ${serviceUsed}! ${response.message || ''} (Message ID: ${response.emailId || 'N/A'})`;
      } else {
        return `Failed to send email via ${serviceUsed || 'the connected service'}. ${response?.message || 'Please try again or check your connection.'}`;
      }
    } catch (error: any) {
      console.error('Error sending email:', error);
      return `Sorry, I couldn't send the email. Error: ${error.message}`;
    }
  } else if (lowerCaseMessage.startsWith('search web')) {
    try {
      const searchQuery = message.substring('search web'.length).trim();
      if (!searchQuery) {
        return "Please provide a term to search for after 'search web'.";
      }

      // Pass userId to searchWeb, although it might be unused by the skill for global search
      const results: SearchResult[] = await searchWeb(searchQuery, userId);

      if (results.length === 0) {
        // webResearchSkills.ts logs specific reasons for empty results (API key, actual no results, error)
        return `I couldn't find any web results for "${searchQuery}", or there might be an issue with the web search service configuration.`;
      }

      const resultList = results.map((result, index) =>
        `${index + 1}. ${result.title}\n   Snippet: ${result.snippet}\n   Link: ${result.link}`
      ).join('\n\n');
      return `Here are the web search results for "${searchQuery}":\n\n${resultList}`;

    } catch (error: any) {
      console.error('Error performing web search in handler:', error);
      return `Sorry, I encountered an error while trying to search the web. Error: ${error.message}`;
    }
  } else if (lowerCaseMessage.startsWith('trigger zap')) {
    try {
      // Command format: trigger zap <ZapName> [with data {"key":"value"}]
      const commandPrefix = "trigger zap ";
      let remainingMessage = message.substring(commandPrefix.length);

      let zapName: string;
      let jsonData: string | undefined;
      let data: ZapData = {};

      const withDataIndex = remainingMessage.toLowerCase().indexOf(' with data ');

      if (withDataIndex === -1) { // No "with data" part
        zapName = remainingMessage.trim();
      } else {
        zapName = remainingMessage.substring(0, withDataIndex).trim();
        jsonData = remainingMessage.substring(withDataIndex + ' with data '.length).trim();
      }

      if (!zapName) {
        return "Please specify the Zap name to trigger. Usage: trigger zap <ZapName> [with data {\"key\":\"value\"}]";
      }

      if (jsonData) {
        // Ensure jsonData is not empty string before trying to parse
        if (!jsonData.trim()) {
             return "Data part is empty. Please provide valid JSON data or omit the 'with data' part.";
        }
        try {
          data = JSON.parse(jsonData);
        } catch (e) {
          return "Invalid JSON data provided for the Zap. Please check the format. Example: {\"key\":\"value\"}";
        }
      }

      const response: ZapTriggerResponse = await triggerZap(userId, zapName, data);

      if (response.success) {
        let successMsg = `Successfully triggered Zap: "${response.zapName}".`;
        if (response.message && response.message !== `Zap "${response.zapName}" triggered successfully.`) { // Avoid redundant default message
            successMsg += ` ${response.message}`;
        }
        if (response.runId) {
            successMsg += ` (Run ID: ${response.runId})`;
        }
        return successMsg.trim();
      } else {
        return `Failed to trigger Zap: "${response.zapName}". Error: ${response.message || 'An unknown error occurred.'}`;
      }
    } catch (error: any) {
      console.error('Error triggering Zap in handler:', error);
      return `Sorry, I couldn't trigger the Zap. Error: ${error.message}`;
    }
  }

  return `Atom received: "${message}". I can understand "list events", "create event {JSON_DETAILS}", "list emails", "read email <id>", "send email {JSON_DETAILS}", "search web <query>", or "trigger zap <ZapName> [with data {JSON_DATA}]".`;
}
