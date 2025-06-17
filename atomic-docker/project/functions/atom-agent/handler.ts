import { listUpcomingEvents, createCalendarEvent } from './skills/calendarSkills';
import { listRecentEmails, readEmail, sendEmail, EmailDetails } from './skills/emailSkills';
import { searchWeb } from './skills/webResearchSkills';
import { triggerZap, ZapData } from './skills/zapierSkills';
import {
  CalendarEvent, CreateEventResponse,
  Email, ReadEmailResponse, SendEmailResponse,
  SearchResult,
  ZapTriggerResponse
} from '../types';

export async function handleMessage(message: string, userId: string): Promise<string> {
  const lowerCaseMessage = message.toLowerCase();
  // userId is now passed as a parameter

  if (lowerCaseMessage.startsWith('list events')) {
    try {
      // Optional: parse limit from message, e.g., "list events 5"
      const parts = message.split(' ');
      const limit = parts.length > 2 && !isNaN(parseInt(parts[2])) ? parseInt(parts[2]) : 10;

      // TODO: Refine error propagation from skills.
      // listUpcomingEvents should ideally return a more explicit error object
      // (e.g., { success: false, message: "Token error", events: [] })
      // to distinguish "no events" from "an error occurred".
      // For now, an empty array implies either no events or an auth/API issue.
      const events: CalendarEvent[] = await listUpcomingEvents(userId, limit);
      if (events.length === 0) {
        // Given current mock token setup, this often means tokens are missing or invalid.
        return "Could not retrieve calendar events. Please ensure your Google Calendar is connected in settings and try again, or there might be no upcoming events.";
      }
      const eventList = events.map(event =>
        `- ${event.summary} (${event.startTime} - ${event.endTime})${event.description ? ': ' + event.description : ''}${event.htmlLink ? ` [Link: ${event.htmlLink}]` : ''}`
      ).join('\n');
      return `Upcoming events:\n${eventList}`;
    } catch (error) {
      console.error('Error listing events:', error);
      return "Sorry, I couldn't fetch the upcoming events.";
    }
  } else if (lowerCaseMessage.startsWith('create event')) {
    try {
      // This is a very basic parsing. A real agent would use NLP to extract details.
      // Example: "create event Meeting with John from 2024-03-20T10:00 to 2024-03-20T11:00 about Project Alpha"
      // For now, we'll expect a JSON-like structure or rely on predefined details for simplicity.
      // Let's assume the message format "create event {"summary":"Test Event","startTime":"2024-03-20T14:00:00Z","endTime":"2024-03-20T15:00:00Z"}"
      const eventDetailsJson = message.substring(message.indexOf('{')).trim();
      let eventDetails: Partial<CalendarEvent>;

      if (eventDetailsJson) {
        try {
            eventDetails = JSON.parse(eventDetailsJson);
        } catch (e) {
            return "Invalid event details format. Please provide JSON for event details. Example: create event {\"summary\":\"My Event\",\"startTime\":\"YYYY-MM-DDTHH:mm:ssZ\",\"endTime\":\"YYYY-MM-DDTHH:mm:ssZ\"}";
        }
      } else {
        // Fallback to a default event if no details are provided
        eventDetails = {
            summary: 'Default Event',
            startTime: new Date().toISOString(),
            endTime: new Date(Date.now() + 60 * 60 * 1000).toISOString(), // 1 hour from now
            description: 'Created by Atom Agent (default)'
        };
      }

      const response: CreateEventResponse = await createCalendarEvent(userId, eventDetails);
      if (response.success) {
        return `Event created: ${response.message || 'Successfully created event.'} (ID: ${response.eventId || 'N/A'})${response.htmlLink ? ` Link: ${response.htmlLink}` : ''}`;
      } else {
        return `Failed to create calendar event. ${response.message || 'Please check your connection or try again.'}`;
      }
    } catch (error) {
      console.error('Error creating event:', error);
      return "Sorry, I couldn't create the calendar event.";
    }
  } else if (lowerCaseMessage.startsWith('list emails')) {
    try {
      const parts = message.split(' ');
      const limit = parts.length > 2 && !isNaN(parseInt(parts[2])) ? parseInt(parts[2]) : 10;

      const emails: Email[] = await listRecentEmails(limit);
      if (emails.length === 0) {
        return "No recent emails found.";
      }
      const emailList = emails.map(email =>
        `- (${email.read ? 'read' : 'unread'}) From: ${email.sender}, Subject: ${email.subject} (ID: ${email.id})`
      ).join('\n');
      return `Recent emails:\n${emailList}`;
    } catch (error) {
      console.error('Error listing emails:', error);
      return "Sorry, I couldn't fetch recent emails.";
    }
  } else if (lowerCaseMessage.startsWith('read email')) {
    try {
      const parts = message.split(' ');
      if (parts.length < 3) {
        return "Please provide an email ID to read. Usage: read email <emailId>";
      }
      const emailId = parts[2];
      const response: ReadEmailResponse = await readEmail(emailId);

      if (response.success && response.email) {
        const email = response.email;
        return `Email (ID: ${email.id}):\nFrom: ${email.sender}\nTo: ${email.recipient}\nSubject: ${email.subject}\nDate: ${email.timestamp}\n\n${email.body}`;
      } else {
        return response.message || "Could not read email.";
      }
    } catch (error) {
      console.error('Error reading email:', error);
      return "Sorry, I couldn't read the specified email.";
    }
  } else if (lowerCaseMessage.startsWith('send email')) {
    try {
      // Example: send email {"to":"test@example.com","subject":"Hello","body":"This is a test."}
      const emailDetailsJson = message.substring(message.indexOf('{')).trim();
      let emailDetails: EmailDetails;

      if (emailDetailsJson) {
        try {
          emailDetails = JSON.parse(emailDetailsJson);
        } catch (e) {
          return "Invalid email details format. Please provide JSON. Example: send email {\"to\":\"recipient@example.com\",\"subject\":\"Your Subject\",\"body\":\"Email content...\"}";
        }
      } else {
        return "Please provide email details in JSON format after 'send email'.";
      }

      const response: SendEmailResponse = await sendEmail(emailDetails);
      if (response.success) {
        return `Email sent: ${response.message} (ID: ${response.emailId})`;
      } else {
        return `Failed to send email: ${response.message}`;
      }
    } catch (error) {
      console.error('Error sending email:', error);
      return "Sorry, I couldn't send the email.";
    }
  } else if (lowerCaseMessage.startsWith('search web')) {
    try {
      const query = message.substring('search web'.length).trim();
      if (!query) {
        return "Please provide a search query. Usage: search web <your query>";
      }

      const results: SearchResult[] = await searchWeb(query);
      if (results.length === 0) {
        return `No web results found for "${query}".`;
      }
      const resultList = results.map(result =>
        `- ${result.title}\n  Link: ${result.link}\n  Snippet: ${result.snippet}`
      ).join('\n\n');
      return `Web search results for "${query}":\n\n${resultList}`;
    } catch (error) {
      console.error('Error performing web search:', error);
      return "Sorry, I couldn't perform the web search.";
    }
  } else if (lowerCaseMessage.startsWith('trigger zap')) {
    try {
      // Example: trigger zap MyZapName with data {"key":"value"}
      const withDataIndex = lowerCaseMessage.indexOf(' with data ');
      let zapName: string;
      let jsonData: string | undefined;

      if (withDataIndex === -1) {
        // No data provided
        zapName = message.substring('trigger zap'.length).trim();
      } else {
        zapName = message.substring('trigger zap'.length, withDataIndex).trim();
        jsonData = message.substring(withDataIndex + ' with data '.length).trim();
      }

      if (!zapName) {
        return "Please provide a Zap name. Usage: trigger zap <ZapName> [with data {JSON_DATA}]";
      }

      let data: ZapData = {};
      if (jsonData) {
        try {
          data = JSON.parse(jsonData);
        } catch (e) {
          return "Invalid JSON data format. Please provide valid JSON for the Zap data.";
        }
      }

      const response: ZapTriggerResponse = await triggerZap(zapName, data);
      if (response.success) {
        return `Zap triggered: ${response.message} (Run ID: ${response.runId})`;
      } else {
        return `Failed to trigger Zap: ${response.message}`;
      }
    } catch (error) {
      console.error('Error triggering Zap:', error);
      return "Sorry, I couldn't trigger the Zap.";
    }
  }

  return `Atom received: "${message}". I can understand "list events", "create event {JSON_DETAILS}", "list emails", "read email <id>", "send email {JSON_DETAILS}", "search web <query>", or "trigger zap <ZapName> [with data {JSON_DATA}]".`;
}
