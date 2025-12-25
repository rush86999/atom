'use client';

import React, { useState, useEffect, useCallback } from 'react';
import {
    Table, Plus, Trash2, Edit2, Save, X, Search, Filter,
    Download, Upload, Database, ChevronDown, MoreHorizontal,
    ArrowUpDown, Zap, RefreshCw
} from 'lucide-react';
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";

// Table schema definition
export interface TableColumn {
    id: string;
    name: string;
    type: 'text' | 'number' | 'date' | 'boolean' | 'select' | 'url' | 'email';
    required?: boolean;
    options?: string[]; // For select type
}

export interface TableRow {
    id: string;
    data: Record<string, any>;
    createdAt: string;
    updatedAt: string;
}

export interface AutomationTable {
    id: string;
    name: string;
    description?: string;
    columns: TableColumn[];
    rows: TableRow[];
    createdAt: string;
    updatedAt: string;
    connectedFlows?: string[];
}

// Sample tables for demonstration
const SAMPLE_TABLES: AutomationTable[] = [
    {
        id: 'leads',
        name: 'Sales Leads',
        description: 'Track and manage incoming leads',
        columns: [
            { id: 'name', name: 'Name', type: 'text', required: true },
            { id: 'email', name: 'Email', type: 'email', required: true },
            { id: 'company', name: 'Company', type: 'text' },
            { id: 'status', name: 'Status', type: 'select', options: ['New', 'Contacted', 'Qualified', 'Converted', 'Lost'] },
            { id: 'score', name: 'Lead Score', type: 'number' },
        ],
        rows: [
            { id: '1', data: { name: 'John Doe', email: 'john@acme.com', company: 'Acme Inc', status: 'New', score: 85 }, createdAt: '2024-01-15', updatedAt: '2024-01-15' },
            { id: '2', data: { name: 'Jane Smith', email: 'jane@tech.io', company: 'TechCorp', status: 'Qualified', score: 92 }, createdAt: '2024-01-14', updatedAt: '2024-01-16' },
            { id: '3', data: { name: 'Bob Wilson', email: 'bob@startup.co', company: 'Startup Co', status: 'Contacted', score: 78 }, createdAt: '2024-01-13', updatedAt: '2024-01-15' },
        ],
        createdAt: '2024-01-01',
        updatedAt: '2024-01-16',
        connectedFlows: ['lead-enrichment', 'follow-up-sequence'],
    },
    {
        id: 'support-tickets',
        name: 'Support Tickets',
        description: 'Customer support request tracking',
        columns: [
            { id: 'title', name: 'Title', type: 'text', required: true },
            { id: 'customer', name: 'Customer', type: 'text', required: true },
            { id: 'priority', name: 'Priority', type: 'select', options: ['Low', 'Medium', 'High', 'Urgent'] },
            { id: 'resolved', name: 'Resolved', type: 'boolean' },
        ],
        rows: [
            { id: '1', data: { title: 'Login issue', customer: 'Alice Brown', priority: 'High', resolved: false }, createdAt: '2024-01-16', updatedAt: '2024-01-16' },
            { id: '2', data: { title: 'Feature request', customer: 'Charlie Green', priority: 'Low', resolved: true }, createdAt: '2024-01-15', updatedAt: '2024-01-16' },
        ],
        createdAt: '2024-01-10',
        updatedAt: '2024-01-16',
        connectedFlows: ['ticket-auto-assign'],
    },
];

interface WorkflowTablesProps {
    onSelectTable?: (table: AutomationTable) => void;
    className?: string;
}

