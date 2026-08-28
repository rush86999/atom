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

interface MailHistorySettings {
    outlook: string;
    gmail: string;
    imap: string;
}

const MAIL_HISTORY_FIELDS: { key: keyof MailHistorySettings; label: string }[] = [
    { key: 'outlook', label: 'Outlook' },
    { key: 'gmail', label: 'Gmail' },
    { key: 'imap', label: 'IMAP / Other' },
];

const DEFAULT_HISTORY_DAYS = '90';

export const PipelineSettingsPanel: React.FC<PipelineSettingsPanelProps> = ({ isOpen, onClose }) => {
    const [pipelineSettings, setPipelineSettings] = useState<PipelineSettings | null>(null);
    const [historyDays, setHistoryDays] = useState<MailHistorySettings>({
        outlook: DEFAULT_HISTORY_DAYS,
        gmail: DEFAULT_HISTORY_DAYS,
        imap: DEFAULT_HISTORY_DAYS,
    });
    const [isSaving, setIsSaving] = useState(false);
    const [isSavingHistory, setIsSavingHistory] = useState(false);
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
                setHistoryDays({
                    outlook: String(data.outlook_history_days ?? 90),
                    gmail: String(data.gmail_history_days ?? 90),
                    imap: String(data.email_history_days ?? 90),
                });
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

    const saveHistoryDays = async () => {
        const payload: Record<string, number> = {};
        for (const { key, label } of MAIL_HISTORY_FIELDS) {
            const days = parseInt(historyDays[key], 10);
            if (isNaN(days) || days < 1 || days > 3650) {
                toast.error(`${label}: history must be between 1 and 3650 days`);
                return;
            }
            const settingKey = key === 'imap' ? 'email_history_days' : `${key}_history_days`;
            payload[settingKey] = days;
        }

        try {
            setIsSavingHistory(true);
            const res = await fetch('/api/v1/settings/automations/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (res.ok) {
                toast.success('Mail sync history saved — applies to each integration\u2019s first connect');
            } else {
                const err = await res.json().catch((): null => null);
                toast.error(err?.detail || 'Failed to update history setting');
            }
        } catch (error) {
            toast.error('Failed to update history setting');
        } finally {
            setIsSavingHistory(false);
        }
    };

    if (!isOpen) return null;

    return (
        <Card className="bg-black/5 dark:bg-black/40 border-black/5 dark:border-white/5 backdrop-blur-xl mb-6 animate-in slide-in-from-top-2 duration-300">
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
                        <div key={i} className="h-24 rounded-lg bg-black/5 dark:bg-white/5 animate-pulse" />
                    ))
                ) : (
                    ['sales', 'projects', 'finance'].map((p) => (
                        <div key={p} className="flex flex-col gap-2 p-3 rounded-lg bg-black/5 dark:bg-white/5 border border-black/10 dark:border-white/10 hover:bg-black/10 dark:hover:bg-black/10 dark:bg-white/10 transition-colors">
                            <div className="flex items-center justify-between">
                                <span className="text-sm font-semibold capitalize text-gray-900 dark:text-white">{p} Pipeline</span>
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
                <div className="md:col-span-3 flex flex-col gap-3 p-3 rounded-lg bg-black/5 dark:bg-white/5 border border-black/10 dark:border-white/10">
                    <div>
                        <span className="text-sm font-semibold text-gray-900 dark:text-white">Mail Sync History</span>
                        <p className="text-[10px] text-muted-foreground">
                            How much mailbox history each integration ingests on first connect (default: 3 months / 90 days)
                        </p>
                    </div>
                    <div className="flex flex-wrap items-end gap-3">
                        {MAIL_HISTORY_FIELDS.map(({ key, label }) => (
                            <div key={key} className="flex items-center gap-1.5">
                                <label className="text-[11px] text-muted-foreground" htmlFor={`history-${key}`}>{label}</label>
                                <input
                                    id={`history-${key}`}
                                    type="number"
                                    min={1}
                                    max={3650}
                                    value={historyDays[key]}
                                    onChange={(e) => setHistoryDays({ ...historyDays, [key]: e.target.value })}
                                    className="w-20 h-7 rounded-md bg-white/60 dark:bg-black/40 border border-black/10 dark:border-white/10 px-2 text-xs text-gray-900 dark:text-white"
                                    aria-label={`${label} history in days`}
                                />
                                <span className="text-[11px] text-muted-foreground">days</span>
                            </div>
                        ))}
                        <Button
                            size="sm"
                            variant="ghost"
                            disabled={isSavingHistory}
                            className="h-7 text-[11px] hover:bg-primary/20 hover:text-primary transition-all"
                            onClick={saveHistoryDays}
                        >
                            <Settings2 className={`w-3 h-3 mr-1.5 ${isSavingHistory ? 'animate-spin' : ''}`} />
                            Save
                        </Button>
                    </div>
                </div>
            </CardContent>
        </Card>
    );
};
