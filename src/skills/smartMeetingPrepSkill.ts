import { findCalendarEventByFuzzyReference, CalendarEventSummary, DateHints } from './calendarSkills';

// Define the expected structure of the skill's input
export interface SmartMeetingPrepSkillInput {
  userId: string;
  meeting_reference: string; // e.g., "my meeting tomorrow morning", "the project sync-up"
  // Potentially other context like preferred language for summaries, etc.
}

import { searchEmailsForPrep } from '../../atomic-docker/project/functions/atom-agent/skills/gmailSkills';
// Assuming types.ts is correctly located relative to gmailSkills.ts for these:
import { GmailSearchParameters, GmailMessageSnippet } from '../../atomic-docker/project/functions/atom-agent/types';

// Define the expected structure of the skill's output
export interface SmartMeetingPrepSkillOutput {
  resolvedEvent?: CalendarEventSummary;
  preparationNotes?: string;
  relatedDocuments?: any[]; // Using any for mock documents for now
  relatedEmails?: GmailMessageSnippet[]; // Added for Gmail results
  // other output fields
}

export class SmartMeetingPrepSkill {
  constructor() {
    // Initialization logic for the skill, if any (e.g., API clients, settings)
  }

  /**
   * Executes the smart meeting preparation skill.
   *
   * @param input - The input parameters for the skill.
   * @returns A promise that resolves to the skill's output, including the resolved event
   *          and any generated preparation materials (though initially just the event).
   */
  public async execute(input: SmartMeetingPrepSkillInput): Promise<SmartMeetingPrepSkillOutput> {
    console.log(`SmartMeetingPrepSkill: Received request for userId: ${input.userId}, meeting_reference: "${input.meeting_reference}"`);

    // Step 1: Resolve the calendar event
    // For now, date_hints is undefined. This could be derived or passed in input in the future.
    const date_hints: DateHints | undefined = undefined;

    const resolvedEvent = await findCalendarEventByFuzzyReference(
      input.userId,
      input.meeting_reference,
      date_hints
    );

    let preparationNotes: string | undefined = undefined;
    let relatedDocuments: any[] = [];
    let relatedEmails: GmailMessageSnippet[] = [];

    if (resolvedEvent) {
      console.log(`SmartMeetingPrepSkill: Resolved event - Title: ${resolvedEvent.title}, StartTime: ${resolvedEvent.startTime}`);

      // Step 2: Find related documents (mocked)
      relatedDocuments = await this._findRelatedDocuments(resolvedEvent);

      // Step 3: Find related emails
      const gmailSearchParams: GmailSearchParameters = {
        // Initially, let's use a generic date query and rely on meetingContext for date refinement.
        // Specific keywords can be added later if needed, or derived from event title/description.
        date_query: "recent", // `searchEmailsForPrep` will use meeting context to refine this
        // body_keywords: resolvedEvent.title, // Optionally add title to body_keywords
      };

      try {
        console.log(`SmartMeetingPrepSkill: Searching emails for event "${resolvedEvent.title}"`);
        const emailSearchResponse = await searchEmailsForPrep(
          input.userId,
          gmailSearchParams,
          resolvedEvent, // Pass the whole event as meetingContext
          5 // Limit to 5 emails for now
        );

        if (emailSearchResponse.ok && emailSearchResponse.data?.results) {
          relatedEmails = emailSearchResponse.data.results;
          console.log(`SmartMeetingPrepSkill: Found ${relatedEmails.length} related emails.`);
        } else {
          console.warn(`SmartMeetingPrepSkill: Email search failed or returned no results. Error: ${emailSearchResponse.error?.message}`);
        }
      } catch (error: any) {
        console.error(`SmartMeetingPrepSkill: Error calling searchEmailsForPrep: ${error.message}`, error);
      }

      // Step 4: Generate preparation notes
      preparationNotes = await this._generatePreparationNotes(resolvedEvent, relatedDocuments, relatedEmails);

      console.log(`SmartMeetingPrepSkill: Successfully generated preparation materials for "${resolvedEvent.title}".`);

    } else {
      console.log(`SmartMeetingPrepSkill: Could not resolve a specific calendar event for "${input.meeting_reference}". No preparation materials will be generated.`);
      preparationNotes = `Could not resolve a specific calendar event for reference: "${input.meeting_reference}". Please try a more specific query or check your calendar.`;
    }

    const output: SmartMeetingPrepSkillOutput = {
      resolvedEvent: resolvedEvent,
      relatedDocuments: relatedDocuments,
      relatedEmails: relatedEmails,
      preparationNotes: preparationNotes,
    };

    console.log("[SmartMeetingPrepSkill.execute] Final output:", JSON.stringify(output, null, 2));
    return output;
  }

