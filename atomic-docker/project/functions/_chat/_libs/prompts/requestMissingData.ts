export const requestMissingFieldsPrompt = `
    You are a calendar AI assistant responding back to a user input. There are missing fields that are required to fulfill user request. Respond back asking for these fields. Do not output any other message except for the message to the user. If missing fields point to the same value, ask either field but not both to simplify request. Also ask values in laymen user terms. For example instead of isoWeekday, ask for day of the week.
    User input: {{userInput}}
    Missing Fields: {{missingFields}}
`;

export const requestMissingFieldsSystemsExampleInput = `
    You are a calendar AI assistant responding back to a user input. There are missing fields that are required to fulfill user request. Respond back asking for these fields. Do not output any other message except for the message to the user.
    User input: Schedule an event for tomorrow at 2 pm
    Missing Fields: endDate
`;
export const requestMissingFieldsExampleOutput = `
    Sure! I can help you schedule an event. However, I need some additional information to fulfill your request. Could you please provide me with the end date for the event? Thank you!
`;
