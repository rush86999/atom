import { Pool } from 'pg';

const poolConfig = {
    connectionString: process.env.DATABASE_URL,
    ssl: process.env.NODE_ENV === 'production' ? { rejectUnauthorized: false } : false,
    // Add a short timeout to fail fast if DB is down
    connectionTimeoutMillis: 2000,
};

// Use a global variable to store the pool instance in development
// This prevents creating multiple connection pools during hot reloading
let pool: Pool;

if (process.env.NODE_ENV === 'production') {
    pool = new Pool(poolConfig);
} else {
    // Graceful handling for development without DATABASE_URL
    if (!poolConfig.connectionString) {
        console.warn('⚠️  WARNING: DATABASE_URL is not set. Database features will not work.');
        // Create a mock pool to prevent crashes on import
        pool = {
            query: async () => {
                console.error('❌  Cannot execute query: Database not connected (missing DATABASE_URL)');
                throw new Error('Database not connected');
            },
            on: () => { },
            connect: async () => {
                throw new Error('Database not connected');
            }
        } as any;
    } else {
        // Check if a pool already exists on the global object
        if (!(global as any).postgresPool) {
            (global as any).postgresPool = new Pool(poolConfig);
        }
        pool = (global as any).postgresPool;
    }
}

export const query = async (text: string, params?: any[]) => {
    try {
        return await pool.query(text, params);
    } catch (error: any) {
        // Enhanced error logging for debugging
        console.error('❌ Database connection error:', {
            message: error.message,
            query: text,
            params: params,
        });

        // Throw the error so the application knows something went wrong
        // Silent failures here would lead to confusing bugs downstream
        throw error;
    }
};
