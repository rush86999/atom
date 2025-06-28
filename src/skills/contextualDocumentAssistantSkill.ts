// Assuming invokeLLM might be moved to a shared utility later.
// For now, if it's needed here, it would be re-defined or imported.
// Let's assume for now that invokeLLM is a global-like utility function.
// If not, we'd need to pass it or instantiate it.
import { invokeLLM } from '../lib/llmUtils'; // Assuming invokeLLM is now in this path

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

// Helper function to simulate fetching documents
async function _fetchMockDocuments(documentIds?: string[]): Promise<DocumentContent[]> {
  console.log(`[_fetchMockDocuments] Attempting to fetch documents. Specified IDs: ${documentIds?.join(', ')}`);
  if (documentIds && documentIds.length > 0) {
    const foundDocs = MOCK_DOCUMENTS.filter(doc => documentIds.includes(doc.id));
    console.log(`[_fetchMockDocuments] Found ${foundDocs.length} documents matching specified IDs.`);
    return foundDocs;
  }
  console.log(`[_fetchMockDocuments] No specific IDs provided, returning all ${MOCK_DOCUMENTS.length} mock documents.`);
  return MOCK_DOCUMENTS; // Return all if no specific IDs are requested
}


/**
 * Represents the content and metadata of a document.
 */
export interface DocumentContent {
  id: string;
  title: string;
  textContent: string; // The full plain text content of the document
  tags?: string[];
  createdAt?: Date;
  // other metadata like author, source, etc. could be added
}

/**
 * Input for the ContextualDocumentAssistantSkill.
 */
export interface DocumentAssistantInput {
  query: string; // Natural language question from the user
  documentIds?: string[]; // Optional: Specific document IDs to search within
  userId: string; // For access control and personalization (not used in mock)
  options?: {
    summarize?: boolean; // Whether to generate summaries for found snippets/documents
    targetSummaryLength?: 'short' | 'medium' | 'long'; // Desired length of summaries
    maxResults?: number; // Maximum number of documents/answers to return
    snippetLength?: number; // Approximate desired length of extracted snippets in characters
  };
}

/**
 * Represents a single answer found within a document.
 */
export interface AnswerObject {
  documentId: string;
  documentTitle?: string;
  relevantSnippets: string[]; // Array of text snippets directly relevant to the query
  summary?: string; // Optional summary of the relevant information in this document
  relevanceScore?: number; // How relevant this document/answer is to the query (0.0 to 1.0)
  pageNumbers?: number[]; // Optional: Page numbers where snippets were found (if applicable)
}

/**
 * Output result from the ContextualDocumentAssistantSkill.
 */
export interface DocumentAssistantResult {
  originalQuery: string;
  answers: AnswerObject[];
  overallSummary?: string; // Optional: A global summary if requested and multiple answers found
  searchPerformedOn?: 'all_accessible' | 'specified_ids'; // Indicates the scope of the search
  // errors?: string[]; // To report any issues during processing
}

/**
 * Skill to find information within documents using natural language queries.
 */
export class ContextualDocumentAssistantSkill {
  constructor() {
    console.log("ContextualDocumentAssistantSkill initialized.");
    // In a real scenario, this might load document indexes, connect to a vector DB, etc.
  }

