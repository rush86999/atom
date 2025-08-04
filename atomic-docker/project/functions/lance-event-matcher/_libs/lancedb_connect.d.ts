import { Table } from 'vectordb';
import { EventSchema } from './types';
export declare function getEventTable(): Promise<Table<EventSchema>>;
export declare function closeDBConnection(): Promise<void>;
