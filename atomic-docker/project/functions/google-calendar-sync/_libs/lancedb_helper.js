import { connect } from 'vectordb';
const LANCEDB_DATA_PATH = '/data/lancedb'; // Assuming a local path
async function connectToLanceDB() {
    try {
        const db = await connect(LANCEDB_DATA_PATH);
        console.log('Successfully connected to LanceDB.');
        return db;
    }
    catch (error) {
        console.error('Failed to connect to LanceDB:', error);
        throw error;
    }
}
export async function getOrCreateEventTable(db) {
    const tableName = 'events';
    try {
        const table = await db.openTable(tableName);
        console.log(`Table "${tableName}" opened successfully.`);
        return table;
    }
    catch (error) {
        // Assuming error indicates table doesn't exist, try to create it
        console.log(`Table "${tableName}" not found, attempting to create it.`);
        try {
            // LanceDB requires a sample data object to infer schema for creation,
            // or an explicit schema definition if supported by the version of vectordb.
            // For simplicity, we'll use an empty array and rely on schema inference if possible,
            // or adjust if direct schema definition is needed.
            // A more robust approach would involve checking the error type.
            const initialData = []; // LanceDB might need representative data or an explicit schema
            // Note: The `vectordb` library's API for table creation might vary.
            // `db.createTable` might require a schema object or sample data.
            // Let's assume `createTable` can take the table name and optionally initial data or a schema.
            // If `embed` function is required like in documentation, we'd need to specify dummy embedding for schema.
            // For now, we'll try creating with just the name and then add data which defines schema.
            // This part might need adjustment based on exact library behavior for schema definition on creation.
            // A common pattern is to provide data with vector fields to create the schema.
            const table = await db.createTable(tableName, initialData);
            console.log(`Table "${tableName}" created successfully.`);
            return table;
        }
        catch (creationError) {
            console.error(`Failed to create table "${tableName}":`, creationError);
            throw creationError;
        }
    }
}
export async function bulkUpsertToLanceDBEvents(data) {
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
        const existingIds = data.map((item) => item.id);
        if (existingIds.length > 0) {
            const deleteQuery = `id IN (${existingIds.map((id) => `'${id}'`).join(',')})`;
            try {
                await table.delete(deleteQuery);
                console.log(`Successfully deleted existing records for IDs: ${existingIds.join(', ')}`);
            }
            catch (deleteError) {
                // It's possible that delete fails if some IDs don't exist; often this is not a critical error for upsert.
                console.warn(`Warning or error during pre-delete for upsert (some IDs might not exist):`, deleteError);
            }
        }
        await table.add(data);
        console.log(`Successfully upserted ${data.length} records.`);
    }
    catch (error) {
        console.error('Error during bulk upsert to LanceDB:', error);
        throw error;
    }
}
export async function bulkDeleteFromLanceDBEvents(ids) {
    if (!ids || ids.length === 0) {
        console.log('No IDs provided for deletion.');
        return;
    }
    const db = await connectToLanceDB();
    const table = await getOrCreateEventTable(db); // Ensure table exists
    try {
        const deleteQuery = `id IN (${ids.map((id) => `'${id.replace(/'/g, "''")}'`).join(',')})`; // Escape single quotes in IDs
        await table.delete(deleteQuery);
        console.log(`Successfully deleted records for IDs: ${ids.join(', ')}`);
    }
    catch (error) {
        console.error('Error during bulk delete from LanceDB:', error);
        throw error;
    }
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoibGFuY2VkYl9oZWxwZXIuanMiLCJzb3VyY2VSb290IjoiIiwic291cmNlcyI6WyJsYW5jZWRiX2hlbHBlci50cyJdLCJuYW1lcyI6W10sIm1hcHBpbmdzIjoiQUFBQSxPQUFPLEVBQUUsT0FBTyxFQUFxQixNQUFNLFVBQVUsQ0FBQztBQUV0RCxNQUFNLGlCQUFpQixHQUFHLGVBQWUsQ0FBQyxDQUFDLHdCQUF3QjtBQVduRSxLQUFLLFVBQVUsZ0JBQWdCO0lBQzdCLElBQUksQ0FBQztRQUNILE1BQU0sRUFBRSxHQUFHLE1BQU0sT0FBTyxDQUFDLGlCQUFpQixDQUFDLENBQUM7UUFDNUMsT0FBTyxDQUFDLEdBQUcsQ0FBQyxvQ0FBb0MsQ0FBQyxDQUFDO1FBQ2xELE9BQU8sRUFBRSxDQUFDO0lBQ1osQ0FBQztJQUFDLE9BQU8sS0FBSyxFQUFFLENBQUM7UUFDZixPQUFPLENBQUMsS0FBSyxDQUFDLCtCQUErQixFQUFFLEtBQUssQ0FBQyxDQUFDO1FBQ3RELE1BQU0sS0FBSyxDQUFDO0lBQ2QsQ0FBQztBQUNILENBQUM7QUFFRCxNQUFNLENBQUMsS0FBSyxVQUFVLHFCQUFxQixDQUN6QyxFQUFjO0lBRWQsTUFBTSxTQUFTLEdBQUcsUUFBUSxDQUFDO0lBQzNCLElBQUksQ0FBQztRQUNILE1BQU0sS0FBSyxHQUFHLE1BQU0sRUFBRSxDQUFDLFNBQVMsQ0FBYyxTQUFTLENBQUMsQ0FBQztRQUN6RCxPQUFPLENBQUMsR0FBRyxDQUFDLFVBQVUsU0FBUyx3QkFBd0IsQ0FBQyxDQUFDO1FBQ3pELE9BQU8sS0FBSyxDQUFDO0lBQ2YsQ0FBQztJQUFDLE9BQU8sS0FBSyxFQUFFLENBQUM7UUFDZixpRUFBaUU7UUFDakUsT0FBTyxDQUFDLEdBQUcsQ0FBQyxVQUFVLFNBQVMsdUNBQXVDLENBQUMsQ0FBQztRQUN4RSxJQUFJLENBQUM7WUFDSCxzRUFBc0U7WUFDdEUsNEVBQTRFO1lBQzVFLHFGQUFxRjtZQUNyRixtREFBbUQ7WUFDbkQsZ0VBQWdFO1lBQ2hFLE1BQU0sV0FBVyxH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ckUsSUFBSSxDQUFDO1FBQ0gsTUFBTSxXQUFXLEdBQUcsVUFBVSxHQUFHLENBQUMsR0FBRyxDQUFDLENBQUMsRUFBRSxFQUFFLEVBQUUsQ0FBQyxJQUFJLEVBQUUsQ0FBQyxPQUFPLENBQUMsSUFBSSxFQUFFLElBQUksQ0FBQyxHQUFHLENBQUMsQ0FBQyxJQUFJLENBQUMsR0FBRyxDQUFDLEdBQUcsQ0FBQyxDQUFDLDhCQUE4QjtRQUN6SCxNQUFNLEtBQUssQ0FBQyxNQUFNLENBQUMsV0FBVyxDQUFDLENBQUM7UUFDaEMsT0FBTyxDQUFDLEdBQUcsQ0FBQyx5Q0FBeUMsR0FBRyxDQUFDLElBQUksQ0FBQyxJQUFJLENBQUMsRUFBRSxDQUFDLENBQUM7SUFDekUsQ0FBQztJQUFDLE9BQU8sS0FBSyxFQUFFLENBQUM7UUFDZixPQUFPLENBQUMsS0FBSyxDQUFDLHdDQUF3QyxFQUFFLEtBQUssQ0FBQyxDQUFDO1FBQy9ELE1BQU0sS0FBSyxDQUFDO0lBQ2QsQ0FBQztBQUNILENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgeyBjb25uZWN0LCBDb25uZWN0aW9uLCBUYWJsZSB9IGZyb20gJ3ZlY3RvcmRiJztcblxuY29uc3QgTEFOQ0VEQl9EQVRBX1BBVEggPSAnL2RhdGEvbGFuY2VkYic7IC8vIEFzc3VtaW5nIGEgbG9jYWwgcGF0aFxuXG5pbnRlcmZhY2UgRXZlbnRTY2hlbWEge1xuICBpZDogc3RyaW5nOyAvLyBQcmltYXJ5IGtleTogZXZlbnRJZCNjYWxlbmRhcklkXG4gIHVzZXJJZDogc3RyaW5nO1xuICB2ZWN0b3I6IG51bWJlcltdOyAvLyBPcGVuQUkgdGV4dC1lbWJlZGRpbmctMy1zbWFsbCBkaW1lbnNpb246IDE1MzZcbiAgc3RhcnRfZGF0ZTogc3RyaW5nOyAvLyBJU08gODYwMSBmb3JtYXRcbiAgZW5kX2RhdGU6IHN0cmluZzsgLy8gSVNPIDg2MDEgZm9ybWF0XG4gIHJhd19ldmVudF90ZXh0Pzogc3RyaW5nOyAvLyBPcHRpb25hbDogc3VtbWFyeTpkZXNjcmlwdGlvblxufVxuXG5hc3luYyBmdW5jdGlvbiBjb25uZWN0VG9MYW5jZURCKCk6IFByb21pc2U8Q29ubmVjdGlvbj4ge1xuICB0cnkge1xuICAgIGNvbnN0IGRiID0gYXdhaXQgY29ubmVjdChMQU5DRURCX0RBVEFfUEFUSCk7XG4gICAgY29uc29sZS5sb2coJ1N1Y2Nlc3NmdWxseSBjb25uZWN0ZWQgdG8gTGFuY2VEQi4nKTtcbiAgICByZXR1cm4gZGI7XG4gIH0gY2F0Y2ggKGVycm9yKSB7XG4gICAgY29uc29sZS5lcnJvcignRmFpbGVkIHRvIGNvbm5lY3QgdG8gTGFuY2VEQjonLCBlcnJvcik7XG4gICAgdGhyb3cgZXJyb3I7XG4gIH1cbn1cblxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIGdldE9yQ3JlYXRlRXZlbnRUYWJsZShcbiAgZGI6IENvbm5lY3Rpb25cbik6IFByb21pc2U8VGFibGU8RXZlbnRTY2hlbWE+PiB7XG4gIGNvbnN0IHRhYmxlTmFtZSA9ICdldmVudHMnO1xuICB0cnkge1xuICAgIGNvbnN0IHRhYmxlID0gYXdhaXQgZGIub3BlblRhYmxlPEV2ZW50U2NoZW1hPih0YWJsZU5hbWUpO1xuICAgIGNvbnNvbGUubG9nKGBUYWJsZSBcIiR7dGFibGVOYW1lfVwiIG9wZW5lZCBzdWNjZXNzZnVsbHkuYCk7XG4gICAgcmV0dXJuIHRhYmxlO1xuICB9IGNhdGNoIChlcnJvcikge1xuICAgIC8vIEFzc3VtaW5nIGVycm9yIGluZGljYXRlcyB0YWJsZSBkb2Vzbid0IGV4aXN0LCB0cnkgdG8gY3JlYXRlIGl0XG4gICAgY29uc29sZS5sb2coYFRhYmxlIFwiJHt0YWJsZU5hbWV9XCIgbm90IGZvdW5kLCBhdHRlbXB0aW5nIHRvIGNyZWF0ZSBpdC5gKTtcbiAgICB0cnkge1xuICAgICAgLy8gTGFuY2VEQiByZXF1aXJlcyBhIHNhbXBsZSBkYXRhIG9iamVjdCB0byBpbmZlciBzY2hlbWEgZm9yIGNyZWF0aW9uLFxuICAgICAgLy8gb3IgYW4gZXhwbGljaXQgc2NoZW1hIGRlZmluaXRpb24gaWYgc3VwcG9ydGVkIGJ5IHRoZSB2ZXJzaW9uIG9mIHZlY3RvcmRiLlxuICAgICAgLy8gRm9yIHNpbXBsaWNpdHksIHdlJ2xsIHVzZSBhbiBlbXB0eSBhcnJheSBhbmQgcmVseSBvbiBzY2hlbWEgaW5mZXJlbmNlIGlmIHBvc3NpYmxlLFxuICAgICAgLy8gb3IgYWRqdXN0IGlmIGRpcmVjdCBzY2hlbWEgZGVmaW5pdGlvbiBpcyBuZWVkZWQuXG4gICAgICAvLyBBIG1vcmUgcm9idXN0IGFwcHJvYWNoIHdvdWxkIGludm9sdmUgY2hlY2tpbmcgdGhlIGVycm9yIHR5cGUuXG4gICAgICBjb25zdCBpbml0aWFsRGF0YTogRXZlbnRTY2hlbWFbXSA9IFtdOyAvLyBMYW5jZURCIG1pZ2h0IG5lZWQgcmVwcmVzZW50YXRpdmUgZGF0YSBvciBhbiBleHBsaWNpdCBzY2hlbWFcblxuICAgICAgLy8gTm90ZTogVGhlIGB2ZWN0b3JkYmAgbGlicmFyeSdzIEFQSSBmb3IgdGFibGUgY3JlYXRpb24gbWlnaHQgdmFyeS5cbiAgICAgIC8vIGBkYi5jcmVhdGVUYWJsZWAgbWlnaHQgcmVxdWlyZSBhIHNjaGVtYSBvYmplY3Qgb3Igc2FtcGxlIGRhdGEuXG4gICAgICAvLyBMZXQncyBhc3N1bWUgYGNyZWF0ZVRhYmxlYCBjYW4gdGFrZSB0aGUgdGFibGUgbmFtZSBhbmQgb3B0aW9uYWxseSBpbml0aWFsIGRhdGEgb3IgYSBzY2hlbWEuXG4gICAgICAvLyBJZiBgZW1iZWRgIGZ1bmN0aW9uIGlzIHJlcXVpcmVkIGxpa2UgaW4gZG9jdW1lbnRhdGlvbiwgd2UnZCBuZWVkIHRvIHNwZWNpZnkgZHVtbXkgZW1iZWRkaW5nIGZvciBzY2hlbWEuXG4gICAgICAvLyBGb3Igbm93LCB3ZSdsbCB0cnkgY3JlYXRpbmcgd2l0aCBqdXN0IHRoZSBuYW1lIGFuZCB0aGVuIGFkZCBkYXRhIHdoaWNoIGRlZmluZXMgc2NoZW1hLlxuICAgICAgLy8gVGhpcyBwYXJ0IG1pZ2h0IG5lZWQgYWRqdXN0bWVudCBiYXNlZCBvbiBleGFjdCBsaWJyYXJ5IGJlaGF2aW9yIGZvciBzY2hlbWEgZGVmaW5pdGlvbiBvbiBjcmVhdGlvbi5cbiAgICAgIC8vIEEgY29tbW9uIHBhdHRlcm4gaXMgdG8gcHJvdmlkZSBkYXRhIHdpdGggdmVjdG9yIGZpZWxkcyB0byBjcmVhdGUgdGhlIHNjaGVtYS5cbiAgICAgIGNvbnN0IHRhYmxlID0gYXdhaXQgZGIuY3JlYXRlVGFibGU8RXZlbnRTY2hlbWE+KHRhYmxlTmFtZSwgaW5pdGlhbERhdGEpO1xuICAgICAgY29uc29sZS5sb2coYFRhYmxlIFwiJHt0YWJsZU5hbWV9XCIgY3JlYXRlZCBzdWNjZXNzZnVsbHkuYCk7XG4gICAgICByZXR1cm4gdGFibGU7XG4gICAgfSBjYXRjaCAoY3JlYXRpb25FcnJvcikge1xuICAgICAgY29uc29sZS5lcnJvcihgRmFpbGVkIHRvIGNyZWF0ZSB0YWJsZSBcIiR7dGFibGVOYW1lfVwiOmAsIGNyZWF0aW9uRXJyb3IpO1xuICAgICAgdGhyb3cgY3JlYXRpb25FcnJvcjtcbiAgICB9XG4gIH1cbn1cblxuZXhwb3J0IGFzeW5jIGZ1bmN0aW9uIGJ1bGtVcHNlcnRUb0xhbmNlREJFdmVudHMoXG4gIGRhdGE6IEV2ZW50U2NoZW1hW11cbik6IFByb21pc2U8dm9pZD4ge1xuICBpZiAoIWRhdGEgfHwgZGF0YS5sZW5ndGggPT09IDApIHtcbiAgICBjb25zb2xlLmxvZygnTm8gZGF0YSBwcm92aWRlZCBmb3IgdXBzZXJ0LicpO1xuICAgIHJldHVybjtcbiAgfVxuICBjb25zdCBkYiA9IGF3YWl0IGNvbm5lY3RUb0xhbmNlREIoKTtcbiAgY29uc3QgdGFibGUgPSBhd2FpdCBnZXRPckNyZWF0ZUV2ZW50VGFibGUoZGIpO1xuXG4gIHRyeSB7XG4gICAgLy8gTGFuY2VEQidzIGFkZCBvcGVyYXRpb24gY2FuIG9mdGVuIGFjdCBhcyBhbiB1cHNlcnQgaWYgSURzIGFyZSBwcmVzZW50XG4gICAgLy8gYW5kIHRoZSB0YWJsZSBpcyBjb25maWd1cmVkIHRvIGhhbmRsZSBjb25mbGljdHMgYnkgcmVwbGFjZW1lbnQgb3IgdXBkYXRlLlxuICAgIC8vIEhvd2V2ZXIsIGEgY29tbW9uIGV4cGxpY2l0IHVwc2VydCBwYXR0ZXJuIGlzIGRlbGV0ZSB0aGVuIGFkZC5cbiAgICAvLyBGb3Igc2ltcGxpY2l0eSwgd2UnbGwgZmlyc3QgZGVsZXRlIGV4aXN0aW5nIHJlY29yZHMgYnkgSUQsIHRoZW4gYWRkIG5ldyBvbmVzLlxuICAgIC8vIFRoaXMgZW5zdXJlcyBpZGVtcG90ZW5jeSBmb3IgdGhlIHVwc2VydCBvcGVyYXRpb24uXG4gICAgY29uc3QgZXhpc3RpbmdJZHMgPSBkYXRhLm1hcCgoaXRlbSkgPT4gaXRlbS5pZCk7XG4gICAgaWYgKGV4aXN0aW5nSWRzLmxlbmd0aCA+IDApIHtcbiAgICAgIGNvbnN0IGRlbGV0ZVF1ZXJ5ID0gYGlkIElOICgke2V4aXN0aW5nSWRzLm1hcCgoaWQpID0+IGAnJHtpZH0nYCkuam9pbignLCcpfSlgO1xuICAgICAgdHJ5IHtcbiAgICAgICAgYXdhaXQgdGFibGUuZGVsZXRlKGRlbGV0ZVF1ZXJ5KTtcbiAgICAgICAgY29uc29sZS5sb2coXG4gICAgICAgICAgYFN1Y2Nlc3NmdWxseSBkZWxldGVkIGV4aXN0aW5nIHJlY29yZHMgZm9yIElEczogJHtleGlzdGluZ0lkcy5qb2luKCcsICcpfWBcbiAgICAgICAgKTtcbiAgICAgIH0gY2F0Y2ggKGRlbGV0ZUVycm9yKSB7XG4gICAgICAgIC8vIEl0J3MgcG9zc2libGUgdGhhdCBkZWxldGUgZmFpbHMgaWYgc29tZSBJRHMgZG9uJ3QgZXhpc3Q7IG9mdGVuIHRoaXMgaXMgbm90IGEgY3JpdGljYWwgZXJyb3IgZm9yIHVwc2VydC5cbiAgICAgICAgY29uc29sZS53YXJuKFxuICAgICAgICAgIGBXYXJuaW5nIG9yIGVycm9yIGR1cmluZyBwcmUtZGVsZXRlIGZvciB1cHNlcnQgKHNvbWUgSURzIG1pZ2h0IG5vdCBleGlzdCk6YCxcbiAgICAgICAgICBkZWxldGVFcnJvclxuICAgICAgICApO1xuICAgICAgfVxuICAgIH1cblxuICAgIGF3YWl0IHRhYmxlLmFkZChkYXRhKTtcbiAgICBjb25zb2xlLmxvZyhgU3VjY2Vzc2Z1bGx5IHVwc2VydGVkICR7ZGF0YS5sZW5ndGh9IHJlY29yZHMuYCk7XG4gIH0gY2F0Y2ggKGVycm9yKSB7XG4gICAgY29uc29sZS5lcnJvcignRXJyb3IgZHVyaW5nIGJ1bGsgdXBzZXJ0IHRvIExhbmNlREI6JywgZXJyb3IpO1xuICAgIHRocm93IGVycm9yO1xuICB9XG59XG5cbmV4cG9ydCBhc3luYyBmdW5jdGlvbiBidWxrRGVsZXRlRnJvbUxhbmNlREJFdmVudHMoXG4gIGlkczogc3RyaW5nW11cbik6IFByb21pc2U8dm9pZD4ge1xuICBpZiAoIWlkcyB8fCBpZHMubGVuZ3RoID09PSAwKSB7XG4gICAgY29uc29sZS5sb2coJ05vIElEcyBwcm92aWRlZCBmb3IgZGVsZXRpb24uJyk7XG4gICAgcmV0dXJuO1xuICB9XG4gIGNvbnN0IGRiID0gYXdhaXQgY29ubmVjdFRvTGFuY2VEQigpO1xuICBjb25zdCB0YWJsZSA9IGF3YWl0IGdldE9yQ3JlYXRlRXZlbnRUYWJsZShkYik7IC8vIEVuc3VyZSB0YWJsZSBleGlzdHNcblxuICB0cnkge1xuICAgIGNvbnN0IGRlbGV0ZVF1ZXJ5ID0gYGlkIElOICgke2lkcy5tYXAoKGlkKSA9PiBgJyR7aWQucmVwbGFjZSgvJy9nLCBcIicnXCIpfSdgKS5qb2luKCcsJyl9KWA7IC8vIEVzY2FwZSBzaW5nbGUgcXVvdGVzIGluIElEc1xuICAgIGF3YWl0IHRhYmxlLmRlbGV0ZShkZWxldGVRdWVyeSk7XG4gICAgY29uc29sZS5sb2coYFN1Y2Nlc3NmdWxseSBkZWxldGVkIHJlY29yZHMgZm9yIElEczogJHtpZHMuam9pbignLCAnKX1gKTtcbiAgfSBjYXRjaCAoZXJyb3IpIHtcbiAgICBjb25zb2xlLmVycm9yKCdFcnJvciBkdXJpbmcgYnVsayBkZWxldGUgZnJvbSBMYW5jZURCOicsIGVycm9yKTtcbiAgICB0aHJvdyBlcnJvcjtcbiAgfVxufVxuIl19