  private async _findRelatedDocuments(event: CalendarEventSummary): Promise<any[]> {
    console.log(`[SmartMeetingPrepSkill._findRelatedDocuments] Dynamically finding mock documents for event: "${event.title}" (ID: ${event.id})`);
    const mockDocs: any[] = [];
    const titleLower = event.title.toLowerCase();
    const descriptionLower = event.description?.toLowerCase() || "";

    // Title-based document mocking
    if (titleLower.includes("budget") || descriptionLower.includes("budget")) {
      mockDocs.push({ name: `Budget Overview for ${event.title}.xlsx`, url: `internal://finance/budget-${event.id}.xlsx`, type: "spreadsheet" });
    }
    if (titleLower.includes("phoenix") || descriptionLower.includes("phoenix")) {
      mockDocs.push({ name: `Project Phoenix Status - ${event.id}.pptx`, url: `internal://projects/phoenix/status-${event.id}.pptx`, type: "presentation" });
    }
    if (titleLower.includes("marketing") || titleLower.includes("strategy") || descriptionLower.includes("marketing") || descriptionLower.includes("strategy")) {
      mockDocs.push({ name: `Marketing Strategy Brief - ${event.id}.pdf`, url: `internal://marketing/strategy-${event.id}.pdf`, type: "pdf" });
    }

    // Attendee-based document mocking
    if (event.attendees) {
      for (const attendeeString of event.attendees) {
        // Using a simplified name extraction here, assuming _extractNameFromAttendeeString is in calendarSkills.ts
        // For direct use here, we'd either import it or use a simpler inline version.
        // Let's use a very simple inline version for this mock:
        const namePart = attendeeString.split('<')[0].trim().toLowerCase();
        const simpleName = namePart.split(' ')[0]; // first word of the name part

        if (simpleName === "alice") {
          mockDocs.push({ name: `Alice's Action Items from previous sessions.txt`, url: `internal://users/alice/actions-${event.id}.txt`, type: "text" });
        }
        if (simpleName === "mark") {
          mockDocs.push({ name: `Mark's Proposal Draft for ${event.title}.docx`, url: `internal://users/mark/drafts/prop-${event.id}.docx`, type: "document" });
        }
         if (simpleName === "sarah" && titleLower.includes("1:1")) {
          mockDocs.push({ name: `Performance Review Notes - Sarah Miller.pdf`, url: `internal://hr/reviews/sarahm-${event.id}.pdf`, type: "confidential" });
        }
      }
    }

    // Generic documents
    mockDocs.push({ name: `Minutes from last general meeting on '${event.title}'.pdf`, url: `internal://meetings/minutes/prev-${event.id}.pdf`, type: "minutes" });

    if (mockDocs.length === 0) {
      mockDocs.push({ name: `Standard Agenda Template.docx`, url: "internal://templates/agenda.docx", type: "template" });
    }

    // Deduplicate (simple check based on name)
    const uniqueDocs = Array.from(new Set(mockDocs.map(doc => doc.name)))
        .map(name => mockDocs.find(doc => doc.name === name));

    console.log(`[SmartMeetingPrepSkill._findRelatedDocuments] Found ${uniqueDocs.length} mock documents dynamically.`);
    return uniqueDocs.slice(0, 4); // Cap at 4 documents for brevity
  }

