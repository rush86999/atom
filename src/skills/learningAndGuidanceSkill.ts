import {
    invokeLLM,
    StructuredLLMPrompt,
    GuidanceQueryClassificationData,
    AnswerFromTextData,
    StepsFromTextData,
    FollowupSuggestionData
    // Assuming LLMTaskType is also exported if needed for casting, or rely on string values
} from '../lib/llmUtils';

// Mock Knowledge Base Data
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
    application: "General", // Applicable to multiple apps or system-wide
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

// Helper function to simulate fetching/searching knowledge base articles
async function _fetchMockKnowledgeBaseArticles(
  query: string,
  contentTypeHint?: KnowledgeBaseArticle['contentType'],
  applicationContext?: string,
  maxResults: number = 3
): Promise<KnowledgeBaseArticle[]> {
  console.log(`[_fetchMockKnowledgeBaseArticles] Query: "${query}", ContentType: ${contentTypeHint}, AppCtx: ${applicationContext}, MaxResults: ${maxResults}`);

  const queryLower = query.toLowerCase();
  const queryKeywords = queryLower.split(/\s+/).filter(kw => kw.length > 2);

  let filteredArticles = MOCK_KB_ARTICLES;

  if (applicationContext) {
    filteredArticles = filteredArticles.filter(article =>
      !article.application || article.application.toLowerCase() === applicationContext.toLowerCase() || article.application === "General"
    );
  }
  if (contentTypeHint) {
    filteredArticles = filteredArticles.filter(article => article.contentType === contentTypeHint);
  }

  // Simple keyword scoring (very basic)
  const scoredArticles = filteredArticles.map(article => {
    let score = 0;
    const titleLower = article.title.toLowerCase();
    const contentSnippetLower = article.content.substring(0, 300).toLowerCase(); // Search in snippet

    queryKeywords.forEach(kw => {
      if (titleLower.includes(kw)) score += 3;
      if (article.keywords?.some(k => k.toLowerCase().includes(kw))) score += 2;
      if (contentSnippetLower.includes(kw)) score += 1;
    });
    // Boost if content type matches common query terms
    if (queryLower.includes(article.contentType)) score +=2;


    return { article, score };
  }).filter(item => item.score > 0) // Only include articles with some match
    .sort((a, b) => b.score - a.score); // Sort by score descending

  console.log(`[_fetchMockKnowledgeBaseArticles] Found ${scoredArticles.length} potentially relevant articles after filtering and scoring.`);
  return scoredArticles.slice(0, maxResults).map(item => item.article);
}


/**
 * Represents an article or entry in the knowledge base.
 */
export interface KnowledgeBaseArticle {
  id: string;
  title: string;
  contentType: 'tutorial' | 'how-to' | 'faq' | 'workflow_guide' | 'explanation';
  application?: string; // e.g., "SpreadsheetApp", "CRM_Platform", "General"
  keywords?: string[];
  content: string; // Can be Markdown, plain text, or structured content
  steps?: { title: string; description: string; }[]; // For tutorials or workflows
  difficulty?: 'beginner' | 'intermediate' | 'advanced';
  // lastUpdatedAt?: Date;
}

/**
 * Type of guidance the user is seeking or the skill determines is needed.
 */
export type GuidanceType = 'answer_question' | 'find_tutorial' | 'guide_workflow' | 'general_explanation';

/**
 * Input for the LearningAndGuidanceSkill.
 */
export interface LearningAndGuidanceInput {
  userId: string;
  query: string; // e.g., "how do I create a pivot table in SpreadsheetApp?"
  guidanceTypeHint?: GuidanceType; // Optional hint from NLU or previous interaction
  applicationContext?: string; // Optional: current application user is in, e.g., "SpreadsheetApp"
  options?: {
    preferContentType?: KnowledgeBaseArticle['contentType'];
    maxResults?: number; // Max number of guidance items to return
  };
}

/**
 * Represents a piece of guidance provided to the user, derived from a KB article.
 */
export interface ProvidedGuidance {
  title: string; // Usually from the source KB article
  contentSnippet?: string; // A direct answer or a key snippet for explanations
  fullContent?: string; // Optional: The full content if concise or specifically requested
  steps?: { title: string; description: string; }[]; // For tutorials/workflows
  sourceArticleId: string;
  relevanceScore?: number; // How relevant this piece of guidance is to the query
}

