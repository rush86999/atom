import axios from 'axios'
import { streamText, generateText } from 'ai'
import { createOpenAI } from '@ai-sdk/openai'
// import { DatabaseService } from '../database' // Commented out for Upstream

export interface LLMRequest {
    model: string
    messages: any[]
    temperature?: number
    type?: 'chat' | 'nlp' | 'vision' | 'prediction' | 'analysis' | 'code' | 'creative' | 'agent_execution'
    context?: Record<string, any>
    stream?: boolean
}

export type ProviderType =
    | 'openai' | 'anthropic' | 'gemini'           // Big 3
    | 'deepseek' | 'qwen' | 'zhipu' | 'baichuan'  // Chinese LLMs
    | 'mistral' | 'cohere' | 'groq'               // Popular Open-Source/Speed

export interface ProviderConfig {
    name: string
    provider: ProviderType
    supports: string[]
    model: string
    costTier: 'low' | 'medium' | 'high'
}

export class LLMRouter {
    private db?: any // Made optional for Upstream standalone use

    private providers: ProviderConfig[] = [
        // --- Big 3 ---
        { name: 'gpt-4o', provider: 'openai', supports: ['chat', 'analysis', 'nlp', 'code', 'vision'], model: 'gpt-4o', costTier: 'high' },
        { name: 'gpt-4o-mini', provider: 'openai', supports: ['chat', 'nlp', 'code'], model: 'gpt-4o-mini', costTier: 'low' },
        { name: 'claude-3.5-sonnet', provider: 'anthropic', supports: ['chat', 'analysis', 'creative', 'code'], model: 'claude-3-5-sonnet-20241022', costTier: 'high' },
        { name: 'claude-3-haiku', provider: 'anthropic', supports: ['chat', 'nlp'], model: 'claude-3-haiku-20240307', costTier: 'low' },
        { name: 'gemini-2.0-flash', provider: 'gemini', supports: ['chat', 'nlp', 'vision'], model: 'gemini-2.0-flash-exp', costTier: 'medium' },

        // --- Chinese LLMs ---
        { name: 'deepseek-chat', provider: 'deepseek', supports: ['chat', 'analysis', 'nlp', 'code'], model: 'deepseek-chat', costTier: 'low' },
        { name: 'deepseek-reasoner', provider: 'deepseek', supports: ['analysis', 'code'], model: 'deepseek-reasoner', costTier: 'medium' },
        { name: 'qwen-turbo', provider: 'qwen', supports: ['chat', 'nlp', 'code'], model: 'qwen-turbo', costTier: 'low' },
        { name: 'qwen-plus', provider: 'qwen', supports: ['chat', 'analysis', 'nlp'], model: 'qwen-plus', costTier: 'medium' },
        { name: 'glm-4', provider: 'zhipu', supports: ['chat', 'nlp', 'analysis'], model: 'glm-4', costTier: 'medium' },
        { name: 'baichuan-turbo', provider: 'baichuan', supports: ['chat', 'nlp'], model: 'Baichuan2-Turbo', costTier: 'low' },

        // --- Popular Providers ---
        { name: 'mistral-large', provider: 'mistral', supports: ['chat', 'analysis', 'code'], model: 'mistral-large-latest', costTier: 'high' },
        { name: 'mistral-small', provider: 'mistral', supports: ['chat', 'nlp'], model: 'mistral-small-latest', costTier: 'low' },
        { name: 'command-r-plus', provider: 'cohere', supports: ['chat', 'analysis', 'nlp'], model: 'command-r-plus', costTier: 'medium' },
        { name: 'llama-3.3-70b', provider: 'groq', supports: ['chat', 'nlp', 'code'], model: 'llama-3.3-70b-versatile', costTier: 'low' },
    ]

    constructor(db?: any) {
        this.db = db
    }

