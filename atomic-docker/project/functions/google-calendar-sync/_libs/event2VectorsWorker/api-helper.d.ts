import { Client } from '@opensearch-project/opensearch';
import { OpenSearchResponseBodyType } from '../types/event2Vectors/types';
export declare const convertEventTitleToOpenAIVector: (title: string) => Promise<number[] | undefined>;
export declare const getSearchClient: () => Promise<Client | undefined>;
export declare const putDataInAllEventIndexInOpenSearch: (id: string, vector: number[], userId: string, start_date: string, end_date: string) => Promise<void>;
export declare const deleteDocInAllEventIndexInOpenSearch: (id: string) => Promise<void>;
export declare const listAllEventWithEventOpenSearch: (userId: string, qVector: number[], startDate: string, endDate: string) => Promise<OpenSearchResponseBodyType>;
