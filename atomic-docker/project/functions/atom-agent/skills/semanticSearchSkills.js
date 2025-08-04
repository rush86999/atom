import { logger } from "../../_utils/logger";
import axios from 'axios'; // Added axios
import { PYTHON_API_SERVICE_BASE_URL } from '../../_libs/constants'; // Added constant import
export class SemanticSearchSkills {
    // private apiHelper: ApiHelper; // Removed
    constructor() {
        // this.apiHelper = apiHelper; // Removed
    }
    getSkills() {
        return [
            {
                name: "search_meeting_notes",
                description: "Searches through your transcribed meeting notes using natural language to find relevant discussions. Provide your search query after the command.",
                parameters: [
                    {
                        name: "query",
                        type: "string",
                        description: "Your natural language search query for meeting notes."
                    }
                ],
                handler: this.handleSearchMeetingNotes.bind(this),
            },
        ];
    }
    // Changed from private to public to allow standalone function to call it
    async handleSearchMeetingNotes(args) {
        const userQuery = args.params?.query;
        const userId = args.user_id; // Passed by the agent framework
        if (!userQuery || userQuery.trim() === "") {
            return "Please provide a search query. For example, 'search_meeting_notes what were the decisions about project alpha?'";
        }
        if (!userId) {
            logger.error({
                message: "User ID is missing in skill arguments for search_meeting_notes.",
                skillArgs: args,
            });
            return "I'm sorry, I can't perform this search without your user identification. Please try again or contact support if the issue persists.";
        }
        const payload = {
            query: userQuery,
            user_id: userId,
        };
        try {
            logger.info({
                message: "Calling backend for semantic_search_meetings",
                url: `${PYTHON_API_SERVICE_BASE_URL}/api/semantic_search_meetings`,
                payload: payload,
                userId: userId,
            });
            const axiosResponse = await axios.post(// Using axios.post
            `${PYTHON_API_SERVICE_BASE_URL}/api/semantic_search_meetings`, payload);
            const backendData = axiosResponse.data; // This is BackendSearchResponse
            logger.info({
                message: "Received response from semantic_search_meetings backend",
                response: backendData,
                userId: userId,
            });
            // Assuming backend returns { status: "success" | "error", data?: ..., message?: ... }
            // OR { ok: true/false, data?: ..., error?: ... }
            // The BackendSearchResponse type might need adjustment based on Python actual response.
            // For now, let's assume it aligns with { status: ..., data: ..., message: ... }
            // And also check for 'ok' field if PythonApiResponse is used directly.
            if (backendData && backendData.status === "success" && backendData.data) {
                if (backendData.data.length > 0) {
                    const formattedResults = backendData.data.map(result => {
                        // Use notion_page_url directly if available and prefer web links.
                        // The notion:// scheme is for deep linking into desktop apps.
                        const link = result.notion_page_url || `notion://page/${result.notion_page_id.replace(/-/g, "")}`;
                        let displayDate = "Date not available";
                        try {
                            if (result.last_edited) { // Use the new field name
                                displayDate = new Date(result.last_edited).toLocaleDateString(undefined, {
                                    year: 'numeric', month: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit'
                                });
                            }
                        }
                        catch (dateError) {
                            logger.warn({
                                message: "Error parsing last_edited date from backend",
                                dateValue: result.last_edited,
                                error: dateError,
                            });
                        }
                        // Include text_preview
                        const preview = result.text_preview ? `\n    Snippet: "${result.text_preview}"` : "";
                        // Return a structured object for the frontend to handle custom rendering
                        const summaryText = `I found ${backendData.data.length} meeting note(s) related to your query:`;
                        return {
                            displayType: 'semantic_search_results',
                            summaryText: summaryText,
                            data: backendData.data // This is ApiMeetingSearchResult[]
                        };
                        // Original text formatting, kept for reference or if structured display fails.
                        // const formattedResults = backendData.data.map(result => {
                        //     const link = result.notion_page_url || `notion://page/${result.notion_page_id.replace(/-/g, "")}`;
                        //     let displayDate = "Date not available";
                        //     try {
                        //         if (result.last_edited) {
                        //             displayDate = new Date(result.last_edited).toLocaleDateString(undefined, {
                        //                 year: 'numeric', month: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit'
                        //             });
                        //         }
                        //     } catch (dateError) { /* ... logging ... */ }
                        //     const preview = result.text_preview ? `\n    Snippet: "${result.text_preview}"` : "";
                        //     return `- "${result.notion_page_title}" (Edited: ${displayDate}, Score: ${result.score.toFixed(2)})${preview}\n    Link: ${link}`;
                        // }).join("\n\n");
                        // return `I found the following meeting notes related to your query:\n\n${formattedResults}`;
                    }, {
                        return: "Sorry, I couldn't find any meeting notes matching your query."
                    });
                }
                else if (backendData && backendData.status === "error" && backendData.message) {
                    logger.error({
                        message: "Error response from semantic_search_meetings backend",
                        error: backendData.message,
                        code: backendData.error?.code,
                        userId: userId,
                    });
                    return `I encountered an error while searching: ${backendData.message}${backendData.error?.code ? ` (Code: ${backendData.error.code})` : ''}`;
                }
                else if (backendData && backendData.ok === false && backendData.error) {
                    logger.error({
                        message: "Error response from semantic_search_meetings backend (PythonApiResponse format)",
                        error: backendData.error,
                        userId: userId,
                    });
                    return `I encountered an error while searching: ${backendData.error.message}`;
                }
                else {
                    logger.error({
                        message: "Invalid or unexpected response from semantic_search_meetings backend",
                        response: backendData,
                        userId: userId,
                    });
                    return "I received an unexpected response from the search service. Please try again later.";
                }
            }
            try { }
            catch (error) {
                const axiosError = error;
                logger.error({
                    message: "Exception calling semantic_search_meetings backend with axios",
                    error: axiosError.isAxiosError ? axiosError.toJSON() : error,
                    errorMessage: axiosError.message,
                    responseData: axiosError.response?.data,
                    payload: payload,
                    userId: userId,
                });
                return "I'm sorry, I ran into a problem trying to search your meeting notes. Please try again later.";
            }
        }
        finally {
        }
    }
}
// Standalone handler function for easier integration with handler.ts switch statements
export async function handleSemanticSearchMeetingNotesSkill(args) {
    const skillInstance = new SemanticSearchSkills(); // Constructor is now empty
    return skillInstance.handleSearchMeetingNotes(args);
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoic2VtYW50aWNTZWFyY2hTa2lsbHMuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJzZW1hbnRpY1NlYXJjaFNraWxscy50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiQUFDQSxPQUFPLEVBQUUsTUFBTSxFQUFFLE1BQU0scUJBQXFCLENBQUM7QUFDN0MsT0FBTyxLQUFxQixNQUFNLE9BQU8sQ0FBQyxDQUFDLGNBQWM7QUFDekQsT0FBTyxFQUFFLDJCQUEyQixFQUFFLE1BQU0sdUJBQXVCLENBQUMsQ0FBQyx3QkFBd0I7QUFzQjdGLE1BQU0sT0FBTyxvQkFBb0I7SUFDN0IsMkNBQTJDO0lBRTNDO1FBQ0kseUNBQXlDO0lBQzdDLENBQUM7SUFFRCxTQUFTO1FBQ0wsT0FBTztZQUNIO2dCQUNJLElBQUksRUFBRSxzQkFBc0I7Z0JBQzVCLFdBQVcsRUFBRSxtSkFBbUo7Z0JBQ2hLLFVBQVUsRUFBRTtvQkFDUjt3QkFDSSxJQUFJLEVBQUUsT0FBTzt3QkFDYixJQUFJLEVBQUUsUUFBUTt3QkFDZCxXQUFXLEVBQUUsdURBQXVEO3FCQUN2RTtpQkFDSjtnQkFDRCxPQUFPLEVBQUUsSUFBSSxDQUFDLHdCQUF3QixDQUFDLElBQUksQ0FBQyxJQUFJLENBQUM7YUFDcEQ7U0FDSixDQUFDO0lBQ04sQ0FBQztJQUVELHlFQUF5RTtJQUNsRSxLQUFLLENBQUMsd0JBQXdCLENBQUMsSUFBZTtRQUNqRCxNQUFNLFNBQVMsR0FBRyxJQUFJLENBQUMsTUFBTSxFQUFFLEtBQWUsQ0FBQztRQUMvQyxNQUFNLE1BQU0sR0FBRyxJQUFJLENBQUMsT0FBTyxDQUFDLENBQUMsZ0NBQWdDO1FBRTdELElBQUksQ0FBQyxTQUFTLElBQUksU0FBUyxDQUFDLElBQUksRUFBRSxLQUFLLEVBQUUsRUFBRSxDQUFDO1lBQ3hDLE9BQU8saUhBQWlILENBQUM7UUFDN0gsQ0FBQztRQUVELElBQUksQ0FBQyxNQUFNLEVBQUUsQ0FBQztZQUNWLE1BQU0sQ0FBQyxLQUFLLENBQUM7Z0JBQ1QsT0FB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QztvQkFDRixNQUFNLENBQUMsS0FBSyxDQUFDO3dCQUNULE9BQU8sRUFBRSxzRUFBc0U7d0JBQy9FLFFBQVEsRUFBRSxXQUFXO3dCQUNyQixNQUFNLEVBQUUsTUFBTTtxQkFDakIsQ0FBQyxDQUFDO29CQUNILE9BQU8sb0ZBQW9GLENBQUM7Z0JBQ2hHLENBQUM7WUFDTCxDQUFDO1lBQUMsSUFBQSxDQUFDLENBQUQsQ0FBQyxBQUFGO1lBQUMsT0FBTyxLQUFVLEVBQUUsQ0FBQztnQkFDbEIsTUFBTSxVQUFVLEdBQUcsS0FBbUIsQ0FBQztnQkFDdkMsTUFBTSxDQUFDLEtBQUssQ0FBQztvQkFDVCxPQUFPLEVBQUUsK0RBQStEO29CQUN4RSxLQUFLLEVBQUUsVUFBVSxDQUFDLFlBQVksQ0FBQyxDQUFDLENBQUMsVUFBVSxDQUFDLE1BQU0sRUFBRSxDQUFDLENBQUMsQ0FBQyxLQUFLO29CQUM1RCxZQUFZLEVBQUUsVUFBVSxDQUFDLE9BQU87b0JBQ2hDLFlBQVksRUFBRSxVQUFVLENBQUMsUUFBUSxFQUFFLElBQUk7b0JBQ3ZDLE9BQU8sRUFBRSxPQUFPO29CQUNoQixNQUFNLEVBQUUsTUFBTTtpQkFDakIsQ0FBQyxDQUFDO2dCQUNILE9BQU8sOEZBQThGLENBQUM7WUFDMUcsQ0FBQztRQUNMLENBQUM7Z0JBQ0wsQ0FBQztRQUFELENBQUMsQUFESTtJQUNMLENBQUM7Q0FBQTtBQUVELHVGQUF1RjtBQUN2RixNQUFNLENBQUMsS0FBSyxVQUFVLHFDQUFxQyxDQUFDLElBQWU7SUFDdkUsTUFBTSxhQUFhLEdBQUcsSUFBSSxvQkFBb0IsRUFBRSxDQUFDLENBQUMsMkJBQTJCO0lBQzdFLE9BQU8sYUFBYSxDQUFDLHdCQUF3QixDQUFDLElBQUksQ0FBQyxDQUFDO0FBQ3hELENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgeyBJU2tpbGwsIElBZ2VudFNraWxscywgU2tpbGxBcmdzIH0gZnJvbSBcIi4uL3R5cGVzXCI7IC8vIEFwaUhlbHBlciByZW1vdmVkXG5pbXBvcnQgeyBsb2dnZXIgfSBmcm9tIFwiLi4vLi4vX3V0aWxzL2xvZ2dlclwiO1xuaW1wb3J0IGF4aW9zLCB7IEF4aW9zRXJyb3IgfSBmcm9tICdheGlvcyc7IC8vIEFkZGVkIGF4aW9zXG5pbXBvcnQgeyBQWVRIT05fQVBJX1NFUlZJQ0VfQkFTRV9VUkwgfSBmcm9tICcuLi8uLi9fbGlicy9jb25zdGFudHMnOyAvLyBBZGRlZCBjb25zdGFudCBpbXBvcnRcblxuLy8gRGVmaW5lIHRoZSBleHBlY3RlZCBzdHJ1Y3R1cmUgb2YgYSBzaW5nbGUgc2VhcmNoIHJlc3VsdCBmcm9tIHRoZSBiYWNrZW5kIEFQSVxuaW50ZXJmYWNlIEFwaU1lZXRpbmdTZWFyY2hSZXN1bHQge1xuICAgIG5vdGlvbl9wYWdlX2lkOiBzdHJpbmc7XG4gICAgbm90aW9uX3BhZ2VfdGl0bGU6IHN0cmluZztcbiAgICBub3Rpb25fcGFnZV91cmw6IHN0cmluZztcbiAgICB0ZXh0X3ByZXZpZXc6IHN0cmluZztcbiAgICBsYXN0X2VkaXRlZDogc3RyaW5nOyAvLyBJU08gZGF0ZSBzdHJpbmdcbiAgICBzY29yZTogbnVtYmVyO1xufVxuXG4vLyBEZWZpbmUgdGhlIGV4cGVjdGVkIHN0cnVjdHVyZSBvZiB0aGUgYmFja2VuZCBBUEkgcmVzcG9uc2VcbmludGVyZmFjZSBCYWNrZW5kU2VhcmNoUmVzcG9uc2Uge1xuICAgIHN0YXR1czogXCJzdWNjZXNzXCIgfCBcImVycm9yXCI7XG4gICAgZGF0YT86IEFwaU1lZXRpbmdTZWFyY2hSZXN1bHRbXTsgLy8gVXNlIHRoZSB1cGRhdGVkIGludGVyZmFjZVxuICAgIG1lc3NhZ2U/OiBzdHJpbmc7XG4gICAgLy8gRm9yIFB5dGhvbkFwaVJlc3BvbnNlIGNvbXBhdGliaWxpdHkgaWYgbmVlZGVkLCB0aG91Z2ggc3RhdHVzL2RhdGEvbWVzc2FnZSBpcyBwcmVmZXJyZWRcbiAgICBvaz86IGJvb2xlYW47XG4gICAgZXJyb3I/OiB7IGNvZGU6IHN0cmluZzsgbWVzc2FnZTogc3RyaW5nOyBkZXRhaWxzPzogYW55IH07XG59XG5cbmV4cG9ydCBjbGFzcyBTZW1hbnRpY1NlYXJjaFNraWxscyBpbXBsZW1lbnRzIElBZ2VudFNraWxscyB7XG4gICAgLy8gcHJpdmF0ZSBhcGlIZWxwZXI6IEFwaUhlbHBlcjsgLy8gUmVtb3ZlZFxuXG4gICAgY29uc3RydWN0b3IoKSB7IC8vIENvbnN0cnVjdG9yIG5vIGxvbmdlciB0YWtlcyBBcGlIZWxwZXJcbiAgICAgICAgLy8gdGhpcy5hcGlIZWxwZXIgPSBhcGlIZWxwZXI7IC8vIFJlbW92ZWRcbiAgICB9XG5cbiAgICBnZXRTa2lsbHMoKTogSVNraWxsW10ge1xuICAgICAgICByZXR1cm4gW1xuICAgICAgICAgICAge1xuICAgICAgICAgICAgICAgIG5hbWU6IFwic2VhcmNoX21lZXRpbmdfbm90ZXNcIixcbiAgICAgICAgICAgICAgICBkZXNjcmlwdGlvbjogXCJTZWFyY2hlcyB0aHJvdWdoIHlvdXIgdHJhbnNjcmliZWQgbWVldGluZyBub3RlcyB1c2luZyBuYXR1cmFsIGxhbmd1YWdlIHRvIGZpbmQgcmVsZXZhbnQgZGlzY3Vzc2lvbnMuIFByb3ZpZGUgeW91ciBzZWFyY2ggcXVlcnkgYWZ0ZXIgdGhlIGNvbW1hbmQuXCIsXG4gICAgICAgICAgICAgICAgcGFyYW1ldGVyczogW1xuICAgICAgICAgICAgICAgICAgICB7XG4gICAgICAgICAgICAgICAgICAgICAgICBuYW1lOiBcInF1ZXJ5XCIsXG4gICAgICAgICAgICAgICAgICAgICAgICB0eXBlOiBcInN0cmluZ1wiLFxuICAgICAgICAgICAgICAgICAgICAgICAgZGVzY3JpcHRpb246IFwiWW91ciBuYXR1cmFsIGxhbmd1YWdlIHNlYXJjaCBxdWVyeSBmb3IgbWVldGluZyBub3Rlcy5cIlxuICAgICAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICAgICAgXSxcbiAgICAgICAgICAgICAgICBoYW5kbGVyOiB0aGlzLmhhbmRsZVNlYXJjaE1lZXRpbmdOb3Rlcy5iaW5kKHRoaXMpLFxuICAgICAgICAgICAgfSxcbiAgICAgICAgXTtcbiAgICB9XG5cbiAgICAvLyBDaGFuZ2VkIGZyb20gcHJpdmF0ZSB0byBwdWJsaWMgdG8gYWxsb3cgc3RhbmRhbG9uZSBmdW5jdGlvbiB0byBjYWxsIGl0XG4gICAgcHVibGljIGFzeW5jIGhhbmRsZVNlYXJjaE1lZXRpbmdOb3RlcyhhcmdzOiBTa2lsbEFyZ3MpOiBQcm9taXNlPHN0cmluZyB8IHsgZGlzcGxheVR5cGU6ICdzZW1hbnRpY19zZWFyY2hfcmVzdWx0cyc7IHN1bW1hcnlUZXh0OiBzdHJpbmc7IGRhdGE6IEFwaU1lZXRpbmdTZWFyY2hSZXN1bHRbXSB9PiB7XG4gICAgICAgIGNvbnN0IHVzZXJRdWVyeSA9IGFyZ3MucGFyYW1zPy5xdWVyeSBhcyBzdHJpbmc7XG4gICAgICAgIGNvbnN0IHVzZXJJZCA9IGFyZ3MudXNlcl9pZDsgLy8gUGFzc2VkIGJ5IHRoZSBhZ2VudCBmcmFtZXdvcmtcblxuICAgICAgICBpZiAoIXVzZXJRdWVyeSB8fCB1c2VyUXVlcnkudHJpbSgpID09PSBcIlwiKSB7XG4gICAgICAgICAgICByZXR1cm4gXCJQbGVhc2UgcHJvdmlkZSBhIHNlYXJjaCBxdWVyeS4gRm9yIGV4YW1wbGUsICdzZWFyY2hfbWVldGluZ19ub3RlcyB3aGF0IHdlcmUgdGhlIGRlY2lzaW9ucyBhYm91dCBwcm9qZWN0IGFscGhhPydcIjtcbiAgICAgICAgfVxuXG4gICAgICAgIGlmICghdXNlcklkKSB7XG4gICAgICAgICAgICBsb2dnZXIuZXJyb3Ioe1xuICAgICAgICAgICAgICAgIG1lc3NhZ2U6IFwiVXNlciBJRCBpcyBtaXNzaW5nIGluIHNraWxsIGFyZ3VtZW50cyBmb3Igc2VhcmNoX21lZXRpbmdfbm90ZXMuXCIsXG4gICAgICAgICAgICAgICAgc2tpbGxBcmdzOiBhcmdzLFxuICAgICAgICAgICAgfSk7XG4gICAgICAgICAgICByZXR1cm4gXCJJJ20gc29ycnksIEkgY2FuJ3QgcGVyZm9ybSB0aGlzIHNlYXJjaCB3aXRob3V0IHlvdXIgdXNlciBpZGVudGlmaWNhdGlvbi4gUGxlYXNlIHRyeSBhZ2FpbiBvciBjb250YWN0IHN1cHBvcnQgaWYgdGhlIGlzc3VlIHBlcnNpc3RzLlwiO1xuICAgICAgICB9XG5cbiAgICAgICAgY29uc3QgcGF5bG9hZCA9IHtcbiAgICAgICAgICAgIHF1ZXJ5OiB1c2VyUXVlcnksXG4gICAgICAgICAgICB1c2VyX2lkOiB1c2VySWQsXG4gICAgICAgIH07XG5cbiAgICAgICAgdHJ5IHtcbiAgICAgICAgICAgIGxvZ2dlci5pbmZvKHtcbiAgICAgICAgICAgICAgICBtZXNzYWdlOiBcIkNhbGxpbmcgYmFja2VuZCBmb3Igc2VtYW50aWNfc2VhcmNoX21lZXRpbmdzXCIsXG4gICAgICAgICAgICAgICAgdXJsOiBgJHtQWVRIT05fQVBJX1NFUlZJQ0VfQkFTRV9VUkx9L2FwaS9zZW1hbnRpY19zZWFyY2hfbWVldGluZ3NgLFxuICAgICAgICAgICAgICAgIHBheWxvYWQ6IHBheWxvYWQsXG4gICAgICAgICAgICAgICAgdXNlcklkOiB1c2VySWQsXG4gICAgICAgICAgICB9KTtcblxuICAgICAgICAgICAgY29uc3QgYXhpb3NSZXNwb25zZSA9IGF3YWl0IGF4aW9zLnBvc3Q8QmFja2VuZFNlYXJjaFJlc3BvbnNlPiggLy8gVXNpbmcgYXhpb3MucG9zdFxuICAgICAgICAgICAgICAgIGAke1BZVEhPTl9BUElfU0VSVklDRV9CQVNFX1VSTH0vYXBpL3NlbWFudGljX3NlYXJjaF9tZWV0aW5nc2AsXG4gICAgICAgICAgICAgICAgcGF5bG9hZFxuICAgICAgICAgICAgKTtcblxuICAgICAgICAgICAgY29uc3QgYmFja2VuZERhdGEgPSBheGlvc1Jlc3BvbnNlLmRhdGE7IC8vIFRoaXMgaXMgQmFja2VuZFNlYXJjaFJlc3BvbnNlXG5cbiAgICAgICAgICAgIGxvZ2dlci5pbmZvKHtcbiAgICAgICAgICAgICAgICBtZXNzYWdlOiBcIlJlY2VpdmVkIHJlc3BvbnNlIGZyb20gc2VtYW50aWNfc2VhcmNoX21lZXRpbmdzIGJhY2tlbmRcIixcbiAgICAgICAgICAgICAgICByZXNwb25zZTogYmFja2VuZERhdGEsXG4gICAgICAgICAgICAgICAgdXNlcklkOiB1c2VySWQsXG4gICAgICAgICAgICB9KTtcblxuICAgICAgICAgICAgLy8gQXNzdW1pbmcgYmFja2VuZCByZXR1cm5zIHsgc3RhdHVzOiBcInN1Y2Nlc3NcIiB8IFwiZXJyb3JcIiwgZGF0YT86IC4uLiwgbWVzc2FnZT86IC4uLiB9XG4gICAgICAgICAgICAvLyBPUiB7IG9rOiB0cnVlL2ZhbHNlLCBkYXRhPzogLi4uLCBlcnJvcj86IC4uLiB9XG4gICAgICAgICAgICAvLyBUaGUgQmFja2VuZFNlYXJjaFJlc3BvbnNlIHR5cGUgbWlnaHQgbmVlZCBhZGp1c3RtZW50IGJhc2VkIG9uIFB5dGhvbiBhY3R1YWwgcmVzcG9uc2UuXG4gICAgICAgICAgICAvLyBGb3Igbm93LCBsZXQncyBhc3N1bWUgaXQgYWxpZ25zIHdpdGggeyBzdGF0dXM6IC4uLiwgZGF0YTogLi4uLCBtZXNzYWdlOiAuLi4gfVxuICAgICAgICAgICAgLy8gQW5kIGFsc28gY2hlY2sgZm9yICdvaycgZmllbGQgaWYgUHl0aG9uQXBpUmVzcG9uc2UgaXMgdXNlZCBkaXJlY3RseS5cblxuICAgICAgICAgICAgaWYgKGJhY2tlbmREYXRhICYmIGJhY2tlbmREYXRhLnN0YXR1cyA9PT0gXCJzdWNjZXNzXCIgJiYgYmFja2VuZERhdGEuZGF0YSkge1xuICAgICAgICAgICAgICAgIGlmIChiYWNrZW5kRGF0YS5kYXRhLmxlbmd0aCA+IDApIHtcbiAgICAgICAgICAgICAgICAgICAgY29uc3QgZm9ybWF0dGVkUmVzdWx0cyA9IGJhY2tlbmREYXRhLmRhdGEubWFwKHJlc3VsdCA9PiB7XG4gICAgICAgICAgICAgICAgICAgICAgICAvLyBVc2Ugbm90aW9uX3BhZ2VfdXJsIGRpcmVjdGx5IGlmIGF2YWlsYWJsZSBhbmQgcHJlZmVyIHdlYiBsaW5rcy5cbiAgICAgICAgICAgICAgICAgICAgICAgIC8vIFRoZSBub3Rpb246Ly8gc2NoZW1lIGlzIGZvciBkZWVwIGxpbmtpbmcgaW50byBkZXNrdG9wIGFwcHMuXG4gICAgICAgICAgICAgICAgICAgICAgICBjb25zdCBsaW5rID0gcmVzdWx0Lm5vdGlvbl9wYWdlX3VybCB8fCBgbm90aW9uOi8vcGFnZS8ke3Jlc3VsdC5ub3Rpb25fcGFnZV9pZC5yZXBsYWNlKC8tL2csIFwiXCIpfWA7XG5cbiAgICAgICAgICAgICAgICAgICAgICAgIGxldCBkaXNwbGF5RGF0ZSA9IFwiRGF0ZSBub3QgYXZhaWxhYmxlXCI7XG4gICAgICAgICAgICAgICAgICAgICAgICB0cnkge1xuICAgICAgICAgICAgICAgICAgICAgICAgICAgIGlmIChyZXN1bHQubGFzdF9lZGl0ZWQpIHsgLy8gVXNlIHRoZSBuZXcgZmllbGQgbmFtZVxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBkaXNwbGF5RGF0ZSA9IG5ldyBEYXRlKHJlc3VsdC5sYXN0X2VkaXRlZCkudG9Mb2NhbGVEYXRlU3RyaW5nKHVuZGVmaW5lZCwge1xuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgeWVhcjogJ251bWVyaWMnLCBtb250aDogJ2xvbmcnLCBkYXk6ICdudW1lcmljJywgaG91cjogJzItZGlnaXQnLCBtaW51dGU6ICcyLWRpZ2l0J1xuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICB9KTtcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICAgICAgICAgICAgICB9IGNhdGNoIChkYXRlRXJyb3IpIHtcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICBsb2dnZXIud2Fybih7XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgIG1lc3NhZ2U6IFwiRXJyb3IgcGFyc2luZyBsYXN0X2VkaXRlZCBkYXRlIGZyb20gYmFja2VuZFwiLFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICBkYXRlVmFsdWU6IHJlc3VsdC5sYXN0X2VkaXRlZCxcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgZXJyb3I6IGRhdGVFcnJvcixcbiAgICAgICAgICAgICAgICAgICAgICAgICAgICB9KTtcbiAgICAgICAgICAgICAgICAgICAgICAgIH1cblxuICAgICAgICAgICAgICAgICAgICAgICAgLy8gSW5jbHVkZSB0ZXh0X3ByZXZpZXdcbiAgICAgICAgICAgICAgICAgICAgICAgIGNvbnN0IHByZXZpZXcgPSByZXN1bHQudGV4dF9wcmV2aWV3ID8gYFxcbiAgICBTbmlwcGV0OiBcIiR7cmVzdWx0LnRleHRfcHJldmlld31cImAgOiBcIlwiO1xuXG4gICAgICAgICAgICAgICAgICAgICAgICAvLyBSZXR1cm4gYSBzdHJ1Y3R1cmVkIG9iamVjdCBmb3IgdGhlIGZyb250ZW5kIHRvIGhhbmRsZSBjdXN0b20gcmVuZGVyaW5nXG4gICAgICAgICAgICAgICAgICAgICAgICBjb25zdCBzdW1tYXJ5VGV4dCA9IGBJIGZvdW5kICR7YmFja2VuZERhdGEuZGF0YS5sZW5ndGh9IG1lZXRpbmcgbm90ZShzKSByZWxhdGVkIHRvIHlvdXIgcXVlcnk6YDtcbiAgICAgICAgICAgICAgICAgICAgICAgIHJldHVybiB7XG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgZGlzcGxheVR5cGU6ICdzZW1hbnRpY19zZWFyY2hfcmVzdWx0cycsXG4gICAgICAgICAgICAgICAgICAgICAgICAgICAgc3VtbWFyeVRleHQ6IHN1bW1hcnlUZXh0LFxuICAgICAgICAgICAgICAgICAgICAgICAgICAgIGRhdGE6IGJhY2tlbmREYXRhLmRhdGEgLy8gVGhpcyBpcyBBcGlNZWV0aW5nU2VhcmNoUmVzdWx0W11cbiAgICAgICAgICAgICAgICAgICAgICAgIH07XG4gICAgICAgICAgICAgICAgICAgIC8vIE9yaWdpbmFsIHRleHQgZm9ybWF0dGluZywga2VwdCBmb3IgcmVmZXJlbmNlIG9yIGlmIHN0cnVjdHVyZWQgZGlzcGxheSBmYWlscy5cbiAgICAgICAgICAgICAgICAgICAgLy8gY29uc3QgZm9ybWF0dGVkUmVzdWx0cyA9IGJhY2tlbmREYXRhLmRhdGEubWFwKHJlc3VsdCA9PiB7XG4gICAgICAgICAgICAgICAgICAgIC8vICAgICBjb25zdCBsaW5rID0gcmVzdWx0Lm5vdGlvbl9wYWdlX3VybCB8fCBgbm90aW9uOi8vcGFnZS8ke3Jlc3VsdC5ub3Rpb25fcGFnZV9pZC5yZXBsYWNlKC8tL2csIFwiXCIpfWA7XG4gICAgICAgICAgICAgICAgICAgIC8vICAgICBsZXQgZGlzcGxheURhdGUgPSBcIkRhdGUgbm90IGF2YWlsYWJsZVwiO1xuICAgICAgICAgICAgICAgICAgICAvLyAgICAgdHJ5IHtcbiAgICAgICAgICAgICAgICAgICAgLy8gICAgICAgICBpZiAocmVzdWx0Lmxhc3RfZWRpdGVkKSB7XG4gICAgICAgICAgICAgICAgICAgIC8vICAgICAgICAgICAgIGRpc3BsYXlEYXRlID0gbmV3IERhdGUocmVzdWx0Lmxhc3RfZWRpdGVkKS50b0xvY2FsZURhdGVTdHJpbmcodW5kZWZpbmVkLCB7XG4gICAgICAgICAgICAgICAgICAgIC8vICAgICAgICAgICAgICAgICB5ZWFyOiAnbnVtZXJpYycsIG1vbnRoOiAnbG9uZycsIGRheTogJ251bWVyaWMnLCBob3VyOiAnMi1kaWdpdCcsIG1pbnV0ZTogJzItZGlnaXQnXG4gICAgICAgICAgICAgICAgICAgIC8vICAgICAgICAgICAgIH0pO1xuICAgICAgICAgICAgICAgICAgICAvLyAgICAgICAgIH1cbiAgICAgICAgICAgICAgICAgICAgLy8gICAgIH0gY2F0Y2ggKGRhdGVFcnJvcikgeyAvKiAuLi4gbG9nZ2luZyAuLi4gKi8gfVxuICAgICAgICAgICAgICAgICAgICAvLyAgICAgY29uc3QgcHJldmlldyA9IHJlc3VsdC50ZXh0X3ByZXZpZXcgPyBgXFxuICAgIFNuaXBwZXQ6IFwiJHtyZXN1bHQudGV4dF9wcmV2aWV3fVwiYCA6IFwiXCI7XG4gICAgICAgICAgICAgICAgICAgIC8vICAgICByZXR1cm4gYC0gXCIke3Jlc3VsdC5ub3Rpb25fcGFnZV90aXRsZX1cIiAoRWRpdGVkOiAke2Rpc3BsYXlEYXRlfSwgU2NvcmU6ICR7cmVzdWx0LnNjb3JlLnRvRml4ZWQoMil9KSR7cHJldmlld31cXG4gICAgTGluazogJHtsaW5rfWA7XG4gICAgICAgICAgICAgICAgICAgIC8vIH0pLmpvaW4oXCJcXG5cXG5cIik7XG4gICAgICAgICAgICAgICAgICAgIC8vIHJldHVybiBgSSBmb3VuZCB0aGUgZm9sbG93aW5nIG1lZXRpbmcgbm90ZXMgcmVsYXRlZCB0byB5b3VyIHF1ZXJ5OlxcblxcbiR7Zm9ybWF0dGVkUmVzdWx0c31gO1xuICAgICAgICAgICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgICAgICAgICAgIHJldHVybiBcIlNvcnJ5LCBJIGNvdWxkbid0IGZpbmQgYW55IG1lZXRpbmcgbm90ZXMgbWF0Y2hpbmcgeW91ciBxdWVyeS5cIjtcbiAgICAgICAgICAgICAgICB9XG4gICAgICAgICAgICB9IGVsc2UgaWYgKGJhY2tlbmREYXRhICYmIGJhY2tlbmREYXRhLnN0YXR1cyA9PT0gXCJlcnJvclwiICYmIGJhY2tlbmREYXRhLm1lc3NhZ2UpIHtcbiAgICAgICAgICAgICAgICBsb2dnZXIuZXJyb3Ioe1xuICAgICAgICAgICAgICAgICAgICBtZXNzYWdlOiBcIkVycm9yIHJlc3BvbnNlIGZyb20gc2VtYW50aWNfc2VhcmNoX21lZXRpbmdzIGJhY2tlbmRcIixcbiAgICAgICAgICAgICAgICAgICAgZXJyb3I6IGJhY2tlbmREYXRhLm1lc3NhZ2UsXG4gICAgICAgICAgICAgICAgICAgIGNvZGU6IGJhY2tlbmREYXRhLmVycm9yPy5jb2RlLFxuICAgICAgICAgICAgICAgICAgICB1c2VySWQ6IHVzZXJJZCxcbiAgICAgICAgICAgICAgICB9KTtcbiAgICAgICAgICAgICAgICByZXR1cm4gYEkgZW5jb3VudGVyZWQgYW4gZXJyb3Igd2hpbGUgc2VhcmNoaW5nOiAke2JhY2tlbmREYXRhLm1lc3NhZ2V9JHtiYWNrZW5kRGF0YS5lcnJvcj8uY29kZSA/IGAgKENvZGU6ICR7YmFja2VuZERhdGEuZXJyb3IuY29kZX0pYCA6ICcnfWA7XG4gICAgICAgICAgICB9IGVsc2UgaWYgKGJhY2tlbmREYXRhICYmIGJhY2tlbmREYXRhLm9rID09PSBmYWxzZSAmJiBiYWNrZW5kRGF0YS5lcnJvcikge1xuICAgICAgICAgICAgICAgICBsb2dnZXIuZXJyb3Ioe1xuICAgICAgICAgICAgICAgICAgICBtZXNzYWdlOiBcIkVycm9yIHJlc3BvbnNlIGZyb20gc2VtYW50aWNfc2VhcmNoX21lZXRpbmdzIGJhY2tlbmQgKFB5dGhvbkFwaVJlc3BvbnNlIGZvcm1hdClcIixcbiAgICAgICAgICAgICAgICAgICAgZXJyb3I6IGJhY2tlbmREYXRhLmVycm9yLFxuICAgICAgICAgICAgICAgICAgICB1c2VySWQ6IHVzZXJJZCxcbiAgICAgICAgICAgICAgICB9KTtcbiAgICAgICAgICAgICAgICByZXR1cm4gYEkgZW5jb3VudGVyZWQgYW4gZXJyb3Igd2hpbGUgc2VhcmNoaW5nOiAke2JhY2tlbmREYXRhLmVycm9yLm1lc3NhZ2V9YDtcbiAgICAgICAgICAgIH1cbiAgICAgICAgICAgIGVsc2Uge1xuICAgICAgICAgICAgICAgIGxvZ2dlci5lcnJvcih7XG4gICAgICAgICAgICAgICAgICAgIG1lc3NhZ2U6IFwiSW52YWxpZCBvciB1bmV4cGVjdGVkIHJlc3BvbnNlIGZyb20gc2VtYW50aWNfc2VhcmNoX21lZXRpbmdzIGJhY2tlbmRcIixcbiAgICAgICAgICAgICAgICAgICAgcmVzcG9uc2U6IGJhY2tlbmREYXRhLFxuICAgICAgICAgICAgICAgICAgICB1c2VySWQ6IHVzZXJJZCxcbiAgICAgICAgICAgICAgICB9KTtcbiAgICAgICAgICAgICAgICByZXR1cm4gXCJJIHJlY2VpdmVkIGFuIHVuZXhwZWN0ZWQgcmVzcG9uc2UgZnJvbSB0aGUgc2VhcmNoIHNlcnZpY2UuIFBsZWFzZSB0cnkgYWdhaW4gbGF0ZXIuXCI7XG4gICAgICAgICAgICB9XG4gICAgICAgIH0gY2F0Y2ggKGVycm9yOiBhbnkpIHtcbiAgICAgICAgICAgIGNvbnN0IGF4aW9zRXJyb3IgPSBlcnJvciBhcyBBeGlvc0Vycm9yO1xuICAgICAgICAgICAgbG9nZ2VyLmVycm9yKHtcbiAgICAgICAgICAgICAgICBtZXNzYWdlOiBcIkV4Y2VwdGlvbiBjYWxsaW5nIHNlbWFudGljX3NlYXJjaF9tZWV0aW5ncyBiYWNrZW5kIHdpdGggYXhpb3NcIixcbiAgICAgICAgICAgICAgICBlcnJvcjogYXhpb3NFcnJvci5pc0F4aW9zRXJyb3IgPyBheGlvc0Vycm9yLnRvSlNPTigpIDogZXJyb3IsXG4gICAgICAgICAgICAgICAgZXJyb3JNZXNzYWdlOiBheGlvc0Vycm9yLm1lc3NhZ2UsXG4gICAgICAgICAgICAgICAgcmVzcG9uc2VEYXRhOiBheGlvc0Vycm9yLnJlc3BvbnNlPy5kYXRhLFxuICAgICAgICAgICAgICAgIHBheWxvYWQ6IHBheWxvYWQsXG4gICAgICAgICAgICAgICAgdXNlcklkOiB1c2VySWQsXG4gICAgICAgICAgICB9KTtcbiAgICAgICAgICAgIHJldHVybiBcIkknbSBzb3JyeSwgSSByYW4gaW50byBhIHByb2JsZW0gdHJ5aW5nIHRvIHNlYXJjaCB5b3VyIG1lZXRpbmcgbm90ZXMuIFBsZWFzZSB0cnkgYWdhaW4gbGF0ZXIuXCI7XG4gICAgICAgIH1cbiAgICB9XG59XG5cbi8vIFN0YW5kYWxvbmUgaGFuZGxlciBmdW5jdGlvbiBmb3IgZWFzaWVyIGludGVncmF0aW9uIHdpdGggaGFuZGxlci50cyBzd2l0Y2ggc3RhdGVtZW50c1xuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIGhhbmRsZVNlbWFudGljU2VhcmNoTWVldGluZ05vdGVzU2tpbGwoYXJnczogU2tpbGxBcmdzKTogUHJvbWlzZTxzdHJpbmc+IHsgLy8gQXBpSGVscGVyIHJlbW92ZWRcbiAgICBjb25zdCBza2lsbEluc3RhbmNlID0gbmV3IFNlbWFudGljU2VhcmNoU2tpbGxzKCk7IC8vIENvbnN0cnVjdG9yIGlzIG5vdyBlbXB0eVxuICAgIHJldHVybiBza2lsbEluc3RhbmNlLmhhbmRsZVNlYXJjaE1lZXRpbmdOb3RlcyhhcmdzKTtcbn1cbiJdfQ==