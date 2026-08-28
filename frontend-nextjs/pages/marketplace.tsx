"use client"

// This page is fully client-rendered (fetches from the API at runtime). Opt out
// of static prerendering so `next build` (standalone output) doesn't try to SSG
// it — which fails with "Cannot access 'H' before initialization" (a TDZ in the
// prerender pass for client components with module-scoped refs).
export const dynamic = 'force-dynamic'

import React, { useState, useEffect, useCallback } from 'react'
import { useRouter } from 'next/router'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import {
    Search,
    Download,
    Star,
    Clock,
    Zap,
    LayoutGrid,
    List as ListIcon
} from 'lucide-react'
import { toast } from 'react-hot-toast' // Assuming sonner is used, if not, change to use-toast
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
    DialogFooter,
} from "@/components/ui/dialog"

interface WorkflowTemplate {
    id: string
    name: string
    description: string
    category: string
    author: string
    version: string
    integrations: string[]
    complexity: string
    created_at: string
    downloads: number
    rating: number
    steps?: any[]
    input_schema?: any
}

interface TemplateReadiness {
    ready: boolean
    missing: string[]
    connect_urls: string[]
}

const categories = [
    { label: "Automation", value: "automation" },
    { label: "Data Processing", value: "data_processing" },
    { label: "AI/ML", value: "ai_ml" },
    { label: "Business", value: "business" },
    { label: "Integration", value: "integration" },
    { label: "Monitoring", value: "monitoring" },
    { label: "Reporting", value: "reporting" },
    { label: "Security", value: "security" },
    { label: "General", value: "general" },
]

const formatCategory = (category?: string) => {
    if (!category) return "General"
    return categories.find(cat => cat.value === category)?.label
        || category.replace(/_/g, " ").replace(/\b\w/g, char => char.toUpperCase())
}

