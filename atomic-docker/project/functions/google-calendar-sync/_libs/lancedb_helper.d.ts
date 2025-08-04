import { Connection, Table } from 'vectordb';
interface EventSchema {
    id: string;
    userId: string;
    vector: number[];
    start_date: string;
    end_date: string;
    raw_event_text?: string;
}
export declare function getOrCreateEventTable(db: Connection): Promise<Table<EventSchema>>;
export declare function bulkUpsertToLanceDBEvents(data: EventSchema[]): Promise<void>;
export declare function bulkDeleteFromLanceDBEvents(ids: string[]): Promise<void>;
export {};
