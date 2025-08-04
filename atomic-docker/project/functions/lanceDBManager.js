// Manages LanceDB connections and table initializations for LTM
import * as lancedb from '@lancedb/lancedb';
// Schema, Field, etc. should be directly available from '@lancedb/lancedb/arrow' or similar if exposed,
// or directly from the main package if re-exported.
// For now, assuming they are directly available or re-exported by '@lancedb/lancedb'
// If not, this will need adjustment based on the actual package structure of '@lancedb/lancedb'.
import { Schema, Field, Float32, Utf8, Timestamp, List, FixedSizeList, } from '@lancedb/lancedb/arrow';
const DEFAULT_LTM_DB_PATH_PREFIX = './lance_db/'; // Default base path if LANCEDB_URI is not set
const DEFAULT_VECTOR_DIMENSION = 1536;
function log(message, level = 'info') {
    const prefix = `[LanceDBManager] ${new Date().toISOString()}`;
    if (level === 'error') {
        console.error(`${prefix} [ERROR]: ${message}`);
    }
    else {
        console.log(`${prefix}: ${message}`);
    }
}
/**
 * Initializes and connects to a LanceDB database.
 * If the database does not exist at the given path, it will be created.
 * @param dbName The name of the database (e.g., 'ltm_agent_data').
 * @returns A promise that resolves to the database connection object or null if connection fails.
 */
// Define Schemas based on LANCEDB_LTM_SCHEMAS.md (with assumptions)
// UserProfiles Schema
const userProfilesSchema = new Schema([
    new Field('user_id', new Utf8(), false), // Not nullable (Primary Key)
    new Field('preferences', new Utf8(), true), // JSON string
    new Field('interaction_summary_embeddings', new FixedSizeList(DEFAULT_VECTOR_DIMENSION, new Field('item', new Float32(), true)), true), // Embedding of a holistic summary of all user interactions
    // interaction_history_embeddings field removed as individual interaction history is stored in knowledge_base table
    new Field('interaction_summaries', new List(new Field('item', new Utf8(), true)), true), // Curated list of key textual interaction summaries
    new Field('created_at', new Timestamp('ms'), true),
    new Field('updated_at', new Timestamp('ms'), true),
]);
// KnowledgeBase Schema
const knowledgeBaseSchema = new Schema([
    new Field('fact_id', new Utf8(), false), // Not nullable (Primary Key)
    new Field('text_content', new Utf8(), true),
    new Field('text_content_embedding', new FixedSizeList(DEFAULT_VECTOR_DIMENSION, new Field('item', new Float32(), true)), true),
    new Field('source', new Utf8(), true), // Origin of the information
    new Field('metadata', new Utf8(), true), // JSON string for tags, categories, etc.
    new Field('created_at', new Timestamp('ms'), true),
    new Field('updated_at', new Timestamp('ms'), true),
    new Field('feedback_status', new Utf8(), true), // e.g., 'verified', 'unreviewed', 'flagged_inaccurate', 'flagged_outdated'
    new Field('feedback_notes', new Utf8(), true), // Optional textual notes for feedback
]);
// ResearchFindings Schema
const researchFindingsSchema = new Schema([
    new Field('finding_id', new Utf8(), false), // Not nullable (Primary Key)
    new Field('query', new Utf8(), true),
    new Field('query_embedding', new FixedSizeList(DEFAULT_VECTOR_DIMENSION, new Field('item', new Float32(), true)), true),
    new Field('summary', new Utf8(), true),
    new Field('summary_embedding', new FixedSizeList(DEFAULT_VECTOR_DIMENSION, new Field('item', new Float32(), true)), true),
    new Field('details_text', new Utf8(), true), // Detailed findings
    new Field('source_references', new List(new Field('item', new Utf8(), true)), true), // List of URLs or identifiers
    new Field('project_page_id', new Utf8(), true), // Optional link to Notion page
    new Field('created_at', new Timestamp('ms'), true),
    new Field('updated_at', new Timestamp('ms'), true),
    new Field('feedback_status', new Utf8(), true), // e.g., 'verified', 'unreviewed', 'flagged_inaccurate', 'flagged_outdated'
    new Field('feedback_notes', new Utf8(), true), // Optional textual notes for feedback
]);
/**
 * Initializes and connects to a LanceDB database using the LANCEDB_URI environment variable if set,
 * otherwise defaults to a local path.
 * If the database does not exist at the given path, it will be created.
 * After successful connection, it ensures all necessary LTM tables exist.
 * @param dbName The name of the database (e.g., 'ltm_agent_data'). This is appended to the path.
 * @returns A promise that resolves to the database connection object or null if connection fails.
 */
export async function initializeDB(dbName) {
    const lanceDbUriFromEnv = process.env.LANCEDB_URI;
    let dbPath;
    if (lanceDbUriFromEnv) {
        // Assuming LANCEDB_URI is a directory path. Append dbName.lance to it.
        // Ensure it ends with a slash if it's a directory.
        const baseUri = lanceDbUriFromEnv.endsWith('/')
            ? lanceDbUriFromEnv
            : `${lanceDbUriFromEnv}/`;
        dbPath = `${baseUri}${dbName}.lance`;
        log(`Using LANCEDB_URI from environment: ${baseUri}`);
    }
    else {
        dbPath = `${DEFAULT_LTM_DB_PATH_PREFIX}${dbName}.lance`;
        log(`LANCEDB_URI not set in environment. Using default path prefix: ${DEFAULT_LTM_DB_PATH_PREFIX}`, 'info');
    }
    log(`Initializing LanceDB at path: ${dbPath}`);
    try {
        // Ensure the directory exists before connecting (lancedb.connect might not create it)
        // This part might need adjustment based on OS and permissions.
        // For simplicity, assuming the directory structure is managed externally or lancedb handles it.
        // For local file-based DBs, make sure the path is writable.
        const db = await lancedb.connect(dbPath);
        log(`Successfully connected to LanceDB: ${dbPath}`);
        await ensureTablesExist(db);
        return db;
    }
    catch (error) {
        log(`Error connecting to or creating LanceDB at ${dbPath}: ${error.message || error}`, 'error');
        return null;
    }
}
/**
 * Creates the UserProfiles table if it doesn't already exist.
 * @param db The LanceDB connection object.
 */
export async function createUserProfilesTable(db) {
    if (!db) {
        log('Database connection not provided to createUserProfilesTable.', 'error');
        return;
    }
    const tableName = 'user_profiles';
    try {
        log(`Attempting to create table: ${tableName}.`);
        // Provide an empty array of the correct type for schema creation if no initial data.
        // LanceDB uses Arrow schema, which can be explicitly defined.
        // The `lancedb` package (version 0.8.0) uses `createTable(name, data)` or `createTable(name, schema)`
        // and `openTable(name)` or `openTable(name, schema)`.
        // `createTable` with mode 'create' should attempt to create.
        // If it fails because it exists, we catch that.
        try {
            await db.openTable(tableName);
            log(`Table '${tableName}' already exists. No action taken.`);
        }
        catch (e) {
            // Assuming error means table does not exist
            log(`Table '${tableName}' does not exist. Attempting to create.`);
            await db.createTable(tableName, userProfilesSchema); // Removed mode, as it might not be supported or needed if openTable fails for non-existence
            log(`Table '${tableName}' created successfully.`);
        }
    }
    catch (error) {
        // This outer catch is for errors during the creation attempt itself, not for "already exists"
        log(`Error during table creation process for '${tableName}': ${error.message || error}`, 'error');
    }
}
/**
 * Creates the KnowledgeBase table if it doesn't already exist.
 * @param db The LanceDB connection object.
 */
export async function createKnowledgeBaseTable(db) {
    if (!db) {
        log('Database connection not provided to createKnowledgeBaseTable.', 'error');
        return;
    }
    const tableName = 'knowledge_base';
    try {
        log(`Attempting to create table: ${tableName}.`);
        try {
            await db.openTable(tableName);
            log(`Table '${tableName}' already exists. No action taken.`);
        }
        catch (e) {
            log(`Table '${tableName}' does not exist. Attempting to create.`);
            await db.createTable(tableName, knowledgeBaseSchema);
            log(`Table '${tableName}' created successfully.`);
        }
    }
    catch (error) {
        log(`Error during table creation process for '${tableName}': ${error.message || error}`, 'error');
    }
}
/**
 * Creates the ResearchFindings table if it doesn't already exist.
 * @param db The LanceDB connection object.
 */
export async function createResearchFindingsTable(db) {
    if (!db) {
        log('Database connection not provided to createResearchFindingsTable.', 'error');
        return;
    }
    const tableName = 'research_findings';
    try {
        log(`Attempting to create table: ${tableName}.`);
        try {
            await db.openTable(tableName);
            log(`Table '${tableName}' already exists. No action taken.`);
        }
        catch (e) {
            log(`Table '${tableName}' does not exist. Attempting to create.`);
            await db.createTable(tableName, researchFindingsSchema);
            log(`Table '${tableName}' created successfully.`);
        }
    }
    catch (error) {
        log(`Error during table creation process for '${tableName}': ${error.message || error}`, 'error');
    }
}
/**
 * Ensures that all predefined tables exist in the database.
 * Calls the creation function for each table.
 * @param db The LanceDB connection object.
 */
export async function ensureTablesExist(db) {
    if (!db) {
        log('Database connection not provided to ensureTablesExist.', 'error');
        return;
    }
    log('Ensuring all LTM tables exist...');
    await createUserProfilesTable(db);
    await createKnowledgeBaseTable(db);
    await createResearchFindingsTable(db);
    log('Finished checking/creating LTM tables.');
}
/**
 * Adds one or more records to the specified LanceDB table.
 * @param db The LanceDB connection object.
 * @param tableName The name of the table to add records to.
 * @param data A single record object or an array of record objects.
 */
