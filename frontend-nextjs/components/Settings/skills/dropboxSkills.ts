/**
 * Dropbox connection helpers for the Settings UI.
 *
 * These functions were previously imported from `src/skills/dropboxSkills`,
 * which never existed in this repository — the import was unresolvable
 * (components/Settings/DropboxManager.tsx). They are re-created here against
 * the real API surface: GET/POST /api/integrations/credentials.
 */

export interface DropboxConnectionStatusInfo {
    isConnected: boolean;
    reason?: string;
}

export interface SkillResult<T> {
    ok: boolean;
    data?: T;
    error?: { message: string };
}

export async function getDropboxConnectionStatus(userId: string): Promise<SkillResult<DropboxConnectionStatusInfo>> {
    try {
        const response = await fetch('/api/integrations/credentials?service=dropbox');
        const data = await response.json();
        if (response.ok && data.isConnected) {
            return { ok: true, data: { isConnected: true } };
        }
        return { ok: true, data: { isConnected: false, reason: data.message || 'Not connected' } };
    } catch (error: any) {
        return { ok: false, error: { message: error?.message || 'Failed to get status' } };
    }
}

export async function disconnectDropbox(userId: string): Promise<SkillResult<null>> {
    try {
        const response = await fetch('/api/integrations/credentials', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ service: 'dropbox', secret: '' }),
        });
        if (response.ok) {
            return { ok: true, data: null };
        }
        return { ok: false, error: { message: 'Failed to disconnect' } };
    } catch (error: any) {
        return { ok: false, error: { message: error?.message || 'Exception during disconnect' } };
    }
}
