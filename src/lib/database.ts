import { Pool, PoolClient } from 'pg';

export class DatabaseService {
  private pool: Pool;
  private client: PoolClient | null = null;

  constructor() {
    const connectionString = process.env.DATABASE_URL;
    if (!connectionString) {
      throw new Error('DATABASE_URL environment variable is required');
    }

    this.pool = new Pool({
      connectionString,
      ssl: process.env.DATABASE_SSL === 'true' || process.env.NODE_ENV === 'production'
        ? { rejectUnauthorized: false }
        : false,
      max: 20,
      idleTimeoutMillis: 30000,
      connectionTimeoutMillis: 5000,
    });
  }

  async query(sql: string, params: any[] = []): Promise<any> {
    try {
      const result = await this.pool.query(sql, params);
      return result;
    } catch (error) {
      console.error('Database query error:', error);
      throw error;
    }
  }

  async transaction<T>(callback: (client: PoolClient) => Promise<T>): Promise<T> {
    const client = await this.pool.connect();
    try {
      await client.query('BEGIN');
      const result = await callback(client);
      await client.query('COMMIT');
      return result;
    } catch (error) {
      await client.query('ROLLBACK');
      console.error('Transaction error:', error);
      throw error;
    } finally {
      client.release();
    }
  }

  async close(): Promise<void> {
    await this.pool.end();
  }

  // Tenant context methods
  async setTenantContext(tenantId: string): Promise<void> {
    await this.query('SELECT set_tenant_context($1)', [tenantId]);
  }

  async getCurrentTenant(): Promise<any> {
    const result = await this.query('SELECT * FROM get_current_tenant()');
    return result.rows[0];
  }

  // Tenant CRUD operations
  async getTenants(filters: {
    search?: string;
    plan?: string;
    status?: string;
    page?: number;
    limit?: number;
  } = {}) {
    let query = `
      SELECT 
        t.*,
        COUNT(DISTINCT u.id) as user_count,
        COUNT(DISTINCT w.id) as workflow_count,
        COUNT(DISTINCT d.id) as document_count
      FROM tenants t
      LEFT JOIN users u ON t.id = u.tenant_id AND u.status = 'active'
      LEFT JOIN workflows w ON t.id = w.tenant_id
      LEFT JOIN ingested_documents d ON t.id = d.tenant_id
      WHERE 1=1
    `;

    const params: any[] = [];
    let paramIndex = 1;

    if (filters.search) {
      query += ` AND (
        t.name ILIKE $${paramIndex++} OR 
        t.subdomain ILIKE $${paramIndex++} OR 
        t.billing_email ILIKE $${paramIndex++}
      )`;
      params.push(`%${filters.search}%`, `%${filters.search}%`, `%${filters.search}%`);
    }

    if (filters.plan) {
      query += ` AND t.plan_type = $${paramIndex++}`;
      params.push(filters.plan);
    }

    if (filters.status) {
      query += ` AND t.is_active = $${paramIndex++}`;
      params.push(filters.status === 'active');
    }

    query += ` GROUP BY t.id ORDER BY t.created_at DESC`;

    if (filters.limit) {
      const offset = ((filters.page || 1) - 1) * filters.limit;
      query += ` LIMIT $${paramIndex++} OFFSET $${paramIndex++}`;
      params.push(filters.limit, offset);
    }

    const result = await this.query(query, params);
    return result.rows;
  }

  async getTenantById(tenantId: string): Promise<any> {
    const result = await this.query(`
      SELECT 
        t.*,
        COUNT(DISTINCT u.id) as user_count,
        COUNT(DISTINCT w.id) as workflow_count,
        COUNT(DISTINCT d.id) as document_count,
        COUNT(DISTINCT a.id) as agent_count
      FROM tenants t
      LEFT JOIN users u ON t.id = u.tenant_id AND u.status = 'active'
      LEFT JOIN workflows w ON t.id = w.tenant_id
      LEFT JOIN ingested_documents d ON t.id = d.tenant_id
      LEFT JOIN agent_registry a ON t.id = a.tenant_id
      WHERE t.id = $1
      GROUP BY t.id
    `, [tenantId]);

    return result.rows[0];
  }

  async getTenantBySubdomain(subdomain: string): Promise<any> {
    const result = await this.query(
      "SELECT * FROM tenants WHERE subdomain = $1 AND status = 'active'",
      [subdomain]
    );

    return result.rows[0];
  }

