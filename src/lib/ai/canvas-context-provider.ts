import { DatabaseService } from '../database'

export interface ArtifactComment {
    id: string
    artifact_id: string
    user_id: string
    author_name: string
    content: string
    created_at: Date
}

export interface CanvasContext {
    canvas_id: string
    artifact_count: number
    recent_artifacts: Array<{
        id: string
        name: string
        type: string
        updated_at: Date
    }>
    comments: ArtifactComment[]
    metadata?: any
}

export class CanvasContextProvider {
    private db: DatabaseService
    private cache: Map<string, { context: CanvasContext; timestamp: number }> = new Map()
    private readonly CACHE_TTL = 30000 // 30 seconds

    constructor(db: DatabaseService) {
        this.db = db
    }

    async getCanvasContext(tenantId: string, canvasId: string): Promise<CanvasContext | null> {
        const cacheKey = `${tenantId}:${canvasId}`
        const cached = this.cache.get(cacheKey)

        if (cached && Date.now() - cached.timestamp < this.CACHE_TTL) {
            return cached.context
        }

        try {
            // 1. Fetch Canvas details
            const canvasResult = await this.db.query(
                'SELECT id, metadata_json FROM canvases WHERE id = $1 AND tenant_id = $2',
                [canvasId, tenantId]
            )

            if (canvasResult.rows.length === 0) return null

            const canvas = canvasResult.rows[0]

            // 2. Fetch Artifacts
            const artifactsResult = await this.db.query(
                'SELECT id, name, type, updated_at FROM artifacts WHERE canvas_id = $1 AND tenant_id = $2 ORDER BY updated_at DESC LIMIT 10',
                [canvasId, tenantId]
            )

            const recentArtifacts = artifactsResult.rows.map((a: any) => ({
                id: a.id,
                name: a.name,
                type: a.type,
                updated_at: new Date(a.updated_at)
            }))

            // 3. Fetch Comments for these artifacts
            const artifactIds = recentArtifacts.map(a => a.id)
            let comments: ArtifactComment[] = []

            if (artifactIds.length > 0) {
                const commentsResult = await this.db.query(`
                    SELECT ac.id, ac.artifact_id, ac.user_id, u.name as author_name, ac.content, ac.created_at
                    FROM artifact_comments ac
                    JOIN users u ON ac.user_id = u.id
                    WHERE ac.artifact_id = ANY($1)
                    ORDER BY ac.created_at DESC
                    LIMIT 50
                `, [artifactIds])

                comments = commentsResult.rows.map((c: any) => ({
                    id: c.id,
                    artifact_id: c.artifact_id,
                    user_id: c.user_id,
                    author_name: c.author_name,
                    content: c.content,
                    created_at: new Date(c.created_at)
                }))
            }

            const context: CanvasContext = {
                canvas_id: canvasId,
                artifact_count: recentArtifacts.length,
                recent_artifacts: recentArtifacts,
                comments: comments,
                metadata: canvas.metadata_json
            }

            this.cache.set(cacheKey, { context, timestamp: Date.now() })
            return context

        } catch (error) {
            console.error('Error fetching canvas context:', error)
            return null
        }
    }

    formatForPrompt(context: CanvasContext): string {
        let text = `CURRENT CANVAS (${context.canvas_id}):\n`

        if (context.recent_artifacts.length > 0) {
            text += `Artifacts:\n${context.recent_artifacts.map(a => `- ${a.name} (${a.type})`).join('\n')}\n`
        }

        if (context.comments.length > 0) {
            text += `Recent Comments:\n${context.comments.slice(0, 10).map(c => `- ${c.author_name}: "${c.content}"`).join('\n')}\n`
        }

        return text
    }

    invalidateCache(tenantId: string, canvasId: string) {
        this.cache.delete(`${tenantId}:${canvasId}`)
    }
}