    // Cost per 1M tokens (input/output averaged)
    private providerCosts: Record<string, { input: number; output: number }> = {
        openai: { input: 2.50, output: 10.00 },      // GPT-4o average
        anthropic: { input: 3.00, output: 15.00 },  // Claude 3.5
        gemini: { input: 0.075, output: 0.30 },     // Gemini Flash
        deepseek: { input: 0.14, output: 0.28 },    // DeepSeek
        qwen: { input: 0.50, output: 1.00 },        // Qwen
        zhipu: { input: 1.00, output: 2.00 },       // GLM-4
        baichuan: { input: 0.50, output: 1.00 },    // Baichuan
        mistral: { input: 2.00, output: 6.00 },     // Mistral Large
        cohere: { input: 0.50, output: 1.50 },      // Command-R
        groq: { input: 0.05, output: 0.10 },        // Llama via Groq (fast)
    }

    async call(
        tenantId: string,
        request: LLMRequest,
        callbacks?: { onFinish?: (content: string, usage?: any) => Promise<void> }
    ) {
        // ... (existing code)
        // Check tenant's AI mode
        let aiMode = 'byok'
        if (this.db) {
            const tenant = await this.db.query(
                'SELECT ai_mode FROM tenants WHERE id = $1',
                [tenantId]
            )
            aiMode = tenant.rows[0]?.ai_mode || 'byok'
        }

        const complexity = this.calculateComplexity(request)
        const provider = await this.selectProvider(tenantId, request.type || 'nlp', complexity, aiMode)

        let apiKey: string | null = null;
        if (aiMode === 'managed' || aiMode === 'hybrid') {
            apiKey = this.getPlatformApiKey(provider.provider)
        }
        if (!apiKey && (aiMode === 'byok' || aiMode === 'hybrid')) {
            apiKey = await this.getTenantApiKey(tenantId, provider.provider)
        }
        if (!apiKey) {
            throw new Error(`No API key found for ${provider.provider}. Please configure BYOK or enable Managed AI.`)
        }

        const onUsage = async (usage: any, content: string) => {
            // 1. Internal Billing Tracking
            if (aiMode === 'managed' || aiMode === 'hybrid') {
                await this.trackTokenUsage(tenantId, provider, {
                    inputTokens: usage.promptTokens,
                    outputTokens: usage.completionTokens,
                    content: content,
                    model: provider.model,
                    provider: provider.provider
                })
            }

            // 2. Caller Callbacks (e.g. Save to Chat History)
            if (callbacks?.onFinish) {
                await callbacks.onFinish(content, usage);
            }
        }

        const result = await this.executeCall(apiKey, provider, request, onUsage)

        // For non-streaming (legacy), we might still need to track if onUsage wasn't called manually
        // But for consistency, let's let executeCall invoke the callback if it can, 
        // OR we do it here if result is standard object.

        if (!request.stream && (aiMode === 'managed' || aiMode === 'hybrid')) {
            // TS Guard: Check if result is not a stream (has 'content')
            if ('content' in result) {
                await this.trackTokenUsage(tenantId, provider, result as any)
            }
        }

        // Ensure onFinish is called for non-streaming as well
        if (!request.stream && callbacks?.onFinish && 'content' in result) {
            await callbacks.onFinish((result as any).content, (result as any).usage);
        }

        return result
    }

    async getEmbedding(tenantId: string, text: string): Promise<number[]> {
        // Check mode/key similar to call()
        let aiMode = 'byok';
        if (this.db) {
            const tenant = await this.db.query('SELECT ai_mode FROM tenants WHERE id = $1', [tenantId]);
            aiMode = tenant.rows[0]?.ai_mode || 'byok';
        }

        let apiKey: string | null = null;
        if (aiMode === 'managed' || aiMode === 'hybrid') apiKey = this.getPlatformApiKey('openai');
        if (!apiKey) apiKey = await this.getTenantApiKey(tenantId, 'openai');

        if (!apiKey) throw new Error('No OpenAI API key found for embeddings.');

        // Mock Support
        if (apiKey.startsWith('TEST_')) {
            return new Array(1536).fill(0.1);
        }

        try {
            const response = await axios.post(
                'https://api.openai.com/v1/embeddings',
                { model: 'text-embedding-3-small', input: text },
                { headers: { 'Authorization': `Bearer ${apiKey}`, 'Content-Type': 'application/json' } }
            );
            return response.data.data[0].embedding;
        } catch (e: any) {
            console.error('Embedding call failed:', e.message);
            throw new Error('Failed to generate embedding');
        }
    }

