import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { RefreshCw, Settings2 } from 'lucide-react';
import { toast } from 'sonner';

interface PipelineConfig {
    mode: 'scheduled' | 'real_time';
    cron: string;
}

interface PipelineSettings {
    [key: string]: PipelineConfig;
}

interface PipelineSettingsPanelProps {
    isOpen: boolean;
    onClose?: () => void;
}

export const PipelineSettingsPanel: React.FC<PipelineSettingsPanelProps> = ({ isOpen, onClose }) => {
    const [pipelineSettings, setPipelineSettings] = useState<PipelineSettings | null>(null);
    const [isSaving, setIsSaving] = useState(false);
    const [isLoading, setIsLoading] = useState(true);

    useEffect(() => {
        if (isOpen) {
            fetchSettings();
        }
    }, [isOpen]);

    const fetchSettings = async () => {
        try {
            setIsLoading(true);
            const res = await fetch('/api/v1/settings/automations/');
            if (res.ok) {
                const data = await res.json();
                setPipelineSettings(data.pipelines || {});
            }
        } catch (error) {
            console.error('Failed to fetch pipeline settings:', error);
            toast.error('Failed to load sync settings');
        } finally {
            setIsLoading(false);
        }
    };

    const togglePipelineMode = async (pipeline: string) => {
        if (!pipelineSettings) return;

        const current = pipelineSettings[pipeline] || { mode: 'scheduled', cron: '*/30 * * * *' };
        const newMode = current.mode === 'real_time' ? 'scheduled' : 'real_time';

        const newSettings: PipelineSettings = {
            ...pipelineSettings,
            [pipeline]: { ...current, mode: newMode as 'scheduled' | 'real_time' }
        };

        try {
            setIsSaving(true);
            const res = await fetch('/api/v1/settings/automations/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ pipelines: newSettings })
            });

            if (res.ok) {
                setPipelineSettings(newSettings);
                toast.success(`${pipeline.charAt(0).toUpperCase() + pipeline.slice(1)} pipeline switched to ${newMode}`);
            }
        } catch (error) {
            toast.error('Failed to update pipeline settings');
        } finally {
            setIsSaving(false);
        }
    };

    if (!isOpen) return null;

    return (
        <Card className="bg-black/40 border-white/5 backdrop-blur-xl mb-6 animate-in slide-in-from-top-2 duration-300">
            <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <Settings2 className="w-4 h-4 text-primary" />
                        Memory Pipeline Ingestion Modes
                    </div>
                    <Badge variant="outline" className="text-[10px] bg-primary/10 text-primary border-primary/20">
                        Global Configuration
                    </Badge>
                </CardTitle>
            </CardHeader>
            <CardContent className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-4">
                {isLoading ? (
                    Array.from({ length: 3 }).map((_, i) => (
                        <div key={i} className="h-24 rounded-lg bg-white/5 animate-pulse" />
                    ))
                ) : (
                    ['sales', 'projects', 'finance'].map((p) => (
                        <div key={p} className="flex flex-col gap-2 p-3 rounded-lg bg-white/5 border border-white/10 hover:bg-white/10 transition-colors">
                            <div className="flex items-center justify-between">
                                <span className="text-sm font-semibold capitalize text-white">{p} Pipeline</span>
                                <Badge className={pipelineSettings?.[p]?.mode === 'real_time' ? 'bg-green-500/20 text-green-400' : 'bg-blue-500/20 text-blue-400'}>
                                    {pipelineSettings?.[p]?.mode === 'real_time' ? 'Real-Time' : 'Scheduled'}
                                </Badge>
                            </div>
                            <p className="text-[10px] text-muted-foreground">
                                {pipelineSettings?.[p]?.mode === 'real_time'
                                    ? 'Continuous ingestion (60s poll loop)'
                                    : `Running on cron: ${pipelineSettings?.[p]?.cron || 'standard'}`}
                            </p>
                            <Button
                                size="sm"
                                variant="ghost"
                                disabled={isSaving}
                                className="h-7 text-[11px] hover:bg-primary/20 hover:text-primary transition-all mt-1"
                                onClick={() => togglePipelineMode(p)}
                            >
                                <RefreshCw className={`w-3 h-3 mr-1.5 ${isSaving ? 'animate-spin' : ''}`} />
                                Switch to {pipelineSettings?.[p]?.mode === 'real_time' ? 'Scheduled' : 'Real-Time'}
                            </Button>
                        </div>
                    ))
                )}
            </CardContent>
        </Card>
    );
};
