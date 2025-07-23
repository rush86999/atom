import { OpenAI } from 'openai';

const openai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY,
});

export async function summarizeEmail(emailContent: string): Promise<string> {
  const response = await openai.chat.completions.create({
    model: 'gpt-3.5-turbo',
    messages: [
      {
        role: 'system',
        content: 'Summarize the following email content. The summary should be concise and capture the main points of the email.',
      },
      {
        role: 'user',
        content: emailContent,
      },
    ],
  });

  return response.choices[0].message.content;
}
