import { connect } from '@lancedb/lancedb';
// Environment variable for LanceDB path or a default
const LANCEDB_DATA_PATH = process.env.LANCEDB_URI || '/data/lancedb';
const EVENT_TABLE_NAME = 'events_data'; // For general event search
const TRAINING_TABLE_NAME = 'training_data'; // For features-apply, schedule-event, and _chat training
let dbConnection = null;
/**
 * Establishes or returns an existing connection to LanceDB.
 */
export async function getDBConnection() {
    if (dbConnection) {
        return dbConnection;
    }
    try {
        dbConnection = await connect(LANCEDB_DATA_PATH);
        console.log(`Successfully connected to LanceDB at ${LANCEDB_DATA_PATH}`);
        return dbConnection;
    }
    catch (error) {
        console.error(`Failed to connect to LanceDB at ${LANCEDB_DATA_PATH}:`, error);
        dbConnection = null; // Reset on failure to allow retry
        throw error;
    }
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
export async function getOrCreateTable(db, tableName, 
// Provide a representative empty item for schema inference, especially for vector types.
// e.g., { id: "", vector: [], ...other_fields_with_default_values }
representativeData) {
    try {
        const table = await db.openTable(tableName);
        console.log(`Table "${tableName}" opened successfully.`);
        return table;
    }
    catch (error) {
        // Basic error check; more specific checks for "table not found" might be needed.
        console.log(`Table "${tableName}" not found, attempting to create it.`);
        try {
            // Create table with representative data to define schema.
            // Ensure the representativeData includes a vector field if the schema requires one.
            const table = await db.createTable(tableName, representativeData);
            console.log(`Table "${tableName}" created successfully with inferred schema.`);
            return table;
        }
        catch (creationError) {
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
export async function upsertItems(db, // Pass connection to avoid repeated calls to getDBConnection
tableName, items, representativeItemSchema // Used if table needs to be created
) {
    if (!items || items.length === 0) {
        console.log(`No items provided for upsert in table "${tableName}".`);
        return;
    }
    const table = await getOrCreateTable(db, tableName, representativeItemSchema);
    // Extract IDs for deletion
    const ids = items.map((item) => item.id);
    if (ids.length > 0) {
        const deleteQuery = `id IN (${ids.map((id) => `'${id.replace(/'/g, "''")}'`).join(',')})`;
        try {
            await table.delete(deleteQuery);
            console.log(`Successfully pre-deleted existing items for upsert in "${tableName}" for IDs: ${ids.join(', ')}`);
        }
        catch (deleteError) {
            // It's often okay if delete fails because items don't exist yet.
            console.warn(`Warning or error during pre-delete for upsert in "${tableName}" (some IDs might not exist):`, deleteError.message);
        }
    }
    try {
        await table.add(items);
        console.log(`Successfully added/updated ${items.length} items in table "${tableName}".`);
    }
    catch (error) {
        console.error(`Error during bulk add for upsert in table "${tableName}":`, error);
        throw error;
    }
}
/**
 * Deletes items from the specified LanceDB table by their IDs.
 * @param tableName The name of the table.
 * @param ids An array of string IDs to delete.
 * @param representativeItemSchema Sample data used if table needs to be "opened" first (though delete usually implies table exists).
 */
export async function deleteItemsByIds(db, tableName, ids, representativeItemSchema) {
    if (!ids || ids.length === 0) {
        console.log(`No IDs provided for deletion in table "${tableName}".`);
        return;
    }
    // Ensure table is accessible; creation logic might not be strictly necessary for delete
    // but getOrCreateTable handles opening it.
    const table = await getOrCreateTable(db, tableName, representativeItemSchema);
    const deleteQuery = `id IN (${ids.map((id) => `'${id.replace(/'/g, "''")}'`).join(',')})`;
    try {
        await table.delete(deleteQuery);
        console.log(`Successfully deleted items from "${tableName}" for IDs: ${ids.join(', ')}`);
    }
    catch (error) {
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
export async function searchTableByVector(db, tableName, vector, limit, representativeItemSchema, filterCondition) {
    if (!vector || vector.length === 0) {
        throw new Error('Search vector must be provided.');
    }
    const table = await getOrCreateTable(db, tableName, representativeItemSchema);
    let query = table.search(vector);
    if (filterCondition && filterCondition.trim() !== '') {
        query = query.where(filterCondition);
    }
    query = query.limit(limit);
    try {
        const results = await query.toArray();
        return results;
    }
    catch (error) {
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
export async function getItemById(db, tableName, id, representativeItemSchema) {
    if (!id) {
        throw new Error('ID must be provided to get an item.');
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
export async function upsertEvents(items) {
    const db = await getDBConnection();
    const sampleEventData = [
        {
            id: '',
            userId: '',
            vector: [],
            start_date: '',
            end_date: '',
            raw_event_text: '',
            last_modified: '',
            title: '',
        },
    ];
    await upsertItems(db, EVENT_TABLE_NAME, items, sampleEventData);
}
export async function deleteEventsByIds(ids) {
    const db = await getDBConnection();
    const sampleEventData = [
        {
            id: '',
            userId: '',
            vector: [],
            start_date: '',
            end_date: '',
            raw_event_text: '',
            last_modified: '',
            title: '',
        },
    ];
    await deleteItemsByIds(db, EVENT_TABLE_NAME, ids, sampleEventData);
}
export async function searchEvents(vector, limit, filterCondition) {
    const db = await getDBConnection();
    const sampleEventData = [
        {
            id: '',
            userId: '',
            vector: [],
            start_date: '',
            end_date: '',
            raw_event_text: '',
            last_modified: '',
            title: '',
        },
    ];
    return (await searchTableByVector(db, EVENT_TABLE_NAME, vector, limit, sampleEventData, filterCondition));
}
export async function getEventById(id) {
    const db = await getDBConnection();
    const sampleEventData = [
        {
            id: '',
            userId: '',
            vector: [],
            start_date: '',
            end_date: '',
            raw_event_text: '',
            last_modified: '',
            title: '',
        },
    ];
    return (await getItemById(db, EVENT_TABLE_NAME, id, sampleEventData));
}
// Similarly for TrainingData
export async function upsertTrainingEvents(items) {
    const db = await getDBConnection();
    const sampleTrainingData = [
        {
            id: '',
            userId: '',
            vector: [],
            source_event_text: '',
            created_at: '',
        },
    ];
    await upsertItems(db, TRAINING_TABLE_NAME, items, sampleTrainingData);
}
export async function deleteTrainingEventsByIds(ids) {
    const db = await getDBConnection();
    const sampleTrainingData = [
        {
            id: '',
            userId: '',
            vector: [],
            source_event_text: '',
            created_at: '',
        },
    ];
    await deleteItemsByIds(db, TRAINING_TABLE_NAME, ids, sampleTrainingData);
}
export async function searchTrainingEvents(vector, limit, filterCondition) {
    const db = await getDBConnection();
    const sampleTrainingData = [
        {
            id: '',
            userId: '',
            vector: [],
            source_event_text: '',
            created_at: '',
        },
    ];
    return (await searchTableByVector(db, TRAINING_TABLE_NAME, vector, limit, sampleTrainingData, filterCondition));
}
export async function getTrainingEventById(id) {
    const db = await getDBConnection();
    const sampleTrainingData = [
        {
            id: '',
            userId: '',
            vector: [],
            source_event_text: '',
            created_at: '',
        },
    ];
    return (await getItemById(db, TRAINING_TABLE_NAME, id, sampleTrainingData));
}
// Example of how to get specific tables (can be expanded)
export async function getEventDataTable() {
    const db = await getDBConnection();
    // Provide a sample data structure for schema inference if table needs creation.
    // Crucially, vector field must be present.
    const sampleEventData = [
        {
            id: '',
            userId: '',
            vector: [],
            start_date: '',
            end_date: '',
            raw_event_text: '',
            last_modified: '',
            title: '',
        },
    ];
    return getOrCreateTable(db, EVENT_TABLE_NAME, sampleEventData);
}
export async function getTrainingDataTable() {
    const db = await getDBConnection();
    const sampleTrainingData = [
        {
            id: '',
            userId: '',
            vector: [],
            source_event_text: '',
            created_at: '',
        },
    ];
    return getOrCreateTable(db, TRAINING_TABLE_NAME, sampleTrainingData);
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoibGFuY2VkYl9zZXJ2aWNlLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsibGFuY2VkYl9zZXJ2aWNlLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiJBQUFBLE9BQU8sRUFBRSxPQUFPLEVBQXFCLE1BQU0sa0JBQWtCLENBQUM7QUFFOUQscURBQXFEO0FBQ3JELE1BQU0saUJBQWlCLEdBQUcsT0FBTyxDQUFDLEdBQUcsQ0FBQyxXQUFXLElBQUksZUFBZSxDQUFDO0FBQ3JFLE1BQU0sZ0JBQWdCLEdBQUcsYUFBYSxDQUFDLENBQUMsMkJBQTJCO0FBQ25FLE1BQU0sbUJBQW1CLEdBQUcsZUFBZSxDQUFDLENBQUMseURBQXlEO0FBRXRHLElBQUksWUFBWSxHQUFzQixJQUFJLENBQUM7QUFFM0M7O0dBRUc7QUFDSCxNQUFNLENBQUMsS0FBSyxVQUFVLGVBQWU7SUFDbkMsSUFBSSxZQUFZLEVBQUUsQ0FBQztRQUNqQixPQUFPLFlBQVksQ0FBQztJQUN0QixDQUFDO0lBQ0QsSUFBSSxDQUFDO1FBQ0gsWUFBWSxHQUFHLE1BQU0sT0FBTyxDQUFDLGlCQUFpQixDQUFDLENBQUM7UUFDaEQsT0FBTyxDQUFDLEdBQUcsQ0FBQyx3Q0FBd0MsaUJBQWlCLEVBQUUsQ0FBQyxDQUFDO1FBQ3pFLE9BQU8sWUFBWSxDQUFDO0lBQ3RCLENBQUM7SUFBQyxPQUFPLEtBQUssRUFBRSxDQUFDO1FBQ2YsT0FBTyxDQUFDLEtBQUssQ0FDWCxtQ0FBbUMsaUJBQWlCLEdBQUcsRUFDdkQsS0FBSyxDQUNOLENBQUM7UUFDRixZQUFZLEdBQUcsSUFBSSxDQUFDLENBQUMsa0NBQWtDO1FBQ3ZELE1BQU0sS0FBSyxDQUFDO0lBQ2QsQ0FBQztBQUNILENBQUM7QUFnQ0Q7Ozs7Ozs7OztHQVNHO0FBQ0gsTUFBTSxDQUFDLEtBQUssVUFBVSxnQkFBZ0IsQ0FDcEMsRUFBYyxFQUNkLFNBQWlCO0FBQ2pCLHlGQUF5RjtBQUN6RixvRUFBb0U7QUFDcEUsa0JBQXlCO0lBRXpCLElBQUksQ0FBQztRQUNILE1BQU0sS0FBSyxHQUFHLE1BQU0sRUFBRSxDQUFDLFNBQVMsQ0FBQyxTQUFTLENBQUMsQ0FBQztRQUM1QyxPQUFPLENBQUMsR0FBRyxDQUFDLFVBQVUsU0FBUyx3QkFBd0IsQ0FBQyxDQUFDO1FBQ3pELE9BQU8sS0FBSyxDQUFDO0lBQ2YsQ0FBQztJQUFDLE9BQU8sS0FBSyxFQUFFLENBQUM7UUFDZixpRkFBaUY7UUFDakYsT0FBTyxDQUFDLEdBQUcsQ0FBQyxVQUFVLFNBQVMsdUNBQXVDLENBQUMsQ0FBQztRQUN4RSxJQUFJLENBQUM7WUFDSCwwREFBMEQ7WUFDMUQsb0ZBQW9GO1lBQ3BGLE1BQU0sS0FBSyxHQUFHLE1BQU0sRUFBRSxDQUFDLFdBQVcsQ0FBQyxTQUFTLEVBQUUsa0JBQWtCLENBQUMsQ0FBQztZQUNsRSxPQUFPLENBQUMsR0FBRyxDQUNULFVBQVUsU0FBUyw4Q0FBOEMsQ0FDbEUsQ0FBQztZQUNGLE9BQU8sS0FBSyxDQUFDO1FBQ2YsQ0FBQztRQUFDLE9BQU8sYUFBYSxFQUFFLENBQUM7WUFDdkIsT0FBTyxDQUFDLEtBQUssQ0FBQywyQkFBMkIsU0FBUyxJQUFJLEVBQUUsYUFBYSxDQUFDLENBQUM7WUFDdkUsTUFBTSxhQUFhLENBQUM7UUFDdEIsQ0FBQztJQUNILENBQUM7QUFDSCxDQUFDO0FBRUQ7Ozs7Ozs7R0FPRztBQUNILE1BQU0sQ0FBQyxLQUFLLFVBQVUsV0FBVyxDQUMvQixFQUFjLEVBQUUsNkRBQTZEO0FBQzdFLFNBQWlCLEVBQ2pCLEtBQVksRUFDWix3QkFBK0IsQ0FBQyxvQ0FBb0M7O0lBRXBFLElBQUksQ0FBQyxLQUFLLElBQUksS0FBSyxDQUFDLE1BQU0sS0FBSyxDQUFDLEVBQUUsQ0FBQztRQUNqQyxPQUFPLENBQUMsR0FBRyxDQUFDLDBDQUEwQyxTQUFTLElBQUksQ0FBQyxDQUFDO1FBQ3JFLE9BQU87SUFDVCxDQUFDO0lBQ0QsTUFBTSxLQUFLLEdBQUcsTUFBTSxnQkFBZ0IsQ0FBQyxFQUFFLEVBQUUsU0FBUyxFQUFFLHdCQUF3QixDQUFDLENBQUM7SUFFOUUsMkJBQTJCO0lBQzNCLE1BQU0sR0FBRyxHQUFHLEtBQUssQ0FBQyxHQUFHLENBQUMsQ0FBQyxJQUFJLEVBQUUsRUFBRSxDQUFDLElBQUksQ0FBQyxFQUFFLENBQUMsQ0FBQztJQUN6QyxJQUFJLEdBQUcsQ0FBQyxNQUFNLEdBQUcsQ0FBQyxFQUFFLENBQUM7UUFDbkIsTUFBTSxXQUFXLEdBQUcsVUFBVSxHQUFHLENBQUMsR0FBRyxDQUFDLENBQUMsRUFBRSxFQUFFLEVBQUUsQ0FBQyxJQUFJLEVBQUUsQ0FBQyxPQUFPLENBQUMsSUFBSSxFQUFFLElBQUksQ0FBQyxHQUFHLENBQUMsQ0FBQyxJQUFJLENBQUMsR0FBRyxDQUFDLEdBQUcsQ0FBQztRQUMxRixJQUFJLENBQUM7WUFDSCxNQUFNLEtBQUssQ0FBQyxNQUFNLENBQUMsV0FBVyxDQUFDLENBQUM7WUFDaEMsT0FBTyxDQUFDLEdBQUcsQ0FDVCwwREFBMEQsU0FBUyxjQUFjLEdBQUcsQ0FBQyxJQUFJLENBQUMsSUFBSSxDQUFDLEVBQUUsQ0FDbEcsQ0FBQztRQUNKLENBQUM7UUFBQyxPQUFPLFdBQVcsRUFBRSxDQUFDO1lBQ3JCLGlFQUFpRTtZQUNqRSxPQUFPLENBQUMsSUFBSSxDQUNWLHFEQUFxRCxTQUFTLCtCQUErQixFQUM3RixXQUFXLENBQUMsT0FBTyxDQUNwQixDQUFDO1FBQ0osQ0FBQztJQUNILENBQUM7SUFFRCxJQUFJLENBQUM7UUFDSCxNQUFNLEtBQUssQ0FBQyxHQUFHLENBQUMsS0FBSyxDQUFDLENBQUM7UUFDdkIsT0FBTyxDQUFDLEdBQUcsQ0FDVCw4QkFBOEIsS0FBSyxDQUFDLE1BQU0sb0JBQW9CLFNBQVMsSUFBSSxDQUM1RSxDQUFDO0lBQ0osQ0FBQztJQUFDLE9BQU8sS0FBSyxFQUFFLENBQUM7UUFDZixPQUFPLENBQUMsS0FBSyxDQUNYLDhDQUE4QyxTQUFTLElBQUksRUFDM0QsS0FBSyxDQUNOLENBQUM7UUFDRixNQUFNLEtBQUssQ0FBQztJQUNkLENBQUM7QUFDSCxDQUFDO0FBRUQ7Ozs7O0dBS0c7QUFDSCxNQUFNLENBQUMsS0FBSyxVQUFVLGdCQUFnQixDQUNwQyxFQUFjLEVBQ2QsU0FBaUIsRUFDakIsR0FBYSxFQUNiLHdCQUErQjtJQUUvQixJQUFJLENBQUMsR0FBRyxJQUFJLEdBQUcsQ0FBQyxNQUFNLEtBQUssQ0FBQyxFQUFFLENBQUM7UUFDN0IsT0FBTyxDQUFDLEdBQUcsQ0FBQywwQ0FBMEMsU0FBUyxJQUFJLENBQUMsQ0FBQztRQUNyRSxPQUFPO0lBQ1QsQ0FBQztJQUNELHdGQUF3RjtJQUN4RiwyQ0FBMkM7SUFDM0MsTUFBTSxLQUFLLEdBQUcsTUFBTSxnQkFBZ0IsQ0FBQyxFQUFFLEVBQUUsU0FBUyxFQUFFLHdCQUF3QixDQUFDLENBQUM7SUFFOUUsTUFBTSxXQUFXLEdBQUcsVUFBVSxHQUFHLENBQUMsR0FBRyxDQUFDLENBQUMsRUFBRSxFQUFFLEVBQUUsQ0FBQyxJQUFJLEVBQUUsQ0FBQyxPQUFPLENBQUMsSUFBSSxFQUFFLElBQUksQ0FBQyxHQUFHLENBQUMsQ0FBQyxJQUFJLENBQUMsR0FBRyxDQUFDLEdBQUcsQ0FBQztJQUMxRixJQUFJLENBQUM7UUFDSCxNQUFNLEtBQUssQ0FBQyxNQUFNLENBQUMsV0FBVyxDQUFDLENBQUM7UUFDaEMsT0FBTyxDQUFDLEdBQUcsQ0FDVCxvQ0FBb0MsU0FBUyxjQUFjLEdBQUcsQ0FBQyxJQUFJLENBQUMsSUFBSSxDQUFDLEVBQUUsQ0FDNUUsQ0FBQztJQUNKLENBQUM7SUFBQyxPQUFPLEtBQUssRUFBRSxDQUFDO1FBQ2YsT0FBTyxDQUFDLEtBQUssQ0FBQyx3Q0FBd0MsU0FBUyxJQUFJLEVBQUUsS0FBSyxDQUFDLENBQUM7UUFDNUUsTUFBTSxLQUFLLENBQUM7SUFDZCxDQUFDO0FBQ0gsQ0FBQztBQUVEOzs7Ozs7OztHQVFHO0FBQ0gsTUFBTSxDQUFDLEtBQUssVUFBVSxtQkFBbUIsQ0FDdkMsRUFBYyxFQUNkLFNBQWlCLEVBQ2pCLE1BQWdCLEVBQ2hCLEtBQWEsRUFDYix3QkFBK0IsRUFDL0IsZUFBd0I7SUFFeEIsSUFBSSxDQUFDLE1BQU0sSUFBSSxNQUFNLENBQUMsTUFBTSxLQUFLLENBQUMsRUFBRSxDQUFDO1FBQ25DLE1BQU0sSUFBSSxLQUFLLENBQUMsaUNBQWlDLENBQUMsQ0FBQztJQUNyRCxDQUFDO0lBQ0QsTUFBTSxLQUFLLEdBQUcsTUFBTSxnQkFBZ0IsQ0FBQyxFQUFFLEVBQUUsU0FBUyxFQUFFLHdCQUF3QixDQUFDLENBQUM7SUFDOUUsSUFBSSxLQUFLLEdBQUcsS0FBSyxDQUFDLE1BQU0sQ0FBQyxNQUFNLENBQUMsQ0FBQztJQUVqQyxJQUFJLGVBQWUsSUFBSSxlQUFlLENBQUMsSUFBSSxFQUFFLEtBQUssRUFBRSxFQUFFLENBQUM7UUFDckQsS0FBSyxHQUFHLEtBQUssQ0FBQyxLQUFLLENBQUMsZUFBZSxDQUFDLENBQUM7SUFDdkMsQ0FBQztJQUVELEtBQUssR0FBRyxLQUFLLENBQUMsS0FBSyxDQUFDLEtBQUssQ0FBQyxDQUFDO0lBRTNCLElBQUksQ0FBQztRQUNILE1BQU0sT0FBTyxHQUFHLE1BQU0sS0FBSyxDQUFDLE9BQU8sRUFBRSxDQUFDO1FBQ3RDLE9BQU8sT0FBTyxDQUFDO0lBQ2pCLENBQUM7SUFBQyxPQUFPLEtBQUssRUFBRSxDQUFDO1FBQ2YsT0FBTyxDQUFDLEtBQUssQ0FBQywwQkFBMEIsU0FBUyxjQUFjLEVBQUUsS0FBSyxDQUFDLENBQUM7UUFDeEUsTUFBTSxLQUFLLENBQUM7SUFDZCxDQUFDO0FBQ0gsQ0FBQztBQUVEOzs7Ozs7R0FNRztBQUNILE1BQU0sQ0FBQyxLQUFLLFVBQVUsV0FBVyxDQUMvQixFQUFjLEVBQ2QsU0FBaUIsRUFDakIsRUFBVSxFQUNWLHdCQUErQjtJQUUvQixJQUFJLENBQUMsRUFBRSxFQUFFLENBQUM7UUFDUixNQUFNLElBQUksS0FBSyxDQUFDLHFDQUFxQyxDQUFDLENBQUM7SUFDekQsQ0FBQztJQUNELE1BQU0sS0FBSyxHQUFHLE1BQU0sZ0JBQWdCLENBQUMsRUFBRSxFQUFFLFNBQVMsRUFBRSx3QkFBd0IsQ0FBQyxDQUFDO0lBRTlFLHdEQUF3RDtJQUN4RCxNQUFNLE9BQU8sR0FBRyxNQUFNLEtBQUs7U0FDeEIsS0FBSyxFQUFFO1NBQ1AsS0FBSyxDQUFDLFNBQVMsRUFBRSxDQUFDLE9BQU8sQ0FBQyxJQUFJLEVBQUUsSUFBSSxDQUFDLEdBQUcsQ0FBQztTQUN6QyxLQUFLLENBQUMsQ0FBQyxDQUFDO1NBQ1IsT0FBTyxFQUFFLENBQUM7SUFFYixPQUFPLE9BQU8sQ0FBQyxNQUFNLEdBQUcsQ0FBQyxDQUFDLENBQUMsQ0FBQyxPQUFPLENBQUMsQ0FBQyxDQUFDLENBQUMsQ0FBQyxDQUFDLElBQUksQ0FBQztBQUNoRCxDQUFDO0FBRUQsOEVBQThFO0FBQzlFLHlEQUF5RDtBQUV6RCxNQUFNLENBQUMsS0FBSyxVQUFVLFlBQVksQ0FBQyxLQUFvQjtJQUNyRCxNQUFNLEVBQUUsR0FBRyxNQUFNLGVBQWUsRUFBRSxDQUFDO0lBQ25DLE1BQU0sZUFBZSxHQUFrQjtRQUNyQztZQUNFLEVBQUUsRUFBRSxFQUFFO1lBQ04sTUFBTSxFQUFFLEVBQUU7WUFDVixNQUFNLEVBQUUsRUFBRTtZQUNWLFVBQVUsRUFBRSxFQUFFO1lBQ2QsUUFBUSxFQUFFLEVBQUU7WUFDWixjQUFjLEVBQUUsRUFBRTtZQUNsQixhQUFhLEVBQUUsRUFBRTtZQUNqQixLQUFLLEVBQUUsRUFBRTtTQUNWO0tBQ0YsQ0FBQztJQUNGLE1BQU0sV0FBVyxDQUFDLEVBQUUsRUFBRSxnQkFBZ0IsRUFBRSxLQUFLLEVBQUUsZUFBZSxDQUFDLENBQUM7QUFDbEUsQ0FBQztBQUVELE1BQU0sQ0FBQyxLQUFLLFVBQVUsaUJBQWlCLENBQUMsR0FBYTtJQUNuRCxNQUFNLEVBQUUsR0FBRyxNQUFNLGVBQWUsRUFBRSxDQUFDO0lBQ25DLE1BQU0sZUFBZSxHQUFrQjtRQUNyQztZQUNFLEVBQUUsRUFBRSxFQUFFO1lBQ04sTUFBTSxFQUFFLEVBQUU7WUFDVixNQUFNLEVBQUUsRUFBRTtZQUNWLFVBQVUsRUFBRSxFQUFFO1lBQ2QsUUFBUSxFQUFFLEVBQUU7WUFDWixjQUFjLEVBQUUsRUFBRTtZQUNsQixhQUFhLEVBQUUsRUFBRTtZQUNqQixLQUFLLEVBQUUsRUFBRTtTQUNWO0tBQ0YsQ0FBQztJQUNGLE1BQU0sZ0JBQWdCLENBQUMsRUFBRSxFQUFFLGdCQUFnQixFQUFFLEdBQUcsRUFBRSxlQUFlLENBQUMsQ0FBQztBQUNyRSxDQUFDO0FBRUQsTUFBTSxDQUFDLEtBQUssVUFBVSxZQUFZLENBQ2hDLE1BQWdCLEVBQ2hCLEtBQWEsRUFDYixlQUF3QjtJQUV4QixNQUFNLEVBQUUsR0FBRyxNQUFNLGVBQWUsRUFBRSxDQUFDO0lBQ25DLE1BQU0sZUFBZSxHQUFrQjtRQUNyQztZQUNFLEVBQUUsRUFBRSxFQUFFO1lBQ04sTUFBTSxFQUFFLEVBQUU7WUFDVixNQUFNLEVBQUUsRUFBRTtZQUNWLFVBQVUsRUFBRSxFQUFFO1lBQ2QsUUFBUSxFQUFFLEVBQUU7WUFDWixjQUFjLEVBQUUsRUFBRTtZQUNsQixhQUFhLEVBQUUsRUFBRTtZQUNqQixLQUFLLEVBQUUsRUFBRTtTQUNWO0tBQ0YsQ0FBQztJQUNGLE9BQU8sQ0FBQyxNQUFNLG1CQUFtQixDQUMvQixFQUFFLEVBQ0YsZ0JBQWdCLEVBQ2hCLE1BQU0sRUFDTixLQUFLLEVBQ0wsZUFBZSxFQUNmLGVBQWUsQ0FDaEIsQ0FBa0IsQ0FBQztBQUN0QixDQUFDO0FBRUQsTUFBTSxDQUFDLEtBQUssVUFBVSxZQUFZLENBQUMsRUFBVTtJQUMzQyxNQUFNLEVBQUUsR0FBRyxNQUFNLGVBQWUsRUFBRSxDQUFDO0lBQ25DLE1BQU0sZUFBZSxHQUFrQjtRQUNyQztZQUNFLEVBQUUsRUFBRSxFQUFFO1lBQ04sTUFBTSxFQUFFLEVBQUU7WUFDVixNQUFNLEVBQUUsRUFBRTtZQUNWLFVBQVUsRUFBRSxFQUFFO1lBQ2QsUUFBUSxFQUFFLEVBQUU7WUFDWixjQUFjLEVBQUUsRUFBRTtZQUNsQixhQUFhLEVBQUUsRUFBRTtZQUNqQixLQUFLLEVBQUUsRUFBRTtTQUNWO0tBQ0YsQ0FBQztJQUNGLE9BQU8sQ0FBQyxNQUFNLFdBQVcsQ0FDdkIsRUFBRSxFQUNGLGdCQUFnQixFQUNoQixFQUFFLEVBQ0YsZUFBZSxDQUNoQixDQUF1QixDQUFDO0FBQzNCLENBQUM7QUFFRCw2QkFBNkI7QUFDN0IsTUFBTSxDQUFDLEtBQUssVUFBVSxvQkFBb0IsQ0FDeEMsS0FBNEI7SUFFNUIsTUFBTSxFQUFFLEdBQUcsTUFBTSxlQUFlLEVBQUUsQ0FBQztJQUNuQyxNQUFNLGtCQUFrQixHQUEwQjtRQUNoRDtZQUNFLEVBQUUsRUFBRSxFQUFFO1lBQ04sTUFBTSxFQUFFLEVBQUU7WUFDVixNQUFNLEVBQUUsRUFBRTtZQUNWLGlCQUFpQixFQUFFLEVBQUU7WUFDckIsVUFBVSxFQUFFLEVBQUU7U0FDZjtLQUNGLENBQUM7SUFDRixNQUFNLFdBQVcsQ0FBQyxFQUFFLEVBQUUsbUJBQW1CLEVBQUUsS0FBSyxFQUFFLGtCQUFrQixDQUFDLENBQUM7QUFDeEUsQ0FBQztBQUVELE1BQU0sQ0FBQyxLQUFLLFVBQVUseUJBQXlCLENBQUMsR0FBYTtJQUMzRCxNQUFNLEVBQUUsR0FBRyxNQUFNLGVBQWUsRUFBRSxDQUFDO0lBQ25DLE1BQU0sa0JBQWtCLEdBQTBCO1FBQ2hEO1lBQ0UsRUFBRSxFQUFFLEVBQUU7WUFDTixNQUFNLEVBQUUsRUFBRTtZQUNWLE1BQU0sRUFBRSxFQUFFO1lBQ1YsaUJBQWlCLEVBQUUsRUFBRTtZQUNyQixVQUFVLEVBQUUsRUFBRTtTQUNmO0tBQ0YsQ0FBQztJQUNGLE1BQU0sZ0JBQWdCLENBQUMsRUFBRSxFQUFFLG1CQUFtQixFQUFFLEdBQUcsRUFBRSxrQkFBa0IsQ0FBQyxDQUFDO0FBQzNFLENBQUM7QUFFRCxNQUFNLENBQUMsS0FBSyxVQUFVLG9CQUFvQixDQUN4QyxNQUFnQixFQUNoQixLQUFhLEVBQ2IsZUFBd0I7SUFFeEIsTUFBTSxFQUFFLEdBQUcsTUFBTSxlQUFlLEVBQUUsQ0FBQztJQUNuQyxNQUFNLGtCQUFrQixHQUEwQjtRQUNoRDtZQUNFLEVBQUUsRUFBRSxFQUFFO1lBQ04sTUFBTSxFQUFFLEVBQUU7WUFDVixNQUFNLEVBQUUsRUFBRTtZQUNWLGlCQUFpQixFQUFFLEVBQUU7WUFDckIsVUFBVSxFQUFFLEVBQUU7U0FDZjtLQUNGLENBQUM7SUFDRixPQUFPLENBQUMsTUFBTSxtQkFBbUIsQ0FDL0IsRUFBRSxFQUNGLG1CQUFtQixFQUNuQixNQUFNLEVBQ04sS0FBSyxFQUNMLGtCQUFrQixFQUNsQixlQUFlLENBQ2hCLENBQTBCLENBQUM7QUFDOUIsQ0FBQztBQUVELE1BQU0sQ0FBQyxLQUFLLFVBQVUsb0JBQW9CLENBQ3hDLEVBQVU7SUFFVixNQUFNLEVBQUUsR0FBRyxNQUFNLGVBQWUsRUFBRSxDQUFDO0lBQ25DLE1BQU0sa0JBQWtCLEdBQTBCO1FBQ2hEO1lBQ0UsRUFBRSxFQUFFLEVBQUU7WUFDTixNQUFNLEVBQUUsRUFBRTtZQUNWLE1BQU0sRUFBRSxFQUFFO1lBQ1YsaUJBQWlCLEVBQUUsRUFBRTtZQUNyQixVQUFVLEVBQUUsRUFBRTtTQUNmO0tBQ0YsQ0FBQztJQUNGLE9BQU8sQ0FBQyxNQUFNLFdBQVcsQ0FDdkIsRUFBRSxFQUNGLG1CQUFtQixFQUNuQixFQUFFLEVBQ0Ysa0JBQWtCLENBQ25CLENBQStCLENBQUM7QUFDbkMsQ0FBQztBQUVELDBEQUEwRDtBQUMxRCxNQUFNLENBQUMsS0FBSyxVQUFVLGlCQUFpQjtJQUNyQyxNQUFNLEVBQUUsR0FBRyxNQUFNLGVBQWUsRUFBRSxDQUFDO0lBQ25DLGdGQUFnRjtJQUNoRiwyQ0FBMkM7SUFDM0MsTUFBTSxlQUFlLEdBQWtCO1FBQ3JDO1lBQ0UsRUFBRSxFQUFFLEVBQUU7WUFDTixNQUFNLEVBQUUsRUFBRTtZQUNWLE1BQU0sRUFBRSxFQUFFO1lBQ1YsVUFBVSxFQUFFLEVBQUU7WUFDZCxRQUFRLEVBQUUsRUFBRTtZQUNaLGNBQWMsRUFBRSxFQUFFO1lBQ2xCLGFBQWEsRUFBRSxFQUFFO1lBQ2pCLEtBQUssRUFBRSxFQUFFO1NBQ1Y7S0FDRixDQUFDO0lBQ0YsT0FBTyxnQkFBZ0IsQ0FBQyxFQUFFLEVBQUUsZ0JBQWdCLEVBQUUsZUFBZSxDQUFDLENBQUM7QUFDakUsQ0FBQztBQUVELE1BQU0sQ0FBQyxLQUFLLFVBQVUsb0JBQW9CO0lBQ3hDLE1BQU0sRUFBRSxHQUFHLE1BQU0sZUFBZSxFQUFFLENBQUM7SUFDbkMsTUFBTSxrQkFBa0IsR0FBMEI7UUFDaEQ7WUFDRSxFQUFFLEVBQUUsRUFBRTtZQUNOLE1BQU0sRUFBRSxFQUFFO1lBQ1YsTUFBTSxFQUFFLEVBQUU7WUFDVixpQkFBaUIsRUFBRSxFQUFFO1lBQ3JCLFVBQVUsRUFBRSxFQUFFO1NBQ2Y7S0FDRixDQUFDO0lBQ0YsT0FBTyxnQkFBZ0IsQ0FBQyxFQUFFLEVBQUUsbUJBQW1CLEVBQUUsa0JBQWtCLENBQUMsQ0FBQztBQUN2RSxDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IHsgY29ubmVjdCwgQ29ubmVjdGlvbiwgVGFibGUgfSBmcm9tICdAbGFuY2VkYi9sYW5jZWRiJztcblxuLy8gRW52aXJvbm1lbnQgdmFyaWFibGUgZm9yIExhbmNlREIgcGF0aCBvciBhIGRlZmF1bHRcbmNvbnN0IExBTkNFREJfREFUQV9QQVRIID0gcHJvY2Vzcy5lbnYuTEFOQ0VEQl9VUkkgfHwgJy9kYXRhL2xhbmNlZGInO1xuY29uc3QgRVZFTlRfVEFCTEVfTkFNRSA9ICdldmVudHNfZGF0YSc7IC8vIEZvciBnZW5lcmFsIGV2ZW50IHNlYXJjaFxuY29uc3QgVFJBSU5JTkdfVEFCTEVfTkFNRSA9ICd0cmFpbmluZ19kYXRhJzsgLy8gRm9yIGZlYXR1cmVzLWFwcGx5LCBzY2hlZHVsZS1ldmVudCwgYW5kIF9jaGF0IHRyYWluaW5nXG5cbmxldCBkYkNvbm5lY3Rpb246IENvbm5lY3Rpb24gfCBudWxsID0gbnVsbDtcblxuLyoqXG4gKiBFc3RhYmxpc2hlcyBvciByZXR1cm5zIGFuIGV4aXN0aW5nIGNvbm5lY3Rpb24gdG8gTGFuY2VEQi5cbiAqL1xuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIGdldERCQ29ubmVjdGlvbigpOiBQcm9taXNlPENvbm5lY3Rpb24+IHtcbiAgaWYgKGRiQ29ubmVjdGlvbikge1xuICAgIHJldHVybiBkYkNvbm5lY3Rpb247XG4gIH1cbiAgdHJ5IHtcbiAgICBkYkNvbm5lY3Rpb24gPSBhd2FpdCBjb25uZWN0KExBTkNFREJfREFUQV9QQVRIKTtcbiAgICBjb25zb2xlLmxvZyhgU3VjY2Vzc2Z1bGx5IGNvbm5lY3RlZCB0byBMYW5jZURCIGF0ICR7TEFOQ0VEQl9EQVRBX1BBVEh9YCk7XG4gICAgcmV0dXJuIGRiQ29ubmVjdGlvbjtcbiAgfSBjYXRjaCAoZXJyb3IpIHtcbiAgICBjb25zb2xlLmVycm9yKFxuICAgICAgYEZhaWxlZCB0byBjb25uZWN0IHRvIExhbmNlREIgYXQgJHtMQU5DRURCX0RBVEFfUEFUSH06YCxcbiAgICAgIGVycm9yXG4gICAgKTtcbiAgICBkYkNvbm5lY3Rpb24gPSBudWxsOyAvLyBSZXNldCBvbiBmYWlsdXJlIHRvIGFsbG93IHJldHJ5XG4gICAgdGhyb3cgZXJyb3I7XG4gIH1cbn1cblxuLy8gU2NoZW1hIERlZmluaXRpb25zXG5cbi8vIEZvciBnZW5lcmFsIGV2ZW50IGRhdGEsIHVzZWQgYnkgX2NoYXQgKGV2ZW50IHNlYXJjaCkgYW5kIGFzIGEgc291cmNlIGZvciB2ZWN0b3JzLlxuZXhwb3J0IGludGVyZmFjZSBFdmVudFNjaGVtYSB7XG4gIGlkOiBzdHJpbmc7IC8vIFByaW1hcnkgS2V5OiBvcmlnaW5hbCBldmVudElkIGZyb20gdGhlIHNvdXJjZSBzeXN0ZW0gKGUuZy4sIGdvb2dsZUV2ZW50SWQpXG4gIHVzZXJJZDogc3RyaW5nO1xuICB2ZWN0b3I6IG51bWJlcltdOyAvLyBPcGVuQUkgdGV4dC1lbWJlZGRpbmctMy1zbWFsbCBkaW1lbnNpb246IDE1MzZcbiAgc3RhcnRfZGF0ZTogc3RyaW5nOyAvLyBJU08gODYwMSBmb3JtYXRcbiAgZW5kX2RhdGU6IHN0cmluZzsgLy8gSVNPIDg2MDEgZm9ybWF0XG4gIHJhd19ldmVudF90ZXh0OiBzdHJpbmc7IC8vIENvbmNhdGVuYXRpb24gb2Ygc3VtbWFyeSwgZGVzY3JpcHRpb24sIGV0Yy5cbiAgY2FsZW5kYXJJZD86IHN0cmluZzsgLy8gT3B0aW9uYWw6IGNhbGVuZGFySWQgaWYgZXZlbnRzIGNhbiBzcGFuIG11bHRpcGxlIGNhbGVuZGFycyBmb3IgYSB1c2VyXG4gIGxhc3RfbW9kaWZpZWQ6IHN0cmluZzsgLy8gSVNPIDg2MDEgZm9ybWF0LCB3aGVuIHRoaXMgcmVjb3JkIHdhcyBsYXN0IHVwZGF0ZWRcbiAgLy8gQWRkIG90aGVyIGZpbHRlcmFibGUvcmV0cmlldmFibGUgZmllbGRzIGFzIG5lZWRlZCBieSBfY2hhdCBzZWFyY2hcbiAgdGl0bGU/OiBzdHJpbmc7XG4gIGxvY2F0aW9uPzogc3RyaW5nO1xufVxuXG4vLyBGb3IgdHJhaW5pbmcgZGF0YSwgdXNlZCBieSBmZWF0dXJlcy1hcHBseSwgc2NoZWR1bGUtZXZlbnQsIGFuZCBfY2hhdCAodHJhaW5pbmcgcGFydClcbmV4cG9ydCBpbnRlcmZhY2UgVHJhaW5pbmdFdmVudFNjaGVtYSB7XG4gIGlkOiBzdHJpbmc7IC8vIFByaW1hcnkgS2V5OiB1c3VhbGx5IHRoZSBJRCBvZiB0aGUgZXZlbnQgd2hvc2UgcHJvcGVydGllcyBhcmUgYmVpbmcgbGVhcm5lZC9zdG9yZWRcbiAgdXNlcklkOiBzdHJpbmc7XG4gIHZlY3RvcjogbnVtYmVyW107IC8vIFZlY3RvciBkZXJpdmVkIGZyb20gc291cmNlX2V2ZW50X3RleHRcbiAgc291cmNlX2V2ZW50X3RleHQ6IHN0cmluZzsgLy8gVGV4dCB1c2VkIHRvIGdlbmVyYXRlIHRoZSB2ZWN0b3IgKGUuZy4sIHRpdGxlOmRlc2NyaXB0aW9uKVxuICAvLyBTdG9yZSBsZWFybmVkIHByb3BlcnRpZXMgZGlyZWN0bHkgb3IgbGluayB0byB0aGVtIGlmIHRoZXkgYXJlIGNvbXBsZXguXG4gIC8vIEV4YW1wbGU6XG4gIC8vIGNhdGVnb3J5X25hbWU/OiBzdHJpbmc7XG4gIC8vIHJlbWluZGVyX3NldHRpbmdfbWludXRlcz86IG51bWJlcltdO1xuICBjcmVhdGVkX2F0OiBzdHJpbmc7IC8vIElTTyA4NjAxIGZvcm1hdFxufVxuXG4vKipcbiAqIE9wZW5zIGFuIGV4aXN0aW5nIHRhYmxlIG9yIGNyZWF0ZXMgaXQgaWYgaXQgZG9lc24ndCBleGlzdC5cbiAqIExhbmNlREIgcmVxdWlyZXMgc2FtcGxlIGRhdGEgKGV2ZW4gaWYgZW1wdHkgYnV0IHR5cGVkKSBvciBhbiBleHBsaWNpdCBzY2hlbWEgZm9yIGNyZWF0aW9uLFxuICogZXNwZWNpYWxseSBmb3IgdmVjdG9yIGNvbHVtbnMgYW5kIHRoZWlyIGluZGV4aW5nLlxuICogQHBhcmFtIGRiIFRoZSBMYW5jZURCIGNvbm5lY3Rpb24gb2JqZWN0LlxuICogQHBhcmFtIHRhYmxlTmFtZSBUaGUgbmFtZSBvZiB0aGUgdGFibGUgdG8gZ2V0IG9yIGNyZWF0ZS5cbiAqIEBwYXJhbSBzYW1wbGVEYXRhIFNhbXBsZSBkYXRhIChjYW4gYmUgYW4gZW1wdHkgdHlwZWQgYXJyYXkpIHRvIGhlbHAgaW5mZXIgc2NoZW1hIG9uIGNyZWF0aW9uLlxuICogICAgICAgICAgICAgICAgICAgSXQncyBjcnVjaWFsIHRoaXMgc2FtcGxlIGRhdGEgKG9yIG9uZSBpdGVtIGluIGl0KSBjb250YWlucyBhbGwgZmllbGRzLFxuICogICAgICAgICAgICAgICAgICAgZXNwZWNpYWxseSB2ZWN0b3IgZmllbGRzLCBmb3IgY29ycmVjdCBzY2hlbWEgc2V0dXAuXG4gKi9cbmV4cG9ydCBhc3luYyBmdW5jdGlvbiBnZXRPckNyZWF0ZVRhYmxlKFxuICBkYjogQ29ubmVjdGlvbixcbiAgdGFibGVOYW1lOiBzdHJpbmcsXG4gIC8vIFByb3ZpZGUgYSByZXByZXNlbnRhdGl2ZSBlbXB0eSBpdGVtIGZvciBzY2hlbWEgaW5mZXJlbmNlLCBlc3BlY2lhbGx5IGZvciB2ZWN0b3IgdHlwZXMuXG4gIC8vIGUuZy4sIHsgaWQ6IFwiXCIsIHZlY3RvcjogW10sIC4uLm90aGVyX2ZpZWxkc193aXRoX2RlZmF1bHRfdmFsdWVzIH1cbiAgcmVwcmVzZW50YXRpdmVEYXRhOiBhbnlbXVxuKTogUHJvbWlzZTxUYWJsZT4ge1xuICB0cnkge1xuICAgIGNvbnN0IHRhYmxlID0gYXdhaXQgZGIub3BlblRhYmxlKHRhYmxlTmFtZSk7XG4gICAgY29uc29sZS5sb2coYFRhYmxlIFwiJHt0YWJsZU5hbWV9XCIgb3BlbmVkIHN1Y2Nlc3NmdWxseS5gKTtcbiAgICByZXR1cm4gdGFibGU7XG4gIH0gY2F0Y2ggKGVycm9yKSB7XG4gICAgLy8gQmFzaWMgZXJyb3IgY2hlY2s7IG1vcmUgc3BlY2lmaWMgY2hlY2tzIGZvciBcInRhYmxlIG5vdCBmb3VuZFwiIG1pZ2h0IGJlIG5lZWRlZC5cbiAgICBjb25zb2xlLmxvZyhgVGFibGUgXCIke3RhYmxlTmFtZX1cIiBub3QgZm91bmQsIGF0dGVtcHRpbmcgdG8gY3JlYXRlIGl0LmApO1xuICAgIHRyeSB7XG4gICAgICAvLyBDcmVhdGUgdGFibGUgd2l0aCByZXByZXNlbnRhdGl2ZSBkYXRhIHRvIGRlZmluZSBzY2hlbWEuXG4gICAgICAvLyBFbnN1cmUgdGhlIHJlcHJlc2VudGF0aXZlRGF0YSBpbmNsdWRlcyBhIHZlY3RvciBmaWVsZCBpZiB0aGUgc2NoZW1hIHJlcXVpcmVzIG9uZS5cbiAgICAgIGNvbnN0IHRhYmxlID0gYXdhaXQgZGIuY3JlYXRlVGFibGUodGFibGVOYW1lLCByZXByZXNlbnRhdGl2ZURhdGEpO1xuICAgICAgY29uc29sZS5sb2coXG4gICAgICAgIGBUYWJsZSBcIiR7dGFibGVOYW1lfVwiIGNyZWF0ZWQgc3VjY2Vzc2Z1bGx5IHdpdGggaW5mZXJyZWQgc2NoZW1hLmBcbiAgICAgICk7XG4gICAgICByZXR1cm4gdGFibGU7XG4gICAgfSBjYXRjaCAoY3JlYXRpb25FcnJvcikge1xuICAgICAgY29uc29sZS5lcnJvcihgRmFpbGVkIHRvIGNyZWF0ZSB0YWJsZSBcIiR7dGFibGVOYW1lfVwiOmAsIGNyZWF0aW9uRXJyb3IpO1xuICAgICAgdGhyb3cgY3JlYXRpb25FcnJvcjtcbiAgICB9XG4gIH1cbn1cblxuLyoqXG4gKiBVcHNlcnRzIGl0ZW1zIGludG8gdGhlIHNwZWNpZmllZCBMYW5jZURCIHRhYmxlLlxuICogVGhpcyBpbXBsZW1lbnRhdGlvbiBhc3N1bWVzIGFuIFwidXBzZXJ0XCIgaXMgYSBkZWxldGUgZm9sbG93ZWQgYnkgYW4gYWRkLlxuICogUmVxdWlyZXMgaXRlbXMgdG8gaGF2ZSBhbiAnaWQnIGZpZWxkLlxuICogQHBhcmFtIHRhYmxlTmFtZSBUaGUgbmFtZSBvZiB0aGUgdGFibGUuXG4gKiBAcGFyYW0gaXRlbXMgQW4gYXJyYXkgb2YgaXRlbXMgdG8gdXBzZXJ0LiBFYWNoIGl0ZW0gbXVzdCBoYXZlIGFuICdpZCcgcHJvcGVydHkuXG4gKiBAcGFyYW0gcmVwcmVzZW50YXRpdmVJdGVtIFNhbXBsZSBkYXRhIChjYW4gYmUgYW4gZW1wdHkgdHlwZWQgYXJyYXkgd2l0aCBvbmUgaXRlbSkgdG8gaGVscCBpbmZlciBzY2hlbWEgb24gY3JlYXRpb24uXG4gKi9cbmV4cG9ydCBhc3luYyBmdW5jdGlvbiB1cHNlcnRJdGVtcyhcbiAgZGI6IENvbm5lY3Rpb24sIC8vIFBhc3MgY29ubmVjdGlvbiB0byBhdm9pZCByZXBlYXRlZCBjYWxscyB0byBnZXREQkNvbm5lY3Rpb25cbiAgdGFibGVOYW1lOiBzdHJpbmcsXG4gIGl0ZW1zOiBhbnlbXSxcbiAgcmVwcmVzZW50YXRpdmVJdGVtU2NoZW1hOiBhbnlbXSAvLyBVc2VkIGlmIHRhYmxlIG5lZWRzIHRvIGJlIGNyZWF0ZWRcbik6IFByb21pc2U8dm9pZD4ge1xuICBpZiAoIWl0ZW1zIHx8IGl0ZW1zLmxlbmd0aCA9PT0gMCkge1xuICAgIGNvbnNvbGUubG9nKGBObyBpdGVtcyBwcm92aWRlZCBmb3IgdXBzZXJ0IGluIHRhYmxlIFwiJHt0YWJsZU5hbWV9XCIuYCk7XG4gICAgcmV0dXJuO1xuICB9XG4gIGNvbnN0IHRhYmxlID0gYXdhaXQgZ2V0T3JDcmVhdGVUYWJsZShkYiwgdGFibGVOYW1lLCByZXByZXNlbnRhdGl2ZUl0ZW1TY2hlbWEpO1xuXG4gIC8vIEV4dHJhY3QgSURzIGZvciBkZWxldGlvblxuICBjb25zdCBpZHMgPSBpdGVtcy5tYXAoKGl0ZW0pID0+IGl0ZW0uaWQpO1xuICBpZiAoaWRzLmxlbmd0aCA+IDApIHtcbiAgICBjb25zdCBkZWxldGVRdWVyeSA9IGBpZCBJTiAoJHtpZHMubWFwKChpZCkgPT4gYCcke2lkLnJlcGxhY2UoLycvZywgXCInJ1wiKX0nYCkuam9pbignLCcpfSlgO1xuICAgIHRyeSB7XG4gICAgICBhd2FpdCB0YWJsZS5kZWxldGUoZGVsZXRlUXVlcnkpO1xuICAgICAgY29uc29sZS5sb2coXG4gICAgICAgIGBTdWNjZXNzZnVsbHkgcHJlLWRlbGV0ZWQgZXhpc3RpbmcgaXRlbXMgZm9yIHVwc2VydCBpbiBcIiR7dGFibGVOYW1lfVwiIGZvciBJRHM6ICR7aWRzLmpvaW4oJywgJyl9YFxuICAgICAgKTtcbiAgICB9IGNhdGNoIChkZWxldGVFcnJvcikge1xuICAgICAgLy8gSXQncyBvZnRlbiBva2F5IGlmIGRlbGV0ZSBmYWlscyBiZWNhdXNlIGl0ZW1zIGRvbid0IGV4aXN0IHlldC5cbiAgICAgIGNvbnNvbGUud2FybihcbiAgICAgICAgYFdhcm5pbmcgb3IgZXJyb3IgZHVyaW5nIHByZS1kZWxldGUgZm9yIHVwc2VydCBpbiBcIiR7dGFibGVOYW1lfVwiIChzb21lIElEcyBtaWdodCBub3QgZXhpc3QpOmAsXG4gICAgICAgIGRlbGV0ZUVycm9yLm1lc3NhZ2VcbiAgICAgICk7XG4gICAgfVxuICB9XG5cbiAgdHJ5IHtcbiAgICBhd2FpdCB0YWJsZS5hZGQoaXRlbXMpO1xuICAgIGNvbnNvbGUubG9nKFxuICAgICAgYFN1Y2Nlc3NmdWxseSBhZGRlZC91cGRhdGVkICR7aXRlbXMubGVuZ3RofSBpdGVtcyBpbiB0YWJsZSBcIiR7dGFibGVOYW1lfVwiLmBcbiAgICApO1xuICB9IGNhdGNoIChlcnJvcikge1xuICAgIGNvbnNvbGUuZXJyb3IoXG4gICAgICBgRXJyb3IgZHVyaW5nIGJ1bGsgYWRkIGZvciB1cHNlcnQgaW4gdGFibGUgXCIke3RhYmxlTmFtZX1cIjpgLFxuICAgICAgZXJyb3JcbiAgICApO1xuICAgIHRocm93IGVycm9yO1xuICB9XG59XG5cbi8qKlxuICogRGVsZXRlcyBpdGVtcyBmcm9tIHRoZSBzcGVjaWZpZWQgTGFuY2VEQiB0YWJsZSBieSB0aGVpciBJRHMuXG4gKiBAcGFyYW0gdGFibGVOYW1lIFRoZSBuYW1lIG9mIHRoZSB0YWJsZS5cbiAqIEBwYXJhbSBpZHMgQW4gYXJyYXkgb2Ygc3RyaW5nIElEcyB0byBkZWxldGUuXG4gKiBAcGFyYW0gcmVwcmVzZW50YXRpdmVJdGVtU2NoZW1hIFNhbXBsZSBkYXRhIHVzZWQgaWYgdGFibGUgbmVlZHMgdG8gYmUgXCJvcGVuZWRcIiBmaXJzdCAodGhvdWdoIGRlbGV0ZSB1c3VhbGx5IGltcGxpZXMgdGFibGUgZXhpc3RzKS5cbiAqL1xuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIGRlbGV0ZUl0ZW1zQnlJZHMoXG4gIGRiOiBDb25uZWN0aW9uLFxuICB0YWJsZU5hbWU6IHN0cmluZyxcbiAgaWRzOiBzdHJpbmdbXSxcbiAgcmVwcmVzZW50YXRpdmVJdGVtU2NoZW1hOiBhbnlbXVxuKTogUHJvbWlzZTx2b2lkPiB7XG4gIGlmICghaWRzIHx8IGlkcy5sZW5ndGggPT09IDApIHtcbiAgICBjb25zb2xlLmxvZyhgTm8gSURzIHByb3ZpZGVkIGZvciBkZWxldGlvbiBpbiB0YWJsZSBcIiR7dGFibGVOYW1lfVwiLmApO1xuICAgIHJldHVybjtcbiAgfVxuICAvLyBFbnN1cmUgdGFibGUgaXMgYWNjZXNzaWJsZTsgY3JlYXRpb24gbG9naWMgbWlnaHQgbm90IGJlIHN0cmljdGx5IG5lY2Vzc2FyeSBmb3IgZGVsZXRlXG4gIC8vIGJ1dCBnZXRPckNyZWF0ZVRhYmxlIGhhbmRsZXMgb3BlbmluZyBpdC5cbiAgY29uc3QgdGFibGUgPSBhd2FpdCBnZXRPckNyZWF0ZVRhYmxlKGRiLCB0YWJsZU5hbWUsIHJlcHJlc2VudGF0aXZlSXRlbVNjaGVtYSk7XG5cbiAgY29uc3QgZGVsZXRlUXVlcnkgPSBgaWQgSU4gKCR7aWRzLm1hcCgoaWQpID0+IGAnJHtpZC5yZXBsYWNlKC8nL2csIFwiJydcIil9J2ApLmpvaW4oJywnKX0pYDtcbiAgdHJ5IHtcbiAgICBhd2FpdCB0YWJsZS5kZWxldGUoZGVsZXRlUXVlcnkpO1xuICAgIGNvbnNvbGUubG9nKFxuICAgICAgYFN1Y2Nlc3NmdWxseSBkZWxldGVkIGl0ZW1zIGZyb20gXCIke3RhYmxlTmFtZX1cIiBmb3IgSURzOiAke2lkcy5qb2luKCcsICcpfWBcbiAgICApO1xuICB9IGNhdGNoIChlcnJvcikge1xuICAgIGNvbnNvbGUuZXJyb3IoYEVycm9yIGR1cmluZyBidWxrIGRlbGV0ZSBmcm9tIHRhYmxlIFwiJHt0YWJsZU5hbWV9XCI6YCwgZXJyb3IpO1xuICAgIHRocm93IGVycm9yO1xuICB9XG59XG5cbi8qKlxuICogU2VhcmNoZXMgYSBMYW5jZURCIHRhYmxlIGJ5IGEgdmVjdG9yLCB3aXRoIG9wdGlvbmFsIGZpbHRlcmluZy5cbiAqIEBwYXJhbSB0YWJsZU5hbWUgVGhlIG5hbWUgb2YgdGhlIHRhYmxlIHRvIHNlYXJjaC5cbiAqIEBwYXJhbSB2ZWN0b3IgVGhlIHNlYXJjaCB2ZWN0b3IuXG4gKiBAcGFyYW0gbGltaXQgVGhlIG1heGltdW0gbnVtYmVyIG9mIHJlc3VsdHMgdG8gcmV0dXJuLlxuICogQHBhcmFtIHJlcHJlc2VudGF0aXZlSXRlbVNjaGVtYSBTYW1wbGUgZGF0YSBmb3IgdGFibGUgc2NoZW1hLlxuICogQHBhcmFtIGZpbHRlckNvbmRpdGlvbiBPcHRpb25hbCBTUUwtbGlrZSBmaWx0ZXIgY29uZGl0aW9uIHN0cmluZyAoZS5nLiwgXCJ1c2VySWQgPSAnMTIzJyBBTkQgcHJpY2UgPiA1MFwiKS5cbiAqICAgICAgICAgICAgICAgICAgICAgICAgRW5zdXJlIGNvbHVtbiBuYW1lcyBhbmQgdmFsdWVzIGFyZSBjb3JyZWN0bHkgcXVvdGVkL2Zvcm1hdHRlZCBmb3IgU1FMLlxuICovXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gc2VhcmNoVGFibGVCeVZlY3RvcihcbiAgZGI6IENvbm5lY3Rpb24sXG4gIHRhYmxlTmFtZTogc3RyaW5nLFxuICB2ZWN0b3I6IG51bWJlcltdLFxuICBsaW1pdDogbnVtYmVyLFxuICByZXByZXNlbnRhdGl2ZUl0ZW1TY2hlbWE6IGFueVtdLFxuICBmaWx0ZXJDb25kaXRpb24/OiBzdHJpbmdcbik6IFByb21pc2U8YW55W10+IHtcbiAgaWYgKCF2ZWN0b3IgfHwgdmVjdG9yLmxlbmd0aCA9PT0gMCkge1xuICAgIHRocm93IG5ldyBFcnJvcignU2VhcmNoIHZlY3RvciBtdXN0IGJlIHByb3ZpZGVkLicpO1xuICB9XG4gIGNvbnN0IHRhYmxlID0gYXdhaXQgZ2V0T3JDcmVhdGVUYWJsZShkYiwgdGFibGVOYW1lLCByZXByZXNlbnRhdGl2ZUl0ZW1TY2hlbWEpO1xuICBsZXQgcXVlcnkgPSB0YWJsZS5zZWFyY2godmVjdG9yKTtcblxuICBpZiAoZmlsdGVyQ29uZGl0aW9uICYmIGZpbHRlckNvbmRpdGlvbi50cmltKCkgIT09ICcnKSB7XG4gICAgcXVlcnkgPSBxdWVyeS53aGVyZShmaWx0ZXJDb25kaXRpb24pO1xuICB9XG5cbiAgcXVlcnkgPSBxdWVyeS5saW1pdChsaW1pdCk7XG5cbiAgdHJ5IHtcbiAgICBjb25zdCByZXN1bHRzID0gYXdhaXQgcXVlcnkudG9BcnJheSgpO1xuICAgIHJldHVybiByZXN1bHRzO1xuICB9IGNhdGNoIChlcnJvcikge1xuICAgIGNvbnNvbGUuZXJyb3IoYEVycm9yIHNlYXJjaGluZyB0YWJsZSBcIiR7dGFibGVOYW1lfVwiIGJ5IHZlY3RvcjpgLCBlcnJvcik7XG4gICAgdGhyb3cgZXJyb3I7XG4gIH1cbn1cblxuLyoqXG4gKiBSZXRyaWV2ZXMgYSBzaW5nbGUgaXRlbSBmcm9tIHRoZSBzcGVjaWZpZWQgTGFuY2VEQiB0YWJsZSBieSBpdHMgSUQuXG4gKiBAcGFyYW0gdGFibGVOYW1lIFRoZSBuYW1lIG9mIHRoZSB0YWJsZS5cbiAqIEBwYXJhbSBpZCBUaGUgSUQgb2YgdGhlIGl0ZW0gdG8gcmV0cmlldmUuXG4gKiBAcGFyYW0gcmVwcmVzZW50YXRpdmVJdGVtU2NoZW1hIFNhbXBsZSBkYXRhIGZvciB0YWJsZSBzY2hlbWEuXG4gKiBAcmV0dXJucyBUaGUgaXRlbSBpZiBmb3VuZCwgb3RoZXJ3aXNlIG51bGwuXG4gKi9cbmV4cG9ydCBhc3luYyBmdW5jdGlvbiBnZXRJdGVtQnlJZChcbiAgZGI6IENvbm5lY3Rpb24sXG4gIHRhYmxlTmFtZTogc3RyaW5nLFxuICBpZDogc3RyaW5nLFxuICByZXByZXNlbnRhdGl2ZUl0ZW1TY2hlbWE6IGFueVtdXG4pOiBQcm9taXNlPGFueSB8IG51bGw+IHtcbiAgaWYgKCFpZCkge1xuICAgIHRocm93IG5ldyBFcnJvcignSUQgbXVzdCBiZSBwcm92aWRlZCB0byBnZXQgYW4gaXRlbS4nKTtcbiAgfVxuICBjb25zdCB0YWJsZSA9IGF3YWl0IGdldE9yQ3JlYXRlVGFibGUoZGIsIHRhYmxlTmFtZSwgcmVwcmVzZW50YXRpdmVJdGVtU2NoZW1hKTtcblxuICAvLyBMYW5jZURCJ3MgcXVlcnkgZm9yIHNwZWNpZmljIElEIG1pZ2h0IGJlIGBpZCA9ICcuLi4nYFxuICBjb25zdCByZXN1bHRzID0gYXdhaXQgdGFibGVcbiAgICAucXVlcnkoKVxuICAgIC53aGVyZShgaWQgPSAnJHtpZC5yZXBsYWNlKC8nL2csIFwiJydcIil9J2ApXG4gICAgLmxpbWl0KDEpXG4gICAgLnRvQXJyYXkoKTtcblxuICByZXR1cm4gcmVzdWx0cy5sZW5ndGggPiAwID8gcmVzdWx0c1swXSA6IG51bGw7XG59XG5cbi8vIFVwZGF0ZSBnZXRFdmVudERhdGFUYWJsZSBhbmQgZ2V0VHJhaW5pbmdEYXRhVGFibGUgdG8gcGFzcyB0aGUgZGIgY29ubmVjdGlvblxuLy8gYW5kIHJlcHJlc2VudGF0aXZlIGRhdGEgdG8gdGhlIGdlbmVyaWMgQ1JVRCBmdW5jdGlvbnMuXG5cbmV4cG9ydCBhc3luYyBmdW5jdGlvbiB1cHNlcnRFdmVudHMoaXRlbXM6IEV2ZW50U2NoZW1hW10pOiBQcm9taXNlPHZvaWQ+IHtcbiAgY29uc3QgZGIgPSBhd2FpdCBnZXREQkNvbm5lY3Rpb24oKTtcbiAgY29uc3Qgc2FtcGxlRXZlbnREYXRhOiBFdmVudFNjaGVtYVtdID0gW1xuICAgIHtcbiAgICAgIGlkOiAnJyxcbiAgICAgIHVzZXJJZDogJycsXG4gICAgICB2ZWN0b3I6IFtdLFxuICAgICAgc3RhcnRfZGF0ZTogJycsXG4gICAgICBlbmRfZGF0ZTogJycsXG4gICAgICByYXdfZXZlbnRfdGV4dDogJycsXG4gICAgICBsYXN0X21vZGlmaWVkOiAnJyxcbiAgICAgIHRpdGxlOiAnJyxcbiAgICB9LFxuICBdO1xuICBhd2FpdCB1cHNlcnRJdGVtcyhkYiwgRVZFTlRfVEFCTEVfTkFNRSwgaXRlbXMsIHNhbXBsZUV2ZW50RGF0YSk7XG59XG5cbmV4cG9ydCBhc3luYyBmdW5jdGlvbiBkZWxldGVFdmVudHNCeUlkcyhpZHM6IHN0cmluZ1tdKTogUHJvbWlzZTx2b2lkPiB7XG4gIGNvbnN0IGRiID0gYXdhaXQgZ2V0REJDb25uZWN0aW9uKCk7XG4gIGNvbnN0IHNhbXBsZUV2ZW50RGF0YTogRXZlbnRTY2hlbWFbXSA9IFtcbiAgICB7XG4gICAgICBpZDogJycsXG4gICAgICB1c2VySWQ6ICcnLFxuICAgICAgdmVjdG9yOiBbXSxcbiAgICAgIHN0YXJ0X2RhdGU6ICcnLFxuICAgICAgZW5kX2RhdGU6ICcnLFxuICAgICAgcmF3X2V2ZW50X3RleHQ6ICcnLFxuICAgICAgbGFzdF9tb2RpZmllZDogJycsXG4gICAgICB0aXRsZTogJycsXG4gICAgfSxcbiAgXTtcbiAgYXdhaXQgZGVsZXRlSXRlbXNCeUlkcyhkYiwgRVZFTlRfVEFCTEVfTkFNRSwgaWRzLCBzYW1wbGVFdmVudERhdGEpO1xufVxuXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gc2VhcmNoRXZlbnRzKFxuICB2ZWN0b3I6IG51bWJlcltdLFxuICBsaW1pdDogbnVtYmVyLFxuICBmaWx0ZXJDb25kaXRpb24/OiBzdHJpbmdcbik6IFByb21pc2U8RXZlbnRTY2hlbWFbXT4ge1xuICBjb25zdCBkYiA9IGF3YWl0IGdldERCQ29ubmVjdGlvbigpO1xuICBjb25zdCBzYW1wbGVFdmVudERhdGE6IEV2ZW50U2NoZW1hW10gPSBbXG4gICAge1xuICAgICAgaWQ6ICcnLFxuICAgICAgdXNlcklkOiAnJyxcbiAgICAgIHZlY3RvcjogW10sXG4gICAgICBzdGFydF9kYXRlOiAnJyxcbiAgICAgIGVuZF9kYXRlOiAnJyxcbiAgICAgIHJhd19ldmVudF90ZXh0OiAnJyxcbiAgICAgIGxhc3RfbW9kaWZpZWQ6ICcnLFxuICAgICAgdGl0bGU6ICcnLFxuICAgIH0sXG4gIF07XG4gIHJldHVybiAoYXdhaXQgc2VhcmNoVGFibGVCeVZlY3RvcihcbiAgICBkYixcbiAgICBFVkVOVF9UQUJMRV9OQU1FLFxuICAgIHZlY3RvcixcbiAgICBsaW1pdCxcbiAgICBzYW1wbGVFdmVudERhdGEsXG4gICAgZmlsdGVyQ29uZGl0aW9uXG4gICkpIGFzIEV2ZW50U2NoZW1hW107XG59XG5cbmV4cG9ydCBhc3luYyBmdW5jdGlvbiBnZXRFdmVudEJ5SWQoaWQ6IHN0cmluZyk6IFByb21pc2U8RXZlbnRTY2hlbWEgfCBudWxsPiB7XG4gIGNvbnN0IGRiID0gYXdhaXQgZ2V0REJDb25uZWN0aW9uKCk7XG4gIGNvbnN0IHNhbXBsZUV2ZW50RGF0YTogRXZlbnRTY2hlbWFbXSA9IFtcbiAgICB7XG4gICAgICBpZDogJycsXG4gICAgICB1c2VySWQ6ICcnLFxuICAgICAgdmVjdG9yOiBbXSxcbiAgICAgIHN0YXJ0X2RhdGU6ICcnLFxuICAgICAgZW5kX2RhdGU6ICcnLFxuICAgICAgcmF3X2V2ZW50X3RleHQ6ICcnLFxuICAgICAgbGFzdF9tb2RpZmllZDogJycsXG4gICAgICB0aXRsZTogJycsXG4gICAgfSxcbiAgXTtcbiAgcmV0dXJuIChhd2FpdCBnZXRJdGVtQnlJZChcbiAgICBkYixcbiAgICBFVkVOVF9UQUJMRV9OQU1FLFxuICAgIGlkLFxuICAgIHNhbXBsZUV2ZW50RGF0YVxuICApKSBhcyBFdmVudFNjaGVtYSB8IG51bGw7XG59XG5cbi8vIFNpbWlsYXJseSBmb3IgVHJhaW5pbmdEYXRhXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gdXBzZXJ0VHJhaW5pbmdFdmVudHMoXG4gIGl0ZW1zOiBUcmFpbmluZ0V2ZW50U2NoZW1hW11cbik6IFByb21pc2U8dm9pZD4ge1xuICBjb25zdCBkYiA9IGF3YWl0IGdldERCQ29ubmVjdGlvbigpO1xuICBjb25zdCBzYW1wbGVUcmFpbmluZ0RhdGE6IFRyYWluaW5nRXZlbnRTY2hlbWFbXSA9IFtcbiAgICB7XG4gICAgICBpZDogJycsXG4gICAgICB1c2VySWQ6ICcnLFxuICAgICAgdmVjdG9yOiBbXSxcbiAgICAgIHNvdXJjZV9ldmVudF90ZXh0OiAnJyxcbiAgICAgIGNyZWF0ZWRfYXQ6ICcnLFxuICAgIH0sXG4gIF07XG4gIGF3YWl0IHVwc2VydEl0ZW1zKGRiLCBUUkFJTklOR19UQUJMRV9OQU1FLCBpdGVtcywgc2FtcGxlVHJhaW5pbmdEYXRhKTtcbn1cblxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIGRlbGV0ZVRyYWluaW5nRXZlbnRzQnlJZHMoaWRzOiBzdHJpbmdbXSk6IFByb21pc2U8dm9pZD4ge1xuICBjb25zdCBkYiA9IGF3YWl0IGdldERCQ29ubmVjdGlvbigpO1xuICBjb25zdCBzYW1wbGVUcmFpbmluZ0RhdGE6IFRyYWluaW5nRXZlbnRTY2hlbWFbXSA9IFtcbiAgICB7XG4gICAgICBpZDogJycsXG4gICAgICB1c2VySWQ6ICcnLFxuICAgICAgdmVjdG9yOiBbXSxcbiAgICAgIHNvdXJjZV9ldmVudF90ZXh0OiAnJyxcbiAgICAgIGNyZWF0ZWRfYXQ6ICcnLFxuICAgIH0sXG4gIF07XG4gIGF3YWl0IGRlbGV0ZUl0ZW1zQnlJZHMoZGIsIFRSQUlOSU5HX1RBQkxFX05BTUUsIGlkcywgc2FtcGxlVHJhaW5pbmdEYXRhKTtcbn1cblxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIHNlYXJjaFRyYWluaW5nRXZlbnRzKFxuICB2ZWN0b3I6IG51bWJlcltdLFxuICBsaW1pdDogbnVtYmVyLFxuICBmaWx0ZXJDb25kaXRpb24/OiBzdHJpbmdcbik6IFByb21pc2U8VHJhaW5pbmdFdmVudFNjaGVtYVtdPiB7XG4gIGNvbnN0IGRiID0gYXdhaXQgZ2V0REJDb25uZWN0aW9uKCk7XG4gIGNvbnN0IHNhbXBsZVRyYWluaW5nRGF0YTogVHJhaW5pbmdFdmVudFNjaGVtYVtdID0gW1xuICAgIHtcbiAgICAgIGlkOiAnJyxcbiAgICAgIHVzZXJJZDogJycsXG4gICAgICB2ZWN0b3I6IFtdLFxuICAgICAgc291cmNlX2V2ZW50X3RleHQ6ICcnLFxuICAgICAgY3JlYXRlZF9hdDogJycsXG4gICAgfSxcbiAgXTtcbiAgcmV0dXJuIChhd2FpdCBzZWFyY2hUYWJsZUJ5VmVjdG9yKFxuICAgIGRiLFxuICAgIFRSQUlOSU5HX1RBQkxFX05BTUUsXG4gICAgdmVjdG9yLFxuICAgIGxpbWl0LFxuICAgIHNhbXBsZVRyYWluaW5nRGF0YSxcbiAgICBmaWx0ZXJDb25kaXRpb25cbiAgKSkgYXMgVHJhaW5pbmdFdmVudFNjaGVtYVtdO1xufVxuXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gZ2V0VHJhaW5pbmdFdmVudEJ5SWQoXG4gIGlkOiBzdHJpbmdcbik6IFByb21pc2U8VHJhaW5pbmdFdmVudFNjaGVtYSB8IG51bGw+IHtcbiAgY29uc3QgZGIgPSBhd2FpdCBnZXREQkNvbm5lY3Rpb24oKTtcbiAgY29uc3Qgc2FtcGxlVHJhaW5pbmdEYXRhOiBUcmFpbmluZ0V2ZW50U2NoZW1hW10gPSBbXG4gICAge1xuICAgICAgaWQ6ICcnLFxuICAgICAgdXNlcklkOiAnJyxcbiAgICAgIHZlY3RvcjogW10sXG4gICAgICBzb3VyY2VfZXZlbnRfdGV4dDogJycsXG4gICAgICBjcmVhdGVkX2F0OiAnJyxcbiAgICB9LFxuICBdO1xuICByZXR1cm4gKGF3YWl0IGdldEl0ZW1CeUlkKFxuICAgIGRiLFxuICAgIFRSQUlOSU5HX1RBQkxFX05BTUUsXG4gICAgaWQsXG4gICAgc2FtcGxlVHJhaW5pbmdEYXRhXG4gICkpIGFzIFRyYWluaW5nRXZlbnRTY2hlbWEgfCBudWxsO1xufVxuXG4vLyBFeGFtcGxlIG9mIGhvdyB0byBnZXQgc3BlY2lmaWMgdGFibGVzIChjYW4gYmUgZXhwYW5kZWQpXG5leHBvcnQgYXN5bmMgZnVuY3Rpb24gZ2V0RXZlbnREYXRhVGFibGUoKTogUHJvbWlzZTxUYWJsZT4ge1xuICBjb25zdCBkYiA9IGF3YWl0IGdldERCQ29ubmVjdGlvbigpO1xuICAvLyBQcm92aWRlIGEgc2FtcGxlIGRhdGEgc3RydWN0dXJlIGZvciBzY2hlbWEgaW5mZXJlbmNlIGlmIHRhYmxlIG5lZWRzIGNyZWF0aW9uLlxuICAvLyBDcnVjaWFsbHksIHZlY3RvciBmaWVsZCBtdXN0IGJlIHByZXNlbnQuXG4gIGNvbnN0IHNhbXBsZUV2ZW50RGF0YTogRXZlbnRTY2hlbWFbXSA9IFtcbiAgICB7XG4gICAgICBpZDogJycsXG4gICAgICB1c2VySWQ6ICcnLFxuICAgICAgdmVjdG9yOiBbXSxcbiAgICAgIHN0YXJ0X2RhdGU6ICcnLFxuICAgICAgZW5kX2RhdGU6ICcnLFxuICAgICAgcmF3X2V2ZW50X3RleHQ6ICcnLFxuICAgICAgbGFzdF9tb2RpZmllZDogJycsXG4gICAgICB0aXRsZTogJycsXG4gICAgfSxcbiAgXTtcbiAgcmV0dXJuIGdldE9yQ3JlYXRlVGFibGUoZGIsIEVWRU5UX1RBQkxFX05BTUUsIHNhbXBsZUV2ZW50RGF0YSk7XG59XG5cbmV4cG9ydCBhc3luYyBmdW5jdGlvbiBnZXRUcmFpbmluZ0RhdGFUYWJsZSgpOiBQcm9taXNlPFRhYmxlPiB7XG4gIGNvbnN0IGRiID0gYXdhaXQgZ2V0REJDb25uZWN0aW9uKCk7XG4gIGNvbnN0IHNhbXBsZVRyYWluaW5nRGF0YTogVHJhaW5pbmdFdmVudFNjaGVtYVtdID0gW1xuICAgIHtcbiAgICAgIGlkOiAnJyxcbiAgICAgIHVzZXJJZDogJycsXG4gICAgICB2ZWN0b3I6IFtdLFxuICAgICAgc291cmNlX2V2ZW50X3RleHQ6ICcnLFxuICAgICAgY3JlYXRlZF9hdDogJycsXG4gICAgfSxcbiAgXTtcbiAgcmV0dXJuIGdldE9yQ3JlYXRlVGFibGUoZGIsIFRSQUlOSU5HX1RBQkxFX05BTUUsIHNhbXBsZVRyYWluaW5nRGF0YSk7XG59XG4iXX0=