/**
 * Output result from the LearningAndGuidanceSkill.
 */
export interface LearningAndGuidanceResult {
  originalQuery: string;
  guidanceProvided: ProvidedGuidance[];
  followUpSuggestions?: string[]; // e.g., "Learn about advanced pivot table features."
  searchPerformedOn?: string; // e.g., "KB Articles for SpreadsheetApp", "All KB Articles"
  // errors?: string[];
}

/**
 * Skill to provide tutorials, answer how-to questions, and guide users.
 */
export class LearningAndGuidanceSkill {
  constructor() {
    console.log("LearningAndGuidanceSkill initialized.");
    // In a real system, this might load/connect to a knowledge base, vector index, etc.
  }

  /**
   * Executes the learning and guidance process.
   * @param input The LearningAndGuidanceInput from the user/system.
   * @returns A Promise resolving to the LearningAndGuidanceResult.
   */
  public async execute(input: LearningAndGuidanceInput): Promise<LearningAndGuidanceResult> {
    console.log(`[LearningAndGuidanceSkill] Received query: "${input.query}" for user: ${input.userId}`);

    // Placeholder mock result
    const mockGuidance: ProvidedGuidance = {
      title: "Mock Article: How to do something",
      contentSnippet: `This is a mock answer to your query: "${input.query}". Detailed steps would be listed if this were a real tutorial.`,
      sourceArticleId: "kb-mock-001",
      relevanceScore: 0.75,
      steps: input.query.toLowerCase().includes("steps") || input.query.toLowerCase().includes("tutorial")
        ? [{title: "Step 1 Mock", description: "Do the first thing."}, {title: "Step 2 Mock", description: "Then do the second thing."}]
        : undefined,
    };

    const result: LearningAndGuidanceResult = {
      originalQuery: input.query,
      guidanceProvided: [mockGuidance],
      followUpSuggestions: ["Ask about advanced features.", "Search for another topic."],
      searchPerformedOn: input.applicationContext
        ? `Mock KB for ${input.applicationContext}`
        : "General Mock KB",
    };

    // Detailed LLM-centric logic will be outlined as comments in the next step.

    // 1. Validate input. (Basic check done, more specific validation could be added)
    const maxResults = input.options?.maxResults || 3;
    let effectiveGuidanceType: GuidanceType = input.guidanceTypeHint || 'answer_question'; // Default if no hint

    if (!input.guidanceTypeHint) {
        console.log(`[LearningAndGuidanceSkill] No guidanceTypeHint provided, attempting to classify query: "${input.query}"`);
        const classificationData: GuidanceQueryClassificationData = { query: input.query };
        const structuredClassificationPrompt: StructuredLLMPrompt = {
            task: 'classify_guidance_query',
            data: classificationData
        };
        try {
            const llmClassificationResponse = await invokeLLM(structuredClassificationPrompt, 'cheapest');
            console.log(`[LearningAndGuidanceSkill] LLM classification response: ${llmClassificationResponse}`);
            const parsedResponse = JSON.parse(llmClassificationResponse);
            const validTypes: GuidanceType[] = ['answer_question', 'find_tutorial', 'guide_workflow', 'general_explanation'];
            if (parsedResponse && parsedResponse.guidanceType && validTypes.includes(parsedResponse.guidanceType as GuidanceType)) {
                effectiveGuidanceType = parsedResponse.guidanceType as GuidanceType;
            } else {
                console.warn(`[LearningAndGuidanceSkill] LLM returned invalid or no guidanceType. Defaulting to '${effectiveGuidanceType}'. Response: ${llmClassificationResponse}`);
            }
        } catch (error) {
            console.error(`[LearningAndGuidanceSkill] Error during LLM query classification:`, error);
            // Keep the default effectiveGuidanceType
        }
    }
    console.log(`[LearningAndGuidanceSkill] Effective guidance type: ${effectiveGuidanceType}`);

    // 3. Fetch relevant articles using _fetchMockKnowledgeBaseArticles, potentially refining search terms with LLM.
    //    Example LLM call for search terms: let searchTermsForKB = await invokeLLM({task: 'extract_search_terms', data: {query: input.query}}, 'cheapest');
    const searchTerms = input.query; // Using raw query for mock fetcher
    const relevantArticles = await _fetchMockKnowledgeBaseArticles(
        searchTerms,
        input.options?.preferContentType,
        input.applicationContext,
        maxResults
    );
    console.log(`[LearningAndGuidanceSkill] Fetched ${relevantArticles.length} relevant articles.`);

    // 4. Initialize guidanceProvided: ProvidedGuidance[] = []
    const guidanceProvided: ProvidedGuidance[] = [];

    // 5. For each relevantArticle:
    for (const article of relevantArticles) {
      //    a. Based on effectiveGuidanceType:
      //        - If 'answer_question': prompt = "Answer '${input.query}' using this text: ${article.content}. Return just the answer." -> answerContent
      //        - If 'find_tutorial'/'guide_workflow': prompt = "Extract key steps for '${input.query}' from this tutorial: ${article.content}. Return as JSON {steps: [{title:'', description:''}]}" -> extractedSteps
      //        - If 'general_explanation': prompt = "Summarize this text regarding '${input.query}': ${article.content}. Return concise explanation." -> explanationContent
      //    b. Call LLM: const llmResponse = await invokeLLM(prompt, 'cheapest') (Conceptual)
      //    c. Parse llmResponse and populate a ProvidedGuidance object (title, contentSnippet/fullContent, steps, sourceArticleId, mock relevanceScore).
      //    d. Add to guidanceProvided.

      let guidance: ProvidedGuidance = {
        title: article.title,
        sourceArticleId: article.id,
        relevanceScore: 0.6, // Base relevance for being fetched
      };

      let llmResponseForArticleProcessing: string;

      switch (effectiveGuidanceType) {
        case 'answer_question':
        case 'general_explanation':
          const taskType = effectiveGuidanceType === 'answer_question' ? 'answer_from_text' : 'summarize_for_explanation';
          const answerData: AnswerFromTextData = {
            query: input.query,
            textContent: article.content.substring(0, 1500),
            articleTitle: article.title
          };
          const structuredAnswerPrompt: StructuredLLMPrompt = { task: taskType, data: answerData };
          llmResponseForArticleProcessing = await invokeLLM(structuredAnswerPrompt, 'cheapest');

          if (llmResponseForArticleProcessing && !llmResponseForArticleProcessing.toLowerCase().startsWith("llm fallback") && !llmResponseForArticleProcessing.toLowerCase().includes("not appear to contain")) {
            guidance.contentSnippet = llmResponseForArticleProcessing;
            guidance.relevanceScore = 0.8; // Higher score if LLM found direct answer
            console.log(`[LearningAndGuidanceSkill] LLM Answer/Explanation for "${article.title}": ${guidance.contentSnippet}`);
          } else {
            guidance.contentSnippet = `Article "${article.title}" was found, but a direct answer/explanation for "${input.query}" could not be extracted by the LLM. You may find relevant information within.`;
             console.log(`[LearningAndGuidanceSkill] LLM could not provide direct answer/explanation for "${article.title}" or fallback.`);
          }
          break;

        case 'find_tutorial':
        case 'guide_workflow':
        // Note: 'how-to' was used in mock _fetchKBArticles, ensure it's mapped or included in GuidanceType if distinct
        // For now, we'll treat 'how-to' effectively as 'find_tutorial' or 'guide_workflow'
          if (article.steps && article.steps.length > 0) {
            guidance.steps = article.steps;
            guidance.contentSnippet = `Found relevant steps in "${article.title}".`;
            guidance.relevanceScore = 0.85; // Higher score for direct step match
            console.log(`[LearningAndGuidanceSkill] Using predefined steps for "${article.title}".`);
          } else {
            const stepsData: StepsFromTextData = {
                query: input.query,
                textContent: article.content.substring(0, 2000),
                articleTitle: article.title
            };
            const structuredStepsPrompt: StructuredLLMPrompt = { task: 'extract_steps_from_text', data: stepsData };
            llmResponseForArticleProcessing = await invokeLLM(structuredStepsPrompt, 'cheapest');
            console.log(`[LearningAndGuidanceSkill] LLM steps response for "${article.title}": ${llmResponseForArticleProcessing}`);
            try {
              const parsedSteps = JSON.parse(llmResponseForArticleProcessing);
              if (parsedSteps && Array.isArray(parsedSteps.steps) && parsedSteps.steps.length > 0) {
                guidance.steps = parsedSteps.steps;
                guidance.contentSnippet = "Extracted the following key steps from the article:";
                guidance.relevanceScore = 0.8;
              } else {
                 guidance.contentSnippet = `While "${article.title}" is relevant, specific steps for "${input.query}" were not automatically extracted. You can review the article content.`;
              }
            } catch (e) {
              console.error(`[LearningAndGuidanceSkill] Error parsing steps JSON from LLM for "${article.title}":`, e);
              guidance.contentSnippet = `Could not extract steps for "${article.title}". The article might still be relevant.`;
            }
          }
          break;

        default: // Should not be reached if effectiveGuidanceType is always set
            guidance.contentSnippet = `Found article: ${article.title}. Displaying general information. (First 200 chars): ${article.content.substring(0, 200)}...`;
            console.warn(`[LearningAndGuidanceSkill] Unexpected guidance type: ${effectiveGuidanceType}`);
      }

      // Fallback if no specific content generated yet
      if (!guidance.contentSnippet && (!guidance.steps || guidance.steps.length === 0)) {
        guidance.contentSnippet = `Article "${article.title}" may contain information relevant to your query. (Excerpt: ${article.content.substring(0, 150)}...)`;
      }
      guidanceProvided.push(guidance);
    }

    // 6. (Optional) Generate followUpSuggestions with LLM
    let followUpSuggestions: string[] | undefined = undefined;
    if (guidanceProvided.length > 0 && guidanceProvided[0]) {
        const firstGuidanceTitle = guidanceProvided[0].title;
        const followupData: FollowupSuggestionData = {
            query: input.query,
            articleTitle: firstGuidanceTitle
        };
        const structuredFollowupPrompt: StructuredLLMPrompt = {
            task: 'generate_followup_suggestions',
            data: followupData
        };
        try {
            const llmFollowUpResponse = await invokeLLM(structuredFollowupPrompt, 'cheapest');
            console.log(`[LearningAndGuidanceSkill] LLM follow-up suggestions response: ${llmFollowUpResponse}`);
            const parsedFollowUp = JSON.parse(llmFollowUpResponse);
            if (parsedFollowUp && Array.isArray(parsedFollowUp.suggestions) && parsedFollowUp.suggestions.length > 0) {
                followUpSuggestions = parsedFollowUp.suggestions.filter((s: any): s is string => typeof s === 'string');
            }
        } catch (e) {
            console.error(`[LearningAndGuidanceSkill] Error processing LLM follow-up suggestions:`, e);
        }
    }

    result.guidanceProvided = guidanceProvided;
    result.followUpSuggestions = followUpSuggestions;
    result.searchPerformedOn = `${relevantArticles.length} articles from ${input.applicationContext || 'General'} KB matching "${searchTerms.substring(0,50)}..."`;


    console.log(`[LearningAndGuidanceSkill] Returning processed guidance for query: "${input.query}"`);
    return result;
  }
}

// Example Usage (for testing or demonstration)
/*
async function testLearningAndGuidanceSkill() {
  const skill = new LearningAndGuidanceSkill();

  const testInput1: LearningAndGuidanceInput = {
    userId: "user-guidance-test-1",
    query: "How do I create a filter in SpreadsheetApp?",
    applicationContext: "SpreadsheetApp",
    options: { preferContentType: 'how-to', maxResults: 1 }
  };
  try {
    console.log("\\n--- Test Case 1: How-to question ---");
    const result1 = await skill.execute(testInput1);
    console.log(JSON.stringify(result1, null, 2));
  } catch (error) {
    console.error("Error (Test Case 1):", error);
  }

  const testInput2: LearningAndGuidanceInput = {
    userId: "user-guidance-test-2",
    query: "Give me a tutorial on email merge",
    guidanceTypeHint: 'find_tutorial'
  };
  try {
    console.log("\\n--- Test Case 2: Find tutorial ---");
    const result2 = await skill.execute(testInput2);
    console.log(JSON.stringify(result2, null, 2));
  } catch (error) {
    console.error("Error (Test Case 2):", error);
  }
}

// testLearningAndGuidanceSkill();
*/