export async function addRecord(db, tableName, data) {
    if (!db) {
        log('Database connection not provided to addRecord.', 'error');
        return Promise.reject(new Error('Database connection not provided.'));
    }
    if (!tableName) {
        log('Table name not provided to addRecord.', 'error');
        return Promise.reject(new Error('Table name not provided.'));
    }
    if (!data || (Array.isArray(data) && data.length === 0)) {
        log('No data provided to addRecord.', 'error');
        return Promise.reject(new Error('No data provided.'));
    }
    try {
        log(`Attempting to open table '${tableName}' for adding records.`);
        const table = await db.openTable(tableName);
        log(`Table '${tableName}' opened. Adding ${Array.isArray(data) ? data.length : 1} record(s).`);
        await table.add(data);
        log(`Successfully added record(s) to table '${tableName}'.`);
    }
    catch (error) {
        log(`Error adding record(s) to table '${tableName}': ${error.message}`, 'error');
        if (error.message && error.message.includes('does not exist')) {
            // Or similar error message
            log(`Table '${tableName}' not found. Please ensure it is created before adding records.`, 'error');
        }
        // console.error("Full error object:", error); // For debugging
        return Promise.reject(error); // Re-throw the error or a custom one
    }
}
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
export async function searchTable(db, tableName, queryVector, limit = 10, vectorColumnName = 'embedding', // Default, but should be specified by caller based on table
filter) {
    if (!db) {
        log('Database connection not provided to searchTable.', 'error');
        return Promise.reject(new Error('Database connection not provided.'));
    }
    if (!tableName) {
        log('Table name not provided to searchTable.', 'error');
        return Promise.reject(new Error('Table name not provided.'));
    }
    if (!queryVector || queryVector.length === 0) {
        log('Query vector not provided or empty to searchTable.', 'error');
        return Promise.reject(new Error('Query vector not provided or empty.'));
    }
    try {
        log(`Attempting to open table '${tableName}' for searching.`);
        const table = await db.openTable(tableName);
        log(`Table '${tableName}' opened. Searching with vector column '${vectorColumnName}', limit ${limit}. Filter: '${filter || 'None'}'`);
        let searchQuery = table
            .search(queryVector, vectorColumnName) // Pass vectorColumnName to search if API supports it, else it uses default.
            .select(['*', '_distance']) // Select all columns and the distance
            .limit(limit);
        if (filter) {
            searchQuery = searchQuery.where(filter);
            log(`Applied filter to search: ${filter}`);
        }
        const results = await searchQuery.execute();
        log(`Search completed on table '${tableName}'. Found ${results.length} results.`);
        return results;
    }
    catch (error) {
        log(`Error searching table '${tableName}': ${error.message}`, 'error');
        if (error.message && error.message.includes('does not exist')) {
            log(`Table '${tableName}' not found. Cannot perform search.`, 'error');
        }
        else if (error.message && error.message.includes('vector_column')) {
            // Example of a specific error
            log(`Potential issue with vector column name '${vectorColumnName}' or its configuration in table '${tableName}'.`, 'error');
        }
        // console.error("Full error object:", error); // For debugging
        return Promise.reject(error); // Re-throw the error or a custom one
    }
}
// Example usage (optional, for testing or direct invocation)
/*
async function setupDatabase() {
  log("Starting database setup example...");
  const dbInstance = await initializeDB('ltm_agent_data');

  if (dbInstance) {
    log("Database initialized and tables ensured.");
    // You could add example data insertion here for testing
    // For example:
    // const userProfiles = await dbInstance.openTable('user_profiles');
    // Example: Add a record
    // const testRecord = {
    //   user_id: `user_${Date.now()}`,
    //   preferences: JSON.stringify({ theme: 'dark' }),
    //   interaction_summary_embeddings: Array(DEFAULT_VECTOR_DIMENSION).fill(0.5),
    //   interaction_history_embeddings: Array(DEFAULT_VECTOR_DIMENSION).fill(0.3),
    //   interaction_summaries: ["summary 1", "summary 2"],
    //   created_at: new Date(),
    //   updated_at: new Date()
    // };
    // await addRecord(dbInstance, 'user_profiles', testRecord);
    // log('Test record added to user_profiles.');

    // Example: Search the table
    // const_query_vector = Array(DEFAULT_VECTOR_DIMENSION).fill(0.45);
    // const searchResults = await searchTable(dbInstance, 'user_profiles', _query_vector, 5, 'interaction_summary_embeddings');
    // log('Search results from user_profiles:', searchResults);

  } else {
    log("Database initialization failed.", 'error');
  }
}

// To run this example:
// 1. Ensure you have a compatible environment for lancedb (e.g., Node.js with required build tools if lancedb has native components)
// 2. Run `npm install` or `pnpm install` to get `vectordb-lance`
// 3. Execute this file: `node --loader ts-node/esm ./atomic-docker/project/functions/lanceDBManager.ts` (if you have ts-node)
//    or compile to JS first and then run with node.

// Uncomment to run setup when this file is executed directly
// setupDatabase().then(() => log("Example setup finished.")).catch(e => log(`Example setup failed: ${e}`, 'error'));
*/
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
export async function updateRecord(db, tableName, recordIdField, recordIdValue, updatedFields) {
    if (!db) {
        log('Database connection not provided to updateRecord.', 'error');
        return Promise.reject(new Error('Database connection not provided.'));
    }
    if (!tableName || !recordIdField || !recordIdValue) {
        log('Table name, recordIdField, or recordIdValue not provided to updateRecord.', 'error');
        return Promise.reject(new Error('Table name, recordIdField, or recordIdValue not provided.'));
    }
    if (!updatedFields || Object.keys(updatedFields).length === 0) {
        log('No fields to update provided to updateRecord.', 'error');
        return Promise.reject(new Error('No fields to update provided.'));
    }
    if (updatedFields.hasOwnProperty(recordIdField)) {
        log(`Cannot update the record ID field ('${recordIdField}') itself.`, 'error');
        return Promise.reject(new Error(`Cannot update the record ID field ('${recordIdField}') itself.`));
    }
    const filter = `${recordIdField} = '${recordIdValue}'`;
    log(`Attempting to update record(s) in table '${tableName}' where ${filter}.`);
    try {
        const table = await db.openTable(tableName);
        // Add/update the 'updated_at' timestamp
        const finalUpdatedFields = {
            ...updatedFields,
            updated_at: new Date().toISOString(),
        };
        // LanceDB's `update` method (added in later versions, e.g., 0.4.x for Python, check Node.js specifics)
        // If table.update(finalUpdatedFields, filter) exists and works:
        // await table.update(finalUpdatedFields, filter);
        // log(`Successfully initiated update for record(s) in table '${tableName}' where ${filter}.`);
        // Workaround if direct update is not available/suitable: Delete and Add.
        // This is less efficient and not atomic.
        // 1. Fetch the records to be updated.
        const recordsToUpdate = await table.search().where(filter).execute();
        if (recordsToUpdate.length === 0) {
            log(`No records found in table '${tableName}' matching filter '${filter}'. Nothing to update.`);
            return;
        }
        log(`Found ${recordsToUpdate.length} record(s) to update. Performing delete and add.`);
        // 2. Delete the old records.
        await table.delete(filter);
        log(`Deleted ${recordsToUpdate.length} old record(s).`);
        // 3. Prepare new records with updated fields.
        const newRecords = recordsToUpdate.map((record) => {
            const { _distance, ...oldRecordFields } = record; // Remove _distance if present
            return { ...oldRecordFields, ...finalUpdatedFields };
        });
        // 4. Add the updated records.
        await table.add(newRecords);
        log(`Added ${newRecords.length} updated record(s) to table '${tableName}'.`);
    }
    catch (error) {
        log(`Error updating record(s) in table '${tableName}': ${error.message}`, 'error');
        // console.error("Full error object:", error); // For debugging
        return Promise.reject(error);
    }
}
/**
 * Deletes one or more records from the specified LanceDB table based on a filter.
 * @param db The LanceDB connection object.
 * @param tableName The name of the table to delete records from.
 * @param recordIdField The name of the field to identify the record(s) (e.g., 'fact_id', 'user_id').
 * @param recordIdValue The value of the identifier for the record(s) to delete.
 */