    private getPlatformApiKey(provider: string): string | null {
        const envMap: Record<string, string> = {
            openai: 'PLATFORM_OPENAI_API_KEY',
            anthropic: 'PLATFORM_ANTHROPIC_API_KEY',
            gemini: 'PLATFORM_GEMINI_API_KEY',
            deepseek: 'PLATFORM_DEEPSEEK_API_KEY',
            qwen: 'PLATFORM_QWEN_API_KEY',
            zhipu: 'PLATFORM_ZHIPU_API_KEY',
            baichuan: 'PLATFORM_BAICHUAN_API_KEY',
            mistral: 'PLATFORM_MISTRAL_API_KEY',
            cohere: 'PLATFORM_COHERE_API_KEY',
            groq: 'PLATFORM_GROQ_API_KEY',
        }
        return process.env[envMap[provider]] || null
    }

    private async trackTokenUsage(
        tenantId: string,
        provider: ProviderConfig,
        result: { inputTokens?: number; outputTokens?: number; content: string; model: string; provider: string }
    ) {
        if (!this.db) return

        const inputTokens = result.inputTokens || Math.ceil(result.content.length / 4)
        const outputTokens = result.outputTokens || Math.ceil(result.content.length / 4)

        const costs = this.providerCosts[provider.provider] || { input: 1, output: 2 }
        const costUsd = (inputTokens * costs.input + outputTokens * costs.output) / 1_000_000

        await this.db.query(
            `INSERT INTO token_usage (tenant_id, provider, model, input_tokens, output_tokens, cost_usd)
             VALUES ($1, $2, $3, $4, $5, $6)`,
            [tenantId, provider.provider, provider.model, inputTokens, outputTokens, costUsd]
        )
    }

    private calculateComplexity(request: LLMRequest): number {
        let score = 0
        const text = request.messages.map(m => m.content).join(' ')
        score += Math.min(text.length / 5000, 0.5)
        if (request.type === 'analysis') score += 0.3
        if (request.type === 'code') score += 0.2
        if (request.context?.businessImportance === 'high') score += 0.2
        return Math.min(score, 1)
    }

    private async selectProvider(tenantId: string, type: string, complexity: number, aiMode: string): Promise<ProviderConfig> {
        // Find providers that support this type
        const caps = this.providers.filter(p => p.supports.includes(type))

        const availableProviders: ProviderConfig[] = []

        if (aiMode === 'managed' || aiMode === 'hybrid') {
            // For Managed AI, we assume all configured providers are available (via platform keys)
            availableProviders.push(...caps)
        } else {
            // For BYOK, check which providers the tenant has keys for
            for (const p of caps) {
                const hasKey = await this.getTenantApiKey(tenantId, p.provider)
                if (hasKey) availableProviders.push(p)
            }
        }

        if (availableProviders.length === 0) {
            // Fallback: return first matching (will fail at key check if BYOK)
            return caps[0] || this.providers[0]
        }

        // Sort by Cost (Cheapest first)
        // We use a simple weighted average of input/output to determine "base cost"
        availableProviders.sort((a, b) => {
            const costA = this.providerCosts[a.provider] || { input: 10, output: 30 }
            const costB = this.providerCosts[b.provider] || { input: 10, output: 30 }
            const avgA = (costA.input + costA.output) / 2
            const avgB = (costB.input + costB.output) / 2
            return avgA - avgB
        })

        // Filter by Complexity
        let candidates = availableProviders

        if (complexity > 0.7) {
            // High complexity: Prefer High/Medium tier, but allow cheapest High/Medium
            candidates = availableProviders.filter(p => p.costTier === 'high' || p.costTier === 'medium')
            // If no high/medium available (unlikely), fall back to any
            if (candidates.length === 0) candidates = availableProviders
        } else if (complexity < 0.3) {
            // Low complexity: Strongly prefer Low tier (DeepSeek, Qwen, etc.)
            candidates = availableProviders.filter(p => p.costTier === 'low')
            // If no low tier, allow medium
            if (candidates.length === 0) candidates = availableProviders.filter(p => p.costTier === 'medium')
            if (candidates.length === 0) candidates = availableProviders
        } else {
            // Medium complexity: Prefer Low/Medium
            candidates = availableProviders.filter(p => p.costTier === 'low' || p.costTier === 'medium')
            if (candidates.length === 0) candidates = availableProviders
        }

        // Return the first one (which is the cheapest due to sorting)
        return candidates[0]
    }

