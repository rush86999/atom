"use client"

import { useState, useEffect } from 'react'
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

export default function MarketplacePage() {
    const [templates, setTemplates] = useState<WorkflowTemplate[]>([])
    const [loading, setLoading] = useState(true)
    const [searchQuery, setSearchQuery] = useState('')
    const [selectedCategory, setSelectedCategory] = useState<string | null>(null)
    const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid')

    // Preview State
    const [previewTemplate, setPreviewTemplate] = useState<WorkflowTemplate | null>(null)
    const [isPreviewOpen, setIsPreviewOpen] = useState(false)

    const categories = ["Productivity", "Sales", "Marketing", "Finance", "Development", "Data Management"]

    useEffect(() => {
        fetchTemplates()
    }, [selectedCategory])

    const fetchTemplates = async () => {
        try {
            setLoading(true)
            const url = selectedCategory
                ? `/api/workflows/templates?category=${selectedCategory}`
                : '/api/workflows/templates'

            const response = await fetch(url)
            if (!response.ok) throw new Error('Failed to fetch templates')
            const data = await response.json()
            setTemplates((data.templates || []).map((t: any) => ({
                ...t,
                integrations: t.tags || [], // Map tags to integrations
                downloads: t.usage_count || 0,
                rating: t.rating || 0,
                created_at: t.created_at || new Date().toISOString(),
                steps: t.steps || [],
                input_schema: t.input_schema || {}
            })))
        } catch (error) {
            console.error('Error fetching templates:', error)
        } finally {
            setLoading(false)
        }
    }

    const handleImport = async (id: string) => {
        try {
            const response = await fetch(`/api/workflows/templates/${id}/import`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            })

            if (response.ok) {
                toast.success('Workflow imported successfully!')
            } else {
                const error = await response.json()
                toast.error(`Import failed: ${error.detail || 'Unknown error'}`)
            }
        } catch (error) {
            console.error('Import error:', error)
            toast.error('Failed to connect to server')
        }
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
                            key={cat}
                            variant={selectedCategory === cat ? "default" : "outline"}
                            onClick={() => setSelectedCategory(cat)}
                            className="whitespace-nowrap"
                        >
                            {cat}
                        </Button>
                    ))}
                </div>
            </div>

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
                                    <Badge variant="outline" className="mb-2">{template.category}</Badge>
                                    <div className="flex items-center text-yellow-500 text-sm">
                                        <Star className="h-3 w-3 fill-current mr-1" />
                                        {template.rating.toFixed(1)}
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
                                <Badge>{previewTemplate?.category}</Badge>
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
                                        {previewTemplate?.rating.toFixed(1)} <Star className="w-3 h-3 fill-current text-yellow-500" />
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
