'use client';

import { useState, useCallback, useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import {
    Table2,
    Save,
    Download,
    Plus,
    Trash2,
    Bold,
    Italic,
    AlignLeft,
    AlignCenter,
    AlignRight,
    ArrowUp,
    ArrowDown,
    Filter,
    BarChart3,
    Calculator,
    Sparkles,
    RefreshCw,
    Upload,
    FileSpreadsheet,
    Sigma,
    Percent
} from 'lucide-react';
import { toast } from 'sonner';
import { useAccessibilityMirror } from '@/lib/canvas/accessibility';

interface SpreadsheetCanvasProps {
    sheetId?: string;
    initialTitle?: string;
    initialData?: CellData[][];
    onSave?: (sheet: SheetData) => Promise<void>;
    onExport?: (format: 'csv' | 'xlsx') => void;
}

interface CellData {
    value: string | number;
    formula?: string;
    format?: CellFormat;
}

interface CellFormat {
    bold?: boolean;
    italic?: boolean;
    align?: 'left' | 'center' | 'right';
    backgroundColor?: string;
    textColor?: string;
    numberFormat?: 'number' | 'currency' | 'percent' | 'date';
}

interface SheetData {
    id?: string;
    title: string;
    data: CellData[][];
    columns: ColumnDef[];
}

interface ColumnDef {
    id: string;
    header: string;
    width: number;
}

const DEFAULT_ROWS = 20;
const DEFAULT_COLS = 8;

const generateColumnLabel = (index: number): string => {
    let label = '';
    while (index >= 0) {
        label = String.fromCharCode(65 + (index % 26)) + label;
        index = Math.floor(index / 26) - 1;
    }
    return label;
};

export function SpreadsheetCanvas({
    sheetId,
    initialTitle = 'Untitled Spreadsheet',
    initialData,
    onSave,
    onExport
}: SpreadsheetCanvasProps) {
    const [title, setTitle] = useState(initialTitle);
    const [data, setData] = useState<CellData[][]>(() => {
        if (initialData) return initialData;
        return Array(DEFAULT_ROWS).fill(null).map(() =>
            Array(DEFAULT_COLS).fill(null).map(() => ({ value: '' }))
        );
    });
    const [selectedCell, setSelectedCell] = useState<{ row: number; col: number } | null>(null);
    const [isSaving, setIsSaving] = useState(false);
    const [formulaBarValue, setFormulaBarValue] = useState('');
    const [isAnalyzing, setIsAnalyzing] = useState(false);

    // Accessibility mirror for screen readers and AI agents
    const accessibilityMirror = useAccessibilityMirror({
        canvasId: sheetId || 'spreadsheet',
        canvasType: 'sheets',
        getContent: () => {
            const lines: string[] = [`Spreadsheet: ${title}`];
            if (data && data.length > 0) {
                data.forEach((row, rowIndex) => {
                    row.forEach((cell, colIndex) => {
                        if (cell.value || cell.formula) {
                            const colLabel = generateColumnLabel(colIndex);
                            lines.push(`${colLabel}${rowIndex + 1}: ${cell.formula || cell.value}`);
                        }
                    });
                });
            } else {
                lines.push('No cells');
            }
            return lines;
        },
    });

    const columns = useMemo(() =>
        Array(data[0]?.length || DEFAULT_COLS).fill(null).map((_, i) => ({
            id: generateColumnLabel(i),
            header: generateColumnLabel(i),
            width: 120
        })),
        [data]
    );

    const handleCellChange = useCallback((row: number, col: number, value: string) => {
        setData(prev => {
            const newData = prev.map(r => [...r]);
            const isFormula = value.startsWith('=');

            newData[row][col] = {
                ...newData[row][col],
                value: isFormula ? evaluateFormula(value, prev) : value,
                formula: isFormula ? value : undefined
            };

            return newData;
        });
    }, []);

    const evaluateFormula = (formula: string, currentData: CellData[][]): string | number => {
        // Simple formula evaluator - supports SUM, AVG, COUNT
        try {
            const cleanFormula = formula.substring(1).toUpperCase();

            if (cleanFormula.startsWith('SUM(')) {
                const range = cleanFormula.match(/SUM\(([A-Z]+\d+):([A-Z]+\d+)\)/);
                if (range) {
                    const values = getCellRange(range[1], range[2], currentData);
                    return values.reduce((a: number, b) => a + (parseFloat(String(b)) || 0), 0);
                }
            }

            if (cleanFormula.startsWith('AVG(') || cleanFormula.startsWith('AVERAGE(')) {
                const range = cleanFormula.match(/(?:AVG|AVERAGE)\(([A-Z]+\d+):([A-Z]+\d+)\)/);
                if (range) {
                    const values = getCellRange(range[1], range[2], currentData);
                    const nums = values.filter(v => !isNaN(parseFloat(String(v)))).map(v => parseFloat(String(v)));
                    return nums.length > 0 ? nums.reduce((a, b) => a + b, 0) / nums.length : 0;
                }
            }

            return formula; // Return original if can't evaluate
        } catch {
            return '#ERROR';
        }
    };

    const getCellRange = (start: string, end: string, currentData: CellData[][]): (string | number)[] => {
        const startCol = start.charCodeAt(0) - 65;
        const startRow = parseInt(start.substring(1)) - 1;
        const endCol = end.charCodeAt(0) - 65;
        const endRow = parseInt(end.substring(1)) - 1;

        const values: (string | number)[] = [];
        for (let r = startRow; r <= endRow; r++) {
            for (let c = startCol; c <= endCol; c++) {
                if (currentData[r]?.[c]) {
                    values.push(currentData[r][c].value);
                }
            }
        }
        return values;
    };

    const handleCellSelect = (row: number, col: number) => {
        setSelectedCell({ row, col });
        const cell = data[row]?.[col];
        setFormulaBarValue(cell?.formula || String(cell?.value || ''));
    };

    const handleFormulaBarChange = (value: string) => {
        setFormulaBarValue(value);
        if (selectedCell) {
            handleCellChange(selectedCell.row, selectedCell.col, value);
        }
    };

    const addRow = () => {
        setData(prev => [...prev, Array(prev[0].length).fill(null).map(() => ({ value: '' }))]);
    };

    const addColumn = () => {
        setData(prev => prev.map(row => [...row, { value: '' }]));
    };

    const deleteRow = () => {
        if (selectedCell && data.length > 1) {
            setData(prev => prev.filter((_, i) => i !== selectedCell.row));
            setSelectedCell(null);
        }
    };

    const handleSave = async () => {
        setIsSaving(true);
        try {
            if (onSave) {
                await onSave({ id: sheetId, title, data, columns });
            }
            toast.success('Spreadsheet saved');
        } catch (error) {
            toast.error('Failed to save');
        } finally {
            setIsSaving(false);
        }
    };

    const handleAIAnalyze = async () => {
        setIsAnalyzing(true);
        try {
            const response = await fetch('/api/canvas/spreadsheet/ai-analyze', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ data, title })
            });

            if (response.ok) {
                const result = await response.json();
                toast.info(result.insight || 'Analysis complete');
            }
        } catch {
            toast.error('AI analysis unavailable');
        } finally {
            setIsAnalyzing(false);
        }
    };

    const insertFunction = (fn: string) => {
        if (selectedCell) {
            const cellRef = `${generateColumnLabel(selectedCell.col)}${selectedCell.row + 1}`;
            setFormulaBarValue(`=${fn}(${cellRef}:${cellRef})`);
        } else {
            setFormulaBarValue(`=${fn}()`);
        }
    };

    return (
        <Card className="w-full max-w-6xl mx-auto">
            <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <Table2 className="h-5 w-5 text-primary" />
                        <Input
                            value={title}
                            onChange={(e) => setTitle(e.target.value)}
                            className="text-lg font-semibold bg-transparent border-none focus-visible:ring-0 px-0 w-auto"
                            placeholder="Spreadsheet title"
                        />
                    </div>

                    <div className="flex items-center gap-2">
                        <Button variant="ghost" size="icon" onClick={() => onExport?.('csv')}>
                            <Download className="h-4 w-4" />
                        </Button>
                        <Button variant="outline" size="icon">
                            <Upload className="h-4 w-4" />
                        </Button>
                        <Button onClick={handleSave} disabled={isSaving}>
                            {isSaving ? (
                                <RefreshCw className="h-4 w-4 mr-1 animate-spin" />
                            ) : (
                                <Save className="h-4 w-4 mr-1" />
                            )}
                            Save
                        </Button>
                    </div>
                </div>
            </CardHeader>

            <CardContent className="space-y-4">
                {/* Toolbar */}
                <div className="flex items-center gap-1 flex-wrap p-2 bg-muted/50 rounded-lg">
                    <Button variant="ghost" size="icon" className="h-8 w-8">
                        <Bold className="h-4 w-4" />
                    </Button>
                    <Button variant="ghost" size="icon" className="h-8 w-8">
                        <Italic className="h-4 w-4" />
                    </Button>

                    <Separator orientation="vertical" className="h-6 mx-1" />

                    <Button variant="ghost" size="icon" className="h-8 w-8">
                        <AlignLeft className="h-4 w-4" />
                    </Button>
                    <Button variant="ghost" size="icon" className="h-8 w-8">
                        <AlignCenter className="h-4 w-4" />
                    </Button>
                    <Button variant="ghost" size="icon" className="h-8 w-8">
                        <AlignRight className="h-4 w-4" />
                    </Button>

                    <Separator orientation="vertical" className="h-6 mx-1" />

                    <Button variant="ghost" size="sm" onClick={() => insertFunction('SUM')}>
                        <Sigma className="h-4 w-4 mr-1" />
                        SUM
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => insertFunction('AVG')}>
                        <Calculator className="h-4 w-4 mr-1" />
                        AVG
                    </Button>
                    <Button variant="ghost" size="sm">
                        <Percent className="h-4 w-4 mr-1" />
                        %
                    </Button>

                    <Separator orientation="vertical" className="h-6 mx-1" />

                    <Button variant="ghost" size="icon" className="h-8 w-8">
                        <Filter className="h-4 w-4" />
                    </Button>
                    <Button variant="ghost" size="icon" className="h-8 w-8">
                        <ArrowUp className="h-4 w-4" />
                    </Button>
                    <Button variant="ghost" size="icon" className="h-8 w-8">
                        <ArrowDown className="h-4 w-4" />
                    </Button>

                    <Separator orientation="vertical" className="h-6 mx-1" />

                    <Button variant="ghost" size="icon" className="h-8 w-8">
                        <BarChart3 className="h-4 w-4" />
                    </Button>

                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={handleAIAnalyze}
                        disabled={isAnalyzing}
                        className="gap-1"
                    >
                        <Sparkles className={`h-4 w-4 ${isAnalyzing ? 'animate-spin' : ''}`} />
                        Analyze
                    </Button>
                </div>

                {/* Formula Bar */}
                <div className="flex items-center gap-2 p-2 bg-background border rounded-lg">
                    <Badge variant="outline" className="font-mono">
                        {selectedCell ? `${generateColumnLabel(selectedCell.col)}${selectedCell.row + 1}` : '-'}
                    </Badge>
                    <span className="text-muted-foreground">fx</span>
                    <Input
                        value={formulaBarValue}
                        onChange={(e) => handleFormulaBarChange(e.target.value)}
                        className="flex-1 font-mono text-sm"
                        placeholder="Enter value or formula (e.g., =SUM(A1:A10))"
                    />
                </div>

                {/* Row/Column Controls */}
                <div className="flex items-center gap-2">
                    <Button variant="outline" size="sm" onClick={addRow}>
                        <Plus className="h-3 w-3 mr-1" />
                        Row
                    </Button>
                    <Button variant="outline" size="sm" onClick={addColumn}>
                        <Plus className="h-3 w-3 mr-1" />
                        Column
                    </Button>
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={deleteRow}
                        disabled={!selectedCell}
                    >
                        <Trash2 className="h-3 w-3 mr-1" />
                        Delete Row
                    </Button>
                </div>

                {/* Spreadsheet Grid */}
                <div className="border rounded-lg overflow-auto max-h-[500px]">
                    <table className="w-full border-collapse">
                        <thead className="sticky top-0 bg-muted z-10">
                            <tr>
                                <th className="w-12 border-b border-r p-2 text-xs text-muted-foreground">#</th>
                                {columns.map((col) => (
                                    <th
                                        key={col.id}
                                        className="border-b border-r p-2 text-xs font-medium text-center min-w-[100px]"
                                        style={{ width: col.width }}
                                    >
                                        {col.header}
                                    </th>
                                ))}
                            </tr>
                        </thead>
                        <tbody>
                            {data.map((row, rowIndex) => (
                                <tr key={rowIndex} className="hover:bg-muted/30">
                                    <td className="border-r p-2 text-xs text-muted-foreground text-center bg-muted/50">
                                        {rowIndex + 1}
                                    </td>
                                    {row.map((cell, colIndex) => (
                                        <td
                                            key={colIndex}
                                            className={`border-r border-b p-0 ${selectedCell?.row === rowIndex && selectedCell?.col === colIndex
                                                ? 'ring-2 ring-primary ring-inset'
                                                : ''
                                                }`}
                                            onClick={() => handleCellSelect(rowIndex, colIndex)}
                                        >
                                            <input
                                                value={String(cell.value)}
                                                onChange={(e) => handleCellChange(rowIndex, colIndex, e.target.value)}
                                                className={`w-full h-full p-2 text-sm bg-transparent border-none focus:outline-none ${cell.format?.bold ? 'font-bold' : ''
                                                    } ${cell.format?.italic ? 'italic' : ''
                                                    } text-${cell.format?.align || 'left'}`}
                                            />
                                        </td>
                                    ))}
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>

                {/* Status Bar */}
                <div className="flex items-center justify-between text-xs text-muted-foreground pt-2 border-t">
                    <div className="flex items-center gap-4">
                        <span>{data.length} rows × {columns.length} columns</span>
                        {selectedCell && (
                            <span>
                                Selected: {generateColumnLabel(selectedCell.col)}{selectedCell.row + 1}
                            </span>
                        )}
                    </div>
                    <div className="flex items-center gap-2">
                        <FileSpreadsheet className="h-3 w-3" />
                        <span>Spreadsheet Canvas</span>
                    </div>
                </div>
            </CardContent>
        </Card>
    );
}

export default SpreadsheetCanvas;