  private async _generatePreparationNotes(
    event: CalendarEventSummary,
    documents: any[],
    emails: GmailMessageSnippet[]
  ): Promise<string> {
    console.log(`[SmartMeetingPrepSkill._generatePreparationNotes] Dynamically generating notes for event: "${event.title}"`);
    const titleLower = event.title.toLowerCase();
    const descriptionLower = event.description?.toLowerCase() || "";

    let notes = `## Meeting Preparation Notes: ${event.title}\n\n`;
    notes += `**Scheduled:** ${event.startTime.toLocaleString()} - ${event.endTime.toLocaleString()}\n`;
    notes += `**Location:** ${event.location || "Not specified"}\n`;
    notes += `**Organizer:** ${event.organizer || "N/A"}\n`;

    const attendeeList = event.attendees && event.attendees.length > 0
      ? event.attendees.map(a => a.split('<')[0].trim()).join(", ") // Show cleaner names
      : "No attendees listed";
    notes += `**Attendees:** ${attendeeList}\n\n`;

    if (event.description) {
      notes += `**Description/Agenda:**\n${event.description}\n\n`;
    }

    notes += "**Key Discussion Points (Suggested):**\n";
    const discussionPoints: string[] = [];
    if (titleLower.includes("budget") || descriptionLower.includes("budget")) {
      discussionPoints.push("Review budget figures and allocations.");
      const budgetDoc = documents.find(doc => doc.name.toLowerCase().includes("budget"));
      if (budgetDoc) {
        discussionPoints.push(`Analyze data in "${budgetDoc.name}".`);
      }
    }
    if (titleLower.includes("strategy") || titleLower.includes("planning") || descriptionLower.includes("strategy") || descriptionLower.includes("planning")) {
      discussionPoints.push("Define/Review strategic goals and next actions.");
    }
    if (titleLower.includes("phoenix") || descriptionLower.includes("phoenix")) {
      discussionPoints.push("Assess Project Phoenix progress and address blockers.");
    }
    if (titleLower.includes("1:1")) {
        const attendeeName = event.title.replace("1:1 with", "").trim(); // Simple extraction
        discussionPoints.push(`Discuss ${attendeeName}'s progress, goals, and any challenges.`);
    }
     if (discussionPoints.length === 0) {
      discussionPoints.push("Clarify meeting objectives and desired outcomes.");
      discussionPoints.push("Identify key topics based on participant roles.");
    }
    discussionPoints.forEach(point => notes += `- ${point}\n`);
    notes += "\n";

    notes += "**Relevant Materials & Context:**\n";
    if (documents.length > 0) {
      documents.forEach(doc => {
        notes += `- **${doc.name}** (${doc.type}): Review this document for relevant background/data. (Mocked Link: ${doc.url})\n`;
      });
    } else {
      notes += "- No specific documents were automatically linked (mocked). Consider searching manually if needed.\n";
    }
    notes += "\n";

    if (emails.length > 0) {
      notes += "**Recently Exchanged Emails (with attendees, around meeting date):**\n";
      emails.forEach(email => {
        const emailDate = email.date ? new Date(email.date).toLocaleDateString() : "N/A";
        notes += `- **Subject:** "${email.subject || '(No Subject)'}" (From: ${email.from || 'N/A'}, Date: ${emailDate})\n`;
        if (email.snippet) {
          notes += `  *Snippet:* ${email.snippet}...\n`;
        }
        if (email.link) {
            notes += `  *Link:* ${email.link}\n`;
        }
      });
      notes += "\n";
    } else {
        notes += "**Recently Exchanged Emails:**\n- No specific recent emails found with attendees around the meeting time.\n\n";
    }


    notes += "**Potential Action Items to Consider from This Meeting (TODO):**\n";
    notes += "- [Assign owners and deadlines for new tasks]\n";
    notes += "- [Schedule follow-up meetings if necessary]\n\n";


    notes += "**Action Items from Previous Related Meetings (TODO):**\n";
    const actionItemDoc = documents.find(doc => doc.name.toLowerCase().includes("action items"));
    const minutesDoc = documents.find(doc => doc.name.toLowerCase().includes("minutes"));
    if (actionItemDoc) {
      notes += `- Review action items from "${actionItemDoc.name}".\n`;
    } else if (minutesDoc) {
      notes += `- Check for open action items in "${minutesDoc.name}".\n`;
    } else {
      notes += "- Check for any outstanding action items from prior relevant meetings.\n";
    }
    notes += "\n";

    // Enhanced Attendee Section - check for specific people and tailor notes
    if (event.attendees) {
        const lowerAttendees = event.attendees.map(a => a.toLowerCase());
        if (lowerAttendees.some(a => a.includes("alice"))) {
            const aliceDoc = documents.find(d => d.name.toLowerCase().includes("alice's action items"));
            if (aliceDoc) {
                notes += `**For Alice:** Please come prepared to discuss items from "${aliceDoc.name}".\n`;
            } else {
                notes += `**For Alice:** Be ready to provide updates on your current tasks.\n`;
            }
        }
         if (lowerAttendees.some(a => a.includes("mark"))) {
            const markDoc = documents.find(d => d.name.toLowerCase().includes("mark's proposal draft"));
            if (markDoc) {
                notes += `**For Mark:** Key discussion point will be your proposal: "${markDoc.name}".\n`;
            }
        }
        notes += "\n";
    }


    notes += "---\nGenerated by SmartMeetingPrepSkill";
    console.log(`[SmartMeetingPrepSkill._generatePreparationNotes] Dynamically generated notes for "${event.title}". Length: ${notes.length}`);
    return notes;
  }
}

