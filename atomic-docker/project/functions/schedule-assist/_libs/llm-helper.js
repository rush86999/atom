import { Configuration, OpenAIApi } from 'openai';
const configuration = new Configuration({
    apiKey: process.env.OPENAI_API_KEY,
});
const openai = new OpenAIApi(configuration);
export const parseUserRequest = async (request) => {
    const response = await openai.createChatCompletion({
        model: 'gpt-3.5-turbo',
        messages: [
            {
                role: 'system',
                content: 'You are a helpful assistant that parses user requests for scheduling meetings. The user will provide a request in natural language, and you should extract the following information: the attendees, the duration of the meeting, and the topic of the meeting. You should return this information as a JSON object.',
            },
            {
                role: 'user',
                content: request,
            },
        ],
    });
    const content = response.data.choices[0].message.content;
    try {
        return JSON.parse(content);
    }
    catch (error) {
        // If the response is not valid JSON, we'll try to extract the information using a regular expression.
        const attendees = /attendees: (.*)/.exec(content)?.[1];
        const duration = /duration: (.*)/.exec(content)?.[1];
        const topic = /topic: (.*)/.exec(content)?.[1];
        if (attendees && duration && topic) {
            return {
                attendees: attendees.split(',').map((s) => s.trim()),
                duration,
                topic,
            };
        }
        else {
            throw new Error('Unable to parse user request');
        }
    }
};
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoibGxtLWhlbHBlci5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImxsbS1oZWxwZXIudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6IkFBQUEsT0FBTyxFQUFFLGFBQWEsRUFBRSxTQUFTLEVBQUUsTUFBTSxRQUFRLENBQUM7QUFFbEQsTUFBTSxhQUFhLEdBQUcsSUFBSSxhQUFhLENBQUM7SUFDdEMsTUFBTSxFQUFFLE9BQU8sQ0FBQyxHQUFHLENBQUMsY0FBYztDQUNuQyxDQUFDLENBQUM7QUFDSCxNQUFNLE1BQU0sR0FBRyxJQUFJLFNBQVMsQ0FBQyxhQUFhLENBQUMsQ0FBQztBQUU1QyxNQUFNLENBQUMsTUFBTSxnQkFBZ0IsR0FBRyxLQUFLLEVBQUUsT0FBZSxFQUFFLEVBQUU7SUFDeEQsTUFBTSxRQUFRLEdBQUcsTUFBTSxNQUFNLENBQUMsb0JBQW9CLENBQUM7UUFDakQsS0FBSyxFQUFFLGVBQWU7UUFDdEIsUUFBUSxFQUFFO1lBQ1I7Z0JBQ0UsSUFBSSxFQUFFLFFBQVE7Z0JBQ2QsT0FBTyxFQUNMLHNUQUFzVDthQUN6VDtZQUNEO2dCQUNFLElBQUksRUFBRSxNQUFNO2dCQUNaLE9BQU8sRUFBRSxPQUFPO2FBQ2pCO1NBQ0Y7S0FDRixDQUFDLENBQUM7SUFFSCxNQUFNLE9BQU8sR0FBRyxRQUFRLENBQUMsSUFBSSxDQUFDLE9BQU8sQ0FBQyxDQUFDLENBQUMsQ0FBQyxPQUFPLENBQUMsT0FBTyxDQUFDO0lBRXpELElBQUksQ0FBQztRQUNILE9BQU8sSUFBSSxDQUFDLEtBQUssQ0FBQyxPQUFPLENBQUMsQ0FBQztJQUM3QixDQUFDO0lBQUMsT0FBTyxLQUFLLEVBQUUsQ0FBQztRQUNmLHNHQUFzRztRQUN0RyxNQUFNLFNBQVMsR0FBRyxpQkFBaUIsQ0FBQyxJQUFJLENBQUMsT0FBTyxDQUFDLEVBQUUsQ0FBQyxDQUFDLENBQUMsQ0FBQztRQUN2RCxNQUFNLFFBQVEsR0FBRyxnQkFBZ0IsQ0FBQyxJQUFJLENBQUMsT0FBTyxDQUFDLEVBQUUsQ0FBQyxDQUFDLENBQUMsQ0FBQztRQUNyRCxNQUFNLEtBQUssR0FBRyxhQUFhLENBQUMsSUFBSSxDQUFDLE9BQU8sQ0FBQyxFQUFFLENBQUMsQ0FBQyxDQUFDLENBQUM7UUFFL0MsSUFBSSxTQUFTLElBQUksUUFBUSxJQUFJLEtBQUssRUFBRSxDQUFDO1lBQ25DLE9BQU87Z0JBQ0wsU0FBUyxFQUFFLFNBQVMsQ0FBQyxLQUFLLENBQUMsR0FBRyxDQUFDLENBQUMsR0FBRyxDQUFDLENBQUMsQ0FBQyxFQUFFLEVBQUUsQ0FBQyxDQUFDLENBQUMsSUFBSSxFQUFFLENBQUM7Z0JBQ3BELFFBQVE7Z0JBQ1IsS0FBSzthQUNOLENBQUM7UUFDSixDQUFDO2FBQU0sQ0FBQztZQUNOLE1BQU0sSUFBSSxLQUFLLENBQUMsOEJBQThCLENBQUMsQ0FBQztRQUNsRCxDQUFDO0lBQ0gsQ0FBQztBQUNILENBQUMsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCB7IENvbmZpZ3VyYXRpb24sIE9wZW5BSUFwaSB9IGZyb20gJ29wZW5haSc7XG5cbmNvbnN0IGNvbmZpZ3VyYXRpb24gPSBuZXcgQ29uZmlndXJhdGlvbih7XG4gIGFwaUtleTogcHJvY2Vzcy5lbnYuT1BFTkFJX0FQSV9LRVksXG59KTtcbmNvbnN0IG9wZW5haSA9IG5ldyBPcGVuQUlBcGkoY29uZmlndXJhdGlvbik7XG5cbmV4cG9ydCBjb25zdCBwYXJzZVVzZXJSZXF1ZXN0ID0gYXN5bmMgKHJlcXVlc3Q6IHN0cmluZykgPT4ge1xuICBjb25zdCByZXNwb25zZSA9IGF3YWl0IG9wZW5haS5jcmVhdGVDaGF0Q29tcGxldGlvbih7XG4gICAgbW9kZWw6ICdncHQtMy41LXR1cmJvJyxcbiAgICBtZXNzYWdlczogW1xuICAgICAge1xuICAgICAgICByb2xlOiAnc3lzdGVtJyxcbiAgICAgICAgY29udGVudDpcbiAgICAgICAgICAnWW91IGFyZSBhIGhlbHBmdWwgYXNzaXN0YW50IHRoYXQgcGFyc2VzIHVzZXIgcmVxdWVzdHMgZm9yIHNjaGVkdWxpbmcgbWVldGluZ3MuIFRoZSB1c2VyIHdpbGwgcHJvdmlkZSBhIHJlcXVlc3QgaW4gbmF0dXJhbCBsYW5ndWFnZSwgYW5kIHlvdSBzaG91bGQgZXh0cmFjdCB0aGUgZm9sbG93aW5nIGluZm9ybWF0aW9uOiB0aGUgYXR0ZW5kZWVzLCB0aGUgZHVyYXRpb24gb2YgdGhlIG1lZXRpbmcsIGFuZCB0aGUgdG9waWMgb2YgdGhlIG1lZXRpbmcuIFlvdSBzaG91bGQgcmV0dXJuIHRoaXMgaW5mb3JtYXRpb24gYXMgYSBKU09OIG9iamVjdC4nLFxuICAgICAgfSxcbiAgICAgIHtcbiAgICAgICAgcm9sZTogJ3VzZXInLFxuICAgICAgICBjb250ZW50OiByZXF1ZXN0LFxuICAgICAgfSxcbiAgICBdLFxuICB9KTtcblxuICBjb25zdCBjb250ZW50ID0gcmVzcG9uc2UuZGF0YS5jaG9pY2VzWzBdLm1lc3NhZ2UuY29udGVudDtcblxuICB0cnkge1xuICAgIHJldHVybiBKU09OLnBhcnNlKGNvbnRlbnQpO1xuICB9IGNhdGNoIChlcnJvcikge1xuICAgIC8vIElmIHRoZSByZXNwb25zZSBpcyBub3QgdmFsaWQgSlNPTiwgd2UnbGwgdHJ5IHRvIGV4dHJhY3QgdGhlIGluZm9ybWF0aW9uIHVzaW5nIGEgcmVndWxhciBleHByZXNzaW9uLlxuICAgIGNvbnN0IGF0dGVuZGVlcyA9IC9hdHRlbmRlZXM6ICguKikvLmV4ZWMoY29udGVudCk/LlsxXTtcbiAgICBjb25zdCBkdXJhdGlvbiA9IC9kdXJhdGlvbjogKC4qKS8uZXhlYyhjb250ZW50KT8uWzFdO1xuICAgIGNvbnN0IHRvcGljID0gL3RvcGljOiAoLiopLy5leGVjKGNvbnRlbnQpPy5bMV07XG5cbiAgICBpZiAoYXR0ZW5kZWVzICYmIGR1cmF0aW9uICYmIHRvcGljKSB7XG4gICAgICByZXR1cm4ge1xuICAgICAgICBhdHRlbmRlZXM6IGF0dGVuZGVlcy5zcGxpdCgnLCcpLm1hcCgocykgPT4gcy50cmltKCkpLFxuICAgICAgICBkdXJhdGlvbixcbiAgICAgICAgdG9waWMsXG4gICAgICB9O1xuICAgIH0gZWxzZSB7XG4gICAgICB0aHJvdyBuZXcgRXJyb3IoJ1VuYWJsZSB0byBwYXJzZSB1c2VyIHJlcXVlc3QnKTtcbiAgICB9XG4gIH1cbn07XG4iXX0=