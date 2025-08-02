import { connect, Connection, Table } from "@lancedb/lancedb";

// Environment variable for LanceDB path or a default
const LANCEDB_DATA_PATH = process.env.LANCEDB_URI || "/data/lancedb";
const EVENT_TABLE_NAME = "events_data"; // For general event search
const TRAINING_TABLE_NAME = "training_data"; // For features-apply, schedule-event, and _chat training

let dbConnection: Connection | null = null;

/**
 * Establishes or returns an existing connection to LanceDB.
 */
export async function getDBConnection(): Promise<Connection> {
  if (dbConnection) {
    return dbConnection;
  }
  try {
    dbConnection = await connect(LANCEDB_DATA_PATH);
    console.log(`Successfully connected to LanceDB at ${LANCEDB_DATA_PATH}`);
    return dbConnection;
  } catch (error) {
    console.error(
      `Failed to connect to LanceDB at ${LANCEDB_DATA_PATH}:`,
      error,
    );
    dbConnection = null; // Reset on failure to allow retry
    throw error;
  }
}

// Schema Definitions

// For general event data, used by _chat (event search) and as a source for vectors.
export interface EventSchema {
  id: string; // Primary Key: original eventId from the source system (e.g., googleEventId)
  userId: string;
  vector: number[]; // OpenAI text-embedding-3-small dimension: 1536
  start_date: string; // ISO 8601 format
  end_date: string; // ISO 8601 format
  raw_event_text: string; // Concatenation of summary, description, etc.
  calendarId?: string; // Optional: calendarId if events can span multiple calendars for a user
  last_modified: string; // ISO 8601 format, when this record was last updated
  // Add other filterable/retrievable fields as needed by _chat search
  title?: string;
  location?: string;
}

// For training data, used by features-apply, schedule-event, and _chat (training part)
export interface TrainingEventSchema {
  id: string; // Primary Key: usually the ID of the event whose properties are being learned/stored
  userId: string;
  vector: number[]; // Vector derived from source_event_text
  source_event_text: string; // Text used to generate the vector (e.g., title:description)
  // Store learned properties directly or link to them if they are complex.
  // Example:
  // category_name?: string;
  // reminder_setting_minutes?: number[];
  created_at: string; // ISO 8601 format
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
export async function getOrCreateTable(
  db: Connection,
  tableName: string,
  // Provide a representative empty item for schema inference, especially for vector types.
  // e.g., { id: "", vector: [], ...other_fields_with_default_values }
  representativeData: any[],
): Promise<Table> {
  try {
    const table = await db.openTable(tableName);
    console.log(`Table "${tableName}" opened successfully.`);
    return table;
  } catch (error) {
    // Basic error check; more specific checks for "table not found" might be needed.
    console.log(`Table "${tableName}" not found, attempting to create it.`);
    try {
      // Create table with representative data to define schema.
      // Ensure the representativeData includes a vector field if the schema requires one.
      const table = await db.createTable(tableName, representativeData);
      console.log(
        `Table "${tableName}" created successfully with inferred schema.`,
      );
      return table;
    } catch (creationError) {
      console.error(`Failed to create table "${tableName}":`, creationError);
      throw creationError;
    }
  }
}

/**
 * Upserts items into the specified LanceDB table.
 * This implementation assumes an "upsert" is a delete followed by an add.
 * Requires items to have an 'id' field.
 * @param tableName The name of the table.
 * @param items An array of items to upsert. Each item must have an 'id' property.
 * @param representativeItem Sample data (can be an empty typed array with one item) to help infer schema on creation.
 */
export async function upsertItems(
  db: Connection, // Pass connection to avoid repeated calls to getDBConnection
  tableName: string,
  items: any[],
  representativeItemSchema: any[], // Used if table needs to be created
): Promise<void> {
  if (!items || items.length === 0) {
    console.log(`No items provided for upsert in table "${tableName}".`);
    return;
  }
  const table = await getOrCreateTable(db, tableName, representativeItemSchema);

  // Extract IDs for deletion
  const ids = items.map((item) => item.id);
  if (ids.length > 0) {
    const deleteQuery = `id IN (${ids.map((id) => `'${id.replace(/'/g, "''")}'`).join(",")})`;
    try {
      await table.delete(deleteQuery);
      console.log(
        `Successfully pre-deleted existing items for upsert in "${tableName}" for IDs: ${ids.join(", ")}`,
      );
    } catch (deleteError) {
      // It's often okay if delete fails because items don't exist yet.
      console.warn(
        `Warning or error during pre-delete for upsert in "${tableName}" (some IDs might not exist):`,
        deleteError.message,
      );
    }
  }

  try {
    await table.add(items);
    console.log(
      `Successfully added/updated ${items.length} items in table "${tableName}".`,
    );
  } catch (error) {
    console.error(
      `Error during bulk add for upsert in table "${tableName}":`,
      error,
    );
    throw error;
  }
}

