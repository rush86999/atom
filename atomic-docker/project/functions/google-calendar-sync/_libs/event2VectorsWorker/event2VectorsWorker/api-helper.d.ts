import { Client } from '@opensearch-project/opensearch';
import {
  BulkImportBodyType,
  OpenSearchResponseBodyType,
} from '../types/event2Vectors/types';
export declare const convertEventTitleToOpenAIVector: (
  title: string
) => Promise<number[]>;
export declare const getSearchClient: () => Promise<Client>;
export declare const putDataInAllEventIndexInOpenSearch: (
  id: string,
  vector: number[],
  userId: string,
  start_date: string,
  end_date: string
) => Promise<void>;
export declare const deleteDocInAllEventIndexInOpenSearch: (
  id: string
) => Promise<void>;
export declare const listAllEventWithEventOpenSearch: (
  userId: string,
  qVector: number[],
  startDate: string,
  endDate: string
) => Promise<OpenSearchResponseBodyType>;
export declare const bulkPutDataInAllEventIndexInOpenSearch: (
  bulkImport: BulkImportBodyType[]
) => Promise<void>;
export declare const bulkDeleteDocInAllEventIndexInOpenSearch: (
  ids: string[]
) => Promise<void>;
export declare const bulkDeleteDocInTrainEventIndexInOpenSearch: (
  ids: string[]
) => Promise<void>;