  /**
   * Executes the document query and assistance process.
   * @param input The DocumentAssistantInput containing the user's query and options.
   * @returns A Promise resolving to the DocumentAssistantResult.
   */
  public async execute(input: DocumentAssistantInput): Promise<DocumentAssistantResult> {
    console.log(`[ContextualDocumentAssistantSkill] Received query: "${input.query}" for user: ${input.userId}, options: ${JSON.stringify(input.options)}`);

    // 1. Validate input (query, userId)
    if (!input.query || !input.userId) {
      throw new Error("Query and userId are required for ContextualDocumentAssistantSkill.");
    }
    const snippetLength = input.options?.snippetLength || 150;
    const targetSummaryLength = input.options?.targetSummaryLength || 'medium';
    const maxResults = input.options?.maxResults || 5;


    // 2. Fetch candidate documents using _fetchMockDocuments(input.documentIds)
    const candidateDocuments = await _fetchMockDocuments(input.documentIds);
    const searchScope = input.documentIds && input.documentIds.length > 0 ? 'specified_ids' : 'all_accessible';
    console.log(`[ContextualDocumentAssistantSkill] Fetched ${candidateDocuments.length} candidate documents to process for scope: ${searchScope}.`);

    // 3. Initialize results array: answers: AnswerObject[] = []
    const answers: AnswerObject[] = [];
    let overallSummary: string | undefined = undefined;

    // 4. For each fetched document:
    //    (Loop will be limited by maxResults if many documents are returned by _fetchMockDocuments without specific IDs)
    for (const doc of candidateDocuments.slice(0, maxResults)) {
      console.log(`[ContextualDocumentAssistantSkill] Processing document: ${doc.id} - ${doc.title}`);
      //    a. Create snippetPrompt: "Given the query '${input.query}', extract up to 3 relevant snippets (each ~${snippetLength} chars) from the following document text. Return as JSON: {snippets: string[]}. Document Text: ${doc.textContent.substring(0, 2000)}..."
      const docTextSnippetForLLM = doc.textContent.substring(0, 2000); // Limit text sent to LLM
      const snippetPrompt = `
        Given the query "${input.query}", extract up to 3 most relevant snippets from the following document text.
        Each snippet should be approximately ${snippetLength} characters long.
        Return the result as a JSON object with a single key "snippets" containing an array of strings: {"snippets": ["snippet1", "snippet2", ...]}.
        If no relevant snippets are found, return {"snippets": []}.

        Document Title: "${doc.title}"
        Document Text:
        "${docTextSnippetForLLM}..."
      `;

      let extractedSnippets: string[] = [];
      try {
        const llmSnippetsResponse = await invokeLLM(snippetPrompt, 'cheapest');
        console.log(`[ContextualDocumentAssistantSkill] LLM snippets response for doc ${doc.id}: ${llmSnippetsResponse}`);
        const parsedSnippetsResponse = JSON.parse(llmSnippetsResponse);
        if (parsedSnippetsResponse && Array.isArray(parsedSnippetsResponse.snippets)) {
          extractedSnippets = parsedSnippetsResponse.snippets.filter((s: any): s is string => typeof s === 'string');
        } else {
          console.warn(`[ContextualDocumentAssistantSkill] LLM snippets response for doc ${doc.id} had invalid structure.`);
        }
      } catch (error) {
        console.error(`[ContextualDocumentAssistantSkill] Error processing LLM snippets for doc ${doc.id}:`, error);
      }

      if (extractedSnippets.length > 0) {
        const answerObject: AnswerObject = {
          documentId: doc.id,
          documentTitle: doc.title,
          relevantSnippets: extractedSnippets,
          relevanceScore: 0.75 + Math.min(0.2, extractedSnippets.length * 0.05), // Placeholder score
        };
        answers.push(answerObject); // Add to answers first, then try to summarize
      }
    } // End of document loop

    // Post-process answers for summarization if requested
    if (input.options?.summarize) {
      for (const answer of answers) {
        if (answer.relevantSnippets.length > 0) {
          const summaryPrompt = `
            Based on the query "${input.query}" and the following relevant snippets from the document titled "${answer.documentTitle}",
            provide a ${targetSummaryLength} summary.
            Return only the summary text.

            Snippets:
            ${answer.relevantSnippets.map(s => `- ${s}`).join('\n')}
          `;
          try {
            const llmSummary = await invokeLLM(summaryPrompt, 'cheapest');
            console.log(`[ContextualDocumentAssistantSkill] LLM summary for doc ${answer.documentId}: ${llmSummary}`);
            if (llmSummary && !llmSummary.toLowerCase().startsWith("llm fallback response")) {
              answer.summary = llmSummary;
            } else {
              answer.summary = "Summary could not be generated by LLM.";
              console.warn(`[ContextualDocumentAssistantSkill] LLM summary failed or returned fallback for doc ${answer.documentId}.`);
            }
          } catch (error) {
            console.error(`[ContextualDocumentAssistantSkill] Error during LLM summarization for doc ${answer.documentId}:`, error);
            answer.summary = "Error generating summary.";
          }
        }
      }
    }

    // 5. (Optional) If input.options?.summarize and multiple answers with summaries exist, generate overallSummary:
    if (input.options?.summarize && answers.some(a => a.summary)) { // Check if any answer has a summary
      const summariesToCombine = answers.filter(a => a.summary).map(a => `Summary from "${a.documentTitle}": ${a.summary}`).join('\n\n---\n\n');
      if (summariesToCombine.length > 0) { // Ensure there's something to summarize
        const overallSummaryPrompt = `
          The user's query was: "${input.query}".
          Combine the following individual summaries from different documents into one concise overall answer.
          Return only the combined summary text. Make sure it flows well and directly answers the query.

          Individual Summaries:
          ${summariesToCombine}
        `;
        try {
          const llmOverallSummary = await invokeLLM(overallSummaryPrompt, 'cheapest');
          console.log(`[ContextualDocumentAssistantSkill] LLM overall summary: ${llmOverallSummary}`);
          if (llmOverallSummary && !llmOverallSummary.toLowerCase().startsWith("llm fallback response")) {
            overallSummary = llmOverallSummary;
          } else {
            console.warn(`[ContextualDocumentAssistantSkill] LLM overall summary failed or returned fallback.`);
            // overallSummary remains undefined or could be set to a message.
          }
        } catch (error) {
          console.error(`[ContextualDocumentAssistantSkill] Error during LLM overall summarization:`, error);
          // overallSummary remains undefined
        }
      }
    }


    // 6. Construct and return DocumentAssistantResult
    const result: DocumentAssistantResult = {
      originalQuery: input.query,
      answers: answers,
      searchPerformedOn: searchScope,
      overallSummary: overallSummary,
    };

    console.log(`[ContextualDocumentAssistantSkill] Returning processed result for query: "${input.query}" with ${answers.length} answers.`);
    return result;
  }
}

