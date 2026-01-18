
import React from 'react';
import {
    Sheet,
    SheetContent,
    SheetDescription,
    SheetHeader,
    SheetTitle,
} from "../ui/sheet";
import { Button } from "@/components/ui/button";
import { Loader2, Sparkles, Check, ArrowRight } from "lucide-react";
import { Badge } from "@/components/ui/badge";

export interface OptimizationSuggestion {
    type: string;
    description: string;
    affected_nodes: string[];
    savings_estimate_ms: number;
    action: string;
}

interface OptimizationPanelProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    isLoading: boolean;
    suggestions: OptimizationSuggestion[];
    onApply: (suggestion: OptimizationSuggestion) => void;
}

const OptimizationPanel: React.FC<OptimizationPanelProps> = ({
    open,
    onOpenChange,
    isLoading,
    suggestions,
    onApply
}) => {
    return (
        <Sheet open={open} onOpenChange={onOpenChange}>
            <SheetContent className="w-[400px] sm:w-[540px] overflow-y-auto">
                <SheetHeader>
                    <SheetTitle className="flex items-center gap-2">
                        <Sparkles className="h-5 w-5 text-indigo-500" />
                        Workflow Optimizer
                    </SheetTitle>
                    <SheetDescription>
                        AI-driven analysis to improve performance and reliability.
                    </SheetDescription>
                </SheetHeader>

                <div className="mt-6 space-y-6">
                    {isLoading ? (
                        <div className="flex flex-col items-center justify-center py-12 text-gray-500">
                            <Loader2 className="h-8 w-8 animate-spin mb-3 text-indigo-500" />
                            <p>Analyzing workflow dependencies...</p>
                        </div>
                    ) : suggestions.length === 0 ? (
                        <div className="text-center py-12 bg-green-50 rounded-lg border border-green-100">
                            <Check className="h-10 w-10 text-green-500 mx-auto mb-3" />
                            <h3 className="text-lg font-medium text-green-900">All Optimized!</h3>
                            <p className="text-green-700 mt-1">No optimization opportunities detected.</p>
                        </div>
                    ) : (
                        <div className="space-y-4">
                            {suggestions.map((suggestion, idx) => (
                                <div key={idx} className="p-4 border rounded-lg bg-white shadow-sm hover:shadow-md transition-shadow">
                                    <div className="flex justify-between items-start mb-2">
                                        <Badge variant="outline" className="bg-blue-50 text-blue-700 border-blue-200">
                                            {suggestion.type === 'parallelization' ? 'Parallelization' : suggestion.type}
                                        </Badge>
                                        <span className="text-sm font-semibold text-green-600">
                                            -{suggestion.savings_estimate_ms}ms
                                        </span>
                                    </div>
                                    <p className="text-sm text-gray-700 mb-4">{suggestion.description}</p>

                                    <div className="bg-gray-50 p-3 rounded text-xs text-gray-500 mb-4 font-mono">
                                        Affected Steps: {suggestion.affected_nodes.join(', ')}
                                    </div>

                                    <Button
                                        className="w-full"
                                        size="sm"
                                        variant="default" // Primary color
                                        onClick={() => onApply(suggestion)}
                                    >
                                        Apply Fix <ArrowRight className="ml-2 h-3 w-3" />
                                    </Button>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            </SheetContent>
        </Sheet>
    );
};

export default OptimizationPanel;