// Example of how this skill might be instantiated and used (for testing/demonstration)
// This would typically be done by a skill orchestrator or a higher-level application logic.

async function testSkill() {
  const skill = new SmartMeetingPrepSkill();
  const userId = "user123-test"; // Consistent user ID for tests

  console.log("\\n--- Test Case 1: General reference 'sync up tomorrow' ---");
  let testInput: SmartMeetingPrepSkillInput = {
    userId: userId,
    meeting_reference: "my sync up tomorrow"
  };
  try {
    let result = await skill.execute(testInput);
    console.log("Skill execution result (sync up tomorrow):", JSON.stringify(result.resolvedEvent?.title || "Not Found", null, 2));
  } catch (error) {
    console.error("Error executing skill (sync up tomorrow):", error);
  }

  console.log("\\n--- Test Case 2: Specific 'Marketing Strategy' ---");
  testInput = {
    userId: userId,
    meeting_reference: "Marketing Strategy meeting"
  };
  try {
    let result = await skill.execute(testInput);
    console.log("Skill execution result (Marketing Strategy):", JSON.stringify(result.resolvedEvent?.title || "Not Found", null, 2));
  } catch (error) {
    console.error("Error executing skill (Marketing Strategy):", error);
  }

  console.log("\\n--- Test Case 3: Reference with specific project name 'Project Phoenix discussion' ---");
  testInput = {
    userId: userId,
    meeting_reference: "Project Phoenix discussion"
  };
  try {
    let result = await skill.execute(testInput);
    console.log("Skill execution result (Phoenix discussion):", JSON.stringify(result.resolvedEvent?.title || "Not Found", null, 2));
     // It should pick "Project Phoenix - Critical Path Discussion" if "discussion" is a keyword and it's sooner or scores higher.
     // Or "Project Phoenix Sync-Up" if that scores higher due to "sync up" vs "discussion"
  } catch (error) {
    console.error("Error executing skill (Phoenix discussion):", error);
  }

  console.log("\\n--- Test Case 4: Vague reference 'my meeting' ---");
  testInput = {
    userId: userId,
    meeting_reference: "my meeting"
  };
  try {
    let result = await skill.execute(testInput);
    console.log("Skill execution result (my meeting):", JSON.stringify(result.resolvedEvent?.title || "Not Found", null, 2));
    // This should likely pick the soonest one if "meeting" is too generic or not a good keyword.
    // Current logic might give low scores to all if "meeting" isn't in titles.
  } catch (error) {
    console.error("Error executing skill (my meeting):", error);
  }

  console.log("\\n--- Test Case 5: Non-existent meeting 'board game night' ---");
  testInput = {
    userId: userId,
    meeting_reference: "board game night"
  };
  try {
    let result = await skill.execute(testInput);
    console.log("Skill execution result (board game night):", JSON.stringify(result.resolvedEvent?.title || "Not Found", null, 2));
  } catch (error) {
    console.error("Error executing skill (board game night):", error);
  }

  // To test date_hints, findCalendarEventByFuzzyReference would need to be called directly
  // or SmartMeetingPrepSkillInput would need to support date_hints.
  // For now, direct calls to findCalendarEventByFuzzyReference for date_hint testing:
  console.log("\\n--- Test Case 6: Direct call with specific date hint (past event) ---");
  try {
    const pastDate = new Date();
    pastDate.setDate(pastDate.getDate() - 7); // Targeting "Budget Review Q2"
    pastDate.setHours(12,0,0,0); // Set a specific time on that day to ensure it's within the event's day
    const event = await findCalendarEventByFuzzyReference(userId, "budget review", { specificDate: pastDate });
    console.log("Direct call result (budget review last week):", JSON.stringify(event?.title || "Not Found", null, 2));
  } catch (error) {
    console.error("Error in direct call (budget review last week):", error);
  }
}

// To run the test:
// You would typically uncomment this in a local environment or run this through a test runner.
// For agent-based execution, we usually don't invoke testSkill() directly here
// unless specifically instructed for a one-off test run.
// testSkill();
