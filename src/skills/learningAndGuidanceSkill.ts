import {
    LLMServiceInterface, // Import the interface
    StructuredLLMPrompt,
    GuidanceQueryClassificationData,
    AnswerFromTextData,
    StepsFromTextData,
    FollowupSuggestionData,
    LLMTaskType // Assuming LLMTaskType is also exported from llmUtils
} from '../lib/llmUtils';

// Mock Knowledge Base Data (as previously defined)
const MOCK_KB_ARTICLES: KnowledgeBaseArticle[] = [
  {
    id: "kb_001",
    title: "How to Create Pivot Tables in SpreadsheetApp",
    contentType: 'how-to',
    application: "SpreadsheetApp",
    keywords: ["pivot table", "spreadsheet", "data analysis", "report"],
    content: "Pivot tables are a powerful tool for summarizing and analyzing large datasets. This guide explains how to create them in SpreadsheetApp.",
    steps: [
      { title: "Select Your Data", description: "Click on any cell within the data range you want to analyze." },
      { title: "Insert Pivot Table", description: "Go to the 'Insert' menu and choose 'PivotTable'." },
      { title: "Configure Fields", description: "In the PivotTable editor pane, drag fields into Rows, Columns, Values, and Filters areas." },
      { title: "Customize", description: "Use options to sort, filter, and format your pivot table." }
    ],
    difficulty: 'intermediate',
  },
  {
    id: "kb_002",
    title: "Tutorial: Email Merge with Attachments",
    contentType: 'tutorial',
    application: "EmailClient",
    keywords: ["email merge", "mail merge", "attachments", "bulk email", "tutorial"],
    content: "This tutorial walks you through performing an email merge operation with personalized attachments using EmailClient and SpreadsheetApp for data.",
    steps: [
      { title: "Prepare Data Source", description: "Create a spreadsheet with recipient emails, names, and attachment file paths." },
      { title: "Open EmailClient Merge Tool", description: "In EmailClient, find the 'Mail Merge Wizard' under 'Tools'." },
      { title: "Connect Data Source", description: "Link your spreadsheet to the wizard." },
      { title: "Compose Template", description: "Write your email template using placeholders for personalized fields (e.g., {{FirstName}})." },
      { title: "Configure Attachments", description: "Specify the column in your spreadsheet that contains the path to each recipient's attachment." },
      { title: "Preview and Send", description: "Review a few merged emails then start the send process." }
    ],
    difficulty: 'intermediate',
  },
  {
    id: "kb_003",
    title: "FAQ: Common Login Issues",
    contentType: 'faq',
    application: "General",
    keywords: ["login", "password", "access denied", "troubleshooting", "faq"],
    content: "Q: I forgot my password. How do I reset it?\nA: Click the 'Forgot Password' link on the login page and follow the instructions sent to your email.\n\nQ: Why am I seeing 'Access Denied' errors?\nA: This could be due to incorrect credentials, insufficient permissions, or network issues. Please verify your username/password and contact support if the problem persists.\n\nQ: What are the password complexity requirements?\nA: Passwords must be at least 12 characters, include uppercase, lowercase, numbers, and symbols.",
    difficulty: 'beginner',
  },
  {
    id: "kb_004",
    title: "Understanding Conditional Formatting",
    contentType: 'explanation',
    application: "SpreadsheetApp",
    keywords: ["conditional formatting", "spreadsheet", "data visualization", "rules"],
    content: "Conditional formatting allows you to automatically apply formatting (like colors, icons, and data bars) to cells that meet certain criteria. This helps in visualizing data, highlighting important information, and identifying trends. You can set up rules based on cell values, formulas, or dates. Common uses include highlighting cells greater than a certain number, color-coding sales performance, or identifying duplicate values.",
    difficulty: 'beginner',
  },
  {
    id: "kb_005",
    title: "Workflow Guide: New Client Onboarding",
    contentType: 'workflow_guide',
    application: "CRM_Platform",
    keywords: ["client onboarding", "crm", "workflow", "new customer", "process"],
    content: "This guide outlines the standard procedure for onboarding new clients in the CRM_Platform.",
    steps: [
        {title: "Receive Lead", description: "New lead is captured from web form or manual entry."},
        {title: "Initial Contact & Qualification", description: "Sales rep makes initial contact within 24 hours to qualify the lead."},
        {title: "Needs Assessment Meeting", description: "Schedule and conduct a meeting to understand client requirements."},
        {title: "Proposal Creation", description: "Generate a tailored proposal in the CRM using approved templates."},
        {title: "Contract & Signature", description: "Send contract for e-signature via integrated tool."},
        {title: "Project Kickoff", description: "Once signed, schedule internal and client kickoff meetings."},
        {title: "CRM Record Update", description: "Update client status to 'Active' and populate all relevant fields."}
    ],
    difficulty: 'intermediate',
  }
];

