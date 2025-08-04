"use strict";
// Shared LLM utilities, types, and mock implementations
Object.defineProperty(exports, "__esModule", { value: true });
exports.RealLLMService = exports.MockLLMService = void 0;
class MockLLMService {
    async generate(structuredPrompt, model, options) {
        console.log(`[MockLLMService] Received task "${structuredPrompt.task}" for model "${model}". Data keys: ${Object.keys(structuredPrompt.data || {}).join(', ')}`);
        await new Promise((resolve) => setTimeout(resolve, Math.random() * 100 + 50));
        try {
            let content;
            switch (structuredPrompt.task) {
                case 'categorize_email': {
                    const data = structuredPrompt.data;
                    const subjectLower = data.subject.toLowerCase();
                    const bodySnippetLower = data.bodySnippet.toLowerCase();
                    const textForCat = `${subjectLower} ${bodySnippetLower}`;
                    let category = 'Other'; // Allow string for flexibility in mock
                    let confidence = parseFloat((Math.random() * 0.3 + 0.3).toFixed(2));
                    if (subjectLower.includes('win a free') ||
                        textForCat.includes('limited time offer') ||
                        textForCat.includes('cialis') ||
                        textForCat.includes('viagra')) {
                        category = 'Spam';
                        confidence = 0.99;
                    }
                    else if (subjectLower.includes('meeting invite') ||
                        subjectLower.includes('calendar invite') ||
                        subjectLower.endsWith('.ics') ||
                        bodySnippetLower.includes('begin:vcalendar')) {
                        category = 'MeetingInvite';
                        confidence = 0.95;
                    }
                    else if (textForCat.includes('urgent') ||
                        textForCat.includes('critical') ||
                        textForCat.includes('outage') ||
                        textForCat.includes('asap')) {
                        category = 'Urgent';
                        confidence = parseFloat((Math.random() * 0.15 + 0.8).toFixed(2));
                    }
                    else if (textForCat.includes('action required') ||
                        textForCat.includes('please review') ||
                        textForCat.includes('task for you') ||
                        textForCat.includes('deadline')) {
                        category = 'ActionRequired';
                        confidence = parseFloat((Math.random() * 0.2 + 0.7).toFixed(2));
                    }
                    else if (textForCat.includes('fyi') ||
                        textForCat.includes('heads up') ||
                        textForCat.includes('update') ||
                        subjectLower.includes('newsletter')) {
                        category = 'FYI';
                        confidence = parseFloat((Math.random() * 0.2 + 0.6).toFixed(2));
                    }
                    else if (data.bodySnippet.length < 50 &&
                        !textForCat.match(/(urgent|action|meeting|spam)/i)) {
                        category = Math.random() < 0.5 ? 'FYI' : 'Other';
                        confidence = parseFloat((Math.random() * 0.2 + 0.45).toFixed(2));
                    }
                    else if (Math.random() < 0.05) {
                        // Chance of plausible miscategorization
                        const cats = ['ActionRequired', 'FYI', 'Other'];
                        category = cats[Math.floor(Math.random() * cats.length)];
                        confidence = parseFloat((Math.random() * 0.3 + 0.3).toFixed(2));
                    }
                    content = JSON.stringify({ category, confidence });
                    break;
                }
                case 'summarize_email': {
                    const data = structuredPrompt.data;
                    const subject = data.subject.trim();
                    const bodySnippet = data.bodySnippet.trim();
                    if (bodySnippet.length === 0)
                        content = `The email with subject "${subject}" has no body content.`;
                    else if (bodySnippet.length < 70 && !bodySnippet.includes('.'))
                        content = `Subject: "${subject}". Content: "${bodySnippet}"`;
                    else {
                        const firstSentence = bodySnippet.match(/[^.!?]+[.!?]+/g)?.[0]?.trim() ||
                            bodySnippet.substring(0, 100);
                        content = `Regarding "${subject}", the email mentions: "${firstSentence.substring(0, 100)}${firstSentence.length > 100 ? '...' : ''}".`;
                    }
                    if (subject.toLowerCase().startsWith('re:') ||
                        subject.toLowerCase().startsWith('fwd:'))
                        content = `This is part of a thread on "${subject}". ${content}`;
                    if (Math.random() < 0.3)
                        content += ' Further details might be important.';
                    break;
                }
                case 'suggest_reply_email': {
                    const data = structuredPrompt.data;
                    if (data.category === 'Spam' ||
                        (data.category === 'FYI' && Math.random() < 0.7)) {
                        // More likely no reply for FYI
                        content = 'No reply needed.';
                    }
                    else if (data.category === 'Urgent') {
                        content =
                            'Acknowledged. Looking into this with high priority and will update shortly.';
                    }
                    else if (data.category === 'ActionRequired') {
                        content =
                            data.actionItems && data.actionItems.length > 0
                                ? `Understood. I will start with: "${data.actionItems[0]}".`
                                : "Received. I'll take care of the necessary actions.";
                    }
                    else if (data.category === 'MeetingInvite') {
                        content =
                            "Thanks for the invite! I'll check my availability and respond via calendar.";
                    }
                    else {
                        content = `Thank you for your email regarding "${data.subject}". I will review it.`;
                    }
                    break;
                }
                case 'extract_actions_email': {
                    const data = structuredPrompt.data;
                    const bodyLower = data.emailBody.toLowerCase();
                    const actions = [];
                    if (bodyLower.includes('please send') ||
                        bodyLower.includes('can you attach'))
                        actions.push('Send/attach requested document.');
                    if (bodyLower.includes('schedule a meeting') ||
                        bodyLower.includes('set up a call'))
                        actions.push('Schedule a meeting.');
                    if (bodyLower.includes('confirm availability') ||
                        bodyLower.includes('are you free'))
                        actions.push('Confirm availability for something.');
                    if (bodyLower.includes('your thoughts on') ||
                        bodyLower.includes('feedback on'))
                        actions.push('Provide feedback/thoughts.');
                    content = JSON.stringify({ actionItems: actions.slice(0, 2) });
                    break;
                }
                case 'extract_document_snippets': {
                    const data = structuredPrompt.data;
                    content = JSON.stringify({
                        snippets: [
                            `Mock snippet for "${data.query}" from "${data.documentTitle}".`,
                            `Another detail regarding "${data.query}".`,
                        ],
                    });
                    break;
                }
                case 'summarize_document_snippets': {
                    const data = structuredPrompt.data;
                    content = `This is a mock ${data.targetLength || 'medium'} summary about "${data.query}" from "${data.documentTitle}".`;
                    break;
                }
                case 'summarize_overall_answer': {
                    const data = structuredPrompt.data;
                    content = `Overall mock summary for "${data.query}", combining ${data.individualSummaries.length} sources.`;
                    break;
                }
                case 'classify_guidance_query': {
                    const data = structuredPrompt.data;
                    const qL = data.query.toLowerCase();
                    if (qL.includes('how to') || qL.includes('steps'))
                        content = JSON.stringify({ guidanceType: 'find_tutorial' });
                    else if (qL.includes('what is') || qL.includes('explain'))
                        content = JSON.stringify({ guidanceType: 'general_explanation' });
                    else if (qL.includes('guide') || qL.includes('workflow'))
                        content = JSON.stringify({ guidanceType: 'guide_workflow' });
                    else
                        content = JSON.stringify({ guidanceType: 'answer_question' });
                    break;
                }
                case 'answer_from_text': {
                    const data = structuredPrompt.data;
                    content = `Mock answer for "${data.query}" from "${data.articleTitle || 'the document'}": ${data.textContent.substring(0, 70)}...`;
                    break;
                }
                case 'extract_steps_from_text': {
                    const data = structuredPrompt.data;
                    content = JSON.stringify({
                        steps: [
                            {
                                title: 'Mock Step 1 (from LLM)',
                                description: `Do this first for ${data.query}`,
                            },
                            { title: 'Mock Step 2', description: 'Then do that.' },
                        ],
                    });
                    break;
                }
                case 'summarize_for_explanation': {
                    const data = structuredPrompt.data;
                    content = `Mock explanation of "${data.query}" based on "${data.articleTitle}". It covers...`;
                    break;
                }
                case 'generate_followup_suggestions': {
                    const data = structuredPrompt.data;
                    content = JSON.stringify({
                        suggestions: [
                            `Advanced ${data.articleTitle || data.query}`,
                            'Related Topic B',
                        ],
                    });
                    break;
                }
                case 'custom_analytical_analysis': {
                    content = JSON.stringify({
                        identifiedEntities: ['pivot table', 'SpreadsheetApp'],
                        explicitTasks: ['create pivot table'],
                        informationNeeded: [],
                        logicalConsistency: { isConsistent: true, reason: '' },
                        problemType: 'how_to',
                    });
                    break;
                }
                case 'custom_creative_analysis': {
                    content = JSON.stringify({
                        alternativeGoals: ['understand data better', 'create a chart'],
                        novelSolutionsSuggested: ['use a pre-built template'],
                        unstatedAssumptions: ['user has data ready'],
                        potentialEnhancements: ['add conditional formatting'],
                        ambiguityFlags: [],
                    });
                    break;
                }
                case 'custom_practical_analysis': {
                    content = JSON.stringify({
                        contextualFactors: [],
                        feasibilityAssessment: {
                            rating: 'High',
                            reason: '',
                            dependencies: [],
                        },
                        efficiencyTips: ["use the 'Recommended PivotTables' feature"],
                        resourceImplications: {
                            timeEstimate: 'Quick',
                            toolsNeeded: ['SpreadsheetApp'],
                        },
                        commonSenseValidation: { isValid: true, reason: '' },
                    });
                    break;
                }
                case 'custom_synthesis': {
                    content = JSON.stringify({
                        primaryGoal: 'create a pivot table',
                        primaryGoalConfidence: 0.9,
                        identifiedTasks: ['create pivot table'],
                        extractedParameters: { app: 'SpreadsheetApp' },
                        suggestedNextAction: {
                            actionType: 'invoke_skill',
                            skillId: 'LearningAndGuidanceSkill',
                            reason: "User is asking a 'how-to' question.",
                        },
                    });
                    break;
                }
                case 'custom_advanced_research': {
                    content = JSON.stringify({
                        researchSummary: 'This is a mock research summary.',
                        keyFindings: ['Mock finding 1', 'Mock finding 2'],
                        sources: [{ title: 'Mock Source', url: 'https://example.com' }],
                    });
                    break;
                }
                case 'custom_social_media': {
                    content = JSON.stringify({
                        scheduledPosts: [
                            {
                                platform: 'Twitter',
                                content: 'This is a mock tweet.',
                                scheduledTime: '2025-01-01T12:00:00Z',
                            },
                        ],
                        engagementSummary: 'This is a mock engagement summary.',
                    });
                    break;
                }
                case 'custom_content_creation': {
                    content = JSON.stringify({
                        generatedContent: 'This is mock generated content.',
                        contentType: 'blog post',
                    });
                    break;
                }
                case 'custom_personalized_shopping': {
                    content = JSON.stringify({
                        productRecommendations: [
                            {
                                productName: 'Mock Laptop',
                                price: 999,
                                url: 'https://example.com/laptop',
                                reasoning: "It's a great value for the price.",
                            },
                        ],
                    });
                    break;
                }
                case 'custom_legal_document_analysis': {
                    content = JSON.stringify({
                        riskAnalysis: [
                            {
                                clause: 'This is a mock clause.',
                                riskLevel: 'Medium',
                                explanation: 'This is a mock explanation.',
                            },
                        ],
                        summary: 'This is a mock summary of the legal document.',
                    });
                    break;
                }
                case 'custom_recruitment_recommendation': {
                    content = JSON.stringify({
                        recommendedCandidates: [
                            {
                                name: 'Mock Candidate',
                                resumeUrl: 'https://example.com/resume',
                                matchScore: 0.9,
                                summary: "This is a mock summary of the candidate's qualifications.",
                            },
                        ],
                    });
                    break;
                }
                case 'custom_vibe_hacking': {
                    content = JSON.stringify({
                        vulnerabilityReport: [
                            {
                                vulnerability: 'Mock Vulnerability',
                                severity: 'High',
                                description: 'This is a mock description of the vulnerability.',
                                remediation: 'This is a mock remediation.',
                            },
                        ],
                    });
                    break;
                }
                default:
                    console.warn(`[MockLLMService] Unhandled task type: ${structuredPrompt.task}`);
                    return {
                        success: false,
                        error: `Unhandled task type: ${structuredPrompt.task}`,
                    };
            }
            return { success: true, content };
        }
        catch (error) {
            console.error(`[MockLLMService] Error during task ${structuredPrompt.task}:`, error);
            return {
                success: false,
                error: error.message || 'Unknown error in MockLLMService',
            };
        }
    }
}
exports.MockLLMService = MockLLMService;
const MAX_RETRIES = 3;
const INITIAL_RETRY_DELAY_MS = 1000;
class RealLLMService {
    apiKey;
    defaultModelName;
    baseURL; // e.g., 'https://api.groq.com/openai/v1' or 'https://api.openai.com/v1'
    openai; // This would be an instance of the OpenAI client
    constructor(apiKey, defaultModelName, baseURL = 'https://api.openai.com/v1' // Default to OpenAI, can be overridden for Groq etc.
    ) {
        if (!apiKey ||
            apiKey === 'YOUR_API_KEY_PLACEHOLDER' ||
            apiKey.length < 10) {
            // In a real app, this might throw an error or have a more robust check.
            console.error('RealLLMService: API Key is missing, a placeholder, or too short! Real calls will likely fail.');
            // Allow construction for testing/mocking purposes, but log a severe warning.
        }
        this.apiKey = apiKey;
        this.defaultModelName = defaultModelName;
        this.baseURL = baseURL;
        // --- Conceptual API Key Security Note ---
        // In a production environment, API keys should NEVER be hardcoded.
        // They should be retrieved from environment variables or a secure secrets management service.
        // Example: this.apiKey = process.env.LLM_API_KEY;
        // The value passed to this constructor should be sourced securely.
        // --- End Security Note ---
        // Initialize the OpenAI client (conceptual)
        // In a real implementation:
        // this.openai = new OpenAI({ apiKey: this.apiKey, baseURL: this.baseURL });
        // For now, we'll keep it as a placeholder that doesn't actually initialize.
        this.openai = null;
        if (this.apiKey &&
            this.apiKey !== 'YOUR_API_KEY_PLACEHOLDER' &&
            this.apiKey.length >= 10) {
            console.log(`RealLLMService initialized for model ${this.defaultModelName} at ${this.baseURL}.`);
        }
        else {
            console.warn(`RealLLMService initialized with a placeholder API key for model ${this.defaultModelName}. API calls will be STUBBED.`);
        }
    }
    // Helper to construct appropriate messages for different tasks
    _constructMessages(structuredPrompt, taskTypeOverride) {
        // Task type from the prompt itself, or an override (e.g. for agent-specific tasks)
        const task = taskTypeOverride || structuredPrompt.task;
        let systemMessage = `You are an AI assistant. Perform the task: ${structuredPrompt.task}.`;
        let userMessageContent = `Data: ${JSON.stringify(structuredPrompt.data)}`;
        // Customize system/user messages based on task for better real LLM performance
        switch (structuredPrompt.task) {
            case 'categorize_email':
                const catData = structuredPrompt.data;
                systemMessage = `Categorize the following email into one of: 'Urgent', 'ActionRequired', 'FYI', 'Spam', 'MeetingInvite', 'Other'. Return ONLY valid JSON: {"category": "CATEGORY_NAME", "confidence": 0.X}`;
                userMessageContent = `Subject: "${catData.subject}"\nBody Snippet: "${catData.bodySnippet}"`;
                break;
            case 'summarize_email':
                const sumData = structuredPrompt.data;
                systemMessage =
                    'Summarize the following email concisely in 1-2 sentences. Return only the summary text.';
                userMessageContent = `Subject: "${sumData.subject}"\nBody Snippet: "${sumData.bodySnippet}"`;
                break;
            case 'suggest_reply_email':
                const repData = structuredPrompt.data;
                systemMessage = `Suggest a brief, polite, professional reply for this email. If no reply is needed (e.g., Spam, some FYI), return "No reply needed.". Category: ${repData.category}.`;
                userMessageContent = `Subject: "${repData.subject}"\nSummary: "${repData.summary}"\n${repData.actionItems && repData.actionItems.length > 0 ? `Identified Action Items: "${repData.actionItems.join('; ')}"` : ''}`;
                break;
            case 'extract_actions_email':
                const actData = structuredPrompt.data;
                systemMessage = `Extract distinct action items from this email body. Return JSON: {"actionItems": ["Action 1", ...]}. If none, return {"actionItems": []}.`;
                userMessageContent = `Email Body: "${actData.emailBody}"`;
                break;
            // Add more cases for other LLMTaskTypes to customize prompts
            case 'extract_document_snippets':
                const snipData = structuredPrompt.data;
                systemMessage = `Extract up to 3 relevant snippets (each ~${snipData.snippetLength || 150} chars) for the query from the document. Return JSON: {"snippets": ["...", ...]}. If none, return {"snippets": []}.`;
                userMessageContent = `Query: "${snipData.query}"\nDocument Title: "${snipData.documentTitle}"\nDocument Text: "${snipData.documentText}"`;
                break;
            case 'summarize_document_snippets':
                const docSumData = structuredPrompt.data;
                systemMessage = `Summarize the provided snippets based on the query. Target length: ${docSumData.targetLength || 'medium'}. Return only the summary.`;
                userMessageContent = `Query: "${docSumData.query}"\nDocument Title: "${docSumData.documentTitle}"\nSnippets:\n${(docSumData.snippets || []).map((s) => `- ${s}`).join('\n')}`;
                break;
            case 'summarize_overall_answer':
                const overallData = structuredPrompt.data;
                systemMessage = `Combine these individual summaries into one concise overall answer to the user's query. Return only the combined summary.`;
                userMessageContent = `User's Query: "${overallData.query}"\nIndividual Summaries:\n${overallData.individualSummaries.map((s) => `From "${s.title}": ${s.summary}`).join('\n---\n')}`;
                break;
            case 'classify_guidance_query':
                const gqClassData = structuredPrompt.data;
                systemMessage = `Classify the user query into one of: 'answer_question', 'find_tutorial', 'guide_workflow', 'general_explanation'. Return JSON: {"guidanceType": "TYPE"}.`;
                userMessageContent = `User Query: "${gqClassData.query}"`;
                break;
            case 'answer_from_text':
                const ansTextData = structuredPrompt.data;
                systemMessage = `Using ONLY the provided text, answer the question. Return only the direct answer.`;
                userMessageContent = `Question: '${ansTextData.query}'\nProvided text from "${ansTextData.articleTitle || 'document'}": '${ansTextData.textContent}'`;
                break;
            case 'extract_steps_from_text':
                const stepsTextData = structuredPrompt.data;
                systemMessage = `Extract key steps for the query from the tutorial text. Return JSON: {"steps": [{"title":"Step Title", "description":"Step desc"}, ...]}. If none, return {"steps": []}.`;
                userMessageContent = `Query: '${stepsTextData.query}'\nTutorial Text from "${stepsTextData.articleTitle || 'document'}": '${stepsTextData.textContent}'`;
                break;
            case 'summarize_for_explanation':
                const explData = structuredPrompt.data;
                systemMessage = `Provide a concise explanation for the query based on the text. Return only the explanation.`;
                userMessageContent = `Query: '${explData.query}'\nText from "${explData.articleTitle || 'document'}": '${explData.textContent}'`;
                break;
            case 'generate_followup_suggestions':
                const sugData = structuredPrompt.data;
                systemMessage = `Given the user query and shown guidance, suggest two distinct, related topics or advanced features. Return JSON: {"suggestions": ["Sugg 1", "Sugg 2"]}. If none, return {"suggestions": []}.`;
                userMessageContent = `User Query: '${sugData.query}'\nGuidance Shown (Title): '${sugData.articleTitle || 'N/A'}'`;
                break;
            case 'parse_search_query':
                const parseData = structuredPrompt.data;
                systemMessage = `You are an expert NLU (Natural Language Understanding) parser for a search engine. Your task is to analyze a user's raw search query and convert it into a structured JSON object.

You must identify the following entities from the user's query:

1.  \`search_term\`: The core subject of the search. Remove filler words like "find me", "show me", "search for", etc. Keep the essential keywords.

2.  \`filters\`: An object containing structured filter criteria. You must extract the following filter types:

    *   \`doc_types\`: An array of document types mentioned. The valid types are: \`gdrive_pdf\`, \`gdrive_docx\`, \`gdrive_folder\`, \`gdrive_sheet\`, \`gdrive_slide\`, \`email_snippet\`, \`notion_summary\`, \`document_chunk\`. If a user says "g-drive doc", map it to \`gdrive_docx\`. If they say "pdf" without "gdrive", map to \`document_chunk\`.

    *   \`date_after\` & \`date_before\`: A date range. Today's date is ${parseData.currentDate}. If the user says "last month", calculate the first and last day of the previous month. If they say "this week", calculate the past Monday and upcoming Sunday. If the user says "yesterday", calculate the start and end of the previous day. Always return the date as a full \`YYYY-MM-DD\` string.

    *   \`date_field_to_filter\`: The date field to filter on. Valid fields are \`ingested_at\`, \`created_at_source\`, \`last_modified_source\`. Default to \`ingested_at\` if ambiguous.

    *   \`metadata_properties\`: Key-value pairs like "by <author>". Extract the key (e.g., "author") and the value.

You MUST respond with ONLY a valid JSON object. The JSON object must conform to this structure:
\`\`\`json
{
  "search_term": "string",
  "filters": {
    "doc_types": ["string", ...],
    "date_after": "YYYY-MM-DD",
    "date_before": "YYYY-MM-DD",
    "date_field_to_filter": "string",
    "metadata_properties": { "key": "value", ... }
  }
}
\`\`\`
If a filter is not present, omit its key. If no filters are found, \`filters\` should be an empty object.`;
                userMessageContent = `User Query: "${parseData.rawQuery}"`;
                break;
            default:
                systemMessage = `You are an AI assistant performing task: ${structuredPrompt.task}. Respond appropriately based on the data.`;
                userMessageContent = `Data: ${JSON.stringify(structuredPrompt.data)}`;
                break;
        }
        return [
            { role: 'system', content: systemMessage },
            { role: 'user', content: userMessageContent },
        ];
    }
    async generate(structuredPrompt, modelNameToUse, options // Added isJsonOutput
    ) {
        const targetModel = modelNameToUse || this.defaultModelName;
        const taskType = structuredPrompt.data?.system_prompt // Heuristic for NLU agent tasks
            ? structuredPrompt.task || 'custom_agent_task'
            : structuredPrompt.task;
        // If API key is a placeholder, immediately fallback to mock to prevent actual call attempts.
        if (!this.apiKey ||
            this.apiKey === 'YOUR_API_KEY_PLACEHOLDER' ||
            this.apiKey.length < 10) {
            console.warn(`[RealLLMService] API Key is a placeholder for model ${targetModel}. Falling back to MockLLMService for task: ${taskType}.`);
            const mockService = new MockLLMService();
            return mockService.generate(structuredPrompt, targetModel, options);
        }
        // This is where the actual 'openai' client would be used.
        // Since 'this.openai' is null in this sandboxed environment, the following block is conceptual.
        if (!this.openai) {
            console.error('[RealLLMService] OpenAI client not initialized. THIS SHOULD NOT HAPPEN IN A REAL APP if API key is valid.');
            console.log('[RealLLMService] STUBBING API call and returning mock response due to uninitialized client.');
            // Fallback to MockLLMService if openai client isn't initialized (e.g. in sandbox)
            const mockService = new MockLLMService();
            const mockResponse = await mockService.generate(structuredPrompt, targetModel, options);
            return {
                ...mockResponse,
                error: mockResponse.error
                    ? mockResponse.error + ' (RealLLM Stub)'
                    : 'RealLLM Stub: OpenAI client not initialized.',
                success: mockResponse.success, // Can be true if mock is successful
            };
        }
        const messages = this._constructMessages(structuredPrompt, taskType);
        let retries = 0;
        console.log(`[RealLLMService] Attempting task "${taskType}" with model "${targetModel}". Attempt ${retries + 1}/${MAX_RETRIES}.`);
        // --- CONCEPTUAL ACTUAL OPENAI SDK CODE ---
        // This block simulates how the real code would look.
        try {
            // const openai = this.openai as OpenAI; // Type assertion for conceptual use
            console.log(`[RealLLMService] Preparing API call to model: ${targetModel}. Messages:`, JSON.stringify(messages, null, 2).substring(0, 500) + '...');
            const responseFormat = options?.isJsonOutput
                ? { type: 'json_object' }
                : undefined;
            if (responseFormat) {
                console.log(`[RealLLMService] Requesting JSON output mode.`);
            }
            // CONCEPTUAL: const chatCompletion = await openai.chat.completions.create({
            //   messages: messages,
            //   model: targetModel,
            //   temperature: options?.temperature ?? (responseFormat ? 0.2 : 0.7),
            //   max_tokens: options?.maxTokens ?? (responseFormat ? 1024 : 400),
            //   ...(responseFormat ? { response_format: responseFormat } : {}),
            //   // timeout: 30000, // Example: 30-second timeout
            // });
            // SIMULATING A SUCCESSFUL RESPONSE FOR THE SAKE OF STRUCTURE
            // IN A REAL SCENARIO, THIS WOULD BE THE ACTUAL LLM RESPONSE
            let simulatedApiContentObject = {
                comment: `This is a simulated successful LLM JSON response for task ${taskType}`,
                data_from_prompt: structuredPrompt.data, // Include original data for reference
            };
            // Task-specific simulated content
            switch (taskType) {
                case 'custom_analytical_analysis':
                    simulatedApiContentObject = {
                        ...simulatedApiContentObject,
                        identifiedEntities: [
                            'sim_entity_analytical_1',
                            'sim_entity_analytical_2',
                        ],
                        explicitTasks: ['sim_task_analytical'],
                        logicalConsistency: {
                            isConsistent: true,
                            reason: 'Simulated by RealLLMService for AnalyticalAgent',
                        },
                        problemType: 'simulated_analytical_problem',
                    };
                    break;
                case 'custom_creative_analysis':
                    simulatedApiContentObject = {
                        ...simulatedApiContentObject,
                        alternativeGoals: ['sim_alt_goal_creative_1'],
                        novelSolutionsSuggested: ['sim_novel_solution_creative'],
                        unstatedAssumptions: ['sim_assumption_creative'],
                        potentialEnhancements: ['sim_enhancement_creative'],
                        ambiguityFlags: [
                            {
                                term: 'sim_ambiguous_term_creative',
                                reason: 'sim_reason_creative',
                            },
                        ],
                    };
                    break;
                case 'custom_practical_analysis':
                    simulatedApiContentObject = {
                        ...simulatedApiContentObject,
                        contextualFactors: ['sim_context_practical_1'],
                        feasibilityAssessment: {
                            rating: 'Medium',
                            reason: 'Simulated by RealLLMService for PracticalAgent',
                            dependencies: ['sim_dependency_practical'],
                        },
                        efficiencyTips: ['sim_tip_practical'],
                        resourceImplications: {
                            timeEstimate: 'Moderate',
                            toolsNeeded: ['sim_tool_practical'],
                        },
                        commonSenseValidation: {
                            isValid: true,
                            reason: 'Simulated by RealLLMService for PracticalAgent',
                        },
                    };
                    break;
                case 'custom_lead_agent_synthesis': // New case for NLULeadAgent's synthesis task
                    simulatedApiContentObject = {
                        ...simulatedApiContentObject,
                        primaryGoal: 'Simulated: Schedule meeting about Project Alpha',
                        primaryGoalConfidence: 0.85,
                        identifiedTasks: [
                            'Check calendar for User A',
                            'Find common availability with User B',
                            'Send meeting invite',
                        ],
                        extractedParameters: {
                            project: 'Project Alpha',
                            attendees: ['User A', 'User B'],
                            reason_for_meeting: 'Discuss Q4 roadmap',
                        },
                        suggestedNextAction: {
                            actionType: 'invoke_skill',
                            skillId: 'CalendarSkill',
                            reason: 'High confidence goal to schedule a meeting, analytical tasks are clear, practical assessment is positive (simulated).',
                            directActionDetails: null, // Or provide if actionType was perform_direct_action
                            clarificationQuestion: null, // Or provide if actionType was clarify_query
                        },
                    };
                    break;
                default: // Generic fallback for other tasks (e.g. original LLMTaskTypes not handled above)
                    simulatedApiContentObject = {
                        ...simulatedApiContentObject,
                        genericField: 'Generic simulated content for other tasks (e.g., email categorization)',
                    };
                    break;
            }
            const simulatedApiContent = JSON.stringify(simulatedApiContentObject);
            // Simulate token usage based on prompt and content length for more realism
            const promptTokens = Math.ceil(JSON.stringify(messages).length / 4); // Rough estimate
            const completionTokens = Math.ceil(simulatedApiContent.length / 4); // Rough estimate
            const simulatedUsage = {
                promptTokens,
                completionTokens,
                totalTokens: promptTokens + completionTokens,
            };
            // const content = chatCompletion.choices[0]?.message?.content;
            // const usage = chatCompletion.usage; // Adapt based on actual SDK structure
            // Remove this simulation block when using real SDK
            const content = simulatedApiContent;
            const usage = simulatedUsage;
            if (content) {
                console.log(`[RealLLMService] Task "${taskType}" successful for model "${targetModel}".`);
                return {
                    success: true,
                    content: content,
                    usage: usage
                        ? {
                            promptTokens: usage.promptTokens,
                            completionTokens: usage.completionTokens,
                            totalTokens: usage.totalTokens,
                        }
                        : undefined,
                };
            }
            else {
                console.error(`[RealLLMService] Task "${taskType}" for model "${targetModel}" succeeded but content is missing.`);
                return {
                    success: false,
                    error: 'API call succeeded but content is missing.',
                };
            }
        }
        catch (error) {
            console.error(`[RealLLMService] Error during API call for task "${taskType}", model "${targetModel}":`, error.message);
            // Conceptual retry logic
            if (error.status === 429 ||
                error.code === 'rate_limit_exceeded' ||
                error.code === 'insufficient_quota') {
                // Example error codes
                if (retries < MAX_RETRIES) {
                    retries++;
                    const delay = INITIAL_RETRY_DELAY_MS * Math.pow(2, retries - 1);
                    console.log(`[RealLLMService] Rate limit / Quota error. Retrying attempt ${retries + 1}/${MAX_RETRIES} in ${delay}ms...`);
                    await new Promise((resolve) => setTimeout(resolve, delay));
                    // In a real recursive/loop retry, you'd call this.generate or the core API logic again.
                    // For this structural example, we'll just return the error after first true attempt.
                    return {
                        success: false,
                        error: `API Error (after ${retries} retries): ${error.message} (Retryable error, but retries not fully implemented in stub)`,
                    };
                }
                return {
                    success: false,
                    error: `API Error (Max retries reached for retryable error): ${error.message}`,
                };
            }
            // Non-retryable error
            return {
                success: false,
                error: `API Error: ${error.message || 'Unknown API error'}`,
            };
        }
        // --- END CONCEPTUAL ACTUAL OPENAI SDK CODE ---
    }
}
exports.RealLLMService = RealLLMService;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoibGxtVXRpbHMuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJsbG1VdGlscy50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiO0FBQUEsd0RBQXdEOzs7QUFnSXhELE1BQWEsY0FBYztJQUNsQixLQUFLLENBQUMsUUFBUSxDQUNuQixnQkFBcUMsRUFDckMsS0FBYSxFQUNiLE9BQXNEO1FBRXRELE9BQU8sQ0FBQyxHQUFHLENBQ1QsbUNBQW1DLGdCQUFnQixDQUFDLElBQUksZ0JBQWdCLEtBQUssaUJBQWlCLE1BQU0sQ0FBQyxJQUFJLENBQUMsZ0JBQWdCLENBQUMsSUFBSSxJQUFJLEVBQUUsQ0FBQyxDQUFDLElBQUksQ0FBQyxJQUFJLENBQUMsRUFBRSxDQUNwSixDQUFDO1FBQ0YsTUFBTSxJQUFJLE9BQU8sQ0FBQyxDQUFDLE9BQU8sRUFBRSxFQUFFLENBQzVCLFVBQVUsQ0FBQyxPQUFPLEVBQUUsSUFBSSxDQUFDLE1BQU0sRUFBRSxHQUFHLEdBQUcsR0FBRyxFQUFFLENBQUMsQ0FDOUMsQ0FBQztRQUVGLElBQUksQ0FBQztZQUNILElBQUksT0FBZSxDQUFDO1lBQ3BCLFFBQVEsZ0JBQWdCLENBQUMsSUFBSSxFQUFFLENBQUM7Z0JBQzlCLEtBQUssa0JBQWtCLENBQUMsQ0FBQyxDQUFDO29CQUN4QixNQUFNLElBQUksR0FBRyxnQkFBZ0IsQ0FBQyxJQUErQixDQUFDO29CQUM5RCxNQUFNLFlBQVksR0FBRyxJQUFJLENBQUMsT0FBTyxDQUFDLFdBQVcsRUFBRSxDQUFDO29CQUNoRCxNQUFNLGdCQUFnQixHQUFHLElBQUksQ0FBQyxXQUFXLENBQUMsV0FBVyxFQUFFLENBQUM7b0JBQ3hELE1BQU0sVUFBVSxHQUFHLEdBQUcsWUFBWSxJQUFJLGdCQUFnQixFQUFFLENBQUM7b0JBQ3pELElBQUksUUFBUSxHQUFXLE9BQU8sQ0FBQyxDQUFDLHVDQUF1QztvQkFDdkUsSUFBSSxVQUFVLEdBQVcsVUFBVSxDQUNqQyxDQUFDLElBQUksQ0FBQyxNQUFNLEVBQUUs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TSxJQUFJLE9BQU8sQ0FBQyxDQUFDLE9BQU8sRUFBRSxFQUFFLENBQUMsVUFBVSxDQUFDLE9BQU8sRUFBRSxLQUFLLENBQUMsQ0FBQyxDQUFDO29CQUMzRCx3RkFBd0Y7b0JBQ3hGLHFGQUFxRjtvQkFDckYsT0FBTzt3QkFDTCxPQUFPLEVBQUUsS0FBSzt3QkFDZCxLQUFLLEVBQUUsb0JBQW9CLE9BQU8sY0FBYyxLQUFLLENBQUMsT0FBTywrREFBK0Q7cUJBQzdILENBQUM7Z0JBQ0osQ0FBQztnQkFDRCxPQUFPO29CQUNMLE9BQU8sRUFBRSxLQUFLO29CQUNkLEtBQUssRUFBRSx3REFBd0QsS0FBSyxDQUFDLE9BQU8sRUFBRTtpQkFDL0UsQ0FBQztZQUNKLENBQUM7WUFDRCxzQkFBc0I7WUFDdEIsT0FBTztnQkFDTCxPQUFPLEVBQUUsS0FBSztnQkFDZCxLQUFLLEVBQUUsY0FBYyxLQUFLLENBQUMsT0FBTyxJQUFJLG1CQUFtQixFQUFFO2FBQzVELENBQUM7UUFDSixDQUFDO1FBQ0QsZ0RBQWdEO0lBQ2xELENBQUM7Q0FDRjtBQTlhRCx3Q0E4YUMiLCJzb3VyY2VzQ29udGVudCI6WyIvLyBTaGFyZWQgTExNIHV0aWxpdGllcywgdHlwZXMsIGFuZCBtb2NrIGltcGxlbWVudGF0aW9uc1xuXG4vLyBSZS1leHBvcnQgRW1haWxDYXRlZ29yeSBpZiBuZWVkZWQgYnkgc2tpbGxzIGRpcmVjdGx5LCB0aG91Z2ggaXQncyBiZXR0ZXIgaWYgc2tpbGxzIHVzZSB0aGVpciBvd24gc3BlY2lmaWMgdHlwZXMgb3IgZ2VuZXJpYyBzdHJpbmdzIGZvciBjYXRlZ29yaWVzIHBhc3NlZCB0byBMTE0uXG4vLyBGb3Igbm93LCB3ZSdsbCBhc3N1bWUgc2tpbGxzIHRoYXQgbmVlZCBFbWFpbENhdGVnb3J5IHdpbGwgZGVmaW5lL2ltcG9ydCBpdCB0aGVtc2VsdmVzIG9yIHRoYXQgdGhlIHN0cmluZyB0eXBlIGZvciBjYXRlZ29yeSBpbiBFbWFpbFJlcGx5U3VnZ2VzdGlvbkRhdGEgaXMgc3VmZmljaWVudC5cbi8vIGltcG9ydCB7IEVtYWlsQ2F0ZWdvcnkgfSBmcm9tICcuLi9za2lsbHMvZW1haWxUcmlhZ2VTa2lsbCc7XG5cbmV4cG9ydCB0eXBlIExMTVRhc2tUeXBlID1cbiAgfCAnY2F0ZWdvcml6ZV9lbWFpbCdcbiAgfCAnc3VtbWFyaXplX2VtYWlsJ1xuICB8ICdzdWdnZXN0X3JlcGx5X2VtYWlsJ1xuICB8ICdleHRyYWN0X2FjdGlvbnNfZW1haWwnXG4gIHwgJ2NsYXNzaWZ5X2d1aWRhbmNlX3F1ZXJ5J1xuICB8ICdhbnN3ZXJfZnJvbV90ZXh0J1xuICB8ICdleHRyYWN0X3N0ZXBzX2Zyb21fdGV4dCdcbiAgfCAnc3VtbWFyaXplX2Zvcl9leHBsYW5hdGlvbidcbiAgfCAnZ2VuZXJhdGVfZm9sbG93dXBfc3VnZ2VzdGlvbnMnXG4gIHwgJ2V4dHJhY3RfZG9jdW1lbnRfc25pcHBldHMnXG4gIHwgJ2N1c3RvbV9sZWFkX2FnZW50X3N5bnRoZXNpcydcbiAgfCAnc3VtbWFyaXplX2RvY3VtZW50X3NuaXBwZXRzJ1xuICB8ICdzdW1tYXJpemVfb3ZlcmFsbF9hbnN3ZXInXG4gIHwgJ3BhcnNlX3NlYXJjaF9xdWVyeSdcbiAgfCAnY3VzdG9tX2FuYWx5dGljYWxfYW5hbHlzaXMnXG4gIHwgJ2N1c3RvbV9jcmVhdGl2ZV9hbmFseXNpcydcbiAgfCAnY3VzdG9tX3ByYWN0aWNhbF9hbmFseXNpcydcbiAgfCAnY3VzdG9tX3N5bnRoZXNpcydcbiAgfCAnY3VzdG9tX2FkdmFuY2VkX3Jlc2VhcmNoJ1xuICB8ICdjdXN0b21fc29jaWFsX21lZGlhJ1xuICB8ICdjdXN0b21fY29udGVudF9jcmVhdGlvbidcbiAgfCAnY3VzdG9tX3BlcnNvbmFsaXplZF9zaG9wcGluZydcbiAgfCAnY3VzdG9tX2xlZ2FsX2RvY3VtZW50X2FuYWx5c2lzJ1xuICB8ICdjdXN0b21fcmVjcnVpdG1lbnRfcmVjb21tZW5kYXRpb24nXG4gIHwgJ2N1c3RvbV92aWJlX2hhY2tpbmcnO1xuXG4vLyAtLS0gRGF0YSBQYXlsb2FkcyBmb3Igc3BlY2lmaWMgdGFza3MgLS0tXG5leHBvcnQgaW50ZXJmYWNlIEVtYWlsQ2F0ZWdvcml6YXRpb25EYXRhIHtcbiAgc3ViamVjdDogc3RyaW5nO1xuICBib2R5U25pcHBldDogc3RyaW5nO1xufVxuZXhwb3J0IGludGVyZmFjZSBTZWFyY2hRdWVyeVBhcnNpbmdEYXRhIHtcbiAgcmF3UXVlcnk6IHN0cmluZztcbiAgY3VycmVudERhdGU6IHN0cmluZztcbn0gLy8gQWRkZWQgZm9yIHRoZSBuZXcgTkxVIGZpbHRlciBza2lsbFxuZXhwb3J0IGludGVyZmFjZSBFbWFpbFN1bW1hcml6YXRpb25EYXRhIHtcbiAgc3ViamVjdDogc3RyaW5nO1xuICBib2R5U25pcHBldDogc3RyaW5nO1xufVxuZXhwb3J0IGludGVyZmFjZSBFbWFpbFJlcGx5U3VnZ2VzdGlvbkRhdGEge1xuICBjYXRlZ29yeTogc3RyaW5nOyAvLyBDb3VsZCBiZSBtb3JlIHNwZWNpZmljIGxpa2UgRW1haWxDYXRlZ29yeSwgYnV0IHN0cmluZyBpcyBmaW5lIGZvciBtb2NrXG4gIHN1YmplY3Q6IHN0cmluZztcbiAgc3VtbWFyeTogc3RyaW5nO1xuICBhY3Rpb25JdGVtcz86IHN0cmluZ1tdO1xufVxuZXhwb3J0IGludGVyZmFjZSBFbWFpbEFjdGlvbkV4dHJhY3Rpb25EYXRhIHtcbiAgZW1haWxCb2R5OiBzdHJpbmc7XG59XG5cbmV4cG9ydCBpbnRlcmZhY2UgR3VpZGFuY2VRdWVyeUNsYXNzaWZpY2F0aW9uRGF0YSB7XG4gIHF1ZXJ5OiBzdHJpbmc7XG59XG5leHBvcnQgaW50ZXJmYWNlIEFuc3dlckZyb21UZXh0RGF0YSB7XG4gIHF1ZXJ5OiBzdHJpbmc7XG4gIHRleHRDb250ZW50OiBzdHJpbmc7XG4gIGFydGljbGVUaXRsZT86IHN0cmluZztcbn1cbmV4cG9ydCBpbnRlcmZhY2UgU3RlcHNGcm9tVGV4dERhdGEge1xuICBxdWVyeTogc3RyaW5nO1xuICB0ZXh0Q29udGVudDogc3RyaW5nO1xuICBhcnRpY2xlVGl0bGU/OiBzdHJpbmc7XG59XG5leHBvcnQgaW50ZXJmYWNlIEV4cGxhbmF0aW9uRGF0YSB7XG4gIHF1ZXJ5OiBzdHJpbmc7XG4gIHRleHRDb250ZW50OiBzdHJpbmc7XG4gIGFydGljbGVUaXRsZT86IHN0cmluZztcbn1cbmV4cG9ydCBpbnRlcmZhY2UgRm9sbG93dXBTdWdnZXN0aW9uRGF0YSB7XG4gIHF1ZXJ5OiBzdHJpbmc7XG4gIGFydGljbGVUaXRsZT86IHN0cmluZztcbn1cblxuZXhwb3J0IGludGVyZmFjZSBEb2N1bWVudFNuaXBwZXREYXRhIHtcbiAgcXVlcnk6IHN0cmluZztcbiAgZG9jdW1lbnRUaXRsZTogc3RyaW5nO1xuICBkb2N1bWVudFRleHQ6IHN0cmluZztcbiAgc25pcHBldExlbmd0aD86IG51bWJlcjtcbn1cbmV4cG9ydCBpbnRlcmZhY2UgRG9jdW1lbnRTdW1tYXJ5RGF0YSB7XG4gIHF1ZXJ5OiBzdHJpbmc7XG4gIGRvY3VtZW50VGl0bGU6IHN0cmluZztcbiAgc25pcHBldHM/OiBzdHJpbmdbXTtcbiAgZG9jdW1lbnRUZXh0Pzogc3RyaW5nO1xuICB0YXJnZXRMZW5ndGg/OiBzdHJpbmc7XG59XG5leHBvcnQgaW50ZXJmYWNlIE92ZXJhbGxTdW1tYXJ5RGF0YSB7XG4gIHF1ZXJ5OiBzdHJpbmc7XG4gIGluZGl2aWR1YWxTdW1tYXJpZXM6IHtcbiAgICB0aXRsZT86IHN0cmluZyB8IHVuZGVmaW5lZDtcbiAgICBzdW1tYXJ5Pzogc3RyaW5nIHwgdW5kZWZpbmVkO1xuICB9W107XG59XG5cbmV4cG9ydCBpbnRlcmZhY2UgU3RydWN0dXJlZExMTVByb21wdCB7XG4gIHRhc2s6IExMTVRhc2tUeXBlO1xuICBkYXRhOiBhbnk7XG59XG5cbmV4cG9ydCBpbnRlcmZhY2UgTExNU2VydmljZVJlc3BvbnNlIHtcbiAgc3VjY2VzczogYm9vbGVhbjtcbiAgY29udGVudD86IHN0cmluZztcbiAgZXJyb3I/OiBzdHJpbmc7XG4gIHVzYWdlPzoge1xuICAgIHByb21wdFRva2VuczogbnVtYmVyO1xuICAgIGNvbXBsZXRpb25Ub2tlbnM6IG51bWJlcjtcbiAgICB0b3RhbFRva2VuczogbnVtYmVyO1xuICB9O1xufVxuXG5leHBvcnQgaW50ZXJmYWNlIExMTVNlcnZpY2VJbnRlcmZhY2Uge1xuICBnZW5lcmF0ZShcbiAgICBwcm9tcHQ6IFN0cnVjdHVyZWRMTE1Qcm9tcHQsXG4gICAgbW9kZWw6IHN0cmluZyxcbiAgICBvcHRpb25zPzoge1xuICAgICAgdGVtcGVyYXR1cmU/OiBudW1iZXI7XG4gICAgICBtYXhUb2tlbnM/OiBudW1iZXI7XG4gICAgICBpc0pzb25PdXRwdXQ/OiBib29sZWFuO1xuICAgIH1cbiAgKTogUHJvbWlzZTxMTE1TZXJ2aWNlUmVzcG9uc2U+O1xufVxuXG5leHBvcnQgY2xhc3MgTW9ja0xMTVNlcnZpY2UgaW1wbGVtZW50cyBMTE1TZXJ2aWNlSW50ZXJmYWNlIHtcbiAgcHVibGljIGFzeW5jIGdlbmVyYXRlKFxuICAgIHN0cnVjdHVyZWRQcm9tcHQ6IFN0cnVjdHVyZWRMTE1Qcm9tcHQsXG4gICAgbW9kZWw6IHN0cmluZyxcbiAgICBvcHRpb25zPzogeyB0ZW1wZXJhdHVyZT86IG51bWJlcjsgbWF4VG9rZW5zPzogbnVtYmVyIH1cbiAgKTogUHJvbWlzZTxMTE1TZXJ2aWNlUmVzcG9uc2U+IHtcbiAgICBjb25zb2xlLmxvZyhcbiAgICAgIGBbTW9ja0xMTVNlcnZpY2VdIFJlY2VpdmVkIHRhc2sgXCIke3N0cnVjdHVyZWRQcm9tcHQudGFza31cIiBmb3IgbW9kZWwgXCIke21vZGVsfVwiLiBEYXRhIGtleXM6ICR7T2JqZWN0LmtleXMoc3RydWN0dXJlZFByb21wdC5kYXRhIHx8IHt9KS5qb2luKCcsICcpfWBcbiAgICApO1xuICAgIGF3YWl0IG5ldyBQcm9taXNlKChyZXNvbHZlKSA9PlxuICAgICAgc2V0VGltZW91dChyZXNvbHZlLCBNYXRoLnJhbmRvbSgpICogMTAwICsgNTApXG4gICAgKTtcblxuICAgIHRyeSB7XG4gICAgICBsZXQgY29udGVudDogc3RyaW5nO1xuICAgICAgc3dpdGNoIChzdHJ1Y3R1cmVkUHJvbXB0LnRhc2spIHtcbiAgICAgICAgY2FzZSAnY2F0ZWdvcml6ZV9lbWFpbCc6IHtcbiAgICAgICAgICBjb25zdCBkYXRhID0gc3RydWN0dXJlZFByb21wdC5kYXRhIGFzIEVtYWlsQ2F0ZWdvcml6YXRpb25EYXRhO1xuICAgICAgICAgIGNvbnN0IHN1YmplY3RMb3dlciA9IGRhdGEuc3ViamVjdC50b0xvd2VyQ2FzZSgpO1xuICAgICAgICAgIGNvbnN0IGJvZHlTbmlwcGV0TG93ZXIgPSBkYXRhLmJvZHlTbmlwcGV0LnRvTG93ZXJDYXNlKCk7XG4gICAgICAgICAgY29uc3QgdGV4dEZvckNhdCA9IGAke3N1YmplY3RMb3dlcn0gJHtib2R5U25pcHBldExvd2VyfWA7XG4gICAgICAgICAgbGV0IGNhdGVnb3J5OiBzdHJpbmcgPSAnT3RoZXInOyAvLyBBbGxvdyBzdHJpbmcgZm9yIGZsZXhpYmlsaXR5IGluIG1vY2tcbiAgICAgICAgICBsZXQgY29uZmlkZW5jZTogbnVtYmVyID0gcGFyc2VGbG9hdChcbiAgICAgICAgICAgIChNYXRoLnJhbmRvbSgpICogMC4zICsgMC4zKS50b0ZpeGVkKDIpXG4gICAgICAgICAgKTtcblxuICAgICAgICAgIGlmIChcbiAgICAgICAgICAgIHN1YmplY3RMb3dlci5pbmNsdWRlcygnd2luIGEgZnJlZScpIHx8XG4gICAgICAgICAgICB0ZXh0Rm9yQ2F0LmluY2x1ZGVzKCdsaW1pdGVkIHRpbWUgb2ZmZXInKSB8fFxuICAgICAgICAgICAgdGV4dEZvckNhdC5pbmNsdWRlcygnY2lhbGlzJykgfHxcbiAgICAgICAgICAgIHRleHRGb3JDYXQuaW5jbHVkZXMoJ3ZpYWdyYScpXG4gICAgICAgICAgKSB7XG4gICAgICAgICAgICBjYXRlZ29yeSA9ICdTcGFtJztcbiAgICAgICAgICAgIGNvbmZpZGVuY2UgPSAwLjk5O1xuICAgICAgICAgIH0gZWxzZSBpZiAoXG4gICAgICAgICAgICBzdWJqZWN0TG93ZXIuaW5jbHVkZXMoJ21lZXRpbmcgaW52aXRlJykgfHxcbiAgICAgICAgICAgIHN1YmplY3RMb3dlci5pbmNsdWRlcygnY2FsZW5kYXIgaW52aXRlJykgfHxcbiAgICAgICAgICAgIHN1YmplY3RMb3dlci5lbmRzV2l0aCgnLmljcycpIHx8XG4gICAgICAgICAgICBib2R5U25pcHBldExvd2VyLmluY2x1ZGVzKCdiZWdpbjp2Y2FsZW5kYXInKVxuICAgICAgICAgICkge1xuICAgICAgICAgICAgY2F0ZWdvcnkgPSAnTWVldGluZ0ludml0ZSc7XG4gICAgICAgICAgICBjb25maWRlbmNlID0gMC45NTtcbiAgICAgICAgICB9IGVsc2UgaWYgKFxuICAgICAgICAgICAgdGV4dEZvckNhdC5pbmNsdWRlcygndXJnZW50JykgfHxcbiAgICAgICAgICAgIHRleHRGb3JDYXQuaW5jbHVkZXMoJ2NyaXRpY2FsJykgfHxcbiAgICAgICAgICAgIHRleHRGb3JDYXQuaW5jbHVkZXMoJ291dGFnZScpIHx8XG4gICAgICAgICAgICB0ZXh0Rm9yQ2F0LmluY2x1ZGVzKCdhc2FwJylcbiAgICAgICAgICApIHtcbiAgICAgICAgICAgIGNhdGVnb3J5ID0gJ1VyZ2VudCc7XG4gICAgICAgICAgICBjb25maWRlbmNlID0gcGFyc2VGbG9hdCgoTWF0aC5yYW5kb20oKSAqIDAuMTUgKyAwLjgpLnRvRml4ZWQoMikpO1xuICAgICAgICAgIH0gZWxzZSBpZiAoXG4gICAgICAgICAgICB0ZXh0Rm9yQ2F0LmluY2x1ZGVzKCdhY3Rpb24gcmVxdWlyZWQnKSB8fFxuICAgICAgICAgICAgdGV4dEZvckNhdC5pbmNsdWRlcygncGxlYXNlIHJldmlldycpIHx8XG4gICAgICAgICAgICB0ZXh0Rm9yQ2F0LmluY2x1ZGVzKCd0YXNrIGZvciB5b3UnKSB8fFxuICAgICAgICAgICAgdGV4dEZvckNhdC5pbmNsdWRlcygnZGVhZGxpbmUnKVxuICAgICAgICAgICkge1xuICAgICAgICAgICAgY2F0ZWdvcnkgPSAnQWN0aW9uUmVxdWlyZWQnO1xuICAgICAgICAgICAgY29uZmlkZW5jZSA9IHBhcnNlRmxvYXQoKE1hdGgucmFuZG9tKCkgKiAwLjIgKyAwLjcpLnRvRml4ZWQoMikpO1xuICAgICAgICAgIH0gZWxzZSBpZiAoXG4gICAgICAgICAgICB0ZXh0Rm9yQ2F0LmluY2x1ZGVzKCdmeWknKSB8fFxuICAgICAgICAgICAgdGV4dEZvckNhdC5pbmNsdWRlcygnaGVhZHMgdXAnKSB8fFxuICAgICAgICAgICAgdGV4dEZvckNhdC5pbmNsdWRlcygndXBkYXRlJykgfHxcbiAgICAgICAgICAgIHN1YmplY3RMb3dlci5pbmNsdWRlcygnbmV3c2xldHRlcicpXG4gICAgICAgICAgKSB7XG4gICAgICAgICAgICBjYXRlZ29yeSA9ICdGWUknO1xuICAgICAgICAgICAgY29uZmlkZW5jZSA9IHBhcnNlRmxvYXQoKE1hdGgucmFuZG9tKCkgKiAwLjIgKyAwLjYpLnRvRml4ZWQoMikpO1xuICAgICAgICAgIH0gZWxzZSBpZiAoXG4gICAgICAgICAgICBkYXRhLmJvZHlTbmlwcGV0Lmxlbmd0aCA8IDUwICYmXG4gICAgICAgICAgICAhdGV4dEZvckNhdC5tYXRjaCgvKHVyZ2VudHxhY3Rpb258bWVldGluZ3xzcGFtKS9pKVxuICAgICAgICAgICkge1xuICAgICAgICAgICAgY2F0ZWdvcnkgPSBNYXRoLnJhbmRvbSgpIDwgMC41ID8gJ0ZZSScgOiAnT3RoZXInO1xuICAgICAgICAgICAgY29uZmlkZW5jZSA9IHBhcnNlRmxvYXQoKE1hdGgucmFuZG9tKCkgKiAwLjIgKyAwLjQ1KS50b0ZpeGVkKDIpKTtcbiAgICAgICAgICB9IGVsc2UgaWYgKE1hdGgucmFuZG9tKCkgPCAwLjA1KSB7XG4gICAgICAgICAgICAvLyBDaGFuY2Ugb2YgcGxhdXNpYmxlIG1pc2NhdGVnb3JpemF0aW9uXG4gICAgICAgICAgICBjb25zdCBjYXRzOiBzdHJpbmdbXSA9IFsnQWN0aW9uUmVxdWlyZWQnLCAnRllJJywgJ090aGVyJ107XG4gICAgICAgICAgICBjYXRlZ29yeSA9IGNhdHNbTWF0aC5mbG9vcihNYXRoLnJhbmRvbSgpICogY2F0cy5sZW5ndGgpXTtcbiAgICAgICAgICAgIGNvbmZpZGVuY2UgPSBwYXJzZUZsb2F0KChNYXRoLnJhbmRvbSgpICogMC4zICsgMC4zKS50b0ZpeGVkKDIpKTtcbiAgICAgICAgICB9XG4gICAgICAgICAgY29udGVudCA9IEpTT04uc3RyaW5naWZ5KHsgY2F0ZWdvcnksIGNvbmZpZGVuY2UgfSk7XG4gICAgICAgICAgYnJlYWs7XG4gICAgICAgIH1cbiAgICAgICAgY2FzZSAnc3VtbWFyaXplX2VtYWlsJzoge1xuICAgICAgICAgIGNvbnN0IGRhdGEgPSBzdHJ1Y3R1cmVkUHJvbXB0LmRhdGEgYXMgRW1haWxTdW1tYXJpemF0aW9uRGF0YTtcbiAgICAgICAgICBjb25zdCBzdWJqZWN0ID0gZGF0YS5zdWJqZWN0LnRyaW0oKTtcbiAgICAgICAgICBjb25zdCBib2R5U25pcHBldCA9IGRhdGEuYm9keVNuaXBwZXQudHJpbSgpO1xuICAgICAgICAgIGlmIChib2R5U25pcHBldC5sZW5ndGggPT09IDApXG4gICAgICAgICAgICBjb250ZW50ID0gYFRoZSBlbWFpbCB3aXRoIHN1YmplY3QgXCIke3N1YmplY3R9XCIgaGFzIG5vIGJvZHkgY29udGVudC5gO1xuICAgICAgICAgIGVsc2UgaWYgKGJvZHlTbmlwcGV0Lmxlbmd0aCA8IDcwICYmICFib2R5U25pcHBldC5pbmNsdWRlcygnLicpKVxuICAgICAgICAgICAgY29udGVudCA9IGBTdWJqZWN0OiBcIiR7c3ViamVjdH1cIi4gQ29udGVudDogXCIke2JvZHlTbmlwcGV0fVwiYDtcbiAgICAgICAgICBlbHNlIHtcbiAgICAgICAgICAgIGNvbnN0IGZpcnN0U2VudGVuY2UgPVxuICAgICAgICAgICAgICBib2R5U25pcHBldC5tYXRjaCgvW14uIT9dK1suIT9dKy9nKT8uWzBdPy50cmltKCkgfHxcbiAgICAgICAgICAgICAgYm9keVNuaXBwZXQuc3Vic3RyaW5nKDAsIDEwMCk7XG4gICAgICAgICAgICBjb250ZW50ID0gYFJlZ2FyZGluZyBcIiR7c3ViamVjdH1cIiwgdGhlIGVtYWlsIG1lbnRpb25zOiBcIiR7Zmlyc3RTZW50ZW5jZS5zdWJzdHJpbmcoMCwgMTAwKX0ke2ZpcnN0U2VudGVuY2UubGVuZ3RoID4gMTAwID8gJy4uLicgOiAnJ31cIi5gO1xuICAgICAgICAgIH1cbiAgICAgICAgICBpZiAoXG4gICAgICAgICAgICBzdWJqZWN0LnRvTG93ZXJDYXNlKCkuc3RhcnRzV2l0aCgncmU6JykgfHxcbiAgICAgICAgICAgIHN1YmplY3QudG9Mb3dlckNhc2UoKS5zdGFydHNXaXRoKCdmd2Q6JylcbiAgICAgICAgICApXG4gICAgICAgICAgICBjb250ZW50ID0gYFRoaXMgaXMgcGFydCBvZiBhIHRocmVhZCBvbiBcIiR7c3ViamVjdH1cIi4gJHtjb250ZW50fWA7XG4gICAgICAgICAgaWYgKE1hdGgucmFuZG9tKCkgPCAwLjMpXG4gICAgICAgICAgICBjb250ZW50ICs9ICcgRnVydGhlciBkZXRhaWxzIG1pZ2h0IGJlIGltcG9ydGFudC4nO1xuICAgICAgICAgIGJyZWFrO1xuICAgICAgICB9XG4gICAgICAgIGNhc2UgJ3N1Z2dlc3RfcmVwbHlfZW1haWwnOiB7XG4gICAgICAgICAgY29uc3QgZGF0YSA9IHN0cnVjdHVyZWRQcm9tcHQuZGF0YSBhcyBFbWFpbFJlcGx5U3VnZ2VzdGlvbkRhdGE7XG4gICAgICAgICAgaWYgKFxuICAgICAgICAgICAgZGF0YS5jYXRlZ29yeSA9PT0gJ1NwYW0nIHx8XG4gICAgICAgICAgICAoZGF0YS5jYXRlZ29yeSA9PT0gJ0ZZSScgJiYgTWF0aC5yYW5kb20oKSA8IDAuNylcbiAgICAgICAgICApIHtcbiAgICAgICAgICAgIC8vIE1vcmUgbGlrZWx5IG5vIHJlcGx5IGZvciBGWUlcbiAgICAgICAgICAgIGNvbnRlbnQgPSAnTm8gcmVwbHkgbmVlZGVkLic7XG4gICAgICAgICAgfSBlbHNlIGlmIChkYXRhLmNhdGVnb3J5ID09PSAnVXJnZW50Jykge1xuICAgICAgICAgICAgY29udGVudCA9XG4gICAgICAgICAgICAgICdBY2tub3dsZWRnZWQuIExvb2tpbmcgaW50byB0aGlzIHdpdGggaGlnaCBwcmlvcml0eSBhbmQgd2lsbCB1cGRhdGUgc2hvcnRseS4nO1xuICAgICAgICAgIH0gZWxzZSBpZiAoZGF0YS5jYXRlZ29yeSA9PT0gJ0FjdGlvblJlcXVpcmVkJykge1xuICAgICAgICAgICAgY29udGVudCA9XG4gICAgICAgICAgICAgIGRhdGEuYWN0aW9uSXRlbXMgJiYgZGF0YS5hY3Rpb25JdGVtcy5sZW5ndGggPiAwXG4gICAgICAgICAgICAgICAgPyBgVW5kZXJzdG9vZC4gSSB3aWxsIHN0YXJ0IHdpdGg6IFwiJHtkYXRhLmFjdGlvbkl0ZW1zWzBdfVwiLmBcbiAgICAgICAgICAgICAgICA6IFwiUmVjZWl2ZWQuIEknbGwgdGFrZSBjYXJlIG9mIHRoZSBuZWNlc3NhcnkgYWN0aW9ucy5cIjtcbiAgICAgICAgICB9IGVsc2UgaWYgKGRhdGEuY2F0ZWdvcnkgPT09ICdNZWV0aW5nSW52aXRlJykge1xuICAgICAgICAgICAgY29udGVudCA9XG4gICAgICAgICAgICAgIFwiVGhhbmtzIGZvciB0aGUgaW52aXRlISBJJ2xsIGNoZWNrIG15IGF2YWlsYWJpbGl0eSBhbmQgcmVzcG9uZCB2aWEgY2FsZW5kYXIuXCI7XG4gICAgICAgICAgfSBlbHNlIHtcbiAgICAgICAgICAgIGNvbnRlbnQgPSBgVGhhbmsgeW91IGZvciB5b3VyIGVtYWlsIHJlZ2FyZGluZyBcIiR7ZGF0YS5zdWJqZWN0fVwiLiBJIHdpbGwgcmV2aWV3IGl0LmA7XG4gICAgICAgICAgfVxuICAgICAgICAgIGJyZWFrO1xuICAgICAgICB9XG4gICAgICAgIGNhc2UgJ2V4dHJhY3RfYWN0aW9uc19lbWFpbCc6IHtcbiAgICAgICAgICBjb25zdCBkYXRhID0gc3RydWN0dXJlZFByb21wdC5kYXRhIGFzIEVtYWlsQWN0aW9uRXh0cmFjdGlvbkRhdGE7XG4gICAgICAgICAgY29uc3QgYm9keUxvd2VyID0gZGF0YS5lbWFpbEJvZHkudG9Mb3dlckNhc2UoKTtcbiAgICAgICAgICBjb25zdCBhY3Rpb25zOiBzdHJpbmdbXSA9IFtdO1xuICAgICAgICAgIGlmIChcbiAgICAgICAgICAgIGJvZHlMb3dlci5pbmNsdWRlcygncGxlYXNlIHNlbmQnKSB8fFxuICAgICAgICAgICAgYm9keUxvd2VyLmluY2x1ZGVzKCdjYW4geW91IGF0dGFjaCcpXG4gICAgICAgICAgKVxuICAgICAgICAgICAgYWN0aW9ucy5wdXNoKCdTZW5kL2F0dGFjaCByZXF1ZXN0ZWQgZG9jdW1lbnQuJyk7XG4gICAgICAgICAgaWYgKFxuICAgICAgICAgICAgYm9keUxvd2VyLmluY2x1ZGVzKCdzY2hlZHVsZSBhIG1lZXRpbmcnKSB8fFxuICAgICAgICAgICAgYm9keUxvd2VyLmluY2x1ZGVzKCdzZXQgdXAgYSBjYWxsJylcbiAgICAgICAgICApXG4gICAgICAgICAgICBhY3Rpb25zLnB1c2goJ1NjaGVkdWxlIGEgbWVldGluZy4nKTtcbiAgICAgICAgICBpZiAoXG4gICAgICAgICAgICBib2R5TG93ZXIuaW5jbHVkZXMoJ2NvbmZpcm0gYXZhaWxhYmlsaXR5JykgfHxcbiAgICAgICAgICAgIGJvZHlMb3dlci5pbmNsdWRlcygnYXJlIHlvdSBmcmVlJylcbiAgICAgICAgICApXG4gICAgICAgICAgICBhY3Rpb25zLnB1c2goJ0NvbmZpcm0gYXZhaWxhYmlsaXR5IGZvciBzb21ldGhpbmcuJyk7XG4gICAgICAgICAgaWYgKFxuICAgICAgICAgICAgYm9keUxvd2VyLmluY2x1ZGVzKCd5b3VyIHRob3VnaHRzIG9uJykgfHxcbiAgICAgICAgICAgIGJvZHlMb3dlci5pbmNsdWRlcygnZmVlZGJhY2sgb24nKVxuICAgICAgICAgIClcbiAgICAgICAgICAgIGFjdGlvbnMucHVzaCgnUHJvdmlkZSBmZWVkYmFjay90aG91Z2h0cy4nKTtcbiAgICAgICAgICBjb250ZW50ID0gSlNPTi5zdHJpbmdpZnkoeyBhY3Rpb25JdGVtczogYWN0aW9ucy5zbGljZSgwLCAyKSB9KTtcbiAgICAgICAgICBicmVhaztcbiAgICAgICAgfVxuICAgICAgICBjYXNlICdleHRyYWN0X2RvY3VtZW50X3NuaXBwZXRzJzoge1xuICAgICAgICAgIGNvbnN0IGRhdGEgPSBzdHJ1Y3R1cmVkUHJvbXB0LmRhdGEgYXMgRG9jdW1lbnRTbmlwcGV0RGF0YTtcbiAgICAgICAgICBjb250ZW50ID0gSlNPTi5zdHJpbmdpZnkoe1xuICAgICAgICAgICAgc25pcHBldHM6IFtcbiAgICAgICAgICAgICAgYE1vY2sgc25pcHBldCBmb3IgXCIke2RhdGEucXVlcnl9XCIgZnJvbSBcIiR7ZGF0YS5kb2N1bWVudFRpdGxlfVwiLmAsXG4gICAgICAgICAgICAgIGBBbm90aGVyIGRldGFpbCByZWdhcmRpbmcgXCIke2RhdGEucXVlcnl9XCIuYCxcbiAgICAgICAgICAgIF0sXG4gICAgICAgICAgfSk7XG4gICAgICAgICAgYnJlYWs7XG4gICAgICAgIH1cbiAgICAgICAgY2FzZSAnc3VtbWFyaXplX2RvY3VtZW50X3NuaXBwZXRzJzoge1xuICAgICAgICAgIGNvbnN0IGRhdGEgPSBzdHJ1Y3R1cmVkUHJvbXB0LmRhdGEgYXMgRG9jdW1lbnRTdW1tYXJ5RGF0YTtcbiAgICAgICAgICBjb250ZW50ID0gYFRoaXMgaXMgYSBtb2NrICR7ZGF0YS50YXJnZXRMZW5ndGggfHwgJ21lZGl1bSd9IHN1bW1hcnkgYWJvdXQgXCIke2RhdGEucXVlcnl9XCIgZnJvbSBcIiR7ZGF0YS5kb2N1bWVudFRpdGxlfVwiLmA7XG4gICAgICAgICAgYnJlYWs7XG4gICAgICAgIH1cbiAgICAgICAgY2FzZSAnc3VtbWFyaXplX292ZXJhbGxfYW5zd2VyJzoge1xuICAgICAgICAgIGNvbnN0IGRhdGEgPSBzdHJ1Y3R1cmVkUHJvbXB0LmRhdGEgYXMgT3ZlcmFsbFN1bW1hcnlEYXRhO1xuICAgICAgICAgIGNvbnRlbnQgPSBgT3ZlcmFsbCBtb2NrIHN1bW1hcnkgZm9yIFwiJHtkYXRhLnF1ZXJ5fVwiLCBjb21iaW5pbmcgJHtkYXRhLmluZGl2aWR1YWxTdW1tYXJpZXMubGVuZ3RofSBzb3VyY2VzLmA7XG4gICAgICAgICAgYnJlYWs7XG4gICAgICAgIH1cbiAgICAgICAgY2FzZSAnY2xhc3NpZnlfZ3VpZGFuY2VfcXVlcnknOiB7XG4gICAgICAgICAgY29uc3QgZGF0YSA9IHN0cnVjdHVyZWRQcm9tcHQuZGF0YSBhcyBHdWlkYW5jZVF1ZXJ5Q2xhc3NpZmljYXRpb25EYXRhO1xuICAgICAgICAgIGNvbnN0IHFMID0gZGF0YS5xdWVyeS50b0xvd2VyQ2FzZSgpO1xuICAgICAgICAgIGlmIChxTC5pbmNsdWRlcygnaG93IHRvJykgfHwgcUwuaW5jbHVkZXMoJ3N0ZXBzJykpXG4gICAgICAgICAgICBjb250ZW50ID0gSlNPTi5zdHJpbmdpZnkoeyBndWlkYW5jZVR5cGU6ICdmaW5kX3R1dG9yaWFsJyB9KTtcbiAgICAgICAgICBlbHNlIGlmIChxTC5pbmNsdWRlcygnd2hhdCBpcycpIHx8IHFMLmluY2x1ZGVzKCdleHBsYWluJykpXG4gICAgICAgICAgICBjb250ZW50ID0gSlNPTi5zdHJpbmdpZnkoeyBndWlkYW5jZVR5cGU6ICdnZW5lcmFsX2V4cGxhbmF0aW9uJyB9KTtcbiAgICAgICAgICBlbHNlIGlmIChxTC5pbmNsdWRlcygnZ3VpZGUnKSB8fCBxTC5pbmNsdWRlcygnd29ya2Zsb3cnKSlcbiAgICAgICAgICAgIGNvbnRlbnQgPSBKU09OLnN0cmluZ2lmeSh7IGd1aWRhbmNlVHlwZTogJ2d1aWRlX3dvcmtmbG93JyB9KTtcbiAgICAgICAgICBlbHNlIGNvbnRlbnQgPSBKU09OLnN0cmluZ2lmeSh7IGd1aWRhbmNlVHlwZTogJ2Fuc3dlcl9xdWVzdGlvbicgfSk7XG4gICAgICAgICAgYnJlYWs7XG4gICAgICAgIH1cbiAgICAgICAgY2FzZSAnYW5zd2VyX2Zyb21fdGV4dCc6IHtcbiAgICAgICAgICBjb25zdCBkYXRhID0gc3RydWN0dXJlZFByb21wdC5kYXRhIGFzIEFuc3dlckZyb21UZXh0RGF0YTtcbiAgICAgICAgICBjb250ZW50ID0gYE1vY2sgYW5zd2VyIGZvciBcIiR7ZGF0YS5xdWVyeX1cIiBmcm9tIFwiJHtkYXRhLmFydGljbGVUaXRsZSB8fCAndGhlIGRvY3VtZW50J31cIjogJHtkYXRhLnRleHRDb250ZW50LnN1YnN0cmluZygwLCA3MCl9Li4uYDtcbiAgICAgICAgICBicmVhaztcbiAgICAgICAgfVxuICAgICAgICBjYXNlICdleHRyYWN0X3N0ZXBzX2Zyb21fdGV4dCc6IHtcbiAgICAgICAgICBjb25zdCBkYXRhID0gc3RydWN0dXJlZFByb21wdC5kYXRhIGFzIFN0ZXBzRnJvbVRleHREYXRhO1xuICAgICAgICAgIGNvbnRlbnQgPSBKU09OLnN0cmluZ2lmeSh7XG4gICAgICAgICAgICBzdGVwczogW1xuICAgICAgICAgICAgICB7XG4gICAgICAgICAgICAgICAgdGl0bGU6ICdNb2NrIFN0ZXAgMSAoZnJvbSBMTE0pJyxcbiAgICAgICAgICAgICAgICBkZXNjcmlwdGlvbjogYERvIHRoaXMgZmlyc3QgZm9yICR7ZGF0YS5xdWVyeX1gLFxuICAgICAgICAgICAgICB9LFxuICAgICAgICAgICAgICB7IHRpdGxlOiAnTW9jayBTdGVwIDInLCBkZXNjcmlwdGlvbjogJ1RoZW4gZG8gdGhhdC4nIH0sXG4gICAgICAgICAgICBdLFxuICAgICAgICAgIH0pO1xuICAgICAgICAgIGJyZWFrO1xuICAgICAgICB9XG4gICAgICAgIGNhc2UgJ3N1bW1hcml6ZV9mb3JfZXhwbGFuYXRpb24nOiB7XG4gICAgICAgICAgY29uc3QgZGF0YSA9IHN0cnVjdHVyZWRQcm9tcHQuZGF0YSBhcyBFeHBsYW5hdGlvbkRhdGE7XG4gICAgICAgICAgY29udGVudCA9IGBNb2NrIGV4cGxhbmF0aW9uIG9mIFwiJHtkYXRhLnF1ZXJ5fVwiIGJhc2VkIG9uIFwiJHtkYXRhLmFydGljbGVUaXRsZX1cIi4gSXQgY292ZXJzLi4uYDtcbiAgICAgICAgICBicmVhaztcbiAgICAgICAgfVxuICAgICAgICBjYXNlICdnZW5lcmF0ZV9mb2xsb3d1cF9zdWdnZXN0aW9ucyc6IHtcbiAgICAgICAgICBjb25zdCBkYXRhID0gc3RydWN0dXJlZFByb21wdC5kYXRhIGFzIEZvbGxvd3VwU3VnZ2VzdGlvbkRhdGE7XG4gICAgICAgICAgY29udGVudCA9IEpTT04uc3RyaW5naWZ5KHtcbiAgICAgICAgICAgIHN1Z2dlc3Rpb25zOiBbXG4gICAgICAgICAgICAgIGBBZHZhbmNlZCAke2RhdGEuYXJ0aWNsZVRpdGxlIHx8IGRhdGEucXVlcnl9YCxcbiAgICAgICAgICAgICAgJ1JlbGF0ZWQgVG9waWMgQicsXG4gICAgICAgICAgICBdLFxuICAgICAgICAgIH0pO1xuICAgICAgICAgIGJyZWFrO1xuICAgICAgICB9XG4gICAgICAgIGNhc2UgJ2N1c3RvbV9hbmFseXRpY2FsX2FuYWx5c2lzJzoge1xuICAgICAgICAgIGNvbnRlbnQgPSBKU09OLnN0cmluZ2lmeSh7XG4gICAgICAgICAgICBpZGVudGlmaWVkRW50aXRpZXM6IFsncGl2b3QgdGFibGUnLCAnU3ByZWFkc2hlZXRBcHAnXSxcbiAgICAgICAgICAgIGV4cGxpY2l0VGFza3M6IFsnY3JlYXRlIHBpdm90IHRhYmxlJ10sXG4gICAgICAgICAgICBpbmZvcm1hdGlvbk5lZWRlZDogW10sXG4gICAgICAgICAgICBsb2dpY2FsQ29uc2lzdGVuY3k6IHsgaXNDb25zaXN0ZW50OiB0cnVlLCByZWFzb246ICcnIH0sXG4gICAgICAgICAgICBwcm9ibGVtVHlwZTogJ2hvd190bycsXG4gICAgICAgICAgfSk7XG4gICAgICAgICAgYnJlYWs7XG4gICAgICAgIH1cbiAgICAgICAgY2FzZSAnY3VzdG9tX2NyZWF0aXZlX2FuYWx5c2lzJzoge1xuICAgICAgICAgIGNvbnRlbnQgPSBKU09OLnN0cmluZ2lmeSh7XG4gICAgICAgICAgICBhbHRlcm5hdGl2ZUdvYWxzOiBbJ3VuZGVyc3RhbmQgZGF0YSBiZXR0ZXInLCAnY3JlYXRlIGEgY2hhcnQnXSxcbiAgICAgICAgICAgIG5vdmVsU29sdXRpb25zU3VnZ2VzdGVkOiBbJ3VzZSBhIHByZS1idWlsdCB0ZW1wbGF0ZSddLFxuICAgICAgICAgICAgdW5zdGF0ZWRBc3N1bXB0aW9uczogWyd1c2VyIGhhcyBkYXRhIHJlYWR5J10sXG4gICAgICAgICAgICBwb3RlbnRpYWxFbmhhbmNlbWVudHM6IFsnYWRkIGNvbmRpdGlvbmFsIGZvcm1hdHRpbmcnXSxcbiAgICAgICAgICAgIGFtYmlndWl0eUZsYWdzOiBbXSxcbiAgICAgICAgICB9KTtcbiAgICAgICAgICBicmVhaztcbiAgICAgICAgfVxuICAgICAgICBjYXNlICdjdXN0b21fcHJhY3RpY2FsX2FuYWx5c2lzJzoge1xuICAgICAgICAgIGNvbnRlbnQgPSBKU09OLnN0cmluZ2lmeSh7XG4gICAgICAgICAgICBjb250ZXh0dWFsRmFjdG9yczogW10sXG4gICAgICAgICAgICBmZWFzaWJpbGl0eUFzc2Vzc21lbnQ6IHtcbiAgICAgICAgICAgICAgcmF0aW5nOiAnSGlnaCcsXG4gICAgICAgICAgICAgIHJlYXNvbjogJycsXG4gICAgICAgICAgICAgIGRlcGVuZGVuY2llczogW10sXG4gICAgICAgICAgICB9LFxuICAgICAgICAgICAgZWZmaWNpZW5jeVRpcHM6IFtcInVzZSB0aGUgJ1JlY29tbWVuZGVkIFBpdm90VGFibGVzJyBmZWF0dXJlXCJdLFxuICAgICAgICAgICAgcmVzb3VyY2VJbXBsaWNhdGlvbnM6IHtcbiAgICAgICAgICAgICAgdGltZUVzdGltYXRlOiAnUXVpY2snLFxuICAgICAgICAgICAgICB0b29sc05lZWRlZDogWydTcHJlYWRzaGVldEFwcCddLFxuICAgICAgICAgICAgfSxcbiAgICAgICAgICAgIGNvbW1vblNlbnNlVmFsaWRhdGlvbjogeyBpc1ZhbGlkOiB0cnVlLCByZWFzb246ICcnIH0sXG4gICAgICAgICAgfSk7XG4gICAgICAgICAgYnJlYWs7XG4gICAgICAgIH1cbiAgICAgICAgY2FzZSAnY3VzdG9tX3N5bnRoZXNpcyc6IHtcbiAgICAgICAgICBjb250ZW50ID0gSlNPTi5zdHJpbmdpZnkoe1xuICAgICAgICAgICAgcHJpbWFyeUdvYWw6ICdjcmVhdGUgYSBwaXZvdCB0YWJsZScsXG4gICAgICAgICAgICBwcmltYXJ5R29hbENvbmZpZGVuY2U6IDAuOSxcbiAgICAgICAgICAgIGlkZW50aWZpZWRUYXNrczogWydjcmVhdGUgcGl2b3QgdGFibGUnXSxcbiAgICAgICAgICAgIGV4dHJhY3RlZFBhcmFtZXRlcnM6IHsgYXBwOiAnU3ByZWFkc2hlZXRBcHAnIH0sXG4gICAgICAgICAgICBzdWdnZXN0ZWROZXh0QWN0aW9uOiB7XG4gICAgICAgICAgICAgIGFjdGlvblR5cGU6ICdpbnZva2Vfc2tpbGwnLFxuICAgICAgICAgICAgICBza2lsbElkOiAnTGVhcm5pbmdBbmRHdWlkYW5jZVNraWxsJyxcbiAgICAgICAgICAgICAgcmVhc29uOiBcIlVzZXIgaXMgYXNraW5nIGEgJ2hvdy10bycgcXVlc3Rpb24uXCIsXG4gICAgICAgICAgICB9LFxuICAgICAgICAgIH0pO1xuICAgICAgICAgIGJyZWFrO1xuICAgICAgICB9XG4gICAgICAgIGNhc2UgJ2N1c3RvbV9hZHZhbmNlZF9yZXNlYXJjaCc6IHtcbiAgICAgICAgICBjb250ZW50ID0gSlNPTi5zdHJpbmdpZnkoe1xuICAgICAgICAgICAgcmVzZWFyY2hTdW1tYXJ5OiAnVGhpcyBpcyBhIG1vY2sgcmVzZWFyY2ggc3VtbWFyeS4nLFxuICAgICAgICAgICAga2V5RmluZGluZ3M6IFsnTW9jayBmaW5kaW5nIDEnLCAnTW9jayBmaW5kaW5nIDInXSxcbiAgICAgICAgICAgIHNvdXJjZXM6IFt7IHRpdGxlOiAnTW9jayBTb3VyY2UnLCB1cmw6ICdodHRwczovL2V4YW1wbGUuY29tJyB9XSxcbiAgICAgICAgICB9KTtcbiAgICAgICAgICBicmVhaztcbiAgICAgICAgfVxuICAgICAgICBjYXNlICdjdXN0b21fc29jaWFsX21lZGlhJzoge1xuICAgICAgICAgIGNvbnRlbnQgPSBKU09OLnN0cmluZ2lmeSh7XG4gICAgICAgICAgICBzY2hlZHVsZWRQb3N0czogW1xuICAgICAgICAgICAgICB7XG4gICAgICAgICAgICAgICAgcGxhdGZvcm06ICdUd2l0dGVyJyxcbiAgICAgICAgICAgICAgICBjb250ZW50OiAnVGhpcyBpcyBhIG1vY2sgdHdlZXQuJyxcbiAgICAgICAgICAgICAgICBzY2hlZHVsZWRUaW1lOiAnMjAyNS0wMS0wMVQxMjowMDowMFonLFxuICAgICAgICAgICAgICB9LFxuICAgICAgICAgICAgXSxcbiAgICAgICAgICAgIGVuZ2FnZW1lbnRTdW1tYXJ5OiAnVGhpcyBpcyBhIG1vY2sgZW5nYWdlbWVudCBzdW1tYXJ5LicsXG4gICAgICAgICAgfSk7XG4gICAgICAgICAgYnJlYWs7XG4gICAgICAgIH1cbiAgICAgICAgY2FzZSAnY3VzdG9tX2NvbnRlbnRfY3JlYXRpb24nOiB7XG4gICAgICAgICAgY29udGVudCA9IEpTT04uc3RyaW5naWZ5KHtcbiAgICAgICAgICAgIGdlbmVyYXRlZENvbnRlbnQ6ICdUaGlzIGlzIG1vY2sgZ2VuZXJhdGVkIGNvbnRlbnQuJyxcbiAgICAgICAgICAgIGNvbnRlbnRUeXBlOiAnYmxvZyBwb3N0JyxcbiAgICAgICAgICB9KTtcbiAgICAgICAgICBicmVhaztcbiAgICAgICAgfVxuICAgICAgICBjYXNlICdjdXN0b21fcGVyc29uYWxpemVkX3Nob3BwaW5nJzoge1xuICAgICAgICAgIGNvbnRlbnQgPSBKU09OLnN0cmluZ2lmeSh7XG4gICAgICAgICAgICBwcm9kdWN0UmVjb21tZW5kYXRpb25zOiBbXG4gICAgICAgICAgICAgIHtcbiAgICAgICAgICAgICAgICBwcm9kdWN0TmFtZTogJ01vY2sgTGFwdG9wJyxcbiAgICAgICAgICAgICAgICBwcmljZTogOTk5LFxuICAgICAgICAgICAgICAgIHVybDogJ2h0dHBzOi8vZXhhbXBsZS5jb20vbGFwdG9wJyxcbiAgICAgICAgICAgICAgICByZWFzb25pbmc6IFwiSXQncyBhIGdyZWF0IHZhbHVlIGZvciB0aGUgcHJpY2UuXCIsXG4gICAgICAgICAgICAgIH0sXG4gICAgICAgICAgICBdLFxuICAgICAgICAgIH0pO1xuICAgICAgICAgIGJyZWFrO1xuICAgICAgICB9XG4gICAgICAgIGNhc2UgJ2N1c3RvbV9sZWdhbF9kb2N1bWVudF9hbmFseXNpcyc6IHtcbiAgICAgICAgICBjb250ZW50ID0gSlNPTi5zdHJpbmdpZnkoe1xuICAgICAgICAgICAgcmlza0FuYWx5c2lzOiBbXG4gICAgICAgICAgICAgIHtcbiAgICAgICAgICAgICAgICBjbGF1c2U6ICdUaGlzIGlzIGEgbW9jayBjbGF1c2UuJyxcbiAgICAgICAgICAgICAgICByaXNrTGV2ZWw6ICdNZWRpdW0nLFxuICAgICAgICAgICAgICAgIGV4cGxhbmF0aW9uOiAnVGhpcyBpcyBhIG1vY2sgZXhwbGFuYXRpb24uJyxcbiAgICAgICAgICAgICAgfSxcbiAgICAgICAgICAgIF0sXG4gICAgICAgICAgICBzdW1tYXJ5OiAnVGhpcyBpcyBhIG1vY2sgc3VtbWFyeSBvZiB0aGUgbGVnYWwgZG9jdW1lbnQuJyxcbiAgICAgICAgICB9KTtcbiAgICAgICAgICBicmVhaztcbiAgICAgICAgfVxuICAgICAgICBjYXNlICdjdXN0b21fcmVjcnVpdG1lbnRfcmVjb21tZW5kYXRpb24nOiB7XG4gICAgICAgICAgY29udGVudCA9IEpTT04uc3RyaW5naWZ5KHtcbiAgICAgICAgICAgIHJlY29tbWVuZGVkQ2FuZGlkYXRlczogW1xuICAgICAgICAgICAgICB7XG4gICAgICAgICAgICAgICAgbmFtZTogJ01vY2sgQ2FuZGlkYXRlJyxcbiAgICAgICAgICAgICAgICByZXN1bWVVcmw6ICdodHRwczovL2V4YW1wbGUuY29tL3Jlc3VtZScsXG4gICAgICAgICAgICAgICAgbWF0Y2hTY29yZTogMC45LFxuICAgICAgICAgICAgICAgIHN1bW1hcnk6XG4gICAgICAgICAgICAgICAgICBcIlRoaXMgaXMgYSBtb2NrIHN1bW1hcnkgb2YgdGhlIGNhbmRpZGF0ZSdzIHF1YWxpZmljYXRpb25zLlwiLFxuICAgICAgICAgICAgICB9LFxuICAgICAgICAgICAgXSxcbiAgICAgICAgICB9KTtcbiAgICAgICAgICBicmVhaztcbiAgICAgICAgfVxuICAgICAgICBjYXNlICdjdXN0b21fdmliZV9oYWNraW5nJzoge1xuICAgICAgICAgIGNvbnRlbnQgPSBKU09OLnN0cmluZ2lmeSh7XG4gICAgICAgICAgICB2dWxuZXJhYmlsaXR5UmVwb3J0OiBbXG4gICAgICAgICAgICAgIHtcbiAgICAgICAgICAgICAgICB2dWxuZXJhYmlsaXR5OiAnTW9jayBWdWxuZXJhYmlsaXR5JyxcbiAgICAgICAgICAgICAgICBzZXZlcml0eTogJ0hpZ2gnLFxuICAgICAgICAgICAgICAgIGRlc2NyaXB0aW9uOiAnVGhpcyBpcyBhIG1vY2sgZGVzY3JpcHRpb24gb2YgdGhlIHZ1bG5lcmFiaWxpdHkuJyxcbiAgICAgICAgICAgICAgICByZW1lZGlhdGlvbjogJ1RoaXMgaXMgYSBtb2NrIHJlbWVkaWF0aW9uLicsXG4gICAgICAgICAgICAgIH0sXG4gICAgICAgICAgICBdLFxuICAgICAgICAgIH0pO1xuICAgICAgICAgIGJyZWFrO1xuICAgICAgICB9XG4gICAgICAgIGRlZmF1bHQ6XG4gICAgICAgICAgY29uc29sZS53YXJuKFxuICAgICAgICAgICAgYFtNb2NrTExNU2VydmljZV0gVW5oYW5kbGVkIHRhc2sgdHlwZTogJHtzdHJ1Y3R1cmVkUHJvbXB0LnRhc2t9YFxuICAgICAgICAgICk7XG4gICAgICAgICAgcmV0dXJuIHtcbiAgICAgICAgICAgIHN1Y2Nlc3M6IGZhbHNlLFxuICAgICAgICAgICAgZXJyb3I6IGBVbmhhbmRsZWQgdGFzayB0eXBlOiAke3N0cnVjdHVyZWRQcm9tcHQudGFza31gLFxuICAgICAgICAgIH07XG4gICAgICB9XG4gICAgICByZXR1cm4geyBzdWNjZXNzOiB0cnVlLCBjb250ZW50IH07XG4gICAgfSBjYXRjaCAoZXJyb3I6IGFueSkge1xuICAgICAgY29uc29sZS5lcnJvcihcbiAgICAgICAgYFtNb2NrTExNU2VydmljZV0gRXJyb3IgZHVyaW5nIHRhc2sgJHtzdHJ1Y3R1cmVkUHJvbXB0LnRhc2t9OmAsXG4gICAgICAgIGVycm9yXG4gICAgICApO1xuICAgICAgcmV0dXJuIHtcbiAgICAgICAgc3VjY2VzczogZmFsc2UsXG4gICAgICAgIGVycm9yOiBlcnJvci5tZXNzYWdlIHx8ICdVbmtub3duIGVycm9yIGluIE1vY2tMTE1TZXJ2aWNlJyxcbiAgICAgIH07XG4gICAgfVxuICB9XG59XG5cbi8vIFBsYWNlaG9sZGVyIGZvciBhIHJlYWwgTExNIFNlcnZpY2UuXG4vLyBJbiBhIHJlYWwgYXBwbGljYXRpb24sIHlvdSB3b3VsZCBpbXBvcnQgdGhlIGFjdHVhbCAnb3BlbmFpJyBwYWNrYWdlLlxuLy8gRm9yIGV4YW1wbGU6IGltcG9ydCBPcGVuQUkgZnJvbSAnb3BlbmFpJztcbi8vIFRoaXMgaXMgYSBjb25jZXB0dWFsIHJlcHJlc2VudGF0aW9uLlxudHlwZSBPcGVuQUlDbGllbnRUeXBlID0gYW55OyAvLyBSZXBsYWNlICdhbnknIHdpdGggJ09wZW5BSScgZnJvbSAnb3BlbmFpJyBwYWNrYWdlXG5cbmNvbnN0IE1BWF9SRVRSSUVTID0gMztcbmNvbnN0IElOSVRJQUxfUkVUUllfREVMQVlfTVMgPSAxMDAwO1xuXG5leHBvcnQgY2xhc3MgUmVhbExMTVNlcnZpY2UgaW1wbGVtZW50cyBMTE1TZXJ2aWNlSW50ZXJmYWNlIHtcbiAgcHJpdmF0ZSBhcGlLZXk6IHN0cmluZztcbiAgcHJpdmF0ZSBkZWZhdWx0TW9kZWxOYW1lOiBzdHJpbmc7XG4gIHByaXZhdGUgYmFzZVVSTDogc3RyaW5nOyAvLyBlLmcuLCAnaHR0cHM6Ly9hcGkuZ3JvcS5jb20vb3BlbmFpL3YxJyBvciAnaHR0cHM6Ly9hcGkub3BlbmFpLmNvbS92MSdcbiAgcHJpdmF0ZSBvcGVuYWk6IE9wZW5BSUNsaWVudFR5cGU7IC8vIFRoaXMgd291bGQgYmUgYW4gaW5zdGFuY2Ugb2YgdGhlIE9wZW5BSSBjbGllbnRcblxuICBjb25zdHJ1Y3RvcihcbiAgICBhcGlLZXk6IHN0cmluZyxcbiAgICBkZWZhdWx0TW9kZWxOYW1lOiBzdHJpbmcsXG4gICAgYmFzZVVSTDogc3RyaW5nID0gJ2h0dHBzOi8vYXBpLm9wZW5haS5jb20vdjEnIC8vIERlZmF1bHQgdG8gT3BlbkFJLCBjYW4gYmUgb3ZlcnJpZGRlbiBmb3IgR3JvcSBldGMuXG4gICkge1xuICAgIGlmIChcbiAgICAgICFhcGlLZXkgfHxcbiAgICAgIGFwaUtleSA9PT0gJ1lPVVJfQVBJX0tFWV9QTEFDRUhPTERFUicgfHxcbiAgICAgIGFwaUtleS5sZW5ndGggPCAxMFxuICAgICkge1xuICAgICAgLy8gSW4gYSByZWFsIGFwcCwgdGhpcyBtaWdodCB0aHJvdyBhbiBlcnJvciBvciBoYXZlIGEgbW9yZSByb2J1c3QgY2hlY2suXG4gICAgICBjb25zb2xlLmVycm9yKFxuICAgICAgICAnUmVhbExMTVNlcnZpY2U6IEFQSSBLZXkgaXMgbWlzc2luZywgYSBwbGFjZWhvbGRlciwgb3IgdG9vIHNob3J0ISBSZWFsIGNhbGxzIHdpbGwgbGlrZWx5IGZhaWwuJ1xuICAgICAgKTtcbiAgICAgIC8vIEFsbG93IGNvbnN0cnVjdGlvbiBmb3IgdGVzdGluZy9tb2NraW5nIHB1cnBvc2VzLCBidXQgbG9nIGEgc2V2ZXJlIHdhcm5pbmcuXG4gICAgfVxuICAgIHRoaXMuYXBpS2V5ID0gYXBpS2V5O1xuICAgIHRoaXMuZGVmYXVsdE1vZGVsTmFtZSA9IGRlZmF1bHRNb2RlbE5hbWU7XG4gICAgdGhpcy5iYXNlVVJMID0gYmFzZVVSTDtcblxuICAgIC8vIC0tLSBDb25jZXB0dWFsIEFQSSBLZXkgU2VjdXJpdHkgTm90ZSAtLS1cbiAgICAvLyBJbiBhIHByb2R1Y3Rpb24gZW52aXJvbm1lbnQsIEFQSSBrZXlzIHNob3VsZCBORVZFUiBiZSBoYXJkY29kZWQuXG4gICAgLy8gVGhleSBzaG91bGQgYmUgcmV0cmlldmVkIGZyb20gZW52aXJvbm1lbnQgdmFyaWFibGVzIG9yIGEgc2VjdXJlIHNlY3JldHMgbWFuYWdlbWVudCBzZXJ2aWNlLlxuICAgIC8vIEV4YW1wbGU6IHRoaXMuYXBpS2V5ID0gcHJvY2Vzcy5lbnYuTExNX0FQSV9LRVk7XG4gICAgLy8gVGhlIHZhbHVlIHBhc3NlZCB0byB0aGlzIGNvbnN0cnVjdG9yIHNob3VsZCBiZSBzb3VyY2VkIHNlY3VyZWx5LlxuICAgIC8vIC0tLSBFbmQgU2VjdXJpdHkgTm90ZSAtLS1cblxuICAgIC8vIEluaXRpYWxpemUgdGhlIE9wZW5BSSBjbGllbnQgKGNvbmNlcHR1YWwpXG4gICAgLy8gSW4gYSByZWFsIGltcGxlbWVudGF0aW9uOlxuICAgIC8vIHRoaXMub3BlbmFpID0gbmV3IE9wZW5BSSh7IGFwaUtleTogdGhpcy5hcGlLZXksIGJhc2VVUkw6IHRoaXMuYmFzZVVSTCB9KTtcbiAgICAvLyBGb3Igbm93LCB3ZSdsbCBrZWVwIGl0IGFzIGEgcGxhY2Vob2xkZXIgdGhhdCBkb2Vzbid0IGFjdHVhbGx5IGluaXRpYWxpemUuXG4gICAgdGhpcy5vcGVuYWkgPSBudWxsO1xuICAgIGlmIChcbiAgICAgIHRoaXMuYXBpS2V5ICYmXG4gICAgICB0aGlzLmFwaUtleSAhPT0gJ1lPVVJfQVBJX0tFWV9QTEFDRUhPTERFUicgJiZcbiAgICAgIHRoaXMuYXBpS2V5Lmxlbmd0aCA+PSAxMFxuICAgICkge1xuICAgICAgY29uc29sZS5sb2coXG4gICAgICAgIGBSZWFsTExNU2VydmljZSBpbml0aWFsaXplZCBmb3IgbW9kZWwgJHt0aGlzLmRlZmF1bHRNb2RlbE5hbWV9IGF0ICR7dGhpcy5iYXNlVVJMfS5gXG4gICAgICApO1xuICAgIH0gZWxzZSB7XG4gICAgICBjb25zb2xlLndhcm4oXG4gICAgICAgIGBSZWFsTExNU2VydmljZSBpbml0aWFsaXplZCB3aXRoIGEgcGxhY2Vob2xkZXIgQVBJIGtleSBmb3IgbW9kZWwgJHt0aGlzLmRlZmF1bHRNb2RlbE5hbWV9LiBBUEkgY2FsbHMgd2lsbCBiZSBTVFVCQkVELmBcbiAgICAgICk7XG4gICAgfVxuICB9XG5cbiAgLy8gSGVscGVyIHRvIGNvbnN0cnVjdCBhcHByb3ByaWF0ZSBtZXNzYWdlcyBmb3IgZGlmZmVyZW50IHRhc2tzXG4gIHByaXZhdGUgX2NvbnN0cnVjdE1lc3NhZ2VzKFxuICAgIHN0cnVjdHVyZWRQcm9tcHQ6IFN0cnVjdHVyZWRMTE1Qcm9tcHQsXG4gICAgdGFza1R5cGVPdmVycmlkZT86IExMTVRhc2tUeXBlIHwgc3RyaW5nXG4gICk6IGFueVtdIHtcbiAgICAvLyBUYXNrIHR5cGUgZnJvbSB0aGUgcHJvbXB0IGl0c2VsZiwgb3IgYW4gb3ZlcnJpZGUgKGUuZy4gZm9yIGFnZW50LXNwZWNpZmljIHRhc2tzKVxuICAgIGNvbnN0IHRhc2sgPSB0YXNrVHlwZU92ZXJyaWRlIHx8IHN0cnVjdHVyZWRQcm9tcHQudGFzaztcbiAgICBsZXQgc3lzdGVtTWVzc2FnZSA9IGBZb3UgYXJlIGFuIEFJIGFzc2lzdGFudC4gUGVyZm9ybSB0aGUgdGFzazogJHtzdHJ1Y3R1cmVkUHJvbXB0LnRhc2t9LmA7XG4gICAgbGV0IHVzZXJNZXNzYWdlQ29udGVudCA9IGBEYXRhOiAke0pTT04uc3RyaW5naWZ5KHN0cnVjdHVyZWRQcm9tcHQuZGF0YSl9YDtcblxuICAgIC8vIEN1c3RvbWl6ZSBzeXN0ZW0vdXNlciBtZXNzYWdlcyBiYXNlZCBvbiB0YXNrIGZvciBiZXR0ZXIgcmVhbCBMTE0gcGVyZm9ybWFuY2VcbiAgICBzd2l0Y2ggKHN0cnVjdHVyZWRQcm9tcHQudGFzaykge1xuICAgICAgY2FzZSAnY2F0ZWdvcml6ZV9lbWFpbCc6XG4gICAgICAgIGNvbnN0IGNhdERhdGEgPSBzdHJ1Y3R1cmVkUHJvbXB0LmRhdGEgYXMgRW1haWxDYXRlZ29yaXphdGlvbkRhdGE7XG4gICAgICAgIHN5c3RlbU1lc3NhZ2UgPSBgQ2F0ZWdvcml6ZSB0aGUgZm9sbG93aW5nIGVtYWlsIGludG8gb25lIG9mOiAnVXJnZW50JywgJ0FjdGlvblJlcXVpcmVkJywgJ0ZZSScsICdTcGFtJywgJ01lZXRpbmdJbnZpdGUnLCAnT3RoZXInLiBSZXR1cm4gT05MWSB2YWxpZCBKU09OOiB7XCJjYXRlZ29yeVwiOiBcIkNBVEVHT1JZX05BTUVcIiwgXCJjb25maWRlbmNlXCI6IDAuWH1gO1xuICAgICAgICB1c2VyTWVzc2FnZUNvbnRlbnQgPSBgU3ViamVjdDogXCIke2NhdERhdGEuc3ViamVjdH1cIlxcbkJvZHkgU25pcHBldDogXCIke2NhdERhdGEuYm9keVNuaXBwZXR9XCJgO1xuICAgICAgICBicmVhaztcbiAgICAgIGNhc2UgJ3N1bW1hcml6ZV9lbWFpbCc6XG4gICAgICAgIGNvbnN0IHN1bURhdGEgPSBzdHJ1Y3R1cmVkUHJvbXB0LmRhdGEgYXMgRW1haWxTdW1tYXJpemF0aW9uRGF0YTtcbiAgICAgICAgc3lzdGVtTWVzc2FnZSA9XG4gICAgICAgICAgJ1N1bW1hcml6ZSB0aGUgZm9sbG93aW5nIGVtYWlsIGNvbmNpc2VseSBpbiAxLTIgc2VudGVuY2VzLiBSZXR1cm4gb25seSB0aGUgc3VtbWFyeSB0ZXh0Lic7XG4gICAgICAgIHVzZXJNZXNzYWdlQ29udGVudCA9IGBTdWJqZWN0OiBcIiR7c3VtRGF0YS5zdWJqZWN0fVwiXFxuQm9keSBTbmlwcGV0OiBcIiR7c3VtRGF0YS5ib2R5U25pcHBldH1cImA7XG4gICAgICAgIGJyZWFrO1xuICAgICAgY2FzZSAnc3VnZ2VzdF9yZXBseV9lbWFpbCc6XG4gICAgICAgIGNvbnN0IHJlcERhdGEgPSBzdHJ1Y3R1cmVkUHJvbXB0LmRhdGEgYXMgRW1haWxSZXBseVN1Z2dlc3Rpb25EYXRhO1xuICAgICAgICBzeXN0ZW1NZXNzYWdlID0gYFN1Z2dlc3QgYSBicmllZiwgcG9saXRlLCBwcm9mZXNzaW9uYWwgcmVwbHkgZm9yIHRoaXMgZW1haWwuIElmIG5vIHJlcGx5IGlzIG5lZWRlZCAoZS5nLiwgU3BhbSwgc29tZSBGWUkpLCByZXR1cm4gXCJObyByZXBseSBuZWVkZWQuXCIuIENhdGVnb3J5OiAke3JlcERhdGEuY2F0ZWdvcnl9LmA7XG4gICAgICAgIHVzZXJNZXNzYWdlQ29udGVudCA9IGBTdWJqZWN0OiBcIiR7cmVwRGF0YS5zdWJqZWN0fVwiXFxuU3VtbWFyeTogXCIke3JlcERhdGEuc3VtbWFyeX1cIlxcbiR7cmVwRGF0YS5hY3Rpb25JdGVtcyAmJiByZXBEYXRhLmFjdGlvbkl0ZW1zLmxlbmd0aCA+IDAgPyBgSWRlbnRpZmllZCBBY3Rpb24gSXRlbXM6IFwiJHtyZXBEYXRhLmFjdGlvbkl0ZW1zLmpvaW4oJzsgJyl9XCJgIDogJyd9YDtcbiAgICAgICAgYnJlYWs7XG4gICAgICBjYXNlICdleHRyYWN0X2FjdGlvbnNfZW1haWwnOlxuICAgICAgICBjb25zdCBhY3REYXRhID0gc3RydWN0dXJlZFByb21wdC5kYXRhIGFzIEVtYWlsQWN0aW9uRXh0cmFjdGlvbkRhdGE7XG4gICAgICAgIHN5c3RlbU1lc3NhZ2UgPSBgRXh0cmFjdCBkaXN0aW5jdCBhY3Rpb24gaXRlbXMgZnJvbSB0aGlzIGVtYWlsIGJvZHkuIFJldHVybiBKU09OOiB7XCJhY3Rpb25JdGVtc1wiOiBbXCJBY3Rpb24gMVwiLCAuLi5dfS4gSWYgbm9uZSwgcmV0dXJuIHtcImFjdGlvbkl0ZW1zXCI6IFtdfS5gO1xuICAgICAgICB1c2VyTWVzc2FnZUNvbnRlbnQgPSBgRW1haWwgQm9keTogXCIke2FjdERhdGEuZW1haWxCb2R5fVwiYDtcbiAgICAgICAgYnJlYWs7XG4gICAgICAvLyBBZGQgbW9yZSBjYXNlcyBmb3Igb3RoZXIgTExNVGFza1R5cGVzIHRvIGN1c3RvbWl6ZSBwcm9tcHRzXG4gICAgICBjYXNlICdleHRyYWN0X2RvY3VtZW50X3NuaXBwZXRzJzpcbiAgICAgICAgY29uc3Qgc25pcERhdGEgPSBzdHJ1Y3R1cmVkUHJvbXB0LmRhdGEgYXMgRG9jdW1lbnRTbmlwcGV0RGF0YTtcbiAgICAgICAgc3lzdGVtTWVzc2FnZSA9IGBFeHRyYWN0IHVwIHRvIDMgcmVsZXZhbnQgc25pcHBldHMgKGVhY2ggfiR7c25pcERhdGEuc25pcHBldExlbmd0aCB8fCAxNTB9IGNoYXJzKSBmb3IgdGhlIHF1ZXJ5IGZyb20gdGhlIGRvY3VtZW50LiBSZXR1cm4gSlNPTjoge1wic25pcHBldHNcIjogW1wiLi4uXCIsIC4uLl19LiBJZiBub25lLCByZXR1cm4ge1wic25pcHBldHNcIjogW119LmA7XG4gICAgICAgIHVzZXJNZXNzYWdlQ29udGVudCA9IGBRdWVyeTogXCIke3NuaXBEYXRhLnF1ZXJ5fVwiXFxuRG9jdW1lbnQgVGl0bGU6IFwiJHtzbmlwRGF0YS5kb2N1bWVudFRpdGxlfVwiXFxuRG9jdW1lbnQgVGV4dDogXCIke3NuaXBEYXRhLmRvY3VtZW50VGV4dH1cImA7XG4gICAgICAgIGJyZWFrO1xuICAgICAgY2FzZSAnc3VtbWFyaXplX2RvY3VtZW50X3NuaXBwZXRzJzpcbiAgICAgICAgY29uc3QgZG9jU3VtRGF0YSA9IHN0cnVjdHVyZWRQcm9tcHQuZGF0YSBhcyBEb2N1bWVudFN1bW1hcnlEYXRhO1xuICAgICAgICBzeXN0ZW1NZXNzYWdlID0gYFN1bW1hcml6ZSB0aGUgcHJvdmlkZWQgc25pcHBldHMgYmFzZWQgb24gdGhlIHF1ZXJ5LiBUYXJnZXQgbGVuZ3RoOiAke2RvY1N1bURhdGEudGFyZ2V0TGVuZ3RoIHx8ICdtZWRpdW0nfS4gUmV0dXJuIG9ubHkgdGhlIHN1bW1hcnkuYDtcbiAgICAgICAgdXNlck1lc3NhZ2VDb250ZW50ID0gYFF1ZXJ5OiBcIiR7ZG9jU3VtRGF0YS5xdWVyeX1cIlxcbkRvY3VtZW50IFRpdGxlOiBcIiR7ZG9jU3VtRGF0YS5kb2N1bWVudFRpdGxlfVwiXFxuU25pcHBldHM6XFxuJHsoZG9jU3VtRGF0YS5zbmlwcGV0cyB8fCBbXSkubWFwKChzKSA9PiBgLSAke3N9YCkuam9pbignXFxuJyl9YDtcbiAgICAgICAgYnJlYWs7XG4gICAgICBjYXNlICdzdW1tYXJpemVfb3ZlcmFsbF9hbnN3ZXInOlxuICAgICAgICBjb25zdCBvdmVyYWxsRGF0YSA9IHN0cnVjdHVyZWRQcm9tcHQuZGF0YSBhcyBPdmVyYWxsU3VtbWFyeURhdGE7XG4gICAgICAgIHN5c3RlbU1lc3NhZ2UgPSBgQ29tYmluZSB0aGVzZSBpbmRpdmlkdWFsIHN1bW1hcmllcyBpbnRvIG9uZSBjb25jaXNlIG92ZXJhbGwgYW5zd2VyIHRvIHRoZSB1c2VyJ3MgcXVlcnkuIFJldHVybiBvbmx5IHRoZSBjb21iaW5lZCBzdW1tYXJ5LmA7XG4gICAgICAgIHVzZXJNZXNzYWdlQ29udGVudCA9IGBVc2VyJ3MgUXVlcnk6IFwiJHtvdmVyYWxsRGF0YS5xdWVyeX1cIlxcbkluZGl2aWR1YWwgU3VtbWFyaWVzOlxcbiR7b3ZlcmFsbERhdGEuaW5kaXZpZHVhbFN1bW1hcmllcy5tYXAoKHMpID0+IGBGcm9tIFwiJHtzLnRpdGxlfVwiOiAke3Muc3VtbWFyeX1gKS5qb2luKCdcXG4tLS1cXG4nKX1gO1xuICAgICAgICBicmVhaztcbiAgICAgIGNhc2UgJ2NsYXNzaWZ5X2d1aWRhbmNlX3F1ZXJ5JzpcbiAgICAgICAgY29uc3QgZ3FDbGFzc0RhdGEgPVxuICAgICAgICAgIHN0cnVjdHVyZWRQcm9tcHQuZGF0YSBhcyBHdWlkYW5jZVF1ZXJ5Q2xhc3NpZmljYXRpb25EYXRhO1xuICAgICAgICBzeXN0ZW1NZXNzYWdlID0gYENsYXNzaWZ5IHRoZSB1c2VyIHF1ZXJ5IGludG8gb25lIG9mOiAnYW5zd2VyX3F1ZXN0aW9uJywgJ2ZpbmRfdHV0b3JpYWwnLCAnZ3VpZGVfd29ya2Zsb3cnLCAnZ2VuZXJhbF9leHBsYW5hdGlvbicuIFJldHVybiBKU09OOiB7XCJndWlkYW5jZVR5cGVcIjogXCJUWVBFXCJ9LmA7XG4gICAgICAgIHVzZXJNZXNzYWdlQ29udGVudCA9IGBVc2VyIFF1ZXJ5OiBcIiR7Z3FDbGFzc0RhdGEucXVlcnl9XCJgO1xuICAgICAgICBicmVhaztcbiAgICAgIGNhc2UgJ2Fuc3dlcl9mcm9tX3RleHQnOlxuICAgICAgICBjb25zdCBhbnNUZXh0RGF0YSA9IHN0cnVjdHVyZWRQcm9tcHQuZGF0YSBhcyBBbnN3ZXJGcm9tVGV4dERhdGE7XG4gICAgICAgIHN5c3RlbU1lc3NhZ2UgPSBgVXNpbmcgT05MWSB0aGUgcHJvdmlkZWQgdGV4dCwgYW5zd2VyIHRoZSBxdWVzdGlvbi4gUmV0dXJuIG9ubHkgdGhlIGRpcmVjdCBhbnN3ZXIuYDtcbiAgICAgICAgdXNlck1lc3NhZ2VDb250ZW50ID0gYFF1ZXN0aW9uOiAnJHthbnNUZXh0RGF0YS5xdWVyeX0nXFxuUHJvdmlkZWQgdGV4dCBmcm9tIFwiJHthbnNUZXh0RGF0YS5hcnRpY2xlVGl0bGUgfHwgJ2RvY3VtZW50J31cIjogJyR7YW5zVGV4dERhdGEudGV4dENvbnRlbnR9J2A7XG4gICAgICAgIGJyZWFrO1xuICAgICAgY2FzZSAnZXh0cmFjdF9zdGVwc19mcm9tX3RleHQnOlxuICAgICAgICBjb25zdCBzdGVwc1RleHREYXRhID0gc3RydWN0dXJlZFByb21wdC5kYXRhIGFzIFN0ZXBzRnJvbVRleHREYXRhO1xuICAgICAgICBzeXN0ZW1NZXNzYWdlID0gYEV4dHJhY3Qga2V5IHN0ZXBzIGZvciB0aGUgcXVlcnkgZnJvbSB0aGUgdHV0b3JpYWwgdGV4dC4gUmV0dXJuIEpTT046IHtcInN0ZXBzXCI6IFt7XCJ0aXRsZVwiOlwiU3RlcCBUaXRsZVwiLCBcImRlc2NyaXB0aW9uXCI6XCJTdGVwIGRlc2NcIn0sIC4uLl19LiBJZiBub25lLCByZXR1cm4ge1wic3RlcHNcIjogW119LmA7XG4gICAgICAgIHVzZXJNZXNzYWdlQ29udGVudCA9IGBRdWVyeTogJyR7c3RlcHNUZXh0RGF0YS5xdWVyeX0nXFxuVHV0b3JpYWwgVGV4dCBmcm9tIFwiJHtzdGVwc1RleHREYXRhLmFydGljbGVUaXRsZSB8fCAnZG9jdW1lbnQnfVwiOiAnJHtzdGVwc1RleHREYXRhLnRleHRDb250ZW50fSdgO1xuICAgICAgICBicmVhaztcbiAgICAgIGNhc2UgJ3N1bW1hcml6ZV9mb3JfZXhwbGFuYXRpb24nOlxuICAgICAgICBjb25zdCBleHBsRGF0YSA9IHN0cnVjdHVyZWRQcm9tcHQuZGF0YSBhcyBFeHBsYW5hdGlvbkRhdGE7XG4gICAgICAgIHN5c3RlbU1lc3NhZ2UgPSBgUHJvdmlkZSBhIGNvbmNpc2UgZXhwbGFuYXRpb24gZm9yIHRoZSBxdWVyeSBiYXNlZCBvbiB0aGUgdGV4dC4gUmV0dXJuIG9ubHkgdGhlIGV4cGxhbmF0aW9uLmA7XG4gICAgICAgIHVzZXJNZXNzYWdlQ29udGVudCA9IGBRdWVyeTogJyR7ZXhwbERhdGEucXVlcnl9J1xcblRleHQgZnJvbSBcIiR7ZXhwbERhdGEuYXJ0aWNsZVRpdGxlIHx8ICdkb2N1bWVudCd9XCI6ICcke2V4cGxEYXRhLnRleHRDb250ZW50fSdgO1xuICAgICAgICBicmVhaztcbiAgICAgIGNhc2UgJ2dlbmVyYXRlX2ZvbGxvd3VwX3N1Z2dlc3Rpb25zJzpcbiAgICAgICAgY29uc3Qgc3VnRGF0YSA9IHN0cnVjdHVyZWRQcm9tcHQuZGF0YSBhcyBGb2xsb3d1cFN1Z2dlc3Rpb25EYXRhO1xuICAgICAgICBzeXN0ZW1NZXNzYWdlID0gYEdpdmVuIHRoZSB1c2VyIHF1ZXJ5IGFuZCBzaG93biBndWlkYW5jZSwgc3VnZ2VzdCB0d28gZGlzdGluY3QsIHJlbGF0ZWQgdG9waWNzIG9yIGFkdmFuY2VkIGZlYXR1cmVzLiBSZXR1cm4gSlNPTjoge1wic3VnZ2VzdGlvbnNcIjogW1wiU3VnZyAxXCIsIFwiU3VnZyAyXCJdfS4gSWYgbm9uZSwgcmV0dXJuIHtcInN1Z2dlc3Rpb25zXCI6IFtdfS5gO1xuICAgICAgICB1c2VyTWVzc2FnZUNvbnRlbnQgPSBgVXNlciBRdWVyeTogJyR7c3VnRGF0YS5xdWVyeX0nXFxuR3VpZGFuY2UgU2hvd24gKFRpdGxlKTogJyR7c3VnRGF0YS5hcnRpY2xlVGl0bGUgfHwgJ04vQSd9J2A7XG4gICAgICAgIGJyZWFrO1xuICAgICAgY2FzZSAncGFyc2Vfc2VhcmNoX3F1ZXJ5JzpcbiAgICAgICAgY29uc3QgcGFyc2VEYXRhID0gc3RydWN0dXJlZFByb21wdC5kYXRhIGFzIFNlYXJjaFF1ZXJ5UGFyc2luZ0RhdGE7XG4gICAgICAgIHN5c3RlbU1lc3NhZ2UgPSBgWW91IGFyZSBhbiBleHBlcnQgTkxVIChOYXR1cmFsIExhbmd1YWdlIFVuZGVyc3RhbmRpbmcpIHBhcnNlciBmb3IgYSBzZWFyY2ggZW5naW5lLiBZb3VyIHRhc2sgaXMgdG8gYW5hbHl6ZSBhIHVzZXIncyByYXcgc2VhcmNoIHF1ZXJ5IGFuZCBjb252ZXJ0IGl0IGludG8gYSBzdHJ1Y3R1cmVkIEpTT04gb2JqZWN0LlxuXG5Zb3UgbXVzdCBpZGVudGlmeSB0aGUgZm9sbG93aW5nIGVudGl0aWVzIGZyb20gdGhlIHVzZXIncyBxdWVyeTpcblxuMS4gIFxcYHNlYXJjaF90ZXJtXFxgOiBUaGUgY29yZSBzdWJqZWN0IG9mIHRoZSBzZWFyY2guIFJlbW92ZSBmaWxsZXIgd29yZHMgbGlrZSBcImZpbmQgbWVcIiwgXCJzaG93IG1lXCIsIFwic2VhcmNoIGZvclwiLCBldGMuIEtlZXAgdGhlIGVzc2VudGlhbCBrZXl3b3Jkcy5cblxuMi4gIFxcYGZpbHRlcnNcXGA6IEFuIG9iamVjdCBjb250YWluaW5nIHN0cnVjdHVyZWQgZmlsdGVyIGNyaXRlcmlhLiBZb3UgbXVzdCBleHRyYWN0IHRoZSBmb2xsb3dpbmcgZmlsdGVyIHR5cGVzOlxuXG4gICAgKiAgIFxcYGRvY190eXBlc1xcYDogQW4gYXJyYXkgb2YgZG9jdW1lbnQgdHlwZXMgbWVudGlvbmVkLiBUaGUgdmFsaWQgdHlwZXMgYXJlOiBcXGBnZHJpdmVfcGRmXFxgLCBcXGBnZHJpdmVfZG9jeFxcYCwgXFxgZ2RyaXZlX2ZvbGRlclxcYCwgXFxgZ2RyaXZlX3NoZWV0XFxgLCBcXGBnZHJpdmVfc2xpZGVcXGAsIFxcYGVtYWlsX3NuaXBwZXRcXGAsIFxcYG5vdGlvbl9zdW1tYXJ5XFxgLCBcXGBkb2N1bWVudF9jaHVua1xcYC4gSWYgYSB1c2VyIHNheXMgXCJnLWRyaXZlIGRvY1wiLCBtYXAgaXQgdG8gXFxgZ2RyaXZlX2RvY3hcXGAuIElmIHRoZXkgc2F5IFwicGRmXCIgd2l0aG91dCBcImdkcml2ZVwiLCBtYXAgdG8gXFxgZG9jdW1lbnRfY2h1bmtcXGAuXG5cbiAgICAqICAgXFxgZGF0ZV9hZnRlclxcYCAmIFxcYGRhdGVfYmVmb3JlXFxgOiBBIGRhdGUgcmFuZ2UuIFRvZGF5J3MgZGF0ZSBpcyAke3BhcnNlRGF0YS5jdXJyZW50RGF0ZX0uIElmIHRoZSB1c2VyIHNheXMgXCJsYXN0IG1vbnRoXCIsIGNhbGN1bGF0ZSB0aGUgZmlyc3QgYW5kIGxhc3QgZGF5IG9mIHRoZSBwcmV2aW91cyBtb250aC4gSWYgdGhleSBzYXkgXCJ0aGlzIHdlZWtcIiwgY2FsY3VsYXRlIHRoZSBwYXN0IE1vbmRheSBhbmQgdXBjb21pbmcgU3VuZGF5LiBJZiB0aGUgdXNlciBzYXlzIFwieWVzdGVyZGF5XCIsIGNhbGN1bGF0ZSB0aGUgc3RhcnQgYW5kIGVuZCBvZiB0aGUgcHJldmlvdXMgZGF5LiBBbHdheXMgcmV0dXJuIHRoZSBkYXRlIGFzIGEgZnVsbCBcXGBZWVlZLU1NLUREXFxgIHN0cmluZy5cblxuICAgICogICBcXGBkYXRlX2ZpZWxkX3RvX2ZpbHRlclxcYDogVGhlIGRhdGUgZmllbGQgdG8gZmlsdGVyIG9uLiBWYWxpZCBmaWVsZHMgYXJlIFxcYGluZ2VzdGVkX2F0XFxgLCBcXGBjcmVhdGVkX2F0X3NvdXJjZVxcYCwgXFxgbGFzdF9tb2RpZmllZF9zb3VyY2VcXGAuIERlZmF1bHQgdG8gXFxgaW5nZXN0ZWRfYXRcXGAgaWYgYW1iaWd1b3VzLlxuXG4gICAgKiAgIFxcYG1ldGFkYXRhX3Byb3BlcnRpZXNcXGA6IEtleS12YWx1ZSBwYWlycyBsaWtlIFwiYnkgPGF1dGhvcj5cIi4gRXh0cmFjdCB0aGUga2V5IChlLmcuLCBcImF1dGhvclwiKSBhbmQgdGhlIHZhbHVlLlxuXG5Zb3UgTVVTVCByZXNwb25kIHdpdGggT05MWSBhIHZhbGlkIEpTT04gb2JqZWN0LiBUaGUgSlNPTiBvYmplY3QgbXVzdCBjb25mb3JtIHRvIHRoaXMgc3RydWN0dXJlOlxuXFxgXFxgXFxganNvblxue1xuICBcInNlYXJjaF90ZXJtXCI6IFwic3RyaW5nXCIsXG4gIFwiZmlsdGVyc1wiOiB7XG4gICAgXCJkb2NfdHlwZXNcIjogW1wic3RyaW5nXCIsIC4uLl0sXG4gICAgXCJkYXRlX2FmdGVyXCI6IFwiWVlZWS1NTS1ERFwiLFxuICAgIFwiZGF0ZV9iZWZvcmVcIjogXCJZWVlZLU1NLUREXCIsXG4gICAgXCJkYXRlX2ZpZWxkX3RvX2ZpbHRlclwiOiBcInN0cmluZ1wiLFxuICAgIFwibWV0YWRhdGFfcHJvcGVydGllc1wiOiB7IFwia2V5XCI6IFwidmFsdWVcIiwgLi4uIH1cbiAgfVxufVxuXFxgXFxgXFxgXG5JZiBhIGZpbHRlciBpcyBub3QgcHJlc2VudCwgb21pdCBpdHMga2V5LiBJZiBubyBmaWx0ZXJzIGFyZSBmb3VuZCwgXFxgZmlsdGVyc1xcYCBzaG91bGQgYmUgYW4gZW1wdHkgb2JqZWN0LmA7XG4gICAgICAgIHVzZXJNZXNzYWdlQ29udGVudCA9IGBVc2VyIFF1ZXJ5OiBcIiR7cGFyc2VEYXRhLnJhd1F1ZXJ5fVwiYDtcbiAgICAgICAgYnJlYWs7XG4gICAgICBkZWZhdWx0OlxuICAgICAgICBzeXN0ZW1NZXNzYWdlID0gYFlvdSBhcmUgYW4gQUkgYXNzaXN0YW50IHBlcmZvcm1pbmcgdGFzazogJHtzdHJ1Y3R1cmVkUHJvbXB0LnRhc2t9LiBSZXNwb25kIGFwcHJvcHJpYXRlbHkgYmFzZWQgb24gdGhlIGRhdGEuYDtcbiAgICAgICAgdXNlck1lc3NhZ2VDb250ZW50ID0gYERhdGE6ICR7SlNPTi5zdHJpbmdpZnkoc3RydWN0dXJlZFByb21wdC5kYXRhKX1gO1xuICAgICAgICBicmVhaztcbiAgICB9XG4gICAgcmV0dXJuIFtcbiAgICAgIHsgcm9sZTogJ3N5c3RlbScsIGNvbnRlbnQ6IHN5c3RlbU1lc3NhZ2UgfSxcbiAgICAgIHsgcm9sZTogJ3VzZXInLCBjb250ZW50OiB1c2VyTWVzc2FnZUNvbnRlbnQgfSxcbiAgICBdO1xuICB9XG5cbiAgcHVibGljIGFzeW5jIGdlbmVyYXRlKFxuICAgIHN0cnVjdHVyZWRQcm9tcHQ6IFN0cnVjdHVyZWRMTE1Qcm9tcHQsXG4gICAgbW9kZWxOYW1lVG9Vc2U/OiBzdHJpbmcsXG4gICAgb3B0aW9ucz86IHtcbiAgICAgIHRlbXBlcmF0dXJlPzogbnVtYmVyO1xuICAgICAgbWF4VG9rZW5zPzogbnVtYmVyO1xuICAgICAgaXNKc29uT3V0cHV0PzogYm9vbGVhbjtcbiAgICB9IC8vIEFkZGVkIGlzSnNvbk91dHB1dFxuICApOiBQcm9taXNlPExMTVNlcnZpY2VSZXNwb25zZT4ge1xuICAgIGNvbnN0IHRhcmdldE1vZGVsID0gbW9kZWxOYW1lVG9Vc2UgfHwgdGhpcy5kZWZhdWx0TW9kZWxOYW1lO1xuICAgIGNvbnN0IHRhc2tUeXBlID0gKHN0cnVjdHVyZWRQcm9tcHQuZGF0YSBhcyBhbnkpPy5zeXN0ZW1fcHJvbXB0IC8vIEhldXJpc3RpYyBmb3IgTkxVIGFnZW50IHRhc2tzXG4gICAgICA/IHN0cnVjdHVyZWRQcm9tcHQudGFzayB8fCAnY3VzdG9tX2FnZW50X3Rhc2snXG4gICAgICA6IHN0cnVjdHVyZWRQcm9tcHQudGFzaztcblxuICAgIC8vIElmIEFQSSBrZXkgaXMgYSBwbGFjZWhvbGRlciwgaW1tZWRpYXRlbHkgZmFsbGJhY2sgdG8gbW9jayB0byBwcmV2ZW50IGFjdHVhbCBjYWxsIGF0dGVtcHRzLlxuICAgIGlmIChcbiAgICAgICF0aGlzLmFwaUtleSB8fFxuICAgICAgdGhpcy5hcGlLZXkgPT09ICdZT1VSX0FQSV9LRVlfUExBQ0VIT0xERVInIHx8XG4gICAgICB0aGlzLmFwaUtleS5sZW5ndGggPCAxMFxuICAgICkge1xuICAgICAgY29uc29sZS53YXJuKFxuICAgICAgICBgW1JlYWxMTE1TZXJ2aWNlXSBBUEkgS2V5IGlzIGEgcGxhY2Vob2xkZXIgZm9yIG1vZGVsICR7dGFyZ2V0TW9kZWx9LiBGYWxsaW5nIGJhY2sgdG8gTW9ja0xMTVNlcnZpY2UgZm9yIHRhc2s6ICR7dGFza1R5cGV9LmBcbiAgICAgICk7XG4gICAgICBjb25zdCBtb2NrU2VydmljZSA9IG5ldyBNb2NrTExNU2VydmljZSgpO1xuICAgICAgcmV0dXJuIG1vY2tTZXJ2aWNlLmdlbmVyYXRlKHN0cnVjdHVyZWRQcm9tcHQsIHRhcmdldE1vZGVsLCBvcHRpb25zKTtcbiAgICB9XG5cbiAgICAvLyBUaGlzIGlzIHdoZXJlIHRoZSBhY3R1YWwgJ29wZW5haScgY2xpZW50IHdvdWxkIGJlIHVzZWQuXG4gICAgLy8gU2luY2UgJ3RoaXMub3BlbmFpJyBpcyBudWxsIGluIHRoaXMgc2FuZGJveGVkIGVudmlyb25tZW50LCB0aGUgZm9sbG93aW5nIGJsb2NrIGlzIGNvbmNlcHR1YWwuXG4gICAgaWYgKCF0aGlzLm9wZW5haSkge1xuICAgICAgY29uc29sZS5lcnJvcihcbiAgICAgICAgJ1tSZWFsTExNU2VydmljZV0gT3BlbkFJIGNsaWVudCBub3QgaW5pdGlhbGl6ZWQuIFRISVMgU0hPVUxEIE5PVCBIQVBQRU4gSU4gQSBSRUFMIEFQUCBpZiBBUEkga2V5IGlzIHZhbGlkLidcbiAgICAgICk7XG4gICAgICBjb25zb2xlLmxvZyhcbiAgICAgICAgJ1tSZWFsTExNU2VydmljZV0gU1RVQkJJTkcgQVBJIGNhbGwgYW5kIHJldHVybmluZyBtb2NrIHJlc3BvbnNlIGR1ZSB0byB1bmluaXRpYWxpemVkIGNsaWVudC4nXG4gICAgICApO1xuICAgICAgLy8gRmFsbGJhY2sgdG8gTW9ja0xMTVNlcnZpY2UgaWYgb3BlbmFpIGNsaWVudCBpc24ndCBpbml0aWFsaXplZCAoZS5nLiBpbiBzYW5kYm94KVxuICAgICAgY29uc3QgbW9ja1NlcnZpY2UgPSBuZXcgTW9ja0xMTVNlcnZpY2UoKTtcbiAgICAgIGNvbnN0IG1vY2tSZXNwb25zZSA9IGF3YWl0IG1vY2tTZXJ2aWNlLmdlbmVyYXRlKFxuICAgICAgICBzdHJ1Y3R1cmVkUHJvbXB0LFxuICAgICAgICB0YXJnZXRNb2RlbCxcbiAgICAgICAgb3B0aW9uc1xuICAgICAgKTtcbiAgICAgIHJldHVybiB7XG4gICAgICAgIC4uLm1vY2tSZXNwb25zZSxcbiAgICAgICAgZXJyb3I6IG1vY2tSZXNwb25zZS5lcnJvclxuICAgICAgICAgID8gbW9ja1Jlc3BvbnNlLmVycm9yICsgJyAoUmVhbExMTSBTdHViKSdcbiAgICAgICAgICA6ICdSZWFsTExNIFN0dWI6IE9wZW5BSSBjbGllbnQgbm90IGluaXRpYWxpemVkLicsXG4gICAgICAgIHN1Y2Nlc3M6IG1vY2tSZXNwb25zZS5zdWNjZXNzLCAvLyBDYW4gYmUgdHJ1ZSBpZiBtb2NrIGlzIHN1Y2Nlc3NmdWxcbiAgICAgIH07XG4gICAgfVxuXG4gICAgY29uc3QgbWVzc2FnZXMgPSB0aGlzLl9jb25zdHJ1Y3RNZXNzYWdlcyhzdHJ1Y3R1cmVkUHJvbXB0LCB0YXNrVHlwZSk7XG4gICAgbGV0IHJldHJpZXMgPSAwO1xuXG4gICAgY29uc29sZS5sb2coXG4gICAgICBgW1JlYWxMTE1TZXJ2aWNlXSBBdHRlbXB0aW5nIHRhc2sgXCIke3Rhc2tUeXBlfVwiIHdpdGggbW9kZWwgXCIke3RhcmdldE1vZGVsfVwiLiBBdHRlbXB0ICR7cmV0cmllcyArIDF9LyR7TUFYX1JFVFJJRVN9LmBcbiAgICApO1xuXG4gICAgLy8gLS0tIENPTkNFUFRVQUwgQUNUVUFMIE9QRU5BSSBTREsgQ09ERSAtLS1cbiAgICAvLyBUaGlzIGJsb2NrIHNpbXVsYXRlcyBob3cgdGhlIHJlYWwgY29kZSB3b3VsZCBsb29rLlxuICAgIHRyeSB7XG4gICAgICAvLyBjb25zdCBvcGVuYWkgPSB0aGlzLm9wZW5haSBhcyBPcGVuQUk7IC8vIFR5cGUgYXNzZXJ0aW9uIGZvciBjb25jZXB0dWFsIHVzZVxuICAgICAgY29uc29sZS5sb2coXG4gICAgICAgIGBbUmVhbExMTVNlcnZpY2VdIFByZXBhcmluZyBBUEkgY2FsbCB0byBtb2RlbDogJHt0YXJnZXRNb2RlbH0uIE1lc3NhZ2VzOmAsXG4gICAgICAgIEpTT04uc3RyaW5naWZ5KG1lc3NhZ2VzLCBudWxsLCAyKS5zdWJzdHJpbmcoMCwgNTAwKSArICcuLi4nXG4gICAgICApO1xuXG4gICAgICBjb25zdCByZXNwb25zZUZvcm1hdCA9IG9wdGlvbnM/LmlzSnNvbk91dHB1dFxuICAgICAgICA/IHsgdHlwZTogJ2pzb25fb2JqZWN0JyBhcyBjb25zdCB9XG4gICAgICAgIDogdW5kZWZpbmVkO1xuICAgICAgaWYgKHJlc3BvbnNlRm9ybWF0KSB7XG4gICAgICAgIGNvbnNvbGUubG9nKGBbUmVhbExMTVNlcnZpY2VdIFJlcXVlc3RpbmcgSlNPTiBvdXRwdXQgbW9kZS5gKTtcbiAgICAgIH1cblxuICAgICAgLy8gQ09OQ0VQVFVBTDogY29uc3QgY2hhdENvbXBsZXRpb24gPSBhd2FpdCBvcGVuYWkuY2hhdC5jb21wbGV0aW9ucy5jcmVhdGUoe1xuICAgICAgLy8gICBtZXNzYWdlczogbWVzc2FnZXMsXG4gICAgICAvLyAgIG1vZGVsOiB0YXJnZXRNb2RlbCxcbiAgICAgIC8vICAgdGVtcGVyYXR1cmU6IG9wdGlvbnM/LnRlbXBlcmF0dXJlID8/IChyZXNwb25zZUZvcm1hdCA/IDAuMiA6IDAuNyksXG4gICAgICAvLyAgIG1heF90b2tlbnM6IG9wdGlvbnM/Lm1heFRva2VucyA/PyAocmVzcG9uc2VGb3JtYXQgPyAxMDI0IDogNDAwKSxcbiAgICAgIC8vICAgLi4uKHJlc3BvbnNlRm9ybWF0ID8geyByZXNwb25zZV9mb3JtYXQ6IHJlc3BvbnNlRm9ybWF0IH0gOiB7fSksXG4gICAgICAvLyAgIC8vIHRpbWVvdXQ6IDMwMDAwLCAvLyBFeGFtcGxlOiAzMC1zZWNvbmQgdGltZW91dFxuICAgICAgLy8gfSk7XG5cbiAgICAgIC8vIFNJTVVMQVRJTkcgQSBTVUNDRVNTRlVMIFJFU1BPTlNFIEZPUiBUSEUgU0FLRSBPRiBTVFJVQ1RVUkVcbiAgICAgIC8vIElOIEEgUkVBTCBTQ0VOQVJJTywgVEhJUyBXT1VMRCBCRSBUSEUgQUNUVUFMIExMTSBSRVNQT05TRVxuICAgICAgbGV0IHNpbXVsYXRlZEFwaUNvbnRlbnRPYmplY3Q6IGFueSA9IHtcbiAgICAgICAgY29tbWVudDogYFRoaXMgaXMgYSBzaW11bGF0ZWQgc3VjY2Vzc2Z1bCBMTE0gSlNPTiByZXNwb25zZSBmb3IgdGFzayAke3Rhc2tUeXBlfWAsXG4gICAgICAgIGRhdGFfZnJvbV9wcm9tcHQ6IHN0cnVjdHVyZWRQcm9tcHQuZGF0YSwgLy8gSW5jbHVkZSBvcmlnaW5hbCBkYXRhIGZvciByZWZlcmVuY2VcbiAgICAgIH07XG5cbiAgICAgIC8vIFRhc2stc3BlY2lmaWMgc2ltdWxhdGVkIGNvbnRlbnRcbiAgICAgIHN3aXRjaCAodGFza1R5cGUpIHtcbiAgICAgICAgY2FzZSAnY3VzdG9tX2FuYWx5dGljYWxfYW5hbHlzaXMnOlxuICAgICAgICAgIHNpbXVsYXRlZEFwaUNvbnRlbnRPYmplY3QgPSB7XG4gICAgICAgICAgICAuLi5zaW11bGF0ZWRBcGlDb250ZW50T2JqZWN0LFxuICAgICAgICAgICAgaWRlbnRpZmllZEVudGl0aWVzOiBbXG4gICAgICAgICAgICAgICdzaW1fZW50aXR5X2FuYWx5dGljYWxfMScsXG4gICAgICAgICAgICAgICdzaW1fZW50aXR5X2FuYWx5dGljYWxfMicsXG4gICAgICAgICAgICBdLFxuICAgICAgICAgICAgZXhwbGljaXRUYXNrczogWydzaW1fdGFza19hbmFseXRpY2FsJ10sXG4gICAgICAgICAgICBsb2dpY2FsQ29uc2lzdGVuY3k6IHtcbiAgICAgICAgICAgICAgaXNDb25zaXN0ZW50OiB0cnVlLFxuICAgICAgICAgICAgICByZWFzb246ICdTaW11bGF0ZWQgYnkgUmVhbExMTVNlcnZpY2UgZm9yIEFuYWx5dGljYWxBZ2VudCcsXG4gICAgICAgICAgICB9LFxuICAgICAgICAgICAgcHJvYmxlbVR5cGU6ICdzaW11bGF0ZWRfYW5hbHl0aWNhbF9wcm9ibGVtJyxcbiAgICAgICAgICB9O1xuICAgICAgICAgIGJyZWFrO1xuICAgICAgICBjYXNlICdjdXN0b21fY3JlYXRpdmVfYW5hbHlzaXMnOlxuICAgICAgICAgIHNpbXVsYXRlZEFwaUNvbnRlbnRPYmplY3QgPSB7XG4gICAgICAgICAgICAuLi5zaW11bGF0ZWRBcGlDb250ZW50T2JqZWN0LFxuICAgICAgICAgICAgYWx0ZXJuYXRpdmVHb2FsczogWydzaW1fYWx0X2dvYWxfY3JlYXRpdmVfMSddLFxuICAgICAgICAgICAgbm92ZWxTb2x1dGlvbnNTdWdnZXN0ZWQ6IFsnc2ltX25vdmVsX3NvbHV0aW9uX2NyZWF0aXZlJ10sXG4gICAgICAgICAgICB1bnN0YXRlZEFzc3VtcHRpb25zOiBbJ3NpbV9hc3N1bXB0aW9uX2NyZWF0aXZlJ10sXG4gICAgICAgICAgICBwb3RlbnRpYWxFbmhhbmNlbWVudHM6IFsnc2ltX2VuaGFuY2VtZW50X2NyZWF0aXZlJ10sXG4gICAgICAgICAgICBhbWJpZ3VpdHlGbGFnczogW1xuICAgICAgICAgICAgICB7XG4gICAgICAgICAgICAgICAgdGVybTogJ3NpbV9hbWJpZ3VvdXNfdGVybV9jcmVhdGl2ZScsXG4gICAgICAgICAgICAgICAgcmVhc29uOiAnc2ltX3JlYXNvbl9jcmVhdGl2ZScsXG4gICAgICAgICAgICAgIH0sXG4gICAgICAgICAgICBdLFxuICAgICAgICAgIH07XG4gICAgICAgICAgYnJlYWs7XG4gICAgICAgIGNhc2UgJ2N1c3RvbV9wcmFjdGljYWxfYW5hbHlzaXMnOlxuICAgICAgICAgIHNpbXVsYXRlZEFwaUNvbnRlbnRPYmplY3QgPSB7XG4gICAgICAgICAgICAuLi5zaW11bGF0ZWRBcGlDb250ZW50T2JqZWN0LFxuICAgICAgICAgICAgY29udGV4dHVhbEZhY3RvcnM6IFsnc2ltX2NvbnRleHRfcHJhY3RpY2FsXzEnXSxcbiAgICAgICAgICAgIGZlYXNpYmlsaXR5QXNzZXNzbWVudDoge1xuICAgICAgICAgICAgICByYXRpbmc6ICdNZWRpdW0nLFxuICAgICAgICAgICAgICByZWFzb246ICdTaW11bGF0ZWQgYnkgUmVhbExMTVNlcnZpY2UgZm9yIFByYWN0aWNhbEFnZW50JyxcbiAgICAgICAgICAgICAgZGVwZW5kZW5jaWVzOiBbJ3NpbV9kZXBlbmRlbmN5X3ByYWN0aWNhbCddLFxuICAgICAgICAgICAgfSxcbiAgICAgICAgICAgIGVmZmljaWVuY3lUaXBzOiBbJ3NpbV90aXBfcHJhY3RpY2FsJ10sXG4gICAgICAgICAgICByZXNvdXJjZUltcGxpY2F0aW9uczoge1xuICAgICAgICAgICAgICB0aW1lRXN0aW1hdGU6ICdNb2RlcmF0ZScsXG4gICAgICAgICAgICAgIHRvb2xzTmVlZGVkOiBbJ3NpbV90b29sX3ByYWN0aWNhbCddLFxuICAgICAgICAgICAgfSxcbiAgICAgICAgICAgIGNvbW1vblNlbnNlVmFsaWRhdGlvbjoge1xuICAgICAgICAgICAgICBpc1ZhbGlkOiB0cnVlLFxuICAgICAgICAgICAgICByZWFzb246ICdTaW11bGF0ZWQgYnkgUmVhbExMTVNlcnZpY2UgZm9yIFByYWN0aWNhbEFnZW50JyxcbiAgICAgICAgICAgIH0sXG4gICAgICAgICAgfTtcbiAgICAgICAgICBicmVhaztcbiAgICAgICAgY2FzZSAnY3VzdG9tX2xlYWRfYWdlbnRfc3ludGhlc2lzJzogLy8gTmV3IGNhc2UgZm9yIE5MVUxlYWRBZ2VudCdzIHN5bnRoZXNpcyB0YXNrXG4gICAgICAgICAgc2ltdWxhdGVkQXBpQ29udGVudE9iamVjdCA9IHtcbiAgICAgICAgICAgIC4uLnNpbXVsYXRlZEFwaUNvbnRlbnRPYmplY3QsXG4gICAgICAgICAgICBwcmltYXJ5R29hbDogJ1NpbXVsYXRlZDogU2NoZWR1bGUgbWVldGluZyBhYm91dCBQcm9qZWN0IEFscGhhJyxcbiAgICAgICAgICAgIHByaW1hcnlHb2FsQ29uZmlkZW5jZTogMC44NSxcbiAgICAgICAgICAgIGlkZW50aWZpZWRUYXNrczogW1xuICAgICAgICAgICAgICAnQ2hlY2sgY2FsZW5kYXIgZm9yIFVzZXIgQScsXG4gICAgICAgICAgICAgICdGaW5kIGNvbW1vbiBhdmFpbGFiaWxpdHkgd2l0aCBVc2VyIEInLFxuICAgICAgICAgICAgICAnU2VuZCBtZWV0aW5nIGludml0ZScsXG4gICAgICAgICAgICBdLFxuICAgICAgICAgICAgZXh0cmFjdGVkUGFyYW1ldGVyczoge1xuICAgICAgICAgICAgICBwcm9qZWN0OiAnUHJvamVjdCBBbHBoYScsXG4gICAgICAgICAgICAgIGF0dGVuZGVlczogWydVc2VyIEEnLCAnVXNlciBCJ10sXG4gICAgICAgICAgICAgIHJlYXNvbl9mb3JfbWVldGluZzogJ0Rpc2N1c3MgUTQgcm9hZG1hcCcsXG4gICAgICAgICAgICB9LFxuICAgICAgICAgICAgc3VnZ2VzdGVkTmV4dEFjdGlvbjoge1xuICAgICAgICAgICAgICBhY3Rpb25UeXBlOiAnaW52b2tlX3NraWxsJyxcbiAgICAgICAgICAgICAgc2tpbGxJZDogJ0NhbGVuZGFyU2tpbGwnLFxuICAgICAgICAgICAgICByZWFzb246XG4gICAgICAgICAgICAgICAgJ0hpZ2ggY29uZmlkZW5jZSBnb2FsIHRvIHNjaGVkdWxlIGEgbWVldGluZywgYW5hbHl0aWNhbCB0YXNrcyBhcmUgY2xlYXIsIHByYWN0aWNhbCBhc3Nlc3NtZW50IGlzIHBvc2l0aXZlIChzaW11bGF0ZWQpLicsXG4gICAgICAgICAgICAgIGRpcmVjdEFjdGlvbkRldGFpbHM6IG51bGwsIC8vIE9yIHByb3ZpZGUgaWYgYWN0aW9uVHlwZSB3YXMgcGVyZm9ybV9kaXJlY3RfYWN0aW9uXG4gICAgICAgICAgICAgIGNsYXJpZmljYXRpb25RdWVzdGlvbjogbnVsbCwgLy8gT3IgcHJvdmlkZSBpZiBhY3Rpb25UeXBlIHdhcyBjbGFyaWZ5X3F1ZXJ5XG4gICAgICAgICAgICB9LFxuICAgICAgICAgIH07XG4gICAgICAgICAgYnJlYWs7XG4gICAgICAgIGRlZmF1bHQ6IC8vIEdlbmVyaWMgZmFsbGJhY2sgZm9yIG90aGVyIHRhc2tzIChlLmcuIG9yaWdpbmFsIExMTVRhc2tUeXBlcyBub3QgaGFuZGxlZCBhYm92ZSlcbiAgICAgICAgICBzaW11bGF0ZWRBcGlDb250ZW50T2JqZWN0ID0ge1xuICAgICAgICAgICAgLi4uc2ltdWxhdGVkQXBpQ29udGVudE9iamVjdCxcbiAgICAgICAgICAgIGdlbmVyaWNGaWVsZDpcbiAgICAgICAgICAgICAgJ0dlbmVyaWMgc2ltdWxhdGVkIGNvbnRlbnQgZm9yIG90aGVyIHRhc2tzIChlLmcuLCBlbWFpbCBjYXRlZ29yaXphdGlvbiknLFxuICAgICAgICAgIH07XG4gICAgICAgICAgYnJlYWs7XG4gICAgICB9XG4gICAgICBjb25zdCBzaW11bGF0ZWRBcGlDb250ZW50ID0gSlNPTi5zdHJpbmdpZnkoc2ltdWxhdGVkQXBpQ29udGVudE9iamVjdCk7XG5cbiAgICAgIC8vIFNpbXVsYXRlIHRva2VuIHVzYWdlIGJhc2VkIG9uIHByb21wdCBhbmQgY29udGVudCBsZW5ndGggZm9yIG1vcmUgcmVhbGlzbVxuICAgICAgY29uc3QgcHJvbXB0VG9rZW5zID0gTWF0aC5jZWlsKEpTT04uc3RyaW5naWZ5KG1lc3NhZ2VzKS5sZW5ndGggLyA0KTsgLy8gUm91Z2ggZXN0aW1hdGVcbiAgICAgIGNvbnN0IGNvbXBsZXRpb25Ub2tlbnMgPSBNYXRoLmNlaWwoc2ltdWxhdGVkQXBpQ29udGVudC5sZW5ndGggLyA0KTsgLy8gUm91Z2ggZXN0aW1hdGVcbiAgICAgIGNvbnN0IHNpbXVsYXRlZFVzYWdlID0ge1xuICAgICAgICBwcm9tcHRUb2tlbnMsXG4gICAgICAgIGNvbXBsZXRpb25Ub2tlbnMsXG4gICAgICAgIHRvdGFsVG9rZW5zOiBwcm9tcHRUb2tlbnMgKyBjb21wbGV0aW9uVG9rZW5zLFxuICAgICAgfTtcblxuICAgICAgLy8gY29uc3QgY29udGVudCA9IGNoYXRDb21wbGV0aW9uLmNob2ljZXNbMF0/Lm1lc3NhZ2U/LmNvbnRlbnQ7XG4gICAgICAvLyBjb25zdCB1c2FnZSA9IGNoYXRDb21wbGV0aW9uLnVzYWdlOyAvLyBBZGFwdCBiYXNlZCBvbiBhY3R1YWwgU0RLIHN0cnVjdHVyZVxuXG4gICAgICAvLyBSZW1vdmUgdGhpcyBzaW11bGF0aW9uIGJsb2NrIHdoZW4gdXNpbmcgcmVhbCBTREtcbiAgICAgIGNvbnN0IGNvbnRlbnQgPSBzaW11bGF0ZWRBcGlDb250ZW50O1xuICAgICAgY29uc3QgdXNhZ2UgPSBzaW11bGF0ZWRVc2FnZTtcblxuICAgICAgaWYgKGNvbnRlbnQpIHtcbiAgICAgICAgY29uc29sZS5sb2coXG4gICAgICAgICAgYFtSZWFsTExNU2VydmljZV0gVGFzayBcIiR7dGFza1R5cGV9XCIgc3VjY2Vzc2Z1bCBmb3IgbW9kZWwgXCIke3RhcmdldE1vZGVsfVwiLmBcbiAgICAgICAgKTtcbiAgICAgICAgcmV0dXJuIHtcbiAgICAgICAgICBzdWNjZXNzOiB0cnVlLFxuICAgICAgICAgIGNvbnRlbnQ6IGNvbnRlbnQsXG4gICAgICAgICAgdXNhZ2U6IHVzYWdlXG4gICAgICAgICAgICA/IHtcbiAgICAgICAgICAgICAgICBwcm9tcHRUb2tlbnM6IHVzYWdlLnByb21wdFRva2VucyxcbiAgICAgICAgICAgICAgICBjb21wbGV0aW9uVG9rZW5zOiB1c2FnZS5jb21wbGV0aW9uVG9rZW5zLFxuICAgICAgICAgICAgICAgIHRvdGFsVG9rZW5zOiB1c2FnZS50b3RhbFRva2VucyxcbiAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgOiB1bmRlZmluZWQsXG4gICAgICAgIH07XG4gICAgICB9IGVsc2Uge1xuICAgICAgICBjb25zb2xlLmVycm9yKFxuICAgICAgICAgIGBbUmVhbExMTVNlcnZpY2VdIFRhc2sgXCIke3Rhc2tUeXBlfVwiIGZvciBtb2RlbCBcIiR7dGFyZ2V0TW9kZWx9XCIgc3VjY2VlZGVkIGJ1dCBjb250ZW50IGlzIG1pc3NpbmcuYFxuICAgICAgICApO1xuICAgICAgICByZXR1cm4ge1xuICAgICAgICAgIHN1Y2Nlc3M6IGZhbHNlLFxuICAgICAgICAgIGVycm9yOiAnQVBJIGNhbGwgc3VjY2VlZGVkIGJ1dCBjb250ZW50IGlzIG1pc3NpbmcuJyxcbiAgICAgICAgfTtcbiAgICAgIH1cbiAgICB9IGNhdGNoIChlcnJvcjogYW55KSB7XG4gICAgICBjb25zb2xlLmVycm9yKFxuICAgICAgICBgW1JlYWxMTE1TZXJ2aWNlXSBFcnJvciBkdXJpbmcgQVBJIGNhbGwgZm9yIHRhc2sgXCIke3Rhc2tUeXBlfVwiLCBtb2RlbCBcIiR7dGFyZ2V0TW9kZWx9XCI6YCxcbiAgICAgICAgZXJyb3IubWVzc2FnZVxuICAgICAgKTtcbiAgICAgIC8vIENvbmNlcHR1YWwgcmV0cnkgbG9naWNcbiAgICAgIGlmIChcbiAgICAgICAgZXJyb3Iuc3RhdHVzID09PSA0MjkgfHxcbiAgICAgICAgZXJyb3IuY29kZSA9PT0gJ3JhdGVfbGltaXRfZXhjZWVkZWQnIHx8XG4gICAgICAgIGVycm9yLmNvZGUgPT09ICdpbnN1ZmZpY2llbnRfcXVvdGEnXG4gICAgICApIHtcbiAgICAgICAgLy8gRXhhbXBsZSBlcnJvciBjb2Rlc1xuICAgICAgICBpZiAocmV0cmllcyA8IE1BWF9SRVRSSUVTKSB7XG4gICAgICAgICAgcmV0cmllcysrO1xuICAgICAgICAgIGNvbnN0IGRlbGF5ID0gSU5JVElBTF9SRVRSWV9ERUxBWV9NUyAqIE1hdGgucG93KDIsIHJldHJpZXMgLSAxKTtcbiAgICAgICAgICBjb25zb2xlLmxvZyhcbiAgICAgICAgICAgIGBbUmVhbExMTVNlcnZpY2VdIFJhdGUgbGltaXQgLyBRdW90YSBlcnJvci4gUmV0cnlpbmcgYXR0ZW1wdCAke3JldHJpZXMgKyAxfS8ke01BWF9SRVRSSUVTfSBpbiAke2RlbGF5fW1zLi4uYFxuICAgICAgICAgICk7XG4gICAgICAgICAgYXdhaXQgbmV3IFByb21pc2UoKHJlc29sdmUpID0+IHNldFRpbWVvdXQocmVzb2x2ZSwgZGVsYXkpKTtcbiAgICAgICAgICAvLyBJbiBhIHJlYWwgcmVjdXJzaXZlL2xvb3AgcmV0cnksIHlvdSdkIGNhbGwgdGhpcy5nZW5lcmF0ZSBvciB0aGUgY29yZSBBUEkgbG9naWMgYWdhaW4uXG4gICAgICAgICAgLy8gRm9yIHRoaXMgc3RydWN0dXJhbCBleGFtcGxlLCB3ZSdsbCBqdXN0IHJldHVybiB0aGUgZXJyb3IgYWZ0ZXIgZmlyc3QgdHJ1ZSBhdHRlbXB0LlxuICAgICAgICAgIHJldHVybiB7XG4gICAgICAgICAgICBzdWNjZXNzOiBmYWxzZSxcbiAgICAgICAgICAgIGVycm9yOiBgQVBJIEVycm9yIChhZnRlciAke3JldHJpZXN9IHJldHJpZXMpOiAke2Vycm9yLm1lc3NhZ2V9IChSZXRyeWFibGUgZXJyb3IsIGJ1dCByZXRyaWVzIG5vdCBmdWxseSBpbXBsZW1lbnRlZCBpbiBzdHViKWAsXG4gICAgICAgICAgfTtcbiAgICAgICAgfVxuICAgICAgICByZXR1cm4ge1xuICAgICAgICAgIHN1Y2Nlc3M6IGZhbHNlLFxuICAgICAgICAgIGVycm9yOiBgQVBJIEVycm9yIChNYXggcmV0cmllcyByZWFjaGVkIGZvciByZXRyeWFibGUgZXJyb3IpOiAke2Vycm9yLm1lc3NhZ2V9YCxcbiAgICAgICAgfTtcbiAgICAgIH1cbiAgICAgIC8vIE5vbi1yZXRyeWFibGUgZXJyb3JcbiAgICAgIHJldHVybiB7XG4gICAgICAgIHN1Y2Nlc3M6IGZhbHNlLFxuICAgICAgICBlcnJvcjogYEFQSSBFcnJvcjogJHtlcnJvci5tZXNzYWdlIHx8ICdVbmtub3duIEFQSSBlcnJvcid9YCxcbiAgICAgIH07XG4gICAgfVxuICAgIC8vIC0tLSBFTkQgQ09OQ0VQVFVBTCBBQ1RVQUwgT1BFTkFJIFNESyBDT0RFIC0tLVxuICB9XG59XG4iXX0=