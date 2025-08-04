"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.ContextualDocumentAssistantSkill = void 0;
// Mock Documents Data Store
const MOCK_DOCUMENTS = [
    {
        id: 'doc_001',
        title: 'Q3 Budget Planning Report',
        textContent: 'The Q3 budget planning meeting concluded with several key decisions. Firstly, the marketing budget was increased by 15% to support the new product launch. Secondly, R&D funding for Project Alpha will be maintained at current levels, while Project Beta will see a 10% reduction. Travel expenses are to be cut by 20% across all departments. A new hiring freeze for non-essential roles was also approved. Detailed minutes will be circulated by EOD tomorrow. The next budget review is scheduled for October 5th.',
        tags: ['budget', 'finance', 'planning', 'Q3'],
        createdAt: new Date('2023-07-15T10:00:00Z'),
    },
    {
        id: 'doc_002',
        title: 'Project Phoenix - Technical Overview',
        textContent: 'Project Phoenix aims to refactor our legacy authentication module using modern microservices architecture. Key technologies include OAuth2, OpenID Connect, and a new identity provider service built with Go. The first phase focuses on core authentication and authorization. Phase two will introduce multi-factor authentication and biometric support. Current team members are Alice (Lead), Bob (Backend), Charlie (Frontend). Estimated completion for Phase 1 is Q4. This project is critical for enhancing security and scalability. All teams are expected to integrate with the new auth module by end of year.',
        tags: [
            'project phoenix',
            'technical',
            'authentication',
            'security',
            'architecture',
        ],
        createdAt: new Date('2023-06-01T14:30:00Z'),
    },
    {
        id: 'doc_003',
        title: 'Marketing Strategy 2024',
        textContent: 'Our 2024 marketing strategy will focus on three core pillars: digital engagement, content leadership, and community building. Digital engagement involves a revamped social media presence and targeted ad campaigns. Content leadership will be driven by weekly blog posts, monthly webinars, and a new podcast series. Community building efforts will center around our annual user conference and regional meetups. Key performance indicators (KPIs) include website traffic, conversion rates, social media engagement, and lead generation. The marketing budget for these initiatives is outlined in the Q3 budget report.',
        tags: ['marketing', 'strategy', '2024', 'digital', 'content', 'community'],
        createdAt: new Date('2023-08-01T09:00:00Z'),
    },
    {
        id: 'doc_004',
        title: 'Employee Handbook - Remote Work Policy',
        textContent: "This document outlines the company's remote work policy. Eligible employees may work remotely up to three days per week, subject to manager approval. Core working hours are 10 AM to 4 PM local time. Employees must ensure they have a secure and productive home office environment. All company equipment used remotely must adhere to security guidelines. For assistance, contact IT support. Regular team check-ins are mandatory. Exceptions to this policy require VP approval.",
        tags: ['hr', 'policy', 'remote work', 'employee handbook'],
        createdAt: new Date('2023-05-10T11:00:00Z'),
    },
];
async function _fetchMockDocuments(documentIds) {
    // console.log(`[_fetchMockDocuments] Attempting to fetch documents. Specified IDs: ${documentIds?.join(', ')}`);
    if (documentIds && documentIds.length > 0) {
        return MOCK_DOCUMENTS.filter((doc) => documentIds.includes(doc.id));
    }
    return MOCK_DOCUMENTS;
}
class ContextualDocumentAssistantSkill {
    llmService;
    constructor(llmService) {
        this.llmService = llmService;
        console.log('ContextualDocumentAssistantSkill initialized with LLMService.');
    }
    async execute(input) {
        console.log(`[ContextualDocumentAssistantSkill] Query: "${input.query}", User: ${input.userId}, Options: ${JSON.stringify(input.options)}`);
        if (!input.query || !input.userId) {
            throw new Error('Query and userId are required.');
        }
        const snippetLength = input.options?.snippetLength || 150;
        const targetSummaryLength = input.options?.targetSummaryLength || 'medium';
        const maxResults = input.options?.maxResults || 3;
        const candidateDocuments = await _fetchMockDocuments(input.documentIds);
        const searchScope = input.documentIds && input.documentIds.length > 0
            ? 'specified_ids'
            : 'all_accessible';
        console.log(`[ContextualDocumentAssistantSkill] Fetched ${candidateDocuments.length} docs for scope: ${searchScope}.`);
        const answers = [];
        let overallSummary = undefined;
        for (const doc of candidateDocuments.slice(0, maxResults)) {
            // console.log(`[ContextualDocumentAssistantSkill] Processing doc: ${doc.id} - ${doc.title}`);
            const snippetData = {
                query: input.query,
                documentTitle: doc.title,
                documentText: doc.textContent.substring(0, 2000),
                snippetLength: snippetLength,
            };
            const structuredSnippetPrompt = {
                task: 'extract_document_snippets',
                data: snippetData,
            };
            let extractedSnippets = [];
            try {
                const llmResponse = await this.llmService.generate(structuredSnippetPrompt, 'cheapest');
                if (llmResponse.success && llmResponse.content) {
                    const parsedResp = JSON.parse(llmResponse.content);
                    if (parsedResp && Array.isArray(parsedResp.snippets)) {
                        extractedSnippets = parsedResp.snippets.filter((s) => typeof s === 'string');
                    }
                    else {
                        console.warn(`[ContextualDocumentAssistantSkill] Snippets resp invalid for ${doc.id}: ${llmResponse.content}`);
                    }
                }
                else {
                    console.error(`[ContextualDocumentAssistantSkill] Snippet LLM call failed for ${doc.id}: ${llmResponse.error}`);
                }
            }
            catch (e) {
                console.error(`[ContextualDocumentAssistantSkill] Error parsing snippet LLM resp for ${doc.id}: ${e.message}`);
            }
            if (extractedSnippets.length > 0) {
                const answerObject = {
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
                    const docSummaryData = {
                        query: input.query,
                        documentTitle: answer.documentTitle,
                        snippets: answer.relevantSnippets,
                        targetLength: targetSummaryLength,
                    };
                    const structuredDocSummaryPrompt = {
                        task: 'summarize_document_snippets',
                        data: docSummaryData,
                    };
                    try {
                        const llmResponse = await this.llmService.generate(structuredDocSummaryPrompt, 'cheapest');
                        if (llmResponse.success &&
                            llmResponse.content &&
                            !llmResponse.content.toLowerCase().startsWith('llm fallback')) {
                            answer.summary = llmResponse.content;
                        }
                        else {
                            answer.summary = 'Summary could not be generated.';
                            console.warn(`[ContextualDocumentAssistantSkill] Doc summary LLM failed for ${answer.documentId}: ${llmResponse.error || llmResponse.content}`);
                        }
                    }
                    catch (e) {
                        console.error(`[ContextualDocumentAssistantSkill] Error in doc summary LLM call for ${answer.documentId}: ${e.message}`);
                        answer.summary = 'Error generating summary.';
                    }
                }
            }
            if (answers.some((a) => a.summary)) {
                const individualSummaries = answers
                    .filter((a) => a.summary)
                    .map((a) => ({ title: a.documentTitle, summary: a.summary }));
                if (individualSummaries.length > 0) {
                    const overallSummaryData = {
                        query: input.query,
                        individualSummaries,
                    };
                    const structuredOverallSummaryPrompt = {
                        task: 'summarize_overall_answer',
                        data: overallSummaryData,
                    };
                    try {
                        const llmResponse = await this.llmService.generate(structuredOverallSummaryPrompt, 'cheapest');
                        if (llmResponse.success &&
                            llmResponse.content &&
                            !llmResponse.content.toLowerCase().startsWith('llm fallback')) {
                            overallSummary = llmResponse.content;
                        }
                        else {
                            console.warn(`[ContextualDocumentAssistantSkill] Overall summary LLM failed: ${llmResponse.error || llmResponse.content}`);
                        }
                    }
                    catch (e) {
                        console.error(`[ContextualDocumentAssistantSkill] Error in overall summary LLM call: ${e.message}`);
                    }
                }
            }
        }
        const result = {
            originalQuery: input.query,
            answers: answers,
            searchPerformedOn: searchScope,
            overallSummary: overallSummary,
        };
        console.log(`[ContextualDocumentAssistantSkill] Result for "${input.query}": ${answers.length} answers.`);
        return result;
    }
}
exports.ContextualDocumentAssistantSkill = ContextualDocumentAssistantSkill;
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
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiY29udGV4dHVhbERvY3VtZW50QXNzaXN0YW50U2tpbGwuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJjb250ZXh0dWFsRG9jdW1lbnRBc3Npc3RhbnRTa2lsbC50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiOzs7QUFTQSw0QkFBNEI7QUFDNUIsTUFBTSxjQUFjLEdBQXNCO0lBQ3hDO1FBQ0UsRUFBRSxFQUFFLFNBQVM7UUFDYixLQUFLLEVBQUUsMkJBQTJCO1FBQ2xDLFdBQVcsRUFDVCw2ZkFBNmY7UUFDL2YsSUFBSSxFQUFFLENBQUMsUUFBUSxFQUFFLFNBQVMsRUFBRSxVQUFVLEVBQUUsSUFBSSxDQUFDO1FBQzdDLFNBQVMsRUFBRSxJQUFJLElBQUksQ0FBQyxzQkFBc0IsQ0FBQztLQUM1QztJQUNEO1FBQ0UsRUFBRSxFQUFFLFNBQVM7UUFDYixLQUFLLEVBQUUsc0NBQXNDO1FBQzdDLFdBQVcsRUFDVCw4bEJBQThsQjtRQUNobUIsSUFBSSxFQUFFO1lBQ0osaUJBQWlCO1lBQ2pCLFdBQVc7WUFDWCxnQkFBZ0I7WUFDaEIsVUFBVTtZQUNWLGNBQWM7U0FDZjtRQUNELFNBQVMsRUFBRSxJQUFJLElBQUksQ0FBQyxzQkFBc0IsQ0FBQztLQUM1QztJQUNEO1FBQ0UsRUFBRSxFQUFFLFNBQVM7UUFDYixLQUFLLEVBQUUseUJBQXlCO1FBQ2hDLFdBQVcsRUFDVCxxbUJBQXFtQjtRQUN2bUIsSUFBSSxFQUFFLENBQUMsV0FBVyxFQUFFLFVBQVUsRUFBRSxNQUFNLEVBQUUsU0FBUyxFQUFFLFNBQVMsRUFBRSxXQUFXLENBQUM7UUFDMUUsU0FBUyxFQUFFLElBQUksSUFBSSxDQUFDLHNCQUFzQixDQUFDO0tBQzVDO0lBQ0Q7UUFDRSxFQUFFLEVBQUUsU0FBUztRQUNiLEtBQUssRUFBRSx3Q0FBd0M7UUFDL0MsV0FBVyxFQUNULDBkQUEwZDtRQUM1ZCxJQUFJLEVBQUUsQ0FBQyxJQUFJLEVBQUUsUUFBUSxFQUFFLGFBQWEsRUFBRSxtQkFBbUIsQ0FBQztRQUMxRCxTQUFTLEVBQUUsSUFBSSxJQUFJLENBQUMsc0JBQXNCLENBQUM7S0FDNUM7Q0FDRixDQUFDO0FBRUYsS0FBSyxVQUFVLG1CQUFtQixDQUNoQyxXQUFzQjtJQUV0QixpSEFBaUg7SUFDakgsSUFBSSxXQUFXLElBQUksV0FBVyxDQUFDLE1BQU0sR0FBRyxDQUFDLEVBQUUsQ0FBQztRQUMxQyxPQUFPLGNBQWMsQ0FBQyxNQUFNLENBQUMsQ0FBQyxHQUFHLEVBQUUsRUFBRSxDQUFDLFdBQVcsQ0FBQyxRQUFRLENBQUMsR0FBRyxDQUFDLEVBQUUsQ0FBQyxDQUFDLENBQUM7SUFDdEUsQ0FBQztJQUNELE9BQU8sY0FBYyxDQUFDO0FBQ3hCLENBQUM7QUFzQ0QsTUFBYSxnQ0FBZ0M7SUFDMUIsVUFBVSxDQUFzQjtJQUVqRCxZQUFZLFVBQStCO1FBQ3pDLElBQUksQ0FBQyxVQUFVLEdBQUcsVUFBVSxDQUFDO1FBQzdCLE9BQU8sQ0FBQyxHQUFHLENBQ1QsK0RBQStELENBQ2hFLENBQUM7SUFDSixDQUFDO0lBRU0sS0FBSyxDQUFDLE9BQU8sQ0FDbEIsS0FBNkI7UUFFN0IsT0FBTyxDQUFDLEdBQUcsQ0FDVCw4Q0FBOEMsS0FBSyxDQUFDLEtBQUssWUFBWSxLQUFLLENBQUMsTUFBTSxjQUFjLElBQUksQ0FBQyxTQUFTLENBQUMsS0FBSyxDQUFDLE9BQU8sQ0FBQyxFQUFFLENBQy9ILENBQUM7UUFFRixJQUFJLENBQUMsS0FBSyxDQUFDLEtBQUssSUFBSSxDQUFDLEtBQUssQ0FBQyxNQUFNLEVBQUUsQ0FBQztZQUNsQyxNQUFNLElBQUksS0FBSyxDQUFDLGdDQUFnQyxDQUFDLENBQUM7UUFDcEQsQ0FBQztRQUNELE1BQU0sYUFBYSxHQUFHLEtBQUssQ0FBQyxPQUFPLEVBQUUsYUFBYSxJQUFJLEdBQUcsQ0FBQztRQUMxRCxNQUFNLG1CQUFtQixHQUFHLEtBQUssQ0FBQyxPQUFPLEVBQUUsbUJBQW1CLElBQUksUUFBUSxDQUFDO1FBQzNFLE1BQU0sVUFBVSxHQUFHLEtBQUssQ0FBQyxPQUFPLEVBQUUsVUFBVSxJQUFJLENBQUMsQ0FBQztRQUVsRCxNQUFNLGtCQUFrQixHQUFHLE1BQU0sbUJBQW1CLENBQUMsS0FBSyxDQUFDLFdBQVcsQ0FBQyxDQUFDO1FBQ3hFLE1BQU0sV0FBVyxHQUNmLEtBQUssQ0FBQyxXQUFXLElBQUksS0FBSyxDQUFDLFdBQVcsQ0FBQyxNQUFNLEdBQUcsQ0FBQztZQUMvQyxDQUFDLENBQUMsZUFBZTtZQUNqQixDQUFDLENBQUMsZ0JBQWdCLENBQUM7UUFDdkIsT0FBTyxDQUFDLEdBQUcsQ0FDVCw4Q0FBOEMsa0JBQWtCLENBQUMsTUFBTSxvQkFBb0IsV0FBVyxHQUFHLENBQzFHLENBQUM7UUFFRixNQUFNLE9BQU8sR0FBbUIsRUFBRSxDQUFDO1FBQ25DLElBQUksY0FBYyxHQUF1QixTQUFTLENBQUM7UUFFbkQsS0FBSyxNQUFNLEdBQUcsSUFBSSxrQkFBa0IsQ0FBQyxLQUFLLENBQUMsQ0FBQyxFQUFFLFVBQVUsQ0FBQyxFQUFFLENBQUM7WUFDMUQsOEZBQThGO1lBQzlGLE1BQU0sV0FBVyxHQUF3QjtnQkFDdkMsS0FBSyxFQUFFLEtBQUssQ0FBQyxLQUFLO2dCQUNsQixhQUFhLEVBQUUsR0FBRyxDQUFDLEtBQUs7Z0JBQ3hCLFlBQVksRUFBRSxHQUFHLENBQUMsV0FBVyxDQUFDLFNBQVMsQ0FBQyxDQUFDLEVBQUUsSUFBSSxDQUFDO2dCQUNoRCxhQUFhLEVBQUUsYUFBYTthQUM3QixDQUFDO1lBQ0YsTUFBTSx1QkFBdUIsR0FBd0I7Z0JBQ25ELElBQUksRUFBRSwyQkFBMkI7Z0JBQ2pDLElBQUksRUFBRSxXQUFXO2FBQ2xCLENBQUM7WUFFRixJQUFJLGlCQUFpQixHQUFhLEVBQUUsQ0FBQztZQUNyQyxJQUFJLENBQUM7Z0JBQ0gsTUFBTSxXQUFXLEdBQUcsTUFBTSxJQUFJLENBQUMsVUFBVSxDQUFDLFFBQVEsQ0FDaEQsdUJBQXVCLEVBQ3ZCLFVBQVUsQ0FDWCxDQUFDO2dCQUNGLElBQUksV0FBVyxDQUFDLE9BQU8sSUFBSSxXQUFXLENBQUMsT0FBTyxFQUFFLENBQUM7b0JBQy9DLE1BQU0sVUFBVSxHQUFHLElBQUksQ0FBQyxLQUFLLENBQUMsV0FBVyxDQUFDLE9BQU8sQ0FBQyxDQUFDO29CQUNuRCxJQUFJLFVBQVUsSUFBSSxLQUFLLENBQUMsT0FBTyxDQUFDLFVBQVUsQ0FBQyxRQUFRLENBQUMsRUFBRSxDQUFDO3dCQUNyRCxpQkFBaUIsR0FBRyxVQUFVLENBQUMsUUFBUSxDQUFDLE1BQU0sQ0FDNUMsQ0FBQyxDQUFNLEVBQWUsRUFBRSxDQUFDLE9BQU8sQ0FBQyxLQUFLLFFBQVEsQ0FDL0MsQ0FBQztvQkFDSixDQUFDO3lCQUFNLENBQUM7d0JBQ04sT0FBTyxDQUFDLElBQUksQ0FDVixnRUFBZ0UsR0FBRyxDQUFDLEVBQUUsS0FBSyxXQUFXLENBQUMsT0FBTyxFQUFFLENBQ2pHLENBQUM7b0JBQ0osQ0FBQztnQkFDSCxDQUFDO3FCQUFNLENBQUM7b0JBQ04sT0FBTyxDQUFDLEtBQUssQ0FDWCxrRUFBa0UsR0FBRyxDQUFDLEVBQUUsS0FBSyxXQUFXLENBQUMsS0FBSyxFQUFFLENBQ2pHLENBQUM7Z0JBQ0osQ0FBQztZQUNILENBQUM7WUFBQyxPQUFPLENBQU0sRUFBRSxDQUFDO2dCQUNoQixPQUFPLENBQUMsS0FBSyxDQUNYLHlFQUF5RSxHQUFHLENBQUMsRUFBRSxLQUFLLENBQUMsQ0FBQyxPQUFPLEVBQUUsQ0FDaEcsQ0FBQztZQUNKLENBQUM7WUFFRCxJQUFJLGlCQUFpQixDQUFDLE1BQU0sR0FBRyxDQUFDLEVBQUUsQ0FBQztnQkFDakMsTUFBTSxZQUFZLEdBQWlCO29CQUNqQyxVQUFVLEVBQUUsR0FBRyxDQUFDLEVBQUU7b0JBQ2xCLGFBQWEsRUFBRSxHQUFHLENBQUMsS0FBSztvQkFDeEIsZ0JBQWdCLEVBQUUsaUJBQWlCO29CQUNuQyxjQUFjLEVBQUUsVUFBVSxDQUN4QixDQUFDLEdBQUcsR0FBRyxJQUFJLENBQUMsR0FBRyxDQUFDLElBQUksRUFBRSxpQkFBaUIsQ0FBQyxNQUFNLEdBQUcsSUFBSSxDQUFDLENBQUMsQ0FBQyxPQUFPLENBQUMsQ0FBQyxDQUFDLENBQ25FO2lCQUNGLENBQUM7Z0JBQ0YsT0FBTyxDQUFDLElBQUksQ0FBQyxZQUFZLENBQUMsQ0FBQztZQUM3QixDQUFDO1FBQ0gsQ0FBQztRQUVELElBQUksS0FBSyxDQUFDLE9BQU8sRUFBRSxTQUFTLEVBQUUsQ0FBQztZQUM3QixLQUFLLE1BQU0sTUFBTSxJQUFJLE9BQU8sRUFBRSxDQUFDO2dCQUM3QixJQUFJLE1BQU0sQ0FBQyxnQkFBZ0IsQ0FBQyxNQUFNLEdBQUcsQ0FBQyxFQUFFLENBQUM7b0JBQ3ZDLE1BQU0sY0FBYyxHQUF3Qjt3QkFDMUMsS0FBSyxFQUFFLEtBQUssQ0FBQyxLQUFLO3dCQUNsQixhQUFhLEVBQUUsTUFBTSxDQUFDLGFBQWE7d0JBQ25DLFFBQVEsRUFBRSxNQUFNLENBQUMsZ0JBQWdCO3dCQUNqQyxZQUFZLEVBQUUsbUJBQW1CO3FCQUNsQyxDQUFDO29CQUNGLE1BQU0sMEJBQTBCLEdBQXdCO3dCQUN0RCxJQUFJLEVBQUUsNkJBQTZCO3dCQUNuQyxJQUFJLEVBQUUsY0FBYztxQkFDckIsQ0FBQztvQkFDRixJQUFJLENBQUM7d0JBQ0gsTUFBTSxXQUFXLEdBQUcsTUFBTSxJQUFJLENBQUMsVUFBVSxDQUFDLFFBQVEsQ0FDaEQsMEJBQTBCLEVBQzFCLFVBQVUsQ0FDWCxDQUFDO3dCQUNGLElBQ0UsV0FBVyxDQUFDLE9BQU87NEJBQ25CLFdBQVcsQ0FBQyxPQUFPOzRCQUNuQixDQUFDLFdBQVcsQ0FBQyxPQUFPLENBQUMsV0FBVyxFQUFFLENBQUMsVUFBVSxDQUFDLGNBQWMsQ0FBQyxFQUM3RCxDQUFDOzRCQUNELE1BQU0sQ0FBQyxPQUFPLEdBQUcsV0FBVyxDQUFDLE9BQU8sQ0FBQzt3QkFDdkMsQ0FBQzs2QkFBTSxDQUFDOzRCQUNOLE1BQU0sQ0FBQyxPQUFPLEdBQUcsaUNBQWlDLENBQUM7NEJBQ25ELE9BQU8sQ0FBQyxJQUFJLENBQ1YsaUVBQWlFLE1BQU0sQ0FBQyxVQUFVLEtBQUssV0FBVyxDQUFDLEtBQUssSUFBSSxXQUFXLENBQUMsT0FBTyxFQUFFLENBQ2xJLENBQUM7d0JBQ0osQ0FBQztvQkFDSCxDQUFDO29CQUFDLE9BQU8sQ0FBTSxFQUFFLENBQUM7d0JBQ2hCLE9BQU8sQ0FBQyxLQUFLLENBQ1gsd0VBQXdFLE1BQU0sQ0FBQyxVQUFVLEtBQUssQ0FBQyxDQUFDLE9BQU8sRUFBRSxDQUMxRyxDQUFDO3dCQUNGLE1BQU0sQ0FBQyxPQUFPLEdBQUcsMkJBQTJCLENBQUM7b0JBQy9DLENBQUM7Z0JBQ0gsQ0FBQztZQUNILENBQUM7WUFFRCxJQUFJLE9BQU8sQ0FBQyxJQUFJLENBQUMsQ0FBQyxDQUFDLEVBQUUsRUFBRSxDQUFDLENBQUMsQ0FBQyxPQUFPLENBQUMsRUFBRSxDQUFDO2dCQUNuQyxNQUFNLG1CQUFtQixHQUFHLE9BQU87cUJBQ2hDLE1BQU0sQ0FBQyxDQUFDLENBQUMsRUFBRSxFQUFFLENBQUMsQ0FBQyxDQUFDLE9BQU8sQ0FBQztxQkFDeEIsR0FBRyxDQUFDLENBQUMsQ0FBQyxFQUFFLEVBQUUsQ0FBQyxDQUFDLEVBQUUsS0FBSyxFQUFFLENBQUMsQ0FBQyxhQUFhLEVBQUUsT0FBTyxFQUFFLENBQUMsQ0FBQyxPQUFPLEVBQUUsQ0FBQyxDQUFDLENBQUM7Z0JBQ2hFLElBQUksbUJBQW1CLENBQUMsTUFBTSxHQUFHLENBQUMsRUFBRSxDQUFDO29CQUNuQyxNQUFNLGtCQUFrQixHQUF1Qjt3QkFDN0MsS0FBSyxFQUFFLEtBQUssQ0FBQyxLQUFLO3dCQUNsQixtQkFBbUI7cUJBQ3BCLENBQUM7b0JBQ0YsTUFBTSw4QkFBOEIsR0FBd0I7d0JBQzFELElBQUksRUFBRSwwQkFBMEI7d0JBQ2hDLElBQUksRUFBRSxrQkFBa0I7cUJBQ3pCLENBQUM7b0JBQ0YsSUFBSSxDQUFDO3dCQUNILE1BQU0sV0FBVyxHQUFHLE1BQU0sSUFBSSxDQUFDLFVBQVUsQ0FBQyxRQUFRLENBQ2hELDhCQUE4QixFQUM5QixVQUFVLENBQ1gsQ0FBQzt3QkFDRixJQUNFLFdBQVcsQ0FBQyxPQUFPOzRCQUNuQixXQUFXLENBQUMsT0FBTzs0QkFDbkIsQ0FBQyxXQUFXLENBQUMsT0FBTyxDQUFDLFdBQVcsRUFBRSxDQUFDLFVBQVUsQ0FBQyxjQUFjLENBQUMsRUFDN0QsQ0FBQzs0QkFDRCxjQUFjLEdBQUcsV0FBVyxDQUFDLE9BQU8sQ0FBQzt3QkFDdkMsQ0FBQzs2QkFBTSxDQUFDOzRCQUNOLE9BQU8sQ0FBQyxJQUFJLENBQ1Ysa0VBQWtFLFdBQVcsQ0FBQyxLQUFLLElBQUksV0FBVyxDQUFDLE9BQU8sRUFBRSxDQUM3RyxDQUFDO3dCQUNKLENBQUM7b0JBQ0gsQ0FBQztvQkFBQyxPQUFPLENBQU0sRUFBRSxDQUFDO3dCQUNoQixPQUFPLENBQUMsS0FBSyxDQUNYLHlFQUF5RSxDQUFDLENBQUMsT0FBTyxFQUFFLENBQ3JGLENBQUM7b0JBQ0osQ0FBQztnQkFDSCxDQUFDO1lBQ0gsQ0FBQztRQUNILENBQUM7UUFFRCxNQUFNLE1BQU0sR0FBNEI7WUFDdEMsYUFBYSxFQUFFLEtBQUssQ0FBQyxLQUFLO1lBQzFCLE9BQU8sRUFBRSxPQUFPO1lBQ2hCLGlCQUFpQixFQUFFLFdBQVc7WUFDOUIsY0FBYyxFQUFFLGNBQWM7U0FDL0IsQ0FBQztRQUVGLE9BQU8sQ0FBQyxHQUFHLENBQ1Qsa0RBQWtELEtBQUssQ0FBQyxLQUFLLE1BQU0sT0FBTyxDQUFDLE1BQU0sV0FBVyxDQUM3RixDQUFDO1FBQ0YsT0FBTyxNQUFNLENBQUM7SUFDaEIsQ0FBQztDQUNGO0FBbkxELDRFQW1MQztBQUVELGlCQUFpQjtBQUNqQjs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7Ozs7OztFQTRCRSIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7XG4gIExMTVNlcnZpY2VJbnRlcmZhY2UsIC8vIEltcG9ydCB0aGUgaW50ZXJmYWNlXG4gIFN0cnVjdHVyZWRMTE1Qcm9tcHQsXG4gIERvY3VtZW50U25pcHBldERhdGEsXG4gIERvY3VtZW50U3VtbWFyeURhdGEsXG4gIE92ZXJhbGxTdW1tYXJ5RGF0YSxcbiAgTExNVGFza1R5cGUsIC8vIEFzc3VtaW5nIHRoZXNlIHR5cGVzIGFyZSBleHBvcnRlZCBmcm9tIGxsbVV0aWxzXG59IGZyb20gJy4uL2xpYi9sbG1VdGlscyc7XG5cbi8vIE1vY2sgRG9jdW1lbnRzIERhdGEgU3RvcmVcbmNvbnN0IE1PQ0tfRE9DVU1FTlRTOiBEb2N1bWVudENvbnRlbnRbXSA9IFtcbiAge1xuICAgIGlkOiAnZG9jXzAwMScsXG4gICAgdGl0bGU6ICdRMyBCdWRnZXQgUGxhbm5pbmcgUmVwb3J0JyxcbiAgICB0ZXh0Q29udGVudDpcbiAgICAgICdUaGUgUTMgYnVkZ2V0IHBsYW5uaW5nIG1lZXRpbmcgY29uY2x1ZGVkIHdpdGggc2V2ZXJhbCBrZXkgZGVjaXNpb25zLiBGaXJzdGx5LCB0aGUgbWFya2V0aW5nIGJ1ZGdldCB3YXMgaW5jcmVhc2VkIGJ5IDE1JSB0byBzdXBwb3J0IHRoZSBuZXcgcHJvZHVjdCBsYXVuY2guIFNlY29uZGx5LCBSJkQgZnVuZGluZyBmb3IgUHJvamVjdCBBbHBoYSB3aWxsIGJlIG1haW50YWluZWQgYXQgY3VycmVudCBsZXZlbHMsIHdoaWxlIFByb2plY3QgQmV0YSB3aWxsIHNlZSBhIDEwJSByZWR1Y3Rpb24uIFRyYXZlbCBleHBlbnNlcyBhcmUgdG8gYmUgY3V0IGJ5IDIwJSBhY3Jvc3MgYWxsIGRlcGFydG1lbnRzLiBBIG5ldyBoaXJpbmcgZnJlZXplIGZvciBub24tZXNzZW50aWFsIHJvbGVzIHdhcyBhbHNvIGFwcHJvdmVkLiBEZXRhaWxlZCBtaW51dGVzIHdpbGwgYmUgY2lyY3VsYXRlZCBieSBFT0QgdG9tb3Jyb3cuIFRoZSBuZXh0IGJ1ZGdldCByZXZpZXcgaXMgc2NoZWR1bGVkIGZvciBPY3RvYmVyIDV0aC4nLFxuICAgIHRhZ3M6IFsnYnVkZ2V0JywgJ2ZpbmFuY2UnLCAncGxhbm5pbmcnLCAnUTMnXSxcbiAgICBjcmVhdGVkQXQ6IG5ldyBEYXRlKCcyMDIzLTA3LTE1VDEwOjAwOjAwWicpLFxuICB9LFxuICB7XG4gICAgaWQ6ICdkb2NfMDAyJyxcbiAgICB0aXRsZTogJ1Byb2plY3QgUGhvZW5peCAtIFRlY2huaWNhbCBPdmVydmlldycsXG4gICAgdGV4dENvbnRlbnQ6XG4gICAgICAnUHJvamVjdCBQaG9lbml4IGFpbXMgdG8gcmVmYWN0b3Igb3VyIGxlZ2FjeSBhdXRoZW50aWNhdGlvbiBtb2R1bGUgdXNpbmcgbW9kZXJuIG1pY3Jvc2VydmljZXMgYXJjaGl0ZWN0dXJlLiBLZXkgdGVjaG5vbG9naWVzIGluY2x1ZGUgT0F1dGgyLCBPcGVuSUQgQ29ubmVjdCwgYW5kIGEgbmV3IGlkZW50aXR5IHByb3ZpZGVyIHNlcnZpY2UgYnVpbHQgd2l0aCBHby4gVGhlIGZpcnN0IHBoYXNlIGZvY3VzZXMgb24gY29yZSBhdXRoZW50aWNhdGlvbiBhbmQgYXV0aG9yaXphdGlvbi4gUGhhc2UgdHdvIHdpbGwgaW50cm9kdWNlIG11bHRpLWZhY3RvciBhdXRoZW50aWNhdGlvbiBhbmQgYmlvbWV0cmljIHN1cHBvcnQuIEN1cnJlbnQgdGVhbSBtZW1iZXJzIGFyZSBBbGljZSAoTGVhZCksIEJvYiAoQmFja2VuZCksIENoYXJsaWUgKEZyb250ZW5kKS4gRXN0aW1hdGVkIGNvbXBsZXRpb24gZm9yIFBoYXNlIDEgaXMgUTQuIFRoaXMgcHJvamVjdCBpcyBjcml0aWNhbCBmb3IgZW5oYW5jaW5nIHNlY3VyaXR5IGFuZCBzY2FsYWJpbGl0eS4gQWxsIHRlYW1zIGFyZSBleHBlY3RlZCB0byBpbnRlZ3JhdGUgd2l0aCB0aGUgbmV3IGF1dGggbW9kdWxlIGJ5IGVuZCBvZiB5ZWFyLicsXG4gICAgdGFnczogW1xuICAgICAgJ3Byb2plY3QgcGhvZW5peCcsXG4gICAgICAndGVjaG5pY2FsJyxcbiAgICAgICdhdXRoZW50aWNhdGlvbicsXG4gICAgICAnc2VjdXJpdHknLFxuICAgICAgJ2FyY2hpdGVjdHVyZScsXG4gICAgXSxcbiAgICBjcmVhdGVkQXQ6IG5ldyBEYXRlKCcyMDIzLTA2LTAxVDE0OjMwOjAwWicpLFxuICB9LFxuICB7XG4gICAgaWQ6ICdkb2NfMDAzJyxcbiAgICB0aXRsZTogJ01hcmtldGluZyBTdHJhdGVneSAyMDI0JyxcbiAgICB0ZXh0Q29udGVudDpcbiAgICAgICdPdXIgMjAyNCBtYXJrZXRpbmcgc3RyYXRlZ3kgd2lsbCBmb2N1cyBvbiB0aHJlZSBjb3JlIHBpbGxhcnM6IGRpZ2l0YWwgZW5nYWdlbWVudCwgY29udGVudCBsZWFkZXJzaGlwLCBhbmQgY29tbXVuaXR5IGJ1aWxkaW5nLiBEaWdpdGFsIGVuZ2FnZW1lbnQgaW52b2x2ZXMgYSByZXZhbXBlZCBzb2NpYWwgbWVkaWEgcHJlc2VuY2UgYW5kIHRhcmdldGVkIGFkIGNhbXBhaWducy4gQ29udGVudCBsZWFkZXJzaGlwIHdpbGwgYmUgZHJpdmVuIGJ5IHdlZWtseSBibG9nIHBvc3RzLCBtb250aGx5IHdlYmluYXJzLCBhbmQgYSBuZXcgcG9kY2FzdCBzZXJpZXMuIENvbW11bml0eSBidWlsZGluZyBlZmZvcnRzIHdpbGwgY2VudGVyIGFyb3VuZCBvdXIgYW5udWFsIHVzZXIgY29uZmVyZW5jZSBhbmQgcmVnaW9uYWwgbWVldHVwcy4gS2V5IHBlcmZvcm1hbmNlIGluZGljYXRvcnMgKEtQSXMpIGluY2x1ZGUgd2Vic2l0ZSB0cmFmZmljLCBjb252ZXJzaW9uIHJhdGVzLCBzb2NpYWwgbWVkaWEgZW5nYWdlbWVudCwgYW5kIGxlYWQgZ2VuZXJhdGlvbi4gVGhlIG1hcmtldGluZyBidWRnZXQgZm9yIHRoZXNlIGluaXRpYXRpdmVzIGlzIG91dGxpbmVkIGluIHRoZSBRMyBidWRnZXQgcmVwb3J0LicsXG4gICAgdGFnczogWydtYXJrZXRpbmcnLCAnc3RyYXRlZ3knLCAnMjAyNCcsICdkaWdpdGFsJywgJ2NvbnRlbnQnLCAnY29tbXVuaXR5J10sXG4gICAgY3JlYXRlZEF0OiBuZXcgRGF0ZSgnMjAyMy0wOC0wMVQwOTowMDowMFonKSxcbiAgfSxcbiAge1xuICAgIGlkOiAnZG9jXzAwNCcsXG4gICAgdGl0bGU6ICdFbXBsb3llZSBIYW5kYm9vayAtIFJlbW90ZSBXb3JrIFBvbGljeScsXG4gICAgdGV4dENvbnRlbnQ6XG4gICAgICBcIlRoaXMgZG9jdW1lbnQgb3V0bGluZXMgdGhlIGNvbXBhbnkncyByZW1vdGUgd29yayBwb2xpY3kuIEVsaWdpYmxlIGVtcGxveWVlcyBtYXkgd29yayByZW1vdGVseSB1cCB0byB0aHJlZSBkYXlzIHBlciB3ZWVrLCBzdWJqZWN0IHRvIG1hbmFnZXIgYXBwcm92YWwuIENvcmUgd29ya2luZyBob3VycyBhcmUgMTAgQU0gdG8gNCBQTSBsb2NhbCB0aW1lLiBFbXBsb3llZXMgbXVzdCBlbnN1cmUgdGhleSBoYXZlIGEgc2VjdXJlIGFuZCBwcm9kdWN0aXZlIGhvbWUgb2ZmaWNlIGVudmlyb25tZW50LiBBbGwgY29tcGFueSBlcXVpcG1lbnQgdXNlZCByZW1vdGVseSBtdXN0IGFkaGVyZSB0byBzZWN1cml0eSBndWlkZWxpbmVzLiBGb3IgYXNzaXN0YW5jZSwgY29udGFjdCBJVCBzdXBwb3J0LiBSZWd1bGFyIHRlYW0gY2hlY2staW5zIGFyZSBtYW5kYXRvcnkuIEV4Y2VwdGlvbnMgdG8gdGhpcyBwb2xpY3kgcmVxdWlyZSBWUCBhcHByb3ZhbC5cIixcbiAgICB0YWdzOiBbJ2hyJywgJ3BvbGljeScsICdyZW1vdGUgd29yaycsICdlbXBsb3llZSBoYW5kYm9vayddLFxuICAgIGNyZWF0ZWRBdDogbmV3IERhdGUoJzIwMjMtMDUtMTBUMTE6MDA6MDBaJyksXG4gIH0sXG5dO1xuXG5hc3luYyBmdW5jdGlvbiBfZmV0Y2hNb2NrRG9jdW1lbnRzKFxuICBkb2N1bWVudElkcz86IHN0cmluZ1tdXG4pOiBQcm9taXNlPERvY3VtZW50Q29udGVudFtdPiB7XG4gIC8vIGNvbnNvbGUubG9nKGBbX2ZldGNoTW9ja0RvY3VtZW50c10gQXR0ZW1wdGluZyB0byBmZXRjaCBkb2N1bWVudHMuIFNwZWNpZmllZCBJRHM6ICR7ZG9jdW1lbnRJZHM/LmpvaW4oJywgJyl9YCk7XG4gIGlmIChkb2N1bWVudElkcyAmJiBkb2N1bWVudElkcy5sZW5ndGggPiAwKSB7XG4gICAgcmV0dXJuIE1PQ0tfRE9DVU1FTlRTLmZpbHRlcigoZG9jKSA9PiBkb2N1bWVudElkcy5pbmNsdWRlcyhkb2MuaWQpKTtcbiAgfVxuICByZXR1cm4gTU9DS19ET0NVTUVOVFM7XG59XG5cbmV4cG9ydCBpbnRlcmZhY2UgRG9jdW1lbnRDb250ZW50IHtcbiAgaWQ6IHN0cmluZztcbiAgdGl0bGU6IHN0cmluZztcbiAgdGV4dENvbnRlbnQ6IHN0cmluZztcbiAgdGFncz86IHN0cmluZ1tdO1xuICBjcmVhdGVkQXQ/OiBEYXRlO1xufVxuXG5leHBvcnQgaW50ZXJmYWNlIERvY3VtZW50QXNzaXN0YW50SW5wdXQge1xuICBxdWVyeTogc3RyaW5nO1xuICBkb2N1bWVudElkcz86IHN0cmluZ1tdO1xuICB1c2VySWQ6IHN0cmluZztcbiAgb3B0aW9ucz86IHtcbiAgICBzdW1tYXJpemU/OiBib29sZWFuO1xuICAgIHRhcmdldFN1bW1hcnlMZW5ndGg/OiAnc2hvcnQnIHwgJ21lZGl1bScgfCAnbG9uZyc7XG4gICAgbWF4UmVzdWx0cz86IG51bWJlcjtcbiAgICBzbmlwcGV0TGVuZ3RoPzogbnVtYmVyO1xuICB9O1xufVxuXG5leHBvcnQgaW50ZXJmYWNlIEFuc3dlck9iamVjdCB7XG4gIGRvY3VtZW50SWQ6IHN0cmluZztcbiAgZG9jdW1lbnRUaXRsZT86IHN0cmluZztcbiAgcmVsZXZhbnRTbmlwcGV0czogc3RyaW5nW107XG4gIHN1bW1hcnk/OiBzdHJpbmc7XG4gIHJlbGV2YW5jZVNjb3JlPzogbnVtYmVyO1xuICBwYWdlTnVtYmVycz86IG51bWJlcltdO1xufVxuXG5leHBvcnQgaW50ZXJmYWNlIERvY3VtZW50QXNzaXN0YW50UmVzdWx0IHtcbiAgb3JpZ2luYWxRdWVyeTogc3RyaW5nO1xuICBhbnN3ZXJzOiBBbnN3ZXJPYmplY3RbXTtcbiAgb3ZlcmFsbFN1bW1hcnk/OiBzdHJpbmc7XG4gIHNlYXJjaFBlcmZvcm1lZE9uPzogJ2FsbF9hY2Nlc3NpYmxlJyB8ICdzcGVjaWZpZWRfaWRzJztcbn1cblxuZXhwb3J0IGNsYXNzIENvbnRleHR1YWxEb2N1bWVudEFzc2lzdGFudFNraWxsIHtcbiAgcHJpdmF0ZSByZWFkb25seSBsbG1TZXJ2aWNlOiBMTE1TZXJ2aWNlSW50ZXJmYWNlO1xuXG4gIGNvbnN0cnVjdG9yKGxsbVNlcnZpY2U6IExMTVNlcnZpY2VJbnRlcmZhY2UpIHtcbiAgICB0aGlzLmxsbVNlcnZpY2UgPSBsbG1TZXJ2aWNlO1xuICAgIGNvbnNvbGUubG9nKFxuICAgICAgJ0NvbnRleHR1YWxEb2N1bWVudEFzc2lzdGFudFNraWxsIGluaXRpYWxpemVkIHdpdGggTExNU2VydmljZS4nXG4gICAgKTtcbiAgfVxuXG4gIHB1YmxpYyBhc3luYyBleGVjdXRlKFxuICAgIGlucHV0OiBEb2N1bWVudEFzc2lzdGFudElucHV0XG4gICk6IFByb21pc2U8RG9jdW1lbnRBc3Npc3RhbnRSZXN1bHQ+IHtcbiAgICBjb25zb2xlLmxvZyhcbiAgICAgIGBbQ29udGV4dHVhbERvY3VtZW50QXNzaXN0YW50U2tpbGxdIFF1ZXJ5OiBcIiR7aW5wdXQucXVlcnl9XCIsIFVzZXI6ICR7aW5wdXQudXNlcklkfSwgT3B0aW9uczogJHtKU09OLnN0cmluZ2lmeShpbnB1dC5vcHRpb25zKX1gXG4gICAgKTtcblxuICAgIGlmICghaW5wdXQucXVlcnkgfHwgIWlucHV0LnVzZXJJZCkge1xuICAgICAgdGhyb3cgbmV3IEVycm9yKCdRdWVyeSBhbmQgdXNlcklkIGFyZSByZXF1aXJlZC4nKTtcbiAgICB9XG4gICAgY29uc3Qgc25pcHBldExlbmd0aCA9IGlucHV0Lm9wdGlvbnM/LnNuaXBwZXRMZW5ndGggfHwgMTUwO1xuICAgIGNvbnN0IHRhcmdldFN1bW1hcnlMZW5ndGggPSBpbnB1dC5vcHRpb25zPy50YXJnZXRTdW1tYXJ5TGVuZ3RoIHx8ICdtZWRpdW0nO1xuICAgIGNvbnN0IG1heFJlc3VsdHMgPSBpbnB1dC5vcHRpb25zPy5tYXhSZXN1bHRzIHx8IDM7XG5cbiAgICBjb25zdCBjYW5kaWRhdGVEb2N1bWVudHMgPSBhd2FpdCBfZmV0Y2hNb2NrRG9jdW1lbnRzKGlucHV0LmRvY3VtZW50SWRzKTtcbiAgICBjb25zdCBzZWFyY2hTY29wZSA9XG4gICAgICBpbnB1dC5kb2N1bWVudElkcyAmJiBpbnB1dC5kb2N1bWVudElkcy5sZW5ndGggPiAwXG4gICAgICAgID8gJ3NwZWNpZmllZF9pZHMnXG4gICAgICAgIDogJ2FsbF9hY2Nlc3NpYmxlJztcbiAgICBjb25zb2xlLmxvZyhcbiAgICAgIGBbQ29udGV4dHVhbERvY3VtZW50QXNzaXN0YW50U2tpbGxdIEZldGNoZWQgJHtjYW5kaWRhdGVEb2N1bWVudHMubGVuZ3RofSBkb2NzIGZvciBzY29wZTogJHtzZWFyY2hTY29wZX0uYFxuICAgICk7XG5cbiAgICBjb25zdCBhbnN3ZXJzOiBBbnN3ZXJPYmplY3RbXSA9IFtdO1xuICAgIGxldCBvdmVyYWxsU3VtbWFyeTogc3RyaW5nIHwgdW5kZWZpbmVkID0gdW5kZWZpbmVkO1xuXG4gICAgZm9yIChjb25zdCBkb2Mgb2YgY2FuZGlkYXRlRG9jdW1lbnRzLnNsaWNlKDAsIG1heFJlc3VsdHMpKSB7XG4gICAgICAvLyBjb25zb2xlLmxvZyhgW0NvbnRleHR1YWxEb2N1bWVudEFzc2lzdGFudFNraWxsXSBQcm9jZXNzaW5nIGRvYzogJHtkb2MuaWR9IC0gJHtkb2MudGl0bGV9YCk7XG4gICAgICBjb25zdCBzbmlwcGV0RGF0YTogRG9jdW1lbnRTbmlwcGV0RGF0YSA9IHtcbiAgICAgICAgcXVlcnk6IGlucHV0LnF1ZXJ5LFxuICAgICAgICBkb2N1bWVudFRpdGxlOiBkb2MudGl0bGUsXG4gICAgICAgIGRvY3VtZW50VGV4dDogZG9jLnRleHRDb250ZW50LnN1YnN0cmluZygwLCAyMDAwKSxcbiAgICAgICAgc25pcHBldExlbmd0aDogc25pcHBldExlbmd0aCxcbiAgICAgIH07XG4gICAgICBjb25zdCBzdHJ1Y3R1cmVkU25pcHBldFByb21wdDogU3RydWN0dXJlZExMTVByb21wdCA9IHtcbiAgICAgICAgdGFzazogJ2V4dHJhY3RfZG9jdW1lbnRfc25pcHBldHMnLFxuICAgICAgICBkYXRhOiBzbmlwcGV0RGF0YSxcbiAgICAgIH07XG5cbiAgICAgIGxldCBleHRyYWN0ZWRTbmlwcGV0czogc3RyaW5nW10gPSBbXTtcbiAgICAgIHRyeSB7XG4gICAgICAgIGNvbnN0IGxsbVJlc3BvbnNlID0gYXdhaXQgdGhpcy5sbG1TZXJ2aWNlLmdlbmVyYXRlKFxuICAgICAgICAgIHN0cnVjdHVyZWRTbmlwcGV0UHJvbXB0LFxuICAgICAgICAgICdjaGVhcGVzdCdcbiAgICAgICAgKTtcbiAgICAgICAgaWYgKGxsbVJlc3BvbnNlLnN1Y2Nlc3MgJiYgbGxtUmVzcG9uc2UuY29udGVudCkge1xuICAgICAgICAgIGNvbnN0IHBhcnNlZFJlc3AgPSBKU09OLnBhcnNlKGxsbVJlc3BvbnNlLmNvbnRlbnQpO1xuICAgICAgICAgIGlmIChwYXJzZWRSZXNwICYmIEFycmF5LmlzQXJyYXkocGFyc2VkUmVzcC5zbmlwcGV0cykpIHtcbiAgICAgICAgICAgIGV4dHJhY3RlZFNuaXBwZXRzID0gcGFyc2VkUmVzcC5zbmlwcGV0cy5maWx0ZXIoXG4gICAgICAgICAgICAgIChzOiBhbnkpOiBzIGlzIHN0cmluZyA9PiB0eXBlb2YgcyA9PT0gJ3N0cmluZydcbiAgICAgICAgICAgICk7XG4gICAgICAgICAgfSBlbHNlIHtcbiAgICAgICAgICAgIGNvbnNvbGUud2FybihcbiAgICAgICAgICAgICAgYFtDb250ZXh0dWFsRG9jdW1lbnRBc3Npc3RhbnRTa2lsbF0gU25pcHBldHMgcmVzcCBpbnZhbGlkIGZvciAke2RvYy5pZH06ICR7bGxtUmVzcG9uc2UuY29udGVudH1gXG4gICAgICAgICAgICApO1xuICAgICAgICAgIH1cbiAgICAgICAgfSBlbHNlIHtcbiAgICAgICAgICBjb25zb2xlLmVycm9yKFxuICAgICAgICAgICAgYFtDb250ZXh0dWFsRG9jdW1lbnRBc3Npc3RhbnRTa2lsbF0gU25pcHBldCBMTE0gY2FsbCBmYWlsZWQgZm9yICR7ZG9jLmlkfTogJHtsbG1SZXNwb25zZS5lcnJvcn1gXG4gICAgICAgICAgKTtcbiAgICAgICAgfVxuICAgICAgfSBjYXRjaCAoZTogYW55KSB7XG4gICAgICAgIGNvbnNvbGUuZXJyb3IoXG4gICAgICAgICAgYFtDb250ZXh0dWFsRG9jdW1lbnRBc3Npc3RhbnRTa2lsbF0gRXJyb3IgcGFyc2luZyBzbmlwcGV0IExMTSByZXNwIGZvciAke2RvYy5pZH06ICR7ZS5tZXNzYWdlfWBcbiAgICAgICAgKTtcbiAgICAgIH1cblxuICAgICAgaWYgKGV4dHJhY3RlZFNuaXBwZXRzLmxlbmd0aCA+IDApIHtcbiAgICAgICAgY29uc3QgYW5zd2VyT2JqZWN0OiBBbnN3ZXJPYmplY3QgPSB7XG4gICAgICAgICAgZG9jdW1lbnRJZDogZG9jLmlkLFxuICAgICAgICAgIGRvY3VtZW50VGl0bGU6IGRvYy50aXRsZSxcbiAgICAgICAgICByZWxldmFudFNuaXBwZXRzOiBleHRyYWN0ZWRTbmlwcGV0cyxcbiAgICAgICAgICByZWxldmFuY2VTY29yZTogcGFyc2VGbG9hdChcbiAgICAgICAgICAgICgwLjYgKyBNYXRoLm1pbigwLjM1LCBleHRyYWN0ZWRTbmlwcGV0cy5sZW5ndGggKiAwLjA4KSkudG9GaXhlZCgyKVxuICAgICAgICAgICksXG4gICAgICAgIH07XG4gICAgICAgIGFuc3dlcnMucHVzaChhbnN3ZXJPYmplY3QpO1xuICAgICAgfVxuICAgIH1cblxuICAgIGlmIChpbnB1dC5vcHRpb25zPy5zdW1tYXJpemUpIHtcbiAgICAgIGZvciAoY29uc3QgYW5zd2VyIG9mIGFuc3dlcnMpIHtcbiAgICAgICAgaWYgKGFuc3dlci5yZWxldmFudFNuaXBwZXRzLmxlbmd0aCA+IDApIHtcbiAgICAgICAgICBjb25zdCBkb2NTdW1tYXJ5RGF0YTogRG9jdW1lbnRTdW1tYXJ5RGF0YSA9IHtcbiAgICAgICAgICAgIHF1ZXJ5OiBpbnB1dC5xdWVyeSxcbiAgICAgICAgICAgIGRvY3VtZW50VGl0bGU6IGFuc3dlci5kb2N1bWVudFRpdGxlLFxuICAgICAgICAgICAgc25pcHBldHM6IGFuc3dlci5yZWxldmFudFNuaXBwZXRzLFxuICAgICAgICAgICAgdGFyZ2V0TGVuZ3RoOiB0YXJnZXRTdW1tYXJ5TGVuZ3RoLFxuICAgICAgICAgIH07XG4gICAgICAgICAgY29uc3Qgc3RydWN0dXJlZERvY1N1bW1hcnlQcm9tcHQ6IFN0cnVjdHVyZWRMTE1Qcm9tcHQgPSB7XG4gICAgICAgICAgICB0YXNrOiAnc3VtbWFyaXplX2RvY3VtZW50X3NuaXBwZXRzJyxcbiAgICAgICAgICAgIGRhdGE6IGRvY1N1bW1hcnlEYXRhLFxuICAgICAgICAgIH07XG4gICAgICAgICAgdHJ5IHtcbiAgICAgICAgICAgIGNvbnN0IGxsbVJlc3BvbnNlID0gYXdhaXQgdGhpcy5sbG1TZXJ2aWNlLmdlbmVyYXRlKFxuICAgICAgICAgICAgICBzdHJ1Y3R1cmVkRG9jU3VtbWFyeVByb21wdCxcbiAgICAgICAgICAgICAgJ2NoZWFwZXN0J1xuICAgICAgICAgICAgKTtcbiAgICAgICAgICAgIGlmIChcbiAgICAgICAgICAgICAgbGxtUmVzcG9uc2Uuc3VjY2VzcyAmJlxuICAgICAgICAgICAgICBsbG1SZXNwb25zZS5jb250ZW50ICYmXG4gICAgICAgICAgICAgICFsbG1SZXNwb25zZS5jb250ZW50LnRvTG93ZXJDYXNlKCkuc3RhcnRzV2l0aCgnbGxtIGZhbGxiYWNrJylcbiAgICAgICAgICAgICkge1xuICAgICAgICAgICAgICBhbnN3ZXIuc3VtbWFyeSA9IGxsbVJlc3BvbnNlLmNvbnRlbnQ7XG4gICAgICAgICAgICB9IGVsc2Uge1xuICAgICAgICAgICAgICBhbnN3ZXIuc3VtbWFyeSA9ICdTdW1tYXJ5IGNvdWxkIG5vdCBiZSBnZW5lcmF0ZWQuJztcbiAgICAgICAgICAgICAgY29uc29sZS53YXJuKFxuICAgICAgICAgICAgICAgIGBbQ29udGV4dHVhbERvY3VtZW50QXNzaXN0YW50U2tpbGxdIERvYyBzdW1tYXJ5IExMTSBmYWlsZWQgZm9yICR7YW5zd2VyLmRvY3VtZW50SWR9OiAke2xsbVJlc3BvbnNlLmVycm9yIHx8IGxsbVJlc3BvbnNlLmNvbnRlbnR9YFxuICAgICAgICAgICAgICApO1xuICAgICAgICAgICAgfVxuICAgICAgICAgIH0gY2F0Y2ggKGU6IGFueSkge1xuICAgICAgICAgICAgY29uc29sZS5lcnJvcihcbiAgICAgICAgICAgICAgYFtDb250ZXh0dWFsRG9jdW1lbnRBc3Npc3RhbnRTa2lsbF0gRXJyb3IgaW4gZG9jIHN1bW1hcnkgTExNIGNhbGwgZm9yICR7YW5zd2VyLmRvY3VtZW50SWR9OiAke2UubWVzc2FnZX1gXG4gICAgICAgICAgICApO1xuICAgICAgICAgICAgYW5zd2VyLnN1bW1hcnkgPSAnRXJyb3IgZ2VuZXJhdGluZyBzdW1tYXJ5Lic7XG4gICAgICAgICAgfVxuICAgICAgICB9XG4gICAgICB9XG5cbiAgICAgIGlmIChhbnN3ZXJzLnNvbWUoKGEpID0+IGEuc3VtbWFyeSkpIHtcbiAgICAgICAgY29uc3QgaW5kaXZpZHVhbFN1bW1hcmllcyA9IGFuc3dlcnNcbiAgICAgICAgICAuZmlsdGVyKChhKSA9PiBhLnN1bW1hcnkpXG4gICAgICAgICAgLm1hcCgoYSkgPT4gKHsgdGl0bGU6IGEuZG9jdW1lbnRUaXRsZSwgc3VtbWFyeTogYS5zdW1tYXJ5IH0pKTtcbiAgICAgICAgaWYgKGluZGl2aWR1YWxTdW1tYXJpZXMubGVuZ3RoID4gMCkge1xuICAgICAgICAgIGNvbnN0IG92ZXJhbGxTdW1tYXJ5RGF0YTogT3ZlcmFsbFN1bW1hcnlEYXRhID0ge1xuICAgICAgICAgICAgcXVlcnk6IGlucHV0LnF1ZXJ5LFxuICAgICAgICAgICAgaW5kaXZpZHVhbFN1bW1hcmllcyxcbiAgICAgICAgICB9O1xuICAgICAgICAgIGNvbnN0IHN0cnVjdHVyZWRPdmVyYWxsU3VtbWFyeVByb21wdDogU3RydWN0dXJlZExMTVByb21wdCA9IHtcbiAgICAgICAgICAgIHRhc2s6ICdzdW1tYXJpemVfb3ZlcmFsbF9hbnN3ZXInLFxuICAgICAgICAgICAgZGF0YTogb3ZlcmFsbFN1bW1hcnlEYXRhLFxuICAgICAgICAgIH07XG4gICAgICAgICAgdHJ5IHtcbiAgICAgICAgICAgIGNvbnN0IGxsbVJlc3BvbnNlID0gYXdhaXQgdGhpcy5sbG1TZXJ2aWNlLmdlbmVyYXRlKFxuICAgICAgICAgICAgICBzdHJ1Y3R1cmVkT3ZlcmFsbFN1bW1hcnlQcm9tcHQsXG4gICAgICAgICAgICAgICdjaGVhcGVzdCdcbiAgICAgICAgICAgICk7XG4gICAgICAgICAgICBpZiAoXG4gICAgICAgICAgICAgIGxsbVJlc3BvbnNlLnN1Y2Nlc3MgJiZcbiAgICAgICAgICAgICAgbGxtUmVzcG9uc2UuY29udGVudCAmJlxuICAgICAgICAgICAgICAhbGxtUmVzcG9uc2UuY29udGVudC50b0xvd2VyQ2FzZSgpLnN0YXJ0c1dpdGgoJ2xsbSBmYWxsYmFjaycpXG4gICAgICAgICAgICApIHtcbiAgICAgICAgICAgICAgb3ZlcmFsbFN1bW1hcnkgPSBsbG1SZXNwb25zZS5jb250ZW50O1xuICAgICAgICAgICAgfSBlbHNlIHtcbiAgICAgICAgICAgICAgY29uc29sZS53YXJuKFxuICAgICAgICAgICAgICAgIGBbQ29udGV4dHVhbERvY3VtZW50QXNzaXN0YW50U2tpbGxdIE92ZXJhbGwgc3VtbWFyeSBMTE0gZmFpbGVkOiAke2xsbVJlc3BvbnNlLmVycm9yIHx8IGxsbVJlc3BvbnNlLmNvbnRlbnR9YFxuICAgICAgICAgICAgICApO1xuICAgICAgICAgICAgfVxuICAgICAgICAgIH0gY2F0Y2ggKGU6IGFueSkge1xuICAgICAgICAgICAgY29uc29sZS5lcnJvcihcbiAgICAgICAgICAgICAgYFtDb250ZXh0dWFsRG9jdW1lbnRBc3Npc3RhbnRTa2lsbF0gRXJyb3IgaW4gb3ZlcmFsbCBzdW1tYXJ5IExMTSBjYWxsOiAke2UubWVzc2FnZX1gXG4gICAgICAgICAgICApO1xuICAgICAgICAgIH1cbiAgICAgICAgfVxuICAgICAgfVxuICAgIH1cblxuICAgIGNvbnN0IHJlc3VsdDogRG9jdW1lbnRBc3Npc3RhbnRSZXN1bHQgPSB7XG4gICAgICBvcmlnaW5hbFF1ZXJ5OiBpbnB1dC5xdWVyeSxcbiAgICAgIGFuc3dlcnM6IGFuc3dlcnMsXG4gICAgICBzZWFyY2hQZXJmb3JtZWRPbjogc2VhcmNoU2NvcGUsXG4gICAgICBvdmVyYWxsU3VtbWFyeTogb3ZlcmFsbFN1bW1hcnksXG4gICAgfTtcblxuICAgIGNvbnNvbGUubG9nKFxuICAgICAgYFtDb250ZXh0dWFsRG9jdW1lbnRBc3Npc3RhbnRTa2lsbF0gUmVzdWx0IGZvciBcIiR7aW5wdXQucXVlcnl9XCI6ICR7YW5zd2Vycy5sZW5ndGh9IGFuc3dlcnMuYFxuICAgICk7XG4gICAgcmV0dXJuIHJlc3VsdDtcbiAgfVxufVxuXG4vLyBFeGFtcGxlIFVzYWdlOlxuLypcbmltcG9ydCB7IE1vY2tMTE1TZXJ2aWNlLCBPcGVuQUlHcm9xU2VydmljZV9TdHViIH0gZnJvbSAnLi4vbGliL2xsbVV0aWxzJztcblxuYXN5bmMgZnVuY3Rpb24gdGVzdENvbnRleHR1YWxEb2NTa2lsbCgpIHtcbiAgLy8gY29uc3QgbGxtU2VydmljZSA9IG5ldyBNb2NrTExNU2VydmljZSgpO1xuICBjb25zdCBsbG1TZXJ2aWNlID0gbmV3IE9wZW5BSUdyb3FTZXJ2aWNlX1N0dWIoXCJZT1VSX0dST1FfQVBJX0tFWVwiLCBcIllPVVJfR1JPUV9NT0RFTFwiKTsgLy8gUmVwbGFjZSB3aXRoIGFjdHVhbHNcbiAgY29uc3Qgc2tpbGwgPSBuZXcgQ29udGV4dHVhbERvY3VtZW50QXNzaXN0YW50U2tpbGwobGxtU2VydmljZSk7XG5cbiAgY29uc3QgdGVzdElucHV0MTogRG9jdW1lbnRBc3Npc3RhbnRJbnB1dCA9IHtcbiAgICB1c2VySWQ6IFwidXNlci10ZXN0LTEyM1wiLFxuICAgIHF1ZXJ5OiBcIldoYXQgd2VyZSB0aGUga2V5IGRlY2lzaW9ucyBmcm9tIHRoZSBRMyBidWRnZXQgbWVldGluZz9cIixcbiAgICBvcHRpb25zOiB7IHN1bW1hcml6ZTogdHJ1ZSwgdGFyZ2V0U3VtbWFyeUxlbmd0aDogJ3Nob3J0JywgbWF4UmVzdWx0czogMiB9XG4gIH07XG4gIGNvbnNvbGUubG9nKFwiXFxcXG4tLS0gVGVzdCBDYXNlIDE6IEJ1ZGdldCBRdWVyeSAtLS1cIik7XG4gIGNvbnN0IHJlc3VsdDEgPSBhd2FpdCBza2lsbC5leGVjdXRlKHRlc3RJbnB1dDEpO1xuICBjb25zb2xlLmxvZyhKU09OLnN0cmluZ2lmeShyZXN1bHQxLCBudWxsLCAyKSk7XG5cbiAgY29uc3QgdGVzdElucHV0MjogRG9jdW1lbnRBc3Npc3RhbnRJbnB1dCA9IHtcbiAgICB1c2VySWQ6IFwidXNlci10ZXN0LTQ1NlwiLFxuICAgIHF1ZXJ5OiBcIlRlbGwgbWUgYWJvdXQgUHJvamVjdCBQaG9lbml4IHNlY3VyaXR5XCIsXG4gICAgZG9jdW1lbnRJZHM6IFtcImRvY18wMDJcIl0sXG4gICAgb3B0aW9uczogeyBzdW1tYXJpemU6IHRydWUsIHNuaXBwZXRMZW5ndGg6IDEwMCB9XG4gIH07XG4gIGNvbnNvbGUubG9nKFwiXFxcXG4tLS0gVGVzdCBDYXNlIDI6IFBob2VuaXggU2VjdXJpdHkgLS0tXCIpO1xuICBjb25zdCByZXN1bHQyID0gYXdhaXQgc2tpbGwuZXhlY3V0ZSh0ZXN0SW5wdXQyKTtcbiAgY29uc29sZS5sb2coSlNPTi5zdHJpbmdpZnkocmVzdWx0MiwgbnVsbCwgMikpO1xufVxuLy8gdGVzdENvbnRleHR1YWxEb2NTa2lsbCgpO1xuKi9cbiJdfQ==