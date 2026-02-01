import { DatabaseService } from '../database'

export interface MemoryData {
    id: string
    type: string
    content: string
    embedding?: number[]
    metadata: any
    expires?: Date
    timestamp: Date
}

export interface StorageResult<T> {
    success: boolean
    data?: T
    error?: string
}

export class HybridMemoryAdapter {
    private baseUrl: string = '/api/ai/memory'

    async storeMemory(memory: Omit<MemoryData, 'id' | 'timestamp'>): Promise<StorageResult<MemoryData>> {
        try {
            const response = await fetch(this.baseUrl, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(memory)
            })
            if (!response.ok) throw new Error(await response.text())
            const data = await response.json()
            return { success: true, data }
        } catch (e: any) {
            return { success: false, error: e.message }
        }
    }

    async queryMemories(options: any): Promise<StorageResult<any>> {
        try {
            // This now returns the COMBO results: experiences, knowledge, formulas, conversations
            const query = new URLSearchParams(options).toString()
            const response = await fetch(`${this.baseUrl}/search?${query}`)
            if (!response.ok) throw new Error(await response.text())
            const data = await response.json()
            return { success: true, data }
        } catch (e: any) {
            return { success: false, error: e.message }
        }
    }

    async semanticSearch(embedding: number[], options: any = {}): Promise<StorageResult<any>> {
        // Redundant with queryMemories in the new backend architecture
        return this.queryMemories({ ...options, has_embedding: true })
    }

    async deleteMemory(memoryId: string): Promise<StorageResult<void>> {
        try {
            const response = await fetch(`${this.baseUrl}/${memoryId}`, { method: 'DELETE' })
            if (!response.ok) throw new Error(await response.text())
            return { success: true }
        } catch (e: any) {
            return { success: false, error: e.message }
        }
    }
}
