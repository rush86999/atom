import { EventEmitter } from 'events'
import { HybridMemoryAdapter, MemoryData } from './memory-storage-adapter'
import { TenantService } from '../tenant/tenant-service'

export interface UnifiedMemoryQuery {
    type?: string
    limit?: number
    includeExpired?: boolean
}

export class UnifiedMemorySystem extends EventEmitter {
    private adapter: HybridMemoryAdapter
    private tenantService: TenantService
    private initialized = false

    constructor(adapter: HybridMemoryAdapter, tenantService: TenantService) {
        super()
        this.adapter = adapter
        this.tenantService = tenantService
    }

    async initialize() {
        this.initialized = true
        this.emit('initialized')
    }

    async store(tenantId: string, memory: Omit<MemoryData, 'id' | 'timestamp'>) {
        this.ensureInitialized()

        // 1. Check Tier Limits
        const canStore = await this.tenantService.checkMemoryLimit(tenantId, this.calculateSize(memory.content))
        if (!canStore) {
            throw new Error('Memory context limit exceeded for your tier.')
        }

        // 2. Store via Adapter
        const result = await this.adapter.storeMemory(memory)
        if (!result.success) throw new Error(result.error)

        this.emit('memory_stored', result.data)
        return result.data
    }

    async query(query: UnifiedMemoryQuery) {
        this.ensureInitialized()
        const result = await this.adapter.queryMemories(query)
        if (!result.success) throw new Error(result.error)
        return result.data
    }

    async delete(memoryId: string) {
        this.ensureInitialized()
        const result = await this.adapter.deleteMemory(memoryId)
        if (!result.success) throw new Error(result.error)
        return true
    }

    private ensureInitialized() {
        if (!this.initialized) throw new Error('Memory system not initialized')
    }

    private calculateSize(content: string): number {
        return Buffer.byteLength(content, 'utf8')
    }
}