export default function MarketplacePage() {
    const router = useRouter()
    const [templates, setTemplates] = useState<WorkflowTemplate[]>([])
    const [loading, setLoading] = useState(true)
    const [errorMessage, setErrorMessage] = useState<string | null>(null)
    const [searchQuery, setSearchQuery] = useState('')
    const [selectedCategory, setSelectedCategory] = useState<string | null>(null)
    const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid')

    // Preview State
    const [previewTemplate, setPreviewTemplate] = useState<WorkflowTemplate | null>(null)
    const [isPreviewOpen, setIsPreviewOpen] = useState(false)

    // Per-template integration readiness (personal starters): drives the
    // "Connect Gmail" CTA instead of failing mid-workflow.
    const [readiness, setReadiness] = useState<Record<string, TemplateReadiness>>({})

    const fetchReadiness = useCallback(async (ids: string[]) => {
        const token = localStorage.getItem('auth_token')
        await Promise.all(ids.map(async id => {
            try {
                const response = await fetch(`/api/workflow-templates/${id}/readiness`, {
                    headers: token ? { 'Authorization': `Bearer ${token}` } : {}
                })
                if (!response.ok) return
                const data = await response.json()
                if (data && typeof data.ready === 'boolean') {
                    setReadiness(prev => ({
                        ...prev,
                        [id]: { ready: data.ready, missing: data.missing || [], connect_urls: data.connect_urls || [] }
                    }))
                }
            } catch {
                // Readiness is advisory; never block the marketplace on it.
            }
        }))
    }, [])

    const fetchTemplates = useCallback(async () => {
        try {
            setLoading(true)
            setErrorMessage(null)
            const url = selectedCategory
                ? `/api/workflow-templates?category=${encodeURIComponent(selectedCategory)}`
                : '/api/workflow-templates'

            const token = localStorage.getItem('auth_token')
            const response = await fetch(url, {
                headers: {
                    ...(token ? { 'Authorization': `Bearer ${token}` } : {})
                }
            })
            if (!response.ok) {
                const details = await response.text().catch(() => '')
                throw new Error(details || `Failed to fetch templates (${response.status})`)
            }
            const data = await response.json()
            const mapped = (data || []).map((t: any) => ({ // Direct list, not data.templates
                ...t,
                id: t.template_id, // Map template_id to id
                integrations: t.tags || [], // Map tags to integrations
                downloads: t.usage_count || 0,
                rating: t.rating || 0,
                created_at: t.created_at || new Date().toISOString(),
                steps: t.steps || [],
                input_schema: t.input_schema || {}
            }))
            setTemplates(mapped)
            const personalIds = mapped
                .map((t: WorkflowTemplate) => t.id)
                .filter((id: string) => id.startsWith('template_personal_'))
            if (personalIds.length > 0) {
                fetchReadiness(personalIds)
            }
        } catch (error) {
            console.warn('Error fetching templates:', error instanceof Error ? error.message : error)
            setTemplates([])
            setErrorMessage('Could not load workflow templates. Make sure the backend is running on port 8000, then refresh.')
        } finally {
            setLoading(false)
        }
    }, [selectedCategory, fetchReadiness])

    useEffect(() => {
        fetchTemplates()
    }, [fetchTemplates])

    const handleImport = async (id: string) => {
        try {
            const token = localStorage.getItem('auth_token')
            const response = await fetch(`/api/workflow-templates/${id}/import`, {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json',
                    ...(token ? { 'Authorization': `Bearer ${token}` } : {})
                }
            })

            if (response.ok) {
                const data = await response.json().catch((): null => null)
                toast.success(
                    data?.editor_url
                        ? 'Workflow imported — opening the editor…'
                        : 'Workflow imported successfully!'
                )
                if (data?.workflow_id && data?.editor_url) {
                    router.push(data.editor_url)
                }
            } else {
                const error = await response.json()
                toast.error(`Import failed: ${error.detail || 'Unknown error'}`)
            }
        } catch (error) {
            console.error('Import error:', error)
            toast.error('Failed to connect to server')
        }
    }

    const openPreview = (template: WorkflowTemplate) => {
        setPreviewTemplate(template)
        setIsPreviewOpen(true)
    }

    const filteredTemplates = templates.filter(t =>
        t.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        t.description.toLowerCase().includes(searchQuery.toLowerCase())
    );

    return (
        <div className="container mx-auto p-6 space-y-8">
            {/* Header */}
            <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight">Workflow Marketplace</h1>
                    <p className="text-muted-foreground mt-1">
                        Discover and import pre-built automation workflows.
                    </p>
                </div>
                <div className="flex items-center gap-2">
                    <Button variant={viewMode === 'grid' ? 'secondary' : 'ghost'} size="icon" onClick={() => setViewMode('grid')}>
                        <LayoutGrid className="h-4 w-4" />
                    </Button>
                    <Button variant={viewMode === 'list' ? 'secondary' : 'ghost'} size="icon" onClick={() => setViewMode('list')}>
                        <ListIcon className="h-4 w-4" />
                    </Button>
                </div>
            </div>

            {/* Search and Filter */}
            <div className="flex flex-col md:flex-row gap-4 items-center">
                <div className="relative flex-1 w-full">
                    <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <Input
                        placeholder="Search workflows..."
                        className="pl-10"
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                    />
                </div>
                <div className="flex gap-2 overflow-x-auto pb-2 md:pb-0 w-full md:w-auto">
                    <Button
                        variant={selectedCategory === null ? "default" : "outline"}
                        onClick={() => setSelectedCategory(null)}
                        className="whitespace-nowrap"
                    >
                        All
                    </Button>
                    {categories.map(cat => (
                        <Button
                            key={cat.value}
                            variant={selectedCategory === cat.value ? "default" : "outline"}
                            onClick={() => setSelectedCategory(cat.value)}
                            className="whitespace-nowrap"
                        >
                            {cat.label}
                        </Button>
                    ))}
                </div>
            </div>

            {errorMessage && (
                <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-900/50 dark:bg-red-950/30 dark:text-red-300">
                    {errorMessage}
                </div>
            )}

            {/* Templates Grid */}
            {loading ? (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {[1, 2, 3].map(i => (
                        <Card key={i} className="h-[300px] animate-pulse bg-muted/50" />
                    ))}
                </div>
            ) : (
                <div className={viewMode === 'grid' ? "grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6" : "space-y-4"}>
                    {filteredTemplates.map(template => (
                        <Card key={template.id} className="flex flex-col hover:shadow-lg transition-shadow border-slate-200 dark:border-slate-800">
                            <CardHeader>
                                <div className="flex justify-between items-start">
                                    <Badge variant="outline" className="mb-2">{formatCategory(template.category)}</Badge>
                                    <div className="flex items-center text-yellow-500 text-sm">
                                        <Star className="h-3 w-3 fill-current mr-1" />
                                        {(template.rating ?? 0).toFixed(1)}
                                    </div>
                                </div>
                                <CardTitle className="line-clamp-1">{template.name}</CardTitle>
                                <CardDescription className="line-clamp-2 h-10">
                                    {template.description}
                                </CardDescription>
                            </CardHeader>
                            <CardContent className="flex-1">
                                <div className="space-y-4">
                                    <div className="flex flex-wrap gap-2">
                                        {template.integrations.map(int => (
                                            <Badge key={int} variant="secondary" className="text-xs">
                                                {int}
                                            </Badge>
                                        ))}
                                    </div>
                                    {readiness[template.id] && !readiness[template.id].ready && (
                                        <a
                                          href={readiness[template.id].connect_urls[0]}
                                          className="inline-flex items-center gap-1 rounded-md border border-amber-300 bg-amber-50 px-2 py-1 text-xs font-medium text-amber-800 hover:bg-amber-100 dark:border-amber-900/50 dark:bg-amber-950/30 dark:text-amber-300"
                                        >
                                            Setup needed: connect {readiness[template.id].missing.join(', ')}
                                        </a>
                                    )}
                                    <div className="flex items-center justify-between text-sm text-muted-foreground">
                                        <div className="flex items-center">
                                            <Clock className="h-3 w-3 mr-1" />
                                            {new Date(template.created_at).toLocaleDateString()}
                                        </div>
                                        <div className="flex items-center">
                                            <Download className="h-3 w-3 mr-1" />
                                            {template.downloads}
                                        </div>
                                    </div>
                                </div>
                            </CardContent>
                            <CardFooter className="gap-2">
                                <Button className="w-full" variant="outline" onClick={() => openPreview(template)}>
                                    Preview
                                </Button>
                                <Button className="w-full" onClick={() => handleImport(template.id)}>
                                    <Zap className="h-4 w-4 mr-2" />
                                    Import
                                </Button>
                            </CardFooter>
                        </Card>
                    ))}
                </div>
            )}

            {!loading && filteredTemplates.length === 0 && (
                <div className="text-center py-12">
                    <p className="text-muted-foreground text-lg">No workflows found matching your criteria.</p>
                    <Button variant="link" onClick={() => { setSearchQuery(''); setSelectedCategory(null) }}>
                        Clear filters
                    </Button>
                </div>
            )}

            {/* Preview Dialog */}
            <Dialog open={isPreviewOpen} onOpenChange={setIsPreviewOpen}>
                <DialogContent className="max-w-2xl max-h-[85vh] flex flex-col">
                    <DialogHeader>
                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                                <Badge>{formatCategory(previewTemplate?.category)}</Badge>
                                <span className="text-sm text-muted-foreground">v{previewTemplate?.version}</span>
                            </div>
                        </div>
                        <DialogTitle className="text-2xl mt-2">{previewTemplate?.name}</DialogTitle>
                        <DialogDescription className="text-base mt-2">
                            {previewTemplate?.description}
                        </DialogDescription>
                    </DialogHeader>

                    <div className="flex-1 overflow-y-auto pr-4 mt-4">
                        <div className="space-y-6">
                            {/* Readiness banner (personal starters) */}
                            {previewTemplate && readiness[previewTemplate.id] && !readiness[previewTemplate.id].ready && (
                                <div className="rounded-md border border-amber-300 bg-amber-50 px-4 py-3 dark:border-amber-900/50 dark:bg-amber-950/30">
                                    <div className="text-sm font-medium text-amber-800 dark:text-amber-300">
                                        Setup needed before first run
                                    </div>
                                    <div className="mt-2 flex flex-wrap gap-2">
                                        {readiness[previewTemplate.id].connect_urls.map(url => (
                                            <a
                                              key={url}
                                              href={url}
                                              className="rounded-md bg-amber-800 px-3 py-1.5 text-xs font-medium text-white hover:bg-amber-900 dark:bg-amber-700 dark:hover:bg-amber-600"
                                            >
                                                Connect {url.split('connect=')[1]}
                                            </a>
                                        ))}
                                    </div>
                                </div>
                            )}

                            {/* Stats */}
                            <div className="grid grid-cols-3 gap-4 p-4 bg-muted/30 rounded-lg">
                                <div className="text-center">
                                    <div className="text-xs text-muted-foreground uppercase font-bold">Complexity</div>
                                    <div className="font-medium capitalize">{previewTemplate?.complexity}</div>
                                </div>
                                <div className="text-center">
                                    <div className="text-xs text-muted-foreground uppercase font-bold">Steps</div>
                                    <div className="font-medium">{previewTemplate?.steps?.length || 0}</div>
                                </div>
                                <div className="text-center">
                                    <div className="text-xs text-muted-foreground uppercase font-bold">Rating</div>
                                    <div className="font-medium flex items-center justify-center gap-1">
                                        {(previewTemplate?.rating ?? 0).toFixed(1)} <Star className="w-3 h-3 fill-current text-yellow-500" />
                                    </div>
                                </div>
                            </div>

                            {/* Workflow Steps */}
                            <div>
                                <h3 className="font-semibold mb-3 flex items-center gap-2">
                                    <ListIcon className="w-4 h-4" /> Workflow Steps
                                </h3>
                                <div className="space-y-3 pl-2 border-l-2 border-slate-200 dark:border-slate-800 ml-1">
                                    {previewTemplate?.steps?.map((step: any, index: number) => (
                                        <div key={index} className="relative pl-6 pb-2">
                                            <div className="absolute -left-[21px] top-1 w-3 h-3 rounded-full bg-primary ring-4 ring-background" />
                                            <div className="font-medium text-sm">{step.name || `Step ${index + 1}`}</div>
                                            <div className="text-xs text-muted-foreground mt-0.5">
                                                Using <span className="font-mono text-primary/80">{step.service}</span> to {step.action}
                                            </div>
                                        </div>
                                    ))}
                                    {(!previewTemplate?.steps || previewTemplate.steps.length === 0) && (
                                        <div className="text-sm text-muted-foreground italic pl-4">No steps defined in preview.</div>
                                    )}
                                </div>
                            </div>

                            {/* Inputs */}
                            {previewTemplate?.input_schema && Object.keys(previewTemplate.input_schema).length > 0 && (
                                <div>
                                    <h3 className="font-semibold mb-3 flex items-center gap-2">
                                        <Zap className="w-4 h-4" /> Required Inputs
                                    </h3>
                                    <div className="grid grid-cols-1 gap-2">
                                        {Object.entries(previewTemplate.input_schema).map(([key, schema]: [string, any]) => (
                                            <div key={key} className="flex items-center justify-between p-2 rounded border bg-card">
                                                <span className="font-mono text-sm">{key}</span>
                                                <Badge variant="outline">{schema.type || 'string'}</Badge>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>

                    <DialogFooter className="mt-6 gap-2 sm:gap-0">
                        <Button variant="outline" onClick={() => setIsPreviewOpen(false)}>Close</Button>
                        <Button onClick={() => {
                            if (previewTemplate) {
                                handleImport(previewTemplate.id);
                                setIsPreviewOpen(false);
                            }
                        }}>
                            <Download className="w-4 h-4 mr-2" />
                            Import Workflow
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    )
}

// Force dynamic rendering (skip SSG). The page is fully client-rendered
// (fetches from the API at runtime); `output: 'standalone'` still attempts
// to prerender Pages-Router pages unless getInitialProps is present, which
// hit a minified TDZ ('Cannot access H before initialization'). Attaching
// getInitialProps marks the page dynamic and skips the prerender pass.
MarketplacePage.getInitialProps = async () => ({})

