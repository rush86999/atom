"use client"

import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
    Search,
    Download,
    Star,
    Clock,
    Zap,
    Filter,
    LayoutGrid,
    List as ListIcon
} from 'lucide-react'
import { toast } from 'sonner'
import { NEXT_PUBLIC_API_BASE_URL } from '@shared-utils/constants'

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
}

const categories = ["Productivity", "Sales", "Marketing", "Finance", "Development"]

export default function MarketplacePage() {
    const [templates, setTemplates] = useState<WorkflowTemplate[]>([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const [searchQuery, setSearchQuery] = useState('')
    const [selectedCategory, setSelectedCategory] = useState<string | null>(null)
    const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid')

    useEffect(() => {
        fetchTemplates()
    }, [selectedCategory])

    const fetchTemplates = async () => {
        try {
            setLoading(true)
            setError(null)
            const url = selectedCategory
                ? `${NEXT_PUBLIC_API_BASE_URL}/api/marketplace/templates?category=${selectedCategory}`
                : `${NEXT_PUBLIC_API_BASE_URL}/api/marketplace/templates`

            const response = await fetch(url)
            if (!response.ok) throw new Error('Failed to fetch templates')
            const data = await response.json()
            setTemplates(data)
        } catch (err) {
            console.error('Error fetching templates:', err)
            setError('Failed to load marketplace templates')
            toast.error('Failed to load marketplace templates')
        } finally {
            setLoading(false)
        }
    }

    const handleImport = async (templateId: string) => {
        try {
            const response = await fetch(`${NEXT_PUBLIC_API_BASE_URL}/api/marketplace/templates/${templateId}/import`, {
                method: 'POST'
            })
            if (!response.ok) throw new Error('Import failed')
            toast.success('Workflow imported successfully!')
        } catch (err) {
            console.error('Import error:', err)
            toast.error('Failed to import workflow')
        }
    }

    const filteredTemplates = templates.filter(template => {
        const matchesSearch = template.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
            template.description.toLowerCase().includes(searchQuery.toLowerCase())
        const matchesCategory = !selectedCategory || template.category === selectedCategory
        return matchesSearch && matchesCategory
    })

    return (
        <div className="container mx-auto p-6 space-y-8">
            {/* Header */}
            <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight">Workflow Marketplace</h1>
                    <p className="text-muted-foreground mt-1">
                        Discover and import pre-built workflows to automate your tasks.
                    </p>
                </div>
                <div className="flex items-center gap-2">
                    <Button variant="outline" size="icon" onClick={() => setViewMode('grid')}>
                        <LayoutGrid className={`h-4 w-4 ${viewMode === 'grid' ? 'text-primary' : ''}`} />
                    </Button>
                    <Button variant="outline" size="icon" onClick={() => setViewMode('list')}>
                        <ListIcon className={`h-4 w-4 ${viewMode === 'list' ? 'text-primary' : ''}`} />
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

            {error && (
                <div className="bg-destructive/10 border border-destructive text-destructive px-4 py-3 rounded">
                    {error}
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
                <>
                    <div className={viewMode === 'grid' ? "grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6" : "space-y-4"}>
                        {filteredTemplates.map(template => (
                            <Card key={template.id} className="flex flex-col hover:shadow-lg transition-shadow">
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
                                <CardFooter className="border-t pt-4">
                                    <div className="flex justify-between items-center w-full">
                                        <div className="flex items-center text-sm text-muted-foreground">
                                            <Zap className="h-3 w-3 mr-1" />
                                            {template.complexity}
                                        </div>
                                        <Button size="sm" onClick={() => handleImport(template.id)}>
                                            Import
                                        </Button>
                                    </div>
                                </CardFooter>
                            </Card>
                        ))}
                    </div>

                    {!loading && filteredTemplates.length === 0 && (
                        <div className="text-center py-12">
                            <p className="text-muted-foreground text-lg">No workflows found matching your criteria.</p>
                            <Button variant="link" onClick={() => { setSearchQuery(''); setSelectedCategory(null) }}>
                                Clear filters
                            </Button>
                        </div>
                    )}
                </>
            )}
        </div>
    )
}