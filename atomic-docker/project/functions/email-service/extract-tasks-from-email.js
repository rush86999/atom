import { OpenAI } from 'openai';
import { getUserLlmModel } from '../_utils/userService';
const openai = new OpenAI({
    apiKey: process.env.OPENAI_API_KEY,
});
export async function extractTasksFromEmail(userId, emailContent) {
    const model = (await getUserLlmModel(userId)) || 'gpt-3.5-turbo';
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
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiZXh0cmFjdC10YXNrcy1mcm9tLWVtYWlsLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsiZXh0cmFjdC10YXNrcy1mcm9tLWVtYWlsLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiJBQUFBLE9BQU8sRUFBRSxNQUFNLEVBQUUsTUFBTSxRQUFRLENBQUM7QUFDaEMsT0FBTyxFQUFFLGVBQWUsRUFBRSxNQUFNLHVCQUF1QixDQUFDO0FBRXhELE1BQU0sTUFBTSxHQUFHLElBQUksTUFBTSxDQUFDO0lBQ3hCLE1BQU0sRUFBRSxPQUFPLENBQUMsR0FBRyxDQUFDLGNBQWM7Q0FDbkMsQ0FBQyxDQUFDO0FBRUgsTUFBTSxDQUFDLEtBQUssVUFBVSxxQkFBcUIsQ0FDekMsTUFBYyxFQUNkLFlBQW9CO0lBRXBCLE1BQU0sS0FBSyxHQUFHLENBQUMsTUFBTSxlQUFlLENBQUMsTUFBTSxDQUFDLENBQUMsSUFBSSxlQUFlLENBQUM7SUFDakUsTUFBTSxRQUFRLEdBQUcsTUFBTSxNQUFNLENBQUMsSUFBSSxDQUFDLFdBQVcsQ0FBQyxNQUFNLENBQUM7UUFDcEQsS0FBSztRQUNMLFFBQVEsRUFBRTtZQUNSO2dCQUNFLElBQUksRUFBRSxRQUFRO2dCQUNkLE9BQU8sRUFDTCxvSkFBb0o7YUFDdko7WUFDRDtnQkFDRSxJQUFJLEVBQUUsTUFBTTtnQkFDWixPQUFPLEVBQUUsWUFBWTthQUN0QjtTQUNGO0tBQ0YsQ0FBQyxDQUFDO0lBRUgsTUFBTSxLQUFLLEdBQUcsSUFBSSxDQUFDLEtBQUssQ0FBQyxRQUFRLENBQUMsT0FBTyxDQUFDLENBQUMsQ0FBQyxDQUFDLE9BQU8sQ0FBQyxPQUFPLENBQUMsQ0FBQztJQUM5RCxPQUFPLEtBQUssQ0FBQztBQUNmLENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgeyBPcGVuQUkgfSBmcm9tICdvcGVuYWknO1xuaW1wb3J0IHsgZ2V0VXNlckxsbU1vZGVsIH0gZnJvbSAnLi4vX3V0aWxzL3VzZXJTZXJ2aWNlJztcblxuY29uc3Qgb3BlbmFpID0gbmV3IE9wZW5BSSh7XG4gIGFwaUtleTogcHJvY2Vzcy5lbnYuT1BFTkFJX0FQSV9LRVksXG59KTtcblxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIGV4dHJhY3RUYXNrc0Zyb21FbWFpbChcbiAgdXNlcklkOiBzdHJpbmcsXG4gIGVtYWlsQ29udGVudDogc3RyaW5nXG4pOiBQcm9taXNlPHN0cmluZ1tdPiB7XG4gIGNvbnN0IG1vZGVsID0gKGF3YWl0IGdldFVzZXJMbG1Nb2RlbCh1c2VySWQpKSB8fCAnZ3B0LTMuNS10dXJibyc7XG4gIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgb3BlbmFpLmNoYXQuY29tcGxldGlvbnMuY3JlYXRlKHtcbiAgICBtb2RlbCxcbiAgICBtZXNzYWdlczogW1xuICAgICAge1xuICAgICAgICByb2xlOiAnc3lzdGVtJyxcbiAgICAgICAgY29udGVudDpcbiAgICAgICAgICAnRXh0cmFjdCB0aGUgYWN0aW9uIGl0ZW1zIG9yIHRhc2tzIGZyb20gdGhlIGZvbGxvd2luZyBlbWFpbCBjb250ZW50LiBSZXR1cm4gdGhlIHRhc2tzIGFzIGEgSlNPTiBhcnJheSBvZiBzdHJpbmdzLiBGb3IgZXhhbXBsZTogW1wiVGFzayAxXCIsIFwiVGFzayAyXCJdJyxcbiAgICAgIH0sXG4gICAgICB7XG4gICAgICAgIHJvbGU6ICd1c2VyJyxcbiAgICAgICAgY29udGVudDogZW1haWxDb250ZW50LFxuICAgICAgfSxcbiAgICBdLFxuICB9KTtcblxuICBjb25zdCB0YXNrcyA9IEpTT04ucGFyc2UocmVzcG9uc2UuY2hvaWNlc1swXS5tZXNzYWdlLmNvbnRlbnQpO1xuICByZXR1cm4gdGFza3M7XG59XG4iXX0=