/**
 * Deletes items from the specified LanceDB table by their IDs.
 * @param tableName The name of the table.
 * @param ids An array of string IDs to delete.
 * @param representativeItemSchema Sample data used if table needs to be "opened" first (though delete usually implies table exists).
 */
export async function deleteItemsByIds(
  db: Connection,
  tableName: string,
  ids: string[],
  representativeItemSchema: any[],
): Promise<void> {
  if (!ids || ids.length === 0) {
    console.log(`No IDs provided for deletion in table "${tableName}".`);
    return;
  }
  // Ensure table is accessible; creation logic might not be strictly necessary for delete
  // but getOrCreateTable handles opening it.
  const table = await getOrCreateTable(db, tableName, representativeItemSchema);

  const deleteQuery = `id IN (${ids.map((id) => `'${id.replace(/'/g, "''")}'`).join(",")})`;
  try {
    await table.delete(deleteQuery);
    console.log(
      `Successfully deleted items from "${tableName}" for IDs: ${ids.join(", ")}`,
    );
  } catch (error) {
    console.error(`Error during bulk delete from table "${tableName}":`, error);
    throw error;
  }
}

/**
 * Searches a LanceDB table by a vector, with optional filtering.
 * @param tableName The name of the table to search.
 * @param vector The search vector.
 * @param limit The maximum number of results to return.
 * @param representativeItemSchema Sample data for table schema.
 * @param filterCondition Optional SQL-like filter condition string (e.g., "userId = '123' AND price > 50").
 *                        Ensure column names and values are correctly quoted/formatted for SQL.
 */
export async function searchTableByVector(
  db: Connection,
  tableName: string,
  vector: number[],
  limit: number,
  representativeItemSchema: any[],
  filterCondition?: string,
): Promise<any[]> {
  if (!vector || vector.length === 0) {
    throw new Error("Search vector must be provided.");
  }
  const table = await getOrCreateTable(db, tableName, representativeItemSchema);
  let query = table.search(vector);

  if (filterCondition && filterCondition.trim() !== "") {
    query = query.where(filterCondition);
  }

  query = query.limit(limit);

  try {
    const results = await query.toArray();
    return results;
  } catch (error) {
    console.error(`Error searching table "${tableName}" by vector:`, error);
    throw error;
  }
}

/**
 * Retrieves a single item from the specified LanceDB table by its ID.
 * @param tableName The name of the table.
 * @param id The ID of the item to retrieve.
 * @param representativeItemSchema Sample data for table schema.
 * @returns The item if found, otherwise null.
 */
export async function getItemById(
  db: Connection,
  tableName: string,
  id: string,
  representativeItemSchema: any[],
): Promise<any | null> {
  if (!id) {
    throw new Error("ID must be provided to get an item.");
  }
  const table = await getOrCreateTable(db, tableName, representativeItemSchema);

  // LanceDB's query for specific ID might be `id = '...'`
  const results = await table
    .query()
    .where(`id = '${id.replace(/'/g, "''")}'`)
    .limit(1)
    .toArray();

  return results.length > 0 ? results[0] : null;
}

// Update getEventDataTable and getTrainingDataTable to pass the db connection
// and representative data to the generic CRUD functions.

export async function upsertEvents(items: EventSchema[]): Promise<void> {
  const db = await getDBConnection();
  const sampleEventData: EventSchema[] = [
    {
      id: "",
      userId: "",
      vector: [],
      start_date: "",
      end_date: "",
      raw_event_text: "",
      last_modified: "",
      title: "",
    },
  ];
  await upsertItems(db, EVENT_TABLE_NAME, items, sampleEventData);
}