async function _fetchMockKnowledgeBaseArticles(
  query: string,
  contentTypeHint?: KnowledgeBaseArticle['contentType'],
  applicationContext?: string,
  maxResults: number = 3
): Promise<KnowledgeBaseArticle[]> {
  console.log(`[_fetchMockKnowledgeBaseArticles] Query: "${query}", CT: ${contentTypeHint}, AppCtx: ${applicationContext}, Max: ${maxResults}`);
  const queryLower = query.toLowerCase();
  const queryKeywords = queryLower.split(/\s+/).filter(kw => kw.length > 2);
  let filtered = MOCK_KB_ARTICLES;

  if (applicationContext) {
    filtered = filtered.filter(a => !a.application || a.application.toLowerCase() === applicationContext.toLowerCase() || a.application === "General");
  }
  if (contentTypeHint) {
    filtered = filtered.filter(a => a.contentType === contentTypeHint);
  }

  const scored = filtered.map(article => {
    let score = 0;
    const titleLower = article.title.toLowerCase();
    const contentSnip = article.content.substring(0, 300).toLowerCase();
    queryKeywords.forEach(kw => {
      if (titleLower.includes(kw)) score += 3;
      if (article.keywords?.some(k => k.toLowerCase().includes(kw))) score += 2;
      if (contentSnip.includes(kw)) score += 1;
    });
    if (queryLower.includes(article.contentType)) score +=2;
    return { article, score };
  }).filter(item => item.score > 0).sort((a, b) => b.score - a.score);
  return scored.slice(0, maxResults).map(item => item.article);
}

export interface KnowledgeBaseArticle {
  id: string;
  title: string;
  contentType: 'tutorial' | 'how-to' | 'faq' | 'workflow_guide' | 'explanation';
  application?: string;
  keywords?: string[];
  content: string;
  steps?: { title: string; description: string; }[];
  difficulty?: 'beginner' | 'intermediate' | 'advanced';
}

export type GuidanceType = 'answer_question' | 'find_tutorial' | 'guide_workflow' | 'general_explanation';

export interface LearningAndGuidanceInput {
  userId: string;
  query: string;
  guidanceTypeHint?: GuidanceType;
  applicationContext?: string;
  options?: {
    preferContentType?: KnowledgeBaseArticle['contentType'];
    maxResults?: number;
  };
}

export interface ProvidedGuidance {
  title: string;
  contentSnippet?: string;
  fullContent?: string;
  steps?: { title: string; description: string; }[];
  sourceArticleId: string;
  relevanceScore?: number;
}

export interface LearningAndGuidanceResult {
  originalQuery: string;
  guidanceProvided: ProvidedGuidance[];
  followUpSuggestions?: string[];
  searchPerformedOn?: string;
}

export class LearningAndGuidanceSkill {
  private readonly llmService: LLMServiceInterface;

  constructor(llmService: LLMServiceInterface) {
    this.llmService = llmService;
    console.log("LearningAndGuidanceSkill initialized with LLMService.");
  }

