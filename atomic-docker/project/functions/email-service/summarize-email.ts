import { OpenAI } from 'openai';
import { getUserLlmModel } from '../_utils/userService';

const openai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY,
});

export async function summarizeEmail(
  userId: string,
  emailContent: string
): Promise<string> {
  const model = (await getUserLlmModel(userId)) || 'gpt-3.5-turbo';
  const response = await openai.chat.completions.create({
    model,
    messages: [
      {
        role: 'system',
        content:
          'Summarize the following email content. The summary should be concise and capture the main points of the email.',
      },
      {
        role: 'user',
        content: emailContent,
      },
    ],
  });

  return response.choices[0].message.content;
}