const WorkflowTables: React.FC<WorkflowTablesProps> = ({ onSelectTable, className }) => {
    const [tables, setTables] = useState<AutomationTable[]>(SAMPLE_TABLES);
    const [selectedTable, setSelectedTable] = useState<AutomationTable | null>(null);
    const [searchQuery, setSearchQuery] = useState('');
    const [isCreating, setIsCreating] = useState(false);
    const [newTableName, setNewTableName] = useState('');
    const [editingCell, setEditingCell] = useState<{ rowId: string; colId: string } | null>(null);
    const [editValue, setEditValue] = useState('');

    // Filter tables by search
    const filteredTables = tables.filter(t =>
        t.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        t.description?.toLowerCase().includes(searchQuery.toLowerCase())
    );

    // Create new table
    const handleCreateTable = () => {
        if (!newTableName.trim()) return;

        const newTable: AutomationTable = {
            id: `table-${Date.now()}`,
            name: newTableName,
            columns: [
                { id: 'col1', name: 'Column 1', type: 'text' },
            ],
            rows: [],
            createdAt: new Date().toISOString(),
            updatedAt: new Date().toISOString(),
        };

        setTables([...tables, newTable]);
        setNewTableName('');
        setIsCreating(false);
        setSelectedTable(newTable);
    };

    // Add row to table
    const handleAddRow = () => {
        if (!selectedTable) return;

        const newRow: TableRow = {
            id: `row-${Date.now()}`,
            data: selectedTable.columns.reduce((acc, col) => ({ ...acc, [col.id]: '' }), {}),
            createdAt: new Date().toISOString(),
            updatedAt: new Date().toISOString(),
        };

        const updatedTable = {
            ...selectedTable,
            rows: [...selectedTable.rows, newRow],
            updatedAt: new Date().toISOString(),
        };

        setSelectedTable(updatedTable);
        setTables(tables.map(t => t.id === selectedTable.id ? updatedTable : t));
    };

    // Add column to table
    const handleAddColumn = () => {
        if (!selectedTable) return;

        const newColumn: TableColumn = {
            id: `col-${Date.now()}`,
            name: `Column ${selectedTable.columns.length + 1}`,
            type: 'text',
        };

        const updatedTable = {
            ...selectedTable,
            columns: [...selectedTable.columns, newColumn],
            rows: selectedTable.rows.map(row => ({
                ...row,
                data: { ...row.data, [newColumn.id]: '' },
            })),
            updatedAt: new Date().toISOString(),
        };

        setSelectedTable(updatedTable);
        setTables(tables.map(t => t.id === selectedTable.id ? updatedTable : t));
    };

    // Update cell value
    const handleCellUpdate = (rowId: string, colId: string, value: any) => {
        if (!selectedTable) return;

        const updatedTable = {
            ...selectedTable,
            rows: selectedTable.rows.map(row =>
                row.id === rowId
                    ? { ...row, data: { ...row.data, [colId]: value }, updatedAt: new Date().toISOString() }
                    : row
            ),
            updatedAt: new Date().toISOString(),
        };

        setSelectedTable(updatedTable);
        setTables(tables.map(t => t.id === selectedTable.id ? updatedTable : t));
        setEditingCell(null);
    };

    // Delete row
    const handleDeleteRow = (rowId: string) => {
        if (!selectedTable) return;

        const updatedTable = {
            ...selectedTable,
            rows: selectedTable.rows.filter(row => row.id !== rowId),
            updatedAt: new Date().toISOString(),
        };

        setSelectedTable(updatedTable);
        setTables(tables.map(t => t.id === selectedTable.id ? updatedTable : t));
    };

    // Render cell value based on column type
    const renderCellValue = (col: TableColumn, value: any, rowId: string) => {
        const isEditing = editingCell?.rowId === rowId && editingCell?.colId === col.id;

        if (isEditing) {
            return (
                <div className="flex items-center gap-1">
                    <Input
                        value={editValue}
                        onChange={(e) => setEditValue(e.target.value)}
                        className="h-7 text-xs"
                        autoFocus
                        onKeyDown={(e) => {
                            if (e.key === 'Enter') handleCellUpdate(rowId, col.id, editValue);
                            if (e.key === 'Escape') setEditingCell(null);
                        }}
                    />
                    <Button size="sm" variant="ghost" className="h-6 w-6 p-0" onClick={() => handleCellUpdate(rowId, col.id, editValue)}>
                        <Save className="w-3 h-3" />
                    </Button>
                    <Button size="sm" variant="ghost" className="h-6 w-6 p-0" onClick={() => setEditingCell(null)}>
                        <X className="w-3 h-3" />
                    </Button>
                </div>
            );
        }

        switch (col.type) {
            case 'boolean':
                return (
                    <input
                        type="checkbox"
                        checked={!!value}
                        onChange={(e) => handleCellUpdate(rowId, col.id, e.target.checked)}
                        className="w-4 h-4"
                    />
                );
            case 'select':
                return (
                    <Badge
                        variant="secondary"
                        className={cn(
                            "text-xs cursor-pointer",
                            value === 'New' && "bg-blue-100 text-blue-700",
                            value === 'Qualified' && "bg-green-100 text-green-700",
                            value === 'High' && "bg-red-100 text-red-700",
                            value === 'Urgent' && "bg-red-200 text-red-800",
                        )}
                        onClick={() => {
                            setEditingCell({ rowId, colId: col.id });
                            setEditValue(value || '');
                        }}
                    >
                        {value || '-'}
                    </Badge>
                );
            case 'number':
                return (
                    <span
                        className="cursor-pointer hover:bg-gray-100 px-1 rounded font-mono text-sm"
                        onClick={() => {
                            setEditingCell({ rowId, colId: col.id });
                            setEditValue(value?.toString() || '');
                        }}
                    >
                        {value ?? '-'}
                    </span>
                );
            case 'email':
                return (
                    <a
                        href={`mailto:${value}`}
                        className="text-blue-600 hover:underline text-sm"
                    >
                        {value || '-'}
                    </a>
                );
            default:
                return (
                    <span
                        className="cursor-pointer hover:bg-gray-100 px-1 rounded text-sm"
                        onClick={() => {
                            setEditingCell({ rowId, colId: col.id });
                            setEditValue(value || '');
                        }}
                    >
                        {value || '-'}
                    </span>
                );
        }
    };

    return (
        <div className={cn("flex h-full", className)}>
            {/* Tables List Sidebar */}
            <div className="w-64 border-r bg-gray-50 flex flex-col">
                <div className="p-4 border-b bg-white">
                    <div className="flex items-center justify-between mb-3">
                        <div className="flex items-center gap-2">
                            <Database className="w-5 h-5 text-teal-600" />
                            <h3 className="font-bold">Tables</h3>
                        </div>
                        <Button size="sm" variant="outline" onClick={() => setIsCreating(true)}>
                            <Plus className="w-3 h-3" />
                        </Button>
                    </div>
                    <Input
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        placeholder="Search tables..."
                        className="text-sm"
                    />
                </div>

                {isCreating && (
                    <div className="p-3 border-b bg-teal-50">
                        <Input
                            value={newTableName}
                            onChange={(e) => setNewTableName(e.target.value)}
                            placeholder="Table name..."
                            className="text-sm mb-2"
                            autoFocus
                            onKeyDown={(e) => e.key === 'Enter' && handleCreateTable()}
                        />
                        <div className="flex gap-2">
                            <Button size="sm" onClick={handleCreateTable}>Create</Button>
                            <Button size="sm" variant="ghost" onClick={() => setIsCreating(false)}>Cancel</Button>
                        </div>
                    </div>
                )}

                <div className="flex-1 overflow-auto p-2">
                    {filteredTables.map(table => (
                        <button
                            key={table.id}
                            onClick={() => {
                                setSelectedTable(table);
                                onSelectTable?.(table);
                            }}
                            className={cn(
                                "w-full text-left p-3 rounded-lg mb-1 transition-colors",
                                selectedTable?.id === table.id
                                    ? "bg-teal-100 text-teal-900"
                                    : "hover:bg-gray-100"
                            )}
                        >
                            <div className="font-medium text-sm">{table.name}</div>
                            <div className="text-xs text-gray-500 flex items-center gap-2 mt-1">
                                <span>{table.rows.length} rows</span>
                                {table.connectedFlows && table.connectedFlows.length > 0 && (
                                    <Badge variant="secondary" className="text-[9px] h-4">
                                        <Zap className="w-2 h-2 mr-1" />
                                        {table.connectedFlows.length}
                                    </Badge>
                                )}
                            </div>
                        </button>
                    ))}
                </div>
            </div>

            {/* Table View */}
            <div className="flex-1 flex flex-col">
                {selectedTable ? (
                    <>
                        {/* Table Header */}
                        <div className="p-4 border-b bg-white flex justify-between items-center">
                            <div>
                                <h2 className="text-lg font-bold">{selectedTable.name}</h2>
                                {selectedTable.description && (
                                    <p className="text-sm text-gray-500">{selectedTable.description}</p>
                                )}
                            </div>
                            <div className="flex gap-2">
                                <Button size="sm" variant="outline" onClick={handleAddColumn}>
                                    <Plus className="w-3 h-3 mr-1" /> Column
                                </Button>
                                <Button size="sm" onClick={handleAddRow}>
                                    <Plus className="w-3 h-3 mr-1" /> Row
                                </Button>
                                <DropdownMenu>
                                    <DropdownMenuTrigger asChild>
                                        <Button size="sm" variant="ghost">
                                            <MoreHorizontal className="w-4 h-4" />
                                        </Button>
                                    </DropdownMenuTrigger>
                                    <DropdownMenuContent>
                                        <DropdownMenuItem>
                                            <Download className="w-4 h-4 mr-2" /> Export CSV
                                        </DropdownMenuItem>
                                        <DropdownMenuItem>
                                            <Upload className="w-4 h-4 mr-2" /> Import CSV
                                        </DropdownMenuItem>
                                        <DropdownMenuItem>
                                            <Zap className="w-4 h-4 mr-2" /> Connect to Flow
                                        </DropdownMenuItem>
                                    </DropdownMenuContent>
                                </DropdownMenu>
                            </div>
                        </div>

                        {/* Table Content */}
                        <div className="flex-1 overflow-auto">
                            <table className="w-full">
                                <thead className="bg-gray-50 sticky top-0">
                                    <tr>
                                        {selectedTable.columns.map(col => (
                                            <th
                                                key={col.id}
                                                className="px-4 py-2 text-left text-xs font-semibold text-gray-600 border-b"
                                            >
                                                <div className="flex items-center gap-1">
                                                    {col.name}
                                                    <ArrowUpDown className="w-3 h-3 text-gray-400" />
                                                </div>
                                            </th>
                                        ))}
                                        <th className="w-10 border-b"></th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {selectedTable.rows.map((row, idx) => (
                                        <tr
                                            key={row.id}
                                            className={cn(
                                                "border-b hover:bg-gray-50",
                                                idx % 2 === 0 && "bg-white",
                                                idx % 2 === 1 && "bg-gray-25"
                                            )}
                                        >
                                            {selectedTable.columns.map(col => (
                                                <td key={col.id} className="px-4 py-2 text-sm">
                                                    {renderCellValue(col, row.data[col.id], row.id)}
                                                </td>
                                            ))}
                                            <td className="px-2">
                                                <Button
                                                    size="sm"
                                                    variant="ghost"
                                                    className="h-6 w-6 p-0 text-gray-400 hover:text-red-500"
                                                    onClick={() => handleDeleteRow(row.id)}
                                                >
                                                    <Trash2 className="w-3 h-3" />
                                                </Button>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>

                            {selectedTable.rows.length === 0 && (
                                <div className="text-center py-12 text-gray-500">
                                    <Database className="w-12 h-12 mx-auto mb-3 opacity-30" />
                                    <p className="font-medium">No data yet</p>
                                    <p className="text-sm">Add rows manually or connect a flow to populate this table</p>
                                    <Button size="sm" className="mt-4" onClick={handleAddRow}>
                                        <Plus className="w-3 h-3 mr-1" /> Add Row
                                    </Button>
                                </div>
                            )}
                        </div>

                        {/* Connected Flows */}
                        {selectedTable.connectedFlows && selectedTable.connectedFlows.length > 0 && (
                            <div className="p-3 border-t bg-gray-50">
                                <div className="flex items-center gap-2 text-xs text-gray-600">
                                    <Zap className="w-3 h-3" />
                                    <span>Connected flows:</span>
                                    {selectedTable.connectedFlows.map(flow => (
                                        <Badge key={flow} variant="secondary" className="text-xs">
                                            {flow}
                                        </Badge>
                                    ))}
                                </div>
                            </div>
                        )}
                    </>
                ) : (
                    <div className="flex-1 flex items-center justify-center text-gray-500">
                        <div className="text-center">
                            <Database className="w-16 h-16 mx-auto mb-4 opacity-30" />
                            <h3 className="font-semibold text-lg mb-1">Select a table</h3>
                            <p className="text-sm">Choose a table from the sidebar or create a new one</p>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};

export default WorkflowTables;
