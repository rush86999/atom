export const agendaPrompt = `
    Create an agenda for a meeting. The agenda should be a list. You will be given the main topic, relevant important points and / or goals that should be included and you can add more if needed. Please make it formal. Allocate approximate times for each topic and subtopic. Do not provide a template or example.
`;
export const agendaPromptExampleInput = `Main topic: Atom see investement
Relevant points: Atom Investment Strategy, Reinventing the Calendar, Your calendar is the ultimates project management tool.
Goals: Get investors, Get marketing budget, Sell more subscriptions for Atomic.`;

export const agendaPromptExampleOutput = `
Agenda:
1. Introduction (5 minutes) 
2. Atom Investment Strategy (30 minutes)
    a. Overview of subscription base (5 minutes) 
    b. Presentation of growth plans (15 minutes) 
    c. Development of strategies to attract investors (10 minutes)
3. Reinventing the Calendar (30 minutes) 
    a. How Atomic has revolutionized the Calendar (10 minutes) 
    b. Features, Benefits and Advantages to using the Atomic Calendar (10 minutes) 
    c. Discussion of key marketing strategies (10 minutes) 
4. Subscription Sales and Growth (20 minutes) 
    a. Presentation of the benefits of Atomic Subscriptions (10 minutes)
    b. Outline of growth strategies for subscription sales (10 minutes)
5. Questions, Open Discussion and Summary (10 minutes)
`;
// provide main topic and list of topics to cover

export const summaryPrompt = `
   Create a summary from the events provided.

`;

export const taskBreakDownPrompt = `
    Given a task, break it down into smaller individual tasks that are manageable in smaller chunks of time. Also provide approximate time for each.
`;

export const meetingRequestPrompt = `
    Write an email to request a meeting to a very important person. Details will be provided about  who the person is and what they do. Also, if any, other characteristics that are relevant. Also who the user is, what the user does and why the user is requesting the appointment. Do not provide a template or example. Do not provide generic advice until the details are provided.
`;

export const meetingRequestWithAvailabilityPrompt = `
    Write an email to request a meeting to a very important person. Details will be provided about who the person is and what they do. Also, if any, other characteristics that are relevant. Also who the user is, what he/she does,  why the user is requesting the appointment. Do not provide a template or example. Do not provide generic advice until the details are provided.
`;

export const summarizeAvailabilityPrompt = `
    The user will give you his/her availability time slots generated from the calendar using code. Rewrite the availability in a more simple and concise terms. Write the response in first person as if conveying the information to a third party. Do not make up availability or hallucinate. Do not provide any availability until information is provided to you.
`;
export const summarizeAvailabilityExampleInput = `02/20/2023 - 8:00 AM - 8:30 AM, 8:30 AM - 9:00 AM, 9:00 AM - 9:30 AM, 9:30 AM - 10:00 AM, 10:00 AM - 10:30 AM, 10:30 AM - 11:00 AM, 11:00 AM - 11:30 AM, 11:30 AM - 12:00 PM, 12:00 PM - 12:30 PM, 12:30 PM - 1:00 PM`;
export const summarizeAvailabilityExampleOutput = `On February 20, I'm available from 8:00 AM to 1:00 PM.
`;
export const summarizeAvailabilityResponsesPrompt = `The user will provide his/her availability. Rewrite the availability in a more simple and concise terms. Write the response in first person as if conveying the information to a third party. Do not make up availability or hallucinate. Do not provide any availability until information is provided to you.`;

export const summarizeAvailabilityResponsesPromptExampleInput = `On February 19, I'm available from 7:00 AM to 10:30 PM. On February 20, I'm available from 6:00 AM to 12:00 PM and from 3:00 PM to 10:00 PM.`;

export const summarizeAvailabilityResponsesPromptExampleOutput = `I'm available on February 19 from 7:00 AM to 10:30 PM, and on February 20 from 6:00 AM to 12:00 PM and from 3:00 PM to 10:00 PM.`;

export const howToTaskPrompt = `
    Help the user figure out how to do this task.
`;

export const dailySchedulePrompt1 = `
    Give a minute by minute schedule for an 
`; // 8 hour work day where

export const dailySchedulePrompt2 = `
    hour work day where the user starts the day at
`;

export const dailySchedulePrompt3 = `Choose an appropriate time given the task. Give the respone in JSON array format with keys 'start_time', 'end_time', and 'task'.
`;

export const dailyScheduleExampleInput = `Exercise,`;

export const dailyScheduleExampleOutput = `[{ "start_time": "8:00 AM", "end_time": "8:45 AM", "task": "Exercise"}]`;