  async createTenant(tenantData: {
    name: string;
    subdomain: string;
    billing_email: string;
    plan_type?: string;
    storage_limit_mb?: number;
    max_users?: number;
    memory_limit_mb?: number;
    max_agents?: number;
    sync_frequency?: string;
    collaborative_memory?: boolean;
    segregated_namespaces?: boolean;
  }): Promise<any> {
    const result = await this.query(`
      INSERT INTO tenants (
        name, subdomain, billing_email, plan_type, 
        storage_limit_mb,
 max_users, memory_limit_mb, max_agents, sync_frequency,
        collaborative_memory, segregated_namespaces
      )
      VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
      RETURNING *
    `, [
      tenantData.name,
      tenantData.subdomain,
      tenantData.billing_email,
      tenantData.plan_type || 'free',
      tenantData.storage_limit_mb || 50,
      tenantData.max_users || 3,
      tenantData.memory_limit_mb || 50,
      tenantData.max_agents || 1,
      tenantData.sync_frequency || 'weekly',
      tenantData.collaborative_memory || false,
      tenantData.segregated_namespaces || false
    ]);

    return result.rows[0];
  }

  async updateTenant(tenantId: string, updates: { auto_sync_enabled?: boolean }): Promise<void> {
    const setClauses: string[] = [];
    const params: any[] = [tenantId];
    let paramIndex = 2;

    if (updates.auto_sync_enabled !== undefined) {
      setClauses.push(`auto_sync_enabled = $${paramIndex++}`);
      params.push(updates.auto_sync_enabled);
    }

    if (setClauses.length === 0) return;

    await this.query(`
      UPDATE tenants 
      SET ${setClauses.join(', ')}, updated_at = NOW()
      WHERE id = $1
    `, params);
  }

  async countIngestedDocuments(tenantId: string): Promise<number> {
    const result = await this.query(
      'SELECT COUNT(*) as count FROM ingested_documents WHERE tenant_id = $1',
      [tenantId]
    );
    return parseInt(result.rows[0].count);
  }

  // User CRUD operations
  async getUsers(tenantId?: string, filters: {
    search?: string;
    is_active?: boolean;
    page?: number;
    limit?: number;
  } = {}) {
    let query = `
      SELECT 
        u.*,
        t.name as tenant_name
      FROM users u
      JOIN tenants t ON u.tenant_id = t.id
      WHERE 1=1
    `;

    const params: any[] = [];
    let paramIndex = 1;

    if (tenantId) {
      query += ` AND u.tenant_id = $${paramIndex++}`;
      params.push(tenantId);
    }

    if (filters.search) {
      query += ` AND (
        u.email ILIKE $${paramIndex++} OR 
        u.name ILIKE $${paramIndex++}
      )`;
      params.push(`%${filters.search}%`, `%${filters.search}%`);
    }

    //     if (filters.is_active !== undefined) {
    //       // query += ` AND u.status = $${paramIndex++}`;
    //       // params.push(filters.is_active ? 'active' : 'suspended');
    //     }

    query += ` ORDER BY u.created_at DESC`;

    if (filters.limit) {
      const offset = ((filters.page || 1) - 1) * filters.limit;
      query += ` LIMIT $${paramIndex++} OFFSET $${paramIndex++}`;
      params.push(filters.limit, offset);
    }

    const result = await this.query(query, params);
    return result.rows;
  }

  async createUser(userData: {
    email: string;
    password_hash: string;
    name: string;
    tenant_id: string;
    is_tenant_admin?: boolean;
    is_active?: boolean;
  }): Promise<any> {
    const result = await this.query(`
      INSERT INTO users (
        email, password_hash, name, tenant_id, 
        is_tenant_admin, status, onboarding_completed
      )
      VALUES ($1, $2, $3, $4, $5, $6, $7)
      RETURNING *
    `, [
      userData.email,
      userData.password_hash,
      userData.name,
      userData.tenant_id,
      userData.is_tenant_admin || false,
      userData.is_active !== false ? 'active' : 'suspended',
      false // default onboarding_completed
    ]);

    return result.rows[0];
  }

  // Analytics methods
  async logEvent(tenantId: string, eventType: string, eventData: any, userId?: string) {
    await this.query(`
      INSERT INTO analytics_events (
        tenant_id, event_type, event_data, user_id
      )
      VALUES ($1, $2, $3, $4)
    `, [tenantId, eventType, eventData, userId]);
  }

  async getAnalytics(tenantId?: string, period: string = '30') {
    const filters = tenantId ? `AND tenant_id = '${tenantId}'` : '';

    const result = await this.query(`
      SELECT 
        event_type,
        COUNT(*) as count,
        COUNT(DISTINCT tenant_id) as unique_tenants,
        COUNT(DISTINCT user_id) as unique_users
      FROM analytics_events
      WHERE timestamp >= NOW() - INTERVAL '${period} days' ${filters}
      GROUP BY event_type
      ORDER BY count DESC
    `);

    return result.rows;
  }

  // Storage management
  async updateStorageUsage(tenantId: string, bytes: number, fileType: string) {
    await this.query('SELECT update_storage_usage($1, $2, $3)', [
      tenantId, bytes, fileType
    ]);
  }

  async getStorageUsage(tenantId: string) {
    const result = await this.query(`
      SELECT 
        file_type,
        SUM(file_size_bytes) as total_bytes,
        SUM(file_size_bytes) / (1024 * 1024) as total_mb,
        COUNT(*) as file_count
      FROM storage_usage 
      WHERE tenant_id = $1
      GROUP BY file_type
      ORDER BY total_bytes DESC
    `, [tenantId]);

    return result.rows;
  }

