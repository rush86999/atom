import { Connection, Table } from '@lancedb/lancedb';
/**
 * Establishes or returns an existing connection to LanceDB.
 */
export declare function getDBConnection(): Promise<Connection>;
export interface EventSchema {
    id: string;
    userId: string;
    vector: number[];
    start_date: string;
    end_date: string;
    raw_event_text: string;
    calendarId?: string;
    last_modified: string;
    title?: string;
    location?: string;
}
export interface TrainingEventSchema {
    id: string;
    userId: string;
    vector: number[];
    source_event_text: string;
    created_at: string;
}
/**
 * Opens an existing table or creates it if it doesn't exist.
 * LanceDB requires sample data (even if empty but typed) or an explicit schema for creation,
 * especially for vector columns and their indexing.
 * @param db The LanceDB connection object.
 * @param tableName The name of the table to get or create.
 * @param sampleData Sample data (can be an empty typed array) to help infer schema on creation.
 *                   It's crucial this sample data (or one item in it) contains all fields,
 *                   especially vector fields, for correct schema setup.
 */
export declare function getOrCreateTable(db: Connection, tableName: string, representativeData: any[]): Promise<Table>;
/**
 * Upserts items into the specified LanceDB table.
 * This implementation assumes an "upsert" is a delete followed by an add.
 * Requires items to have an 'id' field.
 * @param tableName The name of the table.
 * @param items An array of items to upsert. Each item must have an 'id' property.
 * @param representativeItem Sample data (can be an empty typed array with one item) to help infer schema on creation.
 */
export declare function upsertItems(db: Connection, // Pass connection to avoid repeated calls to getDBConnection
tableName: string, items: any[], representativeItemSchema: any[]): Promise<void>;
/**
 * Deletes items from the specified LanceDB table by their IDs.
 * @param tableName The name of the table.
 * @param ids An array of string IDs to delete.
 * @param representativeItemSchema Sample data used if table needs to be "opened" first (though delete usually implies table exists).
 */
export declare function deleteItemsByIds(db: Connection, tableName: string, ids: string[], representativeItemSchema: any[]): Promise<void>;
/**
 * Searches a LanceDB table by a vector, with optional filtering.
 * @param tableName The name of the table to search.
 * @param vector The search vector.
 * @param limit The maximum number of results to return.
 * @param representativeItemSchema Sample data for table schema.
 * @param filterCondition Optional SQL-like filter condition string (e.g., "userId = '123' AND price > 50").
 *                        Ensure column names and values are correctly quoted/formatted for SQL.
 */
export declare function searchTableByVector(db: Connection, tableName: string, vector: number[], limit: number, representativeItemSchema: any[], filterCondition?: string): Promise<any[]>;
/**
 * Retrieves a single item from the specified LanceDB table by its ID.
 * @param tableName The name of the table.
 * @param id The ID of the item to retrieve.
 * @param representativeItemSchema Sample data for table schema.
 * @returns The item if found, otherwise null.
 */
export declare function getItemById(db: Connection, tableName: string, id: string, representativeItemSchema: any[]): Promise<any | null>;
export declare function upsertEvents(items: EventSchema[]): Promise<void>;
export declare function deleteEventsByIds(ids: string[]): Promise<void>;
export declare function searchEvents(vector: number[], limit: number, filterCondition?: string): Promise<EventSchema[]>;
export declare function getEventById(id: string): Promise<EventSchema | null>;
export declare function upsertTrainingEvents(items: TrainingEventSchema[]): Promise<void>;
export declare function deleteTrainingEventsByIds(ids: string[]): Promise<void>;
export declare function searchTrainingEvents(vector: number[], limit: number, filterCondition?: string): Promise<TrainingEventSchema[]>;
export declare function getTrainingEventById(id: string): Promise<TrainingEventSchema | null>;
export declare function getEventDataTable(): Promise<Table>;
export declare function getTrainingDataTable(): Promise<Table>;
