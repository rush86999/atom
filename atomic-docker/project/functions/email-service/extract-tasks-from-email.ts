import { OpenAI } from 'openai';
import { getUserLlmModel } from '../_utils/userService';

const openai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY,
});

export async function extractTasksFromEmail(userId: string, emailContent: string): Promise<string[]> {
  const model = await getUserLlmModel(userId) || 'gpt-3.5-turbo';
  const response = await openai.chat.completions.create({
    model,
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
