import React from 'react';
import {
    Popover,
    PopoverContent,
    PopoverTrigger,
} from "@/components/ui/popover";
import {
    Variable,
    Search,
    ChevronRight,
    Zap,
    Database,
    MessageSquare,
    ChevronDown,
    Layers
} from 'lucide-react';
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";

interface VariablePickerProps {
    onSelect: (variable: string) => void;
    trigger: React.ReactNode;
    availableNodes: any[];
}

const VariablePicker: React.FC<VariablePickerProps> = ({ onSelect, trigger, availableNodes }) => {
    const [isOpen, setIsOpen] = React.useState(false);
    const [search, setSearch] = React.useState('');

    // Filter nodes that have outputs (usually all preceding nodes)
    const activeNodes = availableNodes.filter(n => n.type !== 'condition' || n.data.label);

    return (
        <Popover>
            <PopoverTrigger asChild>
                {trigger}
            </PopoverTrigger>
            <PopoverContent className="w-72 p-0 bg-white shadow-xl border rounded-xl overflow-hidden" align="end">
                <div className="p-2 border-b bg-gray-50/50">
                    <div className="relative">
                        <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-gray-400" />
                        <Input
                            placeholder="Search variables..."
                            className="h-9 pl-8 text-xs bg-white border-gray-200"
                            value={search}
                            onChange={(e) => setSearch(e.target.value)}
                        />
                    </div>
                </div>

                <ScrollArea className="h-64">
                    <div className="p-2">
                        {activeNodes.length === 0 ? (
                            <div className="py-8 text-center px-4">
                                <Variable className="h-8 w-8 text-gray-200 mx-auto mb-2" />
                                <p className="text-[10px] text-gray-400 font-medium">
                                    No variables available. Add steps before this one to use their output.
                                </p>
                            </div>
                        ) : (
                            activeNodes.map((node) => (
                                <div key={node.id} className="mb-2 last:mb-0">
                                    <div className="flex items-center gap-1.5 px-2 py-1.5 mb-1">
                                        <Layers className="h-3 w-3 text-purple-600" />
                                        <span className="text-[10px] font-bold text-gray-900 uppercase tracking-tight truncate max-w-[150px]">
                                            {node.data?.label || node.data?.service || 'Previous Step'}
                                        </span>
                                        <Badge variant="outline" className="ml-auto text-[8px] h-4 border-gray-200 text-gray-500 font-mono">
                                            {node.id}
                                        </Badge>
                                    </div>

                                    <div className="space-y-0.5">
                                        <button
                                            onClick={() => {
                                                onSelect(`{{${node.data?.label || node.id}.output}}`);
                                                setIsOpen(false);
                                            }}
                                            className="w-full text-left px-7 py-1.5 rounded-md hover:bg-purple-50 group flex items-center justify-between"
                                        >
                                            <span className="text-xs text-gray-600 group-hover:text-purple-700">All Output</span>
                                            <ChevronRight className="h-3 w-3 text-gray-300 group-hover:text-purple-400" />
                                        </button>

                                        {/* Mocking some common fields for the demo/impl */}
                                        {['id', 'name', 'content'].map(field => (
                                            <button
                                                key={field}
                                                onClick={() => {
                                                    onSelect(`{{${node.data?.label || node.id}.${field}}}`);
                                                    setIsOpen(false);
                                                }}
                                                className="w-full text-left px-7 py-1.5 rounded-md hover:bg-purple-50 group flex items-center justify-between"
                                            >
                                                <span className="text-xs text-gray-600 group-hover:text-purple-700">{field}</span>
                                                <ChevronRight className="h-3 w-3 text-gray-300 group-hover:text-purple-400" />
                                            </button>
                                        ))}
                                    </div>
                                </div>
                            ))
                        )}
                    </div>
                </ScrollArea>

                <div className="p-3 bg-purple-50 flex items-center gap-2 border-t border-purple-100">
                    <Database className="h-3 w-3 text-purple-600" />
                    <span className="text-[10px] text-purple-800 font-medium">Use data from preceding steps</span>
                </div>
            </PopoverContent>
        </Popover>
    );
};

export default VariablePicker;
