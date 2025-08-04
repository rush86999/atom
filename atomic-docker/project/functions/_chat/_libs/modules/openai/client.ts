// OpenAI Client Module
import OpenAI from "openai";
import { defaultOpenAIAPIKey } from "../../../constants";

const openai = new OpenAI({
  apiKey: defaultOpenAIAPIKey,
} as any);

// Vector operations
export const convertEventTitleToOpenAIVector = async (title: string): Promise<number[] | null> => {
  try {
    if (!title?.trim()) return null;

    const response = await openai.embeddings.create({
      model: 'text-embedding-ada-002',
      input: title,
    });

    return response.data[0]?.embedding || null;
  } catch (error) {
    console.error('Error creating vector from title:', error);
    return null;
  }
};

// Chat completion operations
export const callOpenAIWithMessageHistory = async (messages: any[], model: string = 'gpt-3.5-turbo') => {
  try {
    const response = await openai.chat.completions.create({
      model,
      messages,
    });
    return response.choices[0]?.message?.content;
  } catch (error) {
    console.error('Error calling OpenAI:', error);
    return null;
  }
};

export { openai };

// Legacy function export for backwards compatibility
export const callOpenAI = callOpenAIWithMessageHistory;
