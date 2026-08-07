/**
 * Shopify connection helpers for the Settings UI.
 *
 * These functions were previously imported from `src/skills/shopifySkills`,
 * which never existed in this repository — the import was unresolvable
 * (components/Settings/ShopifyManager.tsx). They are re-created here against
 * the real API surface: GET/POST /api/integrations/credentials.
 */

export interface ShopifyConnectionStatusInfo {
    isConnected: boolean;
    reason?: string;
    shopUrl?: string;
}

export interface SkillResult<T> {
    ok: boolean;
    data?: T;
    error?: { message: string };
}

export async function getShopifyConnectionStatus(userId: string): Promise<SkillResult<ShopifyConnectionStatusInfo>> {
    try {
        const response = await fetch('/api/integrations/credentials?service=shopify');
        const data = await response.json();
        if (response.ok && data.isConnected) {
            return { ok: true, data: { isConnected: true, shopUrl: data.value || undefined } };
        }
        return { ok: true, data: { isConnected: false, reason: data.message || 'Not connected' } };
    } catch (error: any) {
        return { ok: false, error: { message: error?.message || 'Failed to get status' } };
    }
}

export async function disconnectShopify(userId: string): Promise<SkillResult<null>> {
    try {
        const response = await fetch('/api/integrations/credentials', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ service: 'shopify', secret: '' }),
        });
        if (response.ok) {
            return { ok: true, data: null };
        }
        return { ok: false, error: { message: 'Failed to disconnect' } };
    } catch (error: any) {
        return { ok: false, error: { message: error?.message || 'Exception during disconnect' } };
    }
}
