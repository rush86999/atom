export declare const simplifyUserInputPrompt = "\n    Given user input, simplify the input into 1-action many statements. Format the reponse in JSON format with key \"actions\".\n";
export declare const simplifyUserInputExampleInput1 = "\n    schedule a meeting for monday and create a task to write presentation   \n";
export declare const simplifyUserInputExampleOutput1 = "\n    { \"actions\": [ \"schedule a meeting for Monday\", \"create a task to write presentation\" ] }\n";
export declare const simplifyUserInputExampleInput2 = "\nschedule a meeting with Joe on Wednesday for his marketing presentation. Use zoom for the meeting.\n";
export declare const simplifyUserInputExampleOutput2 = "\n{\n    \"actions\": [\n      \"Schedule a meeting with Joe on Wednesday for his marketing presentation using Zoom.\"\n    ]\n  }\n  \n";