  public async execute(input: LearningAndGuidanceInput): Promise<LearningAndGuidanceResult> {
    console.log(`[LearningAndGuidanceSkill] Query: "${input.query}", User: ${input.userId}`);

    if (!input.query || !input.userId) {
      throw new Error("Query and userId are required.");
    }
    const maxResults = input.options?.maxResults || 3;
    let effectiveGuidanceType: GuidanceType = input.guidanceTypeHint || 'answer_question';

    if (!input.guidanceTypeHint) {
      const classData: GuidanceQueryClassificationData = { query: input.query };
      const classPrompt: StructuredLLMPrompt = { task: 'classify_guidance_query', data: classData };
      try {
        const llmResp = await this.llmService.generate(classPrompt, 'cheapest');
        if (llmResp.success && llmResp.content) {
          const parsed = JSON.parse(llmResp.content);
          const validTypes: GuidanceType[] = ['answer_question', 'find_tutorial', 'guide_workflow', 'general_explanation'];
          if (parsed && parsed.guidanceType && validTypes.includes(parsed.guidanceType)) {
            effectiveGuidanceType = parsed.guidanceType;
          } else { console.warn(`[LearningAndGuidanceSkill] LLM invalid guidanceType: ${llmResp.content}`); }
        } else { console.error(`[LearningAndGuidanceSkill] LLM query classification failed: ${llmResp.error}`); }
      } catch (e: any) { console.error(`[LearningAndGuidanceSkill] Error in LLM query classification: ${e.message}`); }
    }
    console.log(`[LearningAndGuidanceSkill] Effective guidance type: ${effectiveGuidanceType}`);

    const relevantArticles = await _fetchMockKnowledgeBaseArticles(input.query, input.options?.preferContentType, input.applicationContext, maxResults);
    const guidanceProvided: ProvidedGuidance[] = [];

    for (const article of relevantArticles) {
      let guidance: ProvidedGuidance = { title: article.title, sourceArticleId: article.id, relevanceScore: 0.6 };
      try {
        let articlePrompt: StructuredLLMPrompt;
        switch (effectiveGuidanceType) {
          case 'answer_question':
          case 'general_explanation':
            const answerData: AnswerFromTextData = { query: input.query, textContent: article.content.substring(0, 1500), articleTitle: article.title };
            articlePrompt = { task: effectiveGuidanceType === 'answer_question' ? 'answer_from_text' : 'summarize_for_explanation', data: answerData };
            const answerResp = await this.llmService.generate(articlePrompt, 'cheapest');
            if (answerResp.success && answerResp.content && !answerResp.content.toLowerCase().startsWith("llm fallback") && !answerResp.content.toLowerCase().includes("not appear to contain")) {
              guidance.contentSnippet = answerResp.content;
              guidance.relevanceScore = 0.8;
            } else { guidance.contentSnippet = `Article "${article.title}" found, but specific info for "${input.query}" not extracted. Error: ${answerResp.error || 'fallback'}`; }
            break;
          case 'find_tutorial':
          case 'guide_workflow':
            if (article.steps && article.steps.length > 0) {
              guidance.steps = article.steps;
              guidance.contentSnippet = `Found steps in "${article.title}".`;
              guidance.relevanceScore = 0.85;
            } else {
              const stepsData: StepsFromTextData = { query: input.query, textContent: article.content.substring(0, 2000), articleTitle: article.title };
              articlePrompt = { task: 'extract_steps_from_text', data: stepsData };
              const stepsResp = await this.llmService.generate(articlePrompt, 'cheapest');
              if (stepsResp.success && stepsResp.content) {
                const parsed = JSON.parse(stepsResp.content);
                if (parsed && Array.isArray(parsed.steps) && parsed.steps.length > 0) {
                  guidance.steps = parsed.steps;
                  guidance.contentSnippet = "Extracted key steps:";
                  guidance.relevanceScore = 0.8;
                } else { guidance.contentSnippet = `"${article.title}" relevant, but steps for "${input.query}" not extracted.`; }
              } else { guidance.contentSnippet = `Could not extract steps for "${article.title}". Error: ${stepsResp.error}`; }
            }
            break;
          default:
            guidance.contentSnippet = `Article: ${article.title}. General info: ${article.content.substring(0, 200)}...`;
        }
      } catch (e: any) {
        console.error(`[LearningAndGuidanceSkill] Error processing article ${article.id} with LLM: ${e.message}`);
        guidance.contentSnippet = `Error processing article "${article.title}".`;
      }
      if (!guidance.contentSnippet && (!guidance.steps || guidance.steps.length === 0)) {
        guidance.contentSnippet = `Article "${article.title}" excerpt: ${article.content.substring(0, 150)}...`;
      }
      guidanceProvided.push(guidance);
    }

    let followUpSuggestions: string[] | undefined = undefined;
    if (guidanceProvided.length > 0 && guidanceProvided[0]) {
      const followupData: FollowupSuggestionData = { query: input.query, articleTitle: guidanceProvided[0].title };
      const followupPrompt: StructuredLLMPrompt = { task: 'generate_followup_suggestions', data: followupData };
      try {
        const followupResp = await this.llmService.generate(followupPrompt, 'cheapest');
        if (followupResp.success && followupResp.content) {
          const parsed = JSON.parse(followupResp.content);
          if (parsed && Array.isArray(parsed.suggestions) && parsed.suggestions.length > 0) {
            followUpSuggestions = parsed.suggestions.filter((s: any): s is string => typeof s === 'string');
          }
        } else { console.warn(`[LearningAndGuidanceSkill] LLM follow-up suggestions failed: ${followupResp.error}`);}
      } catch (e: any) { console.error(`[LearningAndGuidanceSkill] Error processing LLM follow-up suggestions: ${e.message}`);}
    }

    const finalResult: LearningAndGuidanceResult = {
        originalQuery: input.query,
        guidanceProvided: guidanceProvided,
        followUpSuggestions: followUpSuggestions,
        searchPerformedOn: `${relevantArticles.length} articles from ${input.applicationContext || 'General'} KB matching "${input.query.substring(0,50)}..."`
    };

    console.log(`[LearningAndGuidanceSkill] Returning guidance for query: "${input.query}"`);
    return finalResult;
  }
}

// Example Usage
/*
import { MockLLMService } from '../lib/llmUtils'; // Or OpenAIGroqService_Stub

async function testLearningAndGuidanceSkill() {
  const llmService = new MockLLMService();
  const skill = new LearningAndGuidanceSkill(llmService);

  const testInput1: LearningAndGuidanceInput = {
    userId: "user-guidance-test-1",
    query: "How do I create a pivot table in SpreadsheetApp?",
    applicationContext: "SpreadsheetApp",
    options: { preferContentType: 'how-to', maxResults: 1 }
  };
  // ... rest of test code
}
// testLearningAndGuidanceSkill();
*/
