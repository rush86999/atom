/**
 * Google Drive connection helpers for the Settings UI.
 *
 * These functions were previously imported from `src/skills/gdriveSkills`,
 * which never existed in this repository — the import was unresolvable
 * (components/Settings/GDriveManager.tsx). They are re-created here against
 * the real API surface: GET/POST /api/integrations/credentials.
 */

export interface GDriveConnectionStatusInfo {
    isConnected: boolean;
    reason?: string;
}

export interface SkillResult<T> {
    ok: boolean;
    data?: T;
    error?: { message: string };
}

export async function getGDriveConnectionStatus(userId: string): Promise<SkillResult<GDriveConnectionStatusInfo>> {
    try {
        const response = await fetch('/api/integrations/credentials?service=gdrive');
        const data = await response.json();
        if (response.ok && data.isConnected) {
            return { ok: true, data: { isConnected: true } };
        }
        return { ok: true, data: { isConnected: false, reason: data.message || 'Not connected' } };
    } catch (error: any) {
        return { ok: false, error: { message: error?.message || 'Failed to get status' } };
    }
}

export async function disconnectGDrive(userId: string): Promise<SkillResult<null>> {
    try {
        const response = await fetch('/api/integrations/credentials', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ service: 'gdrive', secret: '' }),
        });
        if (response.ok) {
            return { ok: true, data: null };
        }
        return { ok: false, error: { message: 'Failed to disconnect' } };
    } catch (error: any) {
        return { ok: false, error: { message: error?.message || 'Exception during disconnect' } };
    }
}
