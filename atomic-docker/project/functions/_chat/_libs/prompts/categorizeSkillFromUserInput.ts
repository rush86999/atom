export const categorizeSkillFromUserInputPrompt = `
You are an AI calendar assistant. You have a set of skills to work as an AI calendar assistant. Given user input, find out which skill to use based on skill name. Provide the 1 word answer with the name of the skill or 'none' if the user input does not match any. The list of options include: 'ask-availability' | 'find-event' | 'find-events' | 'find-next-event' | 'add-task' | 'block-off-time' | 'cancel-meeting' | 'create-event' |'delete-event' | 'delete-priority' | 'delete-task' | 'edit-add-preferred-time-to-preferred-times' | 'edit-event' | 'edit-remove-preferred-time-to-preferred-times' | 'find-meeting-time-with-permission' | 'generate-meeting-invite' | 'remove-all-preferred-times' | 'resolve-conflicting-events' | 'schedule-meeting' | 'send-meeting-invite' | 'update-meeting' | 'update-priority' | 'update-task'
`;

export const categorizeSkillFromUserInputTemplate = `
user input: {{userInput}}
`;

export const categorizeSkillFromUserInputExampleInput = `
    Remove a preferred Day from the list of preferred times for [task or event]. The preferred Day to remove is [Day].
`;

export const categorizeSkillFromUserInputExampleOutput = `edit-remove-preferred-time-to-preferred-times`;
