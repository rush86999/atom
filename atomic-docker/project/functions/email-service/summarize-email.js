import { OpenAI } from 'openai';
import { getUserLlmModel } from '../_utils/userService';
const openai = new OpenAI({
    apiKey: process.env.OPENAI_API_KEY,
});
export async function summarizeEmail(userId, emailContent) {
    const model = (await getUserLlmModel(userId)) || 'gpt-3.5-turbo';
    const response = await openai.chat.completions.create({
        model,
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
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoic3VtbWFyaXplLWVtYWlsLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsic3VtbWFyaXplLWVtYWlsLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiJBQUFBLE9BQU8sRUFBRSxNQUFNLEVBQUUsTUFBTSxRQUFRLENBQUM7QUFDaEMsT0FBTyxFQUFFLGVBQWUsRUFBRSxNQUFNLHVCQUF1QixDQUFDO0FBRXhELE1BQU0sTUFBTSxHQUFHLElBQUksTUFBTSxDQUFDO0lBQ3hCLE1BQU0sRUFBRSxPQUFPLENBQUMsR0FBRyxDQUFDLGNBQWM7Q0FDbkMsQ0FBQyxDQUFDO0FBRUgsTUFBTSxDQUFDLEtBQUssVUFBVSxjQUFjLENBQ2xDLE1BQWMsRUFDZCxZQUFvQjtJQUVwQixNQUFNLEtBQUssR0FBRyxDQUFDLE1BQU0sZUFBZSxDQUFDLE1BQU0sQ0FBQyxDQUFDLElBQUksZUFBZSxDQUFDO0lBQ2pFLE1BQU0sUUFBUSxHQUFHLE1BQU0sTUFBTSxDQUFDLElBQUksQ0FBQyxXQUFXLENBQUMsTUFBTSxDQUFDO1FBQ3BELEtBQUs7UUFDTCxRQUFRLEVBQUU7WUFDUjtnQkFDRSxJQUFJLEVBQUUsUUFBUTtnQkFDZCxPQUFPLEVBQ0wsZ0hBQWdIO2FBQ25IO1lBQ0Q7Z0JBQ0UsSUFBSSxFQUFFLE1BQU07Z0JBQ1osT0FBTyxFQUFFLFlBQVk7YUFDdEI7U0FDRjtLQUNGLENBQUMsQ0FBQztJQUVILE9BQU8sUUFBUSxDQUFDLE9BQU8sQ0FBQyxDQUFDLENBQUMsQ0FBQyxPQUFPLENBQUMsT0FBTyxDQUFDO0FBQzdDLENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgeyBPcGVuQUkgfSBmcm9tICdvcGVuYWknO1xuaW1wb3J0IHsgZ2V0VXNlckxsbU1vZGVsIH0gZnJvbSAnLi4vX3V0aWxzL3VzZXJTZXJ2aWNlJztcblxuY29uc3Qgb3BlbmFpID0gbmV3IE9wZW5BSSh7XG4gIGFwaUtleTogcHJvY2Vzcy5lbnYuT1BFTkFJX0FQSV9LRVksXG59KTtcblxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIHN1bW1hcml6ZUVtYWlsKFxuICB1c2VySWQ6IHN0cmluZyxcbiAgZW1haWxDb250ZW50OiBzdHJpbmdcbik6IFByb21pc2U8c3RyaW5nPiB7XG4gIGNvbnN0IG1vZGVsID0gKGF3YWl0IGdldFVzZXJMbG1Nb2RlbCh1c2VySWQpKSB8fCAnZ3B0LTMuNS10dXJibyc7XG4gIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgb3BlbmFpLmNoYXQuY29tcGxldGlvbnMuY3JlYXRlKHtcbiAgICBtb2RlbCxcbiAgICBtZXNzYWdlczogW1xuICAgICAge1xuICAgICAgICByb2xlOiAnc3lzdGVtJyxcbiAgICAgICAgY29udGVudDpcbiAgICAgICAgICAnU3VtbWFyaXplIHRoZSBmb2xsb3dpbmcgZW1haWwgY29udGVudC4gVGhlIHN1bW1hcnkgc2hvdWxkIGJlIGNvbmNpc2UgYW5kIGNhcHR1cmUgdGhlIG1haW4gcG9pbnRzIG9mIHRoZSBlbWFpbC4nLFxuICAgICAgfSxcbiAgICAgIHtcbiAgICAgICAgcm9sZTogJ3VzZXInLFxuICAgICAgICBjb250ZW50OiBlbWFpbENvbnRlbnQsXG4gICAgICB9LFxuICAgIF0sXG4gIH0pO1xuXG4gIHJldHVybiByZXNwb25zZS5jaG9pY2VzWzBdLm1lc3NhZ2UuY29udGVudDtcbn1cbiJdfQ==