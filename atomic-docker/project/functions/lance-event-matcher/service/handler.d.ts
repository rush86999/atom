import { SearchRequest, AIProcessedEvent, LanceEventMatcherResponse } from '../_libs/types';
export declare function eventSearchHandler(searchRequestBody: SearchRequest): Promise<LanceEventMatcherResponse<AIProcessedEvent[]>>;
