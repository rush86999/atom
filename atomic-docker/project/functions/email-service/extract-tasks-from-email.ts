import { OpenAI } from 'openai';

const openai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY,
});

export async function extractTasksFromEmail(emailContent: string): Promise<string[]> {
  const response = await openai.chat.completions.create({
    model: 'gpt-3.5-turbo',
    messages: [
      {
        role: 'system',
        content: 'Extract the action items or tasks from the following email content. Return the tasks as a JSON array of strings. For example: ["Task 1", "Task 2"]',
      },
      {
        role: 'user',
        content: emailContent,
      },
    ],
  });

  const tasks = JSON.parse(response.choices[0].message.content);
  return tasks;
}
