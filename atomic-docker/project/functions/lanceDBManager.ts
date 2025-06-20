// Manages LanceDB connections and table initializations for LTM
import * as lancedb from 'vectordb-lance';
import { Schema, Field, Float32, Utf8, Timestamp, List, FixedSizeList } from '@lancedb/lancedb/dist/arrow'; // Adjust path if necessary based on actual package structure

const LTM_DB_PATH_PREFIX = './lance_db/'; // Example base path, can be configured
const DEFAULT_VECTOR_DIMENSION = 768;

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
  new Field('interaction_summary_embeddings', new FixedSizeList(DEFAULT_VECTOR_DIMENSION, new Field('item', new Float32(), true)), true),
  new Field('interaction_history_embeddings', new FixedSizeList(DEFAULT_VECTOR_DIMENSION, new Field('item', new Float32(), true)), true), // Placeholder, see LTM_SCHEMAS.md
  new Field('interaction_summaries', new List(new Field('item', new Utf8(), true)), true),
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
]);


/**
 * Initializes and connects to a LanceDB database.
 * If the database does not exist at the given path, it will be created.
 * After successful connection, it ensures all necessary tables exist.
 * @param dbName The name of the database (e.g., 'ltm_agent_data').
 * @returns A promise that resolves to the database connection object or null if connection fails.
 */
export async function initializeDB(dbName: string): Promise<lancedb.Connection | null> {
  const dbPath = `${LTM_DB_PATH_PREFIX}${dbName}.lance`;
  log(`Initializing LanceDB at path: ${dbPath}`);
  try {
    const db = await lancedb.connect(dbPath);
    log(`Successfully connected to LanceDB: ${dbPath}`);
    await ensureTablesExist(db);
    return db;
  } catch (error) {
    log(`Error connecting to or creating LanceDB at ${dbPath}: ${error}`, 'error');
    return null;
  }
}

/**
 * Creates the UserProfiles table if it doesn't already exist.
 * @param db The LanceDB connection object.
 */
export async function createUserProfilesTable(db: lancedb.Connection): Promise<void> {
  if (!db) {
    log('Database connection not provided to createUserProfilesTable.', 'error');
    return;
  }
  const tableName = 'user_profiles';
  try {
    log(`Attempting to create table: ${tableName}.`);
    // Provide an empty array of the correct type for schema creation if no initial data.
    // LanceDB uses Arrow schema, which can be explicitly defined.
    await db.createTable(tableName, userProfilesSchema, { mode: 'create' });
    log(`Table '${tableName}' created successfully or already exists.`);
  } catch (error: any) {
    if (error.message && error.message.includes('already exists')) { // Error message might vary
      log(`Table '${tableName}' already exists. No action taken.`);
    } else {
      log(`Error creating table '${tableName}': ${error}`, 'error');
      // console.error(error); // For more detailed error object
    }
  }
}

/**
 * Creates the KnowledgeBase table if it doesn't already exist.
 * @param db The LanceDB connection object.
 */
export async function createKnowledgeBaseTable(db: lancedb.Connection): Promise<void> {
  if (!db) {
    log('Database connection not provided to createKnowledgeBaseTable.', 'error');
    return;
  }
  const tableName = 'knowledge_base';
  try {
    log(`Attempting to create table: ${tableName}.`);
    await db.createTable(tableName, knowledgeBaseSchema, { mode: 'create' });
    log(`Table '${tableName}' created successfully or already exists.`);
  } catch (error: any) {
    if (error.message && error.message.includes('already exists')) {
      log(`Table '${tableName}' already exists. No action taken.`);
    } else {
      log(`Error creating table '${tableName}': ${error}`, 'error');
    }
  }
}

/**
 * Creates the ResearchFindings table if it doesn't already exist.
 * @param db The LanceDB connection object.
 */
export async function createResearchFindingsTable(db: lancedb.Connection): Promise<void> {
  if (!db) {
    log('Database connection not provided to createResearchFindingsTable.', 'error');
    return;
  }
  const tableName = 'research_findings';
  try {
    log(`Attempting to create table: ${tableName}.`);
    await db.createTable(tableName, researchFindingsSchema, { mode: 'create' });
    log(`Table '${tableName}' created successfully or already exists.`);
  } catch (error: any) {
    if (error.message && error.message.includes('already exists')) {
      log(`Table '${tableName}' already exists. No action taken.`);
    } else {
      log(`Error creating table '${tableName}': ${error}`, 'error');
    }
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
    log(`Table '${tableName}' opened. Adding ${Array.isArray(data) ? data.length : 1} record(s).`);
    await table.add(data);
    log(`Successfully added record(s) to table '${tableName}'.`);
  } catch (error: any) {
    log(`Error adding record(s) to table '${tableName}': ${error.message}`, 'error');
    if (error.message && error.message.includes('does not exist')) { // Or similar error message
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
    log(`Table '${tableName}' opened. Searching with vector column '${vectorColumnName}', limit ${limit}. Filter: '${filter || 'None'}'`);

    let searchQuery = table.search(queryVector, vectorColumnName) // Pass vectorColumnName to search if API supports it, else it uses default.
                           .select(['*', '_distance']) // Select all columns and the distance
                           .limit(limit);

    if (filter) {
      searchQuery = searchQuery.where(filter);
      log(`Applied filter to search: ${filter}`);
    }

    const results = await searchQuery.execute();
    log(`Search completed on table '${tableName}'. Found ${results.length} results.`);
    return results;
  } catch (error: any) {
    log(`Error searching table '${tableName}': ${error.message}`, 'error');
    if (error.message && error.message.includes('does not exist')) {
      log(`Table '${tableName}' not found. Cannot perform search.`, 'error');
    } else if (error.message && error.message.includes('vector_column')) { // Example of a specific error
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

log('LanceDBManager module loaded with table creation logic.');
