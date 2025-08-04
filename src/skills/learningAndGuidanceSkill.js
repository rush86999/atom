"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.LearningAndGuidanceSkill = void 0;
// Mock Knowledge Base Data
const MOCK_KB_ARTICLES = [
    {
        id: 'kb_001',
        title: 'How to Create Pivot Tables in SpreadsheetApp',
        contentType: 'how-to',
        application: 'SpreadsheetApp',
        keywords: ['pivot table', 'spreadsheet', 'data analysis', 'report'],
        content: 'Pivot tables are a powerful tool for summarizing and analyzing large datasets. This guide explains how to create them in SpreadsheetApp.',
        steps: [
            {
                title: 'Select Your Data',
                description: 'Click on any cell within the data range you want to analyze.',
            },
            {
                title: 'Insert Pivot Table',
                description: "Go to the 'Insert' menu and choose 'PivotTable'.",
            },
            {
                title: 'Configure Fields',
                description: 'In the PivotTable editor pane, drag fields into Rows, Columns, Values, and Filters areas.',
            },
            {
                title: 'Customize',
                description: 'Use options to sort, filter, and format your pivot table.',
            },
        ],
        difficulty: 'intermediate',
    },
    {
        id: 'kb_002',
        title: 'Tutorial: Email Merge with Attachments',
        contentType: 'tutorial',
        application: 'EmailClient',
        keywords: [
            'email merge',
            'mail merge',
            'attachments',
            'bulk email',
            'tutorial',
        ],
        content: 'This tutorial walks you through performing an email merge operation with personalized attachments using EmailClient and SpreadsheetApp for data.',
        steps: [
            {
                title: 'Prepare Data Source',
                description: 'Create a spreadsheet with recipient emails, names, and attachment file paths.',
            },
            {
                title: 'Open EmailClient Merge Tool',
                description: "In EmailClient, find the 'Mail Merge Wizard' under 'Tools'.",
            },
            {
                title: 'Connect Data Source',
                description: 'Link your spreadsheet to the wizard.',
            },
            {
                title: 'Compose Template',
                description: 'Write your email template using placeholders for personalized fields (e.g., {{FirstName}}).',
            },
            {
                title: 'Configure Attachments',
                description: "Specify the column in your spreadsheet that contains the path to each recipient's attachment.",
            },
            {
                title: 'Preview and Send',
                description: 'Review a few merged emails then start the send process.',
            },
        ],
        difficulty: 'intermediate',
    },
    {
        id: 'kb_003',
        title: 'FAQ: Common Login Issues',
        contentType: 'faq',
        application: 'General',
        keywords: ['login', 'password', 'access denied', 'troubleshooting', 'faq'],
        content: "Q: I forgot my password. How do I reset it?\nA: Click the 'Forgot Password' link on the login page and follow the instructions sent to your email.\n\nQ: Why am I seeing 'Access Denied' errors?\nA: This could be due to incorrect credentials, insufficient permissions, or network issues. Please verify your username/password and contact support if the problem persists.\n\nQ: What are the password complexity requirements?\nA: Passwords must be at least 12 characters, include uppercase, lowercase, numbers, and symbols.",
        difficulty: 'beginner',
    },
    {
        id: 'kb_004',
        title: 'Understanding Conditional Formatting',
        contentType: 'explanation',
        application: 'SpreadsheetApp',
        keywords: [
            'conditional formatting',
            'spreadsheet',
            'data visualization',
            'rules',
        ],
        content: 'Conditional formatting allows you to automatically apply formatting (like colors, icons, and data bars) to cells that meet certain criteria. This helps in visualizing data, highlighting important information, and identifying trends. You can set up rules based on cell values, formulas, or dates. Common uses include highlighting cells greater than a certain number, color-coding sales performance, or identifying duplicate values.',
        difficulty: 'beginner',
    },
    {
        id: 'kb_005',
        title: 'Workflow Guide: New Client Onboarding',
        contentType: 'workflow_guide',
        application: 'CRM_Platform',
        keywords: [
            'client onboarding',
            'crm',
            'workflow',
            'new customer',
            'process',
        ],
        content: 'This guide outlines the standard procedure for onboarding new clients in the CRM_Platform.',
        steps: [
            {
                title: 'Receive Lead',
                description: 'New lead is captured from web form or manual entry.',
            },
            {
                title: 'Initial Contact & Qualification',
                description: 'Sales rep makes initial contact within 24 hours to qualify the lead.',
            },
            {
                title: 'Needs Assessment Meeting',
                description: 'Schedule and conduct a meeting to understand client requirements.',
            },
            {
                title: 'Proposal Creation',
                description: 'Generate a tailored proposal in the CRM using approved templates.',
            },
            {
                title: 'Contract & Signature',
                description: 'Send contract for e-signature via integrated tool.',
            },
            {
                title: 'Project Kickoff',
                description: 'Once signed, schedule internal and client kickoff meetings.',
            },
            {
                title: 'CRM Record Update',
                description: "Update client status to 'Active' and populate all relevant fields.",
            },
        ],
        difficulty: 'intermediate',
    },
];
async function _fetchMockKnowledgeBaseArticles(query, contentTypeHint, applicationContext, maxResults = 3) {
    // console.log(`[_fetchMockKnowledgeBaseArticles] Query: "${query}", CT: ${contentTypeHint}, AppCtx: ${applicationContext}, Max: ${maxResults}`);
    const queryLower = query.toLowerCase();
    const queryKeywords = queryLower.split(/\s+/).filter((kw) => kw.length > 2);
    let filtered = MOCK_KB_ARTICLES;
    if (applicationContext) {
        filtered = filtered.filter((a) => !a.application ||
            a.application.toLowerCase() === applicationContext.toLowerCase() ||
            a.application === 'General');
    }
    if (contentTypeHint) {
        filtered = filtered.filter((a) => a.contentType === contentTypeHint);
    }
    const scored = filtered
        .map((article) => {
        let score = 0;
        const titleLower = article.title.toLowerCase();
        const contentSnip = article.content.substring(0, 300).toLowerCase();
        queryKeywords.forEach((kw) => {
            if (titleLower.includes(kw))
                score += 3;
            if (article.keywords?.some((k) => k.toLowerCase().includes(kw)))
                score += 2;
            if (contentSnip.includes(kw))
                score += 1;
        });
        if (queryLower.includes(article.contentType))
            score += 2;
        return { article, score };
    })
        .filter((item) => item.score > 0)
        .sort((a, b) => b.score - a.score);
    return scored.slice(0, maxResults).map((item) => item.article);
}
class LearningAndGuidanceSkill {
    llmService;
    constructor(llmService) {
        this.llmService = llmService;
        console.log('LearningAndGuidanceSkill initialized with LLMService.');
    }
    async execute(input) {
        console.log(`[LearningAndGuidanceSkill] Query: "${input.query}", User: ${input.userId}`);
        if (!input.query || !input.userId) {
            throw new Error('Query and userId are required.');
        }
        const maxResults = input.options?.maxResults || 3;
        let effectiveGuidanceType = input.guidanceTypeHint || 'answer_question';
        if (!input.guidanceTypeHint) {
            const classData = { query: input.query };
            const classPrompt = {
                task: 'classify_guidance_query',
                data: classData,
            };
            try {
                const llmResp = await this.llmService.generate(classPrompt, 'cheapest');
                if (llmResp.success && llmResp.content) {
                    const parsed = JSON.parse(llmResp.content);
                    const validTypes = [
                        'answer_question',
                        'find_tutorial',
                        'guide_workflow',
                        'general_explanation',
                    ];
                    if (parsed &&
                        parsed.guidanceType &&
                        validTypes.includes(parsed.guidanceType)) {
                        effectiveGuidanceType = parsed.guidanceType;
                    }
                    else {
                        console.warn(`[LearningAndGuidanceSkill] LLM invalid guidanceType: ${llmResp.content}`);
                    }
                }
                else {
                    console.error(`[LearningAndGuidanceSkill] LLM query classification failed: ${llmResp.error}`);
                }
            }
            catch (e) {
                console.error(`[LearningAndGuidanceSkill] Error in LLM query classification: ${e.message}`);
            }
        }
        console.log(`[LearningAndGuidanceSkill] Effective guidance type: ${effectiveGuidanceType}`);
        const relevantArticles = await _fetchMockKnowledgeBaseArticles(input.query, input.options?.preferContentType, input.applicationContext, maxResults);
        const guidanceProvided = [];
        for (const article of relevantArticles) {
            let guidance = {
                title: article.title,
                sourceArticleId: article.id,
                relevanceScore: 0.6,
            };
            try {
                let structuredArticlePrompt;
                let task;
                switch (effectiveGuidanceType) {
                    case 'answer_question':
                        task = 'answer_from_text';
                        const answerData = {
                            query: input.query,
                            textContent: article.content.substring(0, 1500),
                            articleTitle: article.title,
                        };
                        structuredArticlePrompt = { task, data: answerData };
                        break;
                    case 'general_explanation':
                        task = 'summarize_for_explanation';
                        const explData = {
                            query: input.query,
                            textContent: article.content.substring(0, 1500),
                            articleTitle: article.title,
                        };
                        structuredArticlePrompt = { task, data: explData };
                        break;
                    case 'find_tutorial':
                    case 'guide_workflow':
                        if (article.steps && article.steps.length > 0) {
                            guidance.steps = article.steps;
                            guidance.contentSnippet = `Found relevant steps in "${article.title}".`;
                            guidance.relevanceScore = 0.85;
                            guidanceProvided.push(guidance); // Push early if predefined steps are used
                            continue; // Skip LLM call for steps
                        }
                        else {
                            task = 'extract_steps_from_text';
                            const stepsData = {
                                query: input.query,
                                textContent: article.content.substring(0, 2000),
                                articleTitle: article.title,
                            };
                            structuredArticlePrompt = { task, data: stepsData };
                        }
                        break;
                    default:
                        console.warn(`[LearningAndGuidanceSkill] Unexpected guidance type: ${effectiveGuidanceType}. Defaulting to snippet.`);
                        guidance.contentSnippet = `Article: ${article.title}. Excerpt: ${article.content.substring(0, 200)}...`;
                        guidanceProvided.push(guidance);
                        continue; // Skip LLM call
                }
                const llmResponse = await this.llmService.generate(structuredArticlePrompt, 'cheapest');
                if (llmResponse.success && llmResponse.content) {
                    if (effectiveGuidanceType === 'answer_question' ||
                        effectiveGuidanceType === 'general_explanation') {
                        if (!llmResponse.content.toLowerCase().startsWith('llm fallback') &&
                            !llmResponse.content
                                .toLowerCase()
                                .includes('not appear to contain')) {
                            guidance.contentSnippet = llmResponse.content;
                            guidance.relevanceScore = 0.8;
                        }
                        else {
                            guidance.contentSnippet = `Article "${article.title}" found, but specific info for "${input.query}" not extracted. LLM said: ${llmResponse.content}`;
                        }
                    }
                    else if (effectiveGuidanceType === 'find_tutorial' ||
                        effectiveGuidanceType === 'guide_workflow') {
                        // Only if LLM was called for steps
                        try {
                            const parsedSteps = JSON.parse(llmResponse.content);
                            if (parsedSteps &&
                                Array.isArray(parsedSteps.steps) &&
                                parsedSteps.steps.length > 0) {
                                guidance.steps = parsedSteps.steps;
                                guidance.contentSnippet = 'Extracted the following key steps:';
                                guidance.relevanceScore = 0.8;
                            }
                            else {
                                guidance.contentSnippet = `"${article.title}" relevant, but specific steps for "${input.query}" not extracted.`;
                            }
                        }
                        catch (e) {
                            console.error(`[LearningAndGuidanceSkill] Error parsing steps JSON from LLM for "${article.title}":`, e);
                            guidance.contentSnippet = `Could not parse steps for "${article.title}". LLM response: ${llmResponse.content.substring(0, 100)}...`;
                        }
                    }
                }
                else {
                    console.error(`[LearningAndGuidanceSkill] LLM processing failed for article ${article.id}: ${llmResponse.error}`);
                    guidance.contentSnippet = `Error processing article "${article.title}" for your query.`;
                }
            }
            catch (e) {
                console.error(`[LearningAndGuidanceSkill] Outer error processing article ${article.id}: ${e.message}`);
                guidance.contentSnippet = `System error processing article "${article.title}".`;
            }
            if (!guidance.contentSnippet &&
                (!guidance.steps || guidance.steps.length === 0)) {
                guidance.contentSnippet = `Article "${article.title}" may be relevant. Excerpt: ${article.content.substring(0, 150)}...`;
            }
            guidanceProvided.push(guidance);
        }
        let followUpSuggestions = undefined;
        if (guidanceProvided.length > 0 && guidanceProvided[0]) {
            const followupData = {
                query: input.query,
                articleTitle: guidanceProvided[0].title,
            };
            const followupPrompt = {
                task: 'generate_followup_suggestions',
                data: followupData,
            };
            try {
                const followupResp = await this.llmService.generate(followupPrompt, 'cheapest');
                if (followupResp.success && followupResp.content) {
                    const parsed = JSON.parse(followupResp.content);
                    if (parsed &&
                        Array.isArray(parsed.suggestions) &&
                        parsed.suggestions.length > 0) {
                        followUpSuggestions = parsed.suggestions.filter((s) => typeof s === 'string');
                    }
                }
                else {
                    console.warn(`[LearningAndGuidanceSkill] LLM follow-up suggestions failed: ${followupResp.error}`);
                }
            }
            catch (e) {
                console.error(`[LearningAndGuidanceSkill] Error processing LLM follow-up suggestions: ${e.message}`);
            }
        }
        const finalResult = {
            originalQuery: input.query,
            guidanceProvided: guidanceProvided,
            followUpSuggestions: followUpSuggestions,
            searchPerformedOn: `${relevantArticles.length} articles from ${input.applicationContext || 'General'} KB matching "${input.query.substring(0, 50)}..."`,
        };
        console.log(`[LearningAndGuidanceSkill] Returning guidance for query: "${input.query}"`);
        return finalResult;
    }
}
exports.LearningAndGuidanceSkill = LearningAndGuidanceSkill;
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
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoibGVhcm5pbmdBbmRHdWlkYW5jZVNraWxsLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsibGVhcm5pbmdBbmRHdWlkYW5jZVNraWxsLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiI7OztBQVdBLDJCQUEyQjtBQUMzQixNQUFNLGdCQUFnQixHQUEyQjtJQUMvQztRQUNFLEVBQUUsRUFBRSxRQUFRO1FBQ1osS0FBSyxFQUFFLDhDQUE4QztRQUNyRCxXQUFXLEVBQUUsUUFBUTtRQUNyQixXQUFXLEVBQUUsZ0JBQWdCO1FBQzdCLFFBQVEsRUFBRSxDQUFDLGFBQWEsRUFBRSxhQUFhLEVBQUUsZUFBZSxFQUFFLFFBQVEsQ0FBQztRQUNuRSxPQUFPLEVBQ0wsMElBQTBJO1FBQzVJLEtBQUssRUFBRTtZQUNMO2dCQUNFLEtBQUssRUFBRSxrQkFBa0I7Z0JBQ3pCLFdBQVcsRUFDVCw4REFBOEQ7YUFDakU7WUFDRDtnQkFDRSxLQUFLLEVBQUUsb0JBQW9CO2dCQUMzQixXQUFXLEVBQUUsa0RBQWtEO2FBQ2hFO1lBQ0Q7Z0JBQ0UsS0FBSyxFQUFFLGtCQUFrQjtnQkFDekIsV0FBVyxFQUNULDJGQUEyRjthQUM5RjtZQUNEO2dCQUNFLEtBQUssRUFBRSxXQUFXO2dCQUNsQixXQUFXLEVBQ1QsMkRBQTJEO2FBQzlEO1NBQ0Y7UUFDRCxVQUFVLEVBQUUsY0FBYztLQUMzQjtJQUNEO1FBQ0UsRUFBRSxFQUFFLFFBQVE7UUFDWixLQUFLLEVBQUUsd0NBQXdDO1FBQy9DLFdBQVcsRUFBRSxVQUFVO1FBQ3ZCLFdBQVcsRUFBRSxhQUFhO1FBQzFCLFFBQVEsRUFBRTtZQUNSLGFBQWE7WUFDYixZQUFZO1lBQ1osYUFBYTtZQUNiLFlBQVk7WUFDWixVQUFVO1NBQ1g7UUFDRCxPQUFPLEVBQ0wsa0pBQWtKO1FBQ3BKLEtBQUssRUFBRTtZQUNMO2dCQUNFLEtBQUssRUFBRSxxQkFBcUI7Z0JBQzVCLFdBQVcsRUFDVCwrRUFBK0U7YUFDbEY7WUFDRDtnQkFDRSxLQUFLLEVBQUUs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LENBQUMsV0FBVyxDQUFDLE1BQU0sR0FBRyxDQUFDLEVBQzdCLENBQUM7d0JBQ0QsbUJBQW1CLEdBQUcsTUFBTSxDQUFDLFdBQVcsQ0FBQyxNQUFNLENBQzdDLENBQUMsQ0FBTSxFQUFlLEVBQUUsQ0FBQyxPQUFPLENBQUMsS0FBSyxRQUFRLENBQy9DLENBQUM7b0JBQ0osQ0FBQztnQkFDSCxDQUFDO3FCQUFNLENBQUM7b0JBQ04sT0FBTyxDQUFDLElBQUksQ0FDVixnRUFBZ0UsWUFBWSxDQUFDLEtBQUssRUFBRSxDQUNyRixDQUFDO2dCQUNKLENBQUM7WUFDSCxDQUFDO1lBQUMsT0FBTyxDQUFNLEVBQUUsQ0FBQztnQkFDaEIsT0FBTyxDQUFDLEtBQUssQ0FDWCwwRUFBMEUsQ0FBQyxDQUFDLE9BQU8sRUFBRSxDQUN0RixDQUFDO1lBQ0osQ0FBQztRQUNILENBQUM7UUFFRCxNQUFNLFdBQVcsR0FBOEI7WUFDN0MsYUFBYSxFQUFFLEtBQUssQ0FBQyxLQUFLO1lBQzFCLGdCQUFnQixFQUFFLGdCQUFnQjtZQUNsQyxtQkFBbUIsRUFBRSxtQkFBbUI7WUFDeEMsaUJBQWlCLEVBQUUsR0FBRyxnQkFBZ0IsQ0FBQyxNQUFNLGtCQUFrQixLQUFLLENBQUMsa0JBQWtCLElBQUksU0FBUyxpQkFBaUIsS0FBSyxDQUFDLEtBQUssQ0FBQyxTQUFTLENBQUMsQ0FBQyxFQUFFLEVBQUUsQ0FBQyxNQUFNO1NBQ3hKLENBQUM7UUFFRixPQUFPLENBQUMsR0FBRyxDQUNULDZEQUE2RCxLQUFLLENBQUMsS0FBSyxHQUFHLENBQzVFLENBQUM7UUFDRixPQUFPLFdBQVcsQ0FBQztJQUNyQixDQUFDO0NBQ0Y7QUF0UEQsNERBc1BDO0FBRUQsZ0JBQWdCO0FBQ2hCOzs7Ozs7Ozs7Ozs7Ozs7O0VBZ0JFIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IHtcbiAgTExNU2VydmljZUludGVyZmFjZSxcbiAgU3RydWN0dXJlZExMTVByb21wdCxcbiAgR3VpZGFuY2VRdWVyeUNsYXNzaWZpY2F0aW9uRGF0YSxcbiAgQW5zd2VyRnJvbVRleHREYXRhLFxuICBTdGVwc0Zyb21UZXh0RGF0YSxcbiAgRXhwbGFuYXRpb25EYXRhLFxuICBGb2xsb3d1cFN1Z2dlc3Rpb25EYXRhLFxuICBMTE1UYXNrVHlwZSxcbn0gZnJvbSAnLi4vbGliL2xsbVV0aWxzJztcblxuLy8gTW9jayBLbm93bGVkZ2UgQmFzZSBEYXRhXG5jb25zdCBNT0NLX0tCX0FSVElDTEVTOiBLbm93bGVkZ2VCYXNlQXJ0aWNsZVtdID0gW1xuICB7XG4gICAgaWQ6ICdrYl8wMDEnLFxuICAgIHRpdGxlOiAnSG93IHRvIENyZWF0ZSBQaXZvdCBUYWJsZXMgaW4gU3ByZWFkc2hlZXRBcHAnLFxuICAgIGNvbnRlbnRUeXBlOiAnaG93LXRvJyxcbiAgICBhcHBsaWNhdGlvbjogJ1NwcmVhZHNoZWV0QXBwJyxcbiAgICBrZXl3b3JkczogWydwaXZvdCB0YWJsZScsICdzcHJlYWRzaGVldCcsICdkYXRhIGFuYWx5c2lzJywgJ3JlcG9ydCddLFxuICAgIGNvbnRlbnQ6XG4gICAgICAnUGl2b3QgdGFibGVzIGFyZSBhIHBvd2VyZnVsIHRvb2wgZm9yIHN1bW1hcml6aW5nIGFuZCBhbmFseXppbmcgbGFyZ2UgZGF0YXNldHMuIFRoaXMgZ3VpZGUgZXhwbGFpbnMgaG93IHRvIGNyZWF0ZSB0aGVtIGluIFNwcmVhZHNoZWV0QXBwLicsXG4gICAgc3RlcHM6IFtcbiAgICAgIHtcbiAgICAgICAgdGl0bGU6ICdTZWxlY3QgWW91ciBEYXRhJyxcbiAgICAgICAgZGVzY3JpcHRpb246XG4gICAgICAgICAgJ0NsaWNrIG9uIGFueSBjZWxsIHdpdGhpbiB0aGUgZGF0YSByYW5nZSB5b3Ugd2FudCB0byBhbmFseXplLicsXG4gICAgICB9LFxuICAgICAge1xuICAgICAgICB0aXRsZTogJ0luc2VydCBQaXZvdCBUYWJsZScsXG4gICAgICAgIGRlc2NyaXB0aW9uOiBcIkdvIHRvIHRoZSAnSW5zZXJ0JyBtZW51IGFuZCBjaG9vc2UgJ1Bpdm90VGFibGUnLlwiLFxuICAgICAgfSxcbiAgICAgIHtcbiAgICAgICAgdGl0bGU6ICdDb25maWd1cmUgRmllbGRzJyxcbiAgICAgICAgZGVzY3JpcHRpb246XG4gICAgICAgICAgJ0luIHRoZSBQaXZvdFRhYmxlIGVkaXRvciBwYW5lLCBkcmFnIGZpZWxkcyBpbnRvIFJvd3MsIENvbHVtbnMsIFZhbHVlcywgYW5kIEZpbHRlcnMgYXJlYXMuJyxcbiAgICAgIH0sXG4gICAgICB7XG4gICAgICAgIHRpdGxlOiAnQ3VzdG9taXplJyxcbiAgICAgICAgZGVzY3JpcHRpb246XG4gICAgICAgICAgJ1VzZSBvcHRpb25zIHRvIHNvcnQsIGZpbHRlciwgYW5kIGZvcm1hdCB5b3VyIHBpdm90IHRhYmxlLicsXG4gICAgICB9LFxuICAgIF0sXG4gICAgZGlmZmljdWx0eTogJ2ludGVybWVkaWF0ZScsXG4gIH0sXG4gIHtcbiAgICBpZDogJ2tiXzAwMicsXG4gICAgdGl0bGU6ICdUdXRvcmlhbDogRW1haWwgTWVyZ2Ugd2l0aCBBdHRhY2htZW50cycsXG4gICAgY29udGVudFR5cGU6ICd0dXRvcmlhbCcsXG4gICAgYXBwbGljYXRpb246ICdFbWFpbENsaWVudCcsXG4gICAga2V5d29yZHM6IFtcbiAgICAgICdlbWFpbCBtZXJnZScsXG4gICAgICAnbWFpbCBtZXJnZScsXG4gICAgICAnYXR0YWNobWVudHMnLFxuICAgICAgJ2J1bGsgZW1haWwnLFxuICAgICAgJ3R1dG9yaWFsJyxcbiAgICBdLFxuICAgIGNvbnRlbnQ6XG4gICAgICAnVGhpcyB0dXRvcmlhbCB3YWxrcyB5b3UgdGhyb3VnaCBwZXJmb3JtaW5nIGFuIGVtYWlsIG1lcmdlIG9wZXJhdGlvbiB3aXRoIHBlcnNvbmFsaXplZCBhdHRhY2htZW50cyB1c2luZyBFbWFpbENsaWVudCBhbmQgU3ByZWFkc2hlZXRBcHAgZm9yIGRhdGEuJyxcbiAgICBzdGVwczogW1xuICAgICAge1xuICAgICAgICB0aXRsZTogJ1ByZXBhcmUgRGF0YSBTb3VyY2UnLFxuICAgICAgICBkZXNjcmlwdGlvbjpcbiAgICAgICAgICAnQ3JlYXRlIGEgc3ByZWFkc2hlZXQgd2l0aCByZWNpcGllbnQgZW1haWxzLCBuYW1lcywgYW5kIGF0dGFjaG1lbnQgZmlsZSBwYXRocy4nLFxuICAgICAgfSxcbiAgICAgIHtcbiAgICAgICAgdGl0bGU6ICdPcGVuIEVtYWlsQ2xpZW50IE1lcmdlIFRvb2wnLFxuICAgICAgICBkZXNjcmlwdGlvbjpcbiAgICAgICAgICBcIkluIEVtYWlsQ2xpZW50LCBmaW5kIHRoZSAnTWFpbCBNZXJnZSBXaXphcmQnIHVuZGVyICdUb29scycuXCIsXG4gICAgICB9LFxuICAgICAge1xuICAgICAgICB0aXRsZTogJ0Nvbm5lY3QgRGF0YSBTb3VyY2UnLFxuICAgICAgICBkZXNjcmlwdGlvbjogJ0xpbmsgeW91ciBzcHJlYWRzaGVldCB0byB0aGUgd2l6YXJkLicsXG4gICAgICB9LFxuICAgICAge1xuICAgICAgICB0aXRsZTogJ0NvbXBvc2UgVGVtcGxhdGUnLFxuICAgICAgICBkZXNjcmlwdGlvbjpcbiAgICAgICAgICAnV3JpdGUgeW91ciBlbWFpbCB0ZW1wbGF0ZSB1c2luZyBwbGFjZWhvbGRlcnMgZm9yIHBlcnNvbmFsaXplZCBmaWVsZHMgKGUuZy4sIHt7Rmlyc3ROYW1lfX0pLicsXG4gICAgICB9LFxuICAgICAge1xuICAgICAgICB0aXRsZTogJ0NvbmZpZ3VyZSBBdHRhY2htZW50cycsXG4gICAgICAgIGRlc2NyaXB0aW9uOlxuICAgICAgICAgIFwiU3BlY2lmeSB0aGUgY29sdW1uIGluIHlvdXIgc3ByZWFkc2hlZXQgdGhhdCBjb250YWlucyB0aGUgcGF0aCB0byBlYWNoIHJlY2lwaWVudCdzIGF0dGFjaG1lbnQuXCIsXG4gICAgICB9LFxuICAgICAge1xuICAgICAgICB0aXRsZTogJ1ByZXZpZXcgYW5kIFNlbmQnLFxuICAgICAgICBkZXNjcmlwdGlvbjogJ1JldmlldyBhIGZldyBtZXJnZWQgZW1haWxzIHRoZW4gc3RhcnQgdGhlIHNlbmQgcHJvY2Vzcy4nLFxuICAgICAgfSxcbiAgICBdLFxuICAgIGRpZmZpY3VsdHk6ICdpbnRlcm1lZGlhdGUnLFxuICB9LFxuICB7XG4gICAgaWQ6ICdrYl8wMDMnLFxuICAgIHRpdGxlOiAnRkFROiBDb21tb24gTG9naW4gSXNzdWVzJyxcbiAgICBjb250ZW50VHlwZTogJ2ZhcScsXG4gICAgYXBwbGljYXRpb246ICdHZW5lcmFsJyxcbiAgICBrZXl3b3JkczogWydsb2dpbicsICdwYXNzd29yZCcsICdhY2Nlc3MgZGVuaWVkJywgJ3Ryb3VibGVzaG9vdGluZycsICdmYXEnXSxcbiAgICBjb250ZW50OlxuICAgICAgXCJROiBJIGZvcmdvdCBteSBwYXNzd29yZC4gSG93IGRvIEkgcmVzZXQgaXQ/XFxuQTogQ2xpY2sgdGhlICdGb3Jnb3QgUGFzc3dvcmQnIGxpbmsgb24gdGhlIGxvZ2luIHBhZ2UgYW5kIGZvbGxvdyB0aGUgaW5zdHJ1Y3Rpb25zIHNlbnQgdG8geW91ciBlbWFpbC5cXG5cXG5ROiBXaHkgYW0gSSBzZWVpbmcgJ0FjY2VzcyBEZW5pZWQnIGVycm9ycz9cXG5BOiBUaGlzIGNvdWxkIGJlIGR1ZSB0byBpbmNvcnJlY3QgY3JlZGVudGlhbHMsIGluc3VmZmljaWVudCBwZXJtaXNzaW9ucywgb3IgbmV0d29yayBpc3N1ZXMuIFBsZWFzZSB2ZXJpZnkgeW91ciB1c2VybmFtZS9wYXNzd29yZCBhbmQgY29udGFjdCBzdXBwb3J0IGlmIHRoZSBwcm9ibGVtIHBlcnNpc3RzLlxcblxcblE6IFdoYXQgYXJlIHRoZSBwYXNzd29yZCBjb21wbGV4aXR5IHJlcXVpcmVtZW50cz9cXG5BOiBQYXNzd29yZHMgbXVzdCBiZSBhdCBsZWFzdCAxMiBjaGFyYWN0ZXJzLCBpbmNsdWRlIHVwcGVyY2FzZSwgbG93ZXJjYXNlLCBudW1iZXJzLCBhbmQgc3ltYm9scy5cIixcbiAgICBkaWZmaWN1bHR5OiAnYmVnaW5uZXInLFxuICB9LFxuICB7XG4gICAgaWQ6ICdrYl8wMDQnLFxuICAgIHRpdGxlOiAnVW5kZXJzdGFuZGluZyBDb25kaXRpb25hbCBGb3JtYXR0aW5nJyxcbiAgICBjb250ZW50VHlwZTogJ2V4cGxhbmF0aW9uJyxcbiAgICBhcHBsaWNhdGlvbjogJ1NwcmVhZHNoZWV0QXBwJyxcbiAgICBrZXl3b3JkczogW1xuICAgICAgJ2NvbmRpdGlvbmFsIGZvcm1hdHRpbmcnLFxuICAgICAgJ3NwcmVhZHNoZWV0JyxcbiAgICAgICdkYXRhIHZpc3VhbGl6YXRpb24nLFxuICAgICAgJ3J1bGVzJyxcbiAgICBdLFxuICAgIGNvbnRlbnQ6XG4gICAgICAnQ29uZGl0aW9uYWwgZm9ybWF0dGluZyBhbGxvd3MgeW91IHRvIGF1dG9tYXRpY2FsbHkgYXBwbHkgZm9ybWF0dGluZyAobGlrZSBjb2xvcnMsIGljb25zLCBhbmQgZGF0YSBiYXJzKSB0byBjZWxscyB0aGF0IG1lZXQgY2VydGFpbiBjcml0ZXJpYS4gVGhpcyBoZWxwcyBpbiB2aXN1YWxpemluZyBkYXRhLCBoaWdobGlnaHRpbmcgaW1wb3J0YW50IGluZm9ybWF0aW9uLCBhbmQgaWRlbnRpZnlpbmcgdHJlbmRzLiBZb3UgY2FuIHNldCB1cCBydWxlcyBiYXNlZCBvbiBjZWxsIHZhbHVlcywgZm9ybXVsYXMsIG9yIGRhdGVzLiBDb21tb24gdXNlcyBpbmNsdWRlIGhpZ2hsaWdodGluZyBjZWxscyBncmVhdGVyIHRoYW4gYSBjZXJ0YWluIG51bWJlciwgY29sb3ItY29kaW5nIHNhbGVzIHBlcmZvcm1hbmNlLCBvciBpZGVudGlmeWluZyBkdXBsaWNhdGUgdmFsdWVzLicsXG4gICAgZGlmZmljdWx0eTogJ2JlZ2lubmVyJyxcbiAgfSxcbiAge1xuICAgIGlkOiAna2JfMDA1JyxcbiAgICB0aXRsZTogJ1dvcmtmbG93IEd1aWRlOiBOZXcgQ2xpZW50IE9uYm9hcmRpbmcnLFxuICAgIGNvbnRlbnRUeXBlOiAnd29ya2Zsb3dfZ3VpZGUnLFxuICAgIGFwcGxpY2F0aW9uOiAnQ1JNX1BsYXRmb3JtJyxcbiAgICBrZXl3b3JkczogW1xuICAgICAgJ2NsaWVudCBvbmJvYXJkaW5nJyxcbiAgICAgICdjcm0nLFxuICAgICAgJ3dvcmtmbG93JyxcbiAgICAgICduZXcgY3VzdG9tZXInLFxuICAgICAgJ3Byb2Nlc3MnLFxuICAgIF0sXG4gICAgY29udGVudDpcbiAgICAgICdUaGlzIGd1aWRlIG91dGxpbmVzIHRoZSBzdGFuZGFyZCBwcm9jZWR1cmUgZm9yIG9uYm9hcmRpbmcgbmV3IGNsaWVudHMgaW4gdGhlIENSTV9QbGF0Zm9ybS4nLFxuICAgIHN0ZXBzOiBbXG4gICAgICB7XG4gICAgICAgIHRpdGxlOiAnUmVjZWl2ZSBMZWFkJyxcbiAgICAgICAgZGVzY3JpcHRpb246ICdOZXcgbGVhZCBpcyBjYXB0dXJlZCBmcm9tIHdlYiBmb3JtIG9yIG1hbnVhbCBlbnRyeS4nLFxuICAgICAgfSxcbiAgICAgIHtcbiAgICAgICAgdGl0bGU6ICdJbml0aWFsIENvbnRhY3QgJiBRdWFsaWZpY2F0aW9uJyxcbiAgICAgICAgZGVzY3JpcHRpb246XG4gICAgICAgICAgJ1NhbGVzIHJlcCBtYWtlcyBpbml0aWFsIGNvbnRhY3Qgd2l0aGluIDI0IGhvdXJzIHRvIHF1YWxpZnkgdGhlIGxlYWQuJyxcbiAgICAgIH0sXG4gICAgICB7XG4gICAgICAgIHRpdGxlOiAnTmVlZHMgQXNzZXNzbWVudCBNZWV0aW5nJyxcbiAgICAgICAgZGVzY3JpcHRpb246XG4gICAgICAgICAgJ1NjaGVkdWxlIGFuZCBjb25kdWN0IGEgbWVldGluZyB0byB1bmRlcnN0YW5kIGNsaWVudCByZXF1aXJlbWVudHMuJyxcbiAgICAgIH0sXG4gICAgICB7XG4gICAgICAgIHRpdGxlOiAnUHJvcG9zYWwgQ3JlYXRpb24nLFxuICAgICAgICBkZXNjcmlwdGlvbjpcbiAgICAgICAgICAnR2VuZXJhdGUgYSB0YWlsb3JlZCBwcm9wb3NhbCBpbiB0aGUgQ1JNIHVzaW5nIGFwcHJvdmVkIHRlbXBsYXRlcy4nLFxuICAgICAgfSxcbiAgICAgIHtcbiAgICAgICAgdGl0bGU6ICdDb250cmFjdCAmIFNpZ25hdHVyZScsXG4gICAgICAgIGRlc2NyaXB0aW9uOiAnU2VuZCBjb250cmFjdCBmb3IgZS1zaWduYXR1cmUgdmlhIGludGVncmF0ZWQgdG9vbC4nLFxuICAgICAgfSxcbiAgICAgIHtcbiAgICAgICAgdGl0bGU6ICdQcm9qZWN0IEtpY2tvZmYnLFxuICAgICAgICBkZXNjcmlwdGlvbjpcbiAgICAgICAgICAnT25jZSBzaWduZWQsIHNjaGVkdWxlIGludGVybmFsIGFuZCBjbGllbnQga2lja29mZiBtZWV0aW5ncy4nLFxuICAgICAgfSxcbiAgICAgIHtcbiAgICAgICAgdGl0bGU6ICdDUk0gUmVjb3JkIFVwZGF0ZScsXG4gICAgICAgIGRlc2NyaXB0aW9uOlxuICAgICAgICAgIFwiVXBkYXRlIGNsaWVudCBzdGF0dXMgdG8gJ0FjdGl2ZScgYW5kIHBvcHVsYXRlIGFsbCByZWxldmFudCBmaWVsZHMuXCIsXG4gICAgICB9LFxuICAgIF0sXG4gICAgZGlmZmljdWx0eTogJ2ludGVybWVkaWF0ZScsXG4gIH0sXG5dO1xuXG5hc3luYyBmdW5jdGlvbiBfZmV0Y2hNb2NrS25vd2xlZGdlQmFzZUFydGljbGVzKFxuICBxdWVyeTogc3RyaW5nLFxuICBjb250ZW50VHlwZUhpbnQ/OiBLbm93bGVkZ2VCYXNlQXJ0aWNsZVsnY29udGVudFR5cGUnXSxcbiAgYXBwbGljYXRpb25Db250ZXh0Pzogc3RyaW5nLFxuICBtYXhSZXN1bHRzOiBudW1iZXIgPSAzXG4pOiBQcm9taXNlPEtub3dsZWRnZUJhc2VBcnRpY2xlW10+IHtcbiAgLy8gY29uc29sZS5sb2coYFtfZmV0Y2hNb2NrS25vd2xlZGdlQmFzZUFydGljbGVzXSBRdWVyeTogXCIke3F1ZXJ5fVwiLCBDVDogJHtjb250ZW50VHlwZUhpbnR9LCBBcHBDdHg6ICR7YXBwbGljYXRpb25Db250ZXh0fSwgTWF4OiAke21heFJlc3VsdHN9YCk7XG4gIGNvbnN0IHF1ZXJ5TG93ZXIgPSBxdWVyeS50b0xvd2VyQ2FzZSgpO1xuICBjb25zdCBxdWVyeUtleXdvcmRzID0gcXVlcnlMb3dlci5zcGxpdCgvXFxzKy8pLmZpbHRlcigoa3cpID0+IGt3Lmxlbmd0aCA+IDIpO1xuICBsZXQgZmlsdGVyZWQgPSBNT0NLX0tCX0FSVElDTEVTO1xuXG4gIGlmIChhcHBsaWNhdGlvbkNvbnRleHQpIHtcbiAgICBmaWx0ZXJlZCA9IGZpbHRlcmVkLmZpbHRlcihcbiAgICAgIChhKSA9PlxuICAgICAgICAhYS5hcHBsaWNhdGlvbiB8fFxuICAgICAgICBhLmFwcGxpY2F0aW9uLnRvTG93ZXJDYXNlKCkgPT09IGFwcGxpY2F0aW9uQ29udGV4dC50b0xvd2VyQ2FzZSgpIHx8XG4gICAgICAgIGEuYXBwbGljYXRpb24gPT09ICdHZW5lcmFsJ1xuICAgICk7XG4gIH1cbiAgaWYgKGNvbnRlbnRUeXBlSGludCkge1xuICAgIGZpbHRlcmVkID0gZmlsdGVyZWQuZmlsdGVyKChhKSA9PiBhLmNvbnRlbnRUeXBlID09PSBjb250ZW50VHlwZUhpbnQpO1xuICB9XG5cbiAgY29uc3Qgc2NvcmVkID0gZmlsdGVyZWRcbiAgICAubWFwKChhcnRpY2xlKSA9PiB7XG4gICAgICBsZXQgc2NvcmUgPSAwO1xuICAgICAgY29uc3QgdGl0bGVMb3dlciA9IGFydGljbGUudGl0bGUudG9Mb3dlckNhc2UoKTtcbiAgICAgIGNvbnN0IGNvbnRlbnRTbmlwID0gYXJ0aWNsZS5jb250ZW50LnN1YnN0cmluZygwLCAzMDApLnRvTG93ZXJDYXNlKCk7XG4gICAgICBxdWVyeUtleXdvcmRzLmZvckVhY2goKGt3KSA9PiB7XG4gICAgICAgIGlmICh0aXRsZUxvd2VyLmluY2x1ZGVzKGt3KSkgc2NvcmUgKz0gMztcbiAgICAgICAgaWYgKGFydGljbGUua2V5d29yZHM/LnNvbWUoKGspID0+IGsudG9Mb3dlckNhc2UoKS5pbmNsdWRlcyhrdykpKVxuICAgICAgICAgIHNjb3JlICs9IDI7XG4gICAgICAgIGlmIChjb250ZW50U25pcC5pbmNsdWRlcyhrdykpIHNjb3JlICs9IDE7XG4gICAgICB9KTtcbiAgICAgIGlmIChxdWVyeUxvd2VyLmluY2x1ZGVzKGFydGljbGUuY29udGVudFR5cGUpKSBzY29yZSArPSAyO1xuICAgICAgcmV0dXJuIHsgYXJ0aWNsZSwgc2NvcmUgfTtcbiAgICB9KVxuICAgIC5maWx0ZXIoKGl0ZW0pID0+IGl0ZW0uc2NvcmUgPiAwKVxuICAgIC5zb3J0KChhLCBiKSA9PiBiLnNjb3JlIC0gYS5zY29yZSk7XG4gIHJldHVybiBzY29yZWQuc2xpY2UoMCwgbWF4UmVzdWx0cykubWFwKChpdGVtKSA9PiBpdGVtLmFydGljbGUpO1xufVxuXG5leHBvcnQgaW50ZXJmYWNlIEtub3dsZWRnZUJhc2VBcnRpY2xlIHtcbiAgaWQ6IHN0cmluZztcbiAgdGl0bGU6IHN0cmluZztcbiAgY29udGVudFR5cGU6ICd0dXRvcmlhbCcgfCAnaG93LXRvJyB8ICdmYXEnIHwgJ3dvcmtmbG93X2d1aWRlJyB8ICdleHBsYW5hdGlvbic7XG4gIGFwcGxpY2F0aW9uPzogc3RyaW5nO1xuICBrZXl3b3Jkcz86IHN0cmluZ1tdO1xuICBjb250ZW50OiBzdHJpbmc7XG4gIHN0ZXBzPzogeyB0aXRsZTogc3RyaW5nOyBkZXNjcmlwdGlvbjogc3RyaW5nIH1bXTtcbiAgZGlmZmljdWx0eT86ICdiZWdpbm5lcicgfCAnaW50ZXJtZWRpYXRlJyB8ICdhZHZhbmNlZCc7XG59XG5cbmV4cG9ydCB0eXBlIEd1aWRhbmNlVHlwZSA9XG4gIHwgJ2Fuc3dlcl9xdWVzdGlvbidcbiAgfCAnZmluZF90dXRvcmlhbCdcbiAgfCAnZ3VpZGVfd29ya2Zsb3cnXG4gIHwgJ2dlbmVyYWxfZXhwbGFuYXRpb24nO1xuXG5leHBvcnQgaW50ZXJmYWNlIExlYXJuaW5nQW5kR3VpZGFuY2VJbnB1dCB7XG4gIHVzZXJJZDogc3RyaW5nO1xuICBxdWVyeTogc3RyaW5nO1xuICBndWlkYW5jZVR5cGVIaW50PzogR3VpZGFuY2VUeXBlO1xuICBhcHBsaWNhdGlvbkNvbnRleHQ/OiBzdHJpbmc7XG4gIG9wdGlvbnM/OiB7XG4gICAgcHJlZmVyQ29udGVudFR5cGU/OiBLbm93bGVkZ2VCYXNlQXJ0aWNsZVsnY29udGVudFR5cGUnXTtcbiAgICBtYXhSZXN1bHRzPzogbnVtYmVyO1xuICB9O1xufVxuXG5leHBvcnQgaW50ZXJmYWNlIFByb3ZpZGVkR3VpZGFuY2Uge1xuICB0aXRsZTogc3RyaW5nO1xuICBjb250ZW50U25pcHBldD86IHN0cmluZztcbiAgZnVsbENvbnRlbnQ/OiBzdHJpbmc7XG4gIHN0ZXBzPzogeyB0aXRsZTogc3RyaW5nOyBkZXNjcmlwdGlvbjogc3RyaW5nIH1bXTtcbiAgc291cmNlQXJ0aWNsZUlkOiBzdHJpbmc7XG4gIHJlbGV2YW5jZVNjb3JlPzogbnVtYmVyO1xufVxuXG5leHBvcnQgaW50ZXJmYWNlIExlYXJuaW5nQW5kR3VpZGFuY2VSZXN1bHQge1xuICBvcmlnaW5hbFF1ZXJ5OiBzdHJpbmc7XG4gIGd1aWRhbmNlUHJvdmlkZWQ6IFByb3ZpZGVkR3VpZGFuY2VbXTtcbiAgZm9sbG93VXBTdWdnZXN0aW9ucz86IHN0cmluZ1tdO1xuICBzZWFyY2hQZXJmb3JtZWRPbj86IHN0cmluZztcbn1cblxuZXhwb3J0IGNsYXNzIExlYXJuaW5nQW5kR3VpZGFuY2VTa2lsbCB7XG4gIHByaXZhdGUgcmVhZG9ubHkgbGxtU2VydmljZTogTExNU2VydmljZUludGVyZmFjZTtcblxuICBjb25zdHJ1Y3RvcihsbG1TZXJ2aWNlOiBMTE1TZXJ2aWNlSW50ZXJmYWNlKSB7XG4gICAgdGhpcy5sbG1TZXJ2aWNlID0gbGxtU2VydmljZTtcbiAgICBjb25zb2xlLmxvZygnTGVhcm5pbmdBbmRHdWlkYW5jZVNraWxsIGluaXRpYWxpemVkIHdpdGggTExNU2VydmljZS4nKTtcbiAgfVxuXG4gIHB1YmxpYyBhc3luYyBleGVjdXRlKFxuICAgIGlucHV0OiBMZWFybmluZ0FuZEd1aWRhbmNlSW5wdXRcbiAgKTogUHJvbWlzZTxMZWFybmluZ0FuZEd1aWRhbmNlUmVzdWx0PiB7XG4gICAgY29uc29sZS5sb2coXG4gICAgICBgW0xlYXJuaW5nQW5kR3VpZGFuY2VTa2lsbF0gUXVlcnk6IFwiJHtpbnB1dC5xdWVyeX1cIiwgVXNlcjogJHtpbnB1dC51c2VySWR9YFxuICAgICk7XG5cbiAgICBpZiAoIWlucHV0LnF1ZXJ5IHx8ICFpbnB1dC51c2VySWQpIHtcbiAgICAgIHRocm93IG5ldyBFcnJvcignUXVlcnkgYW5kIHVzZXJJZCBhcmUgcmVxdWlyZWQuJyk7XG4gICAgfVxuICAgIGNvbnN0IG1heFJlc3VsdHMgPSBpbnB1dC5vcHRpb25zPy5tYXhSZXN1bHRzIHx8IDM7XG4gICAgbGV0IGVmZmVjdGl2ZUd1aWRhbmNlVHlwZTogR3VpZGFuY2VUeXBlID1cbiAgICAgIGlucHV0Lmd1aWRhbmNlVHlwZUhpbnQgfHwgJ2Fuc3dlcl9xdWVzdGlvbic7XG5cbiAgICBpZiAoIWlucHV0Lmd1aWRhbmNlVHlwZUhpbnQpIHtcbiAgICAgIGNvbnN0IGNsYXNzRGF0YTogR3VpZGFuY2VRdWVyeUNsYXNzaWZpY2F0aW9uRGF0YSA9IHsgcXVlcnk6IGlucHV0LnF1ZXJ5IH07XG4gICAgICBjb25zdCBjbGFzc1Byb21wdDogU3RydWN0dXJlZExMTVByb21wdCA9IHtcbiAgICAgICAgdGFzazogJ2NsYXNzaWZ5X2d1aWRhbmNlX3F1ZXJ5JyxcbiAgICAgICAgZGF0YTogY2xhc3NEYXRhLFxuICAgICAgfTtcbiAgICAgIHRyeSB7XG4gICAgICAgIGNvbnN0IGxsbVJlc3AgPSBhd2FpdCB0aGlzLmxsbVNlcnZpY2UuZ2VuZXJhdGUoY2xhc3NQcm9tcHQsICdjaGVhcGVzdCcpO1xuICAgICAgICBpZiAobGxtUmVzcC5zdWNjZXNzICYmIGxsbVJlc3AuY29udGVudCkge1xuICAgICAgICAgIGNvbnN0IHBhcnNlZCA9IEpTT04ucGFyc2UobGxtUmVzcC5jb250ZW50KTtcbiAgICAgICAgICBjb25zdCB2YWxpZFR5cGVzOiBHdWlkYW5jZVR5cGVbXSA9IFtcbiAgICAgICAgICAgICdhbnN3ZXJfcXVlc3Rpb24nLFxuICAgICAgICAgICAgJ2ZpbmRfdHV0b3JpYWwnLFxuICAgICAgICAgICAgJ2d1aWRlX3dvcmtmbG93JyxcbiAgICAgICAgICAgICdnZW5lcmFsX2V4cGxhbmF0aW9uJyxcbiAgICAgICAgICBdO1xuICAgICAgICAgIGlmIChcbiAgICAgICAgICAgIHBhcnNlZCAmJlxuICAgICAgICAgICAgcGFyc2VkLmd1aWRhbmNlVHlwZSAmJlxuICAgICAgICAgICAgdmFsaWRUeXBlcy5pbmNsdWRlcyhwYXJzZWQuZ3VpZGFuY2VUeXBlKVxuICAgICAgICAgICkge1xuICAgICAgICAgICAgZWZmZWN0aXZlR3VpZGFuY2VUeXBlID0gcGFyc2VkLmd1aWRhbmNlVHlwZTtcbiAgICAgICAgICB9IGVsc2Uge1xuICAgICAgICAgICAgY29uc29sZS53YXJuKFxuICAgICAgICAgICAgICBgW0xlYXJuaW5nQW5kR3VpZGFuY2VTa2lsbF0gTExNIGludmFsaWQgZ3VpZGFuY2VUeXBlOiAke2xsbVJlc3AuY29udGVudH1gXG4gICAgICAgICAgICApO1xuICAgICAgICAgIH1cbiAgICAgICAgfSBlbHNlIHtcbiAgICAgICAgICBjb25zb2xlLmVycm9yKFxuICAgICAgICAgICAgYFtMZWFybmluZ0FuZEd1aWRhbmNlU2tpbGxdIExMTSBxdWVyeSBjbGFzc2lmaWNhdGlvbiBmYWlsZWQ6ICR7bGxtUmVzcC5lcnJvcn1gXG4gICAgICAgICAgKTtcbiAgICAgICAgfVxuICAgICAgfSBjYXRjaCAoZTogYW55KSB7XG4gICAgICAgIGNvbnNvbGUuZXJyb3IoXG4gICAgICAgICAgYFtMZWFybmluZ0FuZEd1aWRhbmNlU2tpbGxdIEVycm9yIGluIExMTSBxdWVyeSBjbGFzc2lmaWNhdGlvbjogJHtlLm1lc3NhZ2V9YFxuICAgICAgICApO1xuICAgICAgfVxuICAgIH1cbiAgICBjb25zb2xlLmxvZyhcbiAgICAgIGBbTGVhcm5pbmdBbmRHdWlkYW5jZVNraWxsXSBFZmZlY3RpdmUgZ3VpZGFuY2UgdHlwZTogJHtlZmZlY3RpdmVHdWlkYW5jZVR5cGV9YFxuICAgICk7XG5cbiAgICBjb25zdCByZWxldmFudEFydGljbGVzID0gYXdhaXQgX2ZldGNoTW9ja0tub3dsZWRnZUJhc2VBcnRpY2xlcyhcbiAgICAgIGlucHV0LnF1ZXJ5LFxuICAgICAgaW5wdXQub3B0aW9ucz8ucHJlZmVyQ29udGVudFR5cGUsXG4gICAgICBpbnB1dC5hcHBsaWNhdGlvbkNvbnRleHQsXG4gICAgICBtYXhSZXN1bHRzXG4gICAgKTtcbiAgICBjb25zdCBndWlkYW5jZVByb3ZpZGVkOiBQcm92aWRlZEd1aWRhbmNlW10gPSBbXTtcblxuICAgIGZvciAoY29uc3QgYXJ0aWNsZSBvZiByZWxldmFudEFydGljbGVzKSB7XG4gICAgICBsZXQgZ3VpZGFuY2U6IFByb3ZpZGVkR3VpZGFuY2UgPSB7XG4gICAgICAgIHRpdGxlOiBhcnRpY2xlLnRpdGxlLFxuICAgICAgICBzb3VyY2VBcnRpY2xlSWQ6IGFydGljbGUuaWQsXG4gICAgICAgIHJlbGV2YW5jZVNjb3JlOiAwLjYsXG4gICAgICB9O1xuICAgICAgdHJ5IHtcbiAgICAgICAgbGV0IHN0cnVjdHVyZWRBcnRpY2xlUHJvbXB0OiBTdHJ1Y3R1cmVkTExNUHJvbXB0O1xuICAgICAgICBsZXQgdGFzazogTExNVGFza1R5cGU7XG5cbiAgICAgICAgc3dpdGNoIChlZmZlY3RpdmVHdWlkYW5jZVR5cGUpIHtcbiAgICAgICAgICBjYXNlICdhbnN3ZXJfcXVlc3Rpb24nOlxuICAgICAgICAgICAgdGFzayA9ICdhbnN3ZXJfZnJvbV90ZXh0JztcbiAgICAgICAgICAgIGNvbnN0IGFuc3dlckRhdGE6IEFuc3dlckZyb21UZXh0RGF0YSA9IHtcbiAgICAgICAgICAgICAgcXVlcnk6IGlucHV0LnF1ZXJ5LFxuICAgICAgICAgICAgICB0ZXh0Q29udGVudDogYXJ0aWNsZS5jb250ZW50LnN1YnN0cmluZygwLCAxNTAwKSxcbiAgICAgICAgICAgICAgYXJ0aWNsZVRpdGxlOiBhcnRpY2xlLnRpdGxlLFxuICAgICAgICAgICAgfTtcbiAgICAgICAgICAgIHN0cnVjdHVyZWRBcnRpY2xlUHJvbXB0ID0geyB0YXNrLCBkYXRhOiBhbnN3ZXJEYXRhIH07XG4gICAgICAgICAgICBicmVhaztcbiAgICAgICAgICBjYXNlICdnZW5lcmFsX2V4cGxhbmF0aW9uJzpcbiAgICAgICAgICAgIHRhc2sgPSAnc3VtbWFyaXplX2Zvcl9leHBsYW5hdGlvbic7XG4gICAgICAgICAgICBjb25zdCBleHBsRGF0YTogRXhwbGFuYXRpb25EYXRhID0ge1xuICAgICAgICAgICAgICBxdWVyeTogaW5wdXQucXVlcnksXG4gICAgICAgICAgICAgIHRleHRDb250ZW50OiBhcnRpY2xlLmNvbnRlbnQuc3Vic3RyaW5nKDAsIDE1MDApLFxuICAgICAgICAgICAgICBhcnRpY2xlVGl0bGU6IGFydGljbGUudGl0bGUsXG4gICAgICAgICAgICB9O1xuICAgICAgICAgICAgc3RydWN0dXJlZEFydGljbGVQcm9tcHQgPSB7IHRhc2ssIGRhdGE6IGV4cGxEYXRhIH07XG4gICAgICAgICAgICBicmVhaztcbiAgICAgICAgICBjYXNlICdmaW5kX3R1dG9yaWFsJzpcbiAgICAgICAgICBjYXNlICdndWlkZV93b3JrZmxvdyc6XG4gICAgICAgICAgICBpZiAoYXJ0aWNsZS5zdGVwcyAmJiBhcnRpY2xlLnN0ZXBzLmxlbmd0aCA+IDApIHtcbiAgICAgICAgICAgICAgZ3VpZGFuY2Uuc3RlcHMgPSBhcnRpY2xlLnN0ZXBzO1xuICAgICAgICAgICAgICBndWlkYW5jZS5jb250ZW50U25pcHBldCA9IGBGb3VuZCByZWxldmFudCBzdGVwcyBpbiBcIiR7YXJ0aWNsZS50aXRsZX1cIi5gO1xuICAgICAgICAgICAgICBndWlkYW5jZS5yZWxldmFuY2VTY29yZSA9IDAuODU7XG4gICAgICAgICAgICAgIGd1aWRhbmNlUHJvdmlkZWQucHVzaChndWlkYW5jZSk7IC8vIFB1c2ggZWFybHkgaWYgcHJlZGVmaW5lZCBzdGVwcyBhcmUgdXNlZFxuICAgICAgICAgICAgICBjb250aW51ZTsgLy8gU2tpcCBMTE0gY2FsbCBmb3Igc3RlcHNcbiAgICAgICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgICAgIHRhc2sgPSAnZXh0cmFjdF9zdGVwc19mcm9tX3RleHQnO1xuICAgICAgICAgICAgICBjb25zdCBzdGVwc0RhdGE6IFN0ZXBzRnJvbVRleHREYXRhID0ge1xuICAgICAgICAgICAgICAgIHF1ZXJ5OiBpbnB1dC5xdWVyeSxcbiAgICAgICAgICAgICAgICB0ZXh0Q29udGVudDogYXJ0aWNsZS5jb250ZW50LnN1YnN0cmluZygwLCAyMDAwKSxcbiAgICAgICAgICAgICAgICBhcnRpY2xlVGl0bGU6IGFydGljbGUudGl0bGUsXG4gICAgICAgICAgICAgIH07XG4gICAgICAgICAgICAgIHN0cnVjdHVyZWRBcnRpY2xlUHJvbXB0ID0geyB0YXNrLCBkYXRhOiBzdGVwc0RhdGEgfTtcbiAgICAgICAgICAgIH1cbiAgICAgICAgICAgIGJyZWFrO1xuICAgICAgICAgIGRlZmF1bHQ6XG4gICAgICAgICAgICBjb25zb2xlLndhcm4oXG4gICAgICAgICAgICAgIGBbTGVhcm5pbmdBbmRHdWlkYW5jZVNraWxsXSBVbmV4cGVjdGVkIGd1aWRhbmNlIHR5cGU6ICR7ZWZmZWN0aXZlR3VpZGFuY2VUeXBlfS4gRGVmYXVsdGluZyB0byBzbmlwcGV0LmBcbiAgICAgICAgICAgICk7XG4gICAgICAgICAgICBndWlkYW5jZS5jb250ZW50U25pcHBldCA9IGBBcnRpY2xlOiAke2FydGljbGUudGl0bGV9LiBFeGNlcnB0OiAke2FydGljbGUuY29udGVudC5zdWJzdHJpbmcoMCwgMjAwKX0uLi5gO1xuICAgICAgICAgICAgZ3VpZGFuY2VQcm92aWRlZC5wdXNoKGd1aWRhbmNlKTtcbiAgICAgICAgICAgIGNvbnRpbnVlOyAvLyBTa2lwIExMTSBjYWxsXG4gICAgICAgIH1cblxuICAgICAgICBjb25zdCBsbG1SZXNwb25zZSA9IGF3YWl0IHRoaXMubGxtU2VydmljZS5nZW5lcmF0ZShcbiAgICAgICAgICBzdHJ1Y3R1cmVkQXJ0aWNsZVByb21wdCxcbiAgICAgICAgICAnY2hlYXBlc3QnXG4gICAgICAgICk7XG5cbiAgICAgICAgaWYgKGxsbVJlc3BvbnNlLnN1Y2Nlc3MgJiYgbGxtUmVzcG9uc2UuY29udGVudCkge1xuICAgICAgICAgIGlmIChcbiAgICAgICAgICAgIGVmZmVjdGl2ZUd1aWRhbmNlVHlwZSA9PT0gJ2Fuc3dlcl9xdWVzdGlvbicgfHxcbiAgICAgICAgICAgIGVmZmVjdGl2ZUd1aWRhbmNlVHlwZSA9PT0gJ2dlbmVyYWxfZXhwbGFuYXRpb24nXG4gICAgICAgICAgKSB7XG4gICAgICAgICAgICBpZiAoXG4gICAgICAgICAgICAgICFsbG1SZXNwb25zZS5jb250ZW50LnRvTG93ZXJDYXNlKCkuc3RhcnRzV2l0aCgnbGxtIGZhbGxiYWNrJykgJiZcbiAgICAgICAgICAgICAgIWxsbVJlc3BvbnNlLmNvbnRlbnRcbiAgICAgICAgICAgICAgICAudG9Mb3dlckNhc2UoKVxuICAgICAgICAgICAgICAgIC5pbmNsdWRlcygnbm90IGFwcGVhciB0byBjb250YWluJylcbiAgICAgICAgICAgICkge1xuICAgICAgICAgICAgICBndWlkYW5jZS5jb250ZW50U25pcHBldCA9IGxsbVJlc3BvbnNlLmNvbnRlbnQ7XG4gICAgICAgICAgICAgIGd1aWRhbmNlLnJlbGV2YW5jZVNjb3JlID0gMC44O1xuICAgICAgICAgICAgfSBlbHNlIHtcbiAgICAgICAgICAgICAgZ3VpZGFuY2UuY29udGVudFNuaXBwZXQgPSBgQXJ0aWNsZSBcIiR7YXJ0aWNsZS50aXRsZX1cIiBmb3VuZCwgYnV0IHNwZWNpZmljIGluZm8gZm9yIFwiJHtpbnB1dC5xdWVyeX1cIiBub3QgZXh0cmFjdGVkLiBMTE0gc2FpZDogJHtsbG1SZXNwb25zZS5jb250ZW50fWA7XG4gICAgICAgICAgICB9XG4gICAgICAgICAgfSBlbHNlIGlmIChcbiAgICAgICAgICAgIGVmZmVjdGl2ZUd1aWRhbmNlVHlwZSA9PT0gJ2ZpbmRfdHV0b3JpYWwnIHx8XG4gICAgICAgICAgICBlZmZlY3RpdmVHdWlkYW5jZVR5cGUgPT09ICdndWlkZV93b3JrZmxvdydcbiAgICAgICAgICApIHtcbiAgICAgICAgICAgIC8vIE9ubHkgaWYgTExNIHdhcyBjYWxsZWQgZm9yIHN0ZXBzXG4gICAgICAgICAgICB0cnkge1xuICAgICAgICAgICAgICBjb25zdCBwYXJzZWRTdGVwcyA9IEpTT04ucGFyc2UobGxtUmVzcG9uc2UuY29udGVudCk7XG4gICAgICAgICAgICAgIGlmIChcbiAgICAgICAgICAgICAgICBwYXJzZWRTdGVwcyAmJlxuICAgICAgICAgICAgICAgIEFycmF5LmlzQXJyYXkocGFyc2VkU3RlcHMuc3RlcHMpICYmXG4gICAgICAgICAgICAgICAgcGFyc2VkU3RlcHMuc3RlcHMubGVuZ3RoID4gMFxuICAgICAgICAgICAgICApIHtcbiAgICAgICAgICAgICAgICBndWlkYW5jZS5zdGVwcyA9IHBhcnNlZFN0ZXBzLnN0ZXBzO1xuICAgICAgICAgICAgICAgIGd1aWRhbmNlLmNvbnRlbnRTbmlwcGV0ID0gJ0V4dHJhY3RlZCB0aGUgZm9sbG93aW5nIGtleSBzdGVwczonO1xuICAgICAgICAgICAgICAgIGd1aWRhbmNlLnJlbGV2YW5jZVNjb3JlID0gMC44O1xuICAgICAgICAgICAgICB9IGVsc2Uge1xuICAgICAgICAgICAgICAgIGd1aWRhbmNlLmNvbnRlbnRTbmlwcGV0ID0gYFwiJHthcnRpY2xlLnRpdGxlfVwiIHJlbGV2YW50LCBidXQgc3BlY2lmaWMgc3RlcHMgZm9yIFwiJHtpbnB1dC5xdWVyeX1cIiBub3QgZXh0cmFjdGVkLmA7XG4gICAgICAgICAgICAgIH1cbiAgICAgICAgICAgIH0gY2F0Y2ggKGUpIHtcbiAgICAgICAgICAgICAgY29uc29sZS5lcnJvcihcbiAgICAgICAgICAgICAgICBgW0xlYXJuaW5nQW5kR3VpZGFuY2VTa2lsbF0gRXJyb3IgcGFyc2luZyBzdGVwcyBKU09OIGZyb20gTExNIGZvciBcIiR7YXJ0aWNsZS50aXRsZX1cIjpgLFxuICAgICAgICAgICAgICAgIGVcbiAgICAgICAgICAgICAgKTtcbiAgICAgICAgICAgICAgZ3VpZGFuY2UuY29udGVudFNuaXBwZXQgPSBgQ291bGQgbm90IHBhcnNlIHN0ZXBzIGZvciBcIiR7YXJ0aWNsZS50aXRsZX1cIi4gTExNIHJlc3BvbnNlOiAke2xsbVJlc3BvbnNlLmNvbnRlbnQuc3Vic3RyaW5nKDAsIDEwMCl9Li4uYDtcbiAgICAgICAgICAgIH1cbiAgICAgICAgICB9XG4gICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgY29uc29sZS5lcnJvcihcbiAgICAgICAgICAgIGBbTGVhcm5pbmdBbmRHdWlkYW5jZVNraWxsXSBMTE0gcHJvY2Vzc2luZyBmYWlsZWQgZm9yIGFydGljbGUgJHthcnRpY2xlLmlkfTogJHtsbG1SZXNwb25zZS5lcnJvcn1gXG4gICAgICAgICAgKTtcbiAgICAgICAgICBndWlkYW5jZS5jb250ZW50U25pcHBldCA9IGBFcnJvciBwcm9jZXNzaW5nIGFydGljbGUgXCIke2FydGljbGUudGl0bGV9XCIgZm9yIHlvdXIgcXVlcnkuYDtcbiAgICAgICAgfVxuICAgICAgfSBjYXRjaCAoZTogYW55KSB7XG4gICAgICAgIGNvbnNvbGUuZXJyb3IoXG4gICAgICAgICAgYFtMZWFybmluZ0FuZEd1aWRhbmNlU2tpbGxdIE91dGVyIGVycm9yIHByb2Nlc3NpbmcgYXJ0aWNsZSAke2FydGljbGUuaWR9OiAke2UubWVzc2FnZX1gXG4gICAgICAgICk7XG4gICAgICAgIGd1aWRhbmNlLmNvbnRlbnRTbmlwcGV0ID0gYFN5c3RlbSBlcnJvciBwcm9jZXNzaW5nIGFydGljbGUgXCIke2FydGljbGUudGl0bGV9XCIuYDtcbiAgICAgIH1cbiAgICAgIGlmIChcbiAgICAgICAgIWd1aWRhbmNlLmNvbnRlbnRTbmlwcGV0ICYmXG4gICAgICAgICghZ3VpZGFuY2Uuc3RlcHMgfHwgZ3VpZGFuY2Uuc3RlcHMubGVuZ3RoID09PSAwKVxuICAgICAgKSB7XG4gICAgICAgIGd1aWRhbmNlLmNvbnRlbnRTbmlwcGV0ID0gYEFydGljbGUgXCIke2FydGljbGUudGl0bGV9XCIgbWF5IGJlIHJlbGV2YW50LiBFeGNlcnB0OiAke2FydGljbGUuY29udGVudC5zdWJzdHJpbmcoMCwgMTUwKX0uLi5gO1xuICAgICAgfVxuICAgICAgZ3VpZGFuY2VQcm92aWRlZC5wdXNoKGd1aWRhbmNlKTtcbiAgICB9XG5cbiAgICBsZXQgZm9sbG93VXBTdWdnZXN0aW9uczogc3RyaW5nW10gfCB1bmRlZmluZWQgPSB1bmRlZmluZWQ7XG4gICAgaWYgKGd1aWRhbmNlUHJvdmlkZWQubGVuZ3RoID4gMCAmJiBndWlkYW5jZVByb3ZpZGVkWzBdKSB7XG4gICAgICBjb25zdCBmb2xsb3d1cERhdGE6IEZvbGxvd3VwU3VnZ2VzdGlvbkRhdGEgPSB7XG4gICAgICAgIHF1ZXJ5OiBpbnB1dC5xdWVyeSxcbiAgICAgICAgYXJ0aWNsZVRpdGxlOiBndWlkYW5jZVByb3ZpZGVkWzBdLnRpdGxlLFxuICAgICAgfTtcbiAgICAgIGNvbnN0IGZvbGxvd3VwUHJvbXB0OiBTdHJ1Y3R1cmVkTExNUHJvbXB0ID0ge1xuICAgICAgICB0YXNrOiAnZ2VuZXJhdGVfZm9sbG93dXBfc3VnZ2VzdGlvbnMnLFxuICAgICAgICBkYXRhOiBmb2xsb3d1cERhdGEsXG4gICAgICB9O1xuICAgICAgdHJ5IHtcbiAgICAgICAgY29uc3QgZm9sbG93dXBSZXNwID0gYXdhaXQgdGhpcy5sbG1TZXJ2aWNlLmdlbmVyYXRlKFxuICAgICAgICAgIGZvbGxvd3VwUHJvbXB0LFxuICAgICAgICAgICdjaGVhcGVzdCdcbiAgICAgICAgKTtcbiAgICAgICAgaWYgKGZvbGxvd3VwUmVzcC5zdWNjZXNzICYmIGZvbGxvd3VwUmVzcC5jb250ZW50KSB7XG4gICAgICAgICAgY29uc3QgcGFyc2VkID0gSlNPTi5wYXJzZShmb2xsb3d1cFJlc3AuY29udGVudCk7XG4gICAgICAgICAgaWYgKFxuICAgICAgICAgICAgcGFyc2VkICYmXG4gICAgICAgICAgICBBcnJheS5pc0FycmF5KHBhcnNlZC5zdWdnZXN0aW9ucykgJiZcbiAgICAgICAgICAgIHBhcnNlZC5zdWdnZXN0aW9ucy5sZW5ndGggPiAwXG4gICAgICAgICAgKSB7XG4gICAgICAgICAgICBmb2xsb3dVcFN1Z2dlc3Rpb25zID0gcGFyc2VkLnN1Z2dlc3Rpb25zLmZpbHRlcihcbiAgICAgICAgICAgICAgKHM6IGFueSk6IHMgaXMgc3RyaW5nID0+IHR5cGVvZiBzID09PSAnc3RyaW5nJ1xuICAgICAgICAgICAgKTtcbiAgICAgICAgICB9XG4gICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgY29uc29sZS53YXJuKFxuICAgICAgICAgICAgYFtMZWFybmluZ0FuZEd1aWRhbmNlU2tpbGxdIExMTSBmb2xsb3ctdXAgc3VnZ2VzdGlvbnMgZmFpbGVkOiAke2ZvbGxvd3VwUmVzcC5lcnJvcn1gXG4gICAgICAgICAgKTtcbiAgICAgICAgfVxuICAgICAgfSBjYXRjaCAoZTogYW55KSB7XG4gICAgICAgIGNvbnNvbGUuZXJyb3IoXG4gICAgICAgICAgYFtMZWFybmluZ0FuZEd1aWRhbmNlU2tpbGxdIEVycm9yIHByb2Nlc3NpbmcgTExNIGZvbGxvdy11cCBzdWdnZXN0aW9uczogJHtlLm1lc3NhZ2V9YFxuICAgICAgICApO1xuICAgICAgfVxuICAgIH1cblxuICAgIGNvbnN0IGZpbmFsUmVzdWx0OiBMZWFybmluZ0FuZEd1aWRhbmNlUmVzdWx0ID0ge1xuICAgICAgb3JpZ2luYWxRdWVyeTogaW5wdXQucXVlcnksXG4gICAgICBndWlkYW5jZVByb3ZpZGVkOiBndWlkYW5jZVByb3ZpZGVkLFxuICAgICAgZm9sbG93VXBTdWdnZXN0aW9uczogZm9sbG93VXBTdWdnZXN0aW9ucyxcbiAgICAgIHNlYXJjaFBlcmZvcm1lZE9uOiBgJHtyZWxldmFudEFydGljbGVzLmxlbmd0aH0gYXJ0aWNsZXMgZnJvbSAke2lucHV0LmFwcGxpY2F0aW9uQ29udGV4dCB8fCAnR2VuZXJhbCd9IEtCIG1hdGNoaW5nIFwiJHtpbnB1dC5xdWVyeS5zdWJzdHJpbmcoMCwgNTApfS4uLlwiYCxcbiAgICB9O1xuXG4gICAgY29uc29sZS5sb2coXG4gICAgICBgW0xlYXJuaW5nQW5kR3VpZGFuY2VTa2lsbF0gUmV0dXJuaW5nIGd1aWRhbmNlIGZvciBxdWVyeTogXCIke2lucHV0LnF1ZXJ5fVwiYFxuICAgICk7XG4gICAgcmV0dXJuIGZpbmFsUmVzdWx0O1xuICB9XG59XG5cbi8vIEV4YW1wbGUgVXNhZ2Vcbi8qXG5pbXBvcnQgeyBNb2NrTExNU2VydmljZSB9IGZyb20gJy4uL2xpYi9sbG1VdGlscyc7IC8vIE9yIE9wZW5BSUdyb3FTZXJ2aWNlX1N0dWJcblxuYXN5bmMgZnVuY3Rpb24gdGVzdExlYXJuaW5nQW5kR3VpZGFuY2VTa2lsbCgpIHtcbiAgY29uc3QgbGxtU2VydmljZSA9IG5ldyBNb2NrTExNU2VydmljZSgpO1xuICBjb25zdCBza2lsbCA9IG5ldyBMZWFybmluZ0FuZEd1aWRhbmNlU2tpbGwobGxtU2VydmljZSk7XG5cbiAgY29uc3QgdGVzdElucHV0MTogTGVhcm5pbmdBbmRHdWlkYW5jZUlucHV0ID0ge1xuICAgIHVzZXJJZDogXCJ1c2VyLWd1aWRhbmNlLXRlc3QtMVwiLFxuICAgIHF1ZXJ5OiBcIkhvdyBkbyBJIGNyZWF0ZSBhIHBpdm90IHRhYmxlIGluIFNwcmVhZHNoZWV0QXBwP1wiLFxuICAgIGFwcGxpY2F0aW9uQ29udGV4dDogXCJTcHJlYWRzaGVldEFwcFwiLFxuICAgIG9wdGlvbnM6IHsgcHJlZmVyQ29udGVudFR5cGU6ICdob3ctdG8nLCBtYXhSZXN1bHRzOiAxIH1cbiAgfTtcbiAgLy8gLi4uIHJlc3Qgb2YgdGVzdCBjb2RlXG59XG4vLyB0ZXN0TGVhcm5pbmdBbmRHdWlkYW5jZVNraWxsKCk7XG4qL1xuIl19