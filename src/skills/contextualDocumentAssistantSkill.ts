import {
    LLMServiceInterface, // Import the interface
    StructuredLLMPrompt,
    DocumentSnippetData,
    DocumentSummaryData,
    OverallSummaryData,
    LLMTaskType // Assuming these types are exported from llmUtils
} from '../lib/llmUtils';

// Mock Documents Data Store
const MOCK_DOCUMENTS: DocumentContent[] = [
  {
    id: "doc_001",
    title: "Q3 Budget Planning Report",
    textContent: "The Q3 budget planning meeting concluded with several key decisions. Firstly, the marketing budget was increased by 15% to support the new product launch. Secondly, R&D funding for Project Alpha will be maintained at current levels, while Project Beta will see a 10% reduction. Travel expenses are to be cut by 20% across all departments. A new hiring freeze for non-essential roles was also approved. Detailed minutes will be circulated by EOD tomorrow. The next budget review is scheduled for October 5th.",
    tags: ["budget", "finance", "planning", "Q3"],
    createdAt: new Date("2023-07-15T10:00:00Z"),
  },
  {
    id: "doc_002",
    title: "Project Phoenix - Technical Overview",
    textContent: "Project Phoenix aims to refactor our legacy authentication module using modern microservices architecture. Key technologies include OAuth2, OpenID Connect, and a new identity provider service built with Go. The first phase focuses on core authentication and authorization. Phase two will introduce multi-factor authentication and biometric support. Current team members are Alice (Lead), Bob (Backend), Charlie (Frontend). Estimated completion for Phase 1 is Q4. This project is critical for enhancing security and scalability. All teams are expected to integrate with the new auth module by end of year.",
    tags: ["project phoenix", "technical", "authentication", "security", "architecture"],
    createdAt: new Date("2023-06-01T14:30:00Z"),
  },
  {
    id: "doc_003",
    title: "Marketing Strategy 2024",
    textContent: "Our 2024 marketing strategy will focus on three core pillars: digital engagement, content leadership, and community building. Digital engagement involves a revamped social media presence and targeted ad campaigns. Content leadership will be driven by weekly blog posts, monthly webinars, and a new podcast series. Community building efforts will center around our annual user conference and regional meetups. Key performance indicators (KPIs) include website traffic, conversion rates, social media engagement, and lead generation. The marketing budget for these initiatives is outlined in the Q3 budget report.",
    tags: ["marketing", "strategy", "2024", "digital", "content", "community"],
    createdAt: new Date("2023-08-01T09:00:00Z"),
  },
  {
    id: "doc_004",
    title: "Employee Handbook - Remote Work Policy",
    textContent: "This document outlines the company's remote work policy. Eligible employees may work remotely up to three days per week, subject to manager approval. Core working hours are 10 AM to 4 PM local time. Employees must ensure they have a secure and productive home office environment. All company equipment used remotely must adhere to security guidelines. For assistance, contact IT support. Regular team check-ins are mandatory. Exceptions to this policy require VP approval.",
    tags: ["hr", "policy", "remote work", "employee handbook"],
    createdAt: new Date("2023-05-10T11:00:00Z"),
  }
];

async function _fetchMockDocuments(documentIds?: string[]): Promise<DocumentContent[]> {
  // console.log(`[_fetchMockDocuments] Attempting to fetch documents. Specified IDs: ${documentIds?.join(', ')}`);
  if (documentIds && documentIds.length > 0) {
    return MOCK_DOCUMENTS.filter(doc => documentIds.includes(doc.id));
  }
  return MOCK_DOCUMENTS;
}

export interface DocumentContent {
  id: string;
  title: string;
  textContent: string;
  tags?: string[];
  createdAt?: Date;
}

export interface DocumentAssistantInput {
  query: string;
  documentIds?: string[];
  userId: string;
  options?: {
    summarize?: boolean;
    targetSummaryLength?: 'short' | 'medium' | 'long';
    maxResults?: number;
    snippetLength?: number;
  };
}

export interface AnswerObject {
  documentId: string;
  documentTitle?: string;
  relevantSnippets: string[];
  summary?: string;
  relevanceScore?: number;
  pageNumbers?: number[];
}

export interface DocumentAssistantResult {
  originalQuery: string;
  answers: AnswerObject[];
  overallSummary?: string;
  searchPerformedOn?: 'all_accessible' | 'specified_ids';
}

export class ContextualDocumentAssistantSkill {
  private readonly llmService: LLMServiceInterface;

  constructor(llmService: LLMServiceInterface) {
    this.llmService = llmService;
    console.log("ContextualDocumentAssistantSkill initialized with LLMService.");
  }