// Example Usage (for testing or demonstration)
/*
async function testContextualDocSkill() {
  // Assume invokeLLM is globally available or imported for the skill to use internally
  // For testing here, we don't need to call it directly unless we're testing the skill's usage of it.

  const skill = new ContextualDocumentAssistantSkill();

  const testInput1: DocumentAssistantInput = {
    userId: "user-test-123",
    query: "What were the key decisions from the Q3 budget meeting?",
    options: {
      summarize: true,
      targetSummaryLength: 'medium',
      maxResults: 3,
      snippetLength: 200
    }
  };

  try {
    console.log("\\n--- Test Case 1: General query with summarization ---");
    const result1 = await skill.execute(testInput1);
    console.log(JSON.stringify(result1, null, 2));
  } catch (error) {
    console.error("Error during skill execution (Test Case 1):", error);
  }

  const testInput2: DocumentAssistantInput = {
    userId: "user-test-456",
    query: "Tell me about Project Phoenix in document 'proj-phoenix-brief.pdf'",
    documentIds: ["proj-phoenix-brief.pdf"], // Assuming this ID maps to a mock document
    options: {
      summarize: false, // Just snippets
    }
  };
  try {
    console.log("\\n--- Test Case 2: Query on specific document, no summary ---");
    const result2 = await skill.execute(testInput2);
    console.log(JSON.stringify(result2, null, 2));
  } catch (error) {
    console.error("Error during skill execution (Test Case 2):", error);
  }
}

// testContextualDocSkill();
*/
