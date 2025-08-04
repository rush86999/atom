// Manages LanceDB connections and table initializations for LTM
import * as lancedb from '@lancedb/lancedb';
// Schema, Field, etc. should be directly available from '@lancedb/lancedb/arrow' or similar if exposed,
// or directly from the main package if re-exported.
// For now, assuming they are directly available or re-exported by '@lancedb/lancedb'
// If not, this will need adjustment based on the actual package structure of '@lancedb/lancedb'.
import {
  Schema,
  Field,
  Float32,
  Utf8,
  Timestamp,
  List,
  FixedSizeList,
} from '@lancedb/lancedb/arrow';

const DEFAULT_LTM_DB_PATH_PREFIX = './lance_db/'; // Default base path if LANCEDB_URI is not set
const DEFAULT_VECTOR_DIMENSION = 1536;

function log(message: string, level: 'info' | 'error' = 'info') {
  const prefix = `[LanceDBManager] ${new Date().toISOString()}`;
  if (level === 'error') {
    console.error(`${prefix} [ERROR]: ${message}`);
  } else {
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
  new Field(
    'interaction_summary_embeddings',
    new FixedSizeList(
      DEFAULT_VECTOR_DIMENSION,
      new Field('item', new Float32(), true)
    ),
    true
  ), // Embedding of a holistic summary of all user interactions
  // interaction_history_embeddings field removed as individual interaction history is stored in knowledge_base table
  new Field(
    'interaction_summaries',
    new List(new Field('item', new Utf8(), true)),
    true
  ), // Curated list of key textual interaction summaries
  new Field('created_at', new Timestamp('ms'), true),
  new Field('updated_at', new Timestamp('ms'), true),
]);