  // Feature flags
  async getFeatureFlags(tenantId?: string) {
    let query = `
      SELECT 
        ff.name,
        ff.description,
        ff.is_global,
        tf.is_enabled
      FROM feature_flags ff
    `;

    if (tenantId) {
      query += `
        LEFT JOIN tenant_feature_flags tf ON ff.id = tf.feature_flag_id AND tf.tenant_id = $1
        WHERE ff.is_global = true OR tf.tenant_id = $1
      `;
    } else {
      query += `LEFT JOIN tenant_feature_flags tf ON ff.id = tf.feature_flag_id AND tf.is_enabled = true`;
    }

    query += ` ORDER BY ff.name`;

    const params = tenantId ? [tenantId] : [];
    const result = await this.query(query, params);
    return result.rows;
  }

  async setFeatureFlag(tenantId: string, featureName: string, enabled: boolean) {
    await this.query(`
      INSERT INTO tenant_feature_flags (tenant_id, feature_flag_id, is_enabled)
      VALUES ($1, (SELECT id FROM feature_flags WHERE name = $2), $3)
      ON CONFLICT (tenant_id, feature_flag_id)
      DO UPDATE SET is_enabled = EXCLUDED.is_enabled, updated_at = NOW()
    `, [tenantId, featureName, enabled]);
  }

  // Health check
  async healthCheck(): Promise<{ status: string; timestamp: string; details: any }> {
    try {
      const result = await this.query('SELECT 1 as health, NOW() as timestamp');
      const connections = await this.query('SELECT count(*) as active_connections FROM pg_stat_activity');

      return {
        status: 'healthy',
        timestamp: result.rows[0].timestamp,
        details: {
          active_connections: parseInt(connections.rows[0].active_connections),
          total_connections: this.pool.totalCount,
          idle_connections: this.pool.idleCount,
          waiting_connections: this.pool.waitingCount
        }
      };
    } catch (error) {
      return {
        status: 'unhealthy',
        timestamp: new Date().toISOString(),
        details: { error: error.message }
      };
    }
  }

  // Memory Storage Methods (sync from Atom)
  async storeMemory(
    tenantId: string,
    type: string,
    content: string,
    metadata: any = {}
  ): Promise<any> {
    const result = await this.query(`
      INSERT INTO memories (
        id, tenant_id, type, content, metadata_json
      )
      VALUES ($1, $2, $3, $4, $5)
      RETURNING *
    `, [`mem_${Date.now()}_${Math.random().toString(36).substr(2, 5)}`, tenantId, type, content, metadata]);

    return result.rows[0];
  }

  async queryMemories(
    tenantId: string,
    query: string,
    limit: number = 5,
    typeFilter?: string
  ): Promise<any[]> {
    // Basic text search implementation since pgvector might not be installed
    let sql = `
      SELECT * FROM memories 
      WHERE tenant_id = $1 
      AND content ILIKE $2
    `;
    const params: any[] = [tenantId, `%${query}%`];
    let paramIndex = 3;

    if (typeFilter) {
      sql += ` AND type = $${paramIndex++}`;
      params.push(typeFilter);
    }

    sql += ` ORDER BY created_at DESC LIMIT $${paramIndex++}`;
    params.push(limit);

    const result = await this.query(sql, params);
    return result.rows;
  }

  async updateUser(userId: string, updates: {
    onboarding_completed?: boolean;
    name?: string;
    role?: string;
  }): Promise<void> {
    const setClauses: string[] = [];
    const params: any[] = [userId];
    let paramIndex = 2;

    if (updates.onboarding_completed !== undefined) {
      setClauses.push(`onboarding_completed = $${paramIndex++}`);
      params.push(updates.onboarding_completed);
    }

    if (updates.name) {
      setClauses.push(`name = $${paramIndex++}`);
      params.push(updates.name);
    }

    if (updates.role) {
      setClauses.push(`role = $${paramIndex++}`);
      params.push(updates.role);
    }

    if (setClauses.length === 0) return;

    await this.query(`
      UPDATE users 
      SET ${setClauses.join(', ')}, updated_at = NOW()
      WHERE id = $1
    `, params);
  }

  async updateTenantMemoryUsage(tenantId: string, bytes: number) {
    // Convert bytes to MB and add to existing usage
    const mbToAdd = bytes / (1024 * 1024);
    await this.query(`
      UPDATE tenants 
      SET memory_used_mb = COALESCE(memory_used_mb, 0) + $1,
          updated_at = NOW()
      WHERE id = $2
    `, [mbToAdd, tenantId]);
  }
}

// Singleton instance
let dbInstance: DatabaseService;

export function getDatabase(): DatabaseService {
  if (!dbInstance) {
    dbInstance = new DatabaseService();
  }
  return dbInstance;
}