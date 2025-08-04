import { SearchResult, WebResearchSkillResponse } from '../types';
export declare function searchWeb(query: string): Promise<WebResearchSkillResponse<SearchResult[]>>;
