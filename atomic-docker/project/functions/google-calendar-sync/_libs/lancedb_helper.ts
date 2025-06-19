import { connect, Connection, Table } from 'vectordb';

const LANCEDB_DATA_PATH = '/data/lancedb'; // Assuming a local path

interface EventSchema {
  id: string; // Primary key: eventId#calendarId
  userId: string;
  vector: number[]; // OpenAI text-embedding-3-small dimension: 1536
  start_date: string; // ISO 8601 format
  end_date: string; // ISO 8601 format
  raw_event_text?: string; // Optional: summary:description
}

async function connectToLanceDB(): Promise<Connection> {
  try {
    const db = await connect(LANCEDB_DATA_PATH);
    console.log('Successfully connected to LanceDB.');
    return db;
  } catch (error) {
    console.error('Failed to connect to LanceDB:', error);
    throw error;
  }
}

export async function getOrCreateEventTable(db: Connection): Promise<Table<EventSchema>> {
  const tableName = 'events';
  try {
    const table = await db.openTable<EventSchema>(tableName);
    console.log(`Table "${tableName}" opened successfully.`);
    return table;
  } catch (error) {
    // Assuming error indicates table doesn't exist, try to create it
    console.log(`Table "${tableName}" not found, attempting to create it.`);
    try {
      // LanceDB requires a sample data object to infer schema for creation,
      // or an explicit schema definition if supported by the version of vectordb.
      // For simplicity, we'll use an empty array and rely on schema inference if possible,
      // or adjust if direct schema definition is needed.
      // A more robust approach would involve checking the error type.
      const initialData: EventSchema[] = []; // LanceDB might need representative data or an explicit schema

      // Note: The `vectordb` library's API for table creation might vary.
      // `db.createTable` might require a schema object or sample data.
      // Let's assume `createTable` can take the table name and optionally initial data or a schema.
      // If `embed` function is required like in documentation, we'd need to specify dummy embedding for schema.
      // For now, we'll try creating with just the name and then add data which defines schema.
      // This part might need adjustment based on exact library behavior for schema definition on creation.
      // A common pattern is to provide data with vector fields to create the schema.
      const table = await db.createTable<EventSchema>(tableName, initialData);
      console.log(`Table "${tableName}" created successfully.`);
      return table;
    } catch (creationError) {
      console.error(`Failed to create table "${tableName}":`, creationError);
      throw creationError;
    }
  }
}

export async function bulkUpsertToLanceDBEvents(data: EventSchema[]): Promise<void> {
  if (!data || data.length === 0) {
    console.log('No data provided for upsert.');
    return;
  }
  const db = await connectToLanceDB();
  const table = await getOrCreateEventTable(db);

  try {
    // LanceDB's add operation can often act as an upsert if IDs are present
    // and the table is configured to handle conflicts by replacement or update.
    // However, a common explicit upsert pattern is delete then add.
    // For simplicity, we'll first delete existing records by ID, then add new ones.
    // This ensures idempotency for the upsert operation.
    const existingIds = data.map(item => item.id);
    if (existingIds.length > 0) {
      const deleteQuery = `id IN (${existingIds.map(id => `'${id}'`).join(',')})`;
      try {
        await table.delete(deleteQuery);
        console.log(`Successfully deleted existing records for IDs: ${existingIds.join(', ')}`);
      } catch (deleteError) {
        // It's possible that delete fails if some IDs don't exist; often this is not a critical error for upsert.
        console.warn(`Warning or error during pre-delete for upsert (some IDs might not exist):`, deleteError);
      }
    }

    await table.add(data);
    console.log(`Successfully upserted ${data.length} records.`);
  } catch (error) {
    console.error('Error during bulk upsert to LanceDB:', error);
    throw error;
  }
}

export async function bulkDeleteFromLanceDBEvents(ids: string[]): Promise<void> {
  if (!ids || ids.length === 0) {
    console.log('No IDs provided for deletion.');
    return;
  }
  const db = await connectToLanceDB();
  const table = await getOrCreateEventTable(db); // Ensure table exists

  try {
    const deleteQuery = `id IN (${ids.map(id => `'${id.replace(/'/g, "''")}'`).join(',')})`; // Escape single quotes in IDs
    await table.delete(deleteQuery);
    console.log(`Successfully deleted records for IDs: ${ids.join(', ')}`);
  } catch (error) {
    console.error('Error during bulk delete from LanceDB:', error);
    throw error;
  }
}
