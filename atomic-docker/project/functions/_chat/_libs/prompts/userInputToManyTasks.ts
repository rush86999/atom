export const simplifyUserInputPrompt = `
    Given user input, simplify the input into 1-action many statements. Format the reponse in JSON format with key "actions".
`;

export const simplifyUserInputExampleInput1 = `
    schedule a meeting for monday and create a task to write presentation   
`;

export const simplifyUserInputExampleOutput1 = `
    { "actions": [ "schedule a meeting for Monday", "create a task to write presentation" ] }
`;

export const simplifyUserInputExampleInput2 = `
schedule a meeting with Joe on Wednesday for his marketing presentation. Use zoom for the meeting.
`;

export const simplifyUserInputExampleOutput2 = `
{
    "actions": [
      "Schedule a meeting with Joe on Wednesday for his marketing presentation using Zoom."
    ]
  }
  
`;