// KnowledgeBase Schema
const knowledgeBaseSchema = new Schema([
  new Field('fact_id', new Utf8(), false), // Not nullable (Primary Key)
  new Field('text_content', new Utf8(), true),
  new Field(
    'text_content_embedding',
    new FixedSizeList(
      DEFAULT_VECTOR_DIMENSION,
      new Field('item', new Float32(), true)
    ),
    true
  ),
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
  new Field(
    'query_embedding',
    new FixedSizeList(
      DEFAULT_VECTOR_DIMENSION,
      new Field('item', new Float32(), true)
    ),
    true
  ),
  new Field('summary', new Utf8(), true),
  new Field(
    'summary_embedding',
    new FixedSizeList(
      DEFAULT_VECTOR_DIMENSION,
      new Field('item', new Float32(), true)
    ),
    true
  ),
  new Field('details_text', new Utf8(), true), // Detailed findings
  new Field(
    'source_references',
    new List(new Field('item', new Utf8(), true)),
    true
  ), // List of URLs or identifiers
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
export async function initializeDB(
  dbName: string
): Promise<lancedb.Connection | null> {
  const lanceDbUriFromEnv = process.env.LANCEDB_URI;
  let dbPath: string;

  if (lanceDbUriFromEnv) {
    // Assuming LANCEDB_URI is a directory path. Append dbName.lance to it.
    // Ensure it ends with a slash if it's a directory.
    const baseUri = lanceDbUriFromEnv.endsWith('/')
      ? lanceDbUriFromEnv
      : `${lanceDbUriFromEnv}/`;
    dbPath = `${baseUri}${dbName}.lance`;
    log(`Using LANCEDB_URI from environment: ${baseUri}`);
  } else {
    dbPath = `${DEFAULT_LTM_DB_PATH_PREFIX}${dbName}.lance`;
    log(
      `LANCEDB_URI not set in environment. Using default path prefix: ${DEFAULT_LTM_DB_PATH_PREFIX}`,
      'info'
    );
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
  } catch (error: any) {
    log(
      `Error connecting to or creating LanceDB at ${dbPath}: ${error.message || error}`,
      'error'
    );
    return null;
  }
}

/**
 * Creates the UserProfiles table if it doesn't already exist.
 * @param db The LanceDB connection object.
 */
export async function createUserProfilesTable(
  db: lancedb.Connection
): Promise<void> {
  if (!db) {
    log(
      'Database connection not provided to createUserProfilesTable.',
      'error'
    );
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
    } catch (e) {
      // Assuming error means table does not exist
      log(`Table '${tableName}' does not exist. Attempting to create.`);
      await db.createTable(tableName, userProfilesSchema); // Removed mode, as it might not be supported or needed if openTable fails for non-existence
      log(`Table '${tableName}' created successfully.`);
    }
  } catch (error: any) {
    // This outer catch is for errors during the creation attempt itself, not for "already exists"
    log(
      `Error during table creation process for '${tableName}': ${error.message || error}`,
      'error'
    );
  }
}

/**
 * Creates the KnowledgeBase table if it doesn't already exist.
 * @param db The LanceDB connection object.
 */
export async function createKnowledgeBaseTable(
  db: lancedb.Connection
): Promise<void> {
  if (!db) {
    log(
      'Database connection not provided to createKnowledgeBaseTable.',
      'error'
    );
    return;
  }
  const tableName = 'knowledge_base';
  try {
    log(`Attempting to create table: ${tableName}.`);
    try {
      await db.openTable(tableName);
      log(`Table '${tableName}' already exists. No action taken.`);
    } catch (e) {
      log(`Table '${tableName}' does not exist. Attempting to create.`);
      await db.createTable(tableName, knowledgeBaseSchema);
      log(`Table '${tableName}' created successfully.`);
    }
  } catch (error: any) {
    log(
      `Error during table creation process for '${tableName}': ${error.message || error}`,
      'error'
    );
  }
}

/**
 * Creates the ResearchFindings table if it doesn't already exist.
 * @param db The LanceDB connection object.
 */
export async function createResearchFindingsTable(
  db: lancedb.Connection
): Promise<void> {
  if (!db) {
    log(
      'Database connection not provided to createResearchFindingsTable.',
      'error'
    );
    return;
  }
  const tableName = 'research_findings';
  try {
    log(`Attempting to create table: ${tableName}.`);
    try {
      await db.openTable(tableName);
      log(`Table '${tableName}' already exists. No action taken.`);
    } catch (e) {
      log(`Table '${tableName}' does not exist. Attempting to create.`);
      await db.createTable(tableName, researchFindingsSchema);
      log(`Table '${tableName}' created successfully.`);
    }
  } catch (error: any) {
    log(
      `Error during table creation process for '${tableName}': ${error.message || error}`,
      'error'
    );
  }
}

/**
 * Ensures that all predefined tables exist in the database.
 * Calls the creation function for each table.
 * @param db The LanceDB connection object.
 */
export async function ensureTablesExist(db: lancedb.Connection): Promise<void> {
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
export async function addRecord(
  db: lancedb.Connection,
  tableName: string,
  data: Record<string, any> | Record<string, any>[]
): Promise<void> {
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
    log(
      `Table '${tableName}' opened. Adding ${Array.isArray(data) ? data.length : 1} record(s).`
    );
    await table.add(data);
    log(`Successfully added record(s) to table '${tableName}'.`);
  } catch (error: any) {
    log(
      `Error adding record(s) to table '${tableName}': ${error.message}`,
      'error'
    );
    if (error.message && error.message.includes('does not exist')) {
      // Or similar error message
      log(
        `Table '${tableName}' not found. Please ensure it is created before adding records.`,
        'error'
      );
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
export async function searchTable(
  db: lancedb.Connection,
  tableName: string,
  queryVector: number[],
  limit: number = 10,
  vectorColumnName: string = 'embedding', // Default, but should be specified by caller based on table
  filter?: string
): Promise<any[]> {
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
    log(
      `Table '${tableName}' opened. Searching with vector column '${vectorColumnName}', limit ${limit}. Filter: '${filter || 'None'}'`
    );

    let searchQuery = table
      .search(queryVector, vectorColumnName) // Pass vectorColumnName to search if API supports it, else it uses default.
      .select(['*', '_distance']) // Select all columns and the distance
      .limit(limit);

    if (filter) {
      searchQuery = searchQuery.where(filter);
      log(`Applied filter to search: ${filter}`);
    }

    const results = await searchQuery.execute();
    log(
      `Search completed on table '${tableName}'. Found ${results.length} results.`
    );
    return results;
  } catch (error: any) {
    log(`Error searching table '${tableName}': ${error.message}`, 'error');
    if (error.message && error.message.includes('does not exist')) {
      log(`Table '${tableName}' not found. Cannot perform search.`, 'error');
    } else if (error.message && error.message.includes('vector_column')) {
      // Example of a specific error
      log(
        `Potential issue with vector column name '${vectorColumnName}' or its configuration in table '${tableName}'.`,
        'error'
      );
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
export async function updateRecord(
  db: lancedb.Connection,
  tableName: string,
  recordIdField: string,
  recordIdValue: string,
  updatedFields: Record<string, any>
): Promise<void> {
  if (!db) {
    log('Database connection not provided to updateRecord.', 'error');
    return Promise.reject(new Error('Database connection not provided.'));
  }
  if (!tableName || !recordIdField || !recordIdValue) {
    log(
      'Table name, recordIdField, or recordIdValue not provided to updateRecord.',
      'error'
    );
    return Promise.reject(
      new Error('Table name, recordIdField, or recordIdValue not provided.')
    );
  }
  if (!updatedFields || Object.keys(updatedFields).length === 0) {
    log('No fields to update provided to updateRecord.', 'error');
    return Promise.reject(new Error('No fields to update provided.'));
  }
  if (updatedFields.hasOwnProperty(recordIdField)) {
    log(
      `Cannot update the record ID field ('${recordIdField}') itself.`,
      'error'
    );
    return Promise.reject(
      new Error(
        `Cannot update the record ID field ('${recordIdField}') itself.`
      )
    );
  }

  const filter = `${recordIdField} = '${recordIdValue}'`;
  log(
    `Attempting to update record(s) in table '${tableName}' where ${filter}.`
  );

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
      log(
        `No records found in table '${tableName}' matching filter '${filter}'. Nothing to update.`
      );
      return;
    }
    log(
      `Found ${recordsToUpdate.length} record(s) to update. Performing delete and add.`
    );

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
    log(
      `Added ${newRecords.length} updated record(s) to table '${tableName}'.`
    );
  } catch (error: any) {
    log(
      `Error updating record(s) in table '${tableName}': ${error.message}`,
      'error'
    );
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
export async function deleteRecord(
  db: lancedb.Connection,
  tableName: string,
  recordIdField: string,
  recordIdValue: string
): Promise<void> {
  if (!db) {
    log('Database connection not provided to deleteRecord.', 'error');
    return Promise.reject(new Error('Database connection not provided.'));
  }
  if (!tableName || !recordIdField || !recordIdValue) {
    log(
      'Table name, recordIdField, or recordIdValue not provided to deleteRecord.',
      'error'
    );
    return Promise.reject(
      new Error('Table name, recordIdField, or recordIdValue not provided.')
    );
  }

  const filter = `${recordIdField} = '${recordIdValue}'`;
  log(
    `Attempting to delete record(s) from table '${tableName}' where ${filter}.`
  );

  try {
    const table = await db.openTable(tableName);
    await table.delete(filter);
    log(
      `Successfully deleted record(s) (if they existed) from table '${tableName}' where ${filter}.`
    );
  } catch (error: any) {
    log(
      `Error deleting record(s) from table '${tableName}': ${error.message}`,
      'error'
    );
    // console.error("Full error object:", error); // For debugging
    return Promise.reject(error);
  }
}

log('LanceDBManager module loaded with table creation and CRUD logic.');