  public async execute(input: DocumentAssistantInput): Promise<DocumentAssistantResult> {
    console.log(`[ContextualDocumentAssistantSkill] Query: "${input.query}", User: ${input.userId}, Options: ${JSON.stringify(input.options)}`);

    if (!input.query || !input.userId) {
      throw new Error("Query and userId are required.");
    }
    const snippetLength = input.options?.snippetLength || 150;
    const targetSummaryLength = input.options?.targetSummaryLength || 'medium';
    const maxResults = input.options?.maxResults || 3;

    const candidateDocuments = await _fetchMockDocuments(input.documentIds);
    const searchScope = input.documentIds && input.documentIds.length > 0 ? 'specified_ids' : 'all_accessible';
    console.log(`[ContextualDocumentAssistantSkill] Fetched ${candidateDocuments.length} docs for scope: ${searchScope}.`);

    const answers: AnswerObject[] = [];
    let overallSummary: string | undefined = undefined;

    for (const doc of candidateDocuments.slice(0, maxResults)) {
      // console.log(`[ContextualDocumentAssistantSkill] Processing doc: ${doc.id} - ${doc.title}`);
      const snippetData: DocumentSnippetData = {
        query: input.query,
        documentTitle: doc.title,
        documentText: doc.textContent.substring(0, 2000),
        snippetLength: snippetLength
      };
      const structuredSnippetPrompt: StructuredLLMPrompt = { task: 'extract_document_snippets', data: snippetData };

      let extractedSnippets: string[] = [];
      try {
        const llmResponse = await this.llmService.generate(structuredSnippetPrompt, 'cheapest');
        if (llmResponse.success && llmResponse.content) {
          const parsedResp = JSON.parse(llmResponse.content);
          if (parsedResp && Array.isArray(parsedResp.snippets)) {
            extractedSnippets = parsedResp.snippets.filter((s: any): s is string => typeof s === 'string');
          } else {
            console.warn(`[ContextualDocumentAssistantSkill] Snippets resp invalid for ${doc.id}: ${llmResponse.content}`);
          }
        } else {
          console.error(`[ContextualDocumentAssistantSkill] Snippet LLM call failed for ${doc.id}: ${llmResponse.error}`);
        }
      } catch (e: any) {
        console.error(`[ContextualDocumentAssistantSkill] Error parsing snippet LLM resp for ${doc.id}: ${e.message}`);
      }

      if (extractedSnippets.length > 0) {
        const answerObject: AnswerObject = {
          documentId: doc.id,
          documentTitle: doc.title,
          relevantSnippets: extractedSnippets,
          relevanceScore: parseFloat((0.6 + Math.min(0.35, extractedSnippets.length * 0.08)).toFixed(2)),
        };
        answers.push(answerObject);
      }
    }

    if (input.options?.summarize) {
      for (const answer of answers) {
        if (answer.relevantSnippets.length > 0) {
          const docSummaryData: DocumentSummaryData = {
            query: input.query,
            documentTitle: answer.documentTitle,
            snippets: answer.relevantSnippets,
            targetLength: targetSummaryLength
          };
          const structuredDocSummaryPrompt: StructuredLLMPrompt = { task: 'summarize_document_snippets', data: docSummaryData };
          try {
            const llmResponse = await this.llmService.generate(structuredDocSummaryPrompt, 'cheapest');
            if (llmResponse.success && llmResponse.content && !llmResponse.content.toLowerCase().startsWith("llm fallback")) {
              answer.summary = llmResponse.content;
            } else {
              answer.summary = "Summary could not be generated.";
              console.warn(`[ContextualDocumentAssistantSkill] Doc summary LLM failed for ${answer.documentId}: ${llmResponse.error || llmResponse.content}`);
            }
          } catch (e: any) {
            console.error(`[ContextualDocumentAssistantSkill] Error in doc summary LLM call for ${answer.documentId}: ${e.message}`);
            answer.summary = "Error generating summary.";
          }
        }
      }

      if (answers.some(a => a.summary)) {
        const individualSummaries = answers.filter(a => a.summary).map(a => ({ title: a.documentTitle, summary: a.summary }));
        if (individualSummaries.length > 0) {
          const overallSummaryData: OverallSummaryData = { query: input.query, individualSummaries };
          const structuredOverallSummaryPrompt: StructuredLLMPrompt = { task: 'summarize_overall_answer', data: overallSummaryData };
          try {
            const llmResponse = await this.llmService.generate(structuredOverallSummaryPrompt, 'cheapest');
            if (llmResponse.success && llmResponse.content && !llmResponse.content.toLowerCase().startsWith("llm fallback")) {
              overallSummary = llmResponse.content;
            } else {
              console.warn(`[ContextualDocumentAssistantSkill] Overall summary LLM failed: ${llmResponse.error || llmResponse.content}`);
            }
          } catch (e: any) {
            console.error(`[ContextualDocumentAssistantSkill] Error in overall summary LLM call: ${e.message}`);
          }
        }
      }
    }

    const result: DocumentAssistantResult = {
      originalQuery: input.query,
      answers: answers,
      searchPerformedOn: searchScope,
      overallSummary: overallSummary,
    };

    console.log(`[ContextualDocumentAssistantSkill] Result for "${input.query}": ${answers.length} answers.`);
    return result;
  }
}

// Example Usage:
/*
import { MockLLMService, OpenAIGroqService_Stub } from '../lib/llmUtils';

async function testContextualDocSkill() {
  // const llmService = new MockLLMService();
  const llmService = new OpenAIGroqService_Stub("YOUR_GROQ_API_KEY", "YOUR_GROQ_MODEL"); // Replace with actuals
  const skill = new ContextualDocumentAssistantSkill(llmService);

  const testInput1: DocumentAssistantInput = {
    userId: "user-test-123",
    query: "What were the key decisions from the Q3 budget meeting?",
    options: { summarize: true, targetSummaryLength: 'short', maxResults: 2 }
  };
  console.log("\\n--- Test Case 1: Budget Query ---");
  const result1 = await skill.execute(testInput1);
  console.log(JSON.stringify(result1, null, 2));

  const testInput2: DocumentAssistantInput = {
    userId: "user-test-456",
    query: "Tell me about Project Phoenix security",
    documentIds: ["doc_002"],
    options: { summarize: true, snippetLength: 100 }
  };
  console.log("\\n--- Test Case 2: Phoenix Security ---");
  const result2 = await skill.execute(testInput2);
  console.log(JSON.stringify(result2, null, 2));
}
// testContextualDocSkill();
*/