export async function deleteRecord(db, tableName, recordIdField, recordIdValue) {
    if (!db) {
        log('Database connection not provided to deleteRecord.', 'error');
        return Promise.reject(new Error('Database connection not provided.'));
    }
    if (!tableName || !recordIdField || !recordIdValue) {
        log('Table name, recordIdField, or recordIdValue not provided to deleteRecord.', 'error');
        return Promise.reject(new Error('Table name, recordIdField, or recordIdValue not provided.'));
    }
    const filter = `${recordIdField} = '${recordIdValue}'`;
    log(`Attempting to delete record(s) from table '${tableName}' where ${filter}.`);
    try {
        const table = await db.openTable(tableName);
        await table.delete(filter);
        log(`Successfully deleted record(s) (if they existed) from table '${tableName}' where ${filter}.`);
    }
    catch (error) {
        log(`Error deleting record(s) from table '${tableName}': ${error.message}`, 'error');
        // console.error("Full error object:", error); // For debugging
        return Promise.reject(error);
    }
}
log('LanceDBManager module loaded with table creation and CRUD logic.');
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoibGFuY2VEQk1hbmFnZXIuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJsYW5jZURCTWFuYWdlci50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiQUFBQSxnRUFBZ0U7QUFDaEUsT0FBTyxLQUFLLE9BQU8sTUFBTSxrQkFBa0IsQ0FBQztBQUM1Qyx3R0FBd0c7QUFDeEcsb0RBQW9EO0FBQ3BELHFGQUFxRjtBQUNyRixpR0FBaUc7QUFDakcsT0FBTyxFQUNMLE1BQU0sRUFDTixLQUFLLEVBQ0wsT0FBTyxFQUNQLElBQUksRUFDSixTQUFTLEVBQ1QsSUFBSSxFQUNKLGFBQWEsR0FDZCxNQUFNLHdCQUF3QixDQUFDO0FBRWhDLE1BQU0sMEJBQTBCLEdBQUcsYUFBYSxDQUFDLENBQUMsOENBQThDO0FBQ2hHLE1BQU0sd0JBQXdCLEdBQUcsSUFBSSxDQUFDO0FBRXRDLFNBQVMsR0FBRyxDQUFDLE9BQWUsRUFBRSxRQUEwQixNQUFNO0lBQzVELE1BQU0sTUFBTSxHQUFHLG9CQUFvQixJQUFJLElBQUksRUFBRSxDQUFDLFdBQVcsRUFBRSxFQUFFLENBQUM7SUFDOUQsSUFBSSxLQUFLLEtBQUssT0FBTyxFQUFFLENBQUM7UUFDdEIsT0FBTyxDQUFDLEtBQUssQ0FBQyxHQUFHLE1BQU0sYUFBYSxPQUFPLEVBQUUsQ0FBQyxDQUFDO0lBQ2pELENBQUM7U0FBTSxDQUFDO1FBQ04sT0FBTyxDQUFDLEdBQUcsQ0FBQyxHQUFHLE1BQU0sS0FBSyxPQUFPLEVBQUUsQ0FBQyxDQUFDO0lBQ3ZDLENBQUM7QUFDSCxDQUFDO0FBRUQ7Ozs7O0dBS0c7QUFDSCxvRUFBb0U7QUFFcEUsc0JBQXNCO0FBQ3RCLE1BQU0sa0JBQWtCLEdBQUcsSUFBSSxNQUFNLENBQUM7SUFDcEMsSUFBSSxLQUFLLENBQUMsU0FBUyxFQUFFLElBQUksSUFBSSxFQUFFLEVBQUUsS0FBSyxDQUFDLEVBQUUsNkJBQTZCO0lBQ3RFLElBQUksS0FBSyxDQUFDLGFBQWEsRUFBRSxJQUFJLElBQUksRUFBRSxF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QU0sS0FBSyxDQUFDLE1BQU0sQ0FBQyxNQUFNLENBQUMsQ0FBQztRQUMzQixHQUFHLENBQ0QsZ0VBQWdFLFNBQVMsV0FBVyxNQUFNLEdBQUcsQ0FDOUYsQ0FBQztJQUNKLENBQUM7SUFBQyxPQUFPLEtBQVUsRUFBRSxDQUFDO1FBQ3BCLEdBQUcsQ0FDRCx3Q0FBd0MsU0FBUyxNQUFNLEtBQUssQ0FBQyxPQUFPLEVBQUUsRUFDdEUsT0FBTyxDQUNSLENBQUM7UUFDRiwrREFBK0Q7UUFDL0QsT0FBTyxPQUFPLENBQUMsTUFBTSxDQUFDLEtBQUssQ0FBQyxDQUFDO0lBQy9CLENBQUM7QUFDSCxDQUFDO0FBRUQsR0FBRyxDQUFDLGtFQUFrRSxDQUFDLENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyIvLyBNYW5hZ2VzIExhbmNlREIgY29ubmVjdGlvbnMgYW5kIHRhYmxlIGluaXRpYWxpemF0aW9ucyBmb3IgTFRNXG5pbXBvcnQgKiBhcyBsYW5jZWRiIGZyb20gJ0BsYW5jZWRiL2xhbmNlZGInO1xuLy8gU2NoZW1hLCBGaWVsZCwgZXRjLiBzaG91bGQgYmUgZGlyZWN0bHkgYXZhaWxhYmxlIGZyb20gJ0BsYW5jZWRiL2xhbmNlZGIvYXJyb3cnIG9yIHNpbWlsYXIgaWYgZXhwb3NlZCxcbi8vIG9yIGRpcmVjdGx5IGZyb20gdGhlIG1haW4gcGFja2FnZSBpZiByZS1leHBvcnRlZC5cbi8vIEZvciBub3csIGFzc3VtaW5nIHRoZXkgYXJlIGRpcmVjdGx5IGF2YWlsYWJsZSBvciByZS1leHBvcnRlZCBieSAnQGxhbmNlZGIvbGFuY2VkYidcbi8vIElmIG5vdCwgdGhpcyB3aWxsIG5lZWQgYWRqdXN0bWVudCBiYXNlZCBvbiB0aGUgYWN0dWFsIHBhY2thZ2Ugc3RydWN0dXJlIG9mICdAbGFuY2VkYi9sYW5jZWRiJy5cbmltcG9ydCB7XG4gIFNjaGVtYSxcbiAgRmllbGQsXG4gIEZsb2F0MzIsXG4gIFV0ZjgsXG4gIFRpbWVzdGFtcCxcbiAgTGlzdCxcbiAgRml4ZWRTaXplTGlzdCxcbn0gZnJvbSAnQGxhbmNlZGIvbGFuY2VkYi9hcnJvdyc7XG5cbmNvbnN0IERFRkFVTFRfTFRNX0RCX1BBVEhfUFJFRklYID0gJy4vbGFuY2VfZGIvJzsgLy8gRGVmYXVsdCBiYXNlIHBhdGggaWYgTEFOQ0VEQl9VUkkgaXMgbm90IHNldFxuY29uc3QgREVGQVVMVF9WRUNUT1JfRElNRU5TSU9OID0gMTUzNjtcblxuZnVuY3Rpb24gbG9nKG1lc3NhZ2U6IHN0cmluZywgbGV2ZWw6ICdpbmZvJyB8ICdlcnJvcicgPSAnaW5mbycpIHtcbiAgY29uc3QgcHJlZml4ID0gYFtMYW5jZURCTWFuYWdlcl0gJHtuZXcgRGF0ZSgpLnRvSVNPU3RyaW5nKCl9YDtcbiAgaWYgKGxldmVsID09PSAnZXJyb3InKSB7XG4gICAgY29uc29sZS5lcnJvcihgJHtwcmVmaXh9IFtFUlJPUl06ICR7bWVzc2FnZX1gKTtcbiAgfSBlbHNlIHtcbiAgICBjb25zb2xlLmxvZyhgJHtwcmVmaXh9OiAke21lc3NhZ2V9YCk7XG4gIH1cbn1cblxuLyoqXG4gKiBJbml0aWFsaXplcyBhbmQgY29ubmVjdHMgdG8gYSBMYW5jZURCIGRhdGFiYXNlLlxuICogSWYgdGhlIGRhdGFiYXNlIGRvZXMgbm90IGV4aXN0IGF0IHRoZSBnaXZlbiBwYXRoLCBpdCB3aWxsIGJlIGNyZWF0ZWQuXG4gKiBAcGFyYW0gZGJOYW1lIFRoZSBuYW1lIG9mIHRoZSBkYXRhYmFzZSAoZS5nLiwgJ2x0bV9hZ2VudF9kYXRhJykuXG4gKiBAcmV0dXJucyBBIHByb21pc2UgdGhhdCByZXNvbHZlcyB0byB0aGUgZGF0YWJhc2UgY29ubmVjdGlvbiBvYmplY3Qgb3IgbnVsbCBpZiBjb25uZWN0aW9uIGZhaWxzLlxuICovXG4vLyBEZWZpbmUgU2NoZW1hcyBiYXNlZCBvbiBMQU5DRURCX0xUTV9TQ0hFTUFTLm1kICh3aXRoIGFzc3VtcHRpb25zKVxuXG4vLyBVc2VyUHJvZmlsZXMgU2NoZW1hXG5jb25zdCB1c2VyUHJvZmlsZXNTY2hlbWEgPSBuZXcgU2NoZW1hKFtcbiAgbmV3IEZpZWxkKCd1c2VyX2lkJywgbmV3IFV0ZjgoKSwgZmFsc2UpLCAvLyBOb3QgbnVsbGFibGUgKFByaW1hcnkgS2V5KVxuICBuZXcgRmllbGQoJ3ByZWZlcmVuY2VzJywgbmV3IFV0ZjgoKSwgdHJ1ZSksIC8vIEpTT04gc3RyaW5nXG4gIG5ldyBGaWVsZChcbiAgICAnaW50ZXJhY3Rpb25fc3VtbWFyeV9lbWJlZGRpbmdzJyxcbiAgICBuZXcgRml4ZWRTaXplTGlzdChcbiAgICAgIERFRkFVTFRfVkVDVE9SX0RJTUVOU0lPTixcbiAgICAgIG5ldyBGaWVsZCgnaXRlbScsIG5ldyBGbG9hdDMyKCksIHRydWUpXG4gICAgKSxcbiAgICB0cnVlXG4gICksIC8vIEVtYmVkZGluZyBvZiBhIGhvbGlzdGljIHN1bW1hcnkgb2YgYWxsIHVzZXIgaW50ZXJhY3Rpb25zXG4gIC8vIGludGVyYWN0aW9uX2hpc3RvcnlfZW1iZWRkaW5ncyBmaWVsZCByZW1vdmVkIGFzIGluZGl2aWR1YWwgaW50ZXJhY3Rpb24gaGlzdG9yeSBpcyBzdG9yZWQgaW4ga25vd2xlZGdlX2Jhc2UgdGFibGVcbiAgbmV3IEZpZWxkKFxuICAgICdpbnRlcmFjdGlvbl9zdW1tYXJpZXMnLFxuICAgIG5ldyBMaXN0KG5ldyBGaWVsZCgnaXRlbScsIG5ldyBVdGY4KCksIHRydWUpKSxcbiAgICB0cnVlXG4gICksIC8vIEN1cmF0ZWQgbGlzdCBvZiBrZXkgdGV4dHVhbCBpbnRlcmFjdGlvbiBzdW1tYXJpZXNcbiAgbmV3IEZpZWxkKCdjcmVhdGVkX2F0JywgbmV3IFRpbWVzdGFtcCgnbXMnKSwgdHJ1ZSksXG4gIG5ldyBGaWVsZCgndXBkYXRlZF9hdCcsIG5ldyBUaW1lc3RhbXAoJ21zJyksIHRydWUpLFxuXSk7XG5cbi8vIEtub3dsZWRnZUJhc2UgU2NoZW1hXG5jb25zdCBrbm93bGVkZ2VCYXNlU2NoZW1hID0gbmV3IFNjaGVtYShbXG4gIG5ldyBGaWVsZCgnZmFjdF9pZCcsIG5ldyBVdGY4KCksIGZhbHNlKSwgLy8gTm90IG51bGxhYmxlIChQcmltYXJ5IEtleSlcbiAgbmV3IEZpZWxkKCd0ZXh0X2NvbnRlbnQnLCBuZXcgVXRmOCgpLCB0cnVlKSxcbiAgbmV3IEZpZWxkKFxuICAgICd0ZXh0X2NvbnRlbnRfZW1iZWRkaW5nJyxcbiAgICBuZXcgRml4ZWRTaXplTGlzdChcbiAgICAgIERFRkFVTFRfVkVDVE9SX0RJTUVOU0lPTixcbiAgICAgIG5ldyBGaWVsZCgnaXRlbScsIG5ldyBGbG9hdDMyKCksIHRydWUpXG4gICAgKSxcbiAgICB0cnVlXG4gICksXG4gIG5ldyBGaWVsZCgnc291cmNlJywgbmV3IFV0ZjgoKSwgdHJ1ZSksIC8vIE9yaWdpbiBvZiB0aGUgaW5mb3JtYXRpb25cbiAgbmV3IEZpZWxkKCdtZXRhZGF0YScsIG5ldyBVdGY4KCksIHRydWUpLCAvLyBKU09OIHN0cmluZyBmb3IgdGFncywgY2F0ZWdvcmllcywgZXRjLlxuICBuZXcgRmllbGQoJ2NyZWF0ZWRfYXQnLCBuZXcgVGltZXN0YW1wKCdtcycpLCB0cnVlKSxcbiAgbmV3IEZpZWxkKCd1cGRhdGVkX2F0JywgbmV3IFRpbWVzdGFtcCgnbXMnKSwgdHJ1ZSksXG4gIG5ldyBGaWVsZCgnZmVlZGJhY2tfc3RhdHVzJywgbmV3IFV0ZjgoKSwgdHJ1ZSksIC8vIGUuZy4sICd2ZXJpZmllZCcsICd1bnJldmlld2VkJywgJ2ZsYWdnZWRfaW5hY2N1cmF0ZScsICdmbGFnZ2VkX291dGRhdGVkJ1xuICBuZXcgRmllbGQoJ2ZlZWRiYWNrX25vdGVzJywgbmV3IFV0ZjgoKSwgdHJ1ZSksIC8vIE9wdGlvbmFsIHRleHR1YWwgbm90ZXMgZm9yIGZlZWRiYWNrXG5dKTtcblxuLy8gUmVzZWFyY2hGaW5kaW5ncyBTY2hlbWFcbmNvbnN0IHJlc2VhcmNoRmluZGluZ3NTY2hlbWEgPSBuZXcgU2NoZW1hKFtcbiAgbmV3IEZpZWxkKCdmaW5kaW5nX2lkJywgbmV3IFV0ZjgoKSwgZmFsc2UpLCAvLyBOb3QgbnVsbGFibGUgKFByaW1hcnkgS2V5KVxuICBuZXcgRmllbGQoJ3F1ZXJ5JywgbmV3IFV0ZjgoKSwgdHJ1ZSksXG4gIG5ldyBGaWVsZChcbiAgICAncXVlcnlfZW1iZWRkaW5nJyxcbiAgICBuZXcgRml4ZWRTaXplTGlzdChcbiAgICAgIERFRkFVTFRfVkVDVE9SX0RJTUVOU0lPTixcbiAgICAgIG5ldyBGaWVsZCgnaXRlbScsIG5ldyBGbG9hdDMyKCksIHRydWUpXG4gICAgKSxcbiAgICB0cnVlXG4gICksXG4gIG5ldyBGaWVsZCgnc3VtbWFyeScsIG5ldyBVdGY4KCksIHRydWUpLFxuICBuZXcgRmllbGQoXG4gICAgJ3N1bW1hcnlfZW1iZWRkaW5nJyxcbiAgICBuZXcgRml4ZWRTaXplTGlzdChcbiAgICAgIERFRkFVTFRfVkVDVE9SX0RJTUVOU0lPTixcbiAgICAgIG5ldyBGaWVsZCgnaXRlbScsIG5ldyBGbG9hdDMyKCksIHRydWUpXG4gICAgKSxcbiAgICB0cnVlXG4gICksXG4gIG5ldyBGaWVsZCgnZGV0YWlsc190ZXh0JywgbmV3IFV0ZjgoKSwgdHJ1ZSksIC8vIERldGFpbGVkIGZpbmRpbmdzXG4gIG5ldyBGaWVsZChcbiAgICAnc291cmNlX3JlZmVyZW5jZXMnLFxuICAgIG5ldyBMaXN0KG5ldyBGaWVsZCgnaXRlbScsIG5ldyBVdGY4KCksIHRydWUpKSxcbiAgICB0cnVlXG4gICksIC8vIExpc3Qgb2YgVVJMcyBvciBpZGVudGlmaWVyc1xuICBuZXcgRmllbGQoJ3Byb2plY3RfcGFnZV9pZCcsIG5ldyBVdGY4KCksIHRydWUpLCAvLyBPcHRpb25hbCBsaW5rIHRvIE5vdGlvbiBwYWdlXG4gIG5ldyBGaWVsZCgnY3JlYXRlZF9hdCcsIG5ldyBUaW1lc3RhbXAoJ21zJyksIHRydWUpLFxuICBuZXcgRmllbGQoJ3VwZGF0ZWRfYXQnLCBuZXcgVGltZXN0YW1wKCdtcycpLCB0cnVlKSxcbiAgbmV3IEZpZWxkKCdmZWVkYmFja19zdGF0dXMnLCBuZXcgVXRmOCgpLCB0cnVlKSwgLy8gZS5nLiwgJ3ZlcmlmaWVkJywgJ3VucmV2aWV3ZWQnLCAnZmxhZ2dlZF9pbmFjY3VyYXRlJywgJ2ZsYWdnZWRfb3V0ZGF0ZWQnXG4gIG5ldyBGaWVsZCgnZmVlZGJhY2tfbm90ZXMnLCBuZXcgVXRmOCgpLCB0cnVlKSwgLy8gT3B0aW9uYWwgdGV4dHVhbCBub3RlcyBmb3IgZmVlZGJhY2tcbl0pO1xuXG4vKipcbiAqIEluaXRpYWxpemVzIGFuZCBjb25uZWN0cyB0byBhIExhbmNlREIgZGF0YWJhc2UgdXNpbmcgdGhlIExBTkNFREJfVVJJIGVudmlyb25tZW50IHZhcmlhYmxlIGlmIHNldCxcbiAqIG90aGVyd2lzZSBkZWZhdWx0cyB0byBhIGxvY2FsIHBhdGguXG4gKiBJZiB0aGUgZGF0YWJhc2UgZG9lcyBub3QgZXhpc3QgYXQgdGhlIGdpdmVuIHBhdGgsIGl0IHdpbGwgYmUgY3JlYXRlZC5cbiAqIEFmdGVyIHN1Y2Nlc3NmdWwgY29ubmVjdGlvbiwgaXQgZW5zdXJlcyBhbGwgbmVjZXNzYXJ5IExUTSB0YWJsZXMgZXhpc3QuXG4gKiBAcGFyYW0gZGJOYW1lIFRoZSBuYW1lIG9mIHRoZSBkYXRhYmFzZSAoZS5nLiwgJ2x0bV9hZ2VudF9kYXRhJykuIFRoaXMgaXMgYXBwZW5kZWQgdG8gdGhlIHBhdGguXG4gKiBAcmV0dXJucyBBIHByb21pc2UgdGhhdCByZXNvbHZlcyB0byB0aGUgZGF0YWJhc2UgY29ubmVjdGlvbiBvYmplY3Qgb3IgbnVsbCBpZiBjb25uZWN0aW9uIGZhaWxzLlxuICovXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gaW5pdGlhbGl6ZURCKFxuICBkYk5hbWU6IHN0cmluZ1xuKTogUHJvbWlzZTxsYW5jZWRiLkNvbm5lY3Rpb24gfCBudWxsPiB7XG4gIGNvbnN0IGxhbmNlRGJVcmlGcm9tRW52ID0gcHJvY2Vzcy5lbnYuTEFOQ0VEQl9VUkk7XG4gIGxldCBkYlBhdGg6IHN0cmluZztcblxuICBpZiAobGFuY2VEYlVyaUZyb21FbnYpIHtcbiAgICAvLyBBc3N1bWluZyBMQU5DRURCX1VSSSBpcyBhIGRpcmVjdG9yeSBwYXRoLiBBcHBlbmQgZGJOYW1lLmxhbmNlIHRvIGl0LlxuICAgIC8vIEVuc3VyZSBpdCBlbmRzIHdpdGggYSBzbGFzaCBpZiBpdCdzIGEgZGlyZWN0b3J5LlxuICAgIGNvbnN0IGJhc2VVcmkgPSBsYW5jZURiVXJpRnJvbUVudi5lbmRzV2l0aCgnLycpXG4gICAgICA/IGxhbmNlRGJVcmlGcm9tRW52XG4gICAgICA6IGAke2xhbmNlRGJVcmlGcm9tRW52fS9gO1xuICAgIGRiUGF0aCA9IGAke2Jhc2VVcml9JHtkYk5hbWV9LmxhbmNlYDtcbiAgICBsb2coYFVzaW5nIExBTkNFREJfVVJJIGZyb20gZW52aXJvbm1lbnQ6ICR7YmFzZVVyaX1gKTtcbiAgfSBlbHNlIHtcbiAgICBkYlBhdGggPSBgJHtERUZBVUxUX0xUTV9EQl9QQVRIX1BSRUZJWH0ke2RiTmFtZX0ubGFuY2VgO1xuICAgIGxvZyhcbiAgICAgIGBMQU5DRURCX1VSSSBub3Qgc2V0IGluIGVudmlyb25tZW50LiBVc2luZyBkZWZhdWx0IHBhdGggcHJlZml4OiAke0RFRkFVTFRfTFRNX0RCX1BBVEhfUFJFRklYfWAsXG4gICAgICAnaW5mbydcbiAgICApO1xuICB9XG5cbiAgbG9nKGBJbml0aWFsaXppbmcgTGFuY2VEQiBhdCBwYXRoOiAke2RiUGF0aH1gKTtcbiAgdHJ5IHtcbiAgICAvLyBFbnN1cmUgdGhlIGRpcmVjdG9yeSBleGlzdHMgYmVmb3JlIGNvbm5lY3RpbmcgKGxhbmNlZGIuY29ubmVjdCBtaWdodCBub3QgY3JlYXRlIGl0KVxuICAgIC8vIFRoaXMgcGFydCBtaWdodCBuZWVkIGFkanVzdG1lbnQgYmFzZWQgb24gT1MgYW5kIHBlcm1pc3Npb25zLlxuICAgIC8vIEZvciBzaW1wbGljaXR5LCBhc3N1bWluZyB0aGUgZGlyZWN0b3J5IHN0cnVjdHVyZSBpcyBtYW5hZ2VkIGV4dGVybmFsbHkgb3IgbGFuY2VkYiBoYW5kbGVzIGl0LlxuICAgIC8vIEZvciBsb2NhbCBmaWxlLWJhc2VkIERCcywgbWFrZSBzdXJlIHRoZSBwYXRoIGlzIHdyaXRhYmxlLlxuICAgIGNvbnN0IGRiID0gYXdhaXQgbGFuY2VkYi5jb25uZWN0KGRiUGF0aCk7XG4gICAgbG9nKGBTdWNjZXNzZnVsbHkgY29ubmVjdGVkIHRvIExhbmNlREI6ICR7ZGJQYXRofWApO1xuICAgIGF3YWl0IGVuc3VyZVRhYmxlc0V4aXN0KGRiKTtcbiAgICByZXR1cm4gZGI7XG4gIH0gY2F0Y2ggKGVycm9yOiBhbnkpIHtcbiAgICBsb2coXG4gICAgICBgRXJyb3IgY29ubmVjdGluZyB0byBvciBjcmVhdGluZyBMYW5jZURCIGF0ICR7ZGJQYXRofTogJHtlcnJvci5tZXNzYWdlIHx8IGVycm9yfWAsXG4gICAgICAnZXJyb3InXG4gICAgKTtcbiAgICByZXR1cm4gbnVsbDtcbiAgfVxufVxuXG4vKipcbiAqIENyZWF0ZXMgdGhlIFVzZXJQcm9maWxlcyB0YWJsZSBpZiBpdCBkb2Vzbid0IGFscmVhZHkgZXhpc3QuXG4gKiBAcGFyYW0gZGIgVGhlIExhbmNlREIgY29ubmVjdGlvbiBvYmplY3QuXG4gKi9cbmV4cG9ydCBhc3luYyBmdW5jdGlvbiBjcmVhdGVVc2VyUHJvZmlsZXNUYWJsZShcbiAgZGI6IGxhbmNlZGIuQ29ubmVjdGlvblxuKTogUHJvbWlzZTx2b2lkPiB7XG4gIGlmICghZGIpIHtcbiAgICBsb2coXG4gICAgICAnRGF0YWJhc2UgY29ubmVjdGlvbiBub3QgcHJvdmlkZWQgdG8gY3JlYXRlVXNlclByb2ZpbGVzVGFibGUuJyxcbiAgICAgICdlcnJvcidcbiAgICApO1xuICAgIHJldHVybjtcbiAgfVxuICBjb25zdCB0YWJsZU5hbWUgPSAndXNlcl9wcm9maWxlcyc7XG4gIHRyeSB7XG4gICAgbG9nKGBBdHRlbXB0aW5nIHRvIGNyZWF0ZSB0YWJsZTogJHt0YWJsZU5hbWV9LmApO1xuICAgIC8vIFByb3ZpZGUgYW4gZW1wdHkgYXJyYXkgb2YgdGhlIGNvcnJlY3QgdHlwZSBmb3Igc2NoZW1hIGNyZWF0aW9uIGlmIG5vIGluaXRpYWwgZGF0YS5cbiAgICAvLyBMYW5jZURCIHVzZXMgQXJyb3cgc2NoZW1hLCB3aGljaCBjYW4gYmUgZXhwbGljaXRseSBkZWZpbmVkLlxuICAgIC8vIFRoZSBgbGFuY2VkYmAgcGFja2FnZSAodmVyc2lvbiAwLjguMCkgdXNlcyBgY3JlYXRlVGFibGUobmFtZSwgZGF0YSlgIG9yIGBjcmVhdGVUYWJsZShuYW1lLCBzY2hlbWEpYFxuICAgIC8vIGFuZCBgb3BlblRhYmxlKG5hbWUpYCBvciBgb3BlblRhYmxlKG5hbWUsIHNjaGVtYSlgLlxuICAgIC8vIGBjcmVhdGVUYWJsZWAgd2l0aCBtb2RlICdjcmVhdGUnIHNob3VsZCBhdHRlbXB0IHRvIGNyZWF0ZS5cbiAgICAvLyBJZiBpdCBmYWlscyBiZWNhdXNlIGl0IGV4aXN0cywgd2UgY2F0Y2ggdGhhdC5cbiAgICB0cnkge1xuICAgICAgYXdhaXQgZGIub3BlblRhYmxlKHRhYmxlTmFtZSk7XG4gICAgICBsb2coYFRhYmxlICcke3RhYmxlTmFtZX0nIGFscmVhZHkgZXhpc3RzLiBObyBhY3Rpb24gdGFrZW4uYCk7XG4gICAgfSBjYXRjaCAoZSkge1xuICAgICAgLy8gQXNzdW1pbmcgZXJyb3IgbWVhbnMgdGFibGUgZG9lcyBub3QgZXhpc3RcbiAgICAgIGxvZyhgVGFibGUgJyR7dGFibGVOYW1lfScgZG9lcyBub3QgZXhpc3QuIEF0dGVtcHRpbmcgdG8gY3JlYXRlLmApO1xuICAgICAgYXdhaXQgZGIuY3JlYXRlVGFibGUodGFibGVOYW1lLCB1c2VyUHJvZmlsZXNTY2hlbWEpOyAvLyBSZW1vdmVkIG1vZGUsIGFzIGl0IG1pZ2h0IG5vdCBiZSBzdXBwb3J0ZWQgb3IgbmVlZGVkIGlmIG9wZW5UYWJsZSBmYWlscyBmb3Igbm9uLWV4aXN0ZW5jZVxuICAgICAgbG9nKGBUYWJsZSAnJHt0YWJsZU5hbWV9JyBjcmVhdGVkIHN1Y2Nlc3NmdWxseS5gKTtcbiAgICB9XG4gIH0gY2F0Y2ggKGVycm9yOiBhbnkpIHtcbiAgICAvLyBUaGlzIG91dGVyIGNhdGNoIGlzIGZvciBlcnJvcnMgZHVyaW5nIHRoZSBjcmVhdGlvbiBhdHRlbXB0IGl0c2VsZiwgbm90IGZvciBcImFscmVhZHkgZXhpc3RzXCJcbiAgICBsb2coXG4gICAgICBgRXJyb3IgZHVyaW5nIHRhYmxlIGNyZWF0aW9uIHByb2Nlc3MgZm9yICcke3RhYmxlTmFtZX0nOiAke2Vycm9yLm1lc3NhZ2UgfHwgZXJyb3J9YCxcbiAgICAgICdlcnJvcidcbiAgICApO1xuICB9XG59XG5cbi8qKlxuICogQ3JlYXRlcyB0aGUgS25vd2xlZGdlQmFzZSB0YWJsZSBpZiBpdCBkb2Vzbid0IGFscmVhZHkgZXhpc3QuXG4gKiBAcGFyYW0gZGIgVGhlIExhbmNlREIgY29ubmVjdGlvbiBvYmplY3QuXG4gKi9cbmV4cG9ydCBhc3luYyBmdW5jdGlvbiBjcmVhdGVLbm93bGVkZ2VCYXNlVGFibGUoXG4gIGRiOiBsYW5jZWRiLkNvbm5lY3Rpb25cbik6IFByb21pc2U8dm9pZD4ge1xuICBpZiAoIWRiKSB7XG4gICAgbG9nKFxuICAgICAgJ0RhdGFiYXNlIGNvbm5lY3Rpb24gbm90IHByb3ZpZGVkIHRvIGNyZWF0ZUtub3dsZWRnZUJhc2VUYWJsZS4nLFxuICAgICAgJ2Vycm9yJ1xuICAgICk7XG4gICAgcmV0dXJuO1xuICB9XG4gIGNvbnN0IHRhYmxlTmFtZSA9ICdrbm93bGVkZ2VfYmFzZSc7XG4gIHRyeSB7XG4gICAgbG9nKGBBdHRlbXB0aW5nIHRvIGNyZWF0ZSB0YWJsZTogJHt0YWJsZU5hbWV9LmApO1xuICAgIHRyeSB7XG4gICAgICBhd2FpdCBkYi5vcGVuVGFibGUodGFibGVOYW1lKTtcbiAgICAgIGxvZyhgVGFibGUgJyR7dGFibGVOYW1lfScgYWxyZWFkeSBleGlzdHMuIE5vIGFjdGlvbiB0YWtlbi5gKTtcbiAgICB9IGNhdGNoIChlKSB7XG4gICAgICBsb2coYFRhYmxlICcke3RhYmxlTmFtZX0nIGRvZXMgbm90IGV4aXN0LiBBdHRlbXB0aW5nIHRvIGNyZWF0ZS5gKTtcbiAgICAgIGF3YWl0IGRiLmNyZWF0ZVRhYmxlKHRhYmxlTmFtZSwga25vd2xlZGdlQmFzZVNjaGVtYSk7XG4gICAgICBsb2coYFRhYmxlICcke3RhYmxlTmFtZX0nIGNyZWF0ZWQgc3VjY2Vzc2Z1bGx5LmApO1xuICAgIH1cbiAgfSBjYXRjaCAoZXJyb3I6IGFueSkge1xuICAgIGxvZyhcbiAgICAgIGBFcnJvciBkdXJpbmcgdGFibGUgY3JlYXRpb24gcHJvY2VzcyBmb3IgJyR7dGFibGVOYW1lfSc6ICR7ZXJyb3IubWVzc2FnZSB8fCBlcnJvcn1gLFxuICAgICAgJ2Vycm9yJ1xuICAgICk7XG4gIH1cbn1cblxuLyoqXG4gKiBDcmVhdGVzIHRoZSBSZXNlYXJjaEZpbmRpbmdzIHRhYmxlIGlmIGl0IGRvZXNuJ3QgYWxyZWFkeSBleGlzdC5cbiAqIEBwYXJhbSBkYiBUaGUgTGFuY2VEQiBjb25uZWN0aW9uIG9iamVjdC5cbiAqL1xuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIGNyZWF0ZVJlc2VhcmNoRmluZGluZ3NUYWJsZShcbiAgZGI6IGxhbmNlZGIuQ29ubmVjdGlvblxuKTogUHJvbWlzZTx2b2lkPiB7XG4gIGlmICghZGIpIHtcbiAgICBsb2coXG4gICAgICAnRGF0YWJhc2UgY29ubmVjdGlvbiBub3QgcHJvdmlkZWQgdG8gY3JlYXRlUmVzZWFyY2hGaW5kaW5nc1RhYmxlLicsXG4gICAgICAnZXJyb3InXG4gICAgKTtcbiAgICByZXR1cm47XG4gIH1cbiAgY29uc3QgdGFibGVOYW1lID0gJ3Jlc2VhcmNoX2ZpbmRpbmdzJztcbiAgdHJ5IHtcbiAgICBsb2coYEF0dGVtcHRpbmcgdG8gY3JlYXRlIHRhYmxlOiAke3RhYmxlTmFtZX0uYCk7XG4gICAgdHJ5IHtcbiAgICAgIGF3YWl0IGRiLm9wZW5UYWJsZSh0YWJsZU5hbWUpO1xuICAgICAgbG9nKGBUYWJsZSAnJHt0YWJsZU5hbWV9JyBhbHJlYWR5IGV4aXN0cy4gTm8gYWN0aW9uIHRha2VuLmApO1xuICAgIH0gY2F0Y2ggKGUpIHtcbiAgICAgIGxvZyhgVGFibGUgJyR7dGFibGVOYW1lfScgZG9lcyBub3QgZXhpc3QuIEF0dGVtcHRpbmcgdG8gY3JlYXRlLmApO1xuICAgICAgYXdhaXQgZGIuY3JlYXRlVGFibGUodGFibGVOYW1lLCByZXNlYXJjaEZpbmRpbmdzU2NoZW1hKTtcbiAgICAgIGxvZyhgVGFibGUgJyR7dGFibGVOYW1lfScgY3JlYXRlZCBzdWNjZXNzZnVsbHkuYCk7XG4gICAgfVxuICB9IGNhdGNoIChlcnJvcjogYW55KSB7XG4gICAgbG9nKFxuICAgICAgYEVycm9yIGR1cmluZyB0YWJsZSBjcmVhdGlvbiBwcm9jZXNzIGZvciAnJHt0YWJsZU5hbWV9JzogJHtlcnJvci5tZXNzYWdlIHx8IGVycm9yfWAsXG4gICAgICAnZXJyb3InXG4gICAgKTtcbiAgfVxufVxuXG4vKipcbiAqIEVuc3VyZXMgdGhhdCBhbGwgcHJlZGVmaW5lZCB0YWJsZXMgZXhpc3QgaW4gdGhlIGRhdGFiYXNlLlxuICogQ2FsbHMgdGhlIGNyZWF0aW9uIGZ1bmN0aW9uIGZvciBlYWNoIHRhYmxlLlxuICogQHBhcmFtIGRiIFRoZSBMYW5jZURCIGNvbm5lY3Rpb24gb2JqZWN0LlxuICovXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gZW5zdXJlVGFibGVzRXhpc3QoZGI6IGxhbmNlZGIuQ29ubmVjdGlvbik6IFByb21pc2U8dm9pZD4ge1xuICBpZiAoIWRiKSB7XG4gICAgbG9nKCdEYXRhYmFzZSBjb25uZWN0aW9uIG5vdCBwcm92aWRlZCB0byBlbnN1cmVUYWJsZXNFeGlzdC4nLCAnZXJyb3InKTtcbiAgICByZXR1cm47XG4gIH1cbiAgbG9nKCdFbnN1cmluZyBhbGwgTFRNIHRhYmxlcyBleGlzdC4uLicpO1xuICBhd2FpdCBjcmVhdGVVc2VyUHJvZmlsZXNUYWJsZShkYik7XG4gIGF3YWl0IGNyZWF0ZUtub3dsZWRnZUJhc2VUYWJsZShkYik7XG4gIGF3YWl0IGNyZWF0ZVJlc2VhcmNoRmluZGluZ3NUYWJsZShkYik7XG4gIGxvZygnRmluaXNoZWQgY2hlY2tpbmcvY3JlYXRpbmcgTFRNIHRhYmxlcy4nKTtcbn1cblxuLyoqXG4gKiBBZGRzIG9uZSBvciBtb3JlIHJlY29yZHMgdG8gdGhlIHNwZWNpZmllZCBMYW5jZURCIHRhYmxlLlxuICogQHBhcmFtIGRiIFRoZSBMYW5jZURCIGNvbm5lY3Rpb24gb2JqZWN0LlxuICogQHBhcmFtIHRhYmxlTmFtZSBUaGUgbmFtZSBvZiB0aGUgdGFibGUgdG8gYWRkIHJlY29yZHMgdG8uXG4gKiBAcGFyYW0gZGF0YSBBIHNpbmdsZSByZWNvcmQgb2JqZWN0IG9yIGFuIGFycmF5IG9mIHJlY29yZCBvYmplY3RzLlxuICovXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gYWRkUmVjb3JkKFxuICBkYjogbGFuY2VkYi5Db25uZWN0aW9uLFxuICB0YWJsZU5hbWU6IHN0cmluZyxcbiAgZGF0YTogUmVjb3JkPHN0cmluZywgYW55PiB8IFJlY29yZDxzdHJpbmcsIGFueT5bXVxuKTogUHJvbWlzZTx2b2lkPiB7XG4gIGlmICghZGIpIHtcbiAgICBsb2coJ0RhdGFiYXNlIGNvbm5lY3Rpb24gbm90IHByb3ZpZGVkIHRvIGFkZFJlY29yZC4nLCAnZXJyb3InKTtcbiAgICByZXR1cm4gUHJvbWlzZS5yZWplY3QobmV3IEVycm9yKCdEYXRhYmFzZSBjb25uZWN0aW9uIG5vdCBwcm92aWRlZC4nKSk7XG4gIH1cbiAgaWYgKCF0YWJsZU5hbWUpIHtcbiAgICBsb2coJ1RhYmxlIG5hbWUgbm90IHByb3ZpZGVkIHRvIGFkZFJlY29yZC4nLCAnZXJyb3InKTtcbiAgICByZXR1cm4gUHJvbWlzZS5yZWplY3QobmV3IEVycm9yKCdUYWJsZSBuYW1lIG5vdCBwcm92aWRlZC4nKSk7XG4gIH1cbiAgaWYgKCFkYXRhIHx8IChBcnJheS5pc0FycmF5KGRhdGEpICYmIGRhdGEubGVuZ3RoID09PSAwKSkge1xuICAgIGxvZygnTm8gZGF0YSBwcm92aWRlZCB0byBhZGRSZWNvcmQuJywgJ2Vycm9yJyk7XG4gICAgcmV0dXJuIFByb21pc2UucmVqZWN0KG5ldyBFcnJvcignTm8gZGF0YSBwcm92aWRlZC4nKSk7XG4gIH1cblxuICB0cnkge1xuICAgIGxvZyhgQXR0ZW1wdGluZyB0byBvcGVuIHRhYmxlICcke3RhYmxlTmFtZX0nIGZvciBhZGRpbmcgcmVjb3Jkcy5gKTtcbiAgICBjb25zdCB0YWJsZSA9IGF3YWl0IGRiLm9wZW5UYWJsZSh0YWJsZU5hbWUpO1xuICAgIGxvZyhcbiAgICAgIGBUYWJsZSAnJHt0YWJsZU5hbWV9JyBvcGVuZWQuIEFkZGluZyAke0FycmF5LmlzQXJyYXkoZGF0YSkgPyBkYXRhLmxlbmd0aCA6IDF9IHJlY29yZChzKS5gXG4gICAgKTtcbiAgICBhd2FpdCB0YWJsZS5hZGQoZGF0YSk7XG4gICAgbG9nKGBTdWNjZXNzZnVsbHkgYWRkZWQgcmVjb3JkKHMpIHRvIHRhYmxlICcke3RhYmxlTmFtZX0nLmApO1xuICB9IGNhdGNoIChlcnJvcjogYW55KSB7XG4gICAgbG9nKFxuICAgICAgYEVycm9yIGFkZGluZyByZWNvcmQocykgdG8gdGFibGUgJyR7dGFibGVOYW1lfSc6ICR7ZXJyb3IubWVzc2FnZX1gLFxuICAgICAgJ2Vycm9yJ1xuICAgICk7XG4gICAgaWYgKGVycm9yLm1lc3NhZ2UgJiYgZXJyb3IubWVzc2FnZS5pbmNsdWRlcygnZG9lcyBub3QgZXhpc3QnKSkge1xuICAgICAgLy8gT3Igc2ltaWxhciBlcnJvciBtZXNzYWdlXG4gICAgICBsb2coXG4gICAgICAgIGBUYWJsZSAnJHt0YWJsZU5hbWV9JyBub3QgZm91bmQuIFBsZWFzZSBlbnN1cmUgaXQgaXMgY3JlYXRlZCBiZWZvcmUgYWRkaW5nIHJlY29yZHMuYCxcbiAgICAgICAgJ2Vycm9yJ1xuICAgICAgKTtcbiAgICB9XG4gICAgLy8gY29uc29sZS5lcnJvcihcIkZ1bGwgZXJyb3Igb2JqZWN0OlwiLCBlcnJvcik7IC8vIEZvciBkZWJ1Z2dpbmdcbiAgICByZXR1cm4gUHJvbWlzZS5yZWplY3QoZXJyb3IpOyAvLyBSZS10aHJvdyB0aGUgZXJyb3Igb3IgYSBjdXN0b20gb25lXG4gIH1cbn1cblxuLyoqXG4gKiBTZWFyY2hlcyBhIExhbmNlREIgdGFibGUgdXNpbmcgYSBxdWVyeSB2ZWN0b3IuXG4gKiBAcGFyYW0gZGIgVGhlIExhbmNlREIgY29ubmVjdGlvbiBvYmplY3QuXG4gKiBAcGFyYW0gdGFibGVOYW1lIFRoZSBuYW1lIG9mIHRoZSB0YWJsZSB0byBzZWFyY2guXG4gKiBAcGFyYW0gcXVlcnlWZWN0b3IgVGhlIHZlY3RvciB0byBzZWFyY2ggd2l0aC5cbiAqIEBwYXJhbSBsaW1pdCBUaGUgbWF4aW11bSBudW1iZXIgb2YgcmVzdWx0cyB0byByZXR1cm4gKGRlZmF1bHQ6IDEwKS5cbiAqIEBwYXJhbSB2ZWN0b3JDb2x1bW5OYW1lIFRoZSBuYW1lIG9mIHRoZSB2ZWN0b3IgY29sdW1uIGluIHRoZSB0YWJsZSB0byBzZWFyY2ggYWdhaW5zdCAoZGVmYXVsdDogJ2VtYmVkZGluZycpLlxuICogQHBhcmFtIGZpbHRlciBBbiBvcHRpb25hbCBTUUwtbGlrZSBmaWx0ZXIgc3RyaW5nIHRvIGFwcGx5IGJlZm9yZSB0aGUgdmVjdG9yIHNlYXJjaC5cbiAqIEByZXR1cm5zIEEgcHJvbWlzZSB0aGF0IHJlc29sdmVzIHRvIGFuIGFycmF5IG9mIHNlYXJjaCByZXN1bHRzLlxuICovXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gc2VhcmNoVGFibGUoXG4gIGRiOiBsYW5jZWRiLkNvbm5lY3Rpb24sXG4gIHRhYmxlTmFtZTogc3RyaW5nLFxuICBxdWVyeVZlY3RvcjogbnVtYmVyW10sXG4gIGxpbWl0OiBudW1iZXIgPSAxMCxcbiAgdmVjdG9yQ29sdW1uTmFtZTogc3RyaW5nID0gJ2VtYmVkZGluZycsIC8vIERlZmF1bHQsIGJ1dCBzaG91bGQgYmUgc3BlY2lmaWVkIGJ5IGNhbGxlciBiYXNlZCBvbiB0YWJsZVxuICBmaWx0ZXI/OiBzdHJpbmdcbik6IFByb21pc2U8YW55W10+IHtcbiAgaWYgKCFkYikge1xuICAgIGxvZygnRGF0YWJhc2UgY29ubmVjdGlvbiBub3QgcHJvdmlkZWQgdG8gc2VhcmNoVGFibGUuJywgJ2Vycm9yJyk7XG4gICAgcmV0dXJuIFByb21pc2UucmVqZWN0KG5ldyBFcnJvcignRGF0YWJhc2UgY29ubmVjdGlvbiBub3QgcHJvdmlkZWQuJykpO1xuICB9XG4gIGlmICghdGFibGVOYW1lKSB7XG4gICAgbG9nKCdUYWJsZSBuYW1lIG5vdCBwcm92aWRlZCB0byBzZWFyY2hUYWJsZS4nLCAnZXJyb3InKTtcbiAgICByZXR1cm4gUHJvbWlzZS5yZWplY3QobmV3IEVycm9yKCdUYWJsZSBuYW1lIG5vdCBwcm92aWRlZC4nKSk7XG4gIH1cbiAgaWYgKCFxdWVyeVZlY3RvciB8fCBxdWVyeVZlY3Rvci5sZW5ndGggPT09IDApIHtcbiAgICBsb2coJ1F1ZXJ5IHZlY3RvciBub3QgcHJvdmlkZWQgb3IgZW1wdHkgdG8gc2VhcmNoVGFibGUuJywgJ2Vycm9yJyk7XG4gICAgcmV0dXJuIFByb21pc2UucmVqZWN0KG5ldyBFcnJvcignUXVlcnkgdmVjdG9yIG5vdCBwcm92aWRlZCBvciBlbXB0eS4nKSk7XG4gIH1cblxuICB0cnkge1xuICAgIGxvZyhgQXR0ZW1wdGluZyB0byBvcGVuIHRhYmxlICcke3RhYmxlTmFtZX0nIGZvciBzZWFyY2hpbmcuYCk7XG4gICAgY29uc3QgdGFibGUgPSBhd2FpdCBkYi5vcGVuVGFibGUodGFibGVOYW1lKTtcbiAgICBsb2coXG4gICAgICBgVGFibGUgJyR7dGFibGVOYW1lfScgb3BlbmVkLiBTZWFyY2hpbmcgd2l0aCB2ZWN0b3IgY29sdW1uICcke3ZlY3RvckNvbHVtbk5hbWV9JywgbGltaXQgJHtsaW1pdH0uIEZpbHRlcjogJyR7ZmlsdGVyIHx8ICdOb25lJ30nYFxuICAgICk7XG5cbiAgICBsZXQgc2VhcmNoUXVlcnkgPSB0YWJsZVxuICAgICAgLnNlYXJjaChxdWVyeVZlY3RvciwgdmVjdG9yQ29sdW1uTmFtZSkgLy8gUGFzcyB2ZWN0b3JDb2x1bW5OYW1lIHRvIHNlYXJjaCBpZiBBUEkgc3VwcG9ydHMgaXQsIGVsc2UgaXQgdXNlcyBkZWZhdWx0LlxuICAgICAgLnNlbGVjdChbJyonLCAnX2Rpc3RhbmNlJ10pIC8vIFNlbGVjdCBhbGwgY29sdW1ucyBhbmQgdGhlIGRpc3RhbmNlXG4gICAgICAubGltaXQobGltaXQpO1xuXG4gICAgaWYgKGZpbHRlcikge1xuICAgICAgc2VhcmNoUXVlcnkgPSBzZWFyY2hRdWVyeS53aGVyZShmaWx0ZXIpO1xuICAgICAgbG9nKGBBcHBsaWVkIGZpbHRlciB0byBzZWFyY2g6ICR7ZmlsdGVyfWApO1xuICAgIH1cblxuICAgIGNvbnN0IHJlc3VsdHMgPSBhd2FpdCBzZWFyY2hRdWVyeS5leGVjdXRlKCk7XG4gICAgbG9nKFxuICAgICAgYFNlYXJjaCBjb21wbGV0ZWQgb24gdGFibGUgJyR7dGFibGVOYW1lfScuIEZvdW5kICR7cmVzdWx0cy5sZW5ndGh9IHJlc3VsdHMuYFxuICAgICk7XG4gICAgcmV0dXJuIHJlc3VsdHM7XG4gIH0gY2F0Y2ggKGVycm9yOiBhbnkpIHtcbiAgICBsb2coYEVycm9yIHNlYXJjaGluZyB0YWJsZSAnJHt0YWJsZU5hbWV9JzogJHtlcnJvci5tZXNzYWdlfWAsICdlcnJvcicpO1xuICAgIGlmIChlcnJvci5tZXNzYWdlICYmIGVycm9yLm1lc3NhZ2UuaW5jbHVkZXMoJ2RvZXMgbm90IGV4aXN0JykpIHtcbiAgICAgIGxvZyhgVGFibGUgJyR7dGFibGVOYW1lfScgbm90IGZvdW5kLiBDYW5ub3QgcGVyZm9ybSBzZWFyY2guYCwgJ2Vycm9yJyk7XG4gICAgfSBlbHNlIGlmIChlcnJvci5tZXNzYWdlICYmIGVycm9yLm1lc3NhZ2UuaW5jbHVkZXMoJ3ZlY3Rvcl9jb2x1bW4nKSkge1xuICAgICAgLy8gRXhhbXBsZSBvZiBhIHNwZWNpZmljIGVycm9yXG4gICAgICBsb2coXG4gICAgICAgIGBQb3RlbnRpYWwgaXNzdWUgd2l0aCB2ZWN0b3IgY29sdW1uIG5hbWUgJyR7dmVjdG9yQ29sdW1uTmFtZX0nIG9yIGl0cyBjb25maWd1cmF0aW9uIGluIHRhYmxlICcke3RhYmxlTmFtZX0nLmAsXG4gICAgICAgICdlcnJvcidcbiAgICAgICk7XG4gICAgfVxuICAgIC8vIGNvbnNvbGUuZXJyb3IoXCJGdWxsIGVycm9yIG9iamVjdDpcIiwgZXJyb3IpOyAvLyBGb3IgZGVidWdnaW5nXG4gICAgcmV0dXJuIFByb21pc2UucmVqZWN0KGVycm9yKTsgLy8gUmUtdGhyb3cgdGhlIGVycm9yIG9yIGEgY3VzdG9tIG9uZVxuICB9XG59XG5cbi8vIEV4YW1wbGUgdXNhZ2UgKG9wdGlvbmFsLCBmb3IgdGVzdGluZyBvciBkaXJlY3QgaW52b2NhdGlvbilcbi8qXG5hc3luYyBmdW5jdGlvbiBzZXR1cERhdGFiYXNlKCkge1xuICBsb2coXCJTdGFydGluZyBkYXRhYmFzZSBzZXR1cCBleGFtcGxlLi4uXCIpO1xuICBjb25zdCBkYkluc3RhbmNlID0gYXdhaXQgaW5pdGlhbGl6ZURCKCdsdG1fYWdlbnRfZGF0YScpO1xuXG4gIGlmIChkYkluc3RhbmNlKSB7XG4gICAgbG9nKFwiRGF0YWJhc2UgaW5pdGlhbGl6ZWQgYW5kIHRhYmxlcyBlbnN1cmVkLlwiKTtcbiAgICAvLyBZb3UgY291bGQgYWRkIGV4YW1wbGUgZGF0YSBpbnNlcnRpb24gaGVyZSBmb3IgdGVzdGluZ1xuICAgIC8vIEZvciBleGFtcGxlOlxuICAgIC8vIGNvbnN0IHVzZXJQcm9maWxlcyA9IGF3YWl0IGRiSW5zdGFuY2Uub3BlblRhYmxlKCd1c2VyX3Byb2ZpbGVzJyk7XG4gICAgLy8gRXhhbXBsZTogQWRkIGEgcmVjb3JkXG4gICAgLy8gY29uc3QgdGVzdFJlY29yZCA9IHtcbiAgICAvLyAgIHVzZXJfaWQ6IGB1c2VyXyR7RGF0ZS5ub3coKX1gLFxuICAgIC8vICAgcHJlZmVyZW5jZXM6IEpTT04uc3RyaW5naWZ5KHsgdGhlbWU6ICdkYXJrJyB9KSxcbiAgICAvLyAgIGludGVyYWN0aW9uX3N1bW1hcnlfZW1iZWRkaW5nczogQXJyYXkoREVGQVVMVF9WRUNUT1JfRElNRU5TSU9OKS5maWxsKDAuNSksXG4gICAgLy8gICBpbnRlcmFjdGlvbl9oaXN0b3J5X2VtYmVkZGluZ3M6IEFycmF5KERFRkFVTFRfVkVDVE9SX0RJTUVOU0lPTikuZmlsbCgwLjMpLFxuICAgIC8vICAgaW50ZXJhY3Rpb25fc3VtbWFyaWVzOiBbXCJzdW1tYXJ5IDFcIiwgXCJzdW1tYXJ5IDJcIl0sXG4gICAgLy8gICBjcmVhdGVkX2F0OiBuZXcgRGF0ZSgpLFxuICAgIC8vICAgdXBkYXRlZF9hdDogbmV3IERhdGUoKVxuICAgIC8vIH07XG4gICAgLy8gYXdhaXQgYWRkUmVjb3JkKGRiSW5zdGFuY2UsICd1c2VyX3Byb2ZpbGVzJywgdGVzdFJlY29yZCk7XG4gICAgLy8gbG9nKCdUZXN0IHJlY29yZCBhZGRlZCB0byB1c2VyX3Byb2ZpbGVzLicpO1xuXG4gICAgLy8gRXhhbXBsZTogU2VhcmNoIHRoZSB0YWJsZVxuICAgIC8vIGNvbnN0X3F1ZXJ5X3ZlY3RvciA9IEFycmF5KERFRkFVTFRfVkVDVE9SX0RJTUVOU0lPTikuZmlsbCgwLjQ1KTtcbiAgICAvLyBjb25zdCBzZWFyY2hSZXN1bHRzID0gYXdhaXQgc2VhcmNoVGFibGUoZGJJbnN0YW5jZSwgJ3VzZXJfcHJvZmlsZXMnLCBfcXVlcnlfdmVjdG9yLCA1LCAnaW50ZXJhY3Rpb25fc3VtbWFyeV9lbWJlZGRpbmdzJyk7XG4gICAgLy8gbG9nKCdTZWFyY2ggcmVzdWx0cyBmcm9tIHVzZXJfcHJvZmlsZXM6Jywgc2VhcmNoUmVzdWx0cyk7XG5cbiAgfSBlbHNlIHtcbiAgICBsb2coXCJEYXRhYmFzZSBpbml0aWFsaXphdGlvbiBmYWlsZWQuXCIsICdlcnJvcicpO1xuICB9XG59XG5cbi8vIFRvIHJ1biB0aGlzIGV4YW1wbGU6XG4vLyAxLiBFbnN1cmUgeW91IGhhdmUgYSBjb21wYXRpYmxlIGVudmlyb25tZW50IGZvciBsYW5jZWRiIChlLmcuLCBOb2RlLmpzIHdpdGggcmVxdWlyZWQgYnVpbGQgdG9vbHMgaWYgbGFuY2VkYiBoYXMgbmF0aXZlIGNvbXBvbmVudHMpXG4vLyAyLiBSdW4gYG5wbSBpbnN0YWxsYCBvciBgcG5wbSBpbnN0YWxsYCB0byBnZXQgYHZlY3RvcmRiLWxhbmNlYFxuLy8gMy4gRXhlY3V0ZSB0aGlzIGZpbGU6IGBub2RlIC0tbG9hZGVyIHRzLW5vZGUvZXNtIC4vYXRvbWljLWRvY2tlci9wcm9qZWN0L2Z1bmN0aW9ucy9sYW5jZURCTWFuYWdlci50c2AgKGlmIHlvdSBoYXZlIHRzLW5vZGUpXG4vLyAgICBvciBjb21waWxlIHRvIEpTIGZpcnN0IGFuZCB0aGVuIHJ1biB3aXRoIG5vZGUuXG5cbi8vIFVuY29tbWVudCB0byBydW4gc2V0dXAgd2hlbiB0aGlzIGZpbGUgaXMgZXhlY3V0ZWQgZGlyZWN0bHlcbi8vIHNldHVwRGF0YWJhc2UoKS50aGVuKCgpID0+IGxvZyhcIkV4YW1wbGUgc2V0dXAgZmluaXNoZWQuXCIpKS5jYXRjaChlID0+IGxvZyhgRXhhbXBsZSBzZXR1cCBmYWlsZWQ6ICR7ZX1gLCAnZXJyb3InKSk7XG4qL1xuXG4vKipcbiAqIFVwZGF0ZXMgb25lIG9yIG1vcmUgcmVjb3JkcyBpbiB0aGUgc3BlY2lmaWVkIExhbmNlREIgdGFibGUgdGhhdCBtYXRjaCBhIGZpbHRlci5cbiAqIE5vdGU6IExhbmNlREIncyBOb2RlLmpzIEFQSSBmb3IgdXBkYXRlcyBtaWdodCBiZSBldm9sdmluZy5cbiAqIFRoaXMgZnVuY3Rpb24gYXNzdW1lcyBhIGNvbmNlcHR1YWwgYHRhYmxlLnVwZGF0ZSh2YWx1ZXMsIGZpbHRlcilgIG1ldGhvZCBvciBzaW1pbGFyLlxuICogQXMgb2YgYHZlY3RvcmRiLWxhbmNlQDAuMi4yYCwgZGlyZWN0IHVwZGF0ZXMgYmFzZWQgb24gYSBmaWx0ZXIgYXJlIG5vdCBleHBsaWNpdGx5IGRvY3VtZW50ZWRcbiAqIGluIHRoZSBzYW1lIHdheSBhcyBgZGVsZXRlKGZpbHRlcilgLiBUaGlzIG1pZ2h0IHJlcXVpcmUgYSBkZWxldGUtdGhlbi1hZGQgcGF0dGVybiBpZiBkaXJlY3RcbiAqIGNvbmRpdGlvbmFsIHVwZGF0ZSBpc24ndCBhdmFpbGFibGUgb3IgZWZmaWNpZW50LlxuICogRm9yIHNpbXBsaWNpdHksIHRoaXMgZXhhbXBsZSB3aWxsIHVzZSBgdGFibGUubWVyZ2VJbnNlcnRgIGlmIGFwcGxpY2FibGUsIG9yIHNpbXVsYXRlIGJ5IGRlbGV0ZSthZGQuXG4gKiBBIG1vcmUgcm9idXN0IHNvbHV0aW9uIHdvdWxkIGRlcGVuZCBvbiB0aGUgZXhhY3QgY2FwYWJpbGl0aWVzIG9mIHRoZSBMYW5jZURCIHZlcnNpb24uXG4gKlxuICogVGhpcyBmdW5jdGlvbiB3aWxsIHVwZGF0ZSB0aGUgYHVwZGF0ZWRfYXRgIHRpbWVzdGFtcCBhdXRvbWF0aWNhbGx5LlxuICpcbiAqICoqSW1wb3J0YW50OioqIFRoaXMgaW1wbGVtZW50YXRpb24gdXNlcyBhIGRlbGV0ZS10aGVuLWFkZCBwYXR0ZXJuIGFzIGEgd29ya2Fyb3VuZCBmb3JcbiAqIHBvdGVudGlhbCBsaW1pdGF0aW9ucyBpbiBkaXJlY3QgY29uZGl0aW9uYWwgdXBkYXRlcyBpbiBzb21lIExhbmNlREIgTm9kZS5qcyB2ZXJzaW9ucy5cbiAqIFRoaXMgbWVhbnMgdGhlIG9wZXJhdGlvbiBpcyAqKm5vdCBhdG9taWMqKiBhbmQgY291bGQgbGVhZCB0byBkYXRhIGxvc3MgaWYgYW4gZXJyb3JcbiAqIG9jY3VycyBhZnRlciBkZWxldGlvbiBidXQgYmVmb3JlIHJlLWluc2VydGlvbi4gVXNlIHdpdGggY2F1dGlvbiBvciBlbnN1cmUgdGhlIExhbmNlREJcbiAqIHZlcnNpb24gaW4gdXNlIHN1cHBvcnRzIGEgbW9yZSBkaXJlY3QgYW5kIGF0b21pYyB1cGRhdGUgbWV0aG9kLlxuICpcbiAqIEBwYXJhbSBkYiBUaGUgTGFuY2VEQiBjb25uZWN0aW9uIG9iamVjdC5cbiAqIEBwYXJhbSB0YWJsZU5hbWUgVGhlIG5hbWUgb2YgdGhlIHRhYmxlIHRvIHVwZGF0ZSByZWNvcmRzIGluLlxuICogQHBhcmFtIHJlY29yZElkRmllbGQgVGhlIG5hbWUgb2YgdGhlIGZpZWxkIHRvIGlkZW50aWZ5IHRoZSByZWNvcmQocykgKGUuZy4sICdmYWN0X2lkJywgJ3VzZXJfaWQnKS5cbiAqIEBwYXJhbSByZWNvcmRJZFZhbHVlIFRoZSB2YWx1ZSBvZiB0aGUgaWRlbnRpZmllciBmb3IgdGhlIHJlY29yZChzKSB0byB1cGRhdGUuXG4gKiBAcGFyYW0gdXBkYXRlZEZpZWxkcyBBbiBvYmplY3QgY29udGFpbmluZyB0aGUgZmllbGRzIHRvIHVwZGF0ZSBhbmQgdGhlaXIgbmV3IHZhbHVlcy5cbiAqICAgICAgICAgICAgICAgICAgICAgIERvIG5vdCBpbmNsdWRlIHRoZSByZWNvcmRJZEZpZWxkIGluIHVwZGF0ZWRGaWVsZHMuXG4gKi9cbmV4cG9ydCBhc3luYyBmdW5jdGlvbiB1cGRhdGVSZWNvcmQoXG4gIGRiOiBsYW5jZWRiLkNvbm5lY3Rpb24sXG4gIHRhYmxlTmFtZTogc3RyaW5nLFxuICByZWNvcmRJZEZpZWxkOiBzdHJpbmcsXG4gIHJlY29yZElkVmFsdWU6IHN0cmluZyxcbiAgdXBkYXRlZEZpZWxkczogUmVjb3JkPHN0cmluZywgYW55PlxuKTogUHJvbWlzZTx2b2lkPiB7XG4gIGlmICghZGIpIHtcbiAgICBsb2coJ0RhdGFiYXNlIGNvbm5lY3Rpb24gbm90IHByb3ZpZGVkIHRvIHVwZGF0ZVJlY29yZC4nLCAnZXJyb3InKTtcbiAgICByZXR1cm4gUHJvbWlzZS5yZWplY3QobmV3IEVycm9yKCdEYXRhYmFzZSBjb25uZWN0aW9uIG5vdCBwcm92aWRlZC4nKSk7XG4gIH1cbiAgaWYgKCF0YWJsZU5hbWUgfHwgIXJlY29yZElkRmllbGQgfHwgIXJlY29yZElkVmFsdWUpIHtcbiAgICBsb2coXG4gICAgICAnVGFibGUgbmFtZSwgcmVjb3JkSWRGaWVsZCwgb3IgcmVjb3JkSWRWYWx1ZSBub3QgcHJvdmlkZWQgdG8gdXBkYXRlUmVjb3JkLicsXG4gICAgICAnZXJyb3InXG4gICAgKTtcbiAgICByZXR1cm4gUHJvbWlzZS5yZWplY3QoXG4gICAgICBuZXcgRXJyb3IoJ1RhYmxlIG5hbWUsIHJlY29yZElkRmllbGQsIG9yIHJlY29yZElkVmFsdWUgbm90IHByb3ZpZGVkLicpXG4gICAgKTtcbiAgfVxuICBpZiAoIXVwZGF0ZWRGaWVsZHMgfHwgT2JqZWN0LmtleXModXBkYXRlZEZpZWxkcykubGVuZ3RoID09PSAwKSB7XG4gICAgbG9nKCdObyBmaWVsZHMgdG8gdXBkYXRlIHByb3ZpZGVkIHRvIHVwZGF0ZVJlY29yZC4nLCAnZXJyb3InKTtcbiAgICByZXR1cm4gUHJvbWlzZS5yZWplY3QobmV3IEVycm9yKCdObyBmaWVsZHMgdG8gdXBkYXRlIHByb3ZpZGVkLicpKTtcbiAgfVxuICBpZiAodXBkYXRlZEZpZWxkcy5oYXNPd25Qcm9wZXJ0eShyZWNvcmRJZEZpZWxkKSkge1xuICAgIGxvZyhcbiAgICAgIGBDYW5ub3QgdXBkYXRlIHRoZSByZWNvcmQgSUQgZmllbGQgKCcke3JlY29yZElkRmllbGR9JykgaXRzZWxmLmAsXG4gICAgICAnZXJyb3InXG4gICAgKTtcbiAgICByZXR1cm4gUHJvbWlzZS5yZWplY3QoXG4gICAgICBuZXcgRXJyb3IoXG4gICAgICAgIGBDYW5ub3QgdXBkYXRlIHRoZSByZWNvcmQgSUQgZmllbGQgKCcke3JlY29yZElkRmllbGR9JykgaXRzZWxmLmBcbiAgICAgIClcbiAgICApO1xuICB9XG5cbiAgY29uc3QgZmlsdGVyID0gYCR7cmVjb3JkSWRGaWVsZH0gPSAnJHtyZWNvcmRJZFZhbHVlfSdgO1xuICBsb2coXG4gICAgYEF0dGVtcHRpbmcgdG8gdXBkYXRlIHJlY29yZChzKSBpbiB0YWJsZSAnJHt0YWJsZU5hbWV9JyB3aGVyZSAke2ZpbHRlcn0uYFxuICApO1xuXG4gIHRyeSB7XG4gICAgY29uc3QgdGFibGUgPSBhd2FpdCBkYi5vcGVuVGFibGUodGFibGVOYW1lKTtcblxuICAgIC8vIEFkZC91cGRhdGUgdGhlICd1cGRhdGVkX2F0JyB0aW1lc3RhbXBcbiAgICBjb25zdCBmaW5hbFVwZGF0ZWRGaWVsZHMgPSB7XG4gICAgICAuLi51cGRhdGVkRmllbGRzLFxuICAgICAgdXBkYXRlZF9hdDogbmV3IERhdGUoKS50b0lTT1N0cmluZygpLFxuICAgIH07XG5cbiAgICAvLyBMYW5jZURCJ3MgYHVwZGF0ZWAgbWV0aG9kIChhZGRlZCBpbiBsYXRlciB2ZXJzaW9ucywgZS5nLiwgMC40LnggZm9yIFB5dGhvbiwgY2hlY2sgTm9kZS5qcyBzcGVjaWZpY3MpXG4gICAgLy8gSWYgdGFibGUudXBkYXRlKGZpbmFsVXBkYXRlZEZpZWxkcywgZmlsdGVyKSBleGlzdHMgYW5kIHdvcmtzOlxuICAgIC8vIGF3YWl0IHRhYmxlLnVwZGF0ZShmaW5hbFVwZGF0ZWRGaWVsZHMsIGZpbHRlcik7XG4gICAgLy8gbG9nKGBTdWNjZXNzZnVsbHkgaW5pdGlhdGVkIHVwZGF0ZSBmb3IgcmVjb3JkKHMpIGluIHRhYmxlICcke3RhYmxlTmFtZX0nIHdoZXJlICR7ZmlsdGVyfS5gKTtcblxuICAgIC8vIFdvcmthcm91bmQgaWYgZGlyZWN0IHVwZGF0ZSBpcyBub3QgYXZhaWxhYmxlL3N1aXRhYmxlOiBEZWxldGUgYW5kIEFkZC5cbiAgICAvLyBUaGlzIGlzIGxlc3MgZWZmaWNpZW50IGFuZCBub3QgYXRvbWljLlxuICAgIC8vIDEuIEZldGNoIHRoZSByZWNvcmRzIHRvIGJlIHVwZGF0ZWQuXG4gICAgY29uc3QgcmVjb3Jkc1RvVXBkYXRlID0gYXdhaXQgdGFibGUuc2VhcmNoKCkud2hlcmUoZmlsdGVyKS5leGVjdXRlKCk7XG4gICAgaWYgKHJlY29yZHNUb1VwZGF0ZS5sZW5ndGggPT09IDApIHtcbiAgICAgIGxvZyhcbiAgICAgICAgYE5vIHJlY29yZHMgZm91bmQgaW4gdGFibGUgJyR7dGFibGVOYW1lfScgbWF0Y2hpbmcgZmlsdGVyICcke2ZpbHRlcn0nLiBOb3RoaW5nIHRvIHVwZGF0ZS5gXG4gICAgICApO1xuICAgICAgcmV0dXJuO1xuICAgIH1cbiAgICBsb2coXG4gICAgICBgRm91bmQgJHtyZWNvcmRzVG9VcGRhdGUubGVuZ3RofSByZWNvcmQocykgdG8gdXBkYXRlLiBQZXJmb3JtaW5nIGRlbGV0ZSBhbmQgYWRkLmBcbiAgICApO1xuXG4gICAgLy8gMi4gRGVsZXRlIHRoZSBvbGQgcmVjb3Jkcy5cbiAgICBhd2FpdCB0YWJsZS5kZWxldGUoZmlsdGVyKTtcbiAgICBsb2coYERlbGV0ZWQgJHtyZWNvcmRzVG9VcGRhdGUubGVuZ3RofSBvbGQgcmVjb3JkKHMpLmApO1xuXG4gICAgLy8gMy4gUHJlcGFyZSBuZXcgcmVjb3JkcyB3aXRoIHVwZGF0ZWQgZmllbGRzLlxuICAgIGNvbnN0IG5ld1JlY29yZHMgPSByZWNvcmRzVG9VcGRhdGUubWFwKChyZWNvcmQpID0+IHtcbiAgICAgIGNvbnN0IHsgX2Rpc3RhbmNlLCAuLi5vbGRSZWNvcmRGaWVsZHMgfSA9IHJlY29yZDsgLy8gUmVtb3ZlIF9kaXN0YW5jZSBpZiBwcmVzZW50XG4gICAgICByZXR1cm4geyAuLi5vbGRSZWNvcmRGaWVsZHMsIC4uLmZpbmFsVXBkYXRlZEZpZWxkcyB9O1xuICAgIH0pO1xuXG4gICAgLy8gNC4gQWRkIHRoZSB1cGRhdGVkIHJlY29yZHMuXG4gICAgYXdhaXQgdGFibGUuYWRkKG5ld1JlY29yZHMpO1xuICAgIGxvZyhcbiAgICAgIGBBZGRlZCAke25ld1JlY29yZHMubGVuZ3RofSB1cGRhdGVkIHJlY29yZChzKSB0byB0YWJsZSAnJHt0YWJsZU5hbWV9Jy5gXG4gICAgKTtcbiAgfSBjYXRjaCAoZXJyb3I6IGFueSkge1xuICAgIGxvZyhcbiAgICAgIGBFcnJvciB1cGRhdGluZyByZWNvcmQocykgaW4gdGFibGUgJyR7dGFibGVOYW1lfSc6ICR7ZXJyb3IubWVzc2FnZX1gLFxuICAgICAgJ2Vycm9yJ1xuICAgICk7XG4gICAgLy8gY29uc29sZS5lcnJvcihcIkZ1bGwgZXJyb3Igb2JqZWN0OlwiLCBlcnJvcik7IC8vIEZvciBkZWJ1Z2dpbmdcbiAgICByZXR1cm4gUHJvbWlzZS5yZWplY3QoZXJyb3IpO1xuICB9XG59XG5cbi8qKlxuICogRGVsZXRlcyBvbmUgb3IgbW9yZSByZWNvcmRzIGZyb20gdGhlIHNwZWNpZmllZCBMYW5jZURCIHRhYmxlIGJhc2VkIG9uIGEgZmlsdGVyLlxuICogQHBhcmFtIGRiIFRoZSBMYW5jZURCIGNvbm5lY3Rpb24gb2JqZWN0LlxuICogQHBhcmFtIHRhYmxlTmFtZSBUaGUgbmFtZSBvZiB0aGUgdGFibGUgdG8gZGVsZXRlIHJlY29yZHMgZnJvbS5cbiAqIEBwYXJhbSByZWNvcmRJZEZpZWxkIFRoZSBuYW1lIG9mIHRoZSBmaWVsZCB0byBpZGVudGlmeSB0aGUgcmVjb3JkKHMpIChlLmcuLCAnZmFjdF9pZCcsICd1c2VyX2lkJykuXG4gKiBAcGFyYW0gcmVjb3JkSWRWYWx1ZSBUaGUgdmFsdWUgb2YgdGhlIGlkZW50aWZpZXIgZm9yIHRoZSByZWNvcmQocykgdG8gZGVsZXRlLlxuICovXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gZGVsZXRlUmVjb3JkKFxuICBkYjogbGFuY2VkYi5Db25uZWN0aW9uLFxuICB0YWJsZU5hbWU6IHN0cmluZyxcbiAgcmVjb3JkSWRGaWVsZDogc3RyaW5nLFxuICByZWNvcmRJZFZhbHVlOiBzdHJpbmdcbik6IFByb21pc2U8dm9pZD4ge1xuICBpZiAoIWRiKSB7XG4gICAgbG9nKCdEYXRhYmFzZSBjb25uZWN0aW9uIG5vdCBwcm92aWRlZCB0byBkZWxldGVSZWNvcmQuJywgJ2Vycm9yJyk7XG4gICAgcmV0dXJuIFByb21pc2UucmVqZWN0KG5ldyBFcnJvcignRGF0YWJhc2UgY29ubmVjdGlvbiBub3QgcHJvdmlkZWQuJykpO1xuICB9XG4gIGlmICghdGFibGVOYW1lIHx8ICFyZWNvcmRJZEZpZWxkIHx8ICFyZWNvcmRJZFZhbHVlKSB7XG4gICAgbG9nKFxuICAgICAgJ1RhYmxlIG5hbWUsIHJlY29yZElkRmllbGQsIG9yIHJlY29yZElkVmFsdWUgbm90IHByb3ZpZGVkIHRvIGRlbGV0ZVJlY29yZC4nLFxuICAgICAgJ2Vycm9yJ1xuICAgICk7XG4gICAgcmV0dXJuIFByb21pc2UucmVqZWN0KFxuICAgICAgbmV3IEVycm9yKCdUYWJsZSBuYW1lLCByZWNvcmRJZEZpZWxkLCBvciByZWNvcmRJZFZhbHVlIG5vdCBwcm92aWRlZC4nKVxuICAgICk7XG4gIH1cblxuICBjb25zdCBmaWx0ZXIgPSBgJHtyZWNvcmRJZEZpZWxkfSA9ICcke3JlY29yZElkVmFsdWV9J2A7XG4gIGxvZyhcbiAgICBgQXR0ZW1wdGluZyB0byBkZWxldGUgcmVjb3JkKHMpIGZyb20gdGFibGUgJyR7dGFibGVOYW1lfScgd2hlcmUgJHtmaWx0ZXJ9LmBcbiAgKTtcblxuICB0cnkge1xuICAgIGNvbnN0IHRhYmxlID0gYXdhaXQgZGIub3BlblRhYmxlKHRhYmxlTmFtZSk7XG4gICAgYXdhaXQgdGFibGUuZGVsZXRlKGZpbHRlcik7XG4gICAgbG9nKFxuICAgICAgYFN1Y2Nlc3NmdWxseSBkZWxldGVkIHJlY29yZChzKSAoaWYgdGhleSBleGlzdGVkKSBmcm9tIHRhYmxlICcke3RhYmxlTmFtZX0nIHdoZXJlICR7ZmlsdGVyfS5gXG4gICAgKTtcbiAgfSBjYXRjaCAoZXJyb3I6IGFueSkge1xuICAgIGxvZyhcbiAgICAgIGBFcnJvciBkZWxldGluZyByZWNvcmQocykgZnJvbSB0YWJsZSAnJHt0YWJsZU5hbWV9JzogJHtlcnJvci5tZXNzYWdlfWAsXG4gICAgICAnZXJyb3InXG4gICAgKTtcbiAgICAvLyBjb25zb2xlLmVycm9yKFwiRnVsbCBlcnJvciBvYmplY3Q6XCIsIGVycm9yKTsgLy8gRm9yIGRlYnVnZ2luZ1xuICAgIHJldHVybiBQcm9taXNlLnJlamVjdChlcnJvcik7XG4gIH1cbn1cblxubG9nKCdMYW5jZURCTWFuYWdlciBtb2R1bGUgbG9hZGVkIHdpdGggdGFibGUgY3JlYXRpb24gYW5kIENSVUQgbG9naWMuJyk7XG4iXX0=