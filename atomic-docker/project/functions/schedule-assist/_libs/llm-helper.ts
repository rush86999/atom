import { Configuration, OpenAIApi } from "openai";

const configuration = new Configuration({
  apiKey: process.env.OPENAI_API_KEY,
});
const openai = new OpenAIApi(configuration);

export const parseUserRequest = async (request: string) => {
  const response = await openai.createChatCompletion({
    model: "gpt-3.5-turbo",
    messages: [
      {
        role: "system",
        content:
          "You are a helpful assistant that parses user requests for scheduling meetings. The user will provide a request in natural language, and you should extract the following information: the attendees, the duration of the meeting, and the topic of the meeting. You should return this information as a JSON object.",
      },
      {
        role: "user",
        content: request,
      },
    ],
  });

  const content = response.data.choices[0].message.content;

  try {
    return JSON.parse(content);
  } catch (error) {
    // If the response is not valid JSON, we'll try to extract the information using a regular expression.
    const attendees = /attendees: (.*)/.exec(content)?.[1];
    const duration = /duration: (.*)/.exec(content)?.[1];
    const topic = /topic: (.*)/.exec(content)?.[1];

    if (attendees && duration && topic) {
      return {
        attendees: attendees.split(",").map((s) => s.trim()),
        duration,
        topic,
      };
    } else {
      throw new Error("Unable to parse user request");
    }
  }
};
