import { v4 as uuidv4 } from 'uuid';
import { getDatabase } from '../database';
import { DocumentParser } from './document-parser';
import { UnifiedMemorySystem } from './unified-memory';
import { HybridMemoryAdapter } from './memory-storage-adapter';
import { TenantService } from '../tenant/tenant-service';
import { EmailService } from '../email';
import { zohoWorkDriveService } from '../integrations/zoho';

export enum IntegrationSource {
    GOOGLE_DRIVE = "google_drive",
    DROPBOX = "dropbox",
    ZOHO_WORKDRIVE = "zoho_workdrive",
    LOCAL = "local",
}

export interface IngestionSettings {
    enabled: boolean;
    autoSync: boolean;
    fileTypes: string[];
    maxFileSizeMb: number;
    syncFrequencyMinutes: number;
    lastSync?: Date;
}

export class AutoDocumentIngestionService {
    private tenantId: string;
    private memorySystem: UnifiedMemorySystem;

    constructor(tenantId: string) {
        this.tenantId = tenantId;

        const db = getDatabase();
        const adapter = new HybridMemoryAdapter();
        // EmailService is needed for TenantService, but for ingestion we only need checkMemoryLimit
        const emailService = new EmailService();
        const tenantService = new TenantService(db, emailService);

        this.memorySystem = new UnifiedMemorySystem(adapter, tenantService);
    }

    /**
     * Get ingestion settings for a specific integration
     */
    async getSettings(provider: string): Promise<IngestionSettings> {
        const db = getDatabase();
        const result = await db.query(
            `SELECT settings FROM ingestion_settings WHERE tenant_id = $1 AND provider = $2`,
            [this.tenantId, provider]
        );

        if (result.rows.length > 0) {
            return result.rows[0].settings;
        }

        // Default settings
        return {
            enabled: false,
            autoSync: true,
            fileTypes: ['pdf', 'docx', 'txt', 'md'],
            maxFileSizeMb: 50,
            syncFrequencyMinutes: 60
        };
    }

    /**
     * Sync documents from Zoho WorkDrive
     */
    async syncZohoWorkDrive(): Promise<{ success: boolean; count: number; error?: string }> {
        const settings = await this.getSettings('zoho_workdrive');
        if (!settings.enabled) {
            return { success: false, count: 0, error: "Integration not enabled" };
        }

        try {
            await this.memorySystem.initialize();
            const files = await zohoWorkDriveService.listFiles(this.tenantId);
            let ingestedCount = 0;

            for (const file of files) {
                const db = getDatabase();
                const existing = await db.query(
                    `SELECT id FROM ingested_documents WHERE tenant_id = $1 AND external_id = $2`,
                    [this.tenantId, file.id]
                );

                if (existing.rows.length > 0) continue;

                const content = await zohoWorkDriveService.downloadFile(this.tenantId, file.id);
                if (!content) continue;

                const text = await DocumentParser.parseDocument(content, file.extension || 'txt', file.name);
                if (!text) continue;

                // Store in memory system
                await this.memorySystem.store(this.tenantId, {
                    type: 'document',
                    content: text,
                    metadata: {
                        fileName: file.name,
                        source: 'zoho_workdrive',
                        externalId: file.id,
                        ingestedAt: new Date().toISOString()
                    }
                });

                // Record in DB
                await db.query(
                    `INSERT INTO ingested_documents (id, tenant_id, file_name, file_type, source, size_bytes, content_preview, external_id, ingested_at)
                     VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())`,
                    [uuidv4(), this.tenantId, file.name, file.extension || 'txt', 'zoho_workdrive', file.size || 0, text.substring(0, 500), file.id]
                );

                ingestedCount++;
            }

            return { success: true, count: ingestedCount };
        } catch (error: any) {
            console.error('Zoho sync failed:', error);
            return { success: false, count: 0, error: error.message };
        }
    }
}
