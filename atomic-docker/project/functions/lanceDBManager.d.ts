import * as lancedb from '@lancedb/lancedb';
/**
 * Initializes and connects to a LanceDB database using the LANCEDB_URI environment variable if set,
 * otherwise defaults to a local path.
 * If the database does not exist at the given path, it will be created.
 * After successful connection, it ensures all necessary LTM tables exist.
 * @param dbName The name of the database (e.g., 'ltm_agent_data'). This is appended to the path.
 * @returns A promise that resolves to the database connection object or null if connection fails.
 */
export declare function initializeDB(dbName: string): Promise<lancedb.Connection | null>;
/**
 * Creates the UserProfiles table if it doesn't already exist.
 * @param db The LanceDB connection object.
 */
export declare function createUserProfilesTable(db: lancedb.Connection): Promise<void>;
/**
 * Creates the KnowledgeBase table if it doesn't already exist.
 * @param db The LanceDB connection object.
 */
export declare function createKnowledgeBaseTable(db: lancedb.Connection): Promise<void>;
/**
 * Creates the ResearchFindings table if it doesn't already exist.
 * @param db The LanceDB connection object.
 */
export declare function createResearchFindingsTable(db: lancedb.Connection): Promise<void>;
/**
 * Ensures that all predefined tables exist in the database.
 * Calls the creation function for each table.
 * @param db The LanceDB connection object.
 */
export declare function ensureTablesExist(db: lancedb.Connection): Promise<void>;
/**
 * Adds one or more records to the specified LanceDB table.
 * @param db The LanceDB connection object.
 * @param tableName The name of the table to add records to.
 * @param data A single record object or an array of record objects.
 */
export declare function addRecord(db: lancedb.Connection, tableName: string, data: Record<string, any> | Record<string, any>[]): Promise<void>;
/**
 * Searches a LanceDB table using a query vector.
 * @param db The LanceDB connection object.
 * @param tableName The name of the table to search.
 * @param queryVector The vector to search with.
 * @param limit The maximum number of results to return (default: 10).
 * @param vectorColumnName The name of the vector column in the table to search against (default: 'embedding').
 * @param filter An optional SQL-like filter string to apply before the vector search.
 * @returns A promise that resolves to an array of search results.
 */
export declare function searchTable(db: lancedb.Connection, tableName: string, queryVector: number[], limit?: number, vectorColumnName?: string, // Default, but should be specified by caller based on table
filter?: string): Promise<any[]>;
/**
 * Updates one or more records in the specified LanceDB table that match a filter.
 * Note: LanceDB's Node.js API for updates might be evolving.
 * This function assumes a conceptual `table.update(values, filter)` method or similar.
 * As of `vectordb-lance@0.2.2`, direct updates based on a filter are not explicitly documented
 * in the same way as `delete(filter)`. This might require a delete-then-add pattern if direct
 * conditional update isn't available or efficient.
 * For simplicity, this example will use `table.mergeInsert` if applicable, or simulate by delete+add.
 * A more robust solution would depend on the exact capabilities of the LanceDB version.
 *
 * This function will update the `updated_at` timestamp automatically.
 *
 * **Important:** This implementation uses a delete-then-add pattern as a workaround for
 * potential limitations in direct conditional updates in some LanceDB Node.js versions.
 * This means the operation is **not atomic** and could lead to data loss if an error
 * occurs after deletion but before re-insertion. Use with caution or ensure the LanceDB
 * version in use supports a more direct and atomic update method.
 *
 * @param db The LanceDB connection object.
 * @param tableName The name of the table to update records in.
 * @param recordIdField The name of the field to identify the record(s) (e.g., 'fact_id', 'user_id').
 * @param recordIdValue The value of the identifier for the record(s) to update.
 * @param updatedFields An object containing the fields to update and their new values.
 *                      Do not include the recordIdField in updatedFields.
 */
export declare function updateRecord(db: lancedb.Connection, tableName: string, recordIdField: string, recordIdValue: string, updatedFields: Record<string, any>): Promise<void>;
/**
 * Deletes one or more records from the specified LanceDB table based on a filter.
 * @param db The LanceDB connection object.
 * @param tableName The name of the table to delete records from.
 * @param recordIdField The name of the field to identify the record(s) (e.g., 'fact_id', 'user_id').
 * @param recordIdValue The value of the identifier for the record(s) to delete.
 */
export declare function deleteRecord(db: lancedb.Connection, tableName: string, recordIdField: string, recordIdValue: string): Promise<void>;
