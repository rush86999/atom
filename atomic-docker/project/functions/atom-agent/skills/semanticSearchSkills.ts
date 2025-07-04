import { ISkill, IAgentSkills, SkillArgs } from "../types"; // ApiHelper removed
import { logger } from "../../_utils/logger";
import axios, { AxiosError } from 'axios'; // Added axios
import { PYTHON_API_SERVICE_BASE_URL } from '../../_libs/constants'; // Added constant import

// Define the expected structure of a single search result from the backend API
interface ApiMeetingSearchResult {
    notion_page_id: string;
    notion_page_title: string;
    notion_page_url: string;
    text_preview: string;
    last_edited: string; // ISO date string
    score: number;
}

// Define the expected structure of the backend API response
interface BackendSearchResponse {
    status: "success" | "error";
    data?: ApiMeetingSearchResult[]; // Use the updated interface
    message?: string;
    // For PythonApiResponse compatibility if needed, though status/data/message is preferred
    ok?: boolean;
    error?: { code: string; message: string; details?: any };
}

export class SemanticSearchSkills implements IAgentSkills {
    // private apiHelper: ApiHelper; // Removed

    constructor() { // Constructor no longer takes ApiHelper
        // this.apiHelper = apiHelper; // Removed
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

    // Changed from private to public to allow standalone function to call it
    public async handleSearchMeetingNotes(args: SkillArgs): Promise<string> {
        const userQuery = args.params?.query as string;
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

            const axiosResponse = await axios.post<BackendSearchResponse>( // Using axios.post
                `${PYTHON_API_SERVICE_BASE_URL}/api/semantic_search_meetings`,
                payload
            );

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
                        } catch (dateError) {
                            logger.warn({
                                message: "Error parsing last_edited date from backend",
                                dateValue: result.last_edited,
                                error: dateError,
                            });
                        }

                        // Include text_preview
                        const preview = result.text_preview ? `\n    Snippet: "${result.text_preview}"` : "";

                        return `- "${result.notion_page_title}" (Edited: ${displayDate}, Score: ${result.score.toFixed(2)})${preview}\n    Link: ${link}`;
                    }).join("\n\n"); // Use double newline for better separation between results
                    return `I found the following meeting notes related to your query:\n\n${formattedResults}`;
                } else {
                    return "Sorry, I couldn't find any meeting notes matching your query.";
                }
            } else if (backendData && backendData.status === "error" && backendData.message) {
                logger.error({
                    message: "Error response from semantic_search_meetings backend",
                    error: backendData.message,
                    code: backendData.error?.code, // Log code if available
                    userId: userId,
                });
                return `I encountered an error while searching: ${backendData.message}${backendData.error?.code ? ` (Code: ${backendData.error.code})` : ''}`;
            } else if (backendData && backendData.ok === false && backendData.error) {
                 logger.error({
                    message: "Error response from semantic_search_meetings backend (PythonApiResponse format)",
                    error: backendData.error, // error is { code, message, details }
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
        } catch (error: any) {
            const axiosError = error as AxiosError;
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
}

// Standalone handler function for easier integration with handler.ts switch statements
export async function handleSemanticSearchMeetingNotesSkill(args: SkillArgs): Promise<string> { // ApiHelper removed
    const skillInstance = new SemanticSearchSkills(); // Constructor is now empty
    return skillInstance.handleSearchMeetingNotes(args);
}
