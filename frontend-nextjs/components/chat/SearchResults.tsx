
import React from 'react';
import { Button } from "@/components/ui/button";
import {
    FileText,
    MessageSquare,
    Users,
    Briefcase,
    CheckSquare,
    Building,
    Target,
    Calendar,
    Layers,
    ExternalLink,
    Search
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";

// Define unified entity types matching backend
export type EntityType =
    'contact' | 'company' | 'task' | 'project' | 'file' |
    'message' | 'deal' | 'campaign' | 'event' | 'user';

export interface UnifiedEntity {
    entity_id: string;
    entity_type: EntityType;
    canonical_name: string;
    platform_mappings: Record<string, string>;
    attributes: Record<string, any>;
    created_at: string;
    updated_at: string;
    confidence_score: number;
}

interface SearchResultsProps {
    results: UnifiedEntity[];
    query?: string;
    onResultClick?: (entity: UnifiedEntity) => void;
}

export const SearchResults: React.FC<SearchResultsProps> = ({ results, query, onResultClick }) => {

    if (!results || results.length === 0) {
        return null;
    }

    const getEntityIcon = (type: string) => {
        switch (type) {
            case 'file': return <FileText className="h-4 w-4" />;
            case 'message': return <MessageSquare className="h-4 w-4" />;
            case 'contact':
            case 'user': return <Users className="h-4 w-4" />;
            case 'company': return <Building className="h-4 w-4" />;
            case 'task': return <CheckSquare className="h-4 w-4" />;
            case 'project': return <Briefcase className="h-4 w-4" />;
            case 'deal': return <Target className="h-4 w-4" />;
            case 'event': return <Calendar className="h-4 w-4" />;
            case 'campaign': return <Layers className="h-4 w-4" />;
            default: return <Search className="h-4 w-4" />;
        }
    };

    const getEntitySubtitle = (entity: UnifiedEntity): string => {
        const attrs = entity.attributes;
        switch (entity.entity_type) {
            case 'contact': return attrs.company || attrs.email || 'Contact';
            case 'task': return `Due: ${new Date(attrs.due_date).toLocaleDateString()}` || 'Task';
            case 'file': return attrs.file_type || 'Document';
            case 'project': return attrs.status || 'Project';
            case 'company': return attrs.industry || 'Company';
            default: return Object.keys(entity.platform_mappings).join(', ') || 'Item';
        }
    };

    return (
        <div className="w-full mt-2 border rounded-md bg-background overflow-hidden">
            <div className="bg-muted/30 px-3 py-2 border-b flex justify-between items-center">
                <div className="text-xs font-semibold text-muted-foreground flex items-center gap-1">
                    <Search className="h-3 w-3" />
                    Search Results {query && `for "${query}"`}
                </div>
                <Badge variant="outline" className="text-[10px] h-5">{results.length} found</Badge>
            </div>

            <ScrollArea className="max-h-[240px]">
                <div className="p-1">
                    {results.map((entity) => (
                        <div
                            key={entity.entity_id}
                            onClick={() => onResultClick && onResultClick(entity)}
                            className="flex items-center gap-3 p-2 hover:bg-muted/50 rounded-sm cursor-pointer transition-colors group"
                        >
                            <div className="h-8 w-8 rounded bg-primary/10 flex items-center justify-center text-primary">
                                {getEntityIcon(entity.entity_type)}
                            </div>

                            <div className="flex-1 min-w-0">
                                <div className="font-medium text-sm truncate pr-2">
                                    {entity.canonical_name}
                                </div>
                                <div className="text-xs text-muted-foreground truncate flex items-center gap-2">
                                    <span>{getEntitySubtitle(entity)}</span>
                                    <span className="w-1 h-1 rounded-full bg-border" />
                                    <span className="capitalize">{Object.keys(entity.platform_mappings)[0] || 'Unknown Source'}</span>
                                </div>
                            </div>

                            <Button variant="ghost" size="icon" className="h-6 w-6 opacity-0 group-hover:opacity-100 transition-opacity">
                                <ExternalLink className="h-3 w-3 text-muted-foreground" />
                            </Button>
                        </div>
                    ))}
                </div>
            </ScrollArea>
        </div>
    );
};
