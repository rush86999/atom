import { ISkill, IAgentSkills, SkillArgs } from "../types";
interface ApiMeetingSearchResult {
    notion_page_id: string;
    notion_page_title: string;
    notion_page_url: string;
    text_preview: string;
    last_edited: string;
    score: number;
}
export declare class SemanticSearchSkills implements IAgentSkills {
    constructor();
    getSkills(): ISkill[];
    handleSearchMeetingNotes(args: SkillArgs): Promise<string | {
        displayType: 'semantic_search_results';
        summaryText: string;
        data: ApiMeetingSearchResult[];
    }>;
}
export declare function handleSemanticSearchMeetingNotesSkill(args: SkillArgs): Promise<string>;
export {};
