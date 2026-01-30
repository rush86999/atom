import { getDatabase, DatabaseService } from '@/lib/database';
import { v4 as uuidv4 } from 'uuid';
import jwt from 'jsonwebtoken';

const JWT_SECRET = process.env.JWT_SECRET || 'desktop-auth-secret';

export interface DesktopSession {
    id: string;
    tenantId: string;
    deviceId: string;
    platform: string;
    token: string;
    expiresAt: Date;
}

export interface DesktopAction {
    id: string;
    type: 'file_operation' | 'command_execution' | 'agent_action' | 'computer_use';
    action: string;
    metadata?: Record<string, unknown>;
    timestamp: string;
    success: boolean;
    durationMs?: number;
}

export interface ByokKeyInfo {
    provider: string;
    apiKey: string;
    isValid: boolean;
}

/**
 * Service for managing desktop client connections and operations
 * Enables Tauri desktop app to authenticate and operate via SaaS subscriptions
 */
export class DesktopClientService {
    private db: DatabaseService;

    constructor() {
        this.db = getDatabase();
    }

    /**
     * Authenticate desktop app with API key
     * Returns session info and BYOK keys for the tenant
     */
    async authenticateDesktopApp(
        apiKey: string,
        deviceId?: string,
        platform?: string
    ): Promise<{ session: DesktopSession; tenant: Record<string, unknown> } | null> {
        // Validate API key
        const tenant = await this.db.query(
            `SELECT t.*, u.email, u.name 
       FROM tenants t 
       JOIN users u ON t.user_id = u.id 
       WHERE t.api_key = $1 AND t.status = 'active'`,
            [apiKey]
        );

        if (tenant.rows.length === 0) {
            return null;
        }

        const tenantData = tenant.rows[0];
        const sessionId = uuidv4();
        const expiresAt = new Date(Date.now() + 7 * 24 * 60 * 60 * 1000); // 7 days

        // Create or update session
        await this.db.query(
            `INSERT INTO desktop_sessions (id, tenant_id, device_id, platform, last_active)
       VALUES ($1, $2, $3, $4, NOW())
       ON CONFLICT (tenant_id, device_id) 
       DO UPDATE SET last_active = NOW(), platform = EXCLUDED.platform, id = EXCLUDED.id`,
            [sessionId, tenantData.id, deviceId || 'unknown', platform || 'unknown']
        );

        // Generate JWT
        const token = jwt.sign(
            {
                tenantId: tenantData.id,
                userId: tenantData.user_id,
                sessionId,
                type: 'desktop',
            },
            JWT_SECRET,
            { expiresIn: '7d' }
        );

        return {
            session: {
                id: sessionId,
                tenantId: tenantData.id,
                deviceId: deviceId || 'unknown',
                platform: platform || 'unknown',
                token,
                expiresAt,
            },
            tenant: {
                id: tenantData.id,
                tier: tenantData.tier,
                memoryLimitMb: tenantData.memory_limit_mb,
                maxAgents: tenantData.max_agents,
                syncFrequency: tenantData.sync_frequency,
                email: tenantData.email,
                name: tenantData.name,
            },
        };
    }

    /**
     * Get BYOK keys for desktop agent to use
     * Returns full keys (desktop needs them for local LLM calls)
     */
    async getByokKeysForDesktop(tenantId: string): Promise<ByokKeyInfo[]> {
        const result = await this.db.query(
            `SELECT provider, api_key, is_valid 
       FROM byok_keys 
       WHERE tenant_id = $1 AND is_valid = true`,
            [tenantId]
        );

        return result.rows.map((row: { provider: string; api_key: string; is_valid: boolean }) => ({
            provider: row.provider,
            apiKey: row.api_key,
            isValid: row.is_valid,
        }));
    }

    /**
     * Record actions from desktop for billing and governance
     */
    async syncActions(
        tenantId: string,
        sessionId: string,
        actions: DesktopAction[]
    ): Promise<number> {
        let recordedCount = 0;

        for (const action of actions) {
            await this.db.query(
                `INSERT INTO desktop_actions (
          id, tenant_id, session_id, action_type, action_name,
          metadata, timestamp, success, duration_ms
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        ON CONFLICT (id) DO NOTHING`,
                [
                    action.id || uuidv4(),
                    tenantId,
                    sessionId,
                    action.type,
                    action.action,
                    JSON.stringify(action.metadata || {}),
                    action.timestamp || new Date().toISOString(),
                    action.success,
                    action.durationMs || 0,
                ]
            );
            recordedCount++;
        }

        // Update session activity
        await this.db.query(
            `UPDATE desktop_sessions SET last_active = NOW() WHERE id = $1`,
            [sessionId]
        );

        // Update Computer Use count for billing
        const computerUseCount = actions.filter(a => a.type === 'computer_use').length;
        if (computerUseCount > 0) {
            await this.db.query(
                `UPDATE tenants 
         SET computer_use_count = COALESCE(computer_use_count, 0) + $1,
             last_desktop_sync = NOW()
         WHERE id = $2`,
                [computerUseCount, tenantId]
            );
        }

        return recordedCount;
    }

    /**
     * Validate session token
     */
    validateToken(token: string): { tenantId: string; userId: string; sessionId: string } | null {
        try {
            return jwt.verify(token, JWT_SECRET) as {
                tenantId: string;
                userId: string;
                sessionId: string;
            };
        } catch {
            return null;
        }
    }

    /**
     * Get active desktop sessions for a tenant
     */
    async getActiveSessions(tenantId: string): Promise<{
        id: string;
        deviceId: string;
        platform: string;
        lastActive: Date;
    }[]> {
        const result = await this.db.query(
            `SELECT id, device_id, platform, last_active 
       FROM desktop_sessions 
       WHERE tenant_id = $1 AND last_active > NOW() - INTERVAL '7 days'
       ORDER BY last_active DESC`,
            [tenantId]
        );

        return result.rows.map((row: { id: string; device_id: string; platform: string; last_active: Date }) => ({
            id: row.id,
            deviceId: row.device_id,
            platform: row.platform,
            lastActive: row.last_active,
        }));
    }

    /**
     * Get usage stats for Computer Use Agent
     */
    async getComputerUseStats(tenantId: string): Promise<{
        totalActions: number;
        todayActions: number;
        computerUseActions: number;
    }> {
        const total = await this.db.query(
            `SELECT COUNT(*) as count FROM desktop_actions WHERE tenant_id = $1`,
            [tenantId]
        );

        const today = await this.db.query(
            `SELECT COUNT(*) as count FROM desktop_actions 
       WHERE tenant_id = $1 AND timestamp > NOW() - INTERVAL '24 hours'`,
            [tenantId]
        );

        const computerUse = await this.db.query(
            `SELECT COUNT(*) as count FROM desktop_actions 
       WHERE tenant_id = $1 AND action_type = 'computer_use'`,
            [tenantId]
        );

        return {
            totalActions: parseInt(total.rows[0].count),
            todayActions: parseInt(today.rows[0].count),
            computerUseActions: parseInt(computerUse.rows[0].count),
        };
    }
}