    private async getTenantApiKey(tenantId: string, provider: string): Promise<string | null> {
        const key = `${provider.toUpperCase()}_API_KEY`

        // Fallback to env variable if no DB (Standard Upstream behavior)
        if (!this.db) {
            return process.env[key] || null
        }

        const setting = await this.db.query(
            'SELECT setting_value FROM tenant_settings WHERE tenant_id = $1 AND setting_key = $2',
            [tenantId, key]
        )
        return setting.rows[0]?.setting_value || null
    }

    private async executeCall(
        apiKey: string,
        config: ProviderConfig,
        request: LLMRequest,
        onUsage?: (usage: any, content: string) => Promise<void>
    ) {
        console.log(`[BYOK Router] Routing to ${config.provider} (${config.model}) for tenant workflow`)

        // Mock Support for Testing
        if (apiKey.startsWith('TEST_')) {
            // ... (mock logic)
            return {
                content: "Mock response",
                model: config.model,
                provider: config.provider,
                usage: { total_tokens: 10 }
            };
        }

        try {
            switch (config.provider) {
                case 'openai':
                    return await this.callOpenAI(apiKey, config, request, onUsage)
                case 'anthropic':
                    return await this.callAnthropic(apiKey, config, request)
                case 'gemini':
                    return await this.callGemini(apiKey, config, request)
                case 'deepseek':
                    return await this.callDeepSeek(apiKey, config, request)
                case 'qwen':
                    return await this.callQwen(apiKey, config, request)
                case 'zhipu':
                    return await this.callZhipu(apiKey, config, request)
                case 'baichuan':
                    return await this.callBaichuan(apiKey, config, request)
                case 'mistral':
                    return await this.callMistral(apiKey, config, request)
                case 'cohere':
                    return await this.callCohere(apiKey, config, request)
                case 'groq':
                    return await this.callGroq(apiKey, config, request)
                default:
                    throw new Error(`Unsupported provider: ${config.provider}`)
            }
        } catch (e: any) {
            console.error(`BYOK ${config.provider} call failed:`, e.response?.data || e.message)
            throw new Error(`BYOK ${config.provider} call failed: ${e.response?.data?.error?.message || e.message}`)
        }
    }

    // --- Provider Implementations ---

    private async callOpenAI(
        apiKey: string,
        config: ProviderConfig,
        request: LLMRequest,
        onUsage?: (usage: any, content: string) => Promise<void>
    ) {
        const openai = createOpenAI({
            apiKey: apiKey,
        })

        if (request.stream) {
            // Using Vercel AI SDK Core 'streamText'
            const result = await streamText({
                model: openai(config.model),
                messages: request.messages,
                temperature: request.temperature ?? 0.7,
                onFinish: async ({ text, usage }) => {
                    if (onUsage) {
                        await onUsage(usage, text);
                    }
                }
            })
            return result
        }

        const { text, usage } = await generateText({
            model: openai(config.model),
            messages: request.messages,
            temperature: request.temperature ?? 0.7,
        })

        return { content: text, model: config.model, provider: config.provider, usage: usage }
    }

    private async callAnthropic(apiKey: string, config: ProviderConfig, request: LLMRequest) {
        const response = await axios.post(
            'https://api.anthropic.com/v1/messages',
            { model: config.model, max_tokens: 4096, messages: request.messages.map(m => ({ role: m.role === 'system' ? 'user' : m.role, content: m.content })) },
            { headers: { 'x-api-key': apiKey, 'anthropic-version': '2023-06-01', 'Content-Type': 'application/json' } }
        )
        return { content: response.data.content[0].text, model: config.model, provider: config.provider, usage: response.data.usage }
    }

