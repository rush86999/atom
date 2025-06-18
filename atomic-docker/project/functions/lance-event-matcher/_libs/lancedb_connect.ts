import { connect, Connection, Table } from 'vectordb';
import { LANCEDB_DATA_PATH, LANCEDB_EVENT_TABLE_NAME } from './constants';
import { EventSchema } from './types'; // Assuming EventSchema is defined for table interactions

let dbConnection: Connection | null = null;

async function getDBConnection(): Promise<Connection> {
  if (dbConnection) {
    return dbConnection;
  }
  try {
    dbConnection = await connect(LANCEDB_DATA_PATH);
    console.log('Successfully connected to LanceDB.');
    return dbConnection;
  } catch (error) {
    console.error('Failed to connect to LanceDB:', error);
    // Reset connection on failure to allow retry
    dbConnection = null;
    throw error;
  }
}

export async function getEventTable(): Promise<Table<EventSchema>> {
  const db = await getDBConnection();
  try {
    const table = await db.openTable<EventSchema>(LANCEDB_EVENT_TABLE_NAME);
    console.log(`Table "${LANCEDB_EVENT_TABLE_NAME}" opened successfully.`);
    return table;
  } catch (error) {
    // This simple version assumes the table always exists
    // A more robust version might try to create it if not found,
    // but for a read-focused service, it might be better to ensure it's created elsewhere.
    console.error(`Failed to open table "${LANCEDB_EVENT_TABLE_NAME}":`, error);
    throw new Error(`Table "${LANCEDB_EVENT_TABLE_NAME}" not found or could not be opened. Ensure it is created and populated by the google-calendar-sync service.`);
  }
}

// Optional: Close connection if needed, e.g. for cleanup during application shutdown
export async function closeDBConnection(): Promise<void> {
  if (dbConnection) {
    // await dbConnection.close(); // The `vectordb` API might not have an explicit close for the connection object itself.
    // LanceDB connections are often managed at the process level.
    // For now, we'll just nullify it.
    dbConnection = null;
    console.log('LanceDB connection closed (nullified).');
  }
}
