import { ISkill, IAgentSkills, SkillArgs, ApiHelper } from "../types"; // Adjust path as needed
import { logger } from "../../_utils/logger"; // Assuming a shared logger utility

// Define the expected structure of a single search result from the backend
interface MeetingSearchResult {
    notion_page_id: string;
    meeting_title: string;
    meeting_date: string; // ISO date string
    score: number;
    // transcript_chunk: string; // Optional: if backend sends a snippet
    // user_id: string; // Optional: if needed in frontend
}

// Define the expected structure of the backend API response
interface BackendSearchResponse {
    status: "success" | "error";
    data?: MeetingSearchResult[];
    message?: string;
}

export class SemanticSearchSkills implements IAgentSkills {
    private apiHelper: ApiHelper;

    constructor(apiHelper: ApiHelper) {
        this.apiHelper = apiHelper;
    }

    getSkills(): ISkill[] {
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

    private async handleSearchMeetingNotes(args: SkillArgs): Promise<string> {
        const userQuery = args.params?.query as string;
        const userId = args.user_id; // Passed by the agent framework

        if (!userQuery || userQuery.trim() === "") {
            return "Please provide a search query. For example, 'search_meeting_notes what were the decisions about project alpha?'";
        }

        if (!userId) {
            // This should ideally be handled by the agent framework ensuring user_id is always available
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
            // Assuming the ApiHelper is configured with the base URL for the Python backend service.
            // The first argument to post is the endpoint path.
            // Replace 'python_backend_service_name' with the actual service identifier if apiHelper needs it,
            // or if it's a direct URL construction, it might be `${PYTHON_SERVICE_URL}/semantic_search_meetings`
            // For now, let's assume apiHelper.post knows where to send it based on a configured base URL.
            // The endpoint name here is `/semantic_search_meetings`, which will be appended to a base URL.
            logger.info({
                message: "Calling backend for semantic_search_meetings",
                payload: payload,
                userId: userId,
            });

            const response = await this.apiHelper.post<BackendSearchResponse>(
                "/semantic_search_meetings", // This would typically be an endpoint on your Python service
                payload
            );

            logger.info({
                message: "Received response from semantic_search_meetings backend",
                response: response,
                userId: userId,
            });

            if (response && response.status === "success" && response.data) {
                if (response.data.length > 0) {
                    const formattedResults = response.data.map(result => {
                        // Ensure notion_page_id is valid before replacing dashes
                        const pageId = result.notion_page_id || "";
                        const notionLink = `notion://page/${pageId.replace(/-/g, "")}`;

                        let displayDate = "Date not available";
                        try {
                            if (result.meeting_date) {
                                displayDate = new Date(result.meeting_date).toLocaleDateString(undefined, {
                                    year: 'numeric', month: 'long', day: 'numeric'
                                });
                            }
                        } catch (dateError) {
                            logger.warn({
                                message: "Error parsing meeting_date from backend",
                                dateValue: result.meeting_date,
                                error: dateError,
                            });
                        }

                        return `- "${result.meeting_title}" (${displayDate}): ${notionLink} (Similarity: ${result.score.toFixed(2)})`;
                    }).join("\n");
                    return `Found these meetings related to your query:\n${formattedResults}`;
                } else {
                    return "Sorry, I couldn't find any meeting notes matching your query.";
                }
            } else if (response && response.status === "error" && response.message) {
                logger.error({
                    message: "Error response from semantic_search_meetings backend",
                    error: response.message,
                    userId: userId,
                });
                return `I encountered an error while searching: ${response.message}`;
            } else {
                logger.error({
                    message: "Invalid or unexpected response from semantic_search_meetings backend",
                    response: response,
                    userId: userId,
                });
                return "I received an unexpected response from the search service. Please try again later.";
            }
        } catch (error: any) {
            logger.error({
                message: "Exception calling semantic_search_meetings backend",
                error: error,
                errorMessage: error.message,
                errorStack: error.stack,
                payload: payload,
                userId: userId,
            });
            return "I'm sorry, I ran into a problem trying to search your meeting notes. Please try again later.";
        }
    }
}

// Example of how this might be registered in a main handler (illustrative)
// import { Agent } from "../agent"; // Assuming an Agent class
// import { ApiHelper } from "../apiHelper"; // Assuming an ApiHelper class
//
// const apiHelperInstance = new ApiHelper(); // With appropriate config
// const agent = new Agent();
// agent.registerSkills(new SemanticSearchSkills(apiHelperInstance));