export async function deleteEventsByIds(ids: string[]): Promise<void> {
  const db = await getDBConnection();
  const sampleEventData: EventSchema[] = [
    {
      id: "",
      userId: "",
      vector: [],
      start_date: "",
      end_date: "",
      raw_event_text: "",
      last_modified: "",
      title: "",
    },
  ];
  await deleteItemsByIds(db, EVENT_TABLE_NAME, ids, sampleEventData);
}

export async function searchEvents(
  vector: number[],
  limit: number,
  filterCondition?: string,
): Promise<EventSchema[]> {
  const db = await getDBConnection();
  const sampleEventData: EventSchema[] = [
    {
      id: "",
      userId: "",
      vector: [],
      start_date: "",
      end_date: "",
      raw_event_text: "",
      last_modified: "",
      title: "",
    },
  ];
  return (await searchTableByVector(
    db,
    EVENT_TABLE_NAME,
    vector,
    limit,
    sampleEventData,
    filterCondition,
  )) as EventSchema[];
}

export async function getEventById(id: string): Promise<EventSchema | null> {
  const db = await getDBConnection();
  const sampleEventData: EventSchema[] = [
    {
      id: "",
      userId: "",
      vector: [],
      start_date: "",
      end_date: "",
      raw_event_text: "",
      last_modified: "",
      title: "",
    },
  ];
  return (await getItemById(
    db,
    EVENT_TABLE_NAME,
    id,
    sampleEventData,
  )) as EventSchema | null;
}

// Similarly for TrainingData
export async function upsertTrainingEvents(
  items: TrainingEventSchema[],
): Promise<void> {
  const db = await getDBConnection();
  const sampleTrainingData: TrainingEventSchema[] = [
    {
      id: "",
      userId: "",
      vector: [],
      source_event_text: "",
      created_at: "",
    },
  ];
  await upsertItems(db, TRAINING_TABLE_NAME, items, sampleTrainingData);
}

export async function deleteTrainingEventsByIds(ids: string[]): Promise<void> {
  const db = await getDBConnection();
  const sampleTrainingData: TrainingEventSchema[] = [
    {
      id: "",
      userId: "",
      vector: [],
      source_event_text: "",
      created_at: "",
    },
  ];
  await deleteItemsByIds(db, TRAINING_TABLE_NAME, ids, sampleTrainingData);
}

export async function searchTrainingEvents(
  vector: number[],
  limit: number,
  filterCondition?: string,
): Promise<TrainingEventSchema[]> {
  const db = await getDBConnection();
  const sampleTrainingData: TrainingEventSchema[] = [
    {
      id: "",
      userId: "",
      vector: [],
      source_event_text: "",
      created_at: "",
    },
  ];
  return (await searchTableByVector(
    db,
    TRAINING_TABLE_NAME,
    vector,
    limit,
    sampleTrainingData,
    filterCondition,
  )) as TrainingEventSchema[];
}

export async function getTrainingEventById(
  id: string,
): Promise<TrainingEventSchema | null> {
  const db = await getDBConnection();
  const sampleTrainingData: TrainingEventSchema[] = [
    {
      id: "",
      userId: "",
      vector: [],
      source_event_text: "",
      created_at: "",
    },
  ];
  return (await getItemById(
    db,
    TRAINING_TABLE_NAME,
    id,
    sampleTrainingData,
  )) as TrainingEventSchema | null;
}

// Example of how to get specific tables (can be expanded)
export async function getEventDataTable(): Promise<Table> {
  const db = await getDBConnection();
  // Provide a sample data structure for schema inference if table needs creation.
  // Crucially, vector field must be present.
  const sampleEventData: EventSchema[] = [
    {
      id: "",
      userId: "",
      vector: [],
      start_date: "",
      end_date: "",
      raw_event_text: "",
      last_modified: "",
      title: "",
    },
  ];
  return getOrCreateTable(db, EVENT_TABLE_NAME, sampleEventData);
}

export async function getTrainingDataTable(): Promise<Table> {
  const db = await getDBConnection();
  const sampleTrainingData: TrainingEventSchema[] = [
    {
      id: "",
      userId: "",
      vector: [],
      source_event_text: "",
      created_at: "",
    },
  ];
  return getOrCreateTable(db, TRAINING_TABLE_NAME, sampleTrainingData);
}