    private async callGemini(apiKey: string, config: ProviderConfig, request: LLMRequest) {
        const response = await axios.post(
            `https://generativelanguage.googleapis.com/v1beta/models/${config.model}:generateContent?key=${apiKey}`,
            { contents: request.messages.map(m => ({ role: m.role === 'assistant' ? 'model' : 'user', parts: [{ text: m.content }] })) }
        )
        return { content: response.data.candidates[0].content.parts[0].text, model: config.model, provider: config.provider }
    }

    // --- Chinese LLM Providers ---

    private async callDeepSeek(apiKey: string, config: ProviderConfig, request: LLMRequest) {
        const response = await axios.post(
            'https://api.deepseek.com/v1/chat/completions',
            { model: config.model, messages: request.messages, temperature: request.temperature ?? 0.7 },
            { headers: { 'Authorization': `Bearer ${apiKey}`, 'Content-Type': 'application/json' } }
        )
        return { content: response.data.choices[0].message.content, model: config.model, provider: config.provider, usage: response.data.usage }
    }

    private async callQwen(apiKey: string, config: ProviderConfig, request: LLMRequest) {
        // Alibaba Qwen/Tongyi API (DashScope)
        const response = await axios.post(
            'https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation',
            { model: config.model, input: { messages: request.messages }, parameters: { temperature: request.temperature ?? 0.7 } },
            { headers: { 'Authorization': `Bearer ${apiKey}`, 'Content-Type': 'application/json' } }
        )
        return { content: response.data.output.text, model: config.model, provider: config.provider }
    }

    private async callZhipu(apiKey: string, config: ProviderConfig, request: LLMRequest) {
        // Zhipu AI (GLM)
        const response = await axios.post(
            'https://open.bigmodel.cn/api/paas/v4/chat/completions',
            { model: config.model, messages: request.messages, temperature: request.temperature ?? 0.7 },
            { headers: { 'Authorization': `Bearer ${apiKey}`, 'Content-Type': 'application/json' } }
        )
        return { content: response.data.choices[0].message.content, model: config.model, provider: config.provider, usage: response.data.usage }
    }

    private async callBaichuan(apiKey: string, config: ProviderConfig, request: LLMRequest) {
        const response = await axios.post(
            'https://api.baichuan-ai.com/v1/chat/completions',
            { model: config.model, messages: request.messages, temperature: request.temperature ?? 0.7 },
            { headers: { 'Authorization': `Bearer ${apiKey}`, 'Content-Type': 'application/json' } }
        )
        return { content: response.data.choices[0].message.content, model: config.model, provider: config.provider }
    }

    // --- Popular Providers ---

    private async callMistral(apiKey: string, config: ProviderConfig, request: LLMRequest) {
        const response = await axios.post(
            'https://api.mistral.ai/v1/chat/completions',
            { model: config.model, messages: request.messages, temperature: request.temperature ?? 0.7 },
            { headers: { 'Authorization': `Bearer ${apiKey}`, 'Content-Type': 'application/json' } }
        )
        return { content: response.data.choices[0].message.content, model: config.model, provider: config.provider, usage: response.data.usage }
    }

    private async callCohere(apiKey: string, config: ProviderConfig, request: LLMRequest) {
        const response = await axios.post(
            'https://api.cohere.ai/v1/chat',
            { model: config.model, message: request.messages[request.messages.length - 1].content, chat_history: request.messages.slice(0, -1).map(m => ({ role: m.role === 'user' ? 'USER' : 'CHATBOT', message: m.content })) },
            { headers: { 'Authorization': `Bearer ${apiKey}`, 'Content-Type': 'application/json' } }
        )
        return { content: response.data.text, model: config.model, provider: config.provider }
    }

    private async callGroq(apiKey: string, config: ProviderConfig, request: LLMRequest) {
        // Groq uses OpenAI-compatible API
        const response = await axios.post(
            'https://api.groq.com/openai/v1/chat/completions',
            { model: config.model, messages: request.messages, temperature: request.temperature ?? 0.7 },
            { headers: { 'Authorization': `Bearer ${apiKey}`, 'Content-Type': 'application/json' } }
        )
        return { content: response.data.choices[0].message.content, model: config.model, provider: config.provider, usage: response.data.usage }
    }
}
