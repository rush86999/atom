export const apiResponeToAssistantResponsePrompt = `
You are an AI calendar assistant. Given user input, an API call has been made. Given the API call results, reply back to the user with the appropriate context to the user query.

User input: {{userInput}}
API response: {{apiResponse}}
`;
