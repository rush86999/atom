// Mock LLM function - to be used by multiple skills

/**
 * Simulates a call to a Large Language Model.
 * Behavior is based on keywords in the prompt to mimic different LLM tasks.
 * @param prompt The prompt string for the LLM.
 * @param model The model identifier (e.g., 'cheapest', 'balanced', 'powerful').
 * @returns A Promise resolving to the LLM's string response.
 */
export async function invokeLLM(prompt: string, model: string): Promise<string> {
  console.log(`[Mock LLM Utility] Received prompt for model "${model}":\n"${prompt.substring(0, 200)}..."`); // Log snippet

  // Simulate LLM behavior for email categorization
  if (prompt.includes("Categorize this email")) {
    const promptLower = prompt.toLowerCase();
    if (promptLower.includes("urgent") || promptLower.includes("critical system outage")) {
      return JSON.stringify({ category: "Urgent", confidence: 0.92 });
    } else if (promptLower.includes("action required") || promptLower.includes("please review") || promptLower.includes("task for you")) {
      return JSON.stringify({ category: "ActionRequired", confidence: 0.85 });
    } else if (promptLower.includes("meeting invite") || promptLower.includes("calendar invite") || promptLower.includes(".ics")) {
      return JSON.stringify({ category: "MeetingInvite", confidence: 0.95 });
    } else if (promptLower.includes("fyi") || promptLower.includes("update on") || promptLower.includes("heads up")) {
      return JSON.stringify({ category: "FYI", confidence: 0.78 });
    } else if (promptLower.includes("win a free") || promptLower.includes("limited time offer")) {
        return JSON.stringify({ category: "Spam", confidence: 0.99 });
    }
    return JSON.stringify({ category: "Other", confidence: 0.45 });
  }

  // Simulate LLM behavior for email summarization
  if (prompt.startsWith("Summarize this email")) {
    const subjectMatch = prompt.match(/Subject: "([^"]*)"/);
    const mockSubject = subjectMatch ? subjectMatch[1] : "this email";
    return `LLM Summary: Key information from "${mockSubject}" suggests it's about [topic] and requires [action/attention].`;
  }

  // Simulate LLM behavior for suggested email replies
  if (prompt.includes("Suggest a brief, polite, and professional reply")) {
    const promptLower = prompt.toLowerCase();
    if (promptLower.includes('category: "urgent"')) {
      return "Acknowledged. We are looking into this with high priority and will update you shortly.";
    } else if (promptLower.includes('category: "actionrequired"')) {
      if (promptLower.includes("identified action items:")) {
        const actionItemMatch = prompt.match(/Identified Action Items: "([^;"]*)/);
        const firstAction = actionItemMatch ? actionItemMatch[1] : "the main request";
        return `Understood. I will address the action items, starting with: "${firstAction}".`;
      }
      return "Received. I'll take care of the necessary actions.";
    } else if (promptLower.includes('category: "meetinginvite"')) {
      return "Thanks for the invite! I'll check my availability and respond through the calendar system.";
    } else if (promptLower.includes('category: "fyi"')) {
      return "No reply needed.";
    } else if (promptLower.includes('category: "spam"')) {
      return "No reply needed.";
    } else if (promptLower.includes('category: "other"')) {
      return "Thank you for your email. I will review it and get back to you if a response is needed.";
    }
    return "Thanks for your email.";
  }

  // Simulate LLM behavior for email action item extraction
  if (prompt.includes("Extract action items")) {
    const promptBodyLower = prompt.substring(prompt.indexOf("Email Body:")).toLowerCase();
    const extractedActions: string[] = [];
    if (promptBodyLower.includes("please send the report") || promptBodyLower.includes("can you prepare the document")) {
      extractedActions.push("Send the report", "Prepare the document");
    }
    if (promptBodyLower.includes("schedule a meeting") && promptBodyLower.includes("discuss the proposal")) {
      extractedActions.push("Schedule a meeting to discuss the proposal");
    }
    if (promptBodyLower.includes("confirm your availability")) {
      extractedActions.push("Confirm availability");
    }
    if (promptBodyLower.includes("let me know what you think")) {
      extractedActions.push("Provide feedback or thoughts.");
    }
    if (extractedActions.length > 0) {
      return JSON.stringify({ actionItems: extractedActions.slice(0,2) });
    }
    return JSON.stringify({ actionItems: [] });
  }

  // Simulate LLM behavior for document snippet extraction
  if (prompt.includes("extract up to") && prompt.includes("relevant snippets")) {
    const queryMatch = prompt.match(/query '([^']*)'/);
    const query = queryMatch ? queryMatch[1] : "the topic";
    // Basic simulation: if document text (also in prompt) contains query words.
    // This is a very rough check.
    if (prompt.toLowerCase().includes(query.split(" ")[0].toLowerCase())) { // check first word of query
        return JSON.stringify({ snippets: [`Mock snippet about "${query}".`, `Further details on "${query}" from the document.`] });
    }
    return JSON.stringify({ snippets: [] });
  }

  // Simulate LLM behavior for document summarization (based on query & snippets/title)
  if (prompt.includes("provide a") && prompt.includes("summary") && (prompt.includes("these snippets") || prompt.includes("Document Title"))) {
    const queryMatch = prompt.match(/query '([^']*)'/);
    const query = queryMatch ? queryMatch[1] : "the main subject";
    const lengthMatch = prompt.match(/provide a '([^']*)' summary/);
    const length = lengthMatch ? lengthMatch[1] : "medium";
    return `This is a mock ${length} summary regarding "${query}", based on the provided text.`;
  }

  // Simulate LLM for overall summarization of summaries
  if (prompt.startsWith("Summarize these individual summaries")) {
    const queryMatch = prompt.match(/answer to '([^']*)'/);
    const query = queryMatch ? queryMatch[1] : "the user's query";
    return `This is an overall synthesized mock summary for the query "${query}", based on multiple pieces of information.`;
  }

  // --- Additions for LearningAndGuidanceSkill ---

  // Query Classification for GuidanceType
  if (prompt.includes("Classify this query into GuidanceType")) {
    const queryMatch = prompt.match(/query: "([^"]*)"/i);
    const userQuery = queryMatch ? queryMatch[1].toLowerCase() : "";
    if (userQuery.includes("how to") || userQuery.includes("steps for") || userQuery.includes("tutorial for")) {
      return JSON.stringify({ guidanceType: "find_tutorial" });
    } else if (userQuery.includes("what is") || userQuery.includes("explain") || userQuery.includes("tell me about")) {
      return JSON.stringify({ guidanceType: "general_explanation" });
    } else if (userQuery.includes("guide me through") || userQuery.includes("workflow for")) {
      return JSON.stringify({ guidanceType: "guide_workflow" });
    }
    return JSON.stringify({ guidanceType: "answer_question" });
  }

  // Answering Questions from Text
  if (prompt.includes("Using ONLY the provided text, answer the question:")) {
    const queryMatch = prompt.match(/question: '([^']*)'/i);
    const userQuery = queryMatch ? queryMatch[1] : "the question";
    const textMatch = prompt.match(/Provided text: '([^']*)'/i);
    const articleTextSnippet = textMatch ? textMatch[1] : "";

    // Simple check if any word from query (split, lowercase) is in text snippet
    const queryWords = userQuery.toLowerCase().split(/\s+/).filter(w => w.length > 2);
    if (queryWords.some(qw => articleTextSnippet.toLowerCase().includes(qw))) {
      return `Based on the text, the answer to '${userQuery}' is [mocked detail: ${articleTextSnippet.substring(0, 70)}...].`;
    }
    return `The provided text does not appear to contain a direct answer to your question about '${userQuery}'.`;
  }

  // Extracting Steps (JSON) from Instructional Text
  if (prompt.includes("Extract the key steps for") && prompt.includes("Return as a JSON object")) {
    const textMatch = prompt.match(/tutorial text: '([^']*)'/i);
    const articleTextSnippet = textMatch ? textMatch[1].toLowerCase() : "";
    if (articleTextSnippet.includes("step 1") || articleTextSnippet.includes("firstly") || articleTextSnippet.includes("1.")) {
      return JSON.stringify({ steps: [{title: "Mock Step 1: Initialize", description: "First, initialize the system components based on the provided text."}, {title: "Mock Step 2: Configure", description: "Next, configure the main parameters as detailed in the article."}] });
    }
    return JSON.stringify({ steps: [] });
  }

  // Summarizing Text for Explanation
  if (prompt.includes("Provide a concise explanation regarding") && prompt.includes("based on the following text")) {
    const queryMatch = prompt.match(/regarding '([^']*)'/i);
    const userQuery = queryMatch ? queryMatch[1] : "the topic";
    const textMatch = prompt.match(/following text: '([^']*)'/i);
    const articleTextSnippet = textMatch ? textMatch[1] : "the provided content";
    return `This is a mock explanation regarding '${userQuery}'. The provided text mentions '${articleTextSnippet.substring(0,50)}...' and covers aspects like X, Y, and Z.`;
  }

  // Generating Follow-up Learning Suggestions
  if (prompt.includes("suggest two distinct, related topics")) {
    const articleTitleMatch = prompt.match(/guidance on '([^']*)'/i);
    const articleTitle = articleTitleMatch ? articleTitleMatch[1] : "this topic";
    const queryMatch = prompt.match(/query '([^']*)'/i);
    const userQuery = queryMatch ? queryMatch[1] : "your initial question";

    return JSON.stringify({ suggestions: [`Explore advanced "widgets" for ${articleTitle.split(" ").pop()}`, `Find tutorials on integrating ${userQuery.split(" ").pop()} with other tools.`] });
  }

  console.warn(`[Mock LLM Utility] Unhandled prompt type. Prompt (start): ${prompt.substring(0,150)}...`);
  return "LLM fallback response: Unable to process this specific type of request.";
}
