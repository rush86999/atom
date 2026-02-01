import { getNewHubSpotContacts } from '../../atomic-docker/project/functions/atom-agent/skills/hubspotSkills';
import { createGmailDraft, EmailDetails } from '../../atomic-docker/project/functions/atom-agent/skills/emailSkills';
import { ContentCreationAgent } from '../skills/contentCreationSkill';
import { AgentLLMService, SubAgentInput } from '../nlu_agents/nlu_types';
import { HubSpotContact } from '../../atomic-docker/project/functions/atom-agent/types';
import { OpenAI } from 'openai';
import { ATOM_OPENAI_API_KEY } from '../../atomic-docker/project/functions/atom-agent/_libs/constants';

// A mock or placeholder for the actual LLM service
// In a real scenario, this would be properly instantiated and injected.
class MockAgentLLMService implements AgentLLMService {
    private openai: OpenAI;

    constructor(apiKey: string) {
        this.openai = new OpenAI({ apiKey });
    }

    async generate(prompt: any, model: string, options: any): Promise<any> {
        const response = await this.openai.chat.completions.create({
            model: model,
            messages: [{ role: 'system', content: prompt.data.system_prompt }, { role: 'user', content: prompt.data.user_query }],
            ...options
        });
        return { success: true, content: response.choices[0].message.content, usage: response.usage };
    }
}


interface SalesOutreachResult {
  success: boolean;
  message: string;
  draftsCreated: number;
  contactsProcessed: number;
  errors: string[];
}

export async function runSalesOutreach(userId: string): Promise<SalesOutreachResult> {
  console.log(`[SalesOutreachOrchestrator] Starting automated sales outreach for user ${userId}.`);

  const llmService = new MockAgentLLMService(ATOM_OPENAI_API_KEY!);
  const contentAgent = new ContentCreationAgent(llmService);

  const sevenDaysAgo = new Date();
  sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7);

  const result: SalesOutreachResult = {
    success: false,
    message: '',
    draftsCreated: 0,
    contactsProcessed: 0,
    errors: [],
  };

  // 1. Get new HubSpot contacts
  const contactsResponse = await getNewHubSpotContacts(userId, sevenDaysAgo);
  if (!contactsResponse.ok || !contactsResponse.data) {
    const errorMsg = `Failed to retrieve new HubSpot contacts: ${contactsResponse.error?.message}`;
    console.error(`[SalesOutreachOrchestrator] ${errorMsg}`);
    result.message = errorMsg;
    return result;
  }

  const newContacts: HubSpotContact[] = contactsResponse.data;
  if (newContacts.length === 0) {
    const successMsg = 'No new contacts found in the last 7 days. No outreach needed.';
    console.log(`[SalesOutreachOrchestrator] ${successMsg}`);
    result.success = true;
    result.message = successMsg;
    return result;
  }

  console.log(`[SalesOutreachOrchestrator] Found ${newContacts.length} new contacts to process.`);

  // 2. Iterate through contacts, generate content, and create drafts
  for (const contact of newContacts) {
    result.contactsProcessed++;
    const contactName = contact.properties.firstname || 'there';
    const companyName = contact.properties.company || 'your company';

    if (!contact.properties.email) {
      const errorMsg = `Skipping contact ID ${contact.id} due to missing email address.`;
      console.warn(`[SalesOutreachOrchestrator] ${errorMsg}`);
      result.errors.push(errorMsg);
      continue;
    }

    // 3. Generate personalized email body
    const prompt = `
      Please write a friendly and professional introductory email to a new lead.
      The lead's name is ${contactName}.
      They work at ${companyName}.
      The email should be from the perspective of a team member from 'Atom Inc.' and should briefly introduce our company's AI-powered productivity platform.
      Keep it concise and end with a question to encourage a reply, like asking about their current challenges with productivity or workflow automation.
    `;

    const contentInput: SubAgentInput = {
      userId: userId,
      userInput: prompt,
      context: 'sales_outreach',
    };

    const contentResponse = await contentAgent.analyze(contentInput);
    const emailBody = contentResponse.generatedContent;

    if (!emailBody) {
      const errorMsg = `Failed to generate email content for contact ${contact.id}.`;
      console.error(`[SalesOutreachOrchestrator] ${errorMsg}`);
      result.errors.push(errorMsg);
      continue;
    }

    // 4. Create Gmail draft
    const emailDetails: EmailDetails = {
      to: contact.properties.email,
      subject: `Introduction from Atom Inc.`,
      body: emailBody,
    };

    const draftResponse = await createGmailDraft(userId, emailDetails);
    if (draftResponse.success) {
      console.log(`[SalesOutreachOrchestrator] Successfully created draft for ${contact.properties.email}`);
      result.draftsCreated++;
    } else {
      const errorMsg = `Failed to create draft for ${contact.properties.email}: ${draftResponse.message}`;
      console.error(`[SalesOutreachOrchestrator] ${errorMsg}`);
      result.errors.push(errorMsg);
    }
  }

  result.success = result.errors.length === 0;
  result.message = `Sales outreach process completed. Created ${result.draftsCreated} drafts for ${result.contactsProcessed} contacts.`;
  if (result.errors.length > 0) {
    result.message += ` Encountered ${result.errors.length} errors.`;
  }

  console.log(`[SalesOutreachOrchestrator] ${result.message}`);
  return result;